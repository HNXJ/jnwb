#!/usr/bin/env python3
"""
Comprehensive tests for jnwb.analyzers module.

Focus areas:
- TFRAnalyzer: band extraction, layer-aware averaging, trial averaging
- UnitAnalyzer: autocorrelogram, quality metrics
- PopulationAnalyzer: network connectivity, group comparison, distribution by area
- StatisticalAnalysis: correlation methods
"""

import contextlib
import sys
import unittest
import warnings
import numpy as np
import pandas as pd

from jnwb.analyzers import TFRAnalyzer, UnitAnalyzer, PopulationAnalyzer
from jnwb.statistics import StatisticalAnalysis


@contextlib.contextmanager
def blocked_import(name):
    """Make `import <name>` fail, restoring only that one key.

    `unittest.mock.patch.dict(sys.modules, ...)` cannot be used for this. Its restore is
    `sys.modules.clear()` followed by `update(original)`, so every module imported inside
    the block is evicted on exit. Blocking cupy here sends
    `PopulationAnalyzer.population_trajectory` down its PyTorch fallback, which performs
    the process's first `import torch` and adds ~730 `torch*` entries; the restore removed
    all of them while torch's C extensions stayed loaded, and the next `import torch`
    re-executed `torch/__init__.py` against an already-initialised `torch._C` and crashed
    the interpreter with an access violation. That was P-12.
    """
    missing = object()
    previous = sys.modules.get(name, missing)
    sys.modules[name] = None
    try:
        yield
    finally:
        if previous is missing:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous


class TestTFRAnalyzerBandExtraction(unittest.TestCase):
    """Test TFRAnalyzer band extraction methods."""

    def setUp(self):
        """Create mock TFR data.

        The frequency axis is the only load-bearing one: `extract_band` picks bins by
        comparing `freqs` against the band bounds, and the trailing axes are carried
        through a mean and reach these tests only as numbers in a shape assertion. This
        was (128, 200, 500, 100) -- 9.537 GiB of float64, about 34 s per test to assert
        that three dimensions survive -- against the same outcomes at 2.4 KiB. The
        frequency axis and its coordinates are unchanged, so the same bins fall in each
        band.
        """
        np.random.seed(42)
        self.freqs = np.linspace(1.0, 150.0, 200)
        self.tfr_data = np.random.randn(2, 200, 3, 2)

    def test_extract_band_alpha(self):
        """Verify alpha band extraction (8-12/15 Hz)."""
        result = TFRAnalyzer.extract_band(self.tfr_data, 'alpha', freqs=self.freqs, freq_axis=1)
        self.assertEqual(result.shape, (2, 3, 2))

    def test_extract_band_beta(self):
        """Verify beta band extraction (15-30 Hz)."""
        result = TFRAnalyzer.extract_band(self.tfr_data, 'beta', freqs=self.freqs, freq_axis=1)
        self.assertEqual(result.shape, (2, 3, 2))

    def test_extract_band_bounds(self):
        """Verify extracted band is float."""
        result = TFRAnalyzer.extract_band(self.tfr_data, 'alpha', freqs=self.freqs, freq_axis=1)
        self.assertEqual(result.dtype, float)

    def test_extract_band_value_is_the_mean_over_in_band_bins_only(self):
        """The returned number, not just its shape.

        Every assertion above this one reads `result.shape` or `result.dtype`, so two
        mutations that change every returned number while preserving shape passed this
        whole file: dropping the band's upper bound, and replacing the frequency-axis
        mean with a sum. Measured, the suite does catch both -- through
        `tests/test_audit_reproducers.py`, and for the sum also through
        `tests/test_jnwb_core.py` -- so the file was blind, not the suite. Core
        arithmetic should not depend on an audit probe for its only oracle.

        Each bin carries its own frequency in Hz as its power, so the correct alpha
        result is the mean of the in-band frequencies. alpha is [8.0, 14.0] inclusive
        and the bins are the integers 1..20, so seven are selected and 77/7 is exactly
        11.0 in binary floating point. Dropping the upper bound admits bins 15..20,
        each larger than the true mean, and gives 14.0; the sum gives 77.0.
        """
        freqs = np.linspace(1.0, 20.0, 20)
        self.assertTrue(np.array_equal(freqs, np.arange(1.0, 21.0)), freqs)
        tfr = np.tile(freqs[None, :, None], (1, 1, 2))

        result = TFRAnalyzer.extract_band(tfr, 'alpha', freqs=freqs, freq_axis=1)

        self.assertEqual(result.shape, (1, 2))
        np.testing.assert_allclose(result, 11.0)


class TestTFRAnalyzerTrialAverage(unittest.TestCase):
    """Test trial averaging in TFRAnalyzer."""

    def setUp(self):
        """Create mock TFR data.

        `trial_average` reduces the last axis and has no frequency semantics, so no axis
        here is load-bearing beyond the trial axis needing at least two samples for the
        `ddof=1` standard deviation. This was (64, 100, 300, 80), 1.144 GiB.
        """
        np.random.seed(42)
        self.tfr_data = np.random.randn(2, 3, 4, 5)

    def test_trial_average_shape(self):
        """Verify trial average returns dict with mean array reduced over trials."""
        result = TFRAnalyzer.trial_average(self.tfr_data)
        self.assertIn('mean', result)
        self.assertEqual(result['mean'].shape, (2, 3, 4))

    def test_trial_average_values(self):
        """Verify trial average computes mean correctly."""
        result = TFRAnalyzer.trial_average(self.tfr_data)
        expected = np.mean(self.tfr_data, axis=-1)
        np.testing.assert_array_almost_equal(result['mean'], expected)


class TestTFRAnalyzerLayerAware(unittest.TestCase):
    """Test layer-aware averaging in TFRAnalyzer."""

    def setUp(self):
        """Create mock TFR data with layer mask."""
        np.random.seed(42)
        self.tfr_data = np.random.randn(128, 100, 300)

        # Create layer mask: superficial (first 62), deep (last 66)
        self.layer_mask = {
            'superficial_mask': [True] * 62 + [False] * 66,
            'deep_mask': [False] * 62 + [True] * 66,
        }

    def test_average_across_channels_global(self):
        """Verify global channel averaging without layer mask."""
        result = TFRAnalyzer.average_across_channels(self.tfr_data)
        self.assertEqual(result.shape, (100, 300))

    def test_average_across_channels_with_layer(self):
        """Verify layer-aware averaging preserves layers."""
        result = TFRAnalyzer.average_across_channels(self.tfr_data, layer_mask=self.layer_mask)
        self.assertEqual(result.shape, (2, 100, 300))

    def test_layer_aware_values_differ(self):
        """Verify superficial and deep layers have different values."""
        result = TFRAnalyzer.average_across_channels(self.tfr_data, layer_mask=self.layer_mask)
        superficial = result[0]
        deep = result[1]
        self.assertFalse(np.allclose(superficial, deep))

    def test_channel_count_mask_mismatch_raises_value_error(self):
        """Verify ValueError is raised when layer mask lengths mismatch channel count."""
        mismatched_mask = {
            'superficial_mask': [True] * 10,
            'deep_mask': [False] * 10,
        }
        with self.assertRaises(ValueError):
            TFRAnalyzer.average_across_channels(self.tfr_data, layer_mask=mismatched_mask)

    def test_empty_layer_mask_returns_nan_not_zeros(self):
        """Verify empty layer mask returns NaN array instead of fabricated zeros."""
        empty_sup_mask = {
            'superficial_mask': [False] * 128,
            'deep_mask': [True] * 128,
        }
        result = TFRAnalyzer.average_across_channels(self.tfr_data, layer_mask=empty_sup_mask)
        self.assertTrue(np.all(np.isnan(result[0])))
        self.assertFalse(np.all(np.isnan(result[1])))



class TestUnitAnalyzerAutocorrelogram(unittest.TestCase):
    """Test UnitAnalyzer autocorrelogram with fixed spike data."""

    def setUp(self):
        """Create realistic spike times."""
        np.random.seed(42)
        spike_times = []
        t = 0.0
        while t < 5.0:
            t += 0.01 + np.random.uniform(-0.002, 0.002)
            spike_times.append(t)
        self.spike_times = np.array(spike_times)

    def test_autocorrelogram_shape(self):
        """Verify ACG returns proper lag array."""
        result = UnitAnalyzer.autocorrelogram(self.spike_times, max_lag_ms=50.0, bin_size_ms=1.0)
        self.assertIn('acg', result)
        self.assertIn('lag_times_ms', result)
        self.assertGreater(len(result['acg']), 0)


class TestAutocorrelogramRefractoryTestIsRemoved(unittest.TestCase):
    """The test took the Poisson upper tail of the bin covering about 5.5 to 6.5 ms (centre
    about 6 ms), so an over-filled bin read as a single unit and an empty one did not. Its
    keys were NaN with a FutureWarning for one release and are now gone."""

    REMOVED = ('refractory_period_violation', 'is_single_unit', 'refr_count', 'baseline_count')

    @staticmethod
    def _trains():
        rng = np.random.default_rng(0)
        background = np.sort(rng.uniform(0.0, 600.0, 12000))
        # Every spike has a partner 6 ms later: the tested bin is over-filled.
        contaminated = np.sort(np.concatenate([background, background + 0.006]))
        # A 10 ms dead time after every spike: a clean refractory dip.
        clean = np.cumsum(0.010 + rng.exponential(0.05, 12000))
        return {'contaminated': contaminated, 'clean dip': clean}

    def test_the_keys_are_removed_and_nothing_warns(self):
        for name, train in self._trains().items():
            with self.subTest(train=name):
                with warnings.catch_warnings():
                    warnings.simplefilter('error')
                    result = UnitAnalyzer.autocorrelogram(train, max_lag_ms=50, bin_size_ms=1)
                self.assertEqual(set(result), {'acg', 'lag_times_ms', 'device_used'})
                for key in self.REMOVED:
                    self.assertNotIn(key, result)
                self.assertEqual(len(result['acg']), 50)
                np.testing.assert_allclose(result['lag_times_ms'], np.arange(1, 51))
                self.assertEqual(result['device_used'], 'cpu')


class TestPopulationAnalyzerNetwork(unittest.TestCase):
    """Test PopulationAnalyzer network connectivity."""

    def test_network_connectivity_basic(self):
        """Verify network connectivity computes metrics."""
        corr_matrix = np.array([
            [1.0, 0.7, 0.3, 0.1, 0.2],
            [0.7, 1.0, 0.6, 0.2, 0.1],
            [0.3, 0.6, 1.0, 0.5, 0.4],
            [0.1, 0.2, 0.5, 1.0, 0.8],
            [0.2, 0.1, 0.4, 0.8, 1.0],
        ])

        result = PopulationAnalyzer.network_connectivity(corr_matrix, threshold=0.3)
        self.assertIn('density', result)
        self.assertIn('n_nodes', result)
        self.assertIn('n_edges', result)
        self.assertGreaterEqual(result['density'], 0)
        self.assertLessEqual(result['density'], 1)

    def test_network_connectivity_edge_count(self):
        """Verify edge counting is correct."""
        corr_matrix = np.array([
            [1.0, 0.5, 0.2],
            [0.5, 1.0, 0.6],
            [0.2, 0.6, 1.0],
        ])

        result = PopulationAnalyzer.network_connectivity(corr_matrix, threshold=0.4)
        self.assertGreaterEqual(result['n_edges'], 0)
        self.assertLessEqual(result['n_edges'], 3)

    def test_the_graph_is_the_one_network_topology_computes(self):
        """The method calls the routed function rather than keeping a copy of its rule."""
        from unittest.mock import patch
        import jnwb.connectivity as connectivity

        corr = np.random.default_rng(5).uniform(-1, 1, size=(6, 6))
        with patch.object(connectivity, 'network_topology',
                          wraps=connectivity.network_topology) as spy:
            result = PopulationAnalyzer.network_connectivity(corr, threshold=0.3)
        spy.assert_called_once()
        topology = connectivity.network_topology(corr, threshold=0.3)
        self.assertEqual(result['n_edges'], topology['n_edges'] // 2)
        self.assertEqual(result['degree_distribution'], topology['in_degrees'])

    def test_a_complex_entry_is_thresholded_on_its_modulus(self):
        corr = np.array([[1, 0.1 + 0.9j], [0.1 - 0.9j, 1]])
        result = PopulationAnalyzer.network_connectivity(corr, threshold=0.3)
        self.assertEqual(result['n_edges'], 1)

    def test_a_nan_entry_raises_rather_than_reading_as_no_edge(self):
        corr = np.eye(4)
        corr[0, 1] = corr[1, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "NaN or Inf off the diagonal"):
            PopulationAnalyzer.network_connectivity(corr, threshold=0.3)


class TestPopulationAnalyzerPieChartData(unittest.TestCase):
    """A filter on a column the table lacks refuses; it used to count every unit."""

    UNITS = pd.DataFrame({
        'area': ['V1', 'V1', 'V4', 'MT'],
        'quality_label': ['good', 'mua', 'good', 'good'],
    })

    def test_a_filter_on_an_absent_column_raises(self):
        with self.assertRaisesRegex(ValueError, r"absent from units: \['areaa'\]"):
            PopulationAnalyzer.pie_chart_data(self.UNITS, {'areaa': 'V1'})

    def test_another_filter_error_is_not_relabelled_as_an_absent_column(self):
        units = self.UNITS.iloc[:2]
        with self.assertRaises(ValueError) as err:
            PopulationAnalyzer.pie_chart_data(units, {'area': np.array(['V1', 'V4', 'MT'])})
        self.assertNotIn('absent', str(err.exception))

    def test_a_filter_on_a_present_column_counts_only_the_matching_units(self):
        res = PopulationAnalyzer.pie_chart_data(self.UNITS, {'area': 'V1'})
        self.assertEqual(res['counts'], {'good': 1, 'mua': 1})
        self.assertEqual(res['total'], 2)

    def test_the_filter_is_filter_by_criteria(self):
        from unittest.mock import patch
        import jnwb.metadata as metadata

        with patch.object(metadata, 'filter_by_criteria',
                          wraps=metadata.filter_by_criteria) as spy:
            PopulationAnalyzer.pie_chart_data(self.UNITS, {'area': ['V1', 'MT']})
        spy.assert_called_once()


class TestPopulationAnalyzerCompareCriteria(unittest.TestCase):
    """Test PopulationAnalyzer comparison between unit groups."""

    def setUp(self):
        """Create mock unit populations."""
        np.random.seed(42)
        self.group1 = pd.DataFrame({
            'firing_rate': np.random.exponential(8, 50),
            'area': ['V1'] * 50,
        })
        self.group2 = pd.DataFrame({
            'firing_rate': np.random.exponential(5, 50),
            'area': ['V2'] * 50,
        })

    def test_compare_criteria_returns_dict(self):
        """Verify compare_criteria returns statistical comparison."""
        result = PopulationAnalyzer.compare_criteria(self.group1, self.group2, metric='firing_rate')
        self.assertIsInstance(result, dict)
        self.assertIn('group1_mean', result)
        self.assertIn('group2_mean', result)

    def test_compare_criteria_identifies_difference(self):
        """Verify comparison can detect group differences."""
        result = PopulationAnalyzer.compare_criteria(self.group1, self.group2, metric='firing_rate')
        self.assertGreater(result['group1_mean'], result['group2_mean'])


class TestPopulationAnalyzerDistribution(unittest.TestCase):
    """Test PopulationAnalyzer distribution analysis."""

    def setUp(self):
        """Create mock population data."""
        np.random.seed(42)
        self.units_df = pd.DataFrame({
            'firing_rate': np.random.exponential(5, 150),
            'area': ['V1'] * 50 + ['V2'] * 50 + ['MT'] * 50,
        })

    def test_distribution_by_area_returns_dict(self):
        """Verify distribution_by_area returns area statistics."""
        result = PopulationAnalyzer.distribution_by_area(self.units_df, metric='firing_rate')
        self.assertIn('per_area', result)
        self.assertIn('V1', result['per_area'])
        self.assertIn('V2', result['per_area'])
        self.assertIn('MT', result['per_area'])

    def test_distribution_by_area_values_reasonable(self):
        """Verify area statistics are reasonable."""
        result = PopulationAnalyzer.distribution_by_area(self.units_df, metric='firing_rate')
        for area, stats in result['per_area'].items():
            if isinstance(stats, dict):
                self.assertGreater(stats['mean'], 0)
                self.assertGreater(stats['std'], 0)


class TestStatisticalAnalysisCoverage(unittest.TestCase):
    """Test coverage of StatisticalAnalysis methods."""

    def setUp(self):
        """Create test data."""
        np.random.seed(42)
        self.x = np.random.randn(100)
        self.y = np.random.randn(100)

    def test_correlate_returns_dict(self):
        """Verify correlate returns proper structure."""
        result = StatisticalAnalysis.correlate(self.x, self.y)
        self.assertIsInstance(result, dict)
        self.assertIn('parametric', result)
        self.assertIn('non_parametric', result)
        self.assertEqual(result['parametric']['test'], 'pearson_r')
        self.assertEqual(result['non_parametric']['test'], 'spearman_rho')

    def test_correlate_with_valid_data(self):
        """Verify correlate handles valid data."""
        result = StatisticalAnalysis.correlate(self.x, self.y)
        r = result['parametric']['statistic']
        rho = result['non_parametric']['statistic']
        self.assertGreaterEqual(r, -1.0)
        self.assertLessEqual(r, 1.0)
        self.assertGreaterEqual(rho, -1.0)
        self.assertLessEqual(rho, 1.0)

    def test_correlate_identical_arrays(self):
        """Verify correlate handles perfect correlation."""
        result = StatisticalAnalysis.correlate(self.x, self.x)
        self.assertAlmostEqual(result['parametric']['statistic'], 1.0, places=5)
        self.assertAlmostEqual(result['non_parametric']['statistic'], 1.0, places=5)


class TestTFRAnalyzerBandNames(unittest.TestCase):
    """Test all band extraction methods."""

    def setUp(self):
        """Create TFR data.

        As above, the 150-bin frequency axis and its coordinates are what decide which
        bins each of the five bands selects; the rest was 0.358 GiB of shape assertion.
        """
        np.random.seed(42)
        self.freqs = np.linspace(1.0, 150.0, 150)
        self.tfr_data = np.random.randn(2, 150, 3, 4)

    def test_all_bands_extractable(self):
        """Verify all standard bands can be extracted."""
        bands = ['theta', 'alpha', 'beta', 'low_gamma', 'high_gamma']
        for band in bands:
            with self.subTest(band=band):
                result = TFRAnalyzer.extract_band(self.tfr_data, band, freqs=self.freqs, freq_axis=1)
                self.assertEqual(len(result.shape), 3)
                self.assertEqual(result.shape[0], 2)
                self.assertEqual(result.shape[1], 3)


class TestPsthCountsSpikesOnBothEdges(unittest.TestCase):
    """The window is [onset + pre, onset + post], both edges inclusive, but spike - onset
    rounded a spike on either edge just outside the outer bin edges and np.histogram dropped
    it: on these onsets, 114 of 405 at the left edge and 147 of 405 at the right."""

    ONSETS = 2.0 + 0.7 * np.arange(405)

    def _counts(self, spikes):
        res = UnitAnalyzer.psth(spikes, self.ONSETS, bin_size_ms=10, window_ms=(-100, 200))
        return np.rint(res['psth'] * 0.010 * len(self.ONSETS))

    def test_a_spike_on_the_left_edge_counts_in_the_first_bin(self):
        spikes = self.ONSETS - 0.1
        self.assertGreater(np.sum(spikes - self.ONSETS < -0.1), 0)  # the fixture rounds out
        counts = self._counts(spikes)
        self.assertEqual(counts[0], len(self.ONSETS))
        self.assertEqual(counts.sum(), len(self.ONSETS))

    def test_a_spike_on_the_right_edge_counts_in_the_last_bin(self):
        spikes = self.ONSETS + 0.2
        self.assertGreater(np.sum(spikes - self.ONSETS > 0.2), 0)  # the fixture rounds out
        counts = self._counts(spikes)
        self.assertEqual(counts[-1], len(self.ONSETS))
        self.assertEqual(counts.sum(), len(self.ONSETS))

    def test_a_spike_past_either_edge_is_not_counted(self):
        spikes = np.concatenate([self.ONSETS - 0.1 - 1e-6, self.ONSETS + 0.2 + 1e-6])
        self.assertEqual(self._counts(spikes).sum(), 0)


class TestUnitAnalyzerQualityMetrics(unittest.TestCase):
    """Test UnitAnalyzer quality assessment."""

    def test_quality_metrics_structure(self):
        """Verify quality_metrics returns expected fields."""
        np.random.seed(42)
        spike_times = np.sort(np.random.uniform(0, 10, 200))
        result = UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=250.0, firing_rate=20.0)
        self.assertIsInstance(result, dict)
        self.assertIn('refr_violations_pct', result)
        self.assertIn('fano_factor', result)

    def test_spike_order_does_not_change_any_metric(self):
        """Unsorted, a backward step was a negative interval counted as a violation, and the
        first and last entries were read as the span: 51% violations where there were 1%."""
        rng = np.random.default_rng(0)
        st = np.sort(rng.uniform(0.0, 100.0, 500))
        ref = UnitAnalyzer.quality_metrics(st, 300.0, 5.0)
        expected_pct = 100.0 * np.sum(np.diff(st) * 1000 < 2) / (len(st) - 1)
        self.assertEqual(ref['refr_violations_pct'], expected_pct)
        shuffled = UnitAnalyzer.quality_metrics(rng.permutation(st), 300.0, 5.0)
        self.assertEqual(shuffled, ref)

    def test_a_non_finite_or_multi_dimensional_train_raises(self):
        """A NaN read as a good single unit, an infinity raised OverflowError and a 2-D
        array was pooled into one train."""
        st = np.sort(np.random.default_rng(0).uniform(0.0, 100.0, 500))
        for bad in (np.nan, np.inf):
            with self.subTest(value=bad):
                with self.assertRaisesRegex(ValueError, "1 NaN or infinite value"):
                    UnitAnalyzer.quality_metrics(np.append(st, bad), 300.0, 5.0)
        with self.assertRaisesRegex(ValueError, r"must be one 1-D train; got shape \(2, 250\)"):
            UnitAnalyzer.quality_metrics(st.reshape(2, 250), 300.0, 5.0)

    def test_zero_or_one_spike_gives_nan_and_no_verdict(self):
        """With no interval there is no violation rate: it read 0.0 and a good single unit."""
        for st in (np.array([]), np.array([1.0])):
            with self.subTest(n_spikes=len(st)):
                res = UnitAnalyzer.quality_metrics(st, 400.0, 0.0)
                self.assertTrue(np.isnan(res['refr_violations_pct']))
                self.assertTrue(np.isnan(res['fano_factor']))
                self.assertIsNone(res['is_good_single_unit'])

    def test_an_undefined_fano_factor_gives_no_verdict(self):
        """A span under two whole 1-s windows has no count variance: a NaN Fano factor read
        as passing, and one window read Fano 0."""
        for span in (0.5, 1.5):
            with self.subTest(span_s=span):
                st = np.arange(0.0, span, 0.005)          # 5 ms intervals, no violation
                res = UnitAnalyzer.quality_metrics(st, 300.0, 5.0)
                self.assertEqual(res['refr_violations_pct'], 0.0)
                self.assertTrue(np.isnan(res['fano_factor']))
                self.assertIsNone(res['is_good_single_unit'])

    def test_each_cut_off_is_an_argument(self):
        regular = np.arange(0.0, 10.0, 0.003)             # 3 ms intervals, Fano near 0
        self.assertTrue(UnitAnalyzer.quality_metrics(regular, 300.0, 5.0)['is_good_single_unit'])
        res = UnitAnalyzer.quality_metrics(regular, 300.0, 5.0, refractory_ms=4.0)
        self.assertEqual(res['refr_violations_pct'], 100.0)
        self.assertFalse(res['is_good_single_unit'])

        steps = np.where(np.arange(3000) % 10 == 0, 0.001, 0.003)   # 10 % at 1 ms
        violating = np.concatenate([[0.0], np.cumsum(steps)])
        self.assertAlmostEqual(
            UnitAnalyzer.quality_metrics(violating, 300.0, 5.0)['refr_violations_pct'], 10.0)
        self.assertFalse(UnitAnalyzer.quality_metrics(violating, 300.0, 5.0)['is_good_single_unit'])
        self.assertTrue(UnitAnalyzer.quality_metrics(
            violating, 300.0, 5.0, max_violation_pct=20.0)['is_good_single_unit'])

        counts = [1, 9] * 5 + [1]                          # per second; windows [1, 9]*4 + [1, 10]
        bursty = np.concatenate([k + np.linspace(0.1, 0.9, c) for k, c in enumerate(counts)])
        res = UnitAnalyzer.quality_metrics(bursty, 300.0, 5.0)
        self.assertGreater(res['fano_factor'], 2.0)
        self.assertFalse(res['is_good_single_unit'])
        self.assertTrue(UnitAnalyzer.quality_metrics(
            bursty, 300.0, 5.0, max_fano=10.0)['is_good_single_unit'])

        for name in ('refractory_ms', 'max_violation_pct', 'max_fano'):
            with self.subTest(cut_off=name):
                with self.assertRaisesRegex(ValueError, name):
                    UnitAnalyzer.quality_metrics(regular, 300.0, 5.0, **{name: 0.0})

    def test_a_non_finite_cut_off_is_refused_by_name(self):
        """An infinite cut-off passed every unit, or none, without a word."""
        regular = np.arange(0.0, 10.0, 0.003)
        for name in ('refractory_ms', 'max_violation_pct', 'max_fano'):
            for bad in (np.inf, -np.inf, np.nan):
                with self.subTest(cut_off=name, value=bad):
                    with self.assertRaisesRegex(ValueError, f"{name} must be finite"):
                        UnitAnalyzer.quality_metrics(regular, 300.0, 5.0, **{name: bad})

    def test_a_span_of_exactly_two_seconds_has_a_fano_factor(self):
        """Two whole 1-s windows are the fewest a variance needs."""
        st = np.linspace(0.0, 2.0, 401)                   # 5 ms intervals
        self.assertEqual(st[-1] - st[0], 2.0)
        res = UnitAnalyzer.quality_metrics(st, 300.0, 5.0)
        # Counts 200 and 201 (the end spike falls in the last window): variance 0.5 (ddof=1).
        self.assertEqual(res['fano_factor'], 0.5 / 200.5)
        self.assertIs(res['is_good_single_unit'], True)

    def test_two_windows_fano_uses_the_unbiased_variance(self):
        """ddof=1, the rule of jnwb.fano_factor; 0.2.8's ddof=0 gave 16/5 and passed max_fano=5."""
        st = np.concatenate([[0.0], np.linspace(1.0, 2.0, 9)])   # counts 1 and 9
        res = UnitAnalyzer.quality_metrics(st, 300.0, 5.0)
        self.assertEqual(res['refr_violations_pct'], 0.0)
        self.assertEqual(res['fano_factor'], 32.0 / 5.0)
        self.assertIs(UnitAnalyzer.quality_metrics(
            st, 300.0, 5.0, max_fano=5.0)['is_good_single_unit'], False)
        self.assertIs(UnitAnalyzer.quality_metrics(
            st, 300.0, 5.0, max_fano=7.0)['is_good_single_unit'], True)

    def test_fano_factor_equals_jnwb_fano_factor_on_the_same_windows(self):
        from jnwb import fano_factor
        st = np.sort(np.random.default_rng(3).uniform(0.0, 50.5, 400))
        n_windows = int(st[-1] - st[0])
        ref = fano_factor([st], st[0] + np.arange(n_windows), (0.0, 1.0), summary='mean')
        self.assertEqual(UnitAnalyzer.quality_metrics(st, 300.0, 5.0)['fano_factor'], ref['fano'])

    def test_fano_factor_goes_through_the_shared_helper(self):
        """A retyped variance would agree today and drift later; the value must come from the
        helper jnwb.fano_factor uses."""
        from unittest import mock
        import jnwb.analyzers
        import jnwb.spiking
        self.assertIs(jnwb.analyzers._count_fano, jnwb.spiking._count_fano)
        seen = []

        def marker(counts):
            seen.append(np.array(counts))
            return np.array([123.25])

        st = np.concatenate([[0.0], np.linspace(1.0, 2.0, 9)])
        with mock.patch.object(jnwb.analyzers, '_count_fano', marker):
            res = UnitAnalyzer.quality_metrics(st, 300.0, 5.0)
        self.assertEqual(res['fano_factor'], 123.25)
        self.assertEqual(len(seen), 1)
        np.testing.assert_array_equal(seen[0], [[1, 9]])

    def test_a_value_at_its_cut_off_does_not_pass(self):
        """Each comparison is strict: an interval equal to the refractory period is no
        violation, and a rate or Fano factor equal to its cut-off fails the verdict."""
        quarter = np.arange(41) * 0.25                     # 250 ms intervals, exact in binary
        self.assertEqual(UnitAnalyzer.quality_metrics(
            quarter, 300.0, 5.0, refractory_ms=250.0)['refr_violations_pct'], 0.0)

        steps = np.where(np.arange(3000) % 10 == 0, 0.001, 0.003)
        violating = np.concatenate([[0.0], np.cumsum(steps)])
        # Spikes per second [1, 9]*5 + [1]; the windows start at 0.1 s and the last is closed,
        # so its window counts are [1, 9]*4 + [1, 10].
        counts = [1, 9] * 5 + [1]
        bursty = np.concatenate([k + np.linspace(0.1, 0.9, c) for k, c in enumerate(counts)])
        for train, key, cut_off in ((violating, 'refr_violations_pct', 'max_violation_pct'),
                                    (bursty, 'fano_factor', 'max_fano')):
            with self.subTest(cut_off=cut_off):
                value = UnitAnalyzer.quality_metrics(train, 300.0, 5.0)[key]
                at = UnitAnalyzer.quality_metrics(train, 300.0, 5.0, **{cut_off: value})
                above = UnitAnalyzer.quality_metrics(
                    train, 300.0, 5.0, **{cut_off: np.nextafter(value, np.inf)})
                self.assertIs(at['is_good_single_unit'], False)
                self.assertIs(above['is_good_single_unit'], True)

    def test_docstring_states_each_default_and_the_variance_rule(self):
        import inspect
        doc = inspect.getdoc(UnitAnalyzer.quality_metrics)
        self.assertIn("Each default is a convention with no cited source", doc)
        params = inspect.signature(UnitAnalyzer.quality_metrics).parameters
        for name in ('refractory_ms', 'max_violation_pct', 'max_fano'):
            with self.subTest(cut_off=name):
                self.assertIn(f"``{name}={params[name].default!r}``", doc)
        self.assertIn("by the rule of :func:`jnwb.fano_factor`: the unbiased\n(``ddof=1``) variance", doc)
        self.assertNotIn("no spike in them", doc)   # the first window always holds a spike
        self.assertIn("the last one closed", doc)
        self.assertIn("are right-open", doc)

class TestPopulationAnalyzerTrajectory(unittest.TestCase):
    """Test PopulationAnalyzer.population_trajectory for dtype, device_used, and fallback."""

    def setUp(self):
        rng = np.random.default_rng(42)
        self.X_f64 = rng.standard_normal((50, 10), dtype=np.float64)
        self.X_f32 = rng.standard_normal((50, 10), dtype=np.float32)

    def test_preserves_float64_dtype_and_reports_device(self):
        res = PopulationAnalyzer.population_trajectory(self.X_f64, n_components=3)
        self.assertEqual(res['projection'].dtype, np.float64)
        self.assertEqual(res['components'].dtype, np.float64)
        self.assertEqual(res['explained_variance'].dtype, np.float64)
        self.assertEqual(res['explained_variance_ratio'].dtype, np.float64)
        self.assertIn('device_used', res)
        self.assertIn(res['device_used'], ('cpu', 'cuda'))

    def test_preserves_float32_dtype_and_reports_device(self):
        res = PopulationAnalyzer.population_trajectory(self.X_f32, n_components=3)
        self.assertEqual(res['projection'].dtype, np.float32)
        self.assertEqual(res['components'].dtype, np.float32)
        self.assertEqual(res['explained_variance'].dtype, np.float32)
        self.assertEqual(res['explained_variance_ratio'].dtype, np.float32)
        self.assertIn('device_used', res)
        self.assertIn(res['device_used'], ('cpu', 'cuda'))

    def test_fallback_warning_when_gpu_fails(self):
        import warnings
        from unittest.mock import patch

        with patch("jnwb.analyzers.resolve_device", return_value="cuda"):
            with blocked_import("cupy"):
                with patch("jnwb.analyzers.torch_cuda_available", return_value=False):
                    with warnings.catch_warnings(record=True) as w:
                        warnings.simplefilter("always")
                        res = PopulationAnalyzer.population_trajectory(self.X_f64, n_components=3, device="cuda")
                        self.assertEqual(res['device_used'], 'cpu')
                        runtime_warnings = [item for item in w if issubclass(item.category, RuntimeWarning)]
                        self.assertTrue(any("GPU computation failed" in str(item.message) for item in runtime_warnings))


class TestPopulationAnalyzerTrajectoryUnestimable(unittest.TestCase):
    """Components and variances that cannot be estimated are NaN, as in
    compute_population_trajectory."""

    def test_components_that_could_not_be_estimated_are_nan_not_missing(self):
        # Two units support two components; the other two do not exist.
        X = np.random.default_rng(42).standard_normal((50, 2))
        res = PopulationAnalyzer.population_trajectory(X, n_components=4)
        self.assertEqual(res['projection'].shape, (50, 4))
        self.assertEqual(res['components'].shape, (4, 2))
        self.assertTrue(np.all(np.isfinite(res['projection'][:, :2])))
        self.assertTrue(np.all(np.isnan(res['projection'][:, 2:])))
        self.assertTrue(np.all(np.isnan(res['components'][2:])))
        for key in ('explained_variance', 'explained_variance_ratio'):
            self.assertEqual(res[key].shape, (4,))
            self.assertTrue(np.all(np.isfinite(res[key][:2])) and np.all(np.isnan(res[key][2:])))
        np.testing.assert_allclose(np.nansum(res['explained_variance_ratio']), 1.0, rtol=1e-12)

    def test_a_population_with_no_variance_has_no_explained_variance(self):
        res = PopulationAnalyzer.population_trajectory(np.full((20, 5), 3.0), n_components=2)
        self.assertTrue(np.all(np.isnan(res['explained_variance_ratio'])))
        self.assertTrue(np.all(np.isnan(res['explained_variance'])))
        self.assertEqual(res['explained_variance_ratio'].shape, (2,))


class TestTFRAnalyzerCompareConditions(unittest.TestCase):
    """One t-test per location is a family; the count that answers "which differ" is corrected."""

    SHAPE = (4, 40, 100)          # 16000 locations

    def _pair(self, seed, effect=0.0):
        rng = np.random.default_rng(seed)
        a = rng.normal(size=self.SHAPE + (12,))
        b = rng.normal(size=self.SHAPE + (14,))
        b[0, :5] += effect        # 500 locations carry the effect, when there is one
        return a, b

    def test_null_data_leaves_the_fdr_count_near_zero_and_the_uncorrected_near_alpha_n(self):
        res = TFRAnalyzer.compare_conditions(*self._pair(0))
        n = res['n_tests']
        self.assertEqual(n, 16000)
        # Binomial(16000, 0.05): mean 800, sd 27.6.
        self.assertLess(abs(res['n_significant_uncorrected'] - 0.05 * n), 4 * 27.6)
        self.assertLessEqual(res['n_significant_fdr'], 2)
        self.assertEqual(res['fraction_significant_uncorrected'], res['n_significant_uncorrected'] / n)

    def test_the_fdr_count_is_the_library_correction_of_the_p_values(self):
        res = TFRAnalyzer.compare_conditions(*self._pair(1, effect=2.0))
        q = StatisticalAnalysis.fdr_correct(res['p_values'])
        np.testing.assert_allclose(res['q_values'], q, rtol=1e-12)
        self.assertEqual(res['n_significant_fdr'], int((q < 0.05).sum()))
        # The effect survives correction: the count is not zero by construction.
        self.assertGreater(res['n_significant_fdr'], 400)

    def test_a_location_without_a_p_value_is_not_in_the_family(self):
        a, b = self._pair(2)
        a[0, 0, 0] = 1.0
        b[0, 0, 0] = 1.0
        res = TFRAnalyzer.compare_conditions(a, b)
        self.assertTrue(np.isnan(res['q_values'][0]))
        tested = np.isfinite(res['p_values'])
        np.testing.assert_allclose(res['q_values'][tested],
                                   StatisticalAnalysis.fdr_correct(res['p_values'][tested]),
                                   rtol=1e-12)
        # The count and the uncorrected fraction use the family the FDR correction uses.
        self.assertEqual(res['n_tests'], int(tested.sum()))
        self.assertEqual(res['n_tests'], 16000 - 1)
        self.assertEqual(res['fraction_significant_uncorrected'],
                         res['n_significant_uncorrected'] / res['n_tests'])

    def test_no_location_with_a_p_value_is_an_empty_family(self):
        a = np.ones((2, 3, 4, 5))
        res = TFRAnalyzer.compare_conditions(a, a.copy())
        self.assertEqual(res['n_tests'], 0)
        self.assertEqual(res['n_significant_uncorrected'], 0)
        self.assertEqual(res['n_significant_fdr'], 0)
        self.assertTrue(np.isnan(res['fraction_significant_uncorrected']))

    def test_the_old_key_names_read_the_uncorrected_values_with_a_warning(self):
        res = TFRAnalyzer.compare_conditions(*self._pair(3))
        self.assertNotIn('n_significant', list(res))
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(res['n_significant'], res['n_significant_uncorrected'])
        with self.assertWarns(DeprecationWarning):
            self.assertEqual(res.get('fraction_significant'),
                             res['fraction_significant_uncorrected'])
        self.assertIn('n_significant', res)


if __name__ == '__main__':
    unittest.main(verbosity=2)

