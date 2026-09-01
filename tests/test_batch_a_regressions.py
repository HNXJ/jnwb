import numpy as np
import pytest

import jnwb
from jnwb.onset_fitting import causal_exp_smooth, fit_exponential_onset, onset_model
from jnwb.statistics import StatisticalAnalysis
from omission.jnwb_ext.seed import stable_seed


class TestOnsetBoundStatus:
    def test_onset_lower_bound_censored(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=-50.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] == "lower"
        assert np.isclose(fit["t0"], 0.0, atol=1e-3)

    def test_onset_upper_bound_censored(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=450.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] == "upper"
        assert np.isclose(fit["t0"], 400.0, atol=1e-3)

    def test_onset_interior_unconstrained(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=100.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] is None
        assert np.isclose(fit["t0"], 100.0, atol=1e-1)

    def test_onset_exactly_at_lower_bound(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=0.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] == "lower"
        assert np.isclose(fit["t0"], 0.0, atol=1e-3)

    def test_onset_exactly_at_upper_bound(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=400.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] == "upper"
        assert np.isclose(fit["t0"], 400.0, atol=1e-3)

    def test_onset_just_above_lower_bound(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=25.0, tau=30.0, amplitude=20.0, baseline=5.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        assert fit["converged"] is True
        assert fit["bound_status"] is None
        assert np.isclose(fit["t0"], 25.0, atol=1e-1)

    def test_fitted_keys_and_values_preserved(self):
        t = np.arange(-100.0, 500.0, 5.0)
        rate = onset_model(t, t0=50.0, tau=25.0, amplitude=15.0, baseline=2.0)
        fit = fit_exponential_onset(t, rate, t0_bounds=(0.0, 400.0))
        expected_keys = {"t0", "tau", "amplitude", "baseline", "r2", "converged", "cost", "bound_status"}
        assert set(fit.keys()) == expected_keys
        assert isinstance(fit["t0"], float)
        assert isinstance(fit["tau"], float)
        assert isinstance(fit["amplitude"], float)
        assert isinstance(fit["baseline"], float)
        assert isinstance(fit["r2"], float)
        assert isinstance(fit["converged"], bool)
        assert isinstance(fit["cost"], float)


class TestStatisticsRNG:
    def test_unchanged_historical_default_determinism(self):
        data = np.array([1.2, 2.5, 3.1, 4.8, 5.2, 6.0])
        res1 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500)
        res2 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=500)
        assert res1["bootstrap_ci"] == res2["bootstrap_ci"]
        assert res1["bootstrap_std"] == res2["bootstrap_std"]

        res_perm1 = StatisticalAnalysis.permutation_test(data, data + 1.0, n_permutations=500)
        res_perm2 = StatisticalAnalysis.permutation_test(data, data + 1.0, n_permutations=500)
        assert res_perm1["pval"] == res_perm2["pval"]

    def test_global_rng_state_untouched(self):
        np.random.seed(98765)
        state_before = np.random.get_state()

        data = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=100)
        StatisticalAnalysis.permutation_test(data, data * 1.5, n_permutations=100)
        StatisticalAnalysis.compare_groups(data, data + 2.0, n_bootstrap=100)

        state_after = np.random.get_state()
        assert state_before[0] == state_after[0]
        assert np.array_equal(state_before[1], state_after[1])
        assert state_before[2] == state_after[2]

    def test_custom_independent_generators(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        rng1 = np.random.default_rng(100)
        rng2 = np.random.default_rng(200)

        res1 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=rng1)
        res2 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=rng2)
        assert res1["bootstrap_std"] != res2["bootstrap_std"]

        res3 = StatisticalAnalysis.bootstrap_ci(data, n_bootstrap=1000, rng=np.random.default_rng(100))
        assert res1["bootstrap_std"] == res3["bootstrap_std"]

    def test_invalid_rng_type_raises_type_error(self):
        data = np.array([1.0, 2.0, 3.0])
        with pytest.raises(TypeError, match="rng must be an instance of np.random.Generator"):
            StatisticalAnalysis.bootstrap_ci(data, rng=42)

        with pytest.raises(TypeError, match="rng must be an instance of np.random.Generator"):
            StatisticalAnalysis.permutation_test(data, data, rng="not_an_rng")

        with pytest.raises(TypeError, match="rng must be an instance of np.random.Generator"):
            StatisticalAnalysis.compare_groups(data, data, rng=123)


class TestArtifactDetectionPublicAPI:
    def test_artifact_functions_in_jnwb_all(self):
        expected_exports = [
            "channel_correlation_matrix",
            "bad_channels_from_correlation",
            "trial_correlation_matrix",
            "bad_trials_single_channel",
            "consensus_bad_trials",
        ]
        for name in expected_exports:
            assert name in jnwb.__all__, f"{name} not in jnwb.__all__"
            assert hasattr(jnwb, name), f"jnwb has no attribute {name}"

    def test_artifact_functions_smoke_run(self):
        rng = np.random.default_rng(0)
        data = rng.standard_normal((4, 100))
        data[3] = data[0] * 0.01 + rng.standard_normal(100) * 10.0

        corr = jnwb.channel_correlation_matrix(data)
        assert corr.shape == (4, 4)
        assert np.allclose(np.diag(corr), 1.0)

        bad, summary, z = jnwb.bad_channels_from_correlation(corr, z_thresh=2.0)
        assert bad.shape == (4,)
        assert summary.shape == (4,)

        trials = rng.standard_normal((5, 50))
        t_corr = jnwb.trial_correlation_matrix(trials)
        assert t_corr.shape == (5, 5)

        t_bad, t_z, a_z = jnwb.bad_trials_single_channel(trials)
        assert t_bad.shape == (5,)

        flags = np.array([[True, False], [True, True], [False, False]])
        cons_bad, frac = jnwb.consensus_bad_trials(flags, min_frac_channels=0.5)
        assert cons_bad.shape == (2,)


class TestCausalExpSmoothLatency:
    def test_impulse_centroid_delay_scales_with_tau(self):
        bin_ms = 1.0
        n_pts = 1000
        impulse = np.zeros(n_pts)
        impulse[100] = 1.0

        for tau in [20.0, 40.0, 60.0]:
            smoothed = causal_exp_smooth(impulse, bin_ms=bin_ms, tau_ms=tau)
            t_axis = np.arange(n_pts) * bin_ms
            com = np.sum(t_axis * smoothed) / np.sum(smoothed)
            com_delay = com - 100.0 * bin_ms
            # Compare with exact discrete kernel centroid
            t_filter = np.arange(0, 5 * tau, bin_ms)
            h = np.exp(-t_filter / tau)
            h /= h.sum()
            expected_com = np.sum(t_filter * h)
            assert np.isclose(com_delay, expected_com, atol=1e-5)
            assert np.isclose(com_delay, tau, rtol=0.10)

    def test_step_response_50_pct_rise_scales_with_tau(self):
        bin_ms = 0.5
        n_pts = 2000
        step = np.zeros(n_pts)
        step_onset = 200
        step[step_onset:] = 1.0

        for tau in [30.0, 50.0]:
            smoothed = causal_exp_smooth(step, bin_ms=bin_ms, tau_ms=tau)
            idx_50 = np.where(smoothed >= 0.5)[0][0]
            delay_50 = (idx_50 - step_onset) * bin_ms
            expected_50 = tau * np.log(2.0)
            assert np.isclose(delay_50, expected_50, atol=bin_ms * 2)

    def test_sampling_interval_invariance(self):
        tau = 30.0
        for bin_ms in [1.0, 2.0, 5.0]:
            step = np.zeros(int(1000 / bin_ms))
            onset_idx = int(200 / bin_ms)
            step[onset_idx:] = 1.0
            smoothed = causal_exp_smooth(step, bin_ms=bin_ms, tau_ms=tau)
            idx_50 = np.where(smoothed >= 0.5)[0][0]
            delay_50 = (idx_50 - onset_idx) * bin_ms
            assert abs(delay_50 - tau * np.log(2.0)) <= bin_ms * 1.5


class TestOmissionStableSeeds:
    def test_stable_seed_deterministic_same_process(self):
        s1 = stable_seed("alpha", 50.0, 3)
        s2 = stable_seed("alpha", 50.0, 3)
        assert s1 == s2
        assert isinstance(s1, int)
        assert 0 <= s1 < 2**31

        u1 = stable_seed("AAAB", 2)
        u2 = stable_seed("AAAB", 2)
        assert u1 == u2
        assert isinstance(u1, int)
        assert 0 <= u1 < 2**31

    def test_distinct_representative_inputs(self):
        s1 = stable_seed("alpha", 50.0, 0)
        s2 = stable_seed("alpha", 50.0, 1)
        s3 = stable_seed("beta", 50.0, 0)
        assert len({s1, s2, s3}) == 3

    def test_representative_input_types(self):
        # string, float, integer, and tuple-like inputs
        res_str = stable_seed("AAAB")
        res_flt = stable_seed(50.0)
        res_int = stable_seed(42)
        res_tup = stable_seed("stem_01", "pupil_raw", "v1_theta")
        res_mix = stable_seed("cond_X", 3, 12.5, "R")

        for r in [res_str, res_flt, res_int, res_tup, res_mix]:
            assert isinstance(r, int)
            assert 0 <= r < 2**31

        # All distinct representative inputs yield distinct seeds (not claiming collision-freedom)
        assert len({res_str, res_flt, res_int, res_tup, res_mix}) == 5

    def test_cross_process_invariance_across_types(self):
        """Verify cross-process determinism for string, float, integer, and tuple-like inputs.

        Asserts that seeds are identical across distinct Python interpreter invocations
        with varying PYTHONHASHSEED values ('0', '42', '99999', 'random').
        Note: does NOT claim mathematical collision-freedom (CRC32 is 32-bit).
        """
        import json
        import os
        import subprocess
        import sys

        test_cases = [
            ("AAAB",),
            (50.0,),
            (42,),
            ("stem_01", "pupil_raw", "v1_theta"),
            ("cond_X", 3, 12.5, "R"),
        ]

        expected = [stable_seed(*args) for args in test_cases]

        for seed_env in ["0", "42", "99999", "random"]:
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed_env

            code = (
                "import json; from omission.jnwb_ext.seed import stable_seed; "
                "cases = [('AAAB',), (50.0,), (42,), ('stem_01', 'pupil_raw', 'v1_theta'), ('cond_X', 3, 12.5, 'R')]; "
                "print(json.dumps([stable_seed(*args) for args in cases]))"
            )
            res = subprocess.check_output([sys.executable, "-c", code], env=env, text=True)
            child_seeds = json.loads(res.strip())
            assert child_seeds == expected, f"Cross-process mismatch under PYTHONHASHSEED={seed_env}"
