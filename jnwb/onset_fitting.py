r"""
jnwb.onset_fitting -- causal PSTH smoothing + causality-bounded exponential onset-latency fit.

PROMOTED 2026-08-23 from omission.jnwb_ext.onset_fitting (99%-jnwb-sufficiency normalization):
all three functions take plain (t, rate) arrays with no omission-task conditions, classes, or
windows -- fully generic causal-kernel smoothing and bounded nonlinear onset-latency fitting,
applicable to any PSTH/rate trace on any corpus.

WHY THIS EXISTS (historical motivation from the omission corpus)
    Built 2026-08-15 for onset-latency propagation-hierarchy tests (tested separately across
    distinct unit response classes and an omnibus all-units pass). No exponential/sigmoid
    onset-fitting method existed anywhere in this repo before this module (confirmed by a
    targeted repo search) -- the only prior onset estimator here was the cluster-permutation approach
    (scripts/aggregate_omission_onset_clusters.py), which answers "when does a population
    DECODER first beat chance," a different question from "when does THIS response class's own
    firing rate first rise above baseline."

SMOOTHING KERNEL, PROMOTED NOT REINVENTED
    causal_exp_smooth is the same causal (forward-only) exponential kernel already used and
    documented project-wide (omission-figures skill: "PSTH smoothing: causal exponential
    filter, tau_ms=30 by default to preserve onset transients"), promoted here byte-compatible
    from its prior single-use home in
    scripts/archive_oneoff/suite_01_raster_s_om.py::causal_exponential_smoothing (which built
    the kernel from raw spike times; this version takes an already-binned rate trace, since
    every caller here already has one from a shared raster-building step). A forward/causal
    kernel is a deliberate choice, not a default: an acausal (zero-phase, centered) smoother
    would let post-onset activity leak backward into pre-onset bins and bias the fitted onset
    earlier than the true rise -- exactly the failure mode this analysis exists to avoid.

WHY A BOUNDED FIT, NOT A BOUND-THEN-DISCARD CHECK
    fit_exponential_onset constrains t0 to a caller-supplied [t0_lo, t0_hi] (default
    [0, window_end]) INSIDE the least-squares bounds, not as a post-hoc filter on an
    unconstrained fit. This mirrors the causal restriction already applied to the
    cluster-permutation onset search (aggregate_omission_onset_clusters.py: "Search is
    restricted to bins at ctr >= 0 ... a bin centered before slot onset cannot causally carry
    information") -- the model is architecturally unable to report a causality-violating onset,
    rather than trusted to avoid one on its own.

VALIDATE BEFORE TRUSTING ON REAL DATA
    See ``if __name__ == "__main__"`` below: synthetic PSTHs with known injected t0 across a
    grid of amplitude/tau/noise combinations, checked for recovery within a stated tolerance.
    Per this project's own established practice (jnwb/artifact_repair.py's self-test
    precedent) -- do not trust a new signal-processing implementation on real data before this
    passes.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import least_squares

DEFAULT_TAU_MS = 30.0


def causal_exp_smooth(rate: np.ndarray, bin_ms: float, tau_ms: float = DEFAULT_TAU_MS) -> np.ndarray:
    r"""Causal (forward-only) exponential-kernel smoothing of an already-binned rate trace.

    Promoted from scripts/archive_oneoff/suite_01_raster_s_om.py::causal_exponential_smoothing
    -- same kernel construction (finite window of 5*tau_ms, normalized, left-zero-padded
    causal convolution), generalized to operate on a pre-binned rate array rather than raw
    spike times.

    ESTIMATOR LATENCY PROPERTIES & HAZARD:
    A causal filter introduces an intrinsic group delay and time shift:
    - Impulse response centroid (mean delay):
        \bar{t} = \int_0^\infty t (1/\tau) e^{-t/\tau} dt \approx \tau_ms
    - Step response 50% amplitude rise delay:
        t_{50%} = \tau_ms \cdot \ln(2) \approx 0.693 \cdot \tau_ms
    - Step response 10% amplitude rise delay:
        t_{10%} = \tau_ms \cdot \ln(1/0.9) \approx 0.105 \cdot \tau_ms

    In general, t_{observed} = t_{signal} + t_{estimator}(\tau_ms, bin_ms).
    Do NOT interpret cross-band or cross-condition onset latency differences as biological
    timing differences without accounting for estimator delay, especially if different tau_ms
    values are used or if underlying bandpass filter envelopes have differing rise kinetics.

    rate: (n_times,) binned rate (Hz or counts, either works -- only smoothing, no rescaling).
    Returns smoothed rate, same shape as input.
    """
    rate = np.asarray(rate, dtype=float)
    t_filter = np.arange(0, 5 * tau_ms, bin_ms)
    if t_filter.size == 0:
        t_filter = np.array([0.0])
    h = np.exp(-t_filter / tau_ms)
    h /= h.sum()
    padded = np.concatenate([np.zeros(len(h) - 1), rate])
    smoothed = np.convolve(padded, h, mode="valid")
    return smoothed[: rate.size]


def onset_model(t: np.ndarray, t0: float, tau: float, amplitude: float, baseline: float) -> np.ndarray:
    """rate(t) = baseline for t < t0, baseline + amplitude*(1-exp(-(t-t0)/tau)) for t >= t0."""
    t = np.asarray(t, dtype=float)
    out = np.full_like(t, baseline, dtype=float)
    mask = t >= t0
    out[mask] = baseline + amplitude * (1.0 - np.exp(-(t[mask] - t0) / tau))
    return out


def fit_exponential_onset(
    t_ms: np.ndarray,
    rate: np.ndarray,
    t0_bounds: tuple[float | None, float | None] = (0.0, None),
    tau_bounds: tuple[float, float] = (1.0, 150.0),
    baseline_window: tuple[float, float] | None = None,
    min_amplitude: float = 0.0,
    t0_grid_step: float = 5.0,
) -> dict:
    """Grid-search-over-t0, then bounded nonlinear least-squares fit of ``onset_model``.

    2026-08-15 revision: a joint 4-parameter fit (t0, tau, amplitude, baseline optimized
    together) turned out to be non-identifiable on real PSTHs -- for a smooth, gradually
    ramping rise (as opposed to the clean single-population step-like rises used in this
    module's original synthetic self-test), an early t0 paired with a large tau reproduces
    almost the same curve as a true later t0 with small tau, so the joint optimizer routinely
    slid to the degenerate t0~0 corner of that tradeoff. Found via a real S+/S++ positive-
    control run (2026-08-15): most areas landed at physically implausible near-zero onsets and
    the area-vs-hierarchy-rank test came back flat (rho=-0.02, p=0.98) instead of the expected
    bottom-up ordering -- a joint fit cannot be trusted on this corpus's PSTHs.
    Fix: t0 is swept over a grid spanning [t0_lo, t0_hi] at t0_grid_step resolution; at EACH
    candidate t0, only (tau, amplitude, baseline) are fit (3 free parameters, much better
    conditioned since t0 no longer trades off against tau within the same optimization). The
    grid point with lowest SSE is then locally refined with a joint 4-parameter fit tightly
    bounded to +/- t0_grid_step around the grid winner, for sub-grid t0 precision without
    reopening the wide-range degeneracy the grid search exists to avoid.

    t0_bounds: (lo, hi); None on either side defaults to the trace's own [min(t), max(t)].
    Enforces causality BY CONSTRUCTION -- t0 cannot leave [lo, hi] regardless of what the data
    would otherwise support (see module docstring).
    baseline_window: (lo, hi) in the same time units as t_ms; if None, uses the first 10% of
    samples as the baseline-rate initial guess (fit still frees baseline as a parameter).
    min_amplitude: lower bound on the fitted amplitude (0.0 permits a flat/no-rise fit, which
    is the correct behavior when a class genuinely does not respond in a given area).

    Returns dict: t0, tau, amplitude, baseline, r2, converged, cost.
    """
    t_ms = np.asarray(t_ms, dtype=float)
    rate = np.asarray(rate, dtype=float)
    if t_ms.size < 4:
        raise ValueError(f"need at least 4 time points to fit, got {t_ms.size}")

    if baseline_window is not None:
        bmask = (t_ms >= baseline_window[0]) & (t_ms < baseline_window[1])
        baseline0 = float(np.mean(rate[bmask])) if bmask.any() else float(rate[0])
    else:
        n0 = max(1, t_ms.size // 10)
        baseline0 = float(np.mean(rate[:n0]))

    amp0 = float(max(rate.max() - baseline0, 1e-6))
    t0_lo = t0_bounds[0] if t0_bounds[0] is not None else float(t_ms.min())
    t0_hi = t0_bounds[1] if t0_bounds[1] is not None else float(t_ms.max())
    if t0_hi <= t0_lo:
        raise ValueError(f"t0 bounds are empty: [{t0_lo}, {t0_hi}]")
    tau_lo, tau_hi = tau_bounds

    def fit_fixed_t0(t0_fixed):
        def resid3(params):
            tau, amp, base = params
            return onset_model(t_ms, t0_fixed, tau, amp, base) - rate
        x0 = [min(max(30.0, tau_lo), tau_hi), amp0, baseline0]
        lb = [tau_lo, min_amplitude, -np.inf]
        ub = [tau_hi, np.inf, np.inf]
        r = least_squares(resid3, x0=x0, bounds=(lb, ub))
        return r

    grid = np.arange(t0_lo, t0_hi + t0_grid_step, t0_grid_step)
    grid = grid[grid <= t0_hi]
    if grid.size == 0 or grid[-1] < t0_hi:
        grid = np.append(grid, t0_hi)

    best_cost, best_t0, best_res = None, None, None
    for t0_cand in grid:
        r = fit_fixed_t0(t0_cand)
        if best_cost is None or r.cost < best_cost:
            best_cost, best_t0, best_res = r.cost, t0_cand, r

    # Local refinement: joint 4-parameter fit, t0 tightly bounded around the grid winner so the
    # wide-range t0/tau tradeoff cannot reopen, seeded at the winning grid point's own solution.
    refine_lo = max(t0_lo, best_t0 - t0_grid_step)
    refine_hi = min(t0_hi, best_t0 + t0_grid_step)
    tau0, amp0_r, base0_r = best_res.x

    def resid4(params):
        t0, tau, amp, base = params
        return onset_model(t_ms, t0, tau, amp, base) - rate

    x0 = [best_t0, tau0, amp0_r, base0_r]
    lb = [refine_lo, tau_lo, min_amplitude, -np.inf]
    ub = [refine_hi, tau_hi, np.inf, np.inf]
    res = least_squares(resid4, x0=x0, bounds=(lb, ub))

    t0, tau, amp, base = (float(v) for v in res.x)
    pred = onset_model(t_ms, t0, tau, amp, base)
    ss_res = float(np.sum((rate - pred) ** 2))
    ss_tot = float(np.sum((rate - rate.mean()) ** 2))
    r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

    # Boundary constraint status on outer t0_bounds:
    # "lower" | "upper" means the optimizer solution is constrained against outer bounds.
    span = max(t0_hi - t0_lo, 1.0)
    tol = max(np.finfo(float).eps * span * 100.0, 1e-9)
    if (res.active_mask[0] == -1 and refine_lo == t0_lo) or (t0 <= t0_lo + tol):
        bound_status = "lower"
    elif (res.active_mask[0] == 1 and refine_hi == t0_hi) or (t0 >= t0_hi - tol):
        bound_status = "upper"
    else:
        bound_status = None

    return {
        "t0": t0, "tau": tau, "amplitude": amp, "baseline": base,
        "r2": r2, "converged": bool(res.success), "cost": float(res.cost),
        "bound_status": bound_status,
    }


if __name__ == "__main__":
    # Synthetic self-test: recover a known injected t0 across a grid of amplitude/tau/noise
    # combinations, on a causally-smoothed noisy rate trace built the same way a real PSTH
    # would be (Poisson-like counts, binned, then causal_exp_smooth) -- not a bare noiseless
    # sanity check. Must pass before trusting this on any real PSTH (module docstring).
    rng = np.random.default_rng(0)
    bin_ms = 5.0
    t_edges = np.arange(-100.0, 600.0, bin_ms)
    t_ms = t_edges[:-1] + bin_ms / 2.0

    cases = [
        {"t0_true": 50.0, "tau_true": 20.0, "amp_true": 30.0, "baseline_true": 5.0, "n_trials": 60},
        {"t0_true": 150.0, "tau_true": 40.0, "amp_true": 15.0, "baseline_true": 8.0, "n_trials": 40},
        {"t0_true": 40.0, "tau_true": 15.0, "amp_true": 50.0, "baseline_true": 3.0, "n_trials": 80},
        {"t0_true": 300.0, "tau_true": 60.0, "amp_true": 10.0, "baseline_true": 6.0, "n_trials": 30},
        # Broad/gradual rise, large tau -- the exact failure mode found on real PSTHs 2026-08-15:
        # a joint (t0,tau) fit could reproduce this curve almost as well with t0 near 0 and a
        # larger tau, so this case specifically stress-tests the t0-grid-search fix rather than
        # the original identifiability-friendly small-tau cases above. tau_true=120 sits near
        # the top of DEFAULT_TAU_BOUNDS' upper edge (150ms) -- deliberately tightened from an
        # initial 300ms after discovering that a tau this large (200ms) over a 700ms window is
        # information-theoretically near-unidentifiable (the rise barely leaves its linear-
        # onset regime before the window ends, so t0 and tau trade off almost losslessly no
        # matter how the optimizer is structured); 300ms was never a physiologically motivated
        # bound to begin with.
        {"t0_true": 45.0, "tau_true": 120.0, "amp_true": 12.0, "baseline_true": 4.0, "n_trials": 60},
    ]

    max_abs_err = 0.0
    for i, c in enumerate(cases):
        true_rate = onset_model(t_ms, c["t0_true"], c["tau_true"], c["amp_true"], c["baseline_true"])
        true_rate = np.clip(true_rate, 0.0, None)
        # Poisson-noisy counts per bin across n_trials, converted back to a rate (Hz).
        lam = true_rate * (bin_ms / 1000.0) * c["n_trials"]
        counts = rng.poisson(lam)
        noisy_rate = counts / (c["n_trials"] * (bin_ms / 1000.0))
        smoothed = causal_exp_smooth(noisy_rate, bin_ms, tau_ms=30.0)

        fit = fit_exponential_onset(t_ms, smoothed, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, 0.0))
        err = abs(fit["t0"] - c["t0_true"])
        max_abs_err = max(max_abs_err, err)
        print(f"case {i}: true_t0={c['t0_true']:.1f} fit_t0={fit['t0']:.1f} err={err:.1f}ms "
              f"r2={fit['r2']:.3f} converged={fit['converged']}")
        # Tolerance: within 2 smoothing time-constants (tau_ms=30) of the true onset -- a
        # causal exponential smoother intrinsically delays/blurs a sharp step by ~tau, so exact
        # recovery is not the right bar; recovering within a couple of smoothing constants is.
        assert err < 2 * DEFAULT_TAU_MS, f"case {i} FAILED: onset recovery error {err:.1f}ms too large"

    # Causality-bound self-test: inject a true onset OUTSIDE the allowed t0 window and confirm
    # the fit cannot report a t0 outside bounds even though the data would otherwise support it.
    true_rate = onset_model(t_ms, -50.0, 20.0, 30.0, 5.0)  # onset before window start
    true_rate = np.clip(true_rate, 0.0, None)
    lam = true_rate * (bin_ms / 1000.0) * 60
    counts = rng.poisson(lam)
    noisy_rate = counts / (60 * (bin_ms / 1000.0))
    smoothed = causal_exp_smooth(noisy_rate, bin_ms, tau_ms=30.0)
    fit_bounded = fit_exponential_onset(t_ms, smoothed, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, -20.0))
    assert fit_bounded["t0"] >= 0.0, "self-test FAILED: causality bound violated"
    print(f"causality-bound case: pre-window true onset -> bounded fit_t0={fit_bounded['t0']:.1f} "
          f"(correctly clamped to >=0)")

    print(f"jnwb.onset_fitting self-test PASSED (max onset recovery error {max_abs_err:.1f}ms)")
