"""Adversarial null test (Hamm, 2026-08-27, pre-P4 requirement): shared event drive with
DIFFERENT response kernels/latencies, ZERO direct LFP->SPK coupling. Tests whether the
trial-shuffle null used in test_F (test_causal_validation.py) actually removes the apparent
directionality this confound creates, rather than assuming it does because it worked on one
easier synthetic example (test_F used matched kernels, only an offset center).

Design: P (LFP proxy) and R (spike proxy) are each independently driven by the SAME
deterministic per-trial event onset, but with DIFFERENT kernel SHAPES (P: broad/slow gaussian,
R: narrow/fast gaussian) and a large fixed separation between their centers. There is NO term in
either signal's generation that depends on the other -- any apparent "coupling" is purely a
kernel-shape/timing artifact of both being locked to the same external event.

Two conditions, both must be checked (Hamm: "if ordinary within-condition trial permutation
fails ... quantify that failure"):
  1. FIXED event timing (identical phase every trial, no jitter) -- the worst case for exposing
     whether trial-label permutation can destroy a perfectly phase-locked deterministic template.
  2. JITTERED event timing (per-trial onset jitter) -- more realistic; jitter is itself a
     within-trial-index confound the permutation null does NOT touch (permuting trial LABELS
     doesn't touch each trial's own onset jitter), so this checks whether jitter alone is enough
     for the null to behave correctly, independent of amplitude/kernel-shape effects.
"""
from __future__ import annotations

import numpy as np

from omission.jnwb_ext.lag_estimation import lagged_association
from omission.jnwb_ext.nulls import trial_permutation

FS = 1000.0
LAGS_MS = np.arange(-150, 151, 1.0)


def _gaussian_kernel(t, center, sigma):
    return np.exp(-0.5 * ((t - center) / sigma) ** 2)


def _make_shared_event_no_coupling(n_trials=60, trial_len=400, p_center=150.0, p_sigma=25.0,
                                    r_center=220.0, r_sigma=5.0, jitter_sd_ms=0.0, noise_sd=0.3, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(trial_len)
    P_trials = np.empty((n_trials, trial_len))
    R_trials = np.empty((n_trials, trial_len))
    for i in range(n_trials):
        onset_jitter = rng.normal(0, jitter_sd_ms) if jitter_sd_ms > 0 else 0.0
        # independent noise draws for P and R -- no shared per-trial latent variable beyond the
        # (possibly jittered) event onset time itself
        P_trials[i] = _gaussian_kernel(t, p_center + onset_jitter, p_sigma) + rng.normal(0, noise_sd, trial_len)
        R_trials[i] = _gaussian_kernel(t, r_center + onset_jitter, r_sigma) + rng.normal(0, noise_sd, trial_len)
    return P_trials, R_trials


def _trial_shuffle_null_pvalue(P_trials, R_trials, n_perm=200, seed=100):
    n_trials = P_trials.shape[0]
    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    C_obs = lagged_association(P_concat, R_concat, LAGS_MS, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))
    observed_peak_lag = LAGS_MS[np.nanargmax(np.abs(C_obs))]

    condition_group = np.zeros(n_trials, dtype=int)
    null_peaks = np.empty(n_perm)
    for k in range(n_perm):
        order = trial_permutation(np.arange(n_trials), condition_position_group=condition_group,
                                   rng=np.random.default_rng(seed + k))
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, LAGS_MS, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    return p, observed_peak, observed_peak_lag, null_peaks


def test_adversarial_no_jitter_fixed_template_null_behavior():
    """Worst case: identical event phase every trial, no jitter. Report what actually happens --
    do not assert a specific pass/fail direction a priori; this test's job is to make the
    behavior a receipted, reproducible fact."""
    P_trials, R_trials = _make_shared_event_no_coupling(jitter_sd_ms=0.0, seed=1)
    p, observed_peak, observed_lag, null_peaks = _trial_shuffle_null_pvalue(P_trials, R_trials, seed=1000)
    print(f"\n[no-jitter] p={p:.4f} observed_peak={observed_peak:.3f} at lag={observed_lag}ms; "
          f"null_peaks mean={null_peaks.mean():.3f} sd={null_peaks.std():.3f}")
    # Recorded outcome (2026-08-27 run): with NO jitter, the deterministic template is identical
    # at the same within-trial phase for every trial regardless of trial-label identity, so
    # permuting trial labels cannot destroy it -- null peaks are themselves large (dominated by
    # the same undestroyed deterministic component), so p is NOT small: the null correctly
    # avoids a false "significant" call, but only because it also fails to distinguish this
    # confound from real coupling in a way that would flag anything as anomalous. This is exactly
    # the "quantify the failure" outcome Hamm asked for -- see receipt for interpretation.


def test_adversarial_with_jitter_more_realistic():
    """More realistic: per-trial onset jitter (SD=8ms) breaks exact phase-locking, closer to a
    real omission paradigm's actual trial-to-trial event-timing variability."""
    P_trials, R_trials = _make_shared_event_no_coupling(jitter_sd_ms=8.0, seed=2)
    p, observed_peak, observed_lag, null_peaks = _trial_shuffle_null_pvalue(P_trials, R_trials, seed=2000)
    print(f"\n[jittered] p={p:.4f} observed_peak={observed_peak:.3f} at lag={observed_lag}ms; "
          f"null_peaks mean={null_peaks.mean():.3f} sd={null_peaks.std():.3f}")
