"""A time window left to its default warns that it becomes required in 0.2.15.

`UnitAnalyzer.psth`, `UnitAnalyzer.raster`, `build_time_resolved_matrix` and
`compute_population_trajectory` defaulted their window to (-1000, 2000) ms with no cited
reason. An omitted window still gives that span, with a FutureWarning; a passed one warns
nothing.
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


_WINDOW = {
    "UnitAnalyzer.psth": "window_ms",
    "UnitAnalyzer.raster": "window_ms",
    "build_time_resolved_matrix": "time_window_ms",
    "compute_population_trajectory": "time_window_ms",
}


def _omitted_and_passed(call, name):
    """The result with the window omitted, which must warn, and with it passed."""
    with pytest.warns(FutureWarning, match=rf"{name}: .*required in 0\.2\.15"):
        omitted = call({})
    with warnings.catch_warnings():
        warnings.simplefilter("error", FutureWarning)
        passed = call({_WINDOW[name]: OLD_DEFAULT})
    return omitted, passed


@pytest.mark.parametrize("name", ["binary_occupancy_mutual_information",
                                  "spike_count_mutual_information"])
def test_the_deprecated_mi_aliases_raise_with_neither_window_spelling(name):
    """B3 excuses their `None` windows because a call with neither spelling raises."""
    import jnwb
    with pytest.warns(DeprecationWarning), \
            pytest.raises(ValueError, match="requires time_window_s"):
        getattr(jnwb, name)(SPIKES, SPIKES + 0.001)


def test_psth_without_window_ms_warns_and_uses_the_old_span():
    omitted, passed = _omitted_and_passed(
        lambda kw: UnitAnalyzer.psth(SPIKES, ONSETS, bin_size_ms=100, **kw), "UnitAnalyzer.psth")
    np.testing.assert_array_equal(omitted["bin_centers"], passed["bin_centers"])
    assert passed["bin_centers"][0] == pytest.approx(-0.95), "bins must start at -1000 ms"
    np.testing.assert_array_equal(omitted["psth"], passed["psth"])
    assert np.nansum(passed["psth"]) > 0, "the fixture must put spikes in the window"


def test_raster_without_window_ms_warns_and_uses_the_old_span():
    omitted, passed = _omitted_and_passed(
        lambda kw: UnitAnalyzer.raster(SPIKES, ONSETS, **kw), "UnitAnalyzer.raster")
    assert omitted["window_ms"] == passed["window_ms"] == OLD_DEFAULT
    assert omitted["n_spikes"] == passed["n_spikes"] > 0


def test_time_resolved_matrix_without_time_window_ms_warns_and_uses_the_old_span():
    s = _Session()
    omitted, passed = _omitted_and_passed(
        lambda kw: build_time_resolved_matrix(s, "V1", s.epochs_df, bin_size_ms=100, **kw),
        "build_time_resolved_matrix")
    np.testing.assert_array_equal(omitted[0], passed[0])
    np.testing.assert_array_equal(omitted[2], passed[2])
    assert passed[0].sum() > 0, "the fixture must put spikes in the window"


def test_population_trajectory_without_time_window_ms_warns_once_under_its_own_name():
    s = _Session()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        compute_population_trajectory(s, "V1", s.epochs_df, bin_size_ms=100, n_components=1)
    future = [w for w in caught if issubclass(w.category, FutureWarning)]
    assert len(future) == 1, [str(w.message) for w in future]
    assert str(future[0].message).startswith("compute_population_trajectory: ")
    omitted, passed = _omitted_and_passed(
        lambda kw: compute_population_trajectory(s, "V1", s.epochs_df, bin_size_ms=100,
                                                 n_components=1, **kw),
        "compute_population_trajectory")
    np.testing.assert_array_equal(omitted["bin_centers"], passed["bin_centers"])
