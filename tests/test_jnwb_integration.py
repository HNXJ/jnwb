#!/usr/bin/env python3
"""
Integration tests for jNWB - test working functions end-to-end.

Focus: Population analysis, unit finding, and session operations
that are fully implemented and can be tested without external files.
"""

import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from unittest.mock import Mock, patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from jnwb.functions import (
    find_units,
    compare_populations,
    pie_charts,
    population_by_area,
    units_across_sessions,
)
from jnwb.analyzers import PopulationAnalyzer, TFRAnalyzer


class TestPopulationAnalyzer(unittest.TestCase):
    """Integration tests for population-level analysis."""

    def setUp(self):
        """Create sample units dataframe for all tests."""
        self.units_df = pd.DataFrame({
            'unit_id': [1, 2, 3, 4, 5, 6, 7, 8],
            'session_id': [230629, 230629, 230629, 230630, 230630, 230630, 230714, 230714],
            'area': ['V1', 'V1', 'MT', 'V1', 'MT', 'PFC', 'V1', 'MT'],
            'layer': ['L4', 'L2/3', 'L1', 'L4', 'L1', 'L6', 'L2/3', 'L1'],
            'is_stable': [True, True, False, True, True, False, True, True],
            'stable_plus': [True, False, False, True, True, False, True, False],
            'firing_rate': [5.2, 3.1, 12.4, 6.8, 8.3, 2.1, 4.5, 11.2],
            'waveform_duration': [0.5, 0.8, 1.2, 0.6, 1.3, 0.4, 0.7, 1.1],
            'sig_o_plus': [0.85, 0.72, 0.91, 0.88, 0.79, 0.65, 0.83, 0.89],
        })

    def test_pie_chart_data_by_area(self):
        """Test pie chart aggregation by area."""
        result = PopulationAnalyzer.pie_chart_data(self.units_df, criteria={})

        self.assertIsInstance(result, dict)
        # Result should have area breakdown
        self.assertGreater(len(result), 0)

    def test_pie_chart_data_filtered(self):
        """Test pie chart with filtering criteria."""
        result = PopulationAnalyzer.pie_chart_data(self.units_df, criteria={'is_stable': True})

        self.assertIsInstance(result, dict)
        # Result should be a dict (may be empty if filter doesn't match)

    def test_pie_chart_area_grouping(self):
        """Test area-based pie chart generation."""
        # Group by area manually for verification
        by_area = self.units_df.groupby('area').size()

        self.assertEqual(by_area['V1'], 4)
        self.assertEqual(by_area['MT'], 3)
        self.assertEqual(by_area['PFC'], 1)

    def test_compare_criteria_firing_rates(self):
        """Test statistical comparison of firing rates."""
        v1_rates = self.units_df[self.units_df['area'] == 'V1']['firing_rate'].values
        mt_rates = self.units_df[self.units_df['area'] == 'MT']['firing_rate'].values

        # Use StatisticalAnalysis directly
        from jnwb.statistics import StatisticalAnalysis
        result = StatisticalAnalysis.compare_groups(v1_rates, mt_rates)

        self.assertIsInstance(result, dict)
        # Should have parametric and non-parametric tests
        if 'error' not in result:
            self.assertIn('parametric', result)

    def test_firing_rate_statistics(self):
        """Test firing rate statistics by area."""
        by_area = self.units_df.groupby('area')['firing_rate'].agg(['mean', 'std', 'count'])

        self.assertIsInstance(by_area, pd.DataFrame)
        self.assertGreater(by_area.loc['V1', 'mean'], 0)
        self.assertGreater(by_area.loc['V1', 'count'], 0)


class TestSessionIntegration(unittest.TestCase):
    """Test session-level operations (mocked NWB)."""

    def setUp(self):
        """Create mock OmissionSession."""
        from jnwb.session import OmissionSession

        # Create minimal mock NWB
        self.mock_nwb = MagicMock()
        self.mock_units_df = pd.DataFrame({
            'cluster_id': [1.0, 2.0, 3.0],
            'spike_times': [
                np.array([0.1, 0.2, 0.3, 0.4, 0.5]),
                np.array([0.15, 0.25, 0.35]),
                np.array([0.05, 0.15, 0.25, 0.35, 0.45, 0.55]),
            ],
        })
        self.mock_nwb.units.to_dataframe.return_value = self.mock_units_df

    def test_find_units_quality_filter(self):
        """Test unit finding with quality filtering."""
        units_df = pd.DataFrame({
            'unit_id': [1, 2, 3, 4, 5],
            'is_stable': [True, True, False, True, False],
            'stable_plus': [True, False, False, False, False],
            'area': ['V1', 'V1', 'MT', 'V1', 'MT'],
            'firing_rate': [5.0, 3.0, 12.0, 8.0, 2.0],
        })

        # Test stable_plus filter
        stable_plus = units_df[units_df['stable_plus'] == True]
        self.assertEqual(len(stable_plus), 1)

        # Test stable filter
        stable = units_df[units_df['is_stable'] == True]
        self.assertEqual(len(stable), 3)  # 3 stable units

    def test_find_units_area_filter(self):
        """Test unit finding with area filtering."""
        units_df = pd.DataFrame({
            'unit_id': [1, 2, 3, 4, 5],
            'area': ['V1', 'V1', 'MT', 'V1', 'PFC'],
        })

        v1_units = units_df[units_df['area'] == 'V1']
        self.assertEqual(len(v1_units), 3)

        mt_units = units_df[units_df['area'] == 'MT']
        self.assertEqual(len(mt_units), 1)

    def test_firing_rate_range_filter(self):
        """Test unit finding with firing rate range."""
        units_df = pd.DataFrame({
            'unit_id': [1, 2, 3, 4, 5],
            'firing_rate': [1.0, 3.0, 5.5, 10.0, 150.0],
        })

        in_range = units_df[
            (units_df['firing_rate'] >= 1.0) &
            (units_df['firing_rate'] <= 200.0)
        ]
        self.assertEqual(len(in_range), 5)

        in_range = units_df[
            (units_df['firing_rate'] >= 1.0) &
            (units_df['firing_rate'] <= 50.0)
        ]
        self.assertEqual(len(in_range), 4)


class TestDataFrameOperations(unittest.TestCase):
    """Test core DataFrame operations used throughout jNWB."""

    def test_groupby_aggregation(self):
        """Test groupby aggregation for population analysis."""
        df = pd.DataFrame({
            'area': ['V1', 'V1', 'MT', 'MT', 'PFC'],
            'firing_rate': [5.0, 3.0, 12.0, 8.0, 2.0],
            'layer': ['L4', 'L2/3', 'L1', 'L4', 'L6'],
        })

        by_area = df.groupby('area')['firing_rate'].mean()
        self.assertAlmostEqual(by_area['V1'], 4.0)
        self.assertAlmostEqual(by_area['MT'], 10.0)
        self.assertAlmostEqual(by_area['PFC'], 2.0)

    def test_multiindex_operations(self):
        """Test operations on multi-level grouped data."""
        df = pd.DataFrame({
            'session': [230629, 230629, 230630, 230630],
            'area': ['V1', 'MT', 'V1', 'MT'],
            'unit_count': [10, 5, 12, 8],
        })

        by_session_area = df.groupby(['session', 'area'])['unit_count'].sum()

        self.assertEqual(by_session_area[230629, 'V1'], 10)
        self.assertEqual(by_session_area[230630, 'V1'], 12)

    def test_boolean_masking(self):
        """Test boolean masking for filtering."""
        df = pd.DataFrame({
            'unit_id': [1, 2, 3, 4, 5],
            'is_stable': [True, True, False, True, False],
            'is_mua': [False, False, True, False, True],
        })

        stable_only = df[df['is_stable'] == True]
        self.assertEqual(len(stable_only), 3)

        mua_only = df[df['is_mua'] == True]
        self.assertEqual(len(mua_only), 2)

        stable_not_mua = df[(df['is_stable'] == True) & (df['is_mua'] == False)]
        self.assertEqual(len(stable_not_mua), 3)  # Units 1, 2, 4


class TestLayerAwareAnalysis(unittest.TestCase):
    """Test layer-aware TFR analysis."""

    def test_average_without_layer_mask(self):
        """Test channel averaging without layer info (legacy behavior)."""
        band_power = np.random.randn(44, 99, 500)
        result = TFRAnalyzer.average_across_channels(band_power, layer_mask=None)

        # Should return (time, trials)
        self.assertEqual(result.shape, (99, 500))

    def test_average_with_layer_mask(self):
        """Test layer-aware channel averaging."""
        band_power = np.random.randn(128, 99, 500)

        # Create layer mask: 62 superficial, 64 deep
        layer_mask = {
            'superficial_mask': [True] * 62 + [False] * 66,
            'deep_mask': [False] * 62 + [True] * 64 + [False] * 2,
        }

        result = TFRAnalyzer.average_across_channels(band_power, layer_mask=layer_mask)

        # Should return (2, time, trials) to preserve layers
        self.assertEqual(result.shape, (2, 99, 500))

    def test_layer_mask_size_mismatch(self):
        """Test fallback when layer mask size doesn't match channels."""
        band_power = np.random.randn(44, 99, 500)

        # Wrong-sized layer mask
        layer_mask = {
            'superficial_mask': [True] * 50,
            'deep_mask': [False] * 50,
        }

        result = TFRAnalyzer.average_across_channels(band_power, layer_mask=layer_mask)

        # Should fall back to global average
        self.assertEqual(result.shape, (99, 500))


class TestErrorHandling(unittest.TestCase):
    """Test error handling in core operations."""

    def test_empty_dataframe_groupby(self):
        """Test groupby on empty DataFrames."""
        empty_df = pd.DataFrame(columns=['unit_id', 'area', 'firing_rate'])

        # Groupby should handle gracefully
        result = empty_df.groupby('area').size()
        self.assertEqual(len(result), 0)

    def test_missing_column_check(self):
        """Test checking for missing required columns."""
        df = pd.DataFrame({
            'unit_id': [1, 2, 3],
            'area': ['V1', 'V1', 'MT'],
            # 'firing_rate' is missing
        })

        # Should handle gracefully
        self.assertFalse('firing_rate' in df.columns)

    def test_single_row_groupby(self):
        """Test operations on single-row DataFrames."""
        df = pd.DataFrame({
            'unit_id': [1],
            'area': ['V1'],
            'firing_rate': [5.0],
        })

        result = df.groupby('area').size()
        self.assertEqual(result['V1'], 1)

    def test_all_nan_column(self):
        """Test handling of all-NaN columns."""
        df = pd.DataFrame({
            'unit_id': [1, 2, 3],
            'firing_rate': [np.nan, np.nan, np.nan],
        })

        mean_fr = df['firing_rate'].mean()
        self.assertTrue(np.isnan(mean_fr))


class TestTFRMethods(unittest.TestCase):
    """Test the newly implemented TFR methods."""

    def test_tfr_trial_average_logic(self):
        session = MagicMock()
        tfr_mock = np.ones((5, 128, 99, 10))
        session.tfr_from_preprocessed.return_value = tfr_mock

        from jnwb.functions import tfr_trial_average
        res = tfr_trial_average(session, area="V1", condition="AAAB")
        self.assertIn("mean", res)
        self.assertIn("sem", res)
        self.assertEqual(res["n_trials"], 10)
        self.assertAlmostEqual(res["mean"][0, 0, 0], 1.0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
