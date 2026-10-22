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
    n = len(source) if source.shape == () else min(n_check, source.shape[0])
    if source.shape == ():
        expected = np.asarray(source[()]).astype(dest.dtype, copy=False)
        got = dest[()]
    else:
        expected = np.asarray(source[:n]).astype(dest.dtype, copy=False)
        got = dest[:n]
    if not _values_equal(got, expected):
        return False, "differs from the cast of the source"
    same, detail = _attrs_equal(source, dest, handle_source, handle_dest, n_check)
    if not same:
        return False, detail
    return True, f"equals the cast of the source over first {n} rows"


def _comparison_checks(dst_path: Path, against_path: Path, report: MutationReport,
                       n_check: int) -> list[MutationCheck]:
    out: list[MutationCheck] = []
    exempt: dict[str, str] = {}
    for record in report.applied:
        for changed in record.changed:
            exempt.setdefault(_norm(changed), record.name)
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
            if normed in exempt and exempt[normed] != CAST_OPERATION:
                out.append(MutationCheck(
                    f"/{normed} declared by the report", True,
                    f"operation {exempt[normed]!r}; exempt from byte comparison"))
                continue
            if normed not in dst_names:
                out.append(MutationCheck(
                    f"/{normed} matches the source as declared", False,
                    "unexplained difference: absent from the destination"))
                continue
            try:
                if normed in exempt:
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
