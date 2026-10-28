"""Unit-suffixed parameter names, and the aliases that keep older spellings working.

A time parameter whose name carries no unit puts a 1000x error one keystroke away. The
package already has the divergence: 23 parameters end in ``_ms`` and 7 in ``_s``, and
``examples/tutorials/03_spiking.py`` calls ``raster_psth(..., win_ms=(-100., 400.))`` at
line 38 and ``compute_response_metrics(..., baseline_window=(-0.2, 0.0))`` at line 61 in
the same body -- both take a float 2-tuple, and only one says what a float means.

The remedy is the one ``band_power(fs=, sampling_rate=)`` already implements: the canonical
name carries the unit, the old spelling keeps working as an alias, and passing both
disagreeing values is an error rather than a silent precedence rule.
"""

from __future__ import annotations

import warnings
from typing import Any

__all__ = ["resolve_unit_alias"]


_MISSING = object()


def resolve_unit_alias(
    canonical_value: Any,
    alias_value: Any,
    *,
    canonical_name: str,
    alias_name: str,
    func_name: str,
    default: Any = _MISSING,
) -> Any:
    """Return the single value the caller meant, or say why there isn't one.

    Both names refer to the same quantity in the same unit -- the alias is the older
    spelling, kept so existing call sites keep working, and it is the *name* that changed,
    never the unit. Passing both is only an error when they disagree, which mirrors
    ``_resolve_fs``: repeating yourself is harmless, contradicting yourself is not.

    Args:
        canonical_value: What arrived under the unit-bearing name, or ``None``.
        alias_value: What arrived under the old name, or ``None``.
        canonical_name: The unit-bearing parameter name, for the message.
        alias_name: The old parameter name, for the message.
        func_name: The calling function, so the message names the caller.
        default: Used when neither was supplied. Omit it to make the parameter required.

    Raises:
        ValueError: If both were supplied with different values, or if neither was
            supplied and no ``default`` was given.
    """
    if canonical_value is not None and alias_value is not None:
        if canonical_value != alias_value:
            raise ValueError(
                f"Conflicting values provided to {func_name}: "
                f"{canonical_name}={canonical_value!r}, {alias_name}={alias_value!r}. "
                f"They are the same quantity in the same unit; specify only one "
                f"(prefer {canonical_name}, which carries the unit)."
            )
        return canonical_value
    if canonical_value is not None:
        return canonical_value
    if alias_value is not None:
        return alias_value
    if default is not _MISSING:
        return default
    raise ValueError(
        f"{func_name} requires {canonical_name} (or its alias {alias_name})."
    )


class _Required:
    """Default of a window the caller must pass. Its repr is fixed, so the API page is stable."""

    def __repr__(self) -> str:
        return "_REQUIRED"


_REQUIRED = _Required()


def _window_from_positional(func_name: str, name: str, window: Any, positional: tuple) -> Any:
    """The window a call names: the keyword, or one positional value under a FutureWarning.

    ``positional`` is what ``*_positional`` collected after the leading arguments. Two values,
    or a value next to the keyword, raise TypeError; so does an omitted window.
    """
    if len(positional) > 1:
        raise TypeError(
            f"{func_name} takes one window; got {len(positional)} positional values after "
            "its leading arguments."
        )
    if positional:
        if window is not _REQUIRED:
            raise TypeError(f"{func_name} got {name} both positionally and by keyword.")
        warnings.warn(
            f"{func_name}: pass {name}= by keyword; positional use will stop working",
            FutureWarning, stacklevel=3,
        )
        window = positional[0]
    if window is _REQUIRED:
        raise TypeError(f"{func_name} requires {name}.")
    return window


#: The signal classes a ``signal_class`` argument may name. Spikes and LFP are never pooled.
SIGNAL_CLASSES = ("spikes", "lfp")


class _Omitted:
    """Default of a ``signal_class`` the caller has not passed. Its repr is fixed, so the API page is stable."""

    def __repr__(self) -> str:
        return "_OMITTED"


_OMITTED = _Omitted()


def _check_signal_class(func_name: str, signal_class: Any, n_inputs: int) -> None:
    """Refuse a ``signal_class`` that names an unknown class or a mix; warn when it is omitted.

    One class names every input. A pair ``(class_1, class_2)`` names each of two inputs. A pair
    of different classes is refused. Omitted, the call still runs and warns ``FutureWarning``:
    the argument becomes required.

    Raises:
        ValueError: On a value outside ``SIGNAL_CLASSES``, a pair given to a one-input operation,
            or a pair that mixes spikes and LFP.
    """
    allowed = " or ".join(repr(c) for c in SIGNAL_CLASSES)
    if signal_class is _OMITTED:
        warnings.warn(
            f"{func_name}: pass signal_class= by keyword ({allowed}); it will become required",
            FutureWarning, stacklevel=3,
        )
        return
    if isinstance(signal_class, str):
        pair = (signal_class,) * n_inputs
    elif isinstance(signal_class, tuple) and n_inputs == 2 and len(signal_class) == 2:
        pair = signal_class
    else:
        shape = "one class" if n_inputs == 1 else "one class or a pair (class_1, class_2)"
        raise ValueError(
            f"{func_name}: signal_class takes {shape}, each {allowed}; got {signal_class!r}."
        )
    if any(c not in SIGNAL_CLASSES for c in pair):
        raise ValueError(f"{func_name}: signal_class must be {allowed}; got {signal_class!r}.")
    if len(set(pair)) > 1:
        raise ValueError(
            f"{func_name}: spikes and LFP are never pooled; signal_class={signal_class!r} "
            "names both. Call once for each class."
        )
