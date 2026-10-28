"""A time window is required: left out, each of the four window functions raises.

`UnitAnalyzer.psth`, `UnitAnalyzer.raster`, `build_time_resolved_matrix` and
`compute_population_trajectory` defaulted their window to (-1000, 2000) ms with no cited
reason. The default warned from 0.2.14 and is removed in 0.2.15 (ruling 2026-10-24). A passed
window warns nothing. `psth` takes its window keyword-only, because `bin_size_ms` precedes it.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from jnwb import build_time_resolved_matrix, compute_population_trajectory
from jnwb.analyzers import UnitAnalyzer

SPIKES = np.array([0.5, 1.2, 2.1, 3.3, 4.4, 5.05, 5.5, 6.9])
ONSETS = np.array([2.0, 5.0])
OLD_DEFAULT = (-1000, 2000)


class _Session:
    """Two units in V1 with spikes on both sides of each onset."""

    units_df = pd.DataFrame({"unit_id": [0, 1], "area": ["V1", "V1"], "quality": ["good"] * 2})
    epochs_df = pd.DataFrame({"start_time": ONSETS})

    def get_units(self, quality=None, area=None):
        df = self.units_df
        return df[df["area"] == area] if area else df

    def get_spike_times(self, unit_id):
        return SPIKES + 0.01 * unit_id


def test_psth_without_window_ms_raises():
    with pytest.raises(TypeError, match="window_ms"):
        UnitAnalyzer.psth(SPIKES, ONSETS, bin_size_ms=100)


def test_psth_window_ms_is_keyword_only():
    with pytest.raises(TypeError):
        UnitAnalyzer.psth(SPIKES, ONSETS, 100, OLD_DEFAULT)


def test_raster_without_window_ms_raises():
    with pytest.raises(TypeError, match="window_ms"):
        UnitAnalyzer.raster(SPIKES, ONSETS)


def test_time_resolved_matrix_without_time_window_ms_raises():
    s = _Session()
    with pytest.raises(TypeError, match="time_window_ms"):
        build_time_resolved_matrix(s, "V1", s.epochs_df, bin_size_ms=100)


def test_population_trajectory_without_time_window_ms_raises():
    s = _Session()
    with pytest.raises(TypeError, match="time_window_ms"):
        compute_population_trajectory(s, "V1", s.epochs_df, bin_size_ms=100, n_components=1)


def test_passed_windows_warn_nothing_and_give_the_old_span():
    s = _Session()
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        psth = UnitAnalyzer.psth(SPIKES, ONSETS, bin_size_ms=100, window_ms=OLD_DEFAULT)
        raster = UnitAnalyzer.raster(SPIKES, ONSETS, window_ms=OLD_DEFAULT)
        matrix, _, _ = build_time_resolved_matrix(s, "V1", s.epochs_df, OLD_DEFAULT,
                                                  bin_size_ms=100)
        traj = compute_population_trajectory(s, "V1", s.epochs_df, OLD_DEFAULT,
                                             bin_size_ms=100, n_components=1)
    assert psth["bin_centers_ms"][0] == pytest.approx(-950.0), "bins must start at -1000 ms"
    assert np.nansum(psth["psth"]) > 0, "the fixture must put spikes in the window"
    assert raster["window_ms"] == OLD_DEFAULT
    assert raster["n_spikes"] > 0, "the fixture must put spikes in the window"
    assert matrix.sum() > 0, "the fixture must put spikes in the window"
    assert traj["bin_centers"][0] == pytest.approx(-950.0)
