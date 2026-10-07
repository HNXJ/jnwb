"""Array backends: choosing one, converting to it and back to NumPy."""

from __future__ import annotations

import warnings
import numpy as np


# ===========================================================================
# PRIVATE – tensor handling
# ===========================================================================

def _get_xp(arr):
    """Resolve numpy or cupy namespace depending on array type."""
    try:
        import cupy as cp
        if isinstance(arr, cp.ndarray):
            return cp
    except ImportError:
        pass
    return np


# ===========================================================================
# PRIVATE – execution / backend
# ===========================================================================

_VALID_BACKENDS = ("auto", "numpy", "scipy", "cupy", "jax", "torch")
#: The backends that name an accelerator library jrsa does not compute with.
_ACCELERATOR_BACKENDS = ("cupy", "jax", "torch")


def _get_backend(backend: str, device: str) -> dict:
    """Validate the requested backend and report the one that executes.

    Every metric converts its inputs with `_ensure_np` before it computes anything, so
    the executing backend is NumPy whatever was requested. This used to report the
    *request*: `jrsa(device='cuda', backend='cupy')` recorded
    `{'backend': 'cupy', 'device': 'cuda'}` for arithmetic that ran on the CPU, and
    `_autodetect_backend` picked a name from what happened to be importable, which
    likewise changed the record and nothing else. `parameters['backend']` still carries
    what the caller asked for; `execution['backend']` now carries what ran.

    Naming an accelerator library is a request that is not delivered, so it is announced
    the way a denied ``device='cuda'`` is.
    """
    requested = str(backend).strip().lower()
    if requested not in _VALID_BACKENDS:
        raise ValueError(
            f"jrsa: unrecognised backend {backend!r}; expected one of "
            f"{sorted(_VALID_BACKENDS)}."
        )
    if requested in _ACCELERATOR_BACKENDS:
        warnings.warn(
            f"jrsa: backend={requested!r} was requested, but every jrsa metric computes in "
            f"NumPy on the CPU; execution['backend'] records 'numpy'.",
            RuntimeWarning,
            stacklevel=3,
        )
    return {"name": "numpy", "requested": requested, "device": device}


def _to_backend(arr, backend_ctx: dict) -> np.ndarray:
    """Convert one input to a float64 NumPy array on the host, or raise.

    Dispatch is by type, never by attribute: an ndarray's `.data` is a raw buffer, a CuPy
    array's is a device pointer and a sparse matrix's is its stored non-zeros, so taking
    `.data` from anything that has one returned a wrong array or raised. Accepted: NumPy
    arrays and array-likes, scipy.sparse (densified), torch tensors on any device
    (detached, copied to host), CuPy arrays (copied to host), JAX arrays, and a container
    without `__array__` whose `.data` is one of these (a pynwb TimeSeries). A masked array
    with a masked element raises, because no metric honours a mask.

    jrsa is a NumPy estimator; `backend` and `device` are validated and recorded, and
    change no number.
    """
    if isinstance(arr, np.ma.MaskedArray):
        if np.ma.getmaskarray(arr).any():
            raise TypeError(
                "jrsa: a masked array with masked elements was passed, and no jrsa metric "
                "honours a mask; converting it would compute on the masked values. Drop "
                "or impute them first."
            )
        arr = np.ma.getdata(arr)
    if isinstance(arr, np.ndarray):
        return np.asarray(arr, dtype=np.float64)
    library = type(arr).__module__.split(".")[0]
    if library == "scipy":
        import scipy.sparse
        if scipy.sparse.issparse(arr):
            return np.asarray(arr.toarray(), dtype=np.float64)
    if library == "torch":
        return arr.detach().cpu().double().numpy()
    if library == "cupy":
        return np.asarray(arr.get(), dtype=np.float64)
    if hasattr(arr, "__array__") or isinstance(arr, (list, tuple)) or np.isscalar(arr):
        return np.asarray(arr, dtype=np.float64)
    if hasattr(arr, "data"):
        return _to_backend(arr.data, backend_ctx)
    return np.asarray(arr, dtype=np.float64)


# ===========================================================================
# PRIVATE – metric implementations
# ===========================================================================
# Every metric has the same signature:
#   _metric(x1, x2, axis=-1, **kwargs) -> (value, statistic, effect, p, df)
# When x2 is None, within-x1 analysis is performed.

def _ensure_np(*arrays):
    """Return list of plain numpy arrays (handles torch/jax/cupy)."""
    out = []
    for a in arrays:
        if a is None:
            out.append(None)
            continue
        if hasattr(a, "numpy"):
            try:
                a = a.numpy()
            except (RuntimeError, TypeError, ValueError):
                a = np.asarray(a)
        if hasattr(a, "get"):
            a = a.get()
        out.append(np.asarray(a, dtype=np.float64))
    return out
