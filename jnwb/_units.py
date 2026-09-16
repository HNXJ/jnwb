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
