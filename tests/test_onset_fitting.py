"""Unit tests for jnwb.onset_fitting -- causal PSTH smoothing + causality-bounded exponential
onset-latency fit, promoted 2026-08-23 from omission.jnwb_ext.onset_fitting
(99%-jnwb-sufficiency normalization). These mirror the module's own `if __name__ == "__main__"`
synthetic self-tests, converted to pytest so they run under the standard suite.
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.onset_fitting import causal_exp_smooth, fit_exponential_onset, onset_model, DEFAULT_TAU_MS


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        from jnwb import causal_exp_smooth as pub_smooth
        from jnwb import fit_exponential_onset as pub_fit
        from jnwb import onset_model as pub_model
        assert pub_smooth is causal_exp_smooth
        assert pub_fit is fit_exponential_onset
        assert pub_model is onset_model

    def test_listed_in_jnwb_all(self):
        import jnwb
        assert "causal_exp_smooth" in jnwb.__all__
        assert "fit_exponential_onset" in jnwb.__all__
        assert "onset_model" in jnwb.__all__


class TestCausalExpSmooth:
    def test_output_shape_matches_input(self):
        rate = np.random.default_rng(0).normal(10, 1, size=100)
        smoothed = causal_exp_smooth(rate, bin_ms=5.0)
        assert smoothed.shape == rate.shape

    def test_constant_input_converges_to_constant(self):
        # Left-zero-padded causal convolution ramps up over the first ~5*tau_ms/bin_ms samples
        # (edge effect, expected); the steady-state tail must equal the constant input.
        rate = np.full(50, 7.0)
        smoothed = causal_exp_smooth(rate, bin_ms=5.0, tau_ms=30.0)
        assert np.allclose(smoothed[-10:], 7.0, atol=1e-6)

    def test_step_response_is_causal_not_acausal(self):
        # A step at index 50 must not visibly affect the smoothed trace before index 50
        # (a causal/forward-only kernel cannot leak future information backward).
        rate = np.zeros(100)
        rate[50:] = 10.0
        smoothed = causal_exp_smooth(rate, bin_ms=5.0, tau_ms=15.0)
        assert np.allclose(smoothed[:50], 0.0, atol=1e-9)
        assert smoothed[50] > 0.0


class TestOnsetModel:
    def test_flat_before_t0(self):
        t = np.linspace(0, 100, 50)
        out = onset_model(t, t0=50.0, tau=10.0, amplitude=20.0, baseline=5.0)
        assert np.allclose(out[t < 50.0], 5.0)

    def test_approaches_baseline_plus_amplitude_for_large_t(self):
        t = np.array([1000.0])  # far past t0, many tau's out
        out = onset_model(t, t0=0.0, tau=10.0, amplitude=20.0, baseline=5.0)
        assert np.isclose(out[0], 25.0, atol=1e-6)


class TestFitExponentialOnset:
    def _synthetic_psth(self, t0_true, tau_true, amp_true, baseline_true, n_trials, seed=0):
        rng = np.random.default_rng(seed)
        bin_ms = 5.0
        t_edges = np.arange(-100.0, 600.0, bin_ms)
        t_ms = t_edges[:-1] + bin_ms / 2.0
        true_rate = np.clip(onset_model(t_ms, t0_true, tau_true, amp_true, baseline_true), 0.0, None)
        lam = true_rate * (bin_ms / 1000.0) * n_trials
        counts = rng.poisson(lam)
        noisy_rate = counts / (n_trials * (bin_ms / 1000.0))
        smoothed = causal_exp_smooth(noisy_rate, bin_ms, tau_ms=30.0)
        return t_ms, smoothed

    def test_recovers_known_onset_within_tolerance(self):
        t_ms, rate = self._synthetic_psth(50.0, 20.0, 30.0, 5.0, n_trials=60, seed=0)
        fit = fit_exponential_onset(t_ms, rate, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, 0.0))
        assert abs(fit["t0"] - 50.0) < 2 * DEFAULT_TAU_MS
        assert fit["converged"]

    def test_causality_bound_clamps_pre_window_onset(self):
        # True onset before the allowed window -- fit must not report a t0 outside bounds
        # even though the data would otherwise support an earlier onset.
        t_ms, rate = self._synthetic_psth(-50.0, 20.0, 30.0, 5.0, n_trials=60, seed=1)
        fit = fit_exponential_onset(t_ms, rate, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, -20.0))
        assert fit["t0"] >= 0.0

    def test_rejects_too_few_time_points(self):
        with pytest.raises(ValueError):
            fit_exponential_onset(np.array([0.0, 1.0, 2.0]), np.array([1.0, 2.0, 3.0]))

    def test_rejects_empty_t0_bounds(self):
        t = np.linspace(0, 100, 20)
        rate = np.ones(20)
        with pytest.raises(ValueError):
            fit_exponential_onset(t, rate, t0_bounds=(50.0, 50.0))

    def test_returns_expected_keys(self):
        t_ms, rate = self._synthetic_psth(45.0, 15.0, 50.0, 3.0, n_trials=80, seed=2)
        fit = fit_exponential_onset(t_ms, rate, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, 0.0))
        assert set(fit.keys()) == {"t0", "tau", "amplitude", "baseline", "r2", "converged", "cost"}
