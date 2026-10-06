"""Read-only integrity checks for the ragged columns of an NWB table, and one guarded repair.

An NWB table stores a ragged column (``spike_times``, ``waveform_mean``, ...) as a flat data
array plus an integer ``<column>_index`` array holding, per row, the END offset of that row's
slice (exclusive, 0-based, cumulative over the whole table). A correct index is non-decreasing,
its last element equals the first-axis length of the data, and its dtype can hold that length.

Known writer defect (observed in files written by one MATLAB-based multi-probe writer):
when units are appended probe by probe, the index of every probe after the first is offset by
the FIRST element of the existing index instead of its last element (the running total). The
flat data are complete and in row order; only the index is wrong, so those rows slice into
earlier probes' data. ``check_ragged_indices`` detects it; ``repair_ragged_index`` rewrites the
one index in place under the refusal rules stated on that function.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

import h5py
import numpy as np

#: ``"detected"``: the index equals the known defect's formula and the corrected index ends at
#: the data length. ``"absent"``: the index equals the corrected one. ``"not_tested"``: no probe
#: segmentation was given. ``"inconsistent"``: neither, so the file is damaged some other way.
OffsetBug = Literal["detected", "absent", "not_tested", "inconsistent"]


class RaggedIndexRepairRefused(ValueError):
    """``repair_ragged_index`` found a condition under which it must not write."""


@dataclass(frozen=True)
class RaggedIndexCheck:
    """Status of one ``<column>_index`` array. Every flag is a plain observation.

    ``monotonic`` is non-decreasing; ``ends_at_data_len`` is ``index[-1] == len(data)``;
    ``length_fits`` is that ``len(data)`` is representable in ``index_type``;
    ``offset_bug`` is described by ``OffsetBug``. ``corrected_index`` is the index a repair
    would write, ``None`` unless ``offset_bug == "detected"``.
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

    @property
    def ok(self) -> bool:
        return (self.monotonic and self.ends_at_data_len and self.length_fits
                and self.offset_bug in ("absent", "not_tested"))


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
    """Outcome of ``repair_ragged_index``. ``written`` is False for a dry run."""

    column: str
    written: bool
    rows_changed: int
    old_index: np.ndarray
    new_index: np.ndarray


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
    # Correct layout: segment boundaries need no special case, ends are a plain running total.
    if np.all(np.diff(old64) >= 0) and old64.size and old64[-1] == data_len:
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
            bool(n > 0 and int(old[-1]) == data_len), fits, bug, new))
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
                        backup_path: str | Path | None = None) -> RaggedIndexRepair:
    """Correct one ragged index that carries the multi-probe offset defect.

    Defaults to a dry run, which returns the planned change and writes nothing. With
    ``dry_run=False`` the file is opened ``r+`` and only ``<column>_index`` is overwritten, with
    the same dtype and shape.

    Raises
    ------
    RaggedIndexRepairRefused
        Before any write, when: no segmentation is given; the column's ``offset_bug`` is not
        ``"detected"`` (so the old index is not exactly the defect's formula); the corrected
        index does not end at the data length; the corrected values do not fit the index dtype;
        ``dry_run=False`` without ``backup_path``; or ``backup_path`` already exists.

    Notes
    -----
    ``backup_path`` receives the old index as an ``.npz`` (key ``old_index``) before the write;
    restoring is ``ds[...] = np.load(backup_path)["old_index"]``. Other columns, the data and
    the attributes are never touched.
    """
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
    if int(new[-1]) != check.data_len:
        raise RaggedIndexRepairRefused("corrected index does not end at the data length")
    if not check.length_fits:
        raise RaggedIndexRepairRefused(f"data length {check.data_len} does not fit "
                                       f"{check.index_type}")
    with h5py.File(path, "r") as f:
        old = f[f"{table}/{column}_index"][()]
    if not dry_run:
        if backup_path is None:
            raise RaggedIndexRepairRefused("dry_run=False needs backup_path")
        backup = Path(backup_path)
        if backup.exists():
            raise RaggedIndexRepairRefused(f"{backup} exists; not overwriting a backup")
        np.savez(backup, old_index=old)
        with h5py.File(path, "r+") as f:
            ds = f[f"{table}/{column}_index"]
            ds[...] = new.astype(ds.dtype)
    return RaggedIndexRepair(column, not dry_run, int(np.count_nonzero(old.astype(np.int64) != new)),
                             old, new.astype(old.dtype))
