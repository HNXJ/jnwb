"""Firing-window helpers and the paired fire-probability test."""

from __future__ import annotations

from typing import Dict, Tuple
import numpy as np
from .._rng import RNGLike, resolve_rng
from ..permutation import _count_at_least_as_extreme
from ._tests import _tie_tolerance


def _spike_window_bounds(spike_times, onset_s, window_ms, func_name):
    """Validate a spike-window query; return ``(spike_times, t0, t1)`` with bounds in seconds.

    A reversed or zero-width window returned 0 Hz or "did not fire", indistinguishable from a
    measurement, and ``searchsorted`` silently miscounted unsorted spike times.
    """
    if not (np.isfinite(onset_s) and np.all(np.isfinite(window_ms))):
        raise ValueError(f"{func_name}: onset_s={onset_s} and window_ms={window_ms} must be finite")
    if window_ms[1] <= window_ms[0]:
        raise ValueError(f"{func_name}: window_ms={tuple(window_ms)} has non-positive width")
    spike_times = np.asarray(spike_times, dtype=float)
    if not np.all(np.isfinite(spike_times)):
        raise ValueError(f"{func_name}: spike_times must be finite")
    if spike_times.size > 1 and np.any(np.diff(spike_times) < 0):
        raise ValueError(f"{func_name}: spike_times must be sorted ascending")
    return spike_times, onset_s + window_ms[0] / 1000.0, onset_s + window_ms[1] / 1000.0


def fires_in_window(spike_times: np.ndarray, onset_s: float, window_ms) -> bool:
    """True iff >=1 spike falls in [onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000).

    Pure spike-array/searchsorted arithmetic on an arbitrary onset and window.
    ``spike_times`` must be sorted ascending.

    Raises:
        ValueError: If the window has non-positive width (this returned False), a bound or
            spike time is not finite, or ``spike_times`` is not sorted.
    """
    spike_times, t0, t1 = _spike_window_bounds(spike_times, onset_s, window_ms, "fires_in_window")
    n = int(np.searchsorted(spike_times, t1, side="left") - np.searchsorted(spike_times, t0, side="left"))
    return n > 0


def fire_indicator(spike_times: np.ndarray, onsets_s: np.ndarray, window_ms) -> np.ndarray:
    """Vectorized boolean fire indicator, one entry per onset, constant window."""
    return np.asarray(
        [fires_in_window(spike_times, float(o), window_ms) for o in onsets_s], dtype=bool
    )


def paired_fire_prob_test(
    fires_target: np.ndarray,
    fires_null: np.ndarray,
    n_shuffles: int,
    n_bootstrap: int,
    rng: RNGLike,
) -> Dict:
    """Paired binary test: P(fire | target window) vs P(fire | paired baseline window).

    Two plain boolean arrays, an explicit RNG, and shuffle/bootstrap counts in.

    Significance: shuffle-null on which member of each trial's pair counts as "target"
    (sign-flip of the paired difference), alternative="greater" (tests whether the target
    window's fire probability exceeds the paired baseline's). Risk-difference CI: paired
    bootstrap over trials (percentile method) -- distinct RNG draws from the shuffle-null so the
    hypothesis test and the interval don't share randomness. Odds ratio: McNemar-style
    discordant-pair estimator with Haldane-Anscombe continuity correction (avoids div-by-zero
    when one discordant count is 0).

    Args:
        fires_target: (n,) bool array, one entry per paired trial.
        fires_null: (n,) bool array, the paired baseline/control condition.
        n_shuffles: number of sign-flip draws for the shuffle-null p-value.
        n_bootstrap: number of paired-bootstrap draws for the risk-difference CI.
        rng: an int seed, a numpy.random.Generator, or None for fresh OS entropy.

    Returns:
        dict with p_fire_target, p_fire_baseline, risk_difference (+ CI),
        odds_ratio (+ CI), p_value_fire_shuffle, n_trials. All-NaN/p=1.0 when fewer than 2
        paired trials are available.
    """
    rng = resolve_rng(rng, func_name="paired_fire_prob_test")
    t = np.asarray(fires_target, dtype=bool)
    u = np.asarray(fires_null, dtype=bool)
    # `n = min(len(t), len(u))` silently paired trial i of one condition with trial i of
    # the other and dropped the remainder, so lengths 8 and 4 returned a confident
    # risk_difference of 0.5 over four pairings that do not correspond to the same trials.
    # `shuffle_pvalue_paired` already refuses exactly this, and its docstring names the harm.
    if len(t) != len(u):
        raise ValueError(
            f"paired_fire_prob_test: fires_target and fires_null must be paired (equal "
            f"length); got {len(t)} and {len(u)}. Trials were silently truncated to the "
            "shorter of the two, which pairs unrelated trials."
        )
    n = len(t)
    if n < 2:
        return {
            "p_fire_target": float(np.mean(t)) if len(t) else float("nan"),
            "p_fire_baseline": float(np.mean(u)) if len(u) else float("nan"),
            "risk_difference": float("nan"),
            "risk_difference_ci_lo": float("nan"),
            "risk_difference_ci_hi": float("nan"),
            "odds_ratio": float("nan"),
            "odds_ratio_ci_lo": float("nan"),
            "odds_ratio_ci_hi": float("nan"),
            "p_value_fire_shuffle": 1.0,
            "n_trials": int(n),
        }

    ta = t[:n].astype(float)
    ua = u[:n].astype(float)
    diff = ta - ua
    obs = float(np.mean(diff))
    p_target = float(np.mean(ta))
    p_null = float(np.mean(ua))

    flips = rng.choice(np.array([-1.0, 1.0]), size=(n_shuffles, n))
    null_dist = flips @ diff / n
    k = _count_at_least_as_extreme(null_dist, obs, "greater", atol=_tie_tolerance(diff))
    p_value = (1.0 + k) / (n_shuffles + 1.0)

    boot_idx = rng.integers(0, n, size=(n_bootstrap, n))
    boot_diffs = diff[boot_idx].mean(axis=1)
    ci_lo, ci_hi = np.percentile(boot_diffs, [2.5, 97.5])

    n10 = float(np.sum((ta == 1) & (ua == 0)))
    n01 = float(np.sum((ta == 0) & (ua == 1)))
    n10c, n01c = n10 + 0.5, n01 + 0.5
    odds_ratio = n10c / n01c
    se_log_or = float(np.sqrt(1.0 / n10c + 1.0 / n01c))
    log_or = float(np.log(odds_ratio))
    or_ci_lo = float(np.exp(log_or - 1.96 * se_log_or))
    or_ci_hi = float(np.exp(log_or + 1.96 * se_log_or))

    return {
        "p_fire_target": p_target,
        "p_fire_baseline": p_null,
        "risk_difference": obs,
        "risk_difference_ci_lo": float(ci_lo),
        "risk_difference_ci_hi": float(ci_hi),
        "odds_ratio": float(odds_ratio),
        "odds_ratio_ci_lo": or_ci_lo,
        "odds_ratio_ci_hi": or_ci_hi,
        "p_value_fire_shuffle": float(p_value),
        "n_trials": int(n),
    }


def rate_in_window(spike_times: np.ndarray, onset_s: float, window_ms: Tuple[float, float]) -> float:
    """Firing rate (Hz) in ``[onset_s + window_ms[0]/1000, onset_s + window_ms[1]/1000)``.

    Rate-valued sibling of ``fires_in_window`` (spike count divided by window width).
    ``spike_times`` must be sorted ascending.

    Raises:
        ValueError: If the window has non-positive width, ``onset_s``, the window or a spike
            time is not finite, or ``spike_times`` is not sorted. The first two returned 0.0 Hz,
            indistinguishable from a silent unit; unsorted spike times were miscounted.
    """
    spike_times, t0, t1 = _spike_window_bounds(spike_times, onset_s, window_ms, "rate_in_window")
    n = int(np.searchsorted(spike_times, t1, side="left") - np.searchsorted(spike_times, t0, side="left"))
    return n / ((window_ms[1] - window_ms[0]) / 1000.0)
