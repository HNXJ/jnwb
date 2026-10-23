"""Re-read a written NWB file and check it against its writer's report.

``verify_nwb`` re-reads one written NWB file and checks it. It always
parses the file through pynwb, runs schema validation, and resolves every link and object
reference. With ``against`` and the writer's ``report`` it compares content, not storage:
each dataset the report's ``applied`` records do not name is byte-identical over ``n_check``
rows with its attributes compared (``object_id`` ignored), ``file_create_date`` is ignored,
object references are dereferenced and their targets compared by value, and scalars are read
whole. Any difference in a dataset the report does not name is reported as unexplained.

An ``applied`` record named ``"cast"`` declares its paths as dtype casts of the source, as
``transform_nwb``'s ``cast`` argument declares them; each must equal the source cast into
the destination's dtype.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
import tempfile
import warnings
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path

import h5py
import numpy as np

from jnwb.nwb_io import MissingRequiredNWBFieldError
from jnwb.ontology import Lineage, Provenance

#: The mutation category ``verify_nwb`` records on its report.
CATEGORY = "verify written output"

#: Root-level datasets holding write stamps: storage, not content.
IGNORED_DATASETS = ("file_create_date",)

#: Dataset attributes holding write-assigned identity: storage, not content.
IGNORED_ATTRIBUTES = ("object_id",)

#: An ``applied`` record with this name declares its paths as casts of the source.
CAST_OPERATION = "cast"


@dataclass(frozen=True)
class AppliedOperation:
    """One operation a writer applied: its name plus the dataset paths it changed."""

    name: str
    changed: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "changed", tuple(self.changed))


@dataclass(frozen=True)
class MutationCheck:
    """One row of a report's ``checks``: (name, ok, detail); ``verify_nwb``'s output."""

    name: str
    ok: bool
    detail: str = ""


@dataclass(frozen=True)
class MutationIssue:
    """One row of a report's ``issues``: (severity, location, message)."""

    severity: str
    location: str
    message: str = ""


@dataclass(frozen=True)
class MutationReport:
    """What one mutation operation did, extending ``Provenance`` and ``Lineage``.

    ``applied`` holds one ``AppliedOperation`` per named operation, in order;
    ``verify_nwb`` exempts exactly the dataset paths those records name.
    """

    category: str
    src: str | None
    dst: str | None
    src_sha256: str | None
    dst_sha256: str | None
    applied: tuple[AppliedOperation, ...] = ()
    checks: tuple[MutationCheck, ...] = ()
    issues: tuple[MutationIssue, ...] = ()
    waived: tuple[str, ...] = ()
    provenance: Provenance = field(default=None)
    lineage: Lineage = field(default=None)
    ok: bool = False

    def __post_init__(self):
        object.__setattr__(self, "applied", tuple(self.applied))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(self, "waived", tuple(self.waived))


def _norm(path: str) -> str:
    """One spelling for a dataset path: no leading, trailing or doubled separators."""
    return posixpath.normpath(path.strip()).lstrip("/")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _version(dist: str) -> str | None:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError as exc:
        warnings.warn(f"{dist!r} is not installed ({exc}); recording None",
                      UserWarning, stacklevel=2)
        return None


def _read_check(path: Path) -> MutationCheck:
    """The file parses through pynwb."""
    from pynwb import NWBHDF5IO

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            with NWBHDF5IO(str(path), "r") as io:
                nwb = io.read()
                detail = (f"OK -- {len(nwb.acquisition)} acquisition series, "
                          f"{0 if nwb.units is None else len(nwb.units)} units")
        except Exception as exc:
            return MutationCheck("pynwb read", False, f"{type(exc).__name__}: {exc}"[:500])
    return MutationCheck("pynwb read", True, detail)


def _schema_check(path: Path) -> MutationCheck:
    """The file passes schema validation against the namespaces cached inside it."""
    import pynwb

    try:
        errors = pynwb.validate(path=str(path), use_cached_namespaces=True)
    except Exception as exc:
        return MutationCheck("pynwb schema validation", False,
                             f"{type(exc).__name__}: {exc}"[:500])
    if errors:
        first = str(errors[0])[:300]
        return MutationCheck("pynwb schema validation", False,
                             f"{len(errors)} error(s); first: {first}")
    return MutationCheck("pynwb schema validation", True, "no errors")


def _dangling_link_problems(handle: h5py.File) -> list[str]:
    """Soft and external links that do not resolve, as ``/path: kind`` strings."""
    problems: list[str] = []
    stack = [handle]
    seen = {handle.name}
    while stack:
        group = stack.pop()
        for key in group.keys():
            link = group.get(key, getlink=True)
            if isinstance(link, h5py.HardLink):
                try:
                    obj = group[key]
                except Exception as exc:
                    problems.append(f"{group.name}/{key}: unreadable ({type(exc).__name__})")
                    continue
                if isinstance(obj, h5py.Group) and obj.name not in seen:
                    seen.add(obj.name)
                    stack.append(obj)
            else:
                try:
                    group[key]
                except Exception as exc:
                    problems.append(f"{group.name}/{key}: dangling "
                                    f"{type(link).__name__} ({type(exc).__name__})")
    return problems


def _stored_refs(dataset: h5py.Dataset, n_check: int) -> np.ndarray:
    """The first ``n_check`` references of a reference-dtype dataset, flattened."""
    if dataset.shape == ():
        return np.asarray(dataset[()]).ravel()
    n = min(n_check, dataset.shape[0])
    return np.asarray(dataset[:n]).ravel()


def _is_null(ref) -> bool:
    try:
        return not ref
    except Exception as exc:
        warnings.warn(f"unreadable reference ({type(exc).__name__}); treating it as non-null",
                      UserWarning, stacklevel=2)
        return False


def _reference_problems(handle: h5py.File, n_check: int) -> list[str]:
    """Stored object and region references that do not dereference."""
    problems: list[str] = []

    def visit(name: str, obj) -> None:
        if not (isinstance(obj, h5py.Dataset)
                and h5py.check_dtype(ref=obj.dtype) is not None):
            return
        try:
            refs = _stored_refs(obj, n_check)
        except Exception as exc:
            problems.append(f"/{name}: unreadable ({type(exc).__name__})")
            return
        for ref in refs:
            if _is_null(ref):
                continue
            try:
                handle[ref]
            except Exception as exc:
                problems.append(f"/{name}: dangling reference ({type(exc).__name__})")
                return

    handle.visititems(visit)
    return problems


def _resolution_check(path: Path, n_check: int) -> list[MutationCheck]:
    out = []
    with h5py.File(path, "r") as handle:
        links = _dangling_link_problems(handle)
        refs = _reference_problems(handle, n_check)
    out.append(MutationCheck(
        "soft and external links resolve", not links,
        "all resolve" if not links else "; ".join(links[:5])))
    out.append(MutationCheck(
        "object references resolve", not refs,
        "all resolve" if not refs else "; ".join(refs[:5])))
    return out


def _values_equal(first: np.ndarray, second: np.ndarray) -> bool:
    first, second = np.asarray(first), np.asarray(second)
    if first.shape != second.shape or first.dtype != second.dtype:
        return False
    if first.dtype.kind in "fc":
        return bool(np.array_equal(first, second, equal_nan=True))
    return bool(np.array_equal(first, second))


def _targets_equal(handle_first: h5py.File, ref_first, handle_second: h5py.File,
                   ref_second, n_check: int) -> bool:
    """Two references point at equal content: datasets by value, else kind and path."""
    first = handle_first[ref_first]
    second = handle_second[ref_second]
    if isinstance(first, h5py.Dataset) or isinstance(second, h5py.Dataset):
        if not (isinstance(first, h5py.Dataset) and isinstance(second, h5py.Dataset)):
            return False
        same, _ = _dataset_equal(first, second, handle_first, handle_second, n_check)
        return same
    if isinstance(first, np.ndarray) or isinstance(second, np.ndarray):
        return (isinstance(first, np.ndarray) and isinstance(second, np.ndarray)
                and _values_equal(first, second))
    return ((type(first).__name__, getattr(first, "name", None))
            == (type(second).__name__, getattr(second, "name", None)))


def _refs_equal(first: h5py.Dataset, second: h5py.Dataset, handle_first: h5py.File,
                handle_second: h5py.File, n_check: int) -> bool:
    """Two reference datasets hold the same references: dereference and compare targets."""
    if first.shape != second.shape:
        return False
    for ref_first, ref_second in zip(_stored_refs(first, n_check),
                                     _stored_refs(second, n_check)):
        if _is_null(ref_first) or _is_null(ref_second):
            if _is_null(ref_first) != _is_null(ref_second):
                return False
        elif not _targets_equal(handle_first, ref_first,
                                handle_second, ref_second, n_check):
            return False
    return True


def _attr_scalar_equal(handle_first: h5py.File, one, handle_second: h5py.File,
                       other, n_check: int) -> bool:
    """One attribute element: references dereference to their targets, else ``==``."""
    if isinstance(one, h5py.h5r.Reference) or isinstance(other, h5py.h5r.Reference):
        if not (isinstance(one, h5py.h5r.Reference)
                and isinstance(other, h5py.h5r.Reference)):
            return False
        try:
            return _targets_equal(handle_first, one, handle_second, other, n_check)
        except Exception as exc:
            warnings.warn(f"reference target unreadable ({type(exc).__name__}); "
                          "comparing as different", UserWarning, stacklevel=2)
            return False
    try:
        return bool(one == other)
    except Exception as exc:
        warnings.warn(f"attribute comparison failed ({type(exc).__name__}); comparing reprs",
                      UserWarning, stacklevel=2)
        return repr(one) == repr(other)


def _attr_value_equal(handle_first: h5py.File, value_first, handle_second: h5py.File,
                      value_second, n_check: int) -> bool:
    """One attribute value: elementwise, since references hide in object arrays."""
    first, second = np.asarray(value_first), np.asarray(value_second)
    if first.dtype.hasobject or second.dtype.hasobject:
        if first.shape != second.shape:
            return False
        return all(_attr_scalar_equal(handle_first, one, handle_second, other, n_check)
                   for one, other in zip(first.flat, second.flat))
    return _values_equal(first, second)


def _attrs_equal(first: h5py.Dataset, second: h5py.Dataset, handle_first: h5py.File,
                 handle_second: h5py.File, n_check: int) -> tuple[bool, str]:
    """Two datasets carry the same attributes: references dereferenced to targets."""
    names_first = sorted(k for k in first.attrs.keys() if k not in IGNORED_ATTRIBUTES)
    names_second = sorted(k for k in second.attrs.keys() if k not in IGNORED_ATTRIBUTES)
    if names_first != names_second:
        only = sorted(set(names_first) ^ set(names_second))
        return False, f"attributes only in one file: {only[:5]}"
    for key in names_first:
        if not _attr_value_equal(handle_first, first.attrs[key],
                                 handle_second, second.attrs[key], n_check):
            return False, f"attribute {key!r} differs"
    return True, "attributes match"


def _dataset_equal(first: h5py.Dataset, second: h5py.Dataset, handle_first: h5py.File,
                   handle_second: h5py.File, n_check: int) -> tuple[bool, str]:
    """Byte-identity of two datasets: scalars whole, references dereferenced, attrs equal."""
    if first.shape != second.shape:
        return False, f"shape {first.shape} vs {second.shape}"
    if h5py.check_dtype(ref=first.dtype) is not None \
            or h5py.check_dtype(ref=second.dtype) is not None:
        if not _refs_equal(first, second, handle_first, handle_second, n_check):
            return False, "reference targets differ"
        same, detail = _attrs_equal(first, second, handle_first, handle_second, n_check)
        return (True, "targets match") if same else (False, detail)
    if first.shape == ():
        if not _values_equal(first[()], second[()]):
            return False, "values differ"
        outcome = (True, "exact")
    else:
        n = min(n_check, first.shape[0])
        if not _values_equal(first[:n], second[:n]):
            return False, "values differ"
        outcome = (True, f"exact over first {n} rows")
    same, detail = _attrs_equal(first, second, handle_first, handle_second, n_check)
    return outcome if same else (False, detail)


def _cast_equal(source: h5py.Dataset, dest: h5py.Dataset, handle_source: h5py.File,
                handle_dest: h5py.File, n_check: int) -> tuple[bool, str]:
    """A declared cast equals the cast of the source over the rows checked."""
    if source.shape != dest.shape:
        return False, f"shape {dest.shape} vs source {source.shape}"
    if source.shape == ():
        expected = np.asarray(source[()]).astype(dest.dtype, copy=False)
        if not _values_equal(dest[()], expected):
            return False, "differs from the cast of the source"
        same, detail = _attrs_equal(source, dest, handle_source, handle_dest, n_check)
        if not same:
            return False, detail
        return True, "equals the cast of the source"
    n = min(n_check, source.shape[0])
    expected = np.asarray(source[:n]).astype(dest.dtype, copy=False)
    got = dest[:n]
    if not _values_equal(got, expected):
        return False, "differs from the cast of the source"
    same, detail = _attrs_equal(source, dest, handle_source, handle_dest, n_check)
    if not same:
        return False, detail
    return True, f"equals the cast of the source over first {n} rows"


def _cast_values_equal(source: h5py.Dataset, dest: h5py.Dataset, n_check: int,
                       ) -> tuple[bool, str]:
    """A declared cast compared by values alone: a repair sharing the path owns the attributes.

    ``repair_nwb`` records a dtype repair under both its repair name and ``"cast"``;
    the repair changed the attributes on purpose, so comparing them would fail the
    file for carrying out the repair. Only the values must equal the cast.
    """
    if source.shape != dest.shape:
        return False, f"shape {dest.shape} vs source {source.shape}"
    if source.shape == ():
        expected = np.asarray(source[()]).astype(dest.dtype, copy=False)
        if not _values_equal(dest[()], expected):
            return False, "differs from the cast of the source"
        return True, "equals the cast of the source"
    n = min(n_check, source.shape[0])
    expected = np.asarray(source[:n]).astype(dest.dtype, copy=False)
    got = dest[:n]
    if not _values_equal(got, expected):
        return False, "differs from the cast of the source"
    return True, f"equals the cast of the source over first {n} rows"


def _comparison_checks(dst_path: Path, against_path: Path, report: MutationReport,
                       n_check: int) -> list[MutationCheck]:
    out: list[MutationCheck] = []
    exempt: dict[str, set[str]] = {}
    for record in report.applied:
        for changed in record.changed:
            exempt.setdefault(_norm(changed), set()).add(record.name)
    with h5py.File(against_path, "r") as first, h5py.File(dst_path, "r") as second:
        names: list[str] = []

        def visit(name: str, obj) -> None:
            if isinstance(obj, h5py.Dataset):
                names.append(name)

        first.visititems(visit)
        dst_names: set[str] = set()

        def visit_dst(name: str, obj) -> None:
            if isinstance(obj, h5py.Dataset):
                dst_names.add(_norm(name))

        second.visititems(visit_dst)
        for name in sorted(names):
            normed = _norm(name)
            if normed in IGNORED_DATASETS:
                continue
            entry = exempt.get(normed)
            if entry is not None and CAST_OPERATION not in entry:
                out.append(MutationCheck(
                    f"/{normed} declared by the report", True,
                    f"operation {sorted(entry)!r}; exempt from byte comparison"))
                continue
            if normed not in dst_names:
                out.append(MutationCheck(
                    f"/{normed} matches the source as declared", False,
                    "unexplained difference: absent from the destination"))
                continue
            try:
                if normed in exempt:
                    if len(exempt[normed]) > 1:
                        same, detail = _cast_values_equal(first[name], second[name], n_check)
                        out.append(MutationCheck(f"/{normed} equals the cast of the source",
                                                 same, detail))
                    else:
                        same, detail = _cast_equal(first[name], second[name], first, second,
                                                   n_check)
                        out.append(MutationCheck(f"/{normed} equals the cast of the source",
                                                 same, detail))
                else:
                    same, detail = _dataset_equal(first[name], second[name], first,
                                                  second, n_check)
                    out.append(MutationCheck(
                        f"/{normed} matches the source as declared", same,
                        detail if same else f"unexplained difference: {detail}"))
            except Exception as exc:
                out.append(MutationCheck(
                    f"/{normed} matches the source as declared", False,
                    f"unexplained difference: unreadable ({type(exc).__name__})"))
        src_names = {_norm(n) for n in names}
        for normed in sorted(dst_names - src_names):
            if normed in IGNORED_DATASETS or normed in exempt:
                continue
            out.append(MutationCheck(
                f"/{normed} matches the source as declared", False,
                "unexplained difference: absent from the source"))
    return out


#: The mutation category ``write_nwb`` records on its report.
WRITE_CATEGORY = "write or create"


class NWBMutationError(Exception):
    """Base error for refused NWB mutation operations; carries the report ``issues``."""

    def __init__(self, message: str = "",
                 issues: tuple[MutationIssue, ...] = ()) -> None:
        self.issues = tuple(issues)
        super().__init__(message)


class NWBVerificationError(NWBMutationError):
    """A written file failed its post-write ``verify_nwb`` check; ``dst`` is left in place."""


class AmbiguousMappingError(NWBMutationError):
    """Two plausible mappings for one conversion; the operation refuses to pick one."""


class UnidentifiableRepairError(NWBMutationError):
    """A named repair's identifiability precondition does not hold; nothing is written."""


class UndeclaredUnitError(NWBMutationError):
    """A stored unit string is absent or outside the unit table; a unit is never guessed."""


def _missing_required_fields(nwbfile: NWBFile) -> list[str]:
    """Required ``NWBFile`` fields the caller left empty: schema validation passes ``""``."""
    missing = []
    if not getattr(nwbfile, "session_description", None):
        missing.append("session_description")
    if not getattr(nwbfile, "identifier", None):
        missing.append("identifier")
    if getattr(nwbfile, "session_start_time", None) is None:
        missing.append("session_start_time")
    return missing


def _export_tmp(nwbfile: NWBFile, directory: Path) -> Path:
    """Export the object to a fresh temporary file in ``directory``.

    The caller moves it to ``dst`` once validation passes, or deletes it when
    validation refuses: the same in-memory object is exported exactly once, since
    pynwb refuses to write one object twice.
    """
    from pynwb import NWBHDF5IO

    handle, tmp = tempfile.mkstemp(suffix=".nwb", dir=str(directory))
    os.close(handle)
    with NWBHDF5IO(tmp, "w") as io:
        io.write(nwbfile)
    return Path(tmp)


def _schema_issues(path: Path) -> tuple[MutationIssue, ...]:
    """Schema errors of a written file, against the namespaces cached inside it."""
    import pynwb

    errors = pynwb.validate(path=str(path), use_cached_namespaces=True)
    return tuple(MutationIssue("error", "schema", str(e)[:500]) for e in errors)


def write_nwb(nwbfile: NWBFile, *, dst: str | Path,
              overwrite: bool = False, verify: bool = True) -> MutationReport:
    """Write a caller-built ``NWBFile`` to ``dst`` and report the write.

    jnwb adds no content: the caller's pynwb objects carry every value, unit and
    region. The object is exported to a temporary file first, so a schema failure
    refuses before ``dst`` is touched.

    Parameters
    ----------
    nwbfile : pynwb.NWBFile
        The file to write. Never modified.
    dst : str or Path
        Output path. Its parents are created.
    overwrite : bool
        Allow writing over an existing ``dst``.
    verify : bool
        Re-read ``dst`` through ``verify_nwb`` after writing (default True).

    Returns
    -------
    MutationReport
        Category ``"write or create"``; ``src`` is None. ``ok`` is True in every
        returned report: a failed check raises.

    Raises
    ------
    TypeError
        ``nwbfile`` is not a ``pynwb.NWBFile``.
    MissingRequiredNWBFieldError
        A required field left empty by the caller; nothing is written.
    FileExistsError
        ``dst`` exists and ``overwrite`` is False.
    NWBMutationError
        The object fails schema validation before writing, carrying the issues;
        nothing is written.
    NWBVerificationError
        ``verify`` is True and a post-write check failed; ``dst`` is left in place
        for inspection.

    References:
        Rübel, O., et al. (2022). The Neurodata Without Borders ecosystem for
        neurophysiological data science. eLife 11, e78362. doi:10.7554/eLife.78362
        -- the NWB format this operation writes.
    """
    import jnwb
    from pynwb import NWBFile

    if not isinstance(nwbfile, NWBFile):
        raise TypeError(f"nwbfile must be a pynwb.NWBFile, got {type(nwbfile).__name__}")
    missing = _missing_required_fields(nwbfile)
    if missing:
        raise MissingRequiredNWBFieldError(missing[0])
    dst_path = Path(dst)
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"destination exists (pass overwrite=True): {dst_path}")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _export_tmp(nwbfile, dst_path.parent)
    try:
        issues = _schema_issues(tmp)
        if issues:
            raise NWBMutationError(
                f"the NWBFile fails schema validation with {len(issues)} error(s); "
                f"first: {issues[0].message}; nothing written",
                issues=issues)
        tmp.replace(dst_path)
    finally:
        tmp.unlink(missing_ok=True)
    checks: tuple[MutationCheck, ...] = ()
    if verify:
        rep = verify_nwb(dst_path)
        checks = rep.checks
        if not rep.ok:
            failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
            raise NWBVerificationError(
                f"write_nwb wrote {dst_path}, and {len(failed)} verification "
                "check(s) failed; the file is left in place for inspection: "
                + " | ".join(d[:300] for d in failed))
    dst_sha = _sha256(dst_path)
    provenance = Provenance(
        software_version=jnwb.__version__, backend="numpy",
        parameters={"overwrite": overwrite, "verify": verify},
        environment={"pynwb": _version("pynwb") or "unknown",
                     "hdmf": _version("hdmf") or "unknown"})
    lineage = Lineage(source_type="NWBFile", source_id=dst_sha,
                      operation=WRITE_CATEGORY)
    return MutationReport(
        category=WRITE_CATEGORY, src=None, dst=str(dst_path),
        src_sha256=None, dst_sha256=dst_sha,
        applied=(), checks=checks, issues=(),
        waived=(), provenance=provenance, lineage=lineage, ok=True)


#: The mutation category ``transform_nwb`` records on its report.
TRANSFORM_CATEGORY = "copy or transform"

#: The mutation category ``repair_nwb`` records on its report.
REPAIR_CATEGORY = "structural repair"

#: The repairs ``repair_nwb`` takes by name: the four the read path applies today.
#: Held out of ``__all__``: it is an argument vocabulary, not an operation to route,
#: but reachable as ``jnwb.REPAIRS``.
REPAIRS = ("squeeze_scalar_attributes", "units_colnames", "vector_index_types",
           "waveform_index_dtype")

#: Attribute names the squeeze repair must leave alone: a length-1 value of one of
#: these is a one-element list, not a wrapped scalar. Mirrors the read path's
#: ``jnwb.nwb_io._SEQUENCE_ATTRIBUTES``.
_REPAIR_SEQUENCE_ATTRIBUTES = frozenset({"colnames"})

#: The only storage filters ``transform_nwb`` writes.
_COMPRESSION_FILTERS = ("gzip",)

#: Compression keywords ``transform_nwb`` accepts, besides the filter name.
_COMPRESSION_KEYS = ("filter", "level", "shuffle")


def _check_compression(compression) -> dict | None:
    """The validated compression mapping, or ``None`` for the source's own storage."""
    if compression is None:
        return None
    if not isinstance(compression, dict):
        raise TypeError(
            f"compression must be a mapping like "
            f"{{'filter': 'gzip', 'level': 1, 'shuffle': True}}, got {type(compression).__name__}")
    unknown = sorted(set(compression) - set(_COMPRESSION_KEYS))
    if unknown:
        raise ValueError(
            f"unknown compression key(s) {unknown}; known: {sorted(_COMPRESSION_KEYS)}")
    filtr = compression.get("filter", "gzip")
    if filtr not in _COMPRESSION_FILTERS:
        raise ValueError(
            f"unknown compression filter {filtr!r}; known: {list(_COMPRESSION_FILTERS)}")
    level = compression.get("level", 1)
    if isinstance(level, bool) or not isinstance(level, int) or not 0 <= level <= 9:
        raise ValueError(f"compression level must be an integer 0-9, got {level!r}")
    shuffle = compression.get("shuffle", True)
    if not isinstance(shuffle, bool):
        raise ValueError(f"compression shuffle must be True or False, got {shuffle!r}")
    return {"filter": filtr, "level": level, "shuffle": shuffle}


def _all_datasets(handle: h5py.File) -> list[str]:
    """Every dataset path in the file, as ``/``-rooted names."""
    names: list[str] = []

    def visit(name: str, obj) -> None:
        if isinstance(obj, h5py.Dataset):
            names.append("/" + name)

    handle.visititems(visit)
    return names


def _resolve_transform_paths(handle: h5py.File, keep, drop,
                             cast: dict) -> tuple[list[str], list[str]]:
    """The datasets the copy keeps, and the datasets it drops.

    Every named path must open something, and every ``cast`` path a dataset;
    anything else raises before a byte is written.
    """
    for label, value in (("keep", keep), ("drop", drop)):
        if isinstance(value, (str, bytes)):
            raise TypeError(
                f"{label}= takes a list of dataset or group paths, not one string; "
                f"write {label}=[{value!r}]")
    kept = [_norm(p) for p in keep] if keep is not None else None
    dropped = [_norm(p) for p in drop] if drop is not None else None
    names = {_norm(p) for p in cast}
    for path in list(kept or []) + list(dropped or []) + sorted(names):
        if "/" + path not in handle:
            raise KeyError(f"transform_nwb: {path!r} opens nothing in {Path(handle.filename).name}")
    for path in sorted(names):
        if isinstance(handle["/" + path], h5py.Group):
            raise TypeError(
                f"transform_nwb: cast= names {path!r}, which is a group; casts name datasets")
    datasets = {_norm(p) for p in _all_datasets(handle)}

    def under(path: str, roots: list[str]) -> bool:
        return any(path == root or path.startswith(root + "/") for root in roots)

    if kept is not None:
        final = {d for d in datasets if under(d, kept)}
    elif dropped is not None:
        final = {d for d in datasets if not under(d, dropped)}
    else:
        final = set(datasets)
    for path in sorted(names):
        if _norm(path) not in final:
            raise ValueError(
                f"transform_nwb: cast= names {path!r}, which the copy drops; "
                f"a cast applies to a dataset the copy keeps")
    return sorted(final), sorted(datasets - final)


def _check_cast_dtypes(handle: h5py.File, cast: dict) -> None:
    """Refuse every cast the transform does not offer: floats stay floating.

    A cast naming an ``*_index`` dataset is a ``TypeError`` whatever its dtype;
    a cast of an integer or boolean dataset to a narrower or non-floating dtype
    is a ``TypeError``; a float source narrows freely. Widening an integer to a
    wider float is allowed.
    """
    for path in sorted(cast):
        normed = _norm(path)
        source = handle["/" + normed].dtype
        try:
            dest = np.dtype(cast[path])
        except TypeError:
            raise TypeError(
                f"transform_nwb: cast[{path!r}] is {cast[path]!r}, not a dtype") from None
        if normed.rsplit("/", 1)[-1].endswith("_index"):
            raise TypeError(
                f"transform_nwb: cast= refuses {path!r} with {source} source dtype; "
                f"index datasets are never cast, whatever their dtype")
        if source.kind in "iub":
            if dest.kind != "f" or dest.itemsize < source.itemsize:
                raise TypeError(
                    f"transform_nwb: cast= refuses {path!r} from {source} to {dest}; "
                    f"casts of integer or boolean datasets stay floating-point "
                    f"and never narrow -- never integer, boolean or index ones narrowed")
        elif source.kind == "f":
            if dest.kind != "f":
                raise TypeError(
                    f"transform_nwb: cast= refuses {path!r} to {dest} dtype; "
                    f"casts stay floating-point")
        else:
            raise TypeError(
                f"transform_nwb: cast= refuses {path!r} with {source} source dtype; "
                f"only floating-point datasets are cast, never integer, boolean or index ones")


def _stored_targets(handle: h5py.File) -> list[tuple[str, str]]:
    """``(referrer, target)`` for every stored object reference and soft or external link.

    A referrer that cannot be dereferenced refuses the drop with
    ``NWBMutationError`` naming it, instead of being skipped silently.
    """
    pairs: list[tuple[str, str]] = []

    def note(referrer: str, ref) -> None:
        if _is_null(ref):
            return
        try:
            pairs.append((referrer, handle[ref].name))
        except Exception as exc:
            raise NWBMutationError(
                f"transform_nwb: {referrer} cannot be dereferenced "
                f"({type(exc).__name__}); the drop is refused so no dangling "
                f"reference is written; nothing written") from exc

    def visit(name: str, obj) -> None:
        full = "/" + name
        if isinstance(obj, h5py.Dataset) and h5py.check_dtype(ref=obj.dtype) is not None:
            try:
                refs = _stored_refs(obj, 1 << 30)
            except Exception as exc:
                raise NWBMutationError(
                    f"transform_nwb: {full} cannot be read "
                    f"({type(exc).__name__}); the drop is refused; nothing written") from exc
            for ref in refs:
                note(full, ref)
        for key, value in obj.attrs.items():
            where = f"attribute {key!r} on {full}"
            if isinstance(value, h5py.Reference):
                note(where, value)
            elif (isinstance(value, np.ndarray) and value.dtype.hasobject and value.size
                    and isinstance(np.asarray(value).flat[0], h5py.Reference)):
                for ref in np.asarray(value).flat:
                    note(where, ref)

    for key, value in handle.attrs.items():
        if isinstance(value, h5py.Reference):
            note(f"attribute {key!r} on /", value)
    handle.visititems(visit)
    stack: list[h5py.Group] = [handle]
    seen = {handle.name}
    while stack:
        group = stack.pop()
        for key in group.keys():
            link = group.get(key, getlink=True)
            full = group.name.rstrip("/") + "/" + key
            if isinstance(link, h5py.HardLink):
                try:
                    obj = group[key]
                except Exception as exc:
                    raise NWBMutationError(
                        f"transform_nwb: {full} cannot be opened "
                        f"({type(exc).__name__}); the drop is refused; nothing written") from exc
                if isinstance(obj, h5py.Group) and obj.name not in seen:
                    seen.add(obj.name)
                    stack.append(obj)
            else:
                try:
                    pairs.append((full, group[key].name))
                except Exception as exc:
                    raise NWBMutationError(
                        f"transform_nwb: link {full} cannot be dereferenced "
                        f"({type(exc).__name__}); the drop is refused; nothing written") from exc
    return pairs


def _refuse_dangling_drop(handle: h5py.File, final: list[str], removed: list[str],
                          drop_roots: list[str]) -> None:
    """Refuse to drop a dataset a kept object references or links to.

    The referrer may go with its target; a kept referrer pointing at a dropped
    target would leave a dangling reference, so it raises.
    """
    kept = {"/" + p for p in final}
    gone = {"/" + p for p in removed} | {"/" + r for r in drop_roots}

    def is_gone(target: str) -> bool:
        return target in gone or any(
            target == root or target.startswith(root + "/") for root in gone)

    def is_kept(referrer: str) -> bool:
        # Attribute referrers read "attribute 'key' on /path": the object at
        # /path is what stays or goes with the target.
        obj = referrer.split(" on ", 1)[1] if referrer.startswith("attribute ") else referrer
        if obj in kept:
            return True
        return not (obj in gone or any(
            obj == root or obj.startswith(root + "/") for root in gone))

    for referrer, target in _stored_targets(handle):
        if is_gone(target) and is_kept(referrer):
            raise NWBMutationError(
                f"transform_nwb: dropping {target}, which {referrer} references or links to; "
                f"drop the referrer too or keep the target; nothing written")


def _prune_emptied(dst: h5py.File, removed: list[str]) -> None:
    """Delete the groups the selection emptied, innermost first.

    Only ancestors of removed datasets are candidates, so a group already empty
    in the source is left alone; root-level groups stay as schema slots even
    when emptied.
    """
    ancestors: set[str] = set()
    for path in removed:
        parts = path.split("/")
        for i in range(1, len(parts)):
            ancestors.add("/" + "/".join(parts[:i]))
    for path in sorted(ancestors, key=len, reverse=True):
        if path.count("/") < 2:
            continue
        obj = dst.get(path)
        if isinstance(obj, h5py.Group) and len(obj.keys()) == 0:
            del dst[path]


def _delete_unkept(dst: h5py.File, final: list[str], removed: list[str],
                   drop: list[str] | None) -> None:
    """Leave exactly the kept datasets standing after a full structural copy.

    A whole-tree copy keeps the HDF5 structure validation reads: groups created
    by hand lose the properties the schema check requires. Named drop roots go
    as whole objects, so no table is left as a husk missing its required
    datasets; in keep mode a top-level group holding removed datasets goes
    likewise, while a root child holding none stays as a schema slot,
    and emptied deeper groups are pruned.
    """
    if drop is not None:
        for root in sorted({_norm(p) for p in drop}, key=len, reverse=True):
            if "/" + root in dst:
                del dst["/" + root]
    else:
        kept_tops = {p.split("/")[0] for p in final}
        dropped_tops = {p.split("/")[0] for p in removed}
        for key in list(dst.keys()):
            if key not in kept_tops and key in dropped_tops:
                del dst[key]
        for path in sorted(set(removed), key=len, reverse=True):
            if "/" + path in dst:
                del dst["/" + path]
    _prune_emptied(dst, removed)


def _rewrite_dataset(dst: h5py.File, path: str, dtype, comp: dict | None) -> None:
    """Replace one dataset's values and dtype, keeping its attributes.

    References held elsewhere still name the old object, so the caller runs
    ``_resolve_references`` again afterwards.
    """
    old = dst[path]
    values = np.asarray(old[...]).astype(np.dtype(dtype), copy=False)
    attrs = {key: old.attrs[key] for key in old.attrs}
    chunks = old.chunks
    del dst[path]
    if comp is not None:
        new = dst.create_dataset(path, data=values, dtype=np.dtype(dtype), chunks=True,
                                 compression="gzip", compression_opts=comp["level"],
                                 shuffle=comp["shuffle"])
    elif old.shape == ():
        new = dst.create_dataset(path, data=values, dtype=np.dtype(dtype))
    else:
        new = dst.create_dataset(path, data=values, dtype=np.dtype(dtype), chunks=chunks)
    for key, value in attrs.items():
        new.attrs[key] = value


def _report_and_verify(category: str, src_path: Path, dst_path: Path, applied,
                       issues, checks, parameters: dict) -> MutationReport:
    """The report every mutating writer returns, verified when asked.

    A failed check raises and leaves ``dst`` in place, as ``write_nwb`` does.
    """
    import jnwb

    dst_sha = _sha256(dst_path)
    provenance = Provenance(
        software_version=jnwb.__version__, backend="numpy",
        parameters=parameters,
        environment={"pynwb": _version("pynwb") or "unknown",
                     "hdmf": _version("hdmf") or "unknown"})
    lineage = Lineage(source_type="NWBFile", source_id=_sha256(src_path),
                       operation=category)
    report = MutationReport(
        category=category, src=str(src_path), dst=str(dst_path),
        src_sha256=_sha256(src_path), dst_sha256=dst_sha,
        applied=tuple(applied), checks=tuple(checks), issues=tuple(issues),
        waived=(), provenance=provenance, lineage=lineage, ok=all(c.ok for c in checks))
    if not report.ok:
        failed = [f"{c.name}: {c.detail}" for c in report.checks if not c.ok]
        raise NWBVerificationError(
            f"{category}: {len(failed)} verification check(s) failed on {dst_path}; "
            f"the file is left in place for inspection: " + " | ".join(d[:300] for d in failed))
    return report


def transform_nwb(src: str | Path, *, dst: str | Path, keep=None, drop=None, cast=None,
                  compression=None, overwrite: bool = False,
                  verify: bool = True) -> MutationReport:
    """Copy a file with declared changes and report the copy.

    ``keep`` or ``drop`` (not both) names dataset or group paths. No argument
    changes values other than a declared ``cast``.

    Parameters
    ----------
    src : str or Path
        The source file. Never modified.
    dst : str or Path
        Output path. Its parents are created.
    keep : list of str, optional
        Only these paths and their subtrees are copied.
    drop : list of str, optional
        Everything but these paths and their subtrees is copied.
    cast : dict, optional
        ``{path: dtype}`` recasts; destinations stay floating-point, and integer
        or boolean sources only widen.
    compression : dict, optional
        ``{"filter": "gzip", "level": 1, "shuffle": True}``, applied to the
        rewritten datasets; ``None`` keeps the source's own storage.
    overwrite : bool
        Allow writing over an existing ``dst``.
    verify : bool
        Re-read ``dst`` against ``src`` through ``verify_nwb`` after writing (default True).

    Returns
    -------
    MutationReport
        Category ``"copy or transform"``. ``ok`` is True in every returned
        report: a failed check raises.

    Raises
    ------
    KeyError
        A path that opens nothing.
    TypeError
        A group in ``cast``; a cast naming an ``*_index`` dataset; a cast of an
        integer or boolean dataset to a narrower or non-floating dtype; a cast
        of a floating-point dataset to a non-floating dtype.
    ValueError
        ``keep`` and ``drop`` together; a cast on a dropped path; an unknown
        compression filter; ``dst`` resolving to ``src``.
    NWBMutationError
        Dropping a dataset another kept object references or links to, naming
        the referrer; or schema validation failing before the move.
    FileExistsError
        ``dst`` exists and ``overwrite`` is False.
    NWBVerificationError
        ``verify`` is True and a post-write check failed; ``dst`` is left in place
        for inspection.

    References:
        Rübel, O., et al. (2022). The Neurodata Without Borders ecosystem for
        neurophysiological data science. eLife 11, e78362. doi:10.7554/eLife.78362
        -- the NWB format this operation copies.
    """
    from jnwb.compression import _resolve_references, _structural_copy

    if keep is not None and drop is not None:
        raise ValueError("transform_nwb: keep= and drop= exclude each other; pass one")
    cast = dict(cast) if cast is not None else {}
    comp = _check_compression(compression)
    src_path = Path(src)
    dst_path = Path(dst)
    if src_path.resolve() == dst_path.resolve():
        raise ValueError(f"transform_nwb: dst resolves to src ({src_path}); the source "
                         f"is never modified, so name a different dst")
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"destination exists (pass overwrite=True): {dst_path}")
    with h5py.File(src_path, "r") as handle:
        final, removed = _resolve_transform_paths(handle, keep, drop, cast)
        _check_cast_dtypes(handle, cast)
        drop_roots = [_norm(p) for p in drop] if drop is not None else []
        _refuse_dangling_drop(handle, final, removed, drop_roots)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    handle_tmp, tmp = tempfile.mkstemp(suffix=".nwb", dir=str(dst_path.parent))
    os.close(handle_tmp)
    tmp_path = Path(tmp)
    try:
        with h5py.File(src_path, "r") as src_h, h5py.File(tmp_path, "w") as dst_h:
            _structural_copy(src_h, dst_h)
            _delete_unkept(dst_h, final, removed, drop_roots if drop is not None else None)
        with h5py.File(tmp_path, "r+") as dst_h:
            cast_norm = {_norm(p): v for p, v in cast.items()}
            rewritten = set(cast_norm)
            if comp is not None and not rewritten:
                with h5py.File(src_path, "r") as src_h:
                    rewritten = {_norm(p) for p in _all_datasets(src_h)
                                 if src_h["/" + p].dtype.kind == "f"
                                 and _norm(p) in set(final)}
            with h5py.File(src_path, "r") as src_h:
                fallbacks = {p: src_h["/" + p].dtype for p in rewritten}
            for path in sorted(rewritten):
                dtype = cast_norm.get(path, fallbacks[path])
                _rewrite_dataset(dst_h, "/" + path, dtype, comp)
            with h5py.File(src_path, "r") as src_h:
                _resolve_references(src_h, dst_h)
        issues = _schema_issues(tmp_path)
        if issues:
            raise NWBMutationError(
                f"transform_nwb: the copy fails schema validation with {len(issues)} "
                f"error(s); first: {issues[0].message}; nothing written",
                issues=issues)
        tmp_path.replace(dst_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    applied = []
    if removed:
        name = "drop" if drop is not None else "keep"
        applied.append(AppliedOperation(name, tuple("/" + p for p in removed)))
    if cast:
        applied.append(AppliedOperation(
            CAST_OPERATION, tuple("/" + _norm(p) for p in cast)))
    checks: tuple[MutationCheck, ...] = ()
    if verify:
        preliminary = MutationReport(
            category=TRANSFORM_CATEGORY, src=str(src_path), dst=str(dst_path),
            src_sha256=None, dst_sha256=None, applied=tuple(applied),
            checks=(), issues=(), waived=(),
            provenance=Provenance(software_version="transform_nwb",
                                  backend="numpy"),
            lineage=Lineage(source_type="NWBFile", source_id="transform_nwb",
                            operation=TRANSFORM_CATEGORY),
            ok=True)
        rep = verify_nwb(dst_path, against=src_path, report=preliminary)
        checks = rep.checks
        if not rep.ok:
            failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
            raise NWBVerificationError(
                f"transform_nwb wrote {dst_path}, and {len(failed)} verification "
                "check(s) failed; the file is left in place for inspection: "
                + " | ".join(d[:300] for d in failed))
    return _report_and_verify(
        TRANSFORM_CATEGORY, src_path, dst_path, applied, (), checks,
        {"keep": keep, "drop": drop, "cast": {k: str(v) for k, v in cast.items()},
         "compression": comp, "overwrite": overwrite, "verify": verify})


def _require_session_description(handle: h5py.File) -> None:
    """Refuse a file with no ``session_description`` dataset before any repair.

    A structural repair never invents the required field; the waiver the read
    path offers is a read concern, not a write one.
    """
    try:
        obj = handle["session_description"]
    except KeyError:
        raise MissingRequiredNWBFieldError("session_description") from None
    if not isinstance(obj, h5py.Dataset):
        raise MissingRequiredNWBFieldError("session_description")


def _stored_ndt(obj) -> str | None:
    """The stored ``neurodata_type`` of one object, decoded, or ``None``."""
    raw = obj.attrs.get("neurodata_type")
    if raw is None:
        return None
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def _spec_chain(catalog, ndt: str) -> list:
    """The spec for ``ndt`` plus every type it extends, core namespace first."""
    for namespace in ("core", "hdmf-common"):
        try:
            spec = catalog.get_namespace(namespace).get_spec(ndt)
        except Exception:
            continue
        chain = [spec]
        node = spec
        while isinstance(getattr(node, "data_type_inc", None), str):
            try:
                node = catalog.get_namespace(namespace).get_spec(node.data_type_inc)
            except Exception:
                break
            chain.append(node)
        return chain
    return []


def _declared_scalar(catalog, ndt: str, obj_is_dataset: bool, obj_name: str,
                     attr: str) -> bool:
    """Whether the schema declares ``attr`` a scalar on this object.

    Group attributes are looked up on the group's type; dataset attributes on
    the dataset's entry under its parent's type. Anything undeclared is not
    scalar: the repair refuses rather than squeeze it.
    """
    for node in _spec_chain(catalog, ndt):
        try:
            if obj_is_dataset:
                entry = node.get_dataset(obj_name)
                found = entry.get_attribute(attr) if entry is not None else None
            else:
                found = node.get_attribute(attr)
        except Exception:
            continue
        if found is None:
            continue
        return found.shape is None and found.dims is None
    return False


def _squeeze_candidates(handle: h5py.File) -> list[tuple[str, str]]:
    """``(path, attribute)`` of every length-1 array attribute the read squeezes."""
    out: list[tuple[str, str]] = []

    def collect(path: str, obj) -> None:
        for key, value in obj.attrs.items():
            if key in _REPAIR_SEQUENCE_ATTRIBUTES:
                continue
            if (isinstance(value, np.ndarray) and value.ndim == 1 and len(value) == 1
                    and isinstance(value[0], (bytes, str))):
                out.append((path, key))

    collect("/", handle)
    handle.visititems(lambda name, obj: collect("/" + name, obj))
    return out


def _plan_squeeze_scalar_attributes(handle: h5py.File) -> list[tuple[str, str]]:
    """Check every squeezed attribute against the schema's scalar declarations."""
    from pynwb import get_type_map

    candidates = _squeeze_candidates(handle)
    if not candidates:
        raise UnidentifiableRepairError(
            "repair_nwb: squeeze_scalar_attributes changes nothing in "
            f"{Path(handle.filename).name}; nothing written")
    catalog = get_type_map().namespace_catalog
    for path, attr in candidates:
        obj = handle[path] if path != "/" else handle
        is_dataset = isinstance(obj, h5py.Dataset)
        if is_dataset:
            ndt = _stored_ndt(obj) or _stored_ndt(obj.parent)
            name = path.rsplit("/", 1)[-1]
        elif path == "/":
            ndt, name = "NWBFile", ""
        else:
            ndt, name = _stored_ndt(obj), ""
        if ndt is None or not _declared_scalar(catalog, ndt, is_dataset, name, attr):
            raise UnidentifiableRepairError(
                f"repair_nwb: squeeze_scalar_attributes cannot identify {path} "
                f"attribute {attr!r} as a schema scalar; nothing written")
    return candidates


def _read_colnames(units: h5py.Group) -> list[str]:
    """The stored ``colnames`` as a list, mirroring the read path's decoding."""
    raw = units.attrs.get("colnames", [])
    if isinstance(raw, (str, bytes)):
        raw = [raw]
    return [c.decode("utf-8") if isinstance(c, bytes) else c for c in raw]


def _plan_units_colnames(handle: h5py.File) -> list[str]:
    """The corrected ``colnames`` list, mirroring the read path exactly."""
    if "units" not in handle or not isinstance(handle["units"], h5py.Group):
        raise UnidentifiableRepairError(
            f"repair_nwb: units_colnames finds no units table in {Path(handle.filename).name}; "
            f"nothing written")
    units = handle["units"]
    colnames = _read_colnames(units)
    for index_col in ("spike_times_index", "waveform_mean_index", "spike_amplitudes_index"):
        if index_col in colnames:
            colnames.remove(index_col)
    for col in ("spike_times", "waveform_mean", "spike_amplitudes"):
        if col in units and isinstance(units[col], h5py.Dataset) and col not in colnames:
            colnames.append(col)
    stored = _read_colnames(units)
    if colnames == stored:
        raise UnidentifiableRepairError(
            "repair_nwb: units_colnames changes nothing; the stored colnames already "
            "name every data column and no index; nothing written")
    return colnames


#: The index datasets ``vector_index_types`` repairs: the two the read path fixes.
_VECTOR_INDEX_REPAIR_NAMES = ("waveform_mean_index", "spike_amplitudes_index")


def _plan_vector_index_types(handle: h5py.File) -> list[tuple[str, str]]:
    """``(index path, target path)`` for the two indices the read path fixes.

    The precondition is stricter than the read path: the target must exist under
    the name the index derives, so a targetless index refuses the whole repair
    instead of reading past it. A stored reference that resolves to a valid
    existing dataset other than the derived target is a different intent, not a
    broken link: the repair refuses rather than repoint it. Only a missing or
    dangling stored reference is repointed to the derived target.
    """
    plans: list[tuple[str, str]] = []
    targetless: list[str] = []

    def visit(name: str, obj) -> None:
        if not isinstance(obj, h5py.Dataset):
            return
        base = name.split("/")[-1]
        if base not in _VECTOR_INDEX_REPAIR_NAMES:
            return
        parent = "/" + "/".join(name.split("/")[:-1])
        parent = "/" if parent == "/" else parent
        target = (parent + "/" if parent != "/" else "/") + base[:-len("_index")]
        if target not in handle or not isinstance(handle[target], h5py.Dataset):
            targetless.append("/" + name)
            return
        index = handle["/" + name]
        stored = _stored_ndt(index)
        target_ref = index.attrs.get("target")
        resolved: str | None = None
        if target_ref is not None and not _is_null(target_ref):
            try:
                resolved = handle[target_ref].name
            except Exception:
                resolved = None
        if resolved is not None and resolved != handle[target].name:
            raise UnidentifiableRepairError(
                f"repair_nwb: vector_index_types finds {'/' + name} targeting "
                f"{resolved}, not its derived target {target}; the intended "
                f"representation is not identifiable; nothing written")
        if stored != "VectorIndex" or resolved != handle[target].name:
            plans.append(("/" + name, target))

    handle.visititems(visit)
    if targetless:
        raise UnidentifiableRepairError(
            f"repair_nwb: vector_index_types cannot identify a target for "
            f"{targetless[0]}; the index name must be its target's name plus "
            f"'_index'; nothing written")
    if not plans:
        raise UnidentifiableRepairError(
            "repair_nwb: vector_index_types changes nothing; waveform_mean_index and "
            "spike_amplitudes_index already carry their VectorIndex type and target; "
            "no other *_index dataset is one the read path fixes; nothing written")
    return plans


def _plan_waveform_index_dtype(handle: h5py.File) -> list[str]:
    """``waveform_mean_index`` datasets whose values are integral 0-255 bytes.

    The read path casts without asking; the persistent repair first proves the
    values survive a ``uint8`` cast, whatever dtype stores them, and refuses a
    file whose values do not.
    """
    plans: list[str] = []

    def visit(name: str, obj) -> None:
        if not (isinstance(obj, h5py.Dataset) and name.split("/")[-1] == "waveform_mean_index"):
            return
        if obj.dtype.kind == "uint8":
            return
        values = np.asarray(obj[...])
        if values.dtype.kind == "f":
            bad = bool(values.size and (np.isnan(values).any()
                        or (values != np.floor(values)).any()
                        or (values < 0).any() or (values > 255).any()))
        elif values.dtype.kind in "iub":
            bad = bool(values.size and ((values < 0).any() or (values > 255).any()))
        else:
            raise UnidentifiableRepairError(
                f"repair_nwb: waveform_index_dtype finds {'/' + name} with {obj.dtype} "
                f"dtype; only integral values are identifiably indices; nothing written")
        if bad:
            raise UnidentifiableRepairError(
                f"repair_nwb: waveform_index_dtype finds {'/' + name} holding values "
                f"outside 0-255 or not integral; nothing written")
        plans.append("/" + name)

    handle.visititems(visit)
    if not plans:
        raise UnidentifiableRepairError(
            "repair_nwb: waveform_index_dtype changes nothing; no floating "
            "waveform_mean_index needs the uint8 cast; nothing written")
    return plans


def _contradiction_issues(handle: h5py.File) -> list[MutationIssue]:
    """Every container-type contradiction, reported and never rewritten."""
    from jnwb.nwb_inspect import _series_members, _type_contradictions

    containers: list[tuple[str, h5py.Group]] = []
    for top in ("acquisition", "stimulus", "intervals", "units", "general"):
        group = handle.get(top)
        if not isinstance(group, h5py.Group):
            continue
        for name in sorted(group.keys()):
            obj = group[name]
            if isinstance(obj, h5py.Group):
                containers.append((f"/{top}/{name}", obj))
    if "processing" in handle and isinstance(handle["processing"], h5py.Group):
        for mod in sorted(handle["processing"].keys()):
            group = handle["processing"][mod]
            if not isinstance(group, h5py.Group):
                continue
            for name in sorted(group.keys()):
                obj = group[name]
                if isinstance(obj, h5py.Group) and _series_members(obj):
                    containers.append((f"/processing/{mod}/{name}", obj))
    issues: list[MutationIssue] = []
    for path, group in containers:
        for case, phrase in _type_contradictions(group, _series_members(group)):
            issues.append(MutationIssue("warning", path, f"{case}: {phrase}"))
    return issues


def _apply_repairs(dst: h5py.File, plans: dict) -> None:
    """Write the planned edits into the copied file."""
    for path, attr in plans.get("squeeze_scalar_attributes", []):
        obj = dst[path] if path != "/" else dst
        value = obj.attrs[attr][0]
        if isinstance(value, bytes):
            value = value.decode("utf-8", errors="replace")
        obj.attrs[attr] = str(value)
    if "units_colnames" in plans:
        dst["units"].attrs["colnames"] = np.array(plans["units_colnames"], dtype=object)
    for index_path, target_path in plans.get("vector_index_types", []):
        index = dst[index_path]
        index.attrs["neurodata_type"] = "VectorIndex"
        index.attrs["target"] = dst[target_path].ref
    for path in plans.get("waveform_index_dtype", []):
        old = dst[path]
        values = np.asarray(old[...]).astype(np.uint8)
        attrs = {key: old.attrs[key] for key in old.attrs}
        chunks = old.chunks
        shape = old.shape
        saved_target = attrs.get("target")
        target_path = path[: -len("waveform_mean_index")] + "waveform_mean"
        del dst[path]
        if shape == ():
            new = dst.create_dataset(path, data=values, dtype=np.uint8)
        else:
            new = dst.create_dataset(path, data=values, dtype=np.uint8, chunks=chunks)
        for key, value in attrs.items():
            if key in ("neurodata_type", "target"):
                continue
            new.attrs[key] = value
        if "description" not in attrs:
            target_name = path.rsplit("/", 1)[-1].removesuffix("_index")
            new.attrs["description"] = f"Index for VectorData '{target_name}'"
        new.attrs["neurodata_type"] = "VectorIndex"
        if target_path in dst:
            new.attrs["target"] = dst[target_path].ref
        elif saved_target is not None:
            new.attrs["target"] = saved_target


def repair_nwb(src: str | Path, *, dst: str | Path, repairs,
               overwrite: bool = False, verify: bool = True) -> MutationReport:
    """Make the read path's in-memory repairs persistent and report the repair.

    ``repairs`` is required. Each named repair checks its identifiability
    precondition before anything is written. Two preconditions are stricter
    than the read path: ``vector_index_types`` requires the target the index
    name derives to exist, where the read only
    fixes the target link; and ``waveform_index_dtype`` requires integral
    values in 0-255, where the read casts without asking. A persistent repair
    can therefore refuse a file ``read_nwb`` reads.

    A container-type contradiction is reported in ``issues`` and never
    rewritten: the stored and declared types are two plausible intents.

    Parameters
    ----------
    src : str or Path
        The source file. Never modified.
    dst : str or Path
        Output path. Its parents are created.
    repairs
        The repair names to apply, from ``jnwb.REPAIRS``.
    overwrite : bool
        Allow writing over an existing ``dst``.
    verify : bool
        Re-read ``dst`` against ``src`` through ``verify_nwb`` after writing (default True).

    Returns
    -------
    MutationReport
        Category ``"structural repair"``. ``ok`` is True in every returned
        report: a failed check raises.

    Raises
    ------
    TypeError
        ``repairs`` is None.
    ValueError
        A name not in ``jnwb.REPAIRS``; an empty ``repairs``; ``dst``
        resolving to ``src``.
    UnidentifiableRepairError
        A named repair's precondition does not hold, or it would change
        nothing; nothing is written.
    MissingRequiredNWBFieldError
        A missing ``session_description``; not a structural repair, the value
        is unknown.
    FileExistsError
        ``dst`` exists and ``overwrite`` is False.
    NWBVerificationError
        ``verify`` is True and a post-write check failed; ``dst`` is left in place
        for inspection.

    References:
        Rübel, O., et al. (2022). The Neurodata Without Borders ecosystem for
        neurophysiological data science. eLife 11, e78362. doi:10.7554/eLife.78362
        -- the NWB format this operation repairs.
    """
    from jnwb.compression import _resolve_references, _structural_copy

    if repairs is None:
        raise TypeError(
            "repairs= is required: pass the repair names from jnwb.REPAIRS, "
            "e.g. repairs=['units_colnames']")
    if isinstance(repairs, (str, bytes)):
        raise TypeError(
            "repairs= takes a list of repair names, not one string; "
            f"write repairs=[{repairs!r}]")
    names = list(dict.fromkeys(repairs))
    if not names:
        raise ValueError(
            "repairs= names no repair; pass at least one name from jnwb.REPAIRS: "
            f"{list(REPAIRS)}")
    unknown = [n for n in names if n not in REPAIRS]
    if unknown:
        raise ValueError(
            f"unknown repair {unknown[0]!r}; pass names from jnwb.REPAIRS: {list(REPAIRS)}")
    src_path = Path(src)
    dst_path = Path(dst)
    if src_path.resolve() == dst_path.resolve():
        raise ValueError(f"repair_nwb: dst resolves to src ({src_path}); the source "
                         f"is never modified, so name a different dst")
    if dst_path.exists() and not overwrite:
        raise FileExistsError(f"destination exists (pass overwrite=True): {dst_path}")
    planners = {
        "squeeze_scalar_attributes": _plan_squeeze_scalar_attributes,
        "units_colnames": _plan_units_colnames,
        "vector_index_types": _plan_vector_index_types,
        "waveform_index_dtype": _plan_waveform_index_dtype,
    }
    with h5py.File(src_path, "r") as handle:
        _require_session_description(handle)
        plans = {name: planners[name](handle) for name in names}
        issues = _contradiction_issues(handle)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    handle_tmp, tmp = tempfile.mkstemp(suffix=".nwb", dir=str(dst_path.parent))
    os.close(handle_tmp)
    tmp_path = Path(tmp)
    try:
        with h5py.File(src_path, "r") as src_h, h5py.File(tmp_path, "w") as dst_h:
            _structural_copy(src_h, dst_h)
        with h5py.File(tmp_path, "r+") as dst_h:
            _apply_repairs(dst_h, plans)
            with h5py.File(src_path, "r") as src_h:
                _resolve_references(src_h, dst_h)
        schema = _schema_issues(tmp_path)
        if schema:
            raise NWBMutationError(
                f"repair_nwb: the repaired copy fails schema validation with {len(schema)} "
                f"error(s); first: {schema[0].message}; nothing written",
                issues=schema)
        tmp_path.replace(dst_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    applied = []
    for name in names:
        if name == "squeeze_scalar_attributes":
            applied.append(AppliedOperation(
                name, tuple(p if p.startswith("/") else "/" + p
                            for p, _ in plans[name])))
        elif name == "units_colnames":
            applied.append(AppliedOperation(name, ("units",)))
        elif name == "vector_index_types":
            applied.append(AppliedOperation(name, tuple(p for p, _ in plans[name])))
        elif name == "waveform_index_dtype":
            applied.append(AppliedOperation(name, tuple(plans[name])))
            applied.append(AppliedOperation(CAST_OPERATION, tuple(plans[name])))
    checks: tuple[MutationCheck, ...] = ()
    if verify:
        preliminary = MutationReport(
            category=REPAIR_CATEGORY, src=str(src_path), dst=str(dst_path),
            src_sha256=None, dst_sha256=None, applied=tuple(applied),
            checks=(), issues=tuple(issues), waived=(),
            provenance=Provenance(software_version="repair_nwb",
                                  backend="numpy"),
            lineage=Lineage(source_type="NWBFile", source_id="repair_nwb",
                            operation=REPAIR_CATEGORY),
            ok=True)
        rep = verify_nwb(dst_path, against=src_path, report=preliminary)
        checks = rep.checks
        if not rep.ok:
            failed = [f"{c.name}: {c.detail}" for c in checks if not c.ok]
            raise NWBVerificationError(
                f"repair_nwb wrote {dst_path}, and {len(failed)} verification "
                "check(s) failed; the file is left in place for inspection: "
                + " | ".join(d[:300] for d in failed))
    return _report_and_verify(
        REPAIR_CATEGORY, src_path, dst_path, applied, issues, checks,
        {"repairs": names, "overwrite": overwrite, "verify": verify})


def verify_nwb(dst: str | Path, *, against: str | Path | None = None,
               report: MutationReport | None = None,
               n_check: int = 200_000) -> MutationReport:
    """Re-read one written NWB file and check it, with or without its source.

    Parameters
    ----------
    dst : str or Path
        The written NWB file. Never modified.
    against : str or Path, optional
        The source file the writer started from. Compares content, not storage:
        ``file_create_date`` is ignored, object references are dereferenced and
        their targets compared by value, and scalars are read whole. Dataset
        attributes are compared except ``object_id``. Requires ``report``.
    report : MutationReport, optional
        The writer's report. Its ``applied`` records name the operation and the
        dataset paths that operation changed; ``verify_nwb`` exempts exactly
        those paths. A record named ``"cast"`` declares its paths as dtype casts
        of the source. Dataset attributes are compared, with references in
        attributes dereferenced to their targets.
    n_check : int
        Rows compared per dataset (default 200000). Must be at least 1.

    Returns
    -------
    MutationReport
        Category ``"verify written output"``; ``ok`` is True when every check
        passed. A failed check is ``ok=False`` in the report; writers turn it
        into an error and leave ``dst`` for inspection.

    Raises
    ------
    FileNotFoundError
        ``dst`` (or ``against``) does not exist.
    ValueError
        ``against`` without ``report``: without the declared changes every
        difference would be unexplained. Also when ``n_check`` is below 1.

    References:
        Rübel, O., et al. (2022). The Neurodata Without Borders ecosystem for
        neurophysiological data science. eLife 11, e78362. doi:10.7554/eLife.78362
        -- the NWB format this operation checks a file against.
    """
    import jnwb

    if against is not None and report is None:
        raise ValueError("against= without report=: without the declared changes every "
                         "difference would be unexplained")
    if not isinstance(n_check, int) or isinstance(n_check, bool) or n_check < 1:
        raise ValueError(f"n_check must be an integer of at least 1, got {n_check!r}")
    dst_path = Path(dst)
    if not dst_path.is_file():
        raise FileNotFoundError(dst_path)
    against_path = Path(against) if against is not None else None
    if against_path is not None and not against_path.is_file():
        raise FileNotFoundError(against_path)

    checks: list[MutationCheck] = [_read_check(dst_path), _schema_check(dst_path)]
    checks.extend(_resolution_check(dst_path, n_check))
    if against_path is not None:
        assert report is not None
        checks.extend(_comparison_checks(dst_path, against_path, report, n_check))

    ok = all(c.ok for c in checks)
    src_text = str(against_path) if against_path is not None else None
    provenance = Provenance(
        software_version=jnwb.__version__, backend="numpy",
        parameters={"n_check": n_check,
                    "against": src_text,
                    "compared": against_path is not None},
        environment={"pynwb": _version("pynwb") or "unknown",
                     "hdmf": _version("hdmf") or "unknown"})
    lineage = Lineage(source_type="NWBFile",
                      source_id=(_sha256(against_path) if against_path is not None
                                 else _sha256(dst_path)),
                      operation=CATEGORY)
    return MutationReport(
        category=CATEGORY, src=src_text, dst=str(dst_path),
        src_sha256=_sha256(against_path) if against_path is not None else None,
        dst_sha256=_sha256(dst_path),
        applied=tuple(report.applied) if report is not None else (),
        checks=tuple(checks), issues=(),
        waived=tuple(report.waived) if report is not None else (),
        provenance=provenance, lineage=lineage, ok=ok)
