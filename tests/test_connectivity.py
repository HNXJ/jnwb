"""Unit tests for jnwb.connectivity -- functional connectivity estimators.

Covers the public-import surface plus one smoke test per estimator. Deeper behavioral coverage
may live in downstream project test suites that call the same jnwb functions.
"""
from __future__ import annotations

import ast
import pathlib
import warnings

import numpy as np
import pytest
from scipy import stats

import jnwb

from jnwb.connectivity import (
    spike_mutual_information,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    granger_causality,
    network_topology,
    DirectedResult,
    as_trials,
    bin_spikes,
    granger,
    granger_spectral,
    phase_slope_index,
    transfer_entropy,
    directed_connectivity,
    directed_network,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        for name, obj in (
            ("spike_mutual_information", spike_mutual_information),
            ("binary_occupancy_mutual_information", binary_occupancy_mutual_information),
            ("spike_count_mutual_information", spike_count_mutual_information),
            ("granger_causality", granger_causality),
            ("network_topology", network_topology),
            ("DirectedResult", DirectedResult),
            ("as_trials", as_trials),
            ("bin_spikes", bin_spikes),
            ("granger", granger),
            ("granger_spectral", granger_spectral),
            ("phase_slope_index", phase_slope_index),
            ("transfer_entropy", transfer_entropy),
            ("directed_connectivity", directed_connectivity),
            ("directed_network", directed_network),
        ):
            assert getattr(jnwb, name) is obj

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("spike_mutual_information", "binary_occupancy_mutual_information",
                     "spike_count_mutual_information", "granger_causality", "network_topology",
                     "DirectedResult", "as_trials", "bin_spikes", "granger", "granger_spectral",
                     "phase_slope_index", "transfer_entropy", "directed_connectivity",
                     "directed_network"):
            assert name in jnwb.__all__

class TestSpikeMutualInformation:
    def test_identical_spike_trains_have_positive_mi(self):
        rng = np.random.default_rng(0)
        spikes = np.sort(rng.uniform(0, 5, 200))
        mi = spike_mutual_information(spikes, spikes, time_window=(0.0, 5.0), bin_size_ms=10.0)
        assert mi > 0

    def test_binary_occupancy_and_spike_count_aliases_delegate(self):
        rng = np.random.default_rng(1)
        s1 = np.sort(rng.uniform(0, 5, 100))
        s2 = np.sort(rng.uniform(0, 5, 100))
        mi_bo = binary_occupancy_mutual_information(s1, s2, time_window=(0.0, 5.0))
        mi_full = spike_mutual_information(s1, s2, time_window=(0.0, 5.0), estimator="binary_occupancy")
        assert mi_bo == pytest.approx(mi_full)
        mi_sc = spike_count_mutual_information(s1, s2, time_window=(0.0, 5.0))
        mi_full_sc = spike_mutual_information(s1, s2, time_window=(0.0, 5.0), estimator="spike_count")
        assert mi_sc == pytest.approx(mi_full_sc)


class TestGrangerCausality:
    def test_x_drives_y_shows_asymmetric_causality(self):
        rng = np.random.default_rng(2)
        n = 2000
        x = rng.standard_normal(n)
        y = np.zeros(n)
        for t in range(2, n):
            y[t] = 0.6 * x[t - 1] + 0.1 * rng.standard_normal()
        result = granger_causality(y, x, order=3)
        assert "F_2_to_1" in result
        assert "F_1_to_2" in result


class TestNetworkTopology:
    def test_thresholds_and_counts_edges(self):
        adj = np.array([[0.0, 0.5, 0.0], [0.5, 0.0, 0.0], [0.0, 0.0, 0.0]])
        result = network_topology(adj, threshold=0.3)
        assert result["n_edges"] == 2


class TestAsTrials:
    def test_normalizes_1d_2d_and_list_input(self):
        assert as_trials(np.arange(10.0)).shape == (1, 10)
        assert as_trials(np.zeros((4, 100))).shape == (4, 100)
        assert as_trials([np.arange(10.0), np.arange(8.0)]).shape == (2, 8)


class TestBinSpikes:
    def test_returns_trials_by_bins_shape(self):
        spike_times = [np.array([0.1, 0.2, 0.35]), np.array([0.05, 0.4])]
        counts = bin_spikes(spike_times, window=(0.0, 0.5), bin_size_ms=100.0)
        assert counts.shape == (2, 5)

    def test_temporal_coordinates_and_bin_centers(self):
        spike_times = [np.array([0.1, 0.25])]
        counts, centers = bin_spikes(
            spike_times, window=(0.0, 0.5), bin_size_ms=100.0, return_centers=True
        )
        assert counts.shape == (1, 5)
        # Bins: [0, 0.1), [0.1, 0.2), [0.2, 0.3), [0.3, 0.4), [0.4, 0.5)
        # Centers: 0.05, 0.15, 0.25, 0.35, 0.45
        expected_centers = np.array([0.05, 0.15, 0.25, 0.35, 0.45])
        np.testing.assert_allclose(centers, expected_centers, rtol=1e-12)

    def test_right_open_boundary_contract(self):
        # Window: [0.0, 0.3) with 100ms bins -> 3 bins: [0, 0.1), [0.1, 0.2), [0.2, 0.3)
        # Spikes:
        # -0.01: outside left (< t0) -> excluded
        #  0.00: exactly on t0 -> bin 0
        #  0.10: exactly on edge 1 -> bin 1 (not bin 0)
        #  0.29: strictly inside bin 2 -> bin 2
        #  0.30: exactly on t1 -> excluded (right-open boundary contract)
        #  0.35: outside right (> t1) -> excluded
        spikes = np.array([-0.01, 0.0, 0.10, 0.29, 0.30, 0.35])

        # Test case 1: per-trial list
        counts_list = bin_spikes([spikes], window=(0.0, 0.3), bin_size_ms=100.0)
        np.testing.assert_array_equal(counts_list, [[1.0, 1.0, 1.0]])

        # Test case 2: continuous spikes with trial_starts = [0.0]
        counts_trial = bin_spikes(
            spikes, window=(0.0, 0.3), bin_size_ms=100.0, trial_starts=[0.0]
        )
        np.testing.assert_array_equal(counts_trial, [[1.0, 1.0, 1.0]])

        # Test case 3: continuous spikes with non-zero trial_start, interior points
        interior_spikes = np.array([5.05, 5.15, 5.25])
        counts_offset = bin_spikes(
            interior_spikes, window=(0.0, 0.3), bin_size_ms=100.0, trial_starts=[5.0]
        )
        np.testing.assert_array_equal(counts_offset, [[1.0, 1.0, 1.0]])

    def test_output_rate_scaling(self):
        # 2 spikes in bin 0 (width = 0.05s = 50ms) -> rate = 2 / 0.05 = 40.0 Hz
        spikes = [np.array([0.01, 0.02])]
        rates = bin_spikes(spikes, window=(0.0, 0.2), bin_size_ms=50.0, output="rate")
        assert rates.shape == (1, 4)
        assert rates[0, 0] == pytest.approx(40.0)
        assert rates[0, 1] == pytest.approx(0.0)

    def test_input_validation(self):
        with pytest.raises(ValueError, match="output must be 'count' or 'rate'"):
            bin_spikes([np.array([0.1])], window=(0.0, 0.5), output="invalid")
        with pytest.raises(ValueError, match="window_s must satisfy end > start"):
            bin_spikes([np.array([0.1])], window=(0.5, 0.5))
        with pytest.raises(ValueError, match="yields 1 bins; need >= 2"):
            bin_spikes([np.array([0.1])], window=(0.0, 0.1), bin_size_ms=100.0)

    STEADY_1KHZ = np.arange(0.0005, 3.0, 0.001)  # one spike per ms, off the bin edges

    def test_a_steady_train_reads_its_rate_in_every_bin_of_a_whole_bin_window(self):
        # 0.3 / 0.01 is 29.999999999999996 in floating point, and is still 30 whole bins.
        rates = bin_spikes(self.STEADY_1KHZ, window_s=(0.0, 0.3), bin_size_ms=10.0, output="rate")
        assert rates.shape == (1, 30)
        np.testing.assert_allclose(rates, 1000.0)
        # An absolute window hours into a recording carries rounding beyond 1e-9 bins:
        # this span is 99.99999999854481 bins in floating point.
        far = bin_spikes(10000.0 + self.STEADY_1KHZ, window_s=(10000.003, 10000.103),
                         bin_size_ms=1.0, output="rate")
        assert far.shape == (1, 100)
        np.testing.assert_allclose(far, 1000.0)

    @pytest.mark.parametrize("end", [0.305, 0.304])
    def test_a_window_that_is_not_whole_bins_is_refused(self, end):
        """Rounded up, the last bin held part of its width and read low as a rate; rounded
        down, the spikes between the last edge and the window end were dropped."""
        with pytest.raises(ValueError, match=r"window_s=\(0, 0\.3\) or window_s=\(0, 0\.31\)"):
            bin_spikes(self.STEADY_1KHZ, window_s=(0.0, end), bin_size_ms=10.0, output="rate")
        with pytest.raises(ValueError, match=r"window_s=\(-0\.1, 0\.2\) or window_s=\(-0\.1, 0\.21\)"):
            bin_spikes(self.STEADY_1KHZ, window_s=(-0.1, end - 0.1), bin_size_ms=10.0,
                       trial_starts=[1.0, 2.0])

    def test_mutual_information_refuses_at_its_own_boundary(self):
        s = np.sort(np.random.default_rng(0).uniform(0.0, 1.0, 50))
        with pytest.raises(ValueError, match=r"spike_mutual_information: time_window_s="):
            spike_mutual_information(s, s, time_window_s=(0.0, 1.0), bin_size_ms=35.0)

    def test_mutual_information_bins_a_boundary_spike_as_bin_spikes_does(self):
        """A spike on the window end is outside the right-open window, so these two trains
        occupy the same bins. A last bin closed on the right counted it and lowered the MI."""
        a = np.array([0.05, 0.15, 0.5])
        b = np.array([0.05, 0.15])
        mi = spike_mutual_information(a, b, time_window_s=(0.0, 0.5), bin_size_ms=100.0)
        assert mi == pytest.approx(
            spike_mutual_information(b, b, time_window_s=(0.0, 0.5), bin_size_ms=100.0))


class TestGranger:
    def test_x_leads_y_gives_positive_net(self):
        rng = np.random.default_rng(3)
        n_trials, n_times = 20, 300
        x = rng.standard_normal((n_trials, n_times))
        y = np.zeros_like(x)
        y[:, 1:] = 0.7 * x[:, :-1] + 0.2 * rng.standard_normal((n_trials, n_times - 1))
        result = granger(x, y, order=3)
        assert isinstance(result, DirectedResult)
        assert result.x_to_y > result.y_to_x

    def test_malformed_aic_structure_warns_instead_of_silent_fallback(self):
        from unittest.mock import patch
        from jnwb.jrsa import _granger

        class _BadModel:
            @property
            def aic(self):
                raise AttributeError("no aic on mock statsmodels result")

        fake_res = {
            1: ({"ssr_ftest": (1.0, 0.05, 2.0)}, (None, _BadModel(), None)),
        }
        x = np.linspace(0, 1, 50)
        y = np.roll(x, 1)
        with patch("statsmodels.tsa.stattools.grangercausalitytests", return_value=fake_res):
            with pytest.warns(UserWarning, match="Granger AIC extraction failed"):
                _granger(x, y, max_lag=1)

    def test_granger_null_non_negative_ml_variance(self):
        """Granger causality using ML residual variance RSS/N is non-negative under plain OLS (0.2.3-REV-07)."""
        rng = np.random.default_rng(42)
        # 10 independent noise trials under true null
        x = rng.standard_normal((10, 500))
        y = rng.standard_normal((10, 500))

        result = granger(x, y, order=3, n_surrogates=0, ridge=0.0)
        assert result.x_to_y >= 0.0, f"Expected non-negative GC under plain OLS, got {result.x_to_y}"
        assert result.y_to_x >= 0.0, f"Expected non-negative GC under plain OLS, got {result.y_to_x}"
        assert result.x_to_y == pytest.approx(0.0, abs=0.01)
        assert result.y_to_x == pytest.approx(0.0, abs=0.01)



class TestPhaseSlopeIndex:
    def test_antisymmetric_under_swap(self):
        rng = np.random.default_rng(4)
        t = np.arange(0, 2, 1.0 / 1000.0)
        x = np.sin(2 * np.pi * 20 * t) + 0.1 * rng.standard_normal(len(t))
        lag_samples = 5
        y = np.roll(x, lag_samples)
        fwd = phase_slope_index(x, y, fs=1000.0, bands=(14, 30), nperseg=256)
        rev = phase_slope_index(y, x, fs=1000.0, bands=(14, 30), nperseg=256)
        assert fwd.net == pytest.approx(-rev.net, abs=1e-9)

    def test_multiband_psi_omnibus_pvalue(self):
        """Multi-band PSI computes omnibus top-level p-value rather than extracting first band (0.2.3-REV-08)."""
        from scipy import signal, stats
        rng = np.random.default_rng(42)
        n = 4000
        # Filtered band-limited signal in gamma (55-75 Hz) with 5 ms delay
        raw = rng.standard_normal(n)
        sos = signal.butter(4, [55.0, 75.0], btype="bandpass", fs=1000.0, output="sos")
        gamma_sig = signal.sosfiltfilt(sos, raw)
        x = gamma_sig + 0.05 * rng.standard_normal(n)
        y = np.roll(gamma_sig, 5) + 0.05 * rng.standard_normal(n)

        # Multi-band: theta (4-8 Hz, pure noise) and gamma (55-75 Hz, strong lead)
        bands = {"theta": (4.0, 8.0), "gamma": (55.0, 75.0)}
        res = phase_slope_index(x, y, fs=1000.0, bands=bands, n_surrogates=0)

        assert res.diagnostics["p_is_omnibus"] is True
        p_theta = float(2 * stats.norm.sf(abs(res.per_band["theta"]["z"])))
        p_gamma = float(2 * stats.norm.sf(abs(res.per_band["gamma"]["z"])))

        # Theta has no lead (p > 0.1), Gamma has massive lead (p < 1e-10)
        assert p_theta > 0.1
        assert p_gamma < 1e-10

        # Top-level p_x_to_y must NOT be equal to the first band (theta) p-value
        assert res.p_x_to_y != pytest.approx(p_theta, abs=1e-4)
        assert res.p_x_to_y < 0.05, f"Omnibus p must be significant, got {res.p_x_to_y}"



class TestTransferEntropy:
    def test_x_drives_y_gives_positive_x_to_y(self):
        rng = np.random.default_rng(5)
        n = 2000
        x = rng.integers(0, 4, n)
        y = np.zeros(n, dtype=int)
        y[1:] = x[:-1]
        result = transfer_entropy(x.astype(float), y.astype(float), k=1, l=1, delay=1,
                                   bins=4, n_surrogates=20, seed=0)
        assert isinstance(result, DirectedResult)

    def test_the_symbolic_estimator_is_refused_and_points_to_quantile(self):
        """06-202: two noisy copies of one white source tested significant both ways under
        it. The generic unknown-estimator error also names 'quantile', so the match
        requires the reason as well."""
        x = np.random.default_rng(0).normal(size=(2, 200))
        with pytest.raises(ValueError, match=r"not calibrated under zero-lag mixing.*"
                                             r"estimator='quantile'"):
            transfer_entropy(x[0], x[1], estimator="symbolic", n_surrogates=0)


class TestDirectedConnectivityAndNetwork:
    def test_directed_connectivity_dispatches_by_method(self):
        rng = np.random.default_rng(6)
        x = rng.standard_normal((10, 200))
        y = rng.standard_normal((10, 200))
        result = directed_connectivity(x, y, method="granger", order=2)
        assert isinstance(result, DirectedResult)

    def test_directed_network_returns_all_pairs(self):
        rng = np.random.default_rng(7)
        signals = {
            "A": rng.standard_normal((5, 100)),
            "B": rng.standard_normal((5, 100)),
            "C": rng.standard_normal((5, 100)),
        }
        result = directed_network(signals, method="granger", order=2, fdr=False)
        assert "labels" in result
        assert set(result["labels"]) == {"A", "B", "C"}

    def test_directed_network_draws_a_generator_once_per_pair_up_front(self):
        """06-203: a Generator copied into each worker would replay one stream, so the
        surrogates would depend on n_jobs. Each pair gets an int seed drawn before any
        worker starts, in pair order, and records it."""
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "ABC"}
        res = directed_network(signals, method="granger", order=1, n_surrogates=5,
                               fdr=False, rng=np.random.default_rng(3))
        recorded = [r.params["surrogate_seed_entropy"] for r in res["results"].values()]
        assert recorded == np.random.default_rng(3).integers(0, 2**63 - 1, size=3).tolist()

    def test_directed_network_refuses_two_different_generators(self):
        """`granger(rng=a, seed=b)` raises; the network must not hide the contradiction by
        drawing its per-pair seeds from one of them."""
        rng = np.random.default_rng(8)
        signals = {k: rng.standard_normal((3, 120)) for k in "AB"}
        with pytest.raises(ValueError, match="Conflicting values provided to directed_network"):
            directed_network(signals, method="granger", order=1, n_surrogates=5,
                             rng=np.random.default_rng(1), seed=np.random.default_rng(2))


class TestFewTrialSurrogates:
    """Below 7 trials the surrogates circularly shift each trial instead of re-pairing
    trials: 3 trials admit 2 derangements, so the re-pairing null held two values and
    independent noise tested significant at 0.05 in 30 of 80 p-values here (bc04a791)."""

    def test_independent_noise_at_three_trials_rejects_near_alpha(self):
        ps = []
        for rep in range(40):
            g = np.random.default_rng(rep)
            x, y = g.normal(size=(3, 200)), g.normal(size=(3, 200))
            res = granger(x, y, order=1, n_surrogates=19, rng=rep)
            ps += [res.p_x_to_y, res.p_y_to_x]
        assert np.mean(np.asarray(ps) <= 0.05) <= 0.08

    @pytest.mark.parametrize("n_trials,scheme", [(6, "circular_shift"), (7, "trial_permutation")])
    def test_every_surrogate_consumer_records_the_scheme(self, n_trials, scheme):
        g = np.random.default_rng(0)
        x, y = g.normal(size=(n_trials, 128)), g.normal(size=(n_trials, 128))
        for res in (
            granger(x, y, order=1, n_surrogates=2),
            granger_spectral(x, y, fs=100.0, order=1, n_freqs=16, n_surrogates=2),
            phase_slope_index(x, y, fs=100.0, bands=(5.0, 30.0), n_surrogates=2),
            transfer_entropy(x, y, n_surrogates=2),
        ):
            assert res.params["surrogate_scheme"] == scheme, res.method
        assert granger(x, y, order=1).params["surrogate_scheme"] is None

    def test_seven_trials_keep_the_null_they_had(self):
        """Pinned at bc04a791, before the threshold moved from 3 to 7."""
        g = np.random.default_rng(11)
        x = g.normal(size=(7, 200))
        y = 0.3 * np.roll(x, 1, axis=1) + g.normal(size=(7, 200))
        res = granger(x, y, order=1, n_surrogates=19, rng=0)
        sur = res.diagnostics["surrogates"]
        assert (res.p_x_to_y, res.p_y_to_x, res.p_net) == (0.05, 0.7, 0.05)
        assert sur["null_mean_x_to_y"] == 0.00035468224425054724
        assert sur["null_mean_y_to_x"] == 0.0006370039765307248


class TestCrossAreaCoherenceContract:
    """0.2.4-09: out-of-contract input must fail loudly, not plausibly.

    Both cases below previously produced a result a caller could not distinguish from a
    real measurement, or an error naming neither the argument nor the contract.
    """

    def _bands(self):
        return {"beta": (15.0, 30.0)}

    @pytest.mark.parametrize("shape", [(6, 2048), (2, 2048), (1, 2048), (3, 512)])
    def test_two_dimensional_input_is_rejected(self, shape):
        rng = np.random.default_rng(0)
        a = rng.normal(size=shape)
        b = rng.normal(size=shape)
        with pytest.raises(ValueError, match=r"must be a 1-D time series"):
            jnwb.cross_area_coherence(
                a, b, fs=1000.0, freq_bands=self._bands(), n_surrogates=3
            )

    def test_rejection_names_the_offending_argument_and_shape(self):
        rng = np.random.default_rng(0)
        good = rng.normal(size=1024)
        bad = rng.normal(size=(4, 1024))
        with pytest.raises(ValueError) as excinfo:
            jnwb.cross_area_coherence(
                good, bad, fs=1000.0, freq_bands=self._bands(), n_surrogates=3
            )
        message = str(excinfo.value)
        assert "lfp_area2" in message
        assert "(4, 1024)" in message

    def test_one_dimensional_paired_input_still_computes(self):
        rng = np.random.default_rng(0)
        a = rng.normal(size=4096)
        b = rng.normal(size=4096)
        out = jnwb.cross_area_coherence(
            a, b, fs=1000.0, freq_bands=self._bands(), n_surrogates=5
        )
        assert np.asarray(out["coherence_spectrum"]).ndim == 1
        assert np.asarray(out["frequencies"]).size == np.asarray(out["coherence_spectrum"]).size
        # Bounded in [0, 1]; the upper compare carries float slack because the
        # estimator can land exactly on 1.0 (see the segment-count caveat below).
        assert 0.0 <= out["peak_coherence_value"] <= 1.0 + 1e-9


class TestStationarityDiagnosticIsCalibrated:
    """`_adf_pvalue` drives `stationarity_ok` and `ok_for_interpretation` on every Granger
    result, so a miscalibrated one silently certifies non-stationary series as safe.

    It used to compare the Dickey-Fuller t-statistic to the normal distribution. The DF
    null is shifted well to the left (5% critical value near -2.86 with a constant, not
    -1.645), so it certified roughly 46-48% of pure random walks as stationary while its
    docstring called itself conservative.
    """

    def test_random_walks_are_not_certified_stationary(self):
        from jnwb.connectivity import _adf_pvalue

        rng = np.random.default_rng(0)
        for n in (200, 500):
            p = np.array([_adf_pvalue(np.cumsum(rng.standard_normal(n))) for _ in range(600)])
            rate = float(np.mean(p <= 0.05))
            assert rate <= 0.10, (
                f"n={n}: {rate:.3f} of pure random walks certified stationary; a calibrated "
                f"test rejects the unit root about 5% of the time under H0"
            )

    def test_a_stationary_series_is_still_detected(self):
        """The repair must not buy calibration by refusing to reject anything."""
        from jnwb.connectivity import _adf_pvalue

        rng = np.random.default_rng(1)
        hits = 0
        for _ in range(100):
            e = rng.standard_normal(500)
            y = np.zeros(500)
            for t in range(1, 500):
                y[t] = 0.5 * y[t - 1] + e[t]
            hits += _adf_pvalue(y) <= 0.05
        assert hits >= 90, f"only {hits}/100 stationary AR(1) series rejected the unit root"

    def test_degenerate_series_report_nan_rather_than_a_number(self):
        from jnwb.connectivity import _adf_pvalue

        assert np.isnan(_adf_pvalue(np.arange(5.0)))
        assert np.isnan(_adf_pvalue(np.ones(100)))


class TestTransferEntropyReportsDegenerateDiscretization:
    """The undersampling check could not see the opposite failure. A discretization that
    collapses produces FEWER joint states, so samples_per_joint_state goes UP and the check
    stays quiet. Quantile edges on a sparse series are the common case: spike counts
    averaging 0.05-0.1 per bin are almost all zero, so every quantile edge lands on 0 and
    the series maps to a single symbol. TE is then identically 0 by construction, and it
    was reported as 0.0000 bits, p = 1.0, ok_for_interpretation=True, no warnings -- on
    data where X drives Y at lag 1.
    """

    @staticmethod
    def _coupled(rate, n=2000, seed=0):
        rng = np.random.default_rng(seed)
        x = rng.poisson(rate, size=n).astype(float)
        y = np.zeros_like(x)
        y[1:] = x[:-1] + rng.poisson(rate, size=n - 1)
        return x, y

    @pytest.mark.parametrize("rate", [0.05, 0.1])
    def test_a_collapsed_discretization_is_not_certified_interpretable(self, rate):
        res = transfer_entropy(*self._coupled(rate), n_surrogates=50)
        d = res.diagnostics
        assert res.x_to_y == 0.0
        assert d["n_realized_states_x"] == 1 and d["n_realized_states_y"] == 1
        assert d["ok_for_interpretation"] is False
        assert any("degenerate_discretization" in w for w in d["warnings"])

    def test_a_partially_collapsed_discretization_is_flagged(self):
        res = transfer_entropy(*self._coupled(0.3), n_surrogates=50)
        d = res.diagnostics
        assert d["n_realized_states_x"] < 4
        assert any("discretization_collapsed" in w for w in d["warnings"])
        assert d["ok_for_interpretation"] is False

    def test_a_well_sampled_signal_is_still_clean(self):
        res = transfer_entropy(*self._coupled(5.0), n_surrogates=50)
        d = res.diagnostics
        assert d["n_realized_states_x"] == 4 and d["warnings"] == []
        assert d["ok_for_interpretation"] is True

    def test_the_discrete_estimator_recovers_the_coupling_on_sparse_counts(self):
        """The documented route for integer spike counts still works on the same data the
        quantile estimator cannot represent."""
        x, y = self._coupled(0.1)
        res = transfer_entropy(x.astype(int), y.astype(int), estimator="discrete", n_surrogates=50)
        assert res.x_to_y > 0.1
        assert res.p_x_to_y < 0.05
        assert res.diagnostics["ok_for_interpretation"] is True


class TestCrossModalLagSearchPaysForItself:
    """`cross_modal_comparison` reported the p at the max-|r| lag without correcting for
    the search, so on independent white noise over 101 lags it called 99.5% of runs
    significant. It also swept a symmetric +-min(|lo|, |hi|) window, so (0, 500) searched
    nothing at all and (100, 500) searched +-100 ms.
    """

    @staticmethod
    def _independent(n=600, seed=0):
        rng = np.random.default_rng(seed)
        return rng.standard_normal(n), rng.standard_normal(n)

    def test_the_corrected_p_is_not_the_uncorrected_one(self):
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=200, seed=0)
        assert res["n_lags_searched"] == 101
        assert res["lag_corrected_pvalue"] > res["uncorrected_pvalue"]

    @pytest.mark.parametrize(
        "lag_range,expected_lags,lo,hi",
        [((-500, 500), 101, -500.0, 500.0), ((-500, 100), 61, -500.0, 100.0),
         ((0, 500), 51, 0.0, 500.0), ((100, 500), 41, 100.0, 500.0)],
    )
    def test_every_searched_lag_lies_inside_the_request(self, lag_range, expected_lags, lo, hi):
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent()
        res = cross_modal_comparison(
            x, y, lag_range_ms=lag_range, bin_ms=10.0, n_permutations=20, seed=0
        )
        assert res["n_lags_searched"] == expected_lags
        assert lo <= res["lag_ms"] <= hi

    def test_a_real_lagged_coupling_is_recovered_when_the_series_is_long_enough(self):
        from jnwb.statistics import cross_modal_comparison

        rng = np.random.default_rng(0)
        x = rng.standard_normal(4000)
        y = 0.5 * np.roll(x, 20) + rng.standard_normal(4000)
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=200, seed=0)
        assert res["lag_ms"] == pytest.approx(-200.0)
        assert res["lag_corrected_pvalue"] < 0.05
        assert res["warnings"] == []

    def test_a_lag_window_too_wide_for_the_series_is_flagged(self):
        """The corrected p cannot resolve below about n_lags / n_samples, so a short series
        with a wide lag window cannot reach 0.05 however strong the coupling is."""
        from jnwb.statistics import cross_modal_comparison

        x, y = self._independent(n=600)
        res = cross_modal_comparison(x, y, bin_ms=10.0, n_permutations=100, seed=0)
        assert res["lag_search_resolution_floor"] == pytest.approx(101 / 600)
        assert any("lag_window_too_wide" in w for w in res["warnings"])


class TestPsiInferenceIsNotOverstated:
    """A 10-segment jackknife reported p = 0.0, and overlapping bands were summed
    twice into the headline estimate."""

    @staticmethod
    def _lagged_pair(n=6000, lag=10, seed=0):
        rng = np.random.default_rng(seed)
        base = rng.normal(size=n)
        return base, np.roll(base, lag) + 0.5 * rng.normal(size=n)

    def test_the_jackknife_p_reflects_the_segment_count(self):
        """`2 * norm.sf(|z|)` gave exactly 0.0 -- a p no 10-segment jackknife can support."""
        x, y = self._lagged_pair()
        res = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        assert res.diagnostics["p_source"] == "jackknife_z"
        assert res.p_net > 0.0, "a finite jackknife cannot support p = 0"
        n_seg = res.diagnostics["n_segments"]
        z = res.per_band["full"]["z"]
        expected = float(2 * stats.t.sf(abs(z), df=max(n_seg - 1, 1)))
        assert res.p_net == pytest.approx(expected, rel=1e-9)

    def test_fewer_segments_give_a_larger_p_for_the_same_z(self):
        """The Gaussian tail did not respond to the segment count at all."""
        z = 3.2876
        p_small = float(2 * stats.t.sf(z, df=5))
        p_large = float(2 * stats.t.sf(z, df=200))
        p_gauss = float(2 * stats.norm.sf(z))
        assert p_small > p_large > p_gauss

    def test_duplicate_bands_warn_instead_of_doubling_the_estimate(self):
        """{'a': (14, 30), 'b': (14, 30)} returned exactly 2x {'beta': (14, 30)}."""
        x, y = self._lagged_pair()
        single = phase_slope_index(x, y, fs=1000.0, nperseg=1024, bands={"beta": (14.0, 30.0)})
        with pytest.warns(RuntimeWarning, match="bands overlap"):
            doubled = phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"a": (14.0, 30.0), "b": (14.0, 30.0)}
            )
        assert doubled.net == pytest.approx(2.0 * single.net, rel=1e-9)
        assert any("overlapping_bands" in w for w in doubled.diagnostics["warnings"])

    def test_partially_overlapping_bands_also_warn(self):
        x, y = self._lagged_pair()
        with pytest.warns(RuntimeWarning, match="bands overlap"):
            phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"a": (14.0, 30.0), "b": (25.0, 40.0)}
            )

    def test_disjoint_bands_do_not_warn(self):
        x, y = self._lagged_pair()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            res = phase_slope_index(
                x, y, fs=1000.0, nperseg=1024, bands={"beta": (14.0, 30.0), "gamma": (35.0, 50.0)}
            )
        assert not any("overlapping_bands" in w for w in res.diagnostics["warnings"])

    def test_the_sign_convention_is_unchanged(self):
        """Antisymmetry and direction were verified correct against Nolte et al. 2008."""
        x, y = self._lagged_pair()
        fwd = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        rev = phase_slope_index(y, x, fs=1000.0, nperseg=1024)
        assert fwd.net == pytest.approx(-rev.net, rel=1e-9)
        assert fwd.net > 0.0

    def test_the_returned_spectrum_carries_the_same_sign_as_net(self):
        """The spectrum is public and plotted; summed over the band's adjacent-bin pairs it is
        the band estimate itself, so its sign is pinned by the headline value."""
        x, y = self._lagged_pair()
        fwd = phase_slope_index(x, y, fs=1000.0, nperseg=1024)
        rev = phase_slope_index(y, x, fs=1000.0, nperseg=1024)
        freqs = fwd.spectrum["freqs"]
        lo, hi = fwd.per_band["full"]["band_hz"]
        idx = np.flatnonzero((freqs >= lo) & (freqs <= hi))
        in_band = fwd.spectrum["psi_per_freq"][idx[:-1]].sum()
        assert in_band == pytest.approx(fwd.net, rel=1e-9)
        np.testing.assert_allclose(
            fwd.spectrum["psi_per_freq"], -rev.spectrum["psi_per_freq"], atol=1e-12)


class TestGrangerNotTestedIsNotPassed:
    """An untested assumption and a degenerate fit were both reported as
    interpretable results."""

    # `sys.path[0]` for a script is the script's own directory, not the cwd, so without
    # this the probe would import whatever `jnwb` happens to be in site-packages rather
    # than the checkout under test.
    STATIONARITY_PROBE = [
        "import sys, numpy as np",
        "sys.path.insert(0, REPO_ROOT_PLACEHOLDER)",
        "class B:",
        "    def find_spec(self, name, path=None, target=None):",
        "        if name == 'statsmodels' or name.startswith('statsmodels.'):",
        "            raise ImportError('blocked for this probe')",
        "        return None",
        "sys.meta_path.insert(0, B())",
        "for m in [k for k in sys.modules if k.startswith('statsmodels')]:",
        "    del sys.modules[m]",
        "from jnwb.connectivity import granger",
        "rng = np.random.default_rng(0)",
        "a = np.cumsum(rng.normal(size=800))",
        "b = np.cumsum(rng.normal(size=800))",
        "d = granger(a, b, order=3).diagnostics",
        "print(repr((d['ok_for_interpretation'], d['warnings'])))",
    ]

    def test_an_untested_stationarity_assumption_is_not_reported_as_passed(self, tmp_path):
        """`_adf_pvalue` turns a missing `statsmodels` into NaN, and
        `bool(np.isnan(adf_p) or ...)` turned that into stationarity_ok=True: two pure
        random walks came back ok_for_interpretation=True with an empty warnings list.

        Run in a subprocess because blocking an import mid-process is not reversible.
        """
        import subprocess
        import sys as _sys

        script = tmp_path / "probe.py"
        repo_root = pathlib.Path(__file__).resolve().parents[1]
        lines = [
            line.replace("REPO_ROOT_PLACEHOLDER", repr(str(repo_root)))
            for line in self.STATIONARITY_PROBE
        ]
        script.write_text(chr(10).join(lines), encoding="utf-8")
        out = subprocess.run(
            [_sys.executable, str(script)],
            cwd=str(pathlib.Path(__file__).resolve().parents[1]),
            capture_output=True,
            text=True,
        )
        assert out.returncode == 0, out.stderr
        ok, warns = ast.literal_eval(out.stdout.strip().splitlines()[-1])
        assert ok is False, "an untested assumption must not be reported as interpretable"
        assert "stationarity_not_tested" in warns

    def test_a_tested_and_passing_series_is_still_interpretable(self):
        rng = np.random.default_rng(1)
        g = granger(rng.normal(size=800), rng.normal(size=800), order=3)
        assert g.diagnostics["warnings"] == []
        assert g.diagnostics["ok_for_interpretation"] is True

    def test_a_degenerate_fit_is_not_a_measured_zero(self):
        """granger(ones, ones) returned x_to_y = y_to_x = 0.0 with an empty warnings list
        and ok_for_interpretation=True, while transfer_entropy warns on the same input."""
        constant = np.ones(800)
        g = granger(constant, constant, order=3)
        assert np.isnan(g.x_to_y)
        assert np.isnan(g.y_to_x)
        assert any("degenerate" in w for w in g.diagnostics["warnings"])
        assert g.diagnostics["ok_for_interpretation"] is False

    def test_the_degenerate_verdict_matches_its_siblings(self):
        constant = np.ones(800)
        g = granger(constant, constant, order=3)
        te = transfer_entropy(constant, constant)
        assert g.diagnostics["ok_for_interpretation"] == te.diagnostics["ok_for_interpretation"] is False
