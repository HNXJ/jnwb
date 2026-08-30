"""Regression tests for the nested-CV re-estimation and its controls (2026-08-29).

These lock the properties the biological interpretation depends on:
  * nested tuning never sees outer held-out trials;
  * the injected positive control shows monotone dose-response;
  * the permuted negative control sits at the overfitting floor, NOT at zero;
  * the variance floor prevents the low-variance blow-up that produced a delta of +1.6e8 in the
    distributed-lag work.
"""
from __future__ import annotations

import numpy as np
import pytest

from omission.jnwb_ext.spk_lfp_pilot import lag_interval_features  # noqa: E402
from omission.jnwb_ext.spk_lfp_nested import (
    ALPHAS, BETA_LEVELS, _FloorScaler, all_arms, cv_fit, delta_arm,
    inject_past_lfp_signal, lead_interval_features, permute_lag_features,
)


def _cell(n: int, *, seed: int = 0, true_beta: float = 0.0):
    """A realistic cell: correlated lag features, a strongly nuisance-predictable target."""
    rng = np.random.default_rng(seed)
    L = rng.normal(size=(n, 4))
    L[:, 1] += 0.7 * L[:, 0]
    L[:, 2] += 0.5 * L[:, 1]
    hist = rng.normal(size=n)
    y = 2.0 * hist + rng.normal(scale=1.0, size=n)
    if true_beta:
        y = inject_past_lfp_signal(y, L, true_beta)
    return L, hist, y


# ---------------------------------------------------------------- injection positive control
def test_injection_is_monotone_dose_response():
    L, hist, y = _cell(800, seed=1)
    deltas = [delta_arm(L, hist, inject_past_lfp_signal(y, L, b), alpha=None)["delta_pooled"]
              for b in BETA_LEVELS]
    assert deltas == sorted(deltas), f"injection not monotone in beta: {deltas}"
    assert deltas[-1] > deltas[0] + 0.05, "strongest injection barely detected"


def test_injection_scales_with_sd_of_target_not_absolute_units():
    """beta is defined in units of sd(y); rescaling y must not change the recovered delta."""
    L, hist, y = _cell(600, seed=2)
    d1 = delta_arm(L, hist, inject_past_lfp_signal(y, L, 0.3), alpha=None)["delta_pooled"]
    d2 = delta_arm(L, hist, inject_past_lfp_signal(1000.0 * y, L, 0.3), alpha=None)["delta_pooled"]
    assert d1 == pytest.approx(d2, abs=0.02)


def test_zero_injection_is_an_exact_no_op():
    L, _, y = _cell(200, seed=3)
    assert np.array_equal(inject_past_lfp_signal(y, L, 0.0), y)


def test_detection_threshold_is_worse_at_lower_n():
    """The n-dependence is the whole reason the pilot's omission conditions looked different."""
    beta = 0.10
    lo = delta_arm(*_inject(_cell(137, seed=4), beta), alpha=None)["delta_pooled"]
    hi = delta_arm(*_inject(_cell(820, seed=4), beta), alpha=None)["delta_pooled"]
    assert hi > lo, f"expected easier detection at high n: low_n={lo:.4f} high_n={hi:.4f}"


def _inject(cell, beta):
    L, hist, y = cell
    return L, hist, inject_past_lfp_signal(y, L, beta)


# ---------------------------------------------------------------- permuted negative control
def test_permutation_preserves_feature_covariance_and_breaks_pairing():
    L, _, _ = _cell(300, seed=5)
    P = permute_lag_features(L, seed=7)
    assert np.corrcoef(L.T)[0, 1] == pytest.approx(np.corrcoef(P.T)[0, 1], abs=0.15)
    assert not np.array_equal(P, L)
    assert np.allclose(np.sort(P[:, 0]), np.sort(L[:, 0]))  # same marginal, reordered


def test_permuted_null_floor_is_below_zero_at_low_n():
    """Zero is NOT the null: adding useless features costs held-out R^2. The negative control
    must land at that floor, which is what makes it usable as the detection threshold."""
    floors = [delta_arm(permute_lag_features(L, seed=s), hist, y, alpha=None)["delta_pooled"]
              for s in range(8)
              for L, hist, y in [_cell(137, seed=s)]]
    assert np.median(floors) < 0.0, f"expected a negative overfitting floor, got {floors}"


def test_permuted_and_zero_injection_agree_when_there_is_no_true_effect():
    """Tolerance is deliberately tight. The real quantities here are ~0.002, so a loose abs=
    tolerance would pass even a grossly miscalibrated permuted arm and test nothing."""
    L, hist, y = _cell(400, seed=6)
    d_perm = delta_arm(permute_lag_features(L, seed=11), hist, y, alpha=None)["delta_pooled"]
    d_zero = delta_arm(L, hist, y, alpha=None)["delta_pooled"]
    assert d_perm == pytest.approx(d_zero, abs=0.005)


# ---------------------------------------------------------------- nesting / leakage
def test_alpha_is_selected_per_fold_and_retained():
    L, hist, y = _cell(300, seed=8)
    out = cv_fit(np.column_stack([hist, L]), y, alpha=None)
    assert len(out["fold_alpha"]) == 5
    assert all(a in ALPHAS for a in out["fold_alpha"])


def test_fixed_alpha_arm_records_the_alpha_it_was_given():
    L, hist, y = _cell(300, seed=9)
    out = cv_fit(np.column_stack([hist, L]), y, alpha=1.0)
    assert out["fold_alpha"] == [1.0] * 5


def test_pure_noise_target_is_not_predicted():
    """Guards against leakage: an unpredictable target must not yield positive held-out R^2."""
    rng = np.random.default_rng(12)
    X, y = rng.normal(size=(300, 5)), rng.normal(size=300)
    assert cv_fit(X, y, alpha=None)["pooled_r2"] < 0.05


def test_delta_is_nan_below_the_minimum_trial_count():
    L, hist, y = _cell(20, seed=13)
    assert np.isnan(delta_arm(L, hist, y, alpha=None)["delta_pooled"])


# ---------------------------------------------------------------- variance floor
def test_floor_scaler_neutralises_a_near_constant_column():
    rng = np.random.default_rng(14)
    X = rng.normal(size=(100, 2))
    X[:, 1] = 1.0 + rng.normal(scale=5e-9, size=100)   # the blow-up geometry
    Z = _FloorScaler().fit(X).transform(X)
    assert np.abs(Z[:, 1]).max() < 10.0, "near-constant column was amplified"
    assert np.abs(Z[:, 0]).max() < 10.0


def test_floor_scaler_matches_standard_scaling_on_well_conditioned_data():
    rng = np.random.default_rng(15)
    X = rng.normal(loc=3.0, scale=2.0, size=(200, 3))
    Z = _FloorScaler().fit(X).transform(X)
    assert np.allclose(Z.mean(axis=0), 0.0, atol=1e-12)
    assert np.allclose(Z.std(axis=0), 1.0, atol=1e-12)


# ---------------------------------------------------------------- concurrent arm is forward
def test_lead_features_use_only_post_event_samples():
    time_ms = np.arange(-500.0, 500.0)
    env = np.tile(np.where(time_ms >= 0, 1.0, 0.0), (3, 1))   # power only AFTER the event
    lead = lead_interval_features(env, time_ms, 0.0)
    assert np.allclose(lead, 1.0), "lead features picked up pre-event samples"


# ------------------------------------------------ TEMPORAL PRECEDENCE OF THE PRIMARY ARM
# Independent verification (2026-08-29) found the primary arm's causal property had NO test
# anywhere in omission/tests/, while the sensitivity-only arm did. These close that gap: this is
# the single load-bearing property of the whole analysis, and a regression here would invalidate
# every past-LFP result without failing anything else.
def test_lag_features_contain_no_post_event_sample():
    """A spike of power placed strictly AFTER the event must be invisible to the past features."""
    time_ms = np.arange(-500.0, 500.0)
    env = np.tile(np.where(time_ms >= 0.0, 1.0, 0.0), (3, 1))
    lag = lag_interval_features(env, time_ms, 0.0)
    assert np.allclose(lag, 0.0), f"past features leaked post-event power: {lag}"


def test_lag_features_do_not_include_the_event_sample_itself():
    """Interval (a, b) is [event - b, event - a): the sample AT the event is excluded."""
    time_ms = np.arange(-500.0, 500.0)
    env = np.tile(np.where(time_ms == 0.0, 1.0, 0.0), (2, 1))   # power only exactly at t = 0
    assert np.allclose(lag_interval_features(env, time_ms, 0.0), 0.0)


def test_lag_features_do_see_pre_event_power_in_the_right_interval():
    """Complement of the leakage tests -- otherwise a function returning all zeros would pass."""
    time_ms = np.arange(-500.0, 500.0)
    env = np.tile(np.where((time_ms >= -50.0) & (time_ms < -25.0), 1.0, 0.0), (2, 1))
    lag = lag_interval_features(env, time_ms, 0.0)          # intervals (0,25) (25,50) (50,100) (100,250)
    assert np.allclose(lag[:, 1], 1.0), "the 25-50 ms past interval missed power placed inside it"
    assert np.allclose(lag[:, 0], 0.0) and np.allclose(lag[:, 2], 0.0)


def test_lag_features_track_the_event_time():
    """Precedence must hold relative to the EVENT, not to a fixed zero."""
    time_ms = np.arange(-500.0, 1000.0)
    env = np.tile(np.where((time_ms >= 450.0) & (time_ms < 475.0), 1.0, 0.0), (2, 1))
    assert np.allclose(lag_interval_features(env, time_ms, 500.0)[:, 1], 1.0)
    assert np.allclose(lag_interval_features(env, time_ms, 0.0), 0.0)  # same power, now in the future


def test_all_arms_returns_every_declared_arm():
    L, hist, y = _cell(300, seed=16)
    lead = np.random.default_rng(0).normal(size=(300, 4))
    arms = all_arms(L, lead, hist, y)
    for name in ["fixed", "nested", "concurrent", "permuted"] + [f"inject_{b:g}" for b in BETA_LEVELS]:
        assert name in arms and "delta_pooled" in arms[name]
