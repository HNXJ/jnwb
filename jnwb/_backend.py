"""Decides whether a computation runs on GPU, and says so.

Private module.

Fifteen call sites across seven modules each carried their own probe and fallback
policy, which caused two problems:

* **The sites asked different questions.** Some treated a bare ``import cupy`` as proof
  of a usable GPU; others asked ``torch.cuda.is_available()``. CuPy imports fine with
  the package installed and no working driver, so the sites disagreed about whether the
  same machine had a GPU.
* **Falling back was silent.** A caller who asked for ``device='cuda'`` and got CPU
  arithmetic had no way to find out. This is the mechanism behind JNWB-004: an
  intermittent GPU failure inside a loop swapped the estimator mid-null, and the
  returned dict said nothing.

A requested accelerator that cannot be delivered warrants a warning, every time. CPU
callers are silent, since nothing was denied them.

CPU and GPU paths here differ numerically, and in places use different estimators
(windows, detrending, reduction order). Anything reporting a device-dependent number
should record which device produced it.
"""

from __future__ import annotations

import warnings
from typing import Optional

__all__ = [
    "CPU",
    "CUDA",
    "cupy_available",
    "torch_cuda_available",
    "gpu_available",
    "resolve_device",
    "warn_device_fallback",
]

CPU = "cpu"
CUDA = "cuda"


def cupy_available() -> bool:
    """True if CuPy imports and reports a usable CUDA device.

    The import alone proves nothing: the wheel installs and imports with no driver
    present, failing only at the first allocation. Sites probing by import claimed a GPU
    on machines that had none.
    """
    try:
        import cupy as cp

        return cp.cuda.runtime.getDeviceCount() > 0
    except (ImportError, OSError, RuntimeError, AttributeError):
        return False


def torch_cuda_available() -> bool:
    """True if PyTorch imports and reports a CUDA device."""
    try:
        import torch

        return bool(torch.cuda.is_available())
    except (ImportError, OSError, RuntimeError, AttributeError):
        return False


def gpu_available(prefer: Optional[str] = None) -> bool:
    """Whether any supported GPU backend is usable.

    Args:
        prefer: ``'cupy'`` or ``'torch'`` to ask about one backend specifically;
            ``None`` (default) to accept either.
    """
    if prefer == "cupy":
        return cupy_available()
    if prefer == "torch":
        return torch_cuda_available()
    return cupy_available() or torch_cuda_available()


def resolve_device(
    device: Optional[str],
    *,
    context: str,
    prefer: Optional[str] = None,
    stacklevel: int = 3,
) -> str:
    """Resolve a requested device to one that exists, warning on denial.

    Call this once, before any computation. Resolving inside a loop lets a single
    result mix two estimators.

    Args:
        device: What the caller asked for. ``'cuda'`` (or ``'gpu'``) requests the
            accelerator; ``'cpu'`` or ``None`` requests the CPU.
        context: Function name, used in the warning so the message names the caller
            rather than this module.
        prefer: Restrict the capability probe to one backend (``'cupy'`` / ``'torch'``).
        stacklevel: Passed to :func:`warnings.warn` so the warning points at user code.

    Returns:
        ``'cpu'`` or ``'cuda'`` -- the device that will actually be used.

    Raises:
        ValueError: On an unrecognised name. A typo used to fall through every
            ``if device == 'cuda'`` branch and run on CPU.
    """
    if device is None:
        return CPU

    normalized = str(device).strip().lower()
    if normalized in (CPU, "numpy"):
        return CPU
    if normalized not in (CUDA, "gpu"):
        raise ValueError(
            f"{context}: unrecognised device {device!r}; expected 'cpu' or 'cuda'. "
            f"An unrecognised name would otherwise run on CPU without saying so."
        )

    if gpu_available(prefer=prefer):
        return CUDA

    backend = {"cupy": "CuPy", "torch": "PyTorch"}.get(prefer, "CuPy or PyTorch")
    warnings.warn(
        f"{context}: device='cuda' was requested but no usable CUDA device was found "
        f"via {backend}; running on CPU. CPU and GPU paths may disagree numerically.",
        RuntimeWarning,
        stacklevel=stacklevel,
    )
    return CPU


def warn_device_fallback(context: str, exc: BaseException, *, stacklevel: int = 3) -> None:
    """Announce that a GPU computation failed and CPU results are being used instead.

    For failures surfacing during computation rather than at probe time, typically an
    out-of-memory part-way through. The caller must discard partial GPU work and
    recompute wholesale on the CPU, since a blended result belongs to neither device.
    """
    warnings.warn(
        f"{context}: GPU computation failed ({type(exc).__name__}: {exc}); "
        f"recomputing on CPU. Any partial GPU output has been discarded.",
        RuntimeWarning,
        stacklevel=stacklevel,
    )
