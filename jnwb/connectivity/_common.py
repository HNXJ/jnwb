"""Shared by the directed estimators: the result type, the order check and the surrogate null."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import numpy as np
from .._dictlike import DictAccessMixin
from .._rng import recorded_rng
from ..permutation import _TIE_RTOL, _count_at_least_as_extreme


def _fixed_order(order: Any, func_name: str) -> int:
    """A caller-fixed autoregressive order as an int, or ``ValueError``.

    ``int()`` alone accepted ``0`` (a model with no history, returning zero causality),
    truncated ``2.5`` to ``2`` and read ``True`` as ``1``. An integral float such as ``3.0``
    is accepted as the integer it names.
    """
    if isinstance(order, (bool, np.bool_)) or isinstance(order, str):
        raise ValueError(f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}")
    try:
        as_float = float(order)
    except (TypeError, ValueError):
        raise ValueError(
            f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}") from None
    if not np.isfinite(as_float) or as_float != int(as_float) or as_float < 1:
        raise ValueError(f"{func_name}: order must be 'auto' or an integer >= 1; got {order!r}")
    return int(as_float)


# ===========================================================================
# Generalized directed connectivity — shared input contract
# ===========================================================================
#
# Every public estimator below accepts X and Y in the same forms:
#
#   1-D array            (n_times,)              -> one trial
#   2-D array            (n_trials, n_times)     -> trials x time (``time_axis=-1``)
#   list/tuple of 1-D    ragged allowed          -> truncated to the shortest, logged
#
# and returns a ``DirectedResult``. Nothing in this layer knows or cares whether
# the samples are LFP microvolts, spike counts, MUAe, or dB band power.


@dataclass
class DirectedResult(DictAccessMixin):
    """
    Uniform return type for every directed connectivity estimator.

    Attributes:
        method: ``'granger'`` | ``'psi'`` | ``'transfer_entropy'``
        x_to_y: directed influence X -> Y (units in ``unit``)
        y_to_x: directed influence Y -> X
        net: net directionality. For GC/TE this is ``x_to_y - y_to_x``;
            for PSI (antisymmetric by construction) it is the PSI value itself,
            positive when X leads Y.
        unit: physical/units label for the estimates
        p_x_to_y / p_y_to_x / p_net: p-values where the estimator defines them,
            else ``None``. ``None`` means *not computed*, never "not significant".
        per_band: ``{band_name: {...}}`` for frequency-resolved methods, else ``{}``
        n_trials / n_times / fs: shape and sampling receipts
        params: every parameter that affects the number, for provenance
        diagnostics: assumption checks; ``warnings`` non-empty => do not
            interpret the number as biological directionality
    """

    method: str
    x_to_y: float
    y_to_x: float
    net: float
    unit: str
    p_x_to_y: Optional[float] = None
    p_y_to_x: Optional[float] = None
    p_net: Optional[float] = None
    per_band: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    spectrum: Optional[Dict[str, np.ndarray]] = None
    n_trials: int = 0
    n_times: int = 0
    fs: Optional[float] = None
    params: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = {
            "method": self.method,
            "x_to_y": self.x_to_y,
            "y_to_x": self.y_to_x,
            "net": self.net,
            "unit": self.unit,
            "p_x_to_y": self.p_x_to_y,
            "p_y_to_x": self.p_y_to_x,
            "p_net": self.p_net,
            "per_band": self.per_band,
            "n_trials": self.n_trials,
            "n_times": self.n_times,
            "fs": self.fs,
            "params": self.params,
            "diagnostics": self.diagnostics,
        }
        if self.spectrum is not None:
            out["spectrum"] = self.spectrum
        return out

    @property
    def ok(self) -> bool:
        """True when no diagnostic warning fired."""
        return not self.diagnostics.get("warnings")

    def summary(self) -> str:
        lines = [
            f"{self.method}  ({self.n_trials} trials x {self.n_times} samples"
            + (f", fs={self.fs} Hz)" if self.fs else ")"),
            f"  X -> Y : {self.x_to_y:+.6g} {self.unit}"
            + (f"   p={self.p_x_to_y:.4g}" if self.p_x_to_y is not None else ""),
            f"  Y -> X : {self.y_to_x:+.6g} {self.unit}"
            + (f"   p={self.p_y_to_x:.4g}" if self.p_y_to_x is not None else ""),
            f"  net    : {self.net:+.6g} {self.unit}"
            + (f"   p={self.p_net:.4g}" if self.p_net is not None else ""),
        ]
        for band, vals in self.per_band.items():
            lines.append(
                f"  [{band}] {vals.get('value', float('nan')):+.6g}"
                + (
                    f"  z={vals['z']:+.3f}"
                    if vals.get("z") is not None and np.isfinite(vals.get("z", np.nan))
                    else ""
                )
            )
        for w in self.diagnostics.get("warnings", []):
            lines.append(f"  ! {w}")
        return "\n".join(lines)

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return (
            f"DirectedResult(method={self.method!r}, x_to_y={self.x_to_y:.6g}, "
            f"y_to_x={self.y_to_x:.6g}, net={self.net:.6g})"
        )


#: The surrogate generator and the seed that rebuilds it (``jnwb._rng.recorded_rng``).
#: INTENTIONAL BREAK (0.2.6.1): ``None`` meant seed 0 and was recorded as ``seed=None``,
#: a ``Generator`` raised ``TypeError`` and ``2.7`` ran as seed 2.
#: INTENTIONAL BREAK (0.2.7): a ``Generator`` was used in place and recorded
#: ``surrogate_seed_entropy=None``, so the result alone could not reproduce its p-values. It
#: now gives up one draw, a child seed that the surrogates run on and the result records.
_surrogate_rng = recorded_rng


#: Fewest trials for which the surrogates re-pair trials instead of shifting them.
#: INTENTIONAL BREAK (0.2.6.1): this was 3. With n trials there are only about n!/e
#: derangements -- 2 at three trials -- so the null holds a handful of distinct values. On
#: independent white noise (100 pairs, 39 surrogates), P(p <= 0.05) was 0.25-0.33 at three
#: trials across granger, granger_spectral, phase_slope_index and transfer_entropy, and
#: 0.14-0.21 at four; the circular shift gave 0.02-0.10 at three, four and six trials,
#: and its one value above 0.075 (phase_slope_index at four) was 0.052 over 400 pairs.
_MIN_TRIALS_FOR_TRIAL_PERMUTATION = 7


def _surrogate_scheme(n_trials: int) -> str:
    """The surrogate scheme :func:`_surrogate_source` uses for ``n_trials``."""
    if n_trials >= _MIN_TRIALS_FOR_TRIAL_PERMUTATION:
        return "trial_permutation"
    return "circular_shift"


def _surrogate_source(a: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """
    Destroy cross-signal timing while preserving each trial's own autocorrelation.

    Trial permutation when there are at least ``_MIN_TRIALS_FOR_TRIAL_PERMUTATION`` (7)
    trials (pairs the source with the wrong trial), otherwise a circular shift of each
    trial by at least 10% of the record and at most 90% of it.
    """
    n_trials, n_times = a.shape
    if _surrogate_scheme(n_trials) == "trial_permutation":
        perm = rng.permutation(n_trials)
        # guarantee a real derangement so no trial keeps its own partner
        for i in range(n_trials):
            if perm[i] == i:
                j = (i + 1) % n_trials
                perm[i], perm[j] = perm[j], perm[i]
        return a[perm]
    lo = max(1, n_times // 10)
    out = np.empty_like(a)
    for i in range(n_trials):
        out[i] = np.roll(a[i], int(rng.integers(lo, max(lo + 1, n_times - lo))))
    return out


def _surrogate_p(null: np.ndarray, observed: float, alternative: str,
                 scale: float = 0.0) -> float:
    """``(1 + k) / (B + 1)`` over the ``B`` draws of ``null``, ``k`` counting draws at least as
    extreme as ``observed`` with round-off ties included (see ``_count_at_least_as_extreme``).
    Identical trials make every trial permutation reproduce the observed statistic, summed
    in another trial order.

    ``scale`` is the magnitude of the terms ``observed`` was formed from, for a statistic
    that cancels: a net value ``a - b`` carries the round-off of ``a`` and ``b``, not of
    its own size, so its tie width is ``_TIE_RTOL * (|a| + |b|)``. A Granger value
    ``log(var_r / var_f)`` cancels inside the log, so its scale is 1 (``max(1, |a|) +
    max(1, |b|)`` for the net). A PSI sums one term
    ``Im(conj(C_f) C_{f+1})`` of size at most 1 per bin pair, so its scale is the pair count.
    """
    k = _count_at_least_as_extreme(null, observed, alternative, atol=_TIE_RTOL * scale)
    return float((1 + k) / (len(null) + 1))
