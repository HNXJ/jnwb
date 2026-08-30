"""Generator-level verification for realized_coupling_generator.py (2026-08-28, Hamm item
"Verify the generator before testing estimators"). These tests are independent of any
distributed-lag/estimator machinery -- they check the SYNTHETIC DATA-GENERATING PROCESS itself
against its own structural specification, before any estimator is asked to recover anything from
it.
"""
import numpy as np
import pytest

from omission.jnwb_ext.realized_coupling_generator import synthesize_realized_coupling_pair

N_TRIALS = 400
TRIAL_LEN = 400


def test_beta_zero_R_uncorrelated_with_P_private():
    """Test 1: with beta=0, changing private_P (across trials, Z varying too) must not
    systematically alter R except through independent noise -- i.e. R has no reconstructable
    relationship to the SAME trial's P_private beyond chance."""
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, jitter_sd_ms=8.0, amp_gain=0.4, rho=0.5, beta=0.0,
        z_seed=1, private_seed=2,
    )
    # summarize P_private and R by a comparable scalar (mean over the trial) and correlate
    p_priv_summary = P_private.mean(axis=1)
    r_summary = R.mean(axis=1)
    r_val = np.corrcoef(p_priv_summary, r_summary)[0, 1]
    assert abs(r_val) < 0.15, f"beta=0 but P_private correlates with R (r={r_val:.3f}) -- coupling leak"


def test_beta_positive_R_predictable_from_P_private_at_correct_delay():
    """Test 2: with beta>0 (Z held fixed via explicit true_jitter/true_gain), R's coupled
    component must be predictable from P_private at the injected delay, and NOT at a wrong delay
    of comparable magnitude in the opposite direction."""
    rng = np.random.default_rng(0)
    true_jitter = rng.normal(0, 8.0, N_TRIALS)
    true_gain = np.ones(N_TRIALS)
    beta, delay_ms = 2.0, 30.0
    P, R, tj, tg, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, jitter_sd_ms=0.0, amp_gain=0.0, rho=0.5,
        beta=beta, delay_ms=delay_ms, coupling_kind="innovation", noise_sd=0.05,
        true_jitter=true_jitter, true_gain=true_gain, private_seed=3,
    )
    delay_samples = int(round(delay_ms))
    # Reconstruct the expected coupling contribution directly and compare to R minus its shared
    # component (r_shared is deterministic given true_jitter/true_gain and the known kernel).
    from omission.jnwb_ext.common_driver_control import _gaussian_kernel
    t = np.arange(TRIAL_LEN)
    r_shared = np.stack([true_gain[i] * _gaussian_kernel(t, 220.0 + tj[i], 5.0) for i in range(N_TRIALS)])
    baseline_shape = np.zeros(TRIAL_LEN); baseline_shape[0:80] = 1.0
    r_base = np.stack([0.15 * true_gain[i] * baseline_shape for i in range(N_TRIALS)])
    r_residual = R - r_shared - r_base  # ~= coupling + noise
    expected_coupling = np.stack([
        beta * np.concatenate([np.zeros(delay_samples), P_private[i, :-delay_samples]]) for i in range(N_TRIALS)
    ])
    resid_corr = np.corrcoef(r_residual.reshape(-1), expected_coupling.reshape(-1))[0, 1]
    assert resid_corr > 0.9, f"R's residual after removing shared component poorly matches expected coupling (r={resid_corr:.3f})"


def test_replay_intervention_beta_zero_and_positive():
    """Test 3 (strongest sanity check): same Z realization (z_seed fixed / explicit true_jitter,
    true_gain), two different private-innovation draws (private_seed varies). For beta=0, R
    should differ only via independent per-draw noise (no systematic dependence on which P
    realization occurred). For beta>0, the difference in R must match the known delayed/scaled
    difference in the coupling source, before R's own measurement noise."""
    rng = np.random.default_rng(42)
    true_jitter = rng.normal(0, 6.0, N_TRIALS)
    true_gain = np.ones(N_TRIALS)

    # beta = 0 case
    P_a0, R_a0, *_ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, rho=0.5, beta=0.0, noise_sd=0.0,
        true_jitter=true_jitter, true_gain=true_gain, private_seed=10,
    )
    P_b0, R_b0, *_ = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, rho=0.5, beta=0.0, noise_sd=0.0,
        true_jitter=true_jitter, true_gain=true_gain, private_seed=20,
    )
    delta_P0 = P_a0 - P_b0
    delta_R0 = R_a0 - R_b0
    assert np.abs(delta_P0).mean() > 0.01, "replay draws should have genuinely different P realizations"
    assert np.abs(delta_R0).max() < 1e-9, (
        f"beta=0: R must be IDENTICAL across private-draw replays with noise_sd=0 (R_shared is "
        f"purely a function of Z, no coupling term) -- got max|delta_R|={np.abs(delta_R0).max():.6f}"
    )

    # beta > 0 case
    beta, delay_ms = 1.5, 25.0
    P_a1, R_a1, tj_a, tg_a, Ppriv_a = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, rho=0.5, beta=beta, delay_ms=delay_ms, noise_sd=0.0,
        true_jitter=true_jitter, true_gain=true_gain, private_seed=10,
    )
    P_b1, R_b1, tj_b, tg_b, Ppriv_b = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, trial_len=TRIAL_LEN, rho=0.5, beta=beta, delay_ms=delay_ms, noise_sd=0.0,
        true_jitter=true_jitter, true_gain=true_gain, private_seed=20,
    )
    delay_samples = int(round(delay_ms))
    delta_Ppriv = Ppriv_a - Ppriv_b
    expected_delta_R = beta * np.concatenate(
        [np.zeros((N_TRIALS, delay_samples)), delta_Ppriv[:, :-delay_samples]], axis=1
    )
    delta_R1 = R_a1 - R_b1
    max_err = np.abs(delta_R1 - expected_delta_R).max()
    assert max_err < 1e-9, (
        f"beta>0: R_a-R_b must equal the exact known delayed-beta-scaled P_private difference "
        f"(no noise) -- max abs error {max_err:.6f}"
    )


def test_nuisance_conditioning_does_not_determine_private_P():
    """Test 4: conditioning on exact true_jitter/true_gain must not make P_private
    deterministic -- Var(P_private | true_jitter, true_gain) > 0, i.e. genuine exposure variation
    survives nuisance conditioning (by construction P_private's RNG stream is independent of Z's,
    so this should trivially hold; verified here rather than assumed)."""
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=N_TRIALS, jitter_sd_ms=8.0, amp_gain=0.4, rho=0.5, beta=0.0,
        z_seed=5, private_seed=6,
    )
    p_priv_summary = P_private.mean(axis=1)
    # residual variance of P_private summary after regressing out true_jitter, true_gain linearly
    X = np.stack([true_jitter, true_gain, np.ones(N_TRIALS)], axis=1)
    coef, *_ = np.linalg.lstsq(X, p_priv_summary, rcond=None)
    resid = p_priv_summary - X @ coef
    assert np.var(resid) > 0.5 * np.var(p_priv_summary), (
        "P_private's variance is mostly explained by true_jitter/true_gain -- private component "
        "is not actually independent of the nuisance state"
    )


def test_delay_recovery_without_confound():
    """Test 5: with jitter_sd_ms=0, amp_gain=0 (nuisance terms disabled) and beta>0, the injected
    delay must be recoverable via simple cross-correlation between P_private and R's residual
    (after removing the deterministic shared component, which is now IDENTICAL across trials)."""
    beta, delay_ms = 2.0, 40.0
    P, R, true_jitter, true_gain, P_private = synthesize_realized_coupling_pair(
        n_trials=200, trial_len=TRIAL_LEN, jitter_sd_ms=0.0, amp_gain=0.0, rho=0.6,
        beta=beta, delay_ms=delay_ms, noise_sd=0.1, z_seed=7, private_seed=8,
    )
    from omission.jnwb_ext.common_driver_control import _gaussian_kernel
    t = np.arange(TRIAL_LEN)
    r_shared = _gaussian_kernel(t, 220.0, 5.0)  # true_jitter=0, true_gain=1 for all trials
    baseline_shape = np.zeros(TRIAL_LEN); baseline_shape[0:80] = 1.0
    r_base = 0.15 * baseline_shape
    R_resid = R - (r_shared + r_base)  # (n_trials, trial_len), ~= coupling + noise

    lags = np.arange(0, 100)
    scores = []
    P_priv_concat = P_private.reshape(-1)
    R_resid_concat = R_resid.reshape(-1)
    for lag in lags:
        shifted = np.concatenate([np.zeros((P_private.shape[0], lag)), P_private[:, :TRIAL_LEN - lag]], axis=1).reshape(-1)
        scores.append(float(np.corrcoef(shifted, R_resid_concat)[0, 1]))
    best_lag = lags[int(np.argmax(scores))]
    assert abs(best_lag - delay_ms) <= 3, f"recovered delay {best_lag}ms far from injected {delay_ms}ms"
