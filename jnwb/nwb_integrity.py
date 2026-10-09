"""Read-only integrity checks for the ragged columns of an NWB table, and one guarded repair.

An NWB table stores a ragged column (``spike_times``, ``waveform_mean``, ...) as a flat data
array plus an integer ``<column>_index`` array holding, per row, the END offset of that row's
slice (exclusive, 0-based, cumulative over the whole table), so row ``i`` is
``data[index[i-1]:index[i]]`` with ``index[-1]`` read as 0 for the first row (HDMF
``VectorIndex``). A correct index is therefore non-negative and non-decreasing, its last element
equals the first-axis length of the data (an empty index requires empty data), and its dtype can
hold that length.

Known writer defect (observed in files written by one MATLAB-based multi-probe writer):
when units are appended probe by probe, the index of every probe after the first is offset by
the FIRST element of the existing index instead of its last element (the running total). The
flat data are complete and in row order; only the index is wrong, so those rows slice into
earlier probes' data. ``check_ragged_indices`` detects it; ``repair_ragged_index`` writes the
corrected index to a new file, or in place on request, under the refusal rules stated on that
function.

Waveform blocks need a different check. A unit's ``waveform_mean`` block is sliced from the
flat data by ``waveform_mean_index``, and nothing ties the sliced block to the unit: a file
whose blocks are stored out of unit order reads another unit's block through pynwb with no
warning. ``check_waveform_blocks`` compares each sliced block's row amplitudes against the
unit's stored ``amplitude`` and reports, per unit, whether the block is owned, unowned, or
unknown. It repairs nothing and reassigns nothing: a match is evidence the block is the
unit's, never a license to move one.
"""

from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

import h5py
import numpy as np
from jnwb.addressing import _finite_cutoff

#: ``"detected"``: the index equals the known defect's formula and the corrected index ends at
#: the data length. ``"absent"``: the index equals the corrected one. ``"not_tested"``: no probe
#: segmentation was given. ``"inconsistent"``: neither, so the file is damaged some other way.
OffsetBug = Literal["detected", "absent", "not_tested", "inconsistent"]


class RaggedIndexRepairRefused(ValueError):
    """``repair_ragged_index`` found a condition under which it must not write."""


@dataclass(frozen=True)
class RaggedIndexCheck:
    """Status of one ``<column>_index`` array. Every flag is a plain observation.

    ``monotonic`` is non-decreasing; ``ends_at_data_len`` is ``index[-1] == len(data)``, or
    ``len(data) == 0`` for an empty index; ``length_fits`` is that ``len(data)`` is
    representable in ``index_type``; ``offset_bug`` is described by ``OffsetBug``;
    ``nonnegative`` is ``index[0] >= 0`` (True for an empty index). ``corrected_index`` is the
    index a repair would write, ``None`` unless ``offset_bug == "detected"``.
    """

    column: str
    n_rows: int
    data_len: int
    index_type: str
    monotonic: bool
    ends_at_data_len: bool
    length_fits: bool
    offset_bug: OffsetBug
    corrected_index: np.ndarray | None = None
    nonnegative: bool = True

    @property
    def ok(self) -> bool:
        return (self.monotonic and self.nonnegative and self.ends_at_data_len
                and self.length_fits and self.offset_bug in ("absent", "not_tested"))


@dataclass(frozen=True)
class RaggedIndexReport:
    """All ragged columns of one table. ``unlisted_ragged_columns`` are datasets that have a
    ``<name>_index`` partner but are absent from the table's ``colnames`` attribute, which makes
    pynwb hide them. ``ok`` is every column ``ok`` and no unlisted column."""

    file: str
    table: str
    n_rows: int
    columns: tuple[RaggedIndexCheck, ...]
    unlisted_ragged_columns: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.columns) and not self.unlisted_ragged_columns


@dataclass(frozen=True)
class RaggedIndexRepair:
    """Outcome of ``repair_ragged_index``. ``written`` is False for a dry run and True only
    after the written index was re-read, checked and moved into place; ``output_path`` is the
    file that holds it (``None`` for a dry run)."""

    column: str
    written: bool
    rows_changed: int
    old_index: np.ndarray
    new_index: np.ndarray
    output_path: str | None = None


def _decode(x) -> str:
    return x.decode() if isinstance(x, bytes) else str(x)


def _segment_starts(n_rows: int, probe_starts: Sequence[int] | None, labels) -> np.ndarray | None:
    """0-based row positions where a probe begins, or None when no segmentation was given."""
    if probe_starts is not None:
        starts = np.asarray(probe_starts, dtype=np.int64).ravel()
    elif labels is not None:
        lab = np.asarray(labels)
        if lab.shape[0] != n_rows:
            raise ValueError(f"probe_column has {lab.shape[0]} values for {n_rows} rows")
        starts = np.r_[0, np.flatnonzero(lab[1:] != lab[:-1]) + 1].astype(np.int64)
    else:
        return None
    if starts.size == 0 or starts[0] != 0 or np.any(np.diff(starts) <= 0) or starts[-1] >= n_rows:
        raise ValueError("probe_starts must be strictly increasing row positions in "
                         f"[0, {n_rows}) beginning at 0")
    return starts


def _corrected_from_buggy(old: np.ndarray, starts: np.ndarray) -> np.ndarray | None:
    """Per-row ends under the hypothesis that ``old`` carries the defect, or None when the
    hypothesis implies a negative row length.

    Within probe p the diffs of ``old`` are the true row lengths of all rows but the first;
    that row's length is ``old[start] - old[0]`` for p > 0 (the defect offsets by ``old[0]``)
    and ``old[0]`` for p == 0.
    """
    old = old.astype(np.int64)
    counts = np.empty(old.size, dtype=np.int64)
    counts[1:] = np.diff(old)
    counts[0] = old[0]
    for s in starts[1:]:
        counts[s] = old[s] - old[0]
    if np.any(counts < 0):
        return None
    return np.cumsum(counts)


def _classify(old: np.ndarray, data_len: int, starts: np.ndarray | None):
    if starts is None:
        return "not_tested", None
    old64 = old.astype(np.int64)
    # Correct layout: segment boundaries need no special case, ends are a plain running total
    # from 0, so every row length (including the first) is non-negative.
    if old64.size and np.all(np.diff(old64, prepend=0) >= 0) and old64[-1] == data_len:
        return "absent", None
    new = _corrected_from_buggy(old64, starts)
    if new is None or new[-1] != data_len or starts.size < 2:
        return "inconsistent", None
    return ("detected", new) if not np.array_equal(new, old64) else ("absent", None)


def _group(f: h5py.File, table: str) -> h5py.Group:
    if table not in f or not isinstance(f[table], h5py.Group):
        raise KeyError(f"no table group {table!r} in the file")
    return f[table]


def _labels(g: h5py.Group, probe_column: str | None):
    if probe_column is None:
        return None
    if probe_column not in g:
        raise KeyError(f"probe_column {probe_column!r} is not a column of the table")
    return g[probe_column][()]


def _check_group(g: h5py.Group, starts_arg, probe_column) -> tuple[RaggedIndexCheck, ...]:
    checks = []
    labels = _labels(g, probe_column)
    for key in g:
        if not key.endswith("_index") or key[:-6] not in g:
            continue
        data, idx = g[key[:-6]], g[key]
        if not isinstance(data, h5py.Dataset) or not isinstance(idx, h5py.Dataset):
            continue
        old = idx[()]
        n = int(old.size)
        starts = _segment_starts(n, starts_arg, labels) if n else None
        data_len = int(data.shape[0])
        integer = np.issubdtype(idx.dtype, np.integer)
        fits = bool(integer and data_len <= np.iinfo(idx.dtype).max)
        if not integer:
            checks.append(RaggedIndexCheck(key[:-6], n, data_len, str(idx.dtype), False, False,
                                           False, "inconsistent"))
            continue
        bug, new = _classify(old, data_len, starts)
        checks.append(RaggedIndexCheck(
            key[:-6], n, data_len, str(idx.dtype),
            bool(np.all(np.diff(old.astype(np.int64)) >= 0)),
            bool((int(old[-1]) if n else 0) == data_len), fits, bug, new,
            nonnegative=bool(n == 0 or int(old[0]) >= 0)))
    return tuple(checks)


def check_ragged_indices(path: str | Path, *, table: str = "units",
                         probe_starts: Sequence[int] | None = None,
                         probe_column: str | None = None) -> RaggedIndexReport:
    """Check every ``<column>_index`` of one table of an NWB file, without writing.

    Parameters
    ----------
    path : str or Path
        NWB (HDF5) file, opened read-only.
    table : str
        HDF5 path of the table group (default ``"units"``).
    probe_starts : sequence of int, optional
        0-based row positions where each probe's rows begin; the first must be 0. Needed for
        the offset-defect test. From a per-probe counter column ``c`` that restarts at 0:
        ``np.flatnonzero(c == 0)``.
    probe_column : str, optional
        Alternative to ``probe_starts``: a column whose value changes at each probe boundary
        (a probe or group label). Give at most one of the two.

    Returns
    -------
    RaggedIndexReport
        One ``RaggedIndexCheck`` per ragged column, in file order. Without a segmentation
        ``offset_bug`` is ``"not_tested"``. A single probe cannot show the defect, so with one
        segment a non-correct index is ``"inconsistent"``.

    Notes
    -----
    Nothing is modified or repaired. The defect test reconstructs row lengths under the
    defect's formula and accepts it only when they are non-negative and the corrected index
    ends at the data length; a file that fails both tests is ``"inconsistent"``.
    """
    if probe_starts is not None and probe_column is not None:
        raise ValueError("give probe_starts or probe_column, not both")
    path = Path(path)
    with h5py.File(path, "r") as f:
        g = _group(f, table)
        cols = _check_group(g, probe_starts, probe_column)
        listed = {_decode(c) for c in g.attrs.get("colnames", [])}
        unlisted = tuple(c.column for c in cols
                         if c.column not in listed and f"{c.column}_index" not in listed)
        n_rows = int(g["id"].shape[0]) if "id" in g else 0
    return RaggedIndexReport(path.name, table, n_rows, cols, unlisted)


def repair_ragged_index(path: str | Path, column: str, *, table: str = "units",
                        probe_starts: Sequence[int] | None = None,
                        probe_column: str | None = None, dry_run: bool = True,
                        output_path: str | Path | None = None, in_place: bool = False,
                        backup_path: str | Path | None = None) -> RaggedIndexRepair:
    """Correct one ragged index that carries the multi-probe offset defect.

    Defaults to a dry run, which returns the planned change and writes nothing. With
    ``dry_run=False`` the input is copied, only ``<column>_index`` of the copy is overwritten
    (same dtype and shape), and the copy is re-read and checked before it is moved, with
    ``os.replace``, to ``output_path`` (a new file; the input is left as it was) or, with
    ``in_place=True``, over the input. A failure at any step leaves the input byte-identical
    and removes the copy and any backup this call wrote.

    Parameters
    ----------
    output_path : str or Path, optional
        The repaired file to create. It must not exist; the name is claimed exclusively just
        before the verified copy is moved onto it, so a file that appears meanwhile is refused,
        not overwritten.
    in_place : bool
        Replace the input instead. Needs ``backup_path`` and a writable input; a dry run needs
        neither and ignores ``backup_path``.
    backup_path : str or Path, optional
        With ``in_place=True`` only: receives the old index as ``.npz`` (key ``old_index``) at
        exactly this path, which must not exist.

    Raises
    ------
    RaggedIndexRepairRefused
        Before any write, when: the table has no such ragged column; the column's
        ``offset_bug`` is not ``"detected"`` (so the old index is not exactly the defect's
        formula); the corrected values do not fit the index dtype; ``dry_run=False`` without
        ``output_path`` or ``in_place=True``, or with both; ``in_place=True`` without
        ``backup_path``; ``backup_path`` without ``in_place=True``; ``output_path`` or
        ``backup_path`` exists (a dry run skips the two backup checks); or the input is not writable under ``in_place=True``. After the
        write to the copy and before anything is replaced, when the re-read index is not the
        corrected index or does not pass ``check_ragged_indices``.
    KeyError, ValueError
        As ``check_ragged_indices``.
    OSError
        From h5py or the file system, after the copy and backup are removed.

    Notes
    -----
    Restoring an in-place repair is ``ds[...] = np.load(backup_path)["old_index"]``. Other
    columns, the data and the attributes are never touched.
    """
    if not dry_run and output_path is None and not in_place:
        raise RaggedIndexRepairRefused("dry_run=False needs output_path or in_place=True")
    if output_path is not None and in_place:
        raise RaggedIndexRepairRefused("output_path and in_place=True exclude each other")
    if in_place and backup_path is None and not dry_run:
        raise RaggedIndexRepairRefused("in_place=True needs backup_path")
    if backup_path is not None and not in_place:
        raise RaggedIndexRepairRefused("backup_path applies only with in_place=True")
    path = Path(path)
    report = check_ragged_indices(path, table=table, probe_starts=probe_starts,
                                  probe_column=probe_column)
    check = next((c for c in report.columns if c.column == column), None)
    if check is None:
        raise RaggedIndexRepairRefused(f"{table} has no ragged column {column!r}")
    if check.offset_bug != "detected" or check.corrected_index is None:
        raise RaggedIndexRepairRefused(
            f"{column}_index is not the known offset defect (status {check.offset_bug!r}); "
            "refusing to write")
    new = check.corrected_index
    if not check.length_fits:
        raise RaggedIndexRepairRefused(f"data length {check.data_len} does not fit "
                                       f"{check.index_type}")
    dest = path if in_place else (Path(output_path) if output_path is not None else None)
    backup = Path(backup_path) if backup_path is not None else None
    if output_path is not None and dest.exists():
        raise RaggedIndexRepairRefused(f"output_path {dest} exists; not overwriting it")
    if backup is not None and not dry_run and backup.exists():
        raise RaggedIndexRepairRefused(f"backup_path {backup} exists; not overwriting it")
    if in_place and not os.access(path, os.W_OK):
        raise RaggedIndexRepairRefused(f"{path} is not writable; in-place repair refused")
    with h5py.File(path, "r") as f:
        old = f[f"{table}/{column}_index"][()]
    rows_changed = int(np.count_nonzero(old.astype(np.int64) != new))
    if dry_run:
        return RaggedIndexRepair(column, False, rows_changed, old, new.astype(old.dtype))
    _write_verified(path, dest, backup, old, new, table=table, column=column,
                    probe_starts=probe_starts, probe_column=probe_column)
    return RaggedIndexRepair(column, True, rows_changed, old, new.astype(old.dtype), str(dest))


def _write_verified(src: Path, dest: Path, backup: Path | None, old: np.ndarray,
                    new: np.ndarray, *, table: str, column: str, probe_starts,
                    probe_column) -> None:
    """Copy ``src``, write ``new`` into the copy's index, verify the copy by re-reading it, then
    ``os.replace`` it onto ``dest``. On any failure nothing but the copy and the backup this
    call created is touched, and both are removed."""
    tmp = dest.parent / f".{dest.name}.{uuid.uuid4().hex[:12]}.tmp"
    wrote_backup = False
    claimed = False
    try:
        shutil.copyfile(src, tmp)
        with h5py.File(tmp, "r+") as f:
            ds = f[f"{table}/{column}_index"]
            ds[...] = new.astype(ds.dtype)
        with h5py.File(tmp, "r") as f:
            written = f[f"{table}/{column}_index"][()]
        recheck = next(c for c in check_ragged_indices(
            tmp, table=table, probe_starts=probe_starts, probe_column=probe_column).columns
            if c.column == column)
        if not (recheck.ok and np.array_equal(written.astype(np.int64), new)):
            raise RaggedIndexRepairRefused(
                f"the written {column}_index did not verify (status {recheck.offset_bug!r}, "
                f"ok={recheck.ok}); nothing was replaced")
        if dest == src:
            shutil.copymode(src, tmp)
        if backup is not None:
            with open(backup, "xb") as fh:
                wrote_backup = True
                np.savez(fh, old_index=old)
        if dest != src:
            try:
                with open(dest, "xb"):
                    claimed = True
            except FileExistsError:
                raise RaggedIndexRepairRefused(
                    f"output_path {dest} exists; not overwriting it") from None
        os.replace(tmp, dest)
    except BaseException:
        if wrote_backup:
            backup.unlink(missing_ok=True)
        if claimed:
            dest.unlink(missing_ok=True)
        raise
    finally:
        tmp.unlink(missing_ok=True)


#: Ownership verdicts of one waveform block. ``"unknown"`` is explicit non-assignment:
#: the stored metadata cannot verify the block, so the check neither passes nor fails it.
WaveformOwnership = Literal["owned", "unowned", "unknown"]


@dataclass(frozen=True)
class WaveformBlockCheck:
    """One unit's index-sliced ``waveform_mean`` block against its stored ``amplitude``.

    ``status`` is ``"owned"`` when some row's peak-to-peak matches the stored amplitude
    within tolerance, ``"unowned"`` when the block is complete and no row matches, and
    ``"unknown"`` when there is nothing to compare (an empty block) or no finite
    reference (a NaN or infinite amplitude). ``matched_row`` is the first matching row,
    ``None`` unless owned; ``largest_row`` the first row of greatest peak-to-peak,
    ``None`` for an empty block; ``best_dev`` the smallest absolute deviation of a row's
    peak-to-peak from the stored amplitude, in the data's units, ``None`` when unknown.
    ``peak_channel_id`` is carried as stored (``None`` when the column is absent) so the
    caller can join it against the electrodes table; it is never a criterion, because a
    block row is not in general a channel id (on DANDI:000253 the ids run 2..5281
    against 384 block rows).
    """

    index: int
    unit_id: int
    status: WaveformOwnership
    matched_row: int | None
    largest_row: int | None
    n_rows: int
    stored_amplitude: float
    best_dev: float | None
    peak_channel_id: Any


@dataclass(frozen=True)
class WaveformBlockReport:
    """Every unit's waveform block of one table. ``ok`` is every unit ``"owned"``: an
    ``"unknown"`` is explicit uncertainty, not a pass. ``rtol``/``atol`` echo the
    tolerances the verdicts were computed with."""

    file: str
    table: str
    n_units: int
    rtol: float
    atol: float
    units: tuple[WaveformBlockCheck, ...]

    @property
    def ok(self) -> bool:
        return all(u.status == "owned" for u in self.units)

    @property
    def n_owned(self) -> int:
        return sum(u.status == "owned" for u in self.units)

    @property
    def n_unowned(self) -> int:
        return sum(u.status == "unowned" for u in self.units)

    @property
    def n_unknown(self) -> int:
        return sum(u.status == "unknown" for u in self.units)


def check_waveform_blocks(path: str | Path, *, table: str = "units",
                          rtol: float, atol: float = 0.0) -> WaveformBlockReport:
    """Check every unit's index-sliced ``waveform_mean`` block against its stored ``amplitude``.

    For each unit the block ``data[index[i - 1]:index[i]]`` is sliced exactly as pynwb
    slices it, and each row's peak-to-peak (max minus min) is compared with the unit's
    stored ``amplitude``. The unit is ``"owned"`` when some row matches within tolerance,
    on any row and not only the largest: on the DANDI:000253 file above, 238 of the 2446
    units (9.7%) match only on a smaller-than-largest row. It is ``"unowned"`` when the
    block is
    complete and no row matches, and ``"unknown"`` for an empty block or a missing, NaN
    or infinite amplitude.

    A match is necessary evidence, not sufficient proof: two units with indistinguishable
    amplitudes cannot be told apart by it. What the check never does is reassign: no
    block is moved, relabeled or guessed from its amplitude, so a wrong verdict misleads
    no downstream read.

    Parameters
    ----------
    path : str or Path
        NWB (HDF5) file, opened read-only.
    table : str
        HDF5 path of the table group (default ``"units"``).
    rtol : float
        Required relative tolerance of the amplitude match: a row matches when
        ``|ptp - amplitude| <= atol + rtol * |amplitude|``. Required, because no
        tolerance suits every writer: on DANDI:000253
        ``sub-621890_ses-1186358749_ogen.nwb`` (2446 units, blocks in unit order) every
        unit matches at ``rtol=1e-6`` while 47% miss exact equality, so an exact-only
        rule refuses nearly half of a correctly ordered file, and a loose rule accepts
        another unit's block. Pass what the file's precision justifies.
    atol : float
        Absolute term of the same match; 0.0 disables it. Pass a small voltage when
        amplitudes approach zero, where a relative tolerance decides nothing.

    Returns
    -------
    WaveformBlockReport
        One ``WaveformBlockCheck`` per unit, in row order.

    Raises
    ------
    KeyError
        The table, ``waveform_mean`` with its ``_index``, or ``amplitude`` is absent.
    ValueError
        ``rtol`` or ``atol`` is NaN, infinite or negative; ``amplitude`` is not a
        numeric column; a column's length is not one value per unit; the index is not
        an integer array slicing ``waveform_mean`` (non-integer, negative,
        decreasing, or out of bounds); or ``waveform_mean`` is not a 2-D array of
        ``(channel, sample)`` blocks.
    TypeError
        ``rtol`` or ``atol`` is ``None``, a boolean or not a real number.

    Notes
    -----
    Nothing is modified or repaired. An index that is itself misshapen is refused
    rather than attributed: run ``check_ragged_indices`` first when the index is
    suspect, since slices taken through a wrong index attribute the wrong rows.
    """

    def _refuse(message: str) -> ValueError:
        return ValueError(f"{table}: {message}")

    rtol = _finite_cutoff(rtol, "rtol", "check_waveform_blocks")
    atol = _finite_cutoff(atol, "atol", "check_waveform_blocks")
    if not rtol >= 0:
        raise ValueError(
            f"check_waveform_blocks: rtol must be >= 0, not {rtol!r}")
    if not atol >= 0:
        raise ValueError(
            f"check_waveform_blocks: atol must be >= 0, not {atol!r}")
    path = Path(path)
    with h5py.File(path, "r") as f:
        g = _group(f, table)
        for col in ("waveform_mean", "waveform_mean_index", "amplitude"):
            if col not in g or not isinstance(g[col], h5py.Dataset):
                raise KeyError(f"{table} has no column {col!r}")
        wm, wmi, amp_ds = g["waveform_mean"], g["waveform_mean_index"], g["amplitude"]
        if wm.ndim != 2:
            raise _refuse(f"waveform_mean has shape {wm.shape}; a mean-waveform block "
                          "is (channels, samples), so these rows cannot be attributed")
        if amp_ds.dtype.kind not in "fiub":
            raise _refuse(f"amplitude has dtype {amp_ds.dtype}, not numeric; a stored "
                          "amplitude it cannot be compared with is not a reference")
        if not np.issubdtype(wmi.dtype, np.integer):
            raise _refuse(f"waveform_mean_index has dtype {wmi.dtype}, not integer; "
                          "its slices cannot be taken")
        idx = wmi[()].astype(np.int64)
        n = int(idx.size)
        if np.any(idx < 0) or np.any(np.diff(idx) < 0) or np.any(idx > wm.shape[0]):
            raise _refuse("waveform_mean_index is negative, decreasing, or out of bounds; "
                          "slices taken through it attribute the wrong rows")
        amp = np.asarray(amp_ds[()], dtype=np.float64)
        if amp.shape != (n,):
            raise _refuse(f"amplitude holds {amp.size} values for {n} units; a column "
                          "with no one value per unit is not a reference")
        ids = (g["id"][()] if "id" in g and isinstance(g["id"], h5py.Dataset)
               else np.arange(n))
        if ids.shape != (n,):
            raise _refuse(f"id holds {ids.size} values for {n} units")
        pc = (g["peak_channel_id"][()]
              if "peak_channel_id" in g and isinstance(g["peak_channel_id"], h5py.Dataset)
              else None)
        if pc is not None and pc.shape != (n,):
            raise _refuse(f"peak_channel_id holds {pc.size} values for {n} units")
        starts = np.zeros(0, dtype=np.int64) if n == 0 else np.concatenate(
            ([0], idx[:-1])).astype(np.int64)
        units = []
        for i in range(n):
            block = wm[starts[i]:idx[i]]
            a = float(amp[i])
            n_rows = int(block.shape[0])
            prow = None if pc is None else (
                pc[i].item() if isinstance(pc[i], np.generic) else pc[i])
            uid = ids[i].item() if isinstance(ids[i], np.generic) else ids[i]
            if n_rows == 0 or not np.isfinite(a):
                units.append(WaveformBlockCheck(
                    i, int(uid), "unknown", None, None, 0, a, None, prow))
                continue
            ptp = block.max(axis=1) - block.min(axis=1)
            dev = np.abs(ptp - a)
            limit = atol + rtol * abs(a)
            matched = next((j for j in range(n_rows) if dev[j] <= limit), None)
            units.append(WaveformBlockCheck(
                i, int(uid), "owned" if matched is not None else "unowned", matched,
                int(np.argmax(ptp)), n_rows, a, float(dev.min()), prow))
    return WaveformBlockReport(path.name, table, n, rtol, atol, tuple(units))
