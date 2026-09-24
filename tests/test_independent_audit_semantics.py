"""Regression tests from independent_audit_0.1.7 — discriminating probes per finding."""
from __future__ import annotations

import warnings

import numpy as np
import pytest

import jnwb
from jnwb.statistics import StatisticalAnalysis, shuffle_r2_ci


class TestMonteCarloPValueConvention:
    def test_permutation_test_uses_one_plus_k_over_b_plus_one(self):
        rng = np.random.default_rng(0)
        g1 = np.array([0.0, 0.1, 0.2, 0.3])
        g2 = np.array([1.0, 1.1, 1.2, 1.3])
        res = StatisticalAnalysis.permutation_test(g1, g2, n_permutations=99, rng=rng)
        obs = res["observed_difference"]
        combined = np.concatenate([g1, g2])
        n_x = len(g1)
        local_rng = np.random.default_rng(0)
        null = []
        for _ in range(99):
            idx = local_rng.permutation(len(combined))
            null.append(np.mean(combined[idx[:n_x]]) - np.mean(combined[idx[n_x:]]))
        k = int(np.sum(np.abs(null) >= abs(obs)))
        expected = (1 + k) / (99 + 1)
        assert res["pval"] == pytest.approx(expected)

    def test_shuffle_r2_ci_uses_one_plus_k_over_b_plus_one(self):
        y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1])
        y_score = np.linspace(0.0, 1.0, len(y_true))
        n_shuffle = 99
        out = shuffle_r2_ci(y_true, y_score, n_shuffle=n_shuffle, random_state=0)
        r2_obs = out["r2_observed"]
        rng = np.random.default_rng(0)
        null = []
        for _ in range(n_shuffle):
            y_perm = jnwb.permute_labels(y_true, scheme="global", rng=rng)
            r = np.corrcoef(y_perm, y_score)[0, 1]
            null.append(float(r ** 2))
        k = int(np.sum(np.asarray(null) >= r2_obs))
        assert out["p_val"] == pytest.approx((1 + k) / (n_shuffle + 1))

    def test_jrsa_p_from_null_uses_one_plus_k_over_b_plus_one(self):
        from jnwb.jrsa import _p_from_null

        p = _p_from_null(0.5, np.array([0.0, 0.0, 0.0, 0.0, 1.0]), "two-sided")
        # `float(p)`, not `float(p[0])`. `_p_from_null` returns a 0-d array, matching
        # `value`, `statistic` and `effect`; it used to return shape ``(1,)`` and the
        # subscript was unwrapping that stray axis. The assertion is about the
        # Monte-Carlo convention, not about `p` being indexable -- the sibling test
        # above asserts the same convention on a plain scalar.
        assert float(p) == pytest.approx(2.0 / 6.0)


class TestCompareGroupsPairedContract:
    def test_paired_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="paired=True"):
            StatisticalAnalysis.compare_groups([1, 2, 3, 4], [1, 2, 3], paired=True)

    def test_paired_equal_lengths_use_paired_test(self):
        res = StatisticalAnalysis.compare_groups([1, 2, 3], [2, 3, 4], paired=True)
        assert res["parametric"]["test"] == "paired_t_test"

    def test_paired_asymmetric_nan_pairwise_alignment(self):
        """Asymmetric NaNs must not shift pair alignment.
        True paired diff across complete pairs (idx 0 and 3) is exactly 0.0."""
        g1 = np.array([10.0, 100.0, np.nan, 20.0])
        g2 = np.array([10.0, np.nan, 200.0, 20.0])
        res = StatisticalAnalysis.compare_groups(g1, g2, paired=True, n_bootstrap=100)
        assert res["n1"] == 2
        assert res["n2"] == 2
        assert res["mean_diff_ci"]["observed_mean_diff"] == pytest.approx(0.0)
        # Every difference is zero, so the t statistic is 0/0: no test, not p = 1.
        assert np.isnan(res["parametric"]["pval"])
        assert np.isnan(res["parametric"]["effect_size"])
        assert np.isnan(res["parametric"]["df"])
        assert res["significant_parametric"] is False

    def test_paired_insufficient_finite_pairs_raises(self):
        """When fewer than 2 pairs are mutually finite, ValueError must be raised."""
        g1 = np.array([10.0, np.nan, np.nan])
        g2 = np.array([10.0, 20.0, 30.0])
        with pytest.raises(ValueError, match="at least two paired observations"):
            StatisticalAnalysis.compare_groups(g1, g2, paired=True)



class TestCrossModalComparisonAxes:
    def test_canonical_freq_time_trials_layout(self):
        rng = np.random.default_rng(0)
        tfr = rng.normal(size=(4, 20, 5))  # freq, time, trials
        spike = rng.normal(size=(20, 5))
        out = jnwb.cross_modal_comparison(tfr, spike)
        assert "error" not in out
        assert out["n_samples"] == 20

    def test_trials_time_freq_layout_raises(self):
        rng = np.random.default_rng(0)
        tfr = rng.normal(size=(5, 20, 4))  # trials, time, freq — wrong
        spike = rng.normal(size=(5, 20))
        with pytest.raises(ValueError, match="freq, time, trials"):
            jnwb.cross_modal_comparison(tfr, spike)


class TestSpikeMIBinGrid:
    def test_mi_bins_match_bin_spikes(self):
        from jnwb.connectivity import bin_spikes, spike_mutual_information

        rng = np.random.default_rng(0)
        s1 = np.sort(rng.uniform(0, 1, 50))
        s2 = np.sort(rng.uniform(0, 1, 50))
        window = (0.0, 1.05)  # 30 whole bins; a partial last bin is refused
        bin_ms = 35.0
        n_bins = bin_spikes(s1, window=window, bin_size_ms=bin_ms).shape[1]
        spike_mutual_information(s1, s2, time_window=window, bin_size_ms=bin_ms)
        bin_sec = bin_ms / 1000.0
        expected = int(round((window[1] - window[0]) / bin_sec))
        assert n_bins == expected


class TestGrangerAutoOrder:
    def test_auto_order_matches_select_optimal_lag(self):
        from jnwb.connectivity import granger, select_optimal_lag

        rng = np.random.default_rng(1)
        x = rng.normal(size=400)
        y = rng.normal(size=400)
        lag_xy = select_optimal_lag(x, y, max_lag=8, criterion="bic")
        res = jnwb.granger(
            x, y, order="auto", max_lag=8, criterion="bic", n_surrogates=0, detrend=None
        )
        assert res.params["order_x_to_y"] == lag_xy


class TestGrangerSpectralBandPValues:
    def test_per_band_surrogate_p_not_identical_when_bands_differ(self):
        from scipy import signal

        rng = np.random.default_rng(42)
        fs = 1000.0
        n = 512
        t = np.arange(n) / fs
        carrier = np.sin(2 * np.pi * 12.0 * t)
        x = carrier + 0.05 * rng.normal(size=n)
        y = np.roll(carrier, 8) + 0.05 * rng.normal(size=n)
        # High band is uncoupled broadband noise only
        x += signal.filtfilt(*signal.butter(4, [40 / (fs / 2), 70 / (fs / 2)], btype="band"), rng.normal(size=n))
        y += signal.filtfilt(*signal.butter(4, [40 / (fs / 2), 70 / (fs / 2)], btype="band"), rng.normal(size=n))
        res = jnwb.granger_spectral(
            x, y, fs=fs, order=4, n_surrogates=60, seed=0,
            bands={"low": (8.0, 16.0), "high": (40.0, 70.0)},
        )
        p_low = res.per_band["low"]["p_surrogate"]
        p_high = res.per_band["high"]["p_surrogate"]
        assert p_low is not None and p_high is not None
        assert p_low < p_high


class TestJrsaMetricIdentity:
    def test_renamed_granger_metric_rejects_legacy_alias(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(3, 80))
        with pytest.raises(ValueError, match="granger_ssr_ftest"):
            jnwb.jrsa(x, x, metric="granger", stats=False)

    def test_granger_ssr_ftest_returns_f_statistic(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(80,))
        y = np.roll(x, 2) + 0.1 * rng.normal(size=(80,))
        res = jnwb.jrsa(x, y, metric="granger_ssr_ftest", stats=False)
        assert res.value > 0

    def test_renamed_te_metric_rejects_legacy_alias(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(3, 80))
        with pytest.raises(ValueError, match="transfer_entropy_histogram_nats"):
            jnwb.jrsa(x, x, metric="transfer_entropy", stats=False)

    def test_transfer_entropy_histogram_nats_differs_from_connectivity_bits(self):
        rng = np.random.default_rng(42)
        x = rng.normal(size=(3, 50))
        y = rng.normal(size=(3, 50))
        jr = jnwb.jrsa(x, y, metric="transfer_entropy_histogram_nats", stats=False)
        te = jnwb.transfer_entropy(x, y, n_surrogates=0)
        assert not np.isclose(float(jr.value), float(te.x_to_y), rtol=0.05, atol=0.05)


class TestBandPowerNormalize:
    def test_normalize_without_baseline_raises(self):
        x = np.random.randn(1000)
        with pytest.raises(ValueError, match="baseline"):
            jnwb.band_power(x, fs=1000.0, freq_range=(10, 30), normalize=True, baseline=None)


class TestTransferEntropySymbolicMetadata:
    def test_symbolic_n_times_matches_embedded_length(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(2, 50))
        y = rng.normal(size=(2, 50))
        res = jnwb.transfer_entropy(x, y, estimator="symbolic", symbolic_order=3, n_surrogates=0)
        assert res.n_times == 50 - 3 + 1


class TestFinalAuditRecurrence:
    def test_granger_accepts_minimal_dof_order(self):
        rng = np.random.default_rng(1)
        x = rng.normal(size=20)
        y = rng.normal(size=20)
        res = jnwb.granger(x[None, :], y[None, :], order=6, n_surrogates=0, detrend=None)
        assert res.params["order_x_to_y"] == 6

    def test_granger_causality_undersampled_raises(self):
        x = np.random.default_rng(0).normal(size=8)
        y = np.random.default_rng(1).normal(size=8)
        with pytest.warns(DeprecationWarning):
            with pytest.raises(ValueError, match="fit_var_bivariate"):
                jnwb.granger_causality(x, y, order=5)

    def test_psth_bins_match_bin_spikes(self):
        from jnwb.analyzers import UnitAnalyzer
        from jnwb.connectivity import bin_spikes

        st = np.sort(np.random.default_rng(0).uniform(0, 0.6, 50))
        psth = UnitAnalyzer.psth(
            st, trial_onsets=np.array([0.3]), window_ms=(-100, 530), bin_size_ms=7,
        )
        bs = bin_spikes(st, window=(-0.1, 0.53), bin_size_ms=7)
        assert len(psth["psth"]) == bs.shape[-1]

    def test_psth_refuses_a_window_that_is_not_whole_bins(self):
        """600 ms at 7 ms made 86 bins 6.98 ms wide, each rate divided by 7 ms."""
        from jnwb.analyzers import UnitAnalyzer

        with pytest.raises(ValueError, match=r"window_ms=\(-100, 495\) or window_ms=\(-100, 502\)"):
            UnitAnalyzer.psth(np.array([0.31]), np.array([0.3]), bin_size_ms=7, window_ms=(-100, 500))

    def test_compare_groups_paired_single_pair_raises(self):
        with pytest.raises(ValueError, match="at least two paired"):
            StatisticalAnalysis.compare_groups([5.0], [7.0], paired=True)

    def test_spike_mutual_information_empty_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            jnwb.spike_mutual_information([], [0.1], (0.0, 1.0))

    def test_band_power_empty_freq_range_raises(self):
        sig = np.random.randn(1000)
        with pytest.raises(ValueError, match="no Welch bins"):
            jnwb.band_power(sig, fs=1000.0, freq_range=(600.0, 700.0), normalize=False)


class TestJrsaDtwAlignContract:
    def test_dtw_align_fails_loudly(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=(3, 40))
        y = rng.normal(size=(3, 40))
        with pytest.raises((ImportError, NotImplementedError), match="dtw"):
            jnwb.jrsa(x, y, metric="pearson", align="dtw", stats=False)


class TestGrangerCausalityDeprecation:
    def test_granger_causality_emits_deprecation_warning(self):
        rng = np.random.default_rng(0)
        x = rng.normal(size=200)
        y = rng.normal(size=200)
        with pytest.warns(DeprecationWarning, match="granger_causality"):
            jnwb.granger_causality(x, y, order=2)
