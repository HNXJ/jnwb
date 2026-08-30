"""Leakage test for the observable-Zhat bridge benchmark's nuisance estimators (2026-08-28).

Two independent checks, both required by Hamm:

1. Substituting garbage/random data for R_trials (the outcome) BEFORE computing timing_hat
   (via estimate_timing_nested) and amplitude (via dataset["amplitude"] /
   estimate_amplitude_covariate) must not change either estimate numerically at all, since
   neither is supposed to look at R -- both are P-only, cross-fit statistics.
2. estimate_timing_nested's per-trial estimate, for a given seed/n_splits, is built ONLY from
   that fold's training trials: reproduce one trial's estimate manually by finding its fold via
   the same KFold(n_splits, shuffle=True, random_state=seed) split, averaging P_trials over that
   fold's training indices to get the template, and calling the same matched-filter shift
   function -- the manual reproduction must be bit-identical to estimate_timing_nested's output
   for that trial.
"""
import numpy as np
from sklearn.model_selection import KFold

from omission.jnwb_ext.common_driver_control import _matched_filter_lag, estimate_amplitude_covariate
from omission.jnwb_ext.distributed_lag_model import build_trial_level_dataset, estimate_timing_nested
from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair

N_TRIALS = 120
SEED = 7
N_SPLITS = 5


def _generate():
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, rho=0.5, delay_ms=30.0, coupling_kind="realized",
        jitter_sd_ms=8.0, amp_gain=0.6, beta=1.5, z_seed=SEED, private_seed=SEED + 700000,
    )
    return P, R


def test_timing_hat_identical_under_garbage_R():
    """estimate_timing_nested takes P_trials only -- confirm two calls (one conceptually 'paired'
    with real R, one with garbage R never even passed in) give bit-identical output, and that
    build_trial_level_dataset's own 'timing' field (also P-only, cross-fit inside the function)
    is likewise unaffected by swapping R for garbage before the call."""
    P, R_real = _generate()
    rng = np.random.default_rng(999)
    R_garbage = rng.normal(0, 1000.0, size=R_real.shape)  # wildly different scale/content

    timing_hat_a = estimate_timing_nested(P, n_splits=N_SPLITS, seed=SEED)
    timing_hat_b = estimate_timing_nested(P, n_splits=N_SPLITS, seed=SEED)
    np.testing.assert_array_equal(timing_hat_a, timing_hat_b)

    dataset_real = build_trial_level_dataset(P, R_real, seed=SEED)
    dataset_garbage = build_trial_level_dataset(P, R_garbage, seed=SEED)

    # P-derived fields must be bit-identical regardless of what R was.
    np.testing.assert_array_equal(dataset_real["amplitude"], dataset_garbage["amplitude"])
    np.testing.assert_array_equal(dataset_real["timing"], dataset_garbage["timing"])
    np.testing.assert_array_equal(dataset_real["lag_features"], dataset_garbage["lag_features"])

    # sanity: R-derived fields DO differ (proves the garbage substitution was actually live, not
    # a no-op that would make the "identical amplitude/timing" result vacuous).
    assert not np.allclose(dataset_real["outcome"], dataset_garbage["outcome"])
    assert not np.allclose(dataset_real["own_history"], dataset_garbage["own_history"])


def test_amplitude_covariate_identical_under_garbage_R():
    """estimate_amplitude_covariate takes P_trials only -- direct signature-level confirmation
    that it cannot see R at all (garbage R is never even passed to the function)."""
    P, R_real = _generate()
    amp_a = estimate_amplitude_covariate(P, baseline_window=(0, 80))
    amp_b = estimate_amplitude_covariate(P, baseline_window=(0, 80))
    np.testing.assert_array_equal(amp_a, amp_b)


def test_timing_hat_per_trial_manual_fold_reproduction():
    """Reproduce estimate_timing_nested's per-trial estimate manually: find the trial's fold via
    the SAME KFold(n_splits, shuffle=True, random_state=seed) split used internally, build the
    template from only that fold's training trials, and confirm the manual matched-filter shift
    matches the function's output exactly, for several spot-checked trials."""
    P, _ = _generate()
    timing_hat = estimate_timing_nested(P, n_splits=N_SPLITS, seed=SEED, max_shift=60)

    kf = KFold(n_splits=N_SPLITS, shuffle=True, random_state=SEED)
    splits = list(kf.split(P))

    spot_check_trials = [0, 5, 17, 42, 88, 119]
    checked = 0
    for trial_idx in spot_check_trials:
        for train_idx, test_idx in splits:
            if trial_idx in test_idx:
                template = P[train_idx].mean(axis=0)
                manual_shift = _matched_filter_lag(P[trial_idx], template, max_shift=60)
                assert manual_shift == timing_hat[trial_idx], (
                    f"trial {trial_idx}: manual={manual_shift} vs "
                    f"estimate_timing_nested={timing_hat[trial_idx]}"
                )
                # the training template must NOT have included the test trial itself.
                assert trial_idx not in train_idx
                checked += 1
                break
    assert checked == len(spot_check_trials)
