"""NWB file I/O with scoped HDMF builder repairs for malformed files.

Module-internal: not part of ``jnwb.__all__``. Use public metadata/compression helpers
that call ``nwb_read_io`` / ``read_nwb`` internally.

Repairs apply only while a jnwb-owned read is active. ``import jnwb`` does not alter
HDMF global state.

Concurrency: repairs temporarily replace ``BuildManager.construct`` on the class.
Another thread calling PyNWB/HDMF during that window inherits the patched method.
There is no smaller hook in the HDMF read path that avoids class-level replacement.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

import numpy as np
from pynwb import NWBHDF5IO

_patch_depth = 0
_patch_lock = threading.Lock()
_saved_construct: Any = None


class MissingRequiredNWBFieldError(Exception):
    """A required NWB field is absent from the on-disk builder tree."""

    def __init__(self, field_name: str) -> None:
        self.field_name = field_name
        super().__init__(
            f"NWB file is missing required field '{field_name}'; "
            "jnwb does not synthesize required metadata"
        )


def _repair_builder(builder: Any, orig_construct: Any) -> None:
    b_name = getattr(builder, "name", None)

    if hasattr(builder, "attributes"):
        for key, value in builder.attributes.items():
            if isinstance(value, np.ndarray) and value.ndim == 1 and len(value) == 1:
                element = value[0]
                if isinstance(element, bytes):
                    builder.attributes[key] = element.decode("utf-8", errors="replace")
                elif isinstance(element, str):
                    builder.attributes[key] = str(element)

    if (
        hasattr(builder, "attributes")
        and builder.attributes.get("neurodata_type") == "NWBFile"
        and "session_description" not in builder.datasets
    ):
        raise MissingRequiredNWBFieldError("session_description")

    if b_name == "units":
        colnames = list(builder.attributes.get("colnames", []))
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


@contextmanager
def hdmf_build_repair_context() -> Iterator[None]:
    """Enable malformed-builder repairs for the duration of a jnwb NWB read."""
    global _patch_depth, _saved_construct

    from hdmf.build.manager import BuildManager

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


@contextmanager
def nwb_read_io(path: Any, mode: str = "r", **kwargs: Any) -> Iterator[NWBHDF5IO]:
    """Open an NWB file; apply builder repairs on read paths only."""
    if mode != "r":
        with NWBHDF5IO(path, mode, **kwargs) as io:
            yield io
        return
    with hdmf_build_repair_context():
        with NWBHDF5IO(path, mode, **kwargs) as io:
            yield io


def read_nwb(path: Any, **kwargs: Any) -> Any:
    """Read an NWB file through jnwb's scoped HDMF builder repairs."""
    with nwb_read_io(path, "r", **kwargs) as io:
        return io.read()
