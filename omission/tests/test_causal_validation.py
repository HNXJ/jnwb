"""P0 synthetic validation harness for the causal SPK-LFP coupling pipeline (2026-08-27, Hamm).

"Every subsequent directional result depends on it" -- these tests must pass BEFORE any real-data
causal/lag result from this pipeline is trusted. Covers, per Hamm's explicit spec:

  A. LFP leads SPK by a known positive delay -> estimator recovers lag > 0.
  B. SPK leads LFP (reverse system) -> estimator recovers lag < 0.
  C. Zero-lag common drive -> no manufactured delayed directional peak.
  D. Independent autocorrelated signals -> false-positive rate matches the chosen null's alpha.
  E. Explicit future-leakage test for every causal transform (causal_bandpass, causal_envelope).
  F. Event-locking confound -> trial-shuffle null correctly flags a purely event-locked
     "coupling" as not distinguishable from its own null.
  G. CV-leakage synthetic control -> naive/ungrouped CV reproduces apparent decoding from a
     trivial cycle-identity confound; grouped/cycle-safe CV returns to chance.

Uses ``omission.jnwb_ext.lag_estimation.lagged_association`` (P0-scoped prototype estimator,
not the full P4 Analysis-A pipeline -- see that module's docstring), ``omission.jnwb_ext.
causal_signal`` (P2), and ``omission.jnwb_ext.nulls`` (P1).
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from omission.jnwb_ext.causal_signal import causal_bandpass, causal_envelope, filter_spec
from omission.jnwb_ext.lag_estimation import lagged_association
from omission.jnwb_ext.nulls import circular_shift, spike_jitter, trial_permutation

FS = 1000.0  # Hz -- 1 ms sampling, matches the project's canonical TFR/decoding grid
LAGS_MS = np.arange(-25, 26, 1.0)


def _ar1_noise(n, rho=0.9, sd=1.0, rng=None):
    rng = rng or np.random.default_rng(0)
    x = np.empty(n)
    x[0] = rng.normal(0, sd)
    for i in range(1, n):
        x[i] = rho * x[i - 1] + rng.normal(0, sd * np.sqrt(1 - rho ** 2))
    return x


# ---------------------------------------------------------------------------------------------
# A/B: known-delay directional recovery
# ---------------------------------------------------------------------------------------------

def _make_directional_pair(delta_ms: float, n=6000, seed=0):
    """P(t) is smooth AR(1) 'band power'; R(t) = P(t - delta_ms) + noise (P genuinely leads R
    by delta_ms). Returns (P, R)."""
    rng = np.random.default_rng(seed)
    P = _ar1_noise(n, rho=0.98, sd=1.0, rng=rng) ** 2  # power-like, non-negative, smooth
    delta_samples = int(round(delta_ms * FS / 1000.0))
    R = np.empty(n)
    R[:delta_samples] = rng.normal(0, 0.1, size=delta_samples)
    R[delta_samples:] = P[: n - delta_samples] + rng.normal(0, 0.5, size=n - delta_samples)
    return P, R


@pytest.mark.parametrize("delta_ms", [5.0, 12.0])
def test_A_lfp_leads_spk_recovers_positive_lag(delta_ms):
    P, R = _make_directional_pair(delta_ms, seed=1)
    C = lagged_association(P, R, LAGS_MS, fs=FS)
    peak_lag = LAGS_MS[np.nanargmax(C)]
    assert peak_lag > 0, f"expected positive (LFP-leads) peak lag, got {peak_lag}"
    assert abs(peak_lag - delta_ms) <= 2.0, f"expected peak near {delta_ms}ms, got {peak_lag}ms"


@pytest.mark.parametrize("delta_ms", [5.0, 12.0])
def test_B_spk_leads_lfp_recovers_negative_lag(delta_ms):
    # reverse system: R(t) genuinely leads P(t) by delta_ms, i.e. P(t) = R(t - delta_ms) + noise
    R, P = _make_directional_pair(delta_ms, seed=2)  # reuse generator, swap roles
    C = lagged_association(P, R, LAGS_MS, fs=FS)
    peak_lag = LAGS_MS[np.nanargmax(C)]
    assert peak_lag < 0, f"expected negative (SPK-leads) peak lag, got {peak_lag}"
    assert abs(peak_lag - (-delta_ms)) <= 2.0, f"expected peak near {-delta_ms}ms, got {peak_lag}ms"


# ---------------------------------------------------------------------------------------------
# C: zero-lag common drive must not manufacture a delayed peak
# ---------------------------------------------------------------------------------------------

def test_C_zero_lag_common_drive_no_manufactured_delay():
    rng = np.random.default_rng(3)
    n = 6000
    common = _ar1_noise(n, rho=0.97, sd=1.0, rng=rng)
    P = common ** 2 + rng.normal(0, 0.3, size=n)
    R = common ** 2 + rng.normal(0, 0.3, size=n)  # same-instant common cause, no offset
    C = lagged_association(P, R, LAGS_MS, fs=FS)
    peak_lag = LAGS_MS[np.nanargmax(np.abs(C))]
    assert abs(peak_lag) <= 2.0, f"zero-lag common drive should peak near tau=0, got {peak_lag}ms"


# ---------------------------------------------------------------------------------------------
# D: independent autocorrelated signals -> calibrated false-positive rate
# ---------------------------------------------------------------------------------------------

def test_D_independent_signals_false_positive_rate_calibrated():
    n_trials_sim, alpha, n_perm = 100, 0.05, 200
    rng = np.random.default_rng(4)
    n_sig = 0
    for trial in range(n_trials_sim):
        n = 1500
        P = _ar1_noise(n, rho=0.95, rng=np.random.default_rng(1000 + trial)) ** 2
        R = _ar1_noise(n, rho=0.95, rng=np.random.default_rng(2000 + trial))  # independent draw
        C = lagged_association(P, R, LAGS_MS, fs=FS)
        observed_peak = np.nanmax(np.abs(C))

        null_peaks = np.empty(n_perm)
        for k in range(n_perm):
            shifted, _ = circular_shift(P, fs=FS, exclusion_zone_ms=30.0, rng=np.random.default_rng(5000 + trial * n_perm + k))
            Cn = lagged_association(shifted, R, LAGS_MS, fs=FS)
            null_peaks[k] = np.nanmax(np.abs(Cn))
        p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
        if p < alpha:
            n_sig += 1

    rate = n_sig / n_trials_sim
    # binomial 99% CI around alpha=0.05 for n=100 draws is roughly [0.0, 0.13]; a well-calibrated
    # null should not blow far past this under independent AR(1) inputs
    assert rate <= 0.15, f"false-positive rate {rate:.3f} exceeds calibration tolerance for alpha={alpha}"


# ---------------------------------------------------------------------------------------------
# E: explicit future-leakage test for every causal transform
# ---------------------------------------------------------------------------------------------

def test_E_causal_bandpass_no_future_leakage():
    rng = np.random.default_rng(5)
    n = 2000
    x = _ar1_noise(n, rho=0.9, rng=rng)
    t = 1200
    x_perturbed = x.copy()
    x_perturbed[t + 1:] += rng.normal(0, 10.0, size=n - t - 1)  # large perturbation strictly after t

    y1 = causal_bandpass(x, FS, "beta")
    y2 = causal_bandpass(x_perturbed, FS, "beta")
    np.testing.assert_allclose(y1[: t + 1], y2[: t + 1], atol=1e-10,
                                err_msg="causal_bandpass output at/before t changed when input after t was perturbed")


def test_E_causal_envelope_no_future_leakage():
    rng = np.random.default_rng(6)
    n = 2000
    x = _ar1_noise(n, rho=0.9, rng=rng)
    t = 1200
    x_perturbed = x.copy()
    x_perturbed[t + 1:] += rng.normal(0, 10.0, size=n - t - 1)

    env1, _ = causal_envelope(x, FS, "theta")
    env2, _ = causal_envelope(x_perturbed, FS, "theta")
    np.testing.assert_allclose(env1[: t + 1], env2[: t + 1], atol=1e-8,
                                err_msg="causal_envelope output at/before t changed when input after t was perturbed")


def test_E_filtfilt_reference_DOES_leak_future_information():
    """Negative control: confirms the test itself is discriminating -- an acausal filter (the
    exact filtfilt pattern flagged by the prepare-phase audit) SHOULD fail this invariance, so a
    green test suite isn't accidentally insensitive to the defect it's meant to catch."""
    from scipy.signal import butter, filtfilt
    rng = np.random.default_rng(7)
    n = 2000
    x = _ar1_noise(n, rho=0.9, rng=rng)
    t = 1200
    x_perturbed = x.copy()
    x_perturbed[t + 1:] += rng.normal(0, 10.0, size=n - t - 1)

    b, a = butter(4, [14 / (FS / 2), 30 / (FS / 2)], btype="band")
    y1 = filtfilt(b, a, x)
    y2 = filtfilt(b, a, x_perturbed)
    changed = ~np.isclose(y1[: t + 1], y2[: t + 1], atol=1e-10)
    assert changed.any(), "expected filtfilt to leak future information (sanity check on the test itself)"


# ---------------------------------------------------------------------------------------------
# F: event-locking confound -> trial-shuffle null flags it as non-significant
# ---------------------------------------------------------------------------------------------

def test_F_event_locking_confound_flagged_nonsignificant_by_trial_shuffle_null():
    rng = np.random.default_rng(8)
    n_trials, trial_len = 60, 400  # ms grid at 1kHz
    event_lag_ms = 8.0  # both P and R show a fixed evoked bump at a shared, deterministic offset
    t = np.arange(trial_len)

    def evoked_shape(center):
        return np.exp(-0.5 * ((t - center) / 6.0) ** 2)

    P_trials = np.stack([evoked_shape(150) + rng.normal(0, 0.3, trial_len) for _ in range(n_trials)])
    R_trials = np.stack([evoked_shape(150 + event_lag_ms) + rng.normal(0, 0.3, trial_len) for _ in range(n_trials)])
    # P and R are NOT causally linked to each other -- both are independent noisy readouts of the
    # same deterministic per-trial event timing.

    P_concat = P_trials.reshape(-1)
    R_concat = R_trials.reshape(-1)
    lags = np.arange(-25, 26, 1.0)
    C_obs = lagged_association(P_concat, R_concat, lags, fs=FS)
    observed_peak = np.nanmax(np.abs(C_obs))

    condition_group = np.zeros(n_trials, dtype=int)  # single condition/position group here
    n_perm = 100
    null_peaks = np.empty(n_perm)
    for k in range(n_perm):
        order = trial_permutation(np.arange(n_trials), condition_position_group=condition_group,
                                   rng=np.random.default_rng(9000 + k))
        R_shuffled = R_trials[order].reshape(-1)
        Cn = lagged_association(P_concat, R_shuffled, lags, fs=FS)
        null_peaks[k] = np.nanmax(np.abs(Cn))

    p = (1 + np.sum(null_peaks >= observed_peak)) / (n_perm + 1)
    assert p >= 0.05, (
        f"trial-shuffle null should flag a purely event-locked apparent coupling as "
        f"non-significant (p={p:.3f}), since P and R have no genuine trial-to-trial correspondence"
    )


# ---------------------------------------------------------------------------------------------
# G: CV-leakage synthetic control (mirrors the project's own historical Y_context bug)
# ---------------------------------------------------------------------------------------------

def test_G_naive_cv_leaks_grouped_cv_returns_to_chance():
    rng = np.random.default_rng(10)
    n_cycles, trials_per_cycle, n_features = 20, 10, 30
    cycle_id = np.repeat(np.arange(n_cycles), trials_per_cycle)
    n = len(cycle_id)
    y = (cycle_id % 2)  # label is a deterministic function of cycle identity
    # features: per-cycle random offset (leak vector) + pure noise -- ZERO direct link to y
    # beyond the cycle-identity channel
    cycle_offsets = rng.normal(0, 3.0, size=(n_cycles, n_features))
    X = cycle_offsets[cycle_id] + rng.normal(0, 1.0, size=(n, n_features))

    pipe = lambda: Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0))])

    # naive ungrouped CV: same-cycle trials appear in both train and test -> leak
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    naive_acc = []
    for train_idx, test_idx in skf.split(X, y):
        m = pipe()
        m.fit(X[train_idx], y[train_idx])
        naive_acc.append(m.score(X[test_idx], y[test_idx]))
    naive_acc = np.mean(naive_acc)

    # grouped leave-one-cycle-out CV: test cycle's offset never seen in training -> no leak
    grouped_acc = []
    for held_out in np.unique(cycle_id):
        train_idx = np.flatnonzero(cycle_id != held_out)
        test_idx = np.flatnonzero(cycle_id == held_out)
        m = pipe()
        m.fit(X[train_idx], y[train_idx])
        grouped_acc.append(m.score(X[test_idx], y[test_idx]))
    grouped_acc = np.mean(grouped_acc)

    assert naive_acc >= 0.85, f"expected naive ungrouped CV to show inflated accuracy from the cycle leak, got {naive_acc:.3f}"
    assert grouped_acc <= 0.65, f"expected grouped LOCO CV to return near chance (0.5), got {grouped_acc:.3f}"
    assert naive_acc - grouped_acc >= 0.20, "expected a clear gap between naive (leaked) and grouped (safe) accuracy"


# ---------------------------------------------------------------------------------------------
# Supporting primitive checks (nulls.py, causal_signal.py contract tests)
# ---------------------------------------------------------------------------------------------

def test_circular_shift_preserves_length_and_respects_exclusion_zone():
    rng = np.random.default_rng(11)
    x = rng.normal(size=(5, 500))
    shifted, shifts = circular_shift(x, fs=FS, exclusion_zone_ms=10.0, rng=rng)
    assert shifted.shape == x.shape
    assert np.all(np.abs(shifts) >= 10)  # >= 10 samples at 1kHz = >= 10ms
    # circular shift is a pure reindexing -> exact value-set preserved per row
    for i in range(x.shape[0]):
        assert set(np.round(shifted[i], 8)) == set(np.round(x[i], 8))


def test_spike_jitter_preserves_count_and_trial_bounds():
    rng = np.random.default_rng(12)
    spikes = np.sort(rng.uniform(0.0, 1.0, size=50))
    jittered = spike_jitter(spikes, trial_start=0.0, trial_end=1.0, jitter_range=(-0.02, 0.02), rng=rng)
    assert jittered.shape == spikes.shape
    assert np.all(jittered >= 0.0) and np.all(jittered < 1.0)


def test_filter_spec_group_delay_matches_manual_fir_formula():
    spec = filter_spec("theta", FS, n_cycles=3.0)
    expected_delay_ms = (spec.numtaps - 1) / 2.0 * 1000.0 / FS
    assert abs(spec.group_delay_ms - expected_delay_ms) < 1e-9
    # theta (low frequency) must need more taps, hence more delay, than high_gamma
    spec_hg = filter_spec("high_gamma", FS, n_cycles=3.0)
    assert spec.group_delay_ms > spec_hg.group_delay_ms
