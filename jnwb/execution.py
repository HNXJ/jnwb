"""Caller-held execution records and a filesystem result cache.

An execution record names what ran where: the device string the backend resolved and the
worker count the parallel loop ran with. It carries no behaviour and selects nothing; a
caller builds one beside a result and reads it back later. The cache stores one value per
key under a caller-chosen directory, with no global state: the caller passes ``cache_dir``
to every call. Entries are ``.npz`` archives written with ``allow_pickle=False``; each one
carries the key and the jnwb version it was written with, so a load from another version,
or an entry filed under another key, reads as a miss.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

__all__ = [
    "ExecutionRecord",
    "cache_key",
    "cache_store",
    "cache_load",
    "cache_clear",
]


@dataclass(frozen=True)
class ExecutionRecord:
    """What ran where, recorded by the caller.

    ``device`` is the device string the backend resolved for the run, such as
    ``"cpu"``. ``n_jobs`` is the worker count the parallel loop ran with.
    """

    device: str
    n_jobs: int

    def __post_init__(self) -> None:
        if not isinstance(self.device, str):
            raise TypeError(f"device must be a string, got {type(self.device).__name__}")
        if isinstance(self.n_jobs, bool) or not isinstance(self.n_jobs, int):
            raise TypeError(f"n_jobs must be an int, got {type(self.n_jobs).__name__}")
        if self.n_jobs < 1:
            raise ValueError(f"n_jobs must be at least 1, got {self.n_jobs!r}")


_KEY_RE = re.compile(r"[A-Za-z0-9_.-]+")


def _check_key(key: str) -> None:
    if not isinstance(key, str) or not _KEY_RE.fullmatch(key):
        raise ValueError(f"cache key must match {_KEY_RE.pattern}, got {key!r}")
    if key in (".", ".."):
        raise ValueError(f"cache key must not be {key!r}")


def _canonical(value: Any) -> Any:
    """A JSON-able form of ``value`` with arrays by dtype, shape and bytes."""
    import numpy as np

    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"__bytes__": value.hex()}
    if isinstance(value, np.ndarray):
        return {
            "__ndarray__": True,
            "dtype": str(value.dtype),
            "shape": list(value.shape),
            "data": value.tobytes().hex(),
        }
    if isinstance(value, np.generic):
        return {
            "__numpy_scalar__": True,
            "dtype": str(value.dtype),
            "data": value.tobytes().hex(),
        }
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value, key=repr)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    raise TypeError(
        f"unhashable value of type {type(value).__name__!r} has no canonical form"
    )


def cache_key(name: str, inputs: Any, params: dict) -> str:
    """A hex key from the operation name, the inputs, the parameters and the version.

    Arrays enter the hash as dtype, shape and raw bytes; mappings enter as canonical
    JSON with sorted keys, so mapping order never moves the key. The jnwb version is
    mixed in, so a key from one version never reads a value another version wrote.
    A value with no canonical form raises ``TypeError`` naming its type.
    """
    # top-level `from jnwb import __version__` would be a circular import.
    from jnwb import __version__ as _jnwb_version

    if not isinstance(name, str) or not name:
        raise ValueError(f"operation name must be a non-empty string, got {name!r}")
    if not isinstance(params, dict):
        raise ValueError(f"params must be a dict, got {type(params).__name__}")
    body = "\x00".join(
        (
            name,
            json.dumps(_canonical(inputs), sort_keys=True),
            json.dumps(_canonical(params), sort_keys=True),
            str(_jnwb_version),
        )
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _path_for(cache_dir: str | Path, key: str) -> Path:
    _check_key(key)
    directory = Path(cache_dir)
    return directory / (key + ".npz")


_SCALAR_TYPES = (bool, int, float, complex, str, bytes)


def _encode(value: Any, arrays: dict[str, Any], prefix: str) -> Any:
    """Split ``value`` into a JSON-able manifest; array leaves land in ``arrays``."""
    import numpy as np

    if isinstance(value, np.ndarray):
        leaf = prefix + f".a{len(arrays)}"
        arrays[leaf] = np.ascontiguousarray(value)
        return {"__leaf__": leaf, "dtype": str(value.dtype), "shape": list(value.shape)}
    if isinstance(value, np.generic):
        leaf = prefix + f".a{len(arrays)}"
        arrays[leaf] = np.ascontiguousarray(value)
        return {"__leaf__": leaf, "dtype": str(value.dtype), "shape": []}
    if isinstance(value, _SCALAR_TYPES):
        leaf = prefix + f".a{len(arrays)}"
        arrays[leaf] = np.ascontiguousarray(np.asarray(value))
        return {"__leaf__": leaf, "dtype": str(np.asarray(value).dtype), "shape": []}
    if isinstance(value, dict):
        return {
            "__dict__": True,
            "items": {key: _encode(value[key], arrays, prefix) for key in sorted(value, key=repr)},
        }
    if isinstance(value, list):
        return {"__list__": True, "items": [_encode(item, arrays, prefix) for item in value]}
    if isinstance(value, tuple):
        return {"__tuple__": True, "items": [_encode(item, arrays, prefix) for item in value]}
    raise TypeError(
        f"cache values hold arrays, scalars, dicts, lists and tuples, "
        f"not {type(value).__name__!r}"
    )


def _decode(manifest: Any, arrays: dict[str, Any]) -> Any:
    import numpy as np

    if isinstance(manifest, dict) and "__leaf__" in manifest:
        arr = np.asarray(arrays[manifest["__leaf__"]])
        if manifest["shape"] == [] and arr.dtype.kind not in "mM":
            return arr.reshape(()).tolist()
        return arr.reshape(manifest["shape"]).astype(manifest["dtype"], copy=False)
    if isinstance(manifest, dict) and "__dict__" in manifest:
        return {key: _decode(manifest["items"][key], arrays) for key in manifest["items"]}
    if isinstance(manifest, dict) and "__list__" in manifest:
        return [_decode(item, arrays) for item in manifest["items"]]
    if isinstance(manifest, dict) and "__tuple__" in manifest:
        return tuple(_decode(item, arrays) for item in manifest["items"])
    raise ValueError(f"unreadable cache manifest {manifest!r}")


def cache_store(cache_dir: str | Path, key: str, value: Any) -> Path:
    """Save ``value`` under ``key`` in ``cache_dir`` and return the file path.

    Arrays, scalars, dicts, lists and tuples are stored as ``.npz`` archives written
    with ``allow_pickle=False``; anything else raises ``TypeError``. The write lands
    atomically: bytes go to a temporary sibling file that is flushed and synced, then
    renamed over the target, so a reader never sees a half-written entry.
    """
    import numpy as np

    # top-level `from jnwb import __version__` would be a circular import.
    from jnwb import __version__ as _jnwb_version

    target = _path_for(cache_dir, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, Any] = {}
    manifest = _encode(value, arrays, "v")
    payload = {
        "__key__": np.asarray(key),
        "__version__": np.asarray(str(_jnwb_version)),
        "__manifest__": np.asarray(json.dumps(manifest, sort_keys=True)),
    }
    payload.update(arrays)
    tmp_name = f".{target.name}.{os.getpid()}.tmp"
    tmp = target.parent / tmp_name
    handle = open(tmp, "wb")
    with handle:
        np.savez(handle, allow_pickle=False, **payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, target)
    return target


def cache_load(cache_dir: str | Path, key: str) -> Any:
    """The value stored under ``key`` in ``cache_dir``, or None on a miss.

    A missing entry reads as None, and so does a stale one: an archive whose stored
    key or stored version differs from the requested key or the running jnwb version
    never reads as a hit. A present entry from this version that cannot be read
    raises, so a corrupt file never reads as a value.
    """
    import numpy as np

    # top-level `from jnwb import __version__` would be a circular import.
    from jnwb import __version__ as _jnwb_version

    target = _path_for(cache_dir, key)
    if not target.is_file():
        return None
    with open(target, "rb") as handle:
        archive = np.load(handle, allow_pickle=False)
        stored_key = str(archive["__key__"].reshape(()).tolist())
        stored_version = str(archive["__version__"].reshape(()).tolist())
        if stored_key != key or stored_version != str(_jnwb_version):
            return None
        manifest = json.loads(str(archive["__manifest__"].reshape(()).tolist()))
        arrays = {name: archive[name] for name in archive.files if name.startswith("v")}
    return _decode(manifest, arrays)


def cache_clear(cache_dir: str | Path) -> int:
    """Remove the entries ``cache_store`` wrote directly under ``cache_dir``; return the count.

    An entry is a ``.npz`` archive whose stored key equals its file name; any other file,
    other ``.npz`` archives included, stays.
    """
    import numpy as np

    directory = Path(cache_dir)
    if not directory.is_dir():
        return 0
    removed = 0
    for child in sorted(directory.iterdir()):
        if not (child.is_file() and child.suffix == ".npz" and _KEY_RE.fullmatch(child.stem)):
            continue
        try:
            with open(child, "rb") as handle, np.load(handle, allow_pickle=False) as archive:
                if "__key__" not in archive.files:
                    continue
                stored_key = str(archive["__key__"].reshape(()).tolist())
        except (OSError, ValueError):
            continue
        if stored_key == child.stem:
            child.unlink()
            removed += 1
    return removed
