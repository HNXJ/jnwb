"""Unit tests for jnwb.connectivity -- functional connectivity estimators.

Covers the public-import surface plus one smoke test per estimator. Deeper behavioral coverage
may live in downstream project test suites that call the same jnwb functions.
"""
from __future__ import annotations

import numpy as np
import pytest

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
        with pytest.raises(ValueError, match="window must satisfy end > start"):
            bin_spikes([np.array([0.1])], window=(0.5, 0.5))
        with pytest.raises(ValueError, match="yields 1 bins; need >= 2"):
            bin_spikes([np.array([0.1])], window=(0.0, 0.1), bin_size_ms=100.0)


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
