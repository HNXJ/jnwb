"""Array backend conversion for jnwb."""

from __future__ import annotations

from typing import Any

import numpy as np

from .errors import (
    BLOCKED_BACKEND_CUPY_UNAVAILABLE,
    BLOCKED_BACKEND_JAX_UNAVAILABLE,
    JnwbBlockedError,
)


def to_backend(x: Any, backend: str = "numpy") -> Any:
    """Convert array-like data to the requested backend after NWB load.

    Supported backends: numpy (always), cupy (optional), jax (optional).
    """
    backend = backend.lower()
    if backend == "numpy":
        return np.asarray(x)

    if backend == "cupy":
        try:
            import cupy as cp  # type: ignore
        except ImportError as exc:
            raise JnwbBlockedError(
                "CuPy is not installed",
                code=BLOCKED_BACKEND_CUPY_UNAVAILABLE,
            ) from exc
        return cp.asarray(x)

    if backend == "jax":
        try:
            import jax.numpy as jnp  # type: ignore
        except ImportError as exc:
            raise JnwbBlockedError(
                "JAX is not installed",
                code=BLOCKED_BACKEND_JAX_UNAVAILABLE,
            ) from exc
        return jnp.asarray(x)

    raise ValueError(f"Unsupported backend: {backend}")
