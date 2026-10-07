"""Unit tests for jnwb.onset_fitting -- causal PSTH smoothing + causality-bounded exponential
onset-latency fit. These mirror the module's own `if __name__ == "__main__"`
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
        # Edge-value-padded causal convolution preserves constant baseline across all bins,
        # eliminating startup ramp-up depression (0.2.3-REV-09).
        rate = np.full(50, 7.0)
        smoothed = causal_exp_smooth(rate, bin_ms=5.0, tau_ms=30.0)
        assert np.allclose(smoothed, 7.0, atol=1e-12)

    def test_constant_baseline_preserved_at_startup(self):
        """Edge padding ensures constant baseline rate is preserved without startup ramp-up (0.2.3-REV-09)."""
        rate = np.full(100, 25.0)
        smoothed = causal_exp_smooth(rate, bin_ms=5.0, tau_ms=30.0)
        assert np.allclose(smoothed, 25.0, atol=1e-12)
        assert smoothed[0] == pytest.approx(25.0, abs=1e-12)

    def test_empty_rate_returns_empty(self):
        smoothed = causal_exp_smooth(np.array([]), bin_ms=5.0)
        assert smoothed.size == 0

    def test_step_response_is_causal_not_acausal(self):
        # A step at index 50 must not visibly affect the smoothed trace before index 50
        # (a causal/forward-only kernel cannot leak future information backward).
        rate = np.zeros(100)
        rate[50:] = 10.0
        smoothed = causal_exp_smooth(rate, bin_ms=5.0, tau_ms=15.0)
        assert np.allclose(smoothed[:50], 0.0, atol=1e-9)
        assert smoothed[50] > 0.0

    @pytest.mark.parametrize("tau_ms", [0, -5.0, np.nan, np.inf])
    def test_a_tau_that_is_not_finite_and_positive_is_refused_by_name(self, tau_ms):
        # tau_ms=0 divided by zero and returned ten NaN with only a RuntimeWarning.
        with pytest.raises(ValueError, match="causal_exp_smooth: tau_ms must be a finite positive"):
            causal_exp_smooth(np.ones(10), 1.0, tau_ms=tau_ms)


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
        """The tolerance is tied to this construction at this seed.

        `2 * DEFAULT_TAU_MS` is 60 ms, wider than the 50 ms onset being recovered, so a
        fit that reported onset at 0 ms or at 109 ms passed a test named for recovery.
        The error here is 3.57 ms. The bound is not a general one: over 40 seeds this
        construction has p95 20.7 ms and max 29.3 ms, so a fixed 15 ms bound would fail
        6 of them. Reseed this test and the bound has to be re-measured.
        """
        t_ms, rate = self._synthetic_psth(50.0, 20.0, 30.0, 5.0, n_trials=60, seed=0)
        fit = fit_exponential_onset(t_ms, rate, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, 0.0))
        assert fit["converged"]
        assert abs(fit["t0"] - 50.0) < 8.0

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

    def test_a_window_ending_before_the_default_lower_bound_names_the_default(self):
        t = np.linspace(-200.0, -10.0, 50)
        rate = np.random.default_rng(0).normal(10.0, 1.0, size=50)
        with pytest.raises(ValueError, match="default lower bound of 0 ms"):
            fit_exponential_onset(t, rate)
        fit = fit_exponential_onset(t, rate, t0_bounds_ms=(None, None))
        assert -200.0 <= fit["t0"] <= -10.0

    def test_returns_expected_keys(self):
        t_ms, rate = self._synthetic_psth(45.0, 15.0, 50.0, 3.0, n_trials=80, seed=2)
        fit = fit_exponential_onset(t_ms, rate, t0_bounds=(0.0, 600.0), baseline_window=(-100.0, 0.0))
        assert set(fit.keys()) == {"t0", "tau", "amplitude", "baseline", "r2", "converged", "cost", "bound_status"}
        assert fit["bound_status"] is None


class TestANoiseOnlyPSTH:
    """`bound_status` checks t0 alone, so a fit to a PSTH with no response usually reads
    None; what marks it is `tau` at an end of its bounds and `r2` near 0. The docs state
    this for the quickstart's PSTH and for noise PSTHs in general; these tests hold both.
    """

    ONSETS = np.array([1.0, 3.0, 5.0, 7.0])
    TAU_BOUNDS = (1.0, 150.0)  # the default `tau_bounds_ms`

    def _fit(self, spike_times):
        from jnwb import raster_psth

        t_ms, rate, _ = raster_psth(spike_times, self.ONSETS, win_ms=(-100.0, 400.0), bin_ms=10.0)
        return fit_exponential_onset(t_ms, rate, t0_bounds_ms=(0.0, 250.0))

    def _tau_at_a_bound(self, fit):
        return min(abs(fit["tau"] - b) for b in self.TAU_BOUNDS) < 1e-2

    def test_the_quickstart_psth(self):
        """The page's own code blocks, run in order up to its onset fit, so the draw is the
        page's and not a retyped copy that can fall out of step with it."""
        import contextlib
        import io
        import re
        from pathlib import Path

        page = (Path(__file__).resolve().parents[1] / "docs" / "quickstart.md").read_text(
            encoding="utf-8")
        blocks = re.findall(r"```python\n(.*?)```", page, flags=re.S)
        upto = next(i for i, b in enumerate(blocks) if "fit_exponential_onset" in b)
        namespace: dict = {}
        with contextlib.redirect_stdout(io.StringIO()):
            for block in blocks[:upto + 1]:
                exec(compile(block, "docs/quickstart.md", "exec"), namespace)
        fit = namespace["onset_fit"]

        assert fit["bound_status"] is None
        assert self._tau_at_a_bound(fit), fit["tau"]
        assert abs(fit["r2"]) < 0.05, fit["r2"]

    def test_noise_psths_usually_read_none_with_tau_at_a_bound_and_r2_near_zero(self):
        fits = [self._fit(np.sort(np.random.default_rng(seed).uniform(0, 10, 200)))
                for seed in range(20)]
        unflagged = [f for f in fits if f["bound_status"] is None]

        assert len(unflagged) > len(fits) / 2, f"{len(unflagged)} of {len(fits)} read None"
        assert sum(self._tau_at_a_bound(f) for f in unflagged) > len(unflagged) / 2
        assert max(f["r2"] for f in unflagged) < 0.2
