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


class TestAutocorrelogramRefractoryTestIsWithdrawn(unittest.TestCase):
    """The test took the Poisson upper tail of the bin covering about 5.5 to 6.5 ms (centre
    about 6 ms), so an over-filled bin read as a single unit and an empty one did not."""

    KEYS = ('refractory_period_violation', 'refr_count', 'baseline_count')

    @staticmethod
    def _trains():
        rng = np.random.default_rng(0)
        background = np.sort(rng.uniform(0.0, 600.0, 12000))
        # Every spike has a partner 6 ms later: the tested bin is over-filled.
        contaminated = np.sort(np.concatenate([background, background + 0.006]))
        # A 10 ms dead time after every spike: a clean refractory dip.
        clean = np.cumsum(0.010 + rng.exponential(0.05, 12000))
        return {'contaminated': contaminated, 'clean dip': clean}

    def test_no_train_reads_as_a_single_unit_and_the_keys_are_withdrawn(self):
        for name, train in self._trains().items():
            with self.subTest(train=name):
                with self.assertWarnsRegex(FutureWarning, r"inverted.*0\.2\.7.*quality_metrics"):
                    result = UnitAnalyzer.autocorrelogram(train, max_lag_ms=50, bin_size_ms=1)
                self.assertIsNone(result['is_single_unit'])
                for key in self.KEYS:
                    self.assertIsInstance(result[key], float)
                    self.assertTrue(np.isnan(result[key]), key)
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



if __name__ == '__main__':
    unittest.main(verbosity=2)

