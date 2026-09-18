"""Unit tests for the population trajectory analysis module."""

import numpy as np
import pandas as pd
import pytest
from jnwb import (
    build_time_resolved_matrix,
    compute_population_trajectory,
)

class MockSession:
    """Mock matching the real OmissionSession identity convention: 'unit_id' is a per-probe
    kilosort cluster id that can have gaps relative to the row index (deliberately offset here,
    e.g. row 0 -> unit_id 5, not 1), while get_spike_times's real primary lookup is by raw
    units_df row-index position. This mirrors the real, confirmed bug found in
    jnwb.trajectory.build_time_resolved_matrix (fixed 2026-07-12): it used to pass the 'unit_id'
    column to get_spike_times instead of the row index, which silently fetched the wrong unit's
    spikes whenever kilosort ids had gaps (verified on sub-C31o_ses-230816_rec)."""
    def __init__(self):
        self.units_df = pd.DataFrame({
            'unit_id': [5, 8, 12],  # deliberately NOT equal to row index 0, 1, 2
            'area': ['V1', 'V1', 'V4'],
            'quality': ['stable_plus', 'stable', 'stable_plus']
        })
        self.epochs_df = pd.DataFrame({
            'start_time': [1.0, 2.0, 3.0, 4.0],
            'condition': ['AAAB', 'BBBA', 'AAAB', 'BBBA']
        })
        # Mock spike times, keyed by row-index position (the real identity convention),
        # NOT by the 'unit_id' column.
        self.spikes = {
            0: np.array([1.01, 1.05, 2.02, 3.01, 3.05, 4.02]),
            1: np.array([1.02, 2.03, 3.02, 4.03]),
            2: np.array([1.03, 2.04, 3.03, 4.04])
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
    # unit_ids must be the raw row-index positions (0, 1), NOT the 'unit_id' column (5, 8) --
    # regression test for the real misattribution bug fixed 2026-07-12.
    assert unit_ids == [0, 1]
    assert len(bin_centers) == 5
    assert np.allclose(bin_centers, [10.0, 30.0, 50.0, 70.0, 90.0])
    # The fetched spike counts must match each unit's OWN mocked spike train (keyed by index),
    # not another unit's -- this is exactly what the bug silently corrupted.
    assert X[:, 0, :].sum() == 6  # unit at row 0 has 6 mock spikes
    assert X[:, 1, :].sum() == 4  # unit at row 1 has 4 mock spikes


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
    """05-25. An explicitly requested population with no observations yields an
    *unavailable* estimate, never zero. Zeros are a point in state space like any other, so
    the fabricated version put the population at the origin and reported
    `explained_variance == 0.0` -- "PCA ran and explained nothing" rather than "PCA did not
    run". `TFRAnalyzer.average_across_channels` already answers NaN for the same condition
    (`test_analyzers_coverage.py::test_empty_layer_mask_returns_nan_not_zeros`); this is
    the package-wide policy, and `AGENTS.md` invariant 1.
    """
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
    assert np.all(np.isnan(res['trajectory']))
    assert np.isnan(res['explained_variance'])
    assert res['unit_ids'] == []
    # The bins themselves were requested, not estimated, so they stay real.
    assert np.all(np.isfinite(res['bin_centers']))


def test_components_that_could_not_be_estimated_are_not_zero():
    """Padding to `n_components` with 0.0 made a component that does not exist look like a
    component whose projection was measured to be zero. One unit supports one component.
    """
    session = MockSession()
    res = compute_population_trajectory(
        session,
        area='V1',
        epochs_df=session.epochs_df,
        time_window_ms=(0.0, 100.0),
        bin_size_ms=20.0,
        n_components=8,
    )
    n_real = len(res['unit_ids'])
    assert 0 < n_real < 8
    assert np.all(np.isfinite(res['trajectory'][:, :n_real, :]))
    assert np.all(np.isnan(res['trajectory'][:, n_real:, :]))


def test_a_population_with_no_variance_has_no_explained_variance_ratio():
    """`total_var == 0` is not a ratio of zero; there is no ratio."""
    session = MockSession()
    session.spikes = {k: np.array([]) for k in session.spikes}
    res = compute_population_trajectory(
        session,
        area='V1',
        epochs_df=session.epochs_df,
        time_window_ms=(0.0, 100.0),
        bin_size_ms=20.0,
        n_components=2,
    )
    assert np.isnan(res['explained_variance'])


class TestPopulationTrajectoryEstimandDivergence:
    """Discriminating tests between covariance PCA (centering only) and correlation PCA (standardization)."""

    def test_divergence_on_unequal_variance_features(self):
        """Verify that covariance PCA and correlation PCA produce mathematically distinct components and variance ratios."""
        from jnwb.analyzers import PopulationAnalyzer
        rng = np.random.default_rng(42)
        # 100 samples with 3 features of drastically different scales: 100.0, 1.0, 0.01
        X = np.column_stack([
            rng.normal(0, 100.0, 100),
            rng.normal(0, 1.0, 100),
            rng.normal(0, 0.01, 100),
        ])

        # PopulationAnalyzer.population_trajectory uses unstandardized covariance PCA
        res_cov = PopulationAnalyzer.population_trajectory(X, n_components=2)
        # Covariance PCA: feature 0 dominates first component (>99.9% of variance)
        assert res_cov['explained_variance_ratio'][0] > 0.99
        assert abs(res_cov['components'][0, 0]) > 0.99

        # Standardized correlation PCA (as used in compute_population_trajectory / gpu_pca)
        from jnwb.gpu_pca import gpu_pca
        proj_corr, comp_corr, ev_ratio_corr = gpu_pca(X, n_components=2, device="cpu")
        # Correlation PCA: features are standardized, so feature 0 does NOT dominate (>90%)
        # All 3 features have comparable variance (~33% each)
        assert ev_ratio_corr < 0.85
        assert abs(comp_corr[0, 0]) < 0.85

        # Projections are mathematically distinct and not equivalent
        # Standardizing changes the subspace orientation
        assert not np.allclose(res_cov['projection'], proj_corr)


class TestComputePopulationTrajectoryDeviceFallback:
    """Verify that device='cuda' on denied GPU warns via resolve_device and produces CPU results."""

    def test_denied_gpu_warns_and_computes(self, monkeypatch):
        import jnwb._backend as backend
        monkeypatch.setattr(backend, "gpu_available", lambda prefer=None: False)

        session = MockSession()
        with pytest.warns(RuntimeWarning, match="device='cuda' was requested but no usable CUDA device was found"):
            res = compute_population_trajectory(
                session,
                area='V1',
                epochs_df=session.epochs_df,
                time_window_ms=(0.0, 100.0),
                bin_size_ms=20.0,
                n_components=2,
                device="cuda",
            )
        assert res['trajectory'].shape == (4, 2, 5)
        assert 0.0 <= res['explained_variance'] <= 1.0


