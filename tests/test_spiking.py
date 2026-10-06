"""Unit tests for jnwb.spiking -- generic spike-response metrics (firing rate/latency/z-score,
significance classification, spike-LFP phase locking).
"""
from __future__ import annotations

import warnings

import numpy as np
import pytest
from scipy import stats

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

    @pytest.mark.parametrize("spike, onset, window", [
        (0.3, 0.03, (0.27, 0.5)),   # exactly on the start: 0.3 - 0.03 == 0.27, 0.03 + 0.27 > 0.3
        (0.06, 0.02, (0.0, 0.04)),  # 0.06 - 0.02 < 0.04, but 0.02 + 0.04 <= 0.06
    ])
    def test_windows_select_by_spike_minus_onset(self, spike, onset, window):
        assert window[0] <= spike - onset < window[1]       # the case is what it is named
        m = compute_response_metrics(np.array([spike]), np.array([onset]),
                                     baseline_window_s=(-0.02, -0.01), response_window_s=window)
        assert m["response_count"] == 1
        assert m["latency"] == (spike - onset) - window[0]

    def test_per_trial_rates_are_returned_in_onset_order(self):
        onsets = np.array([0.0, 10.0, 20.0])
        spikes = np.array([-0.2, 0.01, 0.02, 9.8, 9.9, 20.05])  # baseline 1, 2, 0; response 2, 0, 1
        m = compute_response_metrics(spikes, onsets)
        np.testing.assert_allclose(m["baseline_rates"], np.array([1, 2, 0]) / 0.2, rtol=1e-12)
        np.testing.assert_allclose(m["response_rates"], np.array([2, 0, 1]) / 0.15, rtol=1e-12)
        silent = compute_response_metrics(np.array([]), onsets)
        np.testing.assert_array_equal(silent["baseline_rates"], np.zeros(3))
        np.testing.assert_array_equal(silent["response_rates"], np.zeros(3))

    def test_per_trial_counts_and_window_lengths_are_returned(self):
        onsets = np.array([0.0, 10.0, 20.0])
        spikes = np.array([-0.2, 0.01, 0.02, 9.8, 9.9, 20.05])  # baseline 1, 2, 0; response 2, 0, 1
        m = compute_response_metrics(spikes, onsets)
        assert m["baseline_counts"].dtype.kind == "i" and m["response_counts"].dtype.kind == "i"
        np.testing.assert_array_equal(m["baseline_counts"], [1, 2, 0])
        np.testing.assert_array_equal(m["response_counts"], [2, 0, 1])
        np.testing.assert_allclose([m["baseline_duration_s"], m["response_duration_s"]],
                                   [0.2, 0.15], rtol=1e-12)
        silent = compute_response_metrics(np.array([]), onsets)
        np.testing.assert_array_equal(silent["baseline_counts"], [0, 0, 0])
        np.testing.assert_allclose(silent["response_duration_s"], 0.15, rtol=1e-12)

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

    # A reversed window used to return a negative count with a positive rate.
    @pytest.mark.parametrize("window", [(0.15, 0.0), (0.1, 0.1)])
    def test_reversed_or_empty_baseline_window_raises(self, window):
        spikes = np.array([-0.2, -0.1, 0.05, 0.1])
        with pytest.raises(ValueError, match="baseline_window_s"):
            compute_response_metrics(spikes, np.array([0.0, 1.0]), baseline_window_s=window)

    @pytest.mark.parametrize("window", [(0.15, 0.0), (0.1, 0.1)])
    def test_reversed_or_empty_response_window_raises(self, window):
        spikes = np.array([-0.2, -0.1, 0.05, 0.1])
        with pytest.raises(ValueError, match="response_window_s"):
            compute_response_metrics(spikes, np.array([0.0, 1.0]), response_window_s=window)


class TestClassifyResponseSignificance:
    def test_below_min_spike_count_is_low_confidence(self):
        result = classify_response_significance({"response_count": 1, "response_zscore": 5.0},
                                                  min_spike_count=5)
        assert result["confidence"] == "low"
        assert not result["is_significant"]

    # Twenty trials, 0.20 s baseline and 0.15 s response windows (the defaults): 40 baseline
    # and 100 response spikes, where equal rates would put 3/7 of them in the response.
    BASE = np.tile([2, 1, 3, 2, 2], 4)
    RESP = np.tile([5, 4, 6, 5, 5], 4)

    def _metrics(self, z, base=BASE, resp=RESP, d_b=0.2, d_r=0.15):
        return {"response_count": int(np.nansum(resp)), "response_zscore": z,
                "baseline_counts": base, "response_counts": resp,
                "baseline_duration_s": d_b, "response_duration_s": d_r}

    def test_strong_zscore_is_significant_high_confidence(self):
        result = classify_response_significance(self._metrics(4.0))
        assert result["is_significant"]
        assert result["confidence"] == "high"

    def test_weak_zscore_is_not_significant(self):
        result = classify_response_significance(self._metrics(0.5))
        assert not result["is_significant"]

    def test_the_p_value_is_the_conditional_binomial_test(self):
        out = classify_response_significance(self._metrics(4.0))
        np.testing.assert_allclose(
            out["pvalue"], stats.binomtest(100, 140, 0.15 / 0.35).pvalue, rtol=1e-12)

    def test_the_p_value_falls_as_trials_accumulate_at_a_fixed_effect(self):
        """The p derived from an effect size did not depend on the trial count."""
        base, resp = np.array([1, 0, 2, 1, 1]), np.array([2, 1, 2, 3, 2])
        p = [classify_response_significance(
                 self._metrics(2.5, np.tile(base, k), np.tile(resp, k)), min_spike_count=0
             )["pvalue"] for k in (1, 2, 4, 8)]
        assert all(later < earlier for earlier, later in zip(p, p[1:])), p
        assert p[-1] < 1e-4, p

    def test_no_spikes_in_either_window_gives_p_one(self):
        zeros = np.zeros(20, dtype=int)
        out = classify_response_significance(self._metrics(0.0, zeros, zeros), min_spike_count=0)
        assert out["pvalue"] == 1.0 and out["confidence"] == "none"

    def test_counts_at_the_expected_share_are_not_significant_whatever_the_zscore(self):
        """The effect-size gate passes at z = 4, but 30 of 70 spikes is exactly the 3/7 share
        equal rates predict."""
        out = classify_response_significance(
            self._metrics(4.0, np.full(10, 4), np.full(10, 3)))
        assert out["is_significant"] is False
        assert out["pvalue"] == 1.0 and out["confidence"] == "none"

    def test_alpha_is_the_level_the_p_value_is_held_to(self):
        loose = classify_response_significance(self._metrics(4.0))
        assert loose["is_significant"] and 0.0 < loose["pvalue"] < 1e-6
        strict = classify_response_significance(self._metrics(4.0), alpha=loose["pvalue"] / 2)
        assert strict["is_significant"] is False and strict["confidence"] == "none"
        with pytest.raises(ValueError, match="alpha"):
            classify_response_significance(self._metrics(4.0), alpha=0.0)

    def test_p_below_alpha_is_strict(self):
        base, resp = np.array([2, 1, 2, 1, 2]), np.array([3, 3, 2, 3, 3])
        p = classify_response_significance(self._metrics(2.5, base, resp))["pvalue"]
        assert 0.0 < p < 1.0
        at = classify_response_significance(self._metrics(2.5, base, resp), alpha=p)
        above = classify_response_significance(
            self._metrics(2.5, base, resp), alpha=float(np.nextafter(p, 1.0)))
        assert at["is_significant"] is False and above["is_significant"] is True

    def test_mismatched_or_length_one_counts_raise(self):
        with pytest.raises(ValueError, match="differ in shape"):
            classify_response_significance(self._metrics(4.0, self.BASE[:-1], self.RESP))
        with pytest.raises(ValueError, match="differ in shape"):
            classify_response_significance(self._metrics(4.0, self.BASE[:1], self.RESP))

    def test_two_dimensional_counts_raise(self):
        with pytest.raises(ValueError, match="1-D"):
            classify_response_significance(
                self._metrics(4.0, self.BASE.reshape(4, 5), self.RESP.reshape(4, 5)))

    def test_a_nan_count_is_undefined(self):
        """A NaN is a count that is present and unmeasured, not a missing key: no warning."""
        resp = self.RESP.astype(float)
        resp[3] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            out = classify_response_significance(self._metrics(4.0, self.BASE, resp))
        assert out["confidence"] == "undefined" and np.isnan(out["pvalue"])
        assert out["is_significant"] is False

    @pytest.mark.parametrize("bad", [-1, 2.5], ids=["negative", "fractional"])
    def test_a_count_that_is_not_a_non_negative_integer_raises(self, bad):
        resp = self.RESP.astype(float)
        resp[3] = bad
        with pytest.raises(ValueError, match="non-negative integers"):
            classify_response_significance(self._metrics(4.0, self.BASE, resp))

    @pytest.mark.parametrize("d_r", [0.0, np.inf], ids=["zero", "infinite"])
    def test_a_window_length_that_is_not_positive_and_finite_raises(self, d_r):
        with pytest.raises(ValueError, match="positive and finite"):
            classify_response_significance(self._metrics(4.0, d_r=d_r))

    def test_a_dict_without_window_lengths_is_undefined_with_a_warning(self):
        m = self._metrics(4.0)
        del m["baseline_duration_s"], m["response_duration_s"]
        with pytest.warns(UserWarning, match="duration_s"):
            out = classify_response_significance(m)
        assert out["confidence"] == "undefined" and np.isnan(out["pvalue"])

    def test_a_summary_without_per_trial_counts_is_undefined_with_a_warning(self):
        with pytest.warns(UserWarning, match="per-trial counts"):
            out = classify_response_significance({"response_count": 10, "response_zscore": 4.0})
        assert out["confidence"] == "undefined" and out["is_significant"] is False
        assert np.isnan(out["pvalue"])

    @pytest.mark.parametrize("windows", [
        ((-0.25, -0.05), (0.0, 0.15)),   # the defaults: 0.20 s against 0.15 s
        ((-0.2, 0.0), (0.0, 0.2)),
    ], ids=["default_unequal", "equal"])
    def test_at_zero_effect_the_false_positive_rate_is_at_most_alpha(self, windows):
        """Homogeneous 2 Hz Poisson units over 500 trials. A test on paired rate differences
        is miscalibrated when the windows differ in length: a response spike is worth
        6.67 Hz and a baseline spike 5 Hz, so the null differences are skewed. The bound is
        alpha plus three binomial standard errors over the 300 simulated units. The median p
        is held near 0.5 so that a test which never rejects cannot pass."""
        rng = np.random.default_rng(20260926)
        onsets = np.arange(500) * 1.0 + 1.0
        n_units, alpha = 300, 0.05
        p = []
        for _ in range(n_units):
            st = np.sort(rng.uniform(0.0, 502.0, rng.poisson(2.0 * 502.0)))
            m = compute_response_metrics(st, onsets, baseline_window_s=windows[0],
                                         response_window_s=windows[1])
            p.append(classify_response_significance(m, zscore_threshold=0.0,
                                                    min_spike_count=0)["pvalue"])
        p = np.array(p)
        assert not np.isnan(p).any()
        bound = alpha + 3.0 * np.sqrt(alpha * (1 - alpha) / n_units)
        assert np.mean(p < alpha) <= bound, (np.mean(p < alpha), bound)
        assert 0.3 < np.median(p) < 0.7, np.median(p)

    def test_bursting_at_zero_effect_rejects_about_thirty_percent(self):
        """The limit the docstring states: 5 Hz firing in bursts of four spikes 4 ms apart,
        200 trials, default windows, no effect. The test counts each spike of a burst as an
        independent event, so about 30% of 300 units fall below p = 0.05."""
        rng = np.random.default_rng(20260927)
        onsets = np.arange(200) * 1.0 + 1.0
        p = []
        for _ in range(300):
            starts = rng.uniform(0.0, 202.0, rng.poisson(5.0 / 4 * 202.0))
            st = np.sort((starts[:, None] + np.arange(4) * 0.004).ravel())
            m = compute_response_metrics(st, onsets)
            p.append(classify_response_significance(m, zscore_threshold=0.0,
                                                    min_spike_count=0)["pvalue"])
        rate = float(np.mean(np.array(p) < 0.05))
        assert 0.2 < rate < 0.4, rate


class TestPhaseLockingIndex:
    def test_empty_spikes_return_nan_values(self):
        result = phase_locking_index(np.array([]), np.array([0.0]), np.array([0.0]))
        assert np.isnan(result["peak_to_mean_contrast"])
        assert np.isnan(result["pli"])
        assert result["n_spikes"] == 0

    def test_perfectly_locked_spikes_give_high_pli_and_low_pvalue(self):
        # Spikes on every cycle of a 5 Hz LFP, so each lands at the same phase.
        #
        # This fixture used to be np.linspace(0.1, 9.9, 500): evenly spaced in TIME, not
        # in phase. On a 5 Hz LFP those spikes advance 0.098 of a cycle each, so their
        # phases are near-uniform and p ~ 1 is the correct answer. The test passed only
        # because np.interp(..., period=2*np.pi) folded the recording modulo 6.28 seconds
        # and manufactured a concentration. It was asserting the defect.
        lfp_timestamps = np.linspace(0, 10, 10000)
        lfp_phase = np.mod(2 * np.pi * 5 * lfp_timestamps, 2 * np.pi) - np.pi
        spike_times = np.arange(1, 50) * 0.2
        result = phase_locking_index(spike_times, lfp_phase, lfp_timestamps, n_bins=18)
        assert result["n_spikes"] == len(spike_times)
        assert 0.0 <= result["peak_to_mean_contrast"] <= 1.0
        assert result["pli"] == result["peak_to_mean_contrast"]
        assert result["rayleigh_pvalue"] < 1e-10
        assert result["rayleigh_z"] > 40.0

    def test_spikes_spread_over_the_cycle_are_not_called_locked(self):
        """The discriminator the old fixture accidentally became."""
        lfp_timestamps = np.linspace(0, 10, 10000)
        lfp_phase = np.mod(2 * np.pi * 5 * lfp_timestamps, 2 * np.pi) - np.pi
        result = phase_locking_index(
            np.linspace(0.1, 9.9, 500), lfp_phase, lfp_timestamps, n_bins=18
        )
        assert result["rayleigh_pvalue"] > 0.1
        assert result["rayleigh_z"] < 3.0

    def test_locking_estimate_does_not_degrade_with_recording_length(self):
        """np.interp's `period` is the period of x, so it wrapped the time axis: a unit
        whose true resultant length is 0.995 reported pli 0.31 over 60 s and 0.80 over
        6 s. The estimate must not depend on how long the recording is."""
        rng = np.random.default_rng(0)
        values = []
        for duration in (6.0, 60.0, 240.0):
            timestamps = np.arange(0.0, duration, 0.001)
            phase = np.angle(np.exp(1j * 2 * np.pi * 8.0 * timestamps))
            spikes = np.arange(1, int(8 * duration)) / 8.0 + rng.normal(
                0.0, 0.002, size=int(8 * duration) - 1
            )
            spikes = spikes[(spikes > 0) & (spikes < duration)]
            values.append(phase_locking_index(spikes, phase, timestamps)["pli"])
        assert max(values) - min(values) < 0.05, f"pli drifted with duration: {values}"

    def test_the_rayleigh_p_value_is_never_negative(self):
        """The series expansion underflows negative at large z, and a negative p passes
        every `p < alpha` test and corrupts FDR downstream."""
        timestamps = np.arange(0.0, 600.0, 0.001)
        phase = np.angle(np.exp(1j * 2 * np.pi * 8.0 * timestamps))
        rng = np.random.default_rng(0)
        spikes = np.arange(1, 4800) / 8.0 + rng.normal(0.0, 0.002, size=4799)
        spikes = spikes[(spikes > 0) & (spikes < 600.0)]
        result = phase_locking_index(spikes, phase, timestamps)
        assert result["rayleigh_z"] > 1000.0
        assert result["rayleigh_pvalue"] >= 0.0
        assert not str(result["rayleigh_pvalue"]).startswith("-")


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



class TestResponseMetricsDoNotManufactureResponses:
    """`response_zscore` differenced raw spike COUNTS between a baseline and a response
    window that need not be, and by default are not, the same length (0.200 s against
    0.150 s). A homogeneous unit therefore scored a response it did not have, and the
    spurious z grew as the square root of the firing rate: -0.47 at 20 Hz, -1.04 at
    100 Hz, -1.91 at 500 Hz. `classify_response_significance` takes abs(z), so a fast
    non-responsive unit would eventually be certified as responding.
    """

    ONSETS = np.arange(200) * 2.0

    @pytest.mark.parametrize("rate", [20, 100, 500, 2000])
    def test_a_homogeneous_unit_scores_no_response_at_any_rate(self, rate):
        rng = np.random.default_rng(0)
        st = np.sort(rng.uniform(0, 400, size=int(rate * 400)))
        m = compute_response_metrics(st, self.ONSETS)
        assert abs(m["response_zscore"]) < 1.0, (
            f"constant-rate unit at {rate} Hz scored z = {m['response_zscore']:+.2f}"
        )
        assert classify_response_significance(m)["is_significant"] is False

    def test_equal_windows_are_unchanged_by_the_rate_conversion(self):
        """Dividing both windows by their own duration is exactly a no-op when they are
        equal, which is the case where differencing counts was already correct."""
        rng = np.random.default_rng(1)
        st = np.sort(rng.uniform(0, 400, size=8000))
        m = compute_response_metrics(
            st, self.ONSETS, baseline_window=(-0.2, 0.0), response_window=(0.0, 0.2)
        )
        counts_b, counts_r = [], []
        for o in self.ONSETS:
            counts_b.append(int(np.sum((st >= o - 0.2) & (st < o))))
            counts_r.append(int(np.sum((st >= o) & (st < o + 0.2))))
        expected = (np.mean(counts_r) - np.mean(counts_b)) / np.std(counts_b)
        assert m["response_zscore"] == pytest.approx(expected, rel=1e-9)

    def test_a_silent_baseline_is_undefined_not_zero(self):
        """A unit driven hard from a perfectly silent baseline returned z = +0.00 and
        'none' -- a fabricated null on the strongest possible evidence."""
        rng = np.random.default_rng(2)
        st = np.sort(np.concatenate([o + rng.uniform(0.0, 0.150, size=20) for o in self.ONSETS]))
        m = compute_response_metrics(st, self.ONSETS)
        assert m["response_count"] == 4000
        assert m["response_rate"] > 100.0
        assert np.isnan(m["response_zscore"])
        sig = classify_response_significance(m)
        assert sig["confidence"] == "undefined"
        np.testing.assert_allclose(
            sig["pvalue"], stats.binomtest(4000, 4000, 0.15 / 0.35).pvalue, rtol=1e-12)
        assert sig["is_significant"] is False

    def test_a_silent_baseline_still_reports_the_counts_p(self):
        """40 trials of 3 response spikes over a zero baseline. The z-score needs baseline
        variance and is NaN, but the counts test does not: 120 of 120 spikes where equal
        rates put 3/7 in the response. The p was reported as NaN."""
        onsets = np.arange(40) * 1.0 + 1.0
        st = np.sort(np.concatenate([o + np.array([0.01, 0.05, 0.1]) for o in onsets]))
        m = compute_response_metrics(st, onsets)
        assert np.isnan(m["response_zscore"])
        assert int(np.sum(m["baseline_counts"])) == 0 and m["response_count"] == 120
        sig = classify_response_significance(m)
        np.testing.assert_allclose(
            sig["pvalue"], stats.binomtest(120, 120, 0.15 / 0.35).pvalue, rtol=1e-12)
        assert sig["pvalue"] < 1e-44
        assert sig["confidence"] == "undefined" and sig["is_significant"] is False

    def test_a_genuine_response_is_still_detected(self):
        rng = np.random.default_rng(3)
        base = np.sort(rng.uniform(0, 400, size=8000))
        drive = np.concatenate(
            [o + rng.uniform(0.0, 0.150, size=rng.poisson(6)) for o in self.ONSETS]
        )
        m = compute_response_metrics(np.sort(np.concatenate([base, drive])), self.ONSETS)
        sig = classify_response_significance(m)
        assert m["response_zscore"] > 3.0 and sig["is_significant"] and sig["confidence"] == "high"


class TestFleissKappa:
    # Fleiss (1971), doi:10.1037/h0031619: 30 patients, 6 raters each, categories
    # Depression, Personality disorder, Schizophrenia, Neurosis, Other; the paper reports
    # kappa = .430. Ratings as transcribed in the R packages irr (`diagnoses`) and lagree
    # (`diagnosis`, data-raw/make-data-for-examples.R).
    FLEISS_1971 = (
        "NNNNNN PPPOOO PSSSSO OOOOOO PPPNNN DDSSSS SSSSOO DDSSSN DDNNNN OOOOOO "
        "DNNNNN DPNNNN PPPSSS DNNNNN PPNNNO SSSSSO DDDNOO DDDDDP PPNNNN DSSOOO "
        "OOOOOO PNNNNN PPNOOO DDNNNN DNNNNO PPPPPN DDDDOO PPNNNN DSSSSS OOOOOO"
    ).split()

    def _table(self):
        return np.array([[row.count(c) for c in "DPSNO"] for row in self.FLEISS_1971])

    def test_reproduces_the_worked_example_of_fleiss_1971(self):
        from jnwb.spiking import fleiss_kappa
        table = self._table()
        assert table.shape == (30, 5) and set(table.sum(axis=1)) == {6}
        assert round(fleiss_kappa(table), 3) == 0.430

    def test_matches_an_independent_implementation(self):
        from jnwb.spiking import fleiss_kappa
        inter_rater = pytest.importorskip("statsmodels.stats.inter_rater")
        rng = np.random.default_rng(11)
        for table in (self._table(), rng.multinomial(9, [0.5, 0.3, 0.2], size=40)):
            assert fleiss_kappa(table) == pytest.approx(inter_rater.fleiss_kappa(table, method="fleiss"), abs=1e-12)

    def test_items_are_bins_and_raters_are_units(self):
        from jnwb.spiking import fleiss_kappa
        rng = np.random.default_rng(12)
        drive = rng.random(200) < 0.3                       # a shared state every unit mostly follows
        active = np.where(rng.random((8, 200)) < 0.9, drive, ~drive)
        k = active.sum(axis=0)
        kappa = fleiss_kappa(np.column_stack([active.shape[0] - k, k]))
        assert 0.5 < kappa < 0.8                            # 0.9 fidelity: (1 - 2*0.1)^2 = 0.64 expected
        indep = rng.random((8, 200)) < 0.3
        k = indep.sum(axis=0)
        assert abs(fleiss_kappa(np.column_stack([8 - k, k]))) < 0.05

    @pytest.mark.parametrize("bad", [
        np.array([[6, 0], [6, 0]]),                         # constant: kappa is 0/0
        np.array([[3, 3], [2, 3]]),                         # unequal rater counts
        np.array([[1, 0], [0, 1]]),                         # one rater per item
        np.array([[2.5, 3.5], [3, 3]]),                     # fractional
        np.array([[-1, 7], [3, 3]]),                        # negative
        np.array([6, 0]),                                   # not 2-D
    ])
    def test_refuses_an_undefined_or_malformed_table(self, bad):
        from jnwb.spiking import fleiss_kappa
        with pytest.raises(ValueError, match="fleiss_kappa"):
            fleiss_kappa(bad)


class TestSpikeCountCorrelation:
    def test_equals_the_mean_pairwise_pearson_r_of_binned_counts(self):
        from jnwb.spiking import spike_count_correlation
        rng = np.random.default_rng(21)
        common = np.sort(rng.uniform(0, 10, 300))
        units = [np.sort(np.concatenate([common[rng.random(300) < 0.5], rng.uniform(0, 10, 100)]))
                 for _ in range(4)]
        res = spike_count_correlation(units, (0.0, 10.0), bin_ms=50.0)
        edges = np.arange(0, 10.0 + 1e-9, 0.05)
        counts = np.array([np.histogram(u, edges)[0] for u in units])
        ref = [stats.pearsonr(counts[i], counts[j])[0] for i in range(4) for j in range(i + 1, 4)]
        assert res["mean_r"] == pytest.approx(np.mean(ref), abs=1e-12)
        assert res["n_pairs"] == 6 and res["n_excluded"] == 0 and res["n_bins"] == 200
        assert res["mean_r"] > 0.2

    def test_a_silent_unit_is_excluded_and_counted_not_scored_zero(self):
        from jnwb.spiking import spike_count_correlation
        rng = np.random.default_rng(22)
        a = np.sort(rng.uniform(0, 5, 200))
        units = [a, a + 1e-4, np.array([])]
        res = spike_count_correlation(units, (0.0, 5.0), bin_ms=100.0)
        assert res["n_excluded"] == 1 and list(res["excluded_units"]) == [2]
        assert res["n_pairs"] == 1 and res["mean_r"] > 0.9
        assert np.all(np.isnan(res["r"][2]))

    def test_the_bin_width_is_required(self):
        from jnwb.spiking import spike_count_correlation
        with pytest.raises(TypeError):
            spike_count_correlation([np.array([0.1])], (0.0, 1.0))
        with pytest.raises(ValueError, match="bin_ms"):
            spike_count_correlation([np.array([0.1])], (0.0, 1.0), bin_ms=0.0)
        with pytest.raises(ValueError, match="per-unit"):
            spike_count_correlation(np.array([0.1, 0.2]), (0.0, 1.0), bin_ms=10.0)

    def test_a_bare_list_of_spike_times_is_refused_not_split_into_units(self):
        from jnwb.spiking import fano_factor, spike_count_correlation
        train = [0.1, 0.5, 0.9, 1.3, 1.7]
        with pytest.raises(ValueError, match="per-unit"):
            spike_count_correlation(train, (0.0, 2.0), bin_ms=500.0)
        with pytest.raises(ValueError, match="per-unit"):
            fano_factor(train, [0.0, 1.0], (0.0, 1.0), summary="mean")
        units = [np.array([0.1, 0.9]), np.array([0.2, 1.3, 1.7])]
        res = spike_count_correlation((u for u in units), (0.0, 2.0), bin_ms=500.0)
        assert res["n_units"] == 2

    def test_fewer_than_three_bins_is_refused(self):
        from jnwb.spiking import spike_count_correlation
        units = [np.array([0.1, 0.2, 0.7]), np.array([0.3, 0.6, 0.9])]
        # With 2 bins every Pearson r is +1 or -1, so a mean of them measures nothing.
        with pytest.raises(ValueError, match=r"gives 2 bins.*at least 3"):
            spike_count_correlation(units, (0.0, 1.0), bin_ms=500.0)
        with pytest.raises(ValueError, match=r"gives 2 bins.*at least 3"):
            spike_count_correlation([], (0.0, 1.0), bin_ms=500.0)
        assert spike_count_correlation(units, (0.0, 0.9), bin_ms=300.0)["n_bins"] == 3


class TestFanoFactor:
    ONSETS = np.arange(200) * 2.0

    def test_poisson_units_give_one_and_regular_units_give_zero(self):
        from jnwb.spiking import fano_factor
        rng = np.random.default_rng(31)
        poisson = [np.concatenate([o + rng.uniform(0, 0.5, rng.poisson(8)) for o in self.ONSETS])
                   for _ in range(10)]
        res = fano_factor(poisson, self.ONSETS, (0.0, 0.5), summary="mean")
        assert res["fano"] == pytest.approx(1.0, abs=0.1)
        assert res["counts"].shape == (10, 200)
        regular = [np.concatenate([o + np.linspace(0.01, 0.49, 5) for o in self.ONSETS])]
        assert fano_factor(regular, self.ONSETS, (0.0, 0.5), summary="median")["fano"] == 0.0

    def test_is_per_unit_across_trials_not_of_the_population_sum(self):
        from jnwb.spiking import fano_factor
        # Two anti-correlated units: each alternates 0 and 4 spikes, the sum is always 4.
        a = np.concatenate([o + np.linspace(0.1, 0.4, 4) for o in self.ONSETS[0::2]])
        b = np.concatenate([o + np.linspace(0.1, 0.4, 4) for o in self.ONSETS[1::2]])
        res = fano_factor([a, b], self.ONSETS, (0.0, 0.5), summary="mean")
        var = np.var(np.tile([4.0, 0.0], 100), ddof=1)
        np.testing.assert_allclose(res["per_unit"], [var / 2.0, var / 2.0])
        assert res["fano"] == pytest.approx(var / 2.0)          # the population sum would give 0

    def test_a_zero_mean_unit_is_excluded_and_counted(self):
        from jnwb.spiking import fano_factor
        a = np.concatenate([o + np.array([0.1, 0.2]) for o in self.ONSETS[:10]])
        res = fano_factor([a, np.array([])], self.ONSETS[:10], (0.0, 0.5), summary="mean")
        assert res["n_excluded"] == 1 and np.isnan(res["per_unit"][1]) and res["fano"] == 0.0
        assert np.isnan(fano_factor([np.array([])], self.ONSETS[:3], (0.0, 0.5), summary="mean")["fano"])

    def test_the_window_is_right_open(self):
        from jnwb.spiking import fano_factor
        res = fano_factor([np.array([0.0, 0.5, 2.0, 2.5])], [0.0, 2.0], (0.0, 0.5), summary="mean")
        np.testing.assert_array_equal(res["counts"], [[1, 1]])

    # (spike, onset, window): the spike minus the onset is in the window, though adding the
    # onset to an edge rounds the other way for the last two.
    EDGE_CASES = [
        (0.3, 0.1, (0.0, 0.2)),     # 0.3 - 0.1 = 0.19999999999999998 < 0.2
        (0.3, 0.03, (0.27, 0.5)),   # exactly on w0: 0.3 - 0.03 == 0.27, but 0.03 + 0.27 > 0.3
        (0.06, 0.02, (0.0, 0.04)),  # 0.06 - 0.02 < 0.04, but 0.02 + 0.04 <= 0.06
    ]

    @pytest.mark.parametrize("spike, onset, window", EDGE_CASES)
    def test_every_onset_window_selects_by_spike_minus_onset(self, spike, onset, window):
        from jnwb._bins import onset_locked_counts
        from jnwb.connectivity import bin_spikes
        from jnwb.spiking import fano_factor
        w0, w1 = window
        assert w0 <= spike - onset < w1                     # the case is what it is named
        st = np.array([spike])
        fano = fano_factor([st], [onset, onset], window, summary="mean")["counts"]
        np.testing.assert_array_equal(fano, [[1, 1]])
        edges = np.array([w0, w1])
        assert onset_locked_counts(st, [onset], w0, w1, edges, 1.0, right_closed=False).sum() == 1
        assert bin_spikes(st, window_s=window, bin_size_ms=10.0, trial_starts=[onset]).sum() == 1

    @pytest.mark.parametrize("kw", [dict(summary="max"), dict(onsets_s=[1.0]), dict(window_s=(0.5, 0.5))])
    def test_refusals(self, kw):
        from jnwb.spiking import fano_factor
        args = dict(spike_times=[np.array([0.1])], onsets_s=[0.0, 1.0], window_s=(0.0, 0.5), summary="mean")
        args.update(kw)
        with pytest.raises(ValueError, match="fano_factor"):
            fano_factor(**args)
        with pytest.raises(TypeError):
            fano_factor([np.array([0.1])], [0.0, 1.0], (0.0, 0.5))


class TestNetworkBurstIndex:
    def _raster(self, rng):
        """Four units, 0.5 Hz background each, plus two 100 ms network bursts of 20 spikes per unit."""
        units = []
        for _ in range(4):
            bg = rng.uniform(0, 10, 5)
            burst = np.concatenate([rng.uniform(2.0, 2.1, 20), rng.uniform(6.0, 6.1, 20)])
            units.append(np.sort(np.concatenate([bg, burst])))
        return units

    def test_finds_the_planted_bursts_and_their_spike_fraction(self):
        from jnwb.spiking import network_burst_index
        units = self._raster(np.random.default_rng(41))
        res = network_burst_index(units, (0.0, 10.0), bin_ms=50.0, threshold_hz=200.0, min_duration_ms=100.0)
        assert res["n_bursts"] == 2 and res["n_spikes"] == 180
        np.testing.assert_allclose(res["bursts_s"][:, 0], [2.0, 6.0])
        assert res["bursts_s"][0, 1] - res["bursts_s"][0, 0] >= 0.1
        assert res["n_spikes_in_bursts"] >= 160
        assert res["burst_index"] == res["n_spikes_in_bursts"] / 180

    def test_the_minimum_duration_drops_short_runs(self):
        from jnwb.spiking import network_burst_index
        units = self._raster(np.random.default_rng(42))
        res = network_burst_index(units, (0.0, 10.0), bin_ms=50.0, threshold_hz=200.0, min_duration_ms=500.0)
        assert res["n_bursts"] == 0 and res["burst_index"] == 0.0 and res["bursts_s"].shape == (0, 2)

    def test_a_rate_or_run_exactly_at_its_bound_counts(self):
        from jnwb.spiking import network_burst_index
        # 7 spikes in 70 ms is 100 Hz, 99.99999999999999 in floating point.
        res = network_burst_index([np.linspace(0.001, 0.007, 7)], (0.0, 0.14), bin_ms=70.0,
                                  threshold_hz=100.0, min_duration_ms=0.0)
        assert res["n_bursts"] == 1 and res["burst_index"] == 1.0
        # Three 0.7 ms bins last 2.1 ms, 2.0999999999999996 in floating point.
        res = network_burst_index([np.array([0.0001, 0.0008, 0.0015])], (0.0, 0.0028), bin_ms=0.7,
                                  threshold_hz=1000.0, min_duration_ms=2.1)
        assert res["n_bursts"] == 1 and res["n_spikes_in_bursts"] == 3

    def test_no_spikes_is_nan_and_the_definition_is_required(self):
        from jnwb.spiking import network_burst_index
        res = network_burst_index([np.array([])], (0.0, 1.0), bin_ms=10.0, threshold_hz=5.0, min_duration_ms=0.0)
        assert np.isnan(res["burst_index"])
        with pytest.raises(TypeError):
            network_burst_index([np.array([0.1])], (0.0, 1.0), bin_ms=10.0, threshold_hz=5.0)
        with pytest.raises(ValueError, match="threshold_hz"):
            network_burst_index([np.array([0.1])], (0.0, 1.0), bin_ms=10.0, threshold_hz=0.0, min_duration_ms=0.0)
