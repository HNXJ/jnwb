"""Decides where a computation runs -- CPU, CUDA or Metal -- and says so.

Private module.

Nineteen call sites across nine modules route through here. Each used to carry its own
probe and fallback policy, which caused two problems:

* **The sites asked different questions.** Some treated a bare ``import cupy`` as proof
  of a usable GPU; others asked ``torch.cuda.is_available()``. CuPy imports fine with
  the package installed and no working driver, so the sites disagreed about whether the
  same machine had a GPU.
* **Falling back was silent.** A caller who asked for ``device='cuda'`` and got CPU
  arithmetic had no way to find out. An intermittent GPU failure inside a loop swapped
  the estimator mid-null, and the returned dict said nothing.

A requested accelerator that cannot be delivered warrants a warning, every time. CPU
callers are silent, since nothing was denied them. There are exactly three ways to be
denied, and each has one function here, so a caller sees the same contract everywhere:

* **No usable device.** :func:`resolve_device` probes and warns.
* **A device that failed mid-computation.** :func:`warn_device_fallback`, after the
  partial GPU work has been discarded.
* **A device that exists but this code path cannot use.** :func:`warn_no_gpu_path`, or
  :func:`resolve_device` itself when the function does not list the device in
  ``supports``. Either the function has no implementation for that device at all, or the
  particular arguments select a branch that has none. This was the silent case: the
  caller with no GPU was warned and the caller with one was not, which inverts the
  contract.

Resolve once per public entry point, before any loop, and pass the resolved device to
internal helpers. A helper that re-resolves inside a loop warns once per iteration and
names itself rather than the function the caller invoked.

The CPU and CUDA paths use different libraries (cuFFT against pocketfft, cuSOLVER against
LAPACK) and different reduction orders, so they agree to rounding rather than bit for bit.
``tests/test_execution_switch.py`` states the tolerance and measures every CUDA path
against it. A result that records its device names the one that produced every value in
it.

**Metal.** ``device='metal'`` requests Apple's GPU through JAX (the ``jax-metal`` plugin).
It is implemented and has not been run on Metal hardware: no machine that develops this
package has one. Metal has no 64-bit floating point, so a function runs there only when
the caller has already asked for 32-bit output; running a 64-bit request in 32 bits would
change the number, so that request is announced and computed on the CPU instead. A
function declares Metal support by listing it in ``supports``; every other function warns
and computes on the CPU through the same call that handles CUDA.
"""

from __future__ import annotations

import warnings
from typing import Optional, Sequence

import numpy as np

__all__ = [
    "CPU",
    "CUDA",
    "METAL",
    "cupy_available",
    "torch_cuda_available",
    "gpu_available",
    "jax_metal_device",
    "jax_metal_available",
    "resolve_device",
    "warn_device_fallback",
    "warn_no_gpu_path",
]

CPU = "cpu"
CUDA = "cuda"
METAL = "metal"

#: The devices a function supports when it does not say otherwise.
DEFAULT_SUPPORTS = (CPU, CUDA)


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
    """Whether any supported CUDA backend is usable.

    Args:
        prefer: ``'cupy'`` or ``'torch'`` to ask about one backend specifically;
            ``None`` (default) to accept either.
    """
    if prefer == "cupy":
        return cupy_available()
    if prefer == "torch":
        return torch_cuda_available()
    return cupy_available() or torch_cuda_available()


def jax_metal_device():
    """The first JAX device on the ``METAL`` platform.

    Raises:
        RuntimeError: JAX has no Metal platform (``jax-metal`` is absent, or this is not
            an Apple GPU).
        ImportError: JAX is not installed.
    """
    import jax

    return jax.devices("METAL")[0]


def jax_metal_available() -> bool:
    """True if JAX imports and exposes a Metal device.

    Unverified on Metal hardware; see the module docstring.
    """
    try:
        jax_metal_device()
        return True
    except (ImportError, OSError, RuntimeError, AttributeError):
        return False


def _is_64_bit(dtype) -> bool:
    """Whether ``dtype`` carries 64-bit real components (float64 or complex128)."""
    dt = np.dtype(dtype)
    per_component = dt.itemsize // 2 if dt.kind == "c" else dt.itemsize
    return per_component > 4


def resolve_device(
    device: Optional[str],
    *,
    context: str,
    prefer: Optional[str] = None,
    stacklevel: int = 3,
    supports: Sequence[str] = DEFAULT_SUPPORTS,
    working_dtype=None,
) -> str:
    """Resolve a requested device to one that exists, warning on denial.

    Call this once, before any computation. Resolving inside a loop lets a single
    result mix two estimators.

    Args:
        device: What the caller asked for. ``'cuda'`` (or ``'gpu'``) requests CUDA,
            ``'metal'`` requests Apple's GPU through JAX, ``'cpu'`` or ``None`` requests
            the CPU.
        context: Function name, used in the warning so the message names the caller
            rather than this module.
        prefer: Restrict the CUDA probe to one backend (``'cupy'`` / ``'torch'``).
        stacklevel: Passed to :func:`warnings.warn` so the warning points at user code.
        supports: The devices this function has an implementation for. A recognised
            device outside it is announced and resolved to the CPU. The default,
            ``('cpu', 'cuda')``, is every function without a Metal path.
        working_dtype: The precision the caller asked for, when the function takes one.
            Metal is refused for a 64-bit request, since computing it in 32 bits would
            change the number.

    Returns:
        ``'cpu'``, ``'cuda'`` or ``'metal'`` -- the device that will actually be used.

    Raises:
        ValueError: On an unrecognised name. A typo used to fall through every
            ``if device == 'cuda'`` branch and run on CPU.
    """
    if device is None:
        return CPU

    normalized = str(device).strip().lower()
    if normalized in (CPU, "numpy"):
        return CPU
    if normalized == "gpu":
        normalized = CUDA
    if normalized not in (CUDA, METAL):
        raise ValueError(
            f"{context}: unrecognised device {device!r}; expected 'cpu', 'cuda' or "
            f"'metal'. An unrecognised name would otherwise run on CPU without saying so."
        )

    if normalized not in supports:
        warnings.warn(
            f"{context}: device={normalized!r} was requested, but {context} has no "
            f"{'Metal' if normalized == METAL else 'CUDA'} implementation; computing on CPU.",
            RuntimeWarning,
            stacklevel=stacklevel,
        )
        return CPU

    if normalized == METAL:
        if not jax_metal_available():
            warnings.warn(
                f"{context}: device='metal' was requested but no Metal device was found "
                f"via JAX; running on CPU.",
                RuntimeWarning,
                stacklevel=stacklevel,
            )
            return CPU
        if working_dtype is not None and _is_64_bit(working_dtype):
            warnings.warn(
                f"{context}: device='metal' was requested with a 64-bit dtype "
                f"({np.dtype(working_dtype)}), and Metal has no 64-bit floating point; "
                f"computing on CPU. Request the 32-bit dtype to run on Metal.",
                RuntimeWarning,
                stacklevel=stacklevel,
            )
            return CPU
        return METAL

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


def warn_no_gpu_path(context: str, reason: str, *, stacklevel: int = 3) -> None:
    """Announce that a usable GPU exists but this code path will not use it.

    The third denial reason, and the one that used to be silent. :func:`resolve_device`
    covers "no device was found" and :func:`warn_device_fallback` covers "the device
    failed part-way through"; neither fires when the device is fine and the function
    simply has no GPU branch for these arguments. A caller on a CPU-only machine was
    warned and a caller on an A4000 was not, so the better the hardware the quieter the
    denial.

    Args:
        context: The function the caller actually invoked, not the private helper that
            noticed. A warning naming an internal callee sends the reader to code they
            did not call.
        reason: Why this path has no GPU, phrased to complete "but ...". Say what would
            have to change, so the caller can decide whether to change it.
        stacklevel: Passed to :func:`warnings.warn` so the warning points at user code.
    """
    warnings.warn(
        f"{context}: device='cuda' was requested, but {reason}; computing on CPU.",
        RuntimeWarning,
        stacklevel=stacklevel,
    )


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
