"""One call that checks an NWB file against the validators a file has to pass to be published.

``validate_nwb`` runs up to six layers and returns one ``NWBValidationReport``:

``read``
    the file opens through ``jnwb.read_nwb`` (so it is readable by the installed pynwb and jnwb).
``pynwb_schema``
    ``pynwb.validate`` against the namespaces cached inside the file.
``pynwb_core``
    ``pynwb.validate`` against the core namespace of the installed pynwb, i.e. the newest schema
    the installed release knows.
``integrity``
    ragged ``<column>_index`` arrays of the units table (``check_ragged_indices``) and electrode
    regions that point outside the electrodes table. A region may repeat a row (one column per
    unit, several units on one electrode), so repeats are not flagged.
``nwbinspector``
    the NWB Inspector best-practice checks (optional dependency).
``dandi``
    ``dandi validate`` through its Python API (optional dependency): DANDI's own NWB metadata
    requirements.

A layer whose dependency is not installed is reported ``"skipped"`` with the reason; it is never
counted as a pass. ``NWBValidationReport.dandi_ready`` is True only when the ``dandi`` layer
actually ran and found no error.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Callable, Literal, Sequence

import h5py
import numpy as np

LayerStatus = Literal["pass", "fail", "skipped"]

#: Every layer name, in the order ``validate_nwb`` runs them.
LAYERS: tuple[str, ...] = ("read", "pynwb_schema", "pynwb_core", "integrity", "nwbinspector", "dandi")

#: DANDI result ids ignored by default.
DEFAULT_DANDI_IGNORE: tuple[str, ...] = ("DANDI.NO_DANDISET_FOUND",)

_DANDI_FAIL = ("ERROR", "CRITICAL")


@dataclass(frozen=True)
class ValidationLayer:
    """Outcome of one layer. ``messages`` holds at most ``max_messages`` strings; the counts are
    complete. ``n_warnings`` counts findings that do not fail the layer. ``detail`` states why a
    layer was skipped, or what it ran."""

    name: str
    status: LayerStatus
    n_errors: int = 0
    n_warnings: int = 0
    messages: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class NWBValidationReport:
    """All layers of one file, plus the versions that produced them."""

    file: str
    versions: dict
    layers: tuple[ValidationLayer, ...]

    def layer(self, name: str) -> ValidationLayer:
        for lay in self.layers:
            if lay.name == name:
                return lay
        raise KeyError(f"no layer {name!r}; ran {[x.name for x in self.layers]}")

    @property
    def ok(self) -> bool:
        """No layer that ran failed. Skipped layers do not fail it; see ``complete``."""
        return all(x.status != "fail" for x in self.layers)

    @property
    def complete(self) -> bool:
        """Every layer ran (none skipped)."""
        return all(x.status != "skipped" for x in self.layers)

    @property
    def dandi_ready(self) -> bool:
        """The ``dandi`` layer ran and passed, and so did the file's reading and both pynwb
        schema layers. False when the dandi layer was skipped or not requested."""
        by = {x.name: x for x in self.layers}
        need = ("read", "pynwb_schema", "pynwb_core", "dandi")
        return all(n in by and by[n].status == "pass" for n in need)

    def summary(self) -> str:
        rows = [f"{self.file}  ok={self.ok} complete={self.complete} dandi_ready={self.dandi_ready}"]
        for x in self.layers:
            tail = f" ({x.detail})" if x.detail else ""
            rows.append(f"  {x.name:<13} {x.status:<7} errors={x.n_errors} warnings={x.n_warnings}{tail}")
        return "\n".join(rows)


def _version(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        return None


def _layer_read(path: Path, cap: int) -> ValidationLayer:
    from jnwb.nwb_io import read_nwb
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            read_nwb(path)
    except Exception as exc:  # any failure to read is the finding
        return ValidationLayer("read", "fail", 1, 0, (f"{type(exc).__name__}: {exc}"[:500],))
    return ValidationLayer("read", "pass", detail="opened with jnwb.read_nwb")


def _layer_pynwb(path: Path, name: str, cap: int) -> ValidationLayer:
    import pynwb
    try:
        if name == "pynwb_schema":
            errors = pynwb.validate(path=str(path), use_cached_namespaces=True)
            detail = "namespaces cached in the file"
        else:
            errors = pynwb.validate(path=str(path), namespace="core", use_cached_namespaces=False)
            detail = f"core namespace of pynwb {pynwb.__version__}"
    except Exception as exc:
        return ValidationLayer(name, "fail", 1, 0, (f"{type(exc).__name__}: {exc}"[:500],))
    msgs = tuple(str(e)[:500] for e in errors)
    return ValidationLayer(name, "fail" if msgs else "pass", len(msgs), 0, msgs[:cap], detail)


def _electrode_region_problems(f: h5py.File) -> list[str]:
    out: list[str] = []
    ee = f.get("general/extracellular_ephys/electrodes")
    n_elec = int(ee["id"].shape[0]) if ee is not None and "id" in ee else None

    def visit(name: str, obj) -> None:
        if (isinstance(obj, h5py.Dataset) and name.rsplit("/", 1)[-1] == "electrodes"
                and obj.attrs.get("neurodata_type") in (b"DynamicTableRegion", "DynamicTableRegion")
                and name.startswith(("acquisition", "processing"))):
            rows = obj[:].astype(np.int64)
            if n_elec is not None and len(rows) and (rows.min() < 0 or rows.max() >= n_elec):
                out.append(f"/{name}: rows {int(rows.min())}..{int(rows.max())} outside electrodes table of {n_elec} rows")

    f.visititems(visit)
    return out


def _layer_integrity(path: Path, cap: int) -> ValidationLayer:
    from jnwb.nwb_integrity import check_ragged_indices
    msgs: list[str] = []
    try:
        with h5py.File(path, "r") as f:
            has_units = "units" in f
            msgs.extend(_electrode_region_problems(f))
        if has_units:
            rep = check_ragged_indices(path)
            for c in rep.columns:
                if not c.ok:
                    msgs.append(f"units/{c.column}_index: monotonic={c.monotonic} nonnegative={c.nonnegative} "
                                f"ends_at_data_len={c.ends_at_data_len} "
                                f"length_fits={c.length_fits} offset_bug={c.offset_bug}")
            msgs.extend(f"units/{c}: ragged column missing from colnames" for c in rep.unlisted_ragged_columns)
    except Exception as exc:
        msgs.append(f"{type(exc).__name__}: {exc}"[:500])
    return ValidationLayer("integrity", "fail" if msgs else "pass", len(msgs), 0, tuple(msgs[:cap]),
                           "ragged indices of units, electrode regions")


def _layer_inspector(path: Path, cap: int) -> ValidationLayer:
    try:
        import nwbinspector
    except ImportError:
        return ValidationLayer("nwbinspector", "skipped", detail="nwbinspector is not installed (pip install jnwb[validate])")
    try:
        found = [m for m in nwbinspector.inspect_nwbfile(nwbfile_path=str(path)) if m is not None]
    except Exception as exc:
        return ValidationLayer("nwbinspector", "fail", 1, 0, (f"{type(exc).__name__}: {exc}"[:500],))
    hard = [m for m in found if m.importance.name in ("CRITICAL", "ERROR")]
    soft = [m for m in found if m.importance.name not in ("CRITICAL", "ERROR")]
    soft.sort(key=lambda m: m.importance.name != "BEST_PRACTICE_VIOLATION")   # violations before suggestions
    shown = tuple(f"{m.importance.name} {m.check_function_name} {m.object_type}:{m.object_name}: {m.message}"[:500]
                  for m in hard + soft)
    return ValidationLayer("nwbinspector", "fail" if hard else "pass", len(hard), len(soft), shown[:cap],
                           "CRITICAL and ERROR fail; best-practice findings are warnings")


def _dandi_validate() -> Callable | None:
    try:
        from dandi.validate import validate
        return validate
    except ImportError:
        pass
    try:
        from dandi.validate._core import validate
        return validate
    except ImportError:
        return None


def _layer_dandi(path: Path, ignore: Sequence[str], cap: int) -> ValidationLayer:
    try:
        import dandi  # noqa: F401
    except ImportError:
        return ValidationLayer("dandi", "skipped", detail="dandi is not installed (pip install jnwb[validate])")
    validate = _dandi_validate()
    if validate is None:
        return ValidationLayer("dandi", "skipped", detail="installed dandi exposes no validate() entry point")
    try:
        results = [r for r in validate(str(path)) if (r.id or "") not in set(ignore)]
    except Exception as exc:
        return ValidationLayer("dandi", "fail", 1, 0, (f"{type(exc).__name__}: {exc}"[:500],))
    hard = [r for r in results if r.severity is not None and r.severity.name in _DANDI_FAIL]
    soft = [r for r in results if r not in hard]
    shown = tuple(f"{r.severity.name if r.severity else '?'} {r.id}: {r.message or ''}"[:500] for r in hard + soft)
    return ValidationLayer("dandi", "fail" if hard else "pass", len(hard), len(soft), shown[:cap],
                           f"dandi {_version('dandi')}; ignored ids: {', '.join(ignore) or 'none'}")


def validate_nwb(path: str | Path, *, layers: Sequence[str] | None = None,
                 dandi_ignore: Sequence[str] = DEFAULT_DANDI_IGNORE,
                 max_messages: int = 50) -> NWBValidationReport:
    """Validate one NWB file and report every layer. Read-only; nothing is written.

    Parameters
    ----------
    path : str or Path
        NWB (HDF5) file.
    layers : sequence of str, optional
        Subset of ``LAYERS`` to run, in that order. Default: all six.
    dandi_ignore : sequence of str
        DANDI result ids to drop before judging the ``dandi`` layer (default: the
        no-dandiset-found notice).
    max_messages : int
        Messages kept per layer; the counts stay complete.

    Returns
    -------
    NWBValidationReport
        ``ok`` (no layer failed), ``complete`` (no layer skipped) and ``dandi_ready`` (the dandi
        layer ran and passed, as did ``read`` and both pynwb layers).

    Raises
    ------
    FileNotFoundError
        ``path`` does not exist.
    ValueError
        ``layers`` names something not in ``LAYERS``.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    want = tuple(LAYERS if layers is None else layers)
    unknown = [x for x in want if x not in LAYERS]
    if unknown:
        raise ValueError(f"unknown layers {unknown}; choose from {list(LAYERS)}")
    want = tuple(x for x in LAYERS if x in want)
    runners = {
        "read": lambda: _layer_read(path, max_messages),
        "pynwb_schema": lambda: _layer_pynwb(path, "pynwb_schema", max_messages),
        "pynwb_core": lambda: _layer_pynwb(path, "pynwb_core", max_messages),
        "integrity": lambda: _layer_integrity(path, max_messages),
        "nwbinspector": lambda: _layer_inspector(path, max_messages),
        "dandi": lambda: _layer_dandi(path, tuple(dandi_ignore), max_messages),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = tuple(runners[x]() for x in want)
    versions = {d: _version(d) for d in ("pynwb", "hdmf", "nwbinspector", "dandi", "jnwb")}
    return NWBValidationReport(path.name, versions, out)
