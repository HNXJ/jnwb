"""Bin edges of UnitAnalyzer.psth and the whole-second Fano windows of quality_metrics.

Float edges caused both defects: a psth edge built by linspace in seconds sat at 1e-17 s
instead of 0, so a spike on the onset fell in the bin before it; quality_metrics took int() of a
span that rounds just under a whole number of seconds, and its window edges drifted off the spikes.
"""
import unittest

import numpy as np
from numpy.testing import assert_allclose

from jnwb.analyzers import UnitAnalyzer


class TestPsthBinEdges(unittest.TestCase):
    def test_a_spike_on_the_onset_lands_in_the_bin_centred_at_plus_5_ms(self):
        onset = 1.0
        spikes = np.array([onset])
        self.assertEqual(spikes[0] - onset, 0.0)  # fixture: the spike is exactly on the onset
        out = UnitAnalyzer.psth(spikes, np.array([onset]), 10,
                                window_ms=(-100, 200), label="center")
        hit = np.flatnonzero(out["psth"])
        self.assertEqual(hit.size, 1)
        assert_allclose(out["bin_centers_ms"][hit], [5.0], rtol=1e-12, atol=0)
        assert_allclose(out["psth"][hit], [100.0], rtol=1e-12, atol=0)  # 1 spike / 10 ms

    def test_a_spike_on_an_interior_edge_starts_the_bin_there(self):
        # Onset 0; window (-100, 100) in 50 ms bins: [-100, -50), [-50, 0), [0, 50), [50, 100].
        # Each bin is right-open, the last closed on the right, so 0.05 starts the last bin and
        # 0.1 is in it too. Counts [1, 1, 1, 2] give 20, 20, 20, 40 spikes/s.
        spikes = np.array([-0.1, -0.05, 0.0, 0.05, 0.1])
        out = UnitAnalyzer.psth(spikes, np.array([0.0]), 50,
                                window_ms=(-100, 100), label="center")
        assert_allclose(out["psth"], [20.0, 20.0, 20.0, 40.0], rtol=1e-12, atol=0)
        assert_allclose(out["bin_centers_ms"], [-75.0, -25.0, 25.0, 75.0], rtol=1e-12, atol=0)

    def test_an_exact_window_keeps_its_counts_with_a_spike_on_every_edge(self):
        # (0, 100) in 10 ms bins has edges that were already exact, so every count is unchanged:
        # eleven spikes at 0, 10, ..., 100 ms give nine bins of one spike and the last of two.
        spikes = np.arange(0, 101, 10) / 1000.0
        out = UnitAnalyzer.psth(spikes, np.array([0.0]), 10, window_ms=(0, 100), label="center")
        assert_allclose(out["psth"], [100.0] * 9 + [200.0], rtol=1e-12, atol=0)

    def test_spikes_off_the_edges_in_an_inexact_window_keep_their_bins(self):
        # (-100, 100) in 50 ms bins has one interior edge a float off, so only a spike on an
        # edge can move. Spikes at -75, -20, 10, 25 and 60 ms sit mid-bin: counts [1, 1, 2, 1].
        spikes = np.array([-0.075, -0.02, 0.01, 0.025, 0.06])
        out = UnitAnalyzer.psth(spikes, np.array([0.0]), 50,
                                window_ms=(-100, 100), label="center")
        assert_allclose(out["psth"], [20.0, 20.0, 40.0, 20.0], rtol=1e-12, atol=0)


class TestQualityMetricsWholeSecondWindows(unittest.TestCase):
    def test_windows_from_the_first_spike_count_1_1_2(self):
        spikes = np.array([2.15, 3.15, 4.15, 5.15])
        self.assertAlmostEqual(spikes[-1] - spikes[0], 3.0, places=12)  # fixture: a 3 s span
        # Counts [1, 1, 2] give (ddof=1 variance) / mean = (1/3) / (4/3) = 1/4.
        # [2, 0, 2], the old result, gives 1.
        fano = UnitAnalyzer.quality_metrics(spikes, 300.0, 5.0)["fano_factor"]
        assert_allclose(fano, 0.25, rtol=1e-12, atol=0)

    def test_a_span_that_rounds_just_under_two_seconds_gives_a_finite_fano(self):
        spikes = np.array([0.05, 1.0, 2.05])
        duration = spikes[-1] - spikes[0]
        self.assertLess(duration, 2.0)  # fixture: the span rounds just under 2 s
        self.assertGreater(duration, 2.0 - 1e-9)
        # Two whole windows: [0.05, 1.05) holds 0.05 and 1.0, [1.05, 2.05] holds 2.05.
        # Counts [2, 1] give (0.5) / 1.5 = 1/3.
        fano = UnitAnalyzer.quality_metrics(spikes, 300.0, 5.0)["fano_factor"]
        self.assertTrue(np.isfinite(fano))
        assert_allclose(fano, 1.0 / 3.0, rtol=1e-12, atol=0)


if __name__ == "__main__":
    unittest.main()
