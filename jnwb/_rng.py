"""One way to ask for randomness, and no seed hidden in a function body.

Two defects motivate this module.

05-35: five functions declared ``rng: Optional[np.random.Generator] = None`` and then ran
``np.random.default_rng(42)`` -- or ``default_rng(0)`` -- when the caller left it out.
``None`` reads as "fresh randomness" and behaved as a fixed seed, so two calls a caller
believed were independent shared a null distribution and agreed exactly. The seed is now
in the signature, where ``inspect.signature`` and ``help()`` show it, and ``None`` means
what it means everywhere else in NumPy: draw fresh entropy from the OS.

05-34: ``nested_cv_linear_svm`` had no randomness parameter at all and hardcoded
``random_state=42`` at four sites, so nobody could ask whether a decoding accuracy
survived a different partition of the same trials.

Both resolvers accept the same three things -- an ``int`` seed, a ``Generator``, or
``None`` -- so one spelling covers the package's split between ``rng: Generator`` and
``seed: int``.
"""

from __future__ import annotations

from typing import Any, Optional, Union

import numpy as np

__all__ = ["DEFAULT_SEED", "RNGLike", "resolve_rng", "sklearn_random_state"]


#: The seed these functions used all along, moved out of the bodies and into the
#: signatures. Changing it changes published numbers, so it is a constant, not a knob.
DEFAULT_SEED = 42

RNGLike = Union[int, np.random.Generator, None]


def resolve_rng(rng: RNGLike, *, func_name: str) -> np.random.Generator:
    """Return a ``Generator`` for ``rng``.

    Args:
        rng: An ``int`` seed, an existing ``numpy.random.Generator`` (returned as-is, so
            successive calls advance one stream rather than restarting it), or ``None``
            for fresh OS entropy.
        func_name: The calling function, so a wrong type names the caller.

    Raises:
        TypeError: For anything else. A ``float`` seed is refused rather than truncated,
            because ``2.7`` and ``2`` would otherwise silently name the same stream.
    """
    if rng is None or isinstance(rng, np.random.Generator):
        return np.random.default_rng(rng)
    if isinstance(rng, (int, np.integer)) and not isinstance(rng, bool):
        return np.random.default_rng(int(rng))
    raise TypeError(
        f"{func_name}: rng must be an int seed, a numpy.random.Generator, or None "
        f"for fresh entropy; got {type(rng).__name__}."
    )


def sklearn_random_state(rng: RNGLike, *, func_name: str) -> Optional[int]:
    """Return what scikit-learn's ``random_state=`` accepts, for ``rng``.

    scikit-learn estimators take an ``int``, a legacy ``RandomState`` or ``None``; they do
    not take a ``Generator``. An ``int`` is passed through **unchanged** rather than being
    used to seed a ``Generator`` and redrawn, so ``rng=DEFAULT_SEED`` reproduces the
    partitions the hardcoded ``random_state=42`` produced, to the fold.
    """
    if rng is None:
        return None
    if isinstance(rng, (int, np.integer)) and not isinstance(rng, bool):
        return int(rng)
    if isinstance(rng, np.random.Generator):
        return int(rng.integers(0, 2**32 - 1))
    raise TypeError(
        f"{func_name}: rng must be an int seed, a numpy.random.Generator, or None "
        f"for fresh entropy; got {type(rng).__name__}."
    )
