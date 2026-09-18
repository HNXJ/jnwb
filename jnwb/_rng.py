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

__all__ = [
    "DEFAULT_SEED",
    "Default",
    "REQUIRED",
    "RNGLike",
    "resolve_rng",
    "resolve_seed_alias",
    "sklearn_random_state",
]


class _Required:
    """Stands in for a parameter that has no default and must still be aliasable."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - display only
        return "<required>"


#: Marks a renamed parameter that was required before the rename. Both spellings need a
#: default so that either one may be omitted, so the requirement moves from the signature
#: into :func:`resolve_seed_alias`, which raises when neither was supplied.
REQUIRED = _Required()


#: The seed these functions used all along, moved out of the bodies and into the
#: signatures. Changing it changes published numbers, so it is a constant, not a knob.
DEFAULT_SEED = 42

RNGLike = Union[int, np.random.Generator, None]


class Default:
    """A parameter default that is still recognizable as "the caller said nothing".

    ``None`` cannot mark "not supplied" for a random-number argument, because ``None`` is
    a meaningful value: it means fresh OS entropy. ``granger(seed=None)`` and ``granger()``
    must not resolve to the same stream. A plain sentinel would fix that but would replace
    the visible default in the signature -- the exact defect 05-35 repaired -- so this one
    reports the value it stands for:

    >>> import inspect
    >>> inspect.signature(lambda rng=Default(0): None).parameters["rng"].default
    0
    >>> Default(0) == 0
    True

    ``isinstance(x, Default)`` is therefore the only way to ask whether the argument was
    passed, and it is what :func:`resolve_seed_alias` uses.
    """

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def __repr__(self) -> str:
        return repr(self.value)

    def __eq__(self, other: Any) -> bool:
        if other is self:
            return True
        if isinstance(other, Default):
            return self.value == other.value
        return bool(self.value == other)

    def __hash__(self) -> int:
        return hash(self.value) if self.value is not None else hash(None)


def resolve_seed_alias(
    canonical_value: Any,
    alias_value: Any,
    *,
    alias_name: str,
    func_name: str,
    canonical_name: str = "rng",
) -> Any:
    """Return the single random-number argument the caller meant.

    The package spelled one concept four ways -- ``rng``, ``seed``, ``random_state`` and
    ``random_seed`` -- so ``rng`` is now canonical everywhere and the old spelling stays as
    a keyword-only alias. Repeating yourself is harmless; contradicting yourself is not,
    which is the contract ``band_power(fs=, sampling_rate=)`` already implements.

    Both parameters default to a :class:`Default`, so "not supplied" is distinguishable
    from an explicit ``None``.

    Raises:
        ValueError: If both spellings were supplied with different values.
    """
    canonical_given = not isinstance(canonical_value, Default)
    alias_given = not isinstance(alias_value, Default)

    if canonical_given and alias_given:
        if canonical_value is not alias_value and canonical_value != alias_value:
            raise ValueError(
                f"Conflicting values provided to {func_name}: "
                f"{canonical_name}={canonical_value!r}, {alias_name}={alias_value!r}. "
                f"They are the same argument under two names; specify only one "
                f"(prefer {canonical_name})."
            )
        return canonical_value
    if canonical_given:
        resolved = canonical_value
    elif alias_given:
        resolved = alias_value
    else:
        resolved = canonical_value.value

    if isinstance(resolved, _Required):
        raise TypeError(
            f"{func_name} requires {canonical_name} (or its alias {alias_name})."
        )
    return resolved


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
