"""NWB file I/O with scoped HDMF builder repairs for malformed files.

Module-internal, with one exception: the module is not exported, but
``MissingRequiredNWBFieldError`` is in ``jnwb.__all__`` and is meant to be caught by name. The
sentence here used to claim otherwise, which told a reader hitting that raise that nothing in the
file was catchable. Prefer the public metadata/compression helpers, which call ``nwb_read_io`` /
``read_nwb`` internally.

Repairs apply only while a jnwb-owned read is active. ``import jnwb`` does not alter
HDMF global state.

Concurrency: repairs temporarily replace ``BuildManager.construct`` on the class.
Another thread calling PyNWB/HDMF during that window inherits the patched method.
There is no smaller hook in the HDMF read path that avoids class-level replacement.
"""
from __future__ import annotations

import threading
import warnings
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Iterator, Sequence, Tuple, Union

import numpy as np
from pynwb import NWBFile, NWBHDF5IO

PathLike = Union[str, Path]
#: What every path-or-handle entry point in `nwb_events` and `nwb_inspect` accepts.
NWBInput = Union[PathLike, NWBFile]

_patch_depth = 0
_patch_lock = threading.Lock()
_saved_construct: Any = None

#: Required NWB fields the caller has opted to tolerate for the duration of one read, and the
#: attributes the repair squeezed during it. The HDMF patch is class-level and depth-counted, so
#: per-read state cannot ride on a parameter: a ContextVar keeps it scoped to the calling context
#: and out of the way of another thread reading a different file through the same patched method.
_ALLOW_MISSING: ContextVar[frozenset] = ContextVar("_ALLOW_MISSING", default=frozenset())
_SQUEEZED: ContextVar[list] = ContextVar("_SQUEEZED", default=[])


class SqueezedAttributeWarning(UserWarning):
    """A length-1 array attribute was collapsed to a scalar while reading a malformed file.

    The repair is correct and the value is right, but a caller that cannot see it happened cannot
    record, in a receipt written from the file, that the file needed repairing. One warning is
    raised per read rather than per attribute: a badly written file can carry hundreds, and a
    warning nobody can read through is a warning nobody reads.
    """


class MissingRequiredNWBFieldError(Exception):
    """A required NWB field is absent from the on-disk builder tree."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(
            f"NWB file is missing required field '{field_name}'; "
            "jnwb does not synthesize required metadata"
        )


#: Attributes the NWB schema specifies as sequences. A length-1 value of one of these is
#: a one-element list, not a scalar that happens to be wrapped, so the repair below must
#: leave it alone. 05-37: a units table with a single column carries
#: ``colnames = array(['spike_times'])``; collapsing that to the string ``'spike_times'``
#: made the next ``list(...)`` spell it out, one character per column, and every jnwb
#: entry point died on a file plain pynwb reads without complaint.
_SEQUENCE_ATTRIBUTES = frozenset({"colnames"})


def _repair_builder(builder: Any, orig_construct: Any) -> None:
    b_name = getattr(builder, "name", None)

    if hasattr(builder, "attributes"):
        for key, value in builder.attributes.items():
            if key in _SEQUENCE_ATTRIBUTES:
                continue
            if isinstance(value, np.ndarray) and value.ndim == 1 and len(value) == 1:
                element = value[0]
                if isinstance(element, bytes):
                    builder.attributes[key] = element.decode("utf-8", errors="replace")
                    _SQUEEZED.get().append(f"{b_name or '?'}.{key}")
                elif isinstance(element, str):
                    builder.attributes[key] = str(element)
                    _SQUEEZED.get().append(f"{b_name or '?'}.{key}")

    if (
        hasattr(builder, "attributes")
        and builder.attributes.get("neurodata_type") == "NWBFile"
        and "session_description" not in builder.datasets
    ):
        if "session_description" not in _ALLOW_MISSING.get():
            raise MissingRequiredNWBFieldError("session_description")
        # Waiving jnwb's refusal is not enough to open the file: pynwb takes
        # `session_description` as a required positional argument of `NWBFile.__init__`, so
        # without it HDMF raises ConstructError from a TypeError and the read fails anyway. The
        # builder must therefore carry *something*, and the honest choice is the empty string:
        # falsy, sorts and prints as absent, and impossible to mistake for a description the file
        # actually contained. `jnwb_waived_requirements` on the returned object is what tells a
        # caller the emptiness was jnwb's doing rather than the recording's.
        from hdmf.build import DatasetBuilder

        builder.set_dataset(DatasetBuilder("session_description", ""))

    if b_name == "units":
        raw_colnames = builder.attributes.get("colnames", [])
        if isinstance(raw_colnames, (str, bytes)):
            # Belt and braces for the same defect: a bare string here would otherwise be
            # iterated character by character, whatever put it there.
            raw_colnames = [raw_colnames]
        colnames = list(raw_colnames)
        for index_col in (
            "spike_times_index",
            "waveform_mean_index",
            "spike_amplitudes_index",
        ):
            if index_col in colnames:
                colnames.remove(index_col)
        for col in ("spike_times", "waveform_mean", "spike_amplitudes"):
            if (
                hasattr(builder, "datasets")
                and col in builder.datasets
                and col not in colnames
            ):
                colnames.append(col)
        builder.attributes["colnames"] = np.array(colnames, dtype=object)

    if b_name in ("waveform_mean_index", "spike_amplitudes_index"):
        if hasattr(builder, "attributes"):
            builder.attributes["neurodata_type"] = "VectorIndex"
            target_name = b_name.replace("_index", "")
            if builder.parent and target_name in builder.parent:
                builder.attributes["target"] = builder.parent[target_name]

        if b_name == "waveform_mean_index" and "data" in builder:
            builder["data"] = np.array(builder["data"], dtype=np.int64)


def _make_patched_construct(orig_construct: Any) -> Any:
    def patched_construct(self: Any, *args: Any, **kwargs: Any) -> Any:
        if args:
            builder = args[0]
        else:
            builder = kwargs.get("builder")
        if builder is not None:
            _repair_builder(builder, orig_construct)
        return orig_construct(self, *args, **kwargs)

    patched_construct.__name__ = "jnwb_hdmf_repair_construct"
    return patched_construct


#: Required NWB fields ``allow_missing`` recognises. Anything else is a caller error rather than a
#: silent no-op: a typo that quietly tolerates nothing is the failure mode this list exists to
#: prevent. It grows only when a refusal for that field actually exists above.
TOLERABLE_MISSING_FIELDS = frozenset({"session_description"})


def _normalise_allow_missing(allow_missing: Union[Sequence[str], str, None]) -> frozenset:
    """Validate the opt-in and return it as a set, rejecting a field jnwb never refuses on."""
    if allow_missing is None:
        return frozenset()
    if isinstance(allow_missing, str):
        allow_missing = (allow_missing,)
    requested = frozenset(allow_missing)
    unknown = requested - TOLERABLE_MISSING_FIELDS
    if unknown:
        raise ValueError(
            f"allow_missing={sorted(unknown)!r} is not a field jnwb refuses on, so tolerating it "
            f"would do nothing. Known: {sorted(TOLERABLE_MISSING_FIELDS)!r}."
        )
    return requested


@contextmanager
def hdmf_build_repair_context(
    allow_missing: Union[Sequence[str], str, None] = None,
) -> Iterator[None]:
    """Enable malformed-builder repairs for the duration of a jnwb NWB read.

    ``allow_missing`` names required fields whose absence is tolerated for this read. Nothing is
    synthesized: the field stays absent on the returned object, exactly as it is absent on disk.
    Ruled 2026-09-19, and the distinction is the whole point -- `artifacts/goal.md` section 4
    forbids substituting a value, not reading a file that lacks one.
    """
    global _patch_depth, _saved_construct

    from hdmf.build.manager import BuildManager

    allow_token = _ALLOW_MISSING.set(_normalise_allow_missing(allow_missing))
    squeezed: list = []
    squeeze_token = _SQUEEZED.set(squeezed)

    with _patch_lock:
        if _patch_depth == 0:
            _saved_construct = BuildManager.construct
            BuildManager.construct = _make_patched_construct(_saved_construct)
        _patch_depth += 1
    try:
        yield
    finally:
        with _patch_lock:
            _patch_depth -= 1
            if _patch_depth == 0:
                BuildManager.construct = _saved_construct
                _saved_construct = None
        _ALLOW_MISSING.reset(allow_token)
        _SQUEEZED.reset(squeeze_token)
        if squeezed:
            shown = ", ".join(sorted(set(squeezed))[:5])
            more = len(set(squeezed)) - 5
            warnings.warn(
                f"jnwb repaired {len(squeezed)} malformed length-1 array attribute(s) while "
                f"reading this file, collapsing each to the scalar it wrapped: {shown}"
                + (f", and {more} more" if more > 0 else "")
                + ". The values are correct; the file is not. Anything written from this read "
                "records data that needed repairing.",
                SqueezedAttributeWarning,
                stacklevel=3,
            )


@contextmanager
def nwb_read_io(
    path: Any,
    mode: str = "r",
    allow_missing: Union[Sequence[str], str, None] = None,
    **kwargs: Any,
) -> Iterator[NWBHDF5IO]:
    """Open an NWB file; apply builder repairs on read paths only.

    ``allow_missing`` is accepted only for ``mode='r'``: the repairs, and therefore the refusal it
    waives, exist on the read path alone. Passing it for a write mode raises rather than being
    quietly ignored.
    """
    if mode != "r":
        if allow_missing:
            raise ValueError(
                f"allow_missing is a read-path option and mode is {mode!r}. jnwb applies builder "
                "repairs only when reading, so tolerating a missing field here would do nothing."
            )
        with NWBHDF5IO(path, mode, **kwargs) as io:
            yield io
        return
    with hdmf_build_repair_context(allow_missing=allow_missing):
        with NWBHDF5IO(path, mode, **kwargs) as io:
            yield io


#: Attribute recording which required fields a read tolerated. Present on every object returned by
#: :func:`read_nwb`, empty tuple in the ordinary case, so a caller can branch on it without a
#: ``hasattr`` and a receipt can state that the file was incomplete.
WAIVED_REQUIREMENTS_ATTR = "jnwb_waived_requirements"


def read_nwb(
    path: Any, allow_missing: Union[Sequence[str], str, None] = None, **kwargs: Any
) -> Any:
    """Read an NWB file through jnwb's scoped HDMF builder repairs.

    By default a file missing a required field is refused, with
    :class:`MissingRequiredNWBFieldError`. ``allow_missing`` names fields to tolerate for this
    read -- today only ``"session_description"``. Nothing is synthesized: the field is absent on
    the returned object exactly as it is absent on disk, and
    ``nwbfile.jnwb_waived_requirements`` records what was waived so a receipt written from this
    read can say the file was incomplete.

        read_nwb(path, allow_missing=("session_description",))
    """
    waived: Tuple[str, ...] = tuple(sorted(_normalise_allow_missing(allow_missing)))
    with nwb_read_io(path, "r", allow_missing=allow_missing, **kwargs) as io:
        nwbfile = io.read()
    try:
        setattr(nwbfile, WAIVED_REQUIREMENTS_ATTR, waived)
    except (AttributeError, TypeError):  # pragma: no cover - pynwb container restriction
        # Recording it is the point of the opt-in, so a read that tolerated something and cannot
        # say so must not pass silently. An ordinary read loses nothing and carries on.
        if waived:
            raise
    return nwbfile


def _with_nwb(path_or_nwb: NWBInput, fn):
    """Call ``fn`` with an open NWBFile, opening and closing ``path_or_nwb`` if needed.

    An already-open handle is passed straight through and is not closed here: the caller
    that opened it owns it.
    """
    if isinstance(path_or_nwb, NWBFile):
        return fn(path_or_nwb)
    path = Path(path_or_nwb)
    if not path.exists():
        raise FileNotFoundError(f"NWB file not found: {path}")
    with nwb_read_io(str(path), load_namespaces=True) as io:
        return fn(io.read())
