"""Unit tests for jnwb.connectivity -- modality-agnostic functional connectivity (mutual
information, Granger causality, phase slope index, transfer entropy), promoted 2026-08-23 from
omission.jnwb_ext.connectivity (99%-jnwb-sufficiency normalization). Deep behavioral coverage
(surrogate determinism, conditioning, spectral-Geweke agreement, etc.) already lives in
omission/tests/test_decoding_connectivity.py against the same functions via the jnwb.connectivity
redirect; these tests cover the public-import surface plus one smoke test per estimator.
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

    def test_omission_reexports_same_objects(self):
        omission = pytest.importorskip("omission")
        assert omission.granger is granger
        assert omission.phase_slope_index is phase_slope_index
        assert omission.transfer_entropy is transfer_entropy


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
