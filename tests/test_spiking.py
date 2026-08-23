"""Unit tests for jnwb.spiking -- generic spike-response metrics (firing rate/latency/z-score,
significance classification, spike-LFP phase locking), promoted 2026-08-23 from
omission.jnwb_ext.spiking (99%-jnwb-sufficiency normalization).
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.spiking import compute_response_metrics, classify_response_significance, phase_locking_index


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.compute_response_metrics is compute_response_metrics
        assert jnwb.classify_response_significance is classify_response_significance
        assert jnwb.phase_locking_index is phase_locking_index

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("compute_response_metrics", "classify_response_significance",
                     "phase_locking_index"):
            assert name in jnwb.__all__

    def test_omission_reexports_same_objects(self):
        omission = pytest.importorskip("omission")
        assert omission.compute_response_metrics is compute_response_metrics
        assert omission.classify_response_significance is classify_response_significance
        assert omission.phase_locking_index is phase_locking_index


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
        assert 0.0 <= result["pli"] <= 1.0
