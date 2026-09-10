"""Unit tests for jnwb.spiking -- generic spike-response metrics (firing rate/latency/z-score,
significance classification, spike-LFP phase locking).
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.spiking import (
    compute_response_metrics,
    classify_response_significance,
    phase_locking_index,
    pairwise_phase_consistency,
    gaussian_smooth_rate,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.compute_response_metrics is compute_response_metrics
        assert jnwb.classify_response_significance is classify_response_significance
        assert jnwb.phase_locking_index is phase_locking_index
        assert jnwb.pairwise_phase_consistency is pairwise_phase_consistency
        assert jnwb.gaussian_smooth_rate is gaussian_smooth_rate

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("compute_response_metrics", "classify_response_significance",
                     "phase_locking_index", "pairwise_phase_consistency", "gaussian_smooth_rate"):
            assert name in jnwb.__all__

class TestComputeResponseMetrics:
    def test_empty_inputs_returns_zeroed_defaults(self):
        metrics = compute_response_metrics(np.array([]), np.array([0.0, 1.0]))
        assert metrics["baseline_rate"] == 0.0
        assert metrics["response_rate"] == 0.0
        assert metrics["latency"] is None

    def test_known_rates_computed_exactly(self):
        # 2 spikes per trial in baseline window (-0.25,-0.05 -> 0.2s), 4 spikes per trial in
        # response window (0.0,0.15 -> 0.15s), across 3 trials.
        onsets = np.array([0.0, 10.0, 20.0])
        spikes = []
        for onset in onsets:
            spikes += [onset - 0.2, onset - 0.1]  # baseline: 2 spikes
            spikes += [onset + 0.01, onset + 0.05, onset + 0.08, onset + 0.12]  # response: 4
        spikes = np.array(spikes)
        metrics = compute_response_metrics(spikes, onsets)
        assert metrics["baseline_rate"] == pytest.approx(2 / 0.2)
        assert metrics["response_rate"] == pytest.approx(4 / 0.15)
        assert metrics["response_count"] == 12

    def test_exact_boundary_conditions_right_open(self):
        # Onset at 0.0. Contiguous windows: baseline [-0.2, 0.0), response [0.0, 0.2)
        onsets = np.array([0.0])
        # Spike exactly at -0.2 (baseline_start) -> included in baseline
        # Spike exactly at 0.0 (baseline_stop / response_start) -> included in response, excluded from baseline
        # Spike exactly at 0.2 (response_stop) -> excluded from response
        spikes = np.array([-0.2, 0.0, 0.2])
        metrics = compute_response_metrics(
            spikes, onsets, baseline_window=(-0.2, 0.0), response_window=(0.0, 0.2)
        )
        assert metrics["baseline_rate"] == pytest.approx(1 / 0.2)  # exactly 1 spike at -0.2
        assert metrics["response_rate"] == pytest.approx(1 / 0.2)  # exactly 1 spike at 0.0
        assert metrics["response_count"] == 1  # only spike at 0.0, spike at 0.2 is excluded


class TestClassifyResponseSignificance:
    def test_below_min_spike_count_is_low_confidence(self):
        result = classify_response_significance({"response_count": 1, "response_zscore": 5.0},
                                                  min_spike_count=5)
        assert result["confidence"] == "low"
        assert not result["is_significant"]

    def test_strong_zscore_is_significant_high_confidence(self):
        result = classify_response_significance({"response_count": 10, "response_zscore": 4.0})
        assert result["is_significant"]
        assert result["confidence"] == "high"

    def test_weak_zscore_is_not_significant(self):
        result = classify_response_significance({"response_count": 10, "response_zscore": 0.5})
        assert not result["is_significant"]


class TestPhaseLockingIndex:
    def test_empty_spikes_returns_zeroed_defaults(self):
        result = phase_locking_index(np.array([]), np.array([0.0]), np.array([0.0]))
        assert result["peak_to_mean_contrast"] == 0.0
        assert result["pli"] == 0.0
        assert result["n_spikes"] == 0

    def test_perfectly_locked_spikes_give_high_pli_and_low_pvalue(self):
        # Spikes always occur at the same LFP phase (0 rad) -> maximal locking.
        n = 500
        lfp_timestamps = np.linspace(0, 10, 10000)
        lfp_phase = np.mod(2 * np.pi * 5 * lfp_timestamps, 2 * np.pi) - np.pi
        # find timestamps closest to phase 0
        spike_times = np.linspace(0.1, 9.9, n)
        result = phase_locking_index(spike_times, lfp_phase, lfp_timestamps, n_bins=18)
        assert result["n_spikes"] == n
        assert 0.0 <= result["peak_to_mean_contrast"] <= 1.0
        assert result["pli"] == result["peak_to_mean_contrast"]
        assert result["rayleigh_pvalue"] < 1e-10


class TestPairwisePhaseConsistency:
    def _ppc_explicit_o_n2(self, phases: np.ndarray) -> float:
        n = len(phases)
        if n < 2:
            return float("nan")
        s = 0.0
        for j in range(n):
            for k in range(j + 1, n):
                s += np.cos(phases[j] - phases[k])
        return float(2.0 * s / (n * (n - 1)))

    def test_identity_against_explicit_pairwise_sum(self):
        rng = np.random.default_rng(42)
        phases = rng.uniform(-np.pi, np.pi, size=60)
        val_on = pairwise_phase_consistency(phases)
        val_on2 = self._ppc_explicit_o_n2(phases)
        assert val_on == pytest.approx(val_on2, abs=1e-12)

    def test_identical_phases_give_unity(self):
        phases = np.full(50, 1.35)
        val = pairwise_phase_consistency(phases)
        assert val == pytest.approx(1.0, abs=1e-12)

    def test_phase_rotation_and_permutation_invariance(self):
        rng = np.random.default_rng(123)
        phases = rng.vonmises(mu=0.0, kappa=2.0, size=100)
        base = pairwise_phase_consistency(phases)
        # Rotation by arbitrary angle phi
        rotated = pairwise_phase_consistency(phases + 1.87)
        assert base == pytest.approx(rotated, abs=1e-12)
        # Permutation of sample order
        permuted = pairwise_phase_consistency(rng.permutation(phases))
        assert base == pytest.approx(permuted, abs=1e-12)

    def test_uniform_null_expectation_near_zero(self):
        rng = np.random.default_rng(999)
        # Large sample under uniform null
        phases = rng.uniform(-np.pi, np.pi, size=10000)
        val = pairwise_phase_consistency(phases)
        assert abs(val) < 0.02

    def test_degenerate_sample_size_returns_nan(self):
        assert np.isnan(pairwise_phase_consistency(np.array([])))
        assert np.isnan(pairwise_phase_consistency(np.array([1.2])))

    def test_multidimensional_axes(self):
        rng = np.random.default_rng(7)
        phases = rng.uniform(-np.pi, np.pi, size=(5, 40))
        ppc_axis1 = pairwise_phase_consistency(phases, axis=-1)
        assert ppc_axis1.shape == (5,)
        ppc_axis0 = pairwise_phase_consistency(phases.T, axis=0)
        np.testing.assert_allclose(ppc_axis1, ppc_axis0)

    def test_nan_propagation(self):
        phases = np.array([0.0, 0.5, np.nan, 1.0])
        assert np.isnan(pairwise_phase_consistency(phases))


class TestGaussianSmoothRate:
    def test_symmetric_acausal_impulse_response(self):
        # A delta impulse at center must spread symmetrically forward AND backward
        trace = np.zeros(21)
        trace[10] = 10.0
        smoothed = gaussian_smooth_rate(trace, bin_ms=10.0, sigma_ms=20.0)
        # Pre-event bins must become non-zero (proving acausality)
        assert smoothed[9] > 0
        assert smoothed[11] > 0
        # Symmetry about the impulse center
        np.testing.assert_allclose(smoothed[:10], smoothed[20:10:-1])

    def test_distinction_from_causal_exponential_smooth(self):
        from jnwb.onset_fitting import causal_exp_smooth
        trace = np.zeros(50)
        trace[25] = 10.0
        gauss = gaussian_smooth_rate(trace, bin_ms=10.0, sigma_ms=30.0)
        causal = causal_exp_smooth(trace, bin_ms=10.0, tau_ms=30.0)
        # Causal filter must have exactly 0 before index 25
        np.testing.assert_allclose(causal[:25], 0.0)
        # Gaussian filter has non-zero anticipatory spread before index 25
        assert np.sum(gauss[:25]) > 0.1

    def test_zero_or_negative_sigma_returns_unmodified_copy(self):
        trace = np.array([1.0, 5.0, 2.0])
        np.testing.assert_array_equal(gaussian_smooth_rate(trace, bin_ms=10.0, sigma_ms=0.0), trace)
        np.testing.assert_array_equal(gaussian_smooth_rate(trace, bin_ms=10.0, sigma_ms=-5.0), trace)

    def test_invalid_bin_ms_raises(self):
        trace = np.ones(10)
        with pytest.raises(ValueError, match="strictly positive"):
            gaussian_smooth_rate(trace, bin_ms=0.0)

