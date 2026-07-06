"""
Unit tests for the population trajectory analysis module.

Author: Antigravity
Date: 2026-07-04
"""

import numpy as np
import pandas as pd
import pytest
from jnwb import (
    build_time_resolved_matrix,
    compute_population_trajectory
)

class MockSession:
    def __init__(self):
        self.units_df = pd.DataFrame({
            'unit_id': [1, 2, 3],
            'area': ['V1', 'V1', 'V4'],
            'quality': ['stable_plus', 'stable', 'stable_plus']
        })
        self.epochs_df = pd.DataFrame({
            'start_time': [1.0, 2.0, 3.0, 4.0],
            'condition': ['AAAB', 'BBBA', 'AAAB', 'BBBA']
        })
        # Mock spike times
        self.spikes = {
            1: np.array([1.01, 1.05, 2.02, 3.01, 3.05, 4.02]),
            2: np.array([1.02, 2.03, 3.02, 4.03]),
            3: np.array([1.03, 2.04, 3.03, 4.04])
        }

    def get_units(self, quality=None, area=None):
        df = self.units_df.copy()
        if quality:
            df = df[df['quality'] == quality]
        if area:
            df = df[df['area'] == area]
        return df

    def get_spike_times(self, unit_id):
        return self.spikes.get(unit_id, np.array([]))


def test_build_time_resolved_matrix():
    session = MockSession()
    
    # Extract time resolved spike matrix for V1
    X, unit_ids, bin_centers = build_time_resolved_matrix(
        session,
        area='V1',
        epochs_df=session.epochs_df,
        time_window_ms=(0.0, 100.0),
        bin_size_ms=20.0
    )
    
    # 4 trials, 2 V1 units, 5 bins (0-20, 20-40, 40-60, 60-80, 80-100 ms)
    assert X.shape == (4, 2, 5)
    assert len(unit_ids) == 2
    assert unit_ids == [1, 2]
    assert len(bin_centers) == 5
    assert np.allclose(bin_centers, [10.0, 30.0, 50.0, 70.0, 90.0])


def test_compute_population_trajectory():
    session = MockSession()
    
    # Compute PCA trajectory
    res = compute_population_trajectory(
        session,
        area='V1',
        epochs_df=session.epochs_df,
        time_window_ms=(0.0, 100.0),
        bin_size_ms=20.0,
        n_components=2
    )
    
    assert 'trajectory' in res
    assert 'explained_variance' in res
    assert 'unit_ids' in res
    assert 'bin_centers' in res
    
    # Check shape: (n_trials, n_components, n_bins) -> (4, 2, 5)
    assert res['trajectory'].shape == (4, 2, 5)
    assert isinstance(res['explained_variance'], float)
    assert 0.0 <= res['explained_variance'] <= 1.0


def test_compute_population_trajectory_empty():
    session = MockSession()
    
    # Area with no units
    res = compute_population_trajectory(
        session,
        area='NONEXISTENT',
        epochs_df=session.epochs_df,
        time_window_ms=(0.0, 100.0),
        bin_size_ms=20.0,
        n_components=2
    )
    
    assert res['trajectory'].shape == (4, 2, 5)
    assert np.all(res['trajectory'] == 0.0)
    assert res['explained_variance'] == 0.0
