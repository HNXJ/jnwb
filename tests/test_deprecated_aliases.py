"""Deprecated spellings warn, name their replacement and return what the replacement returns."""

import numpy as np
import pytest

import jnwb

WINDOW = (0.0, 20.0)


def _spike_trains():
    """Two trains that share occupied bins, with repeats so per-bin counts reach 2."""
    rng = np.random.default_rng(4)
    centres = (np.arange(2000) + 0.5) * 0.010
    occupied = centres[rng.random(2000) < 0.3]
    s1 = np.sort(np.concatenate([occupied, occupied[:50]]))
    s2 = centres[(rng.random(2000) < 0.3) | np.isin(centres, occupied)]
    return s1, s2


@pytest.mark.parametrize(("alias", "estimator"), [
    ("binary_occupancy_mutual_information", "binary_occupancy"),
    ("spike_count_mutual_information", "spike_count"),
])
def test_mi_alias_warns_and_returns_what_spike_mutual_information_returns(alias, estimator):
    s1, s2 = _spike_trains()
    replacement = jnwb.spike_mutual_information(
        s1, s2, time_window_s=WINDOW, bin_size_ms=10.0, estimator=estimator)
    assert replacement > 0, "fixture must carry mutual information"
    with pytest.warns(DeprecationWarning, match="spike_mutual_information"):
        value = getattr(jnwb, alias)(s1, s2, time_window_s=WINDOW, bin_size_ms=10.0)
    np.testing.assert_array_equal(value, replacement)


def test_clopper_pearson_ci_warns_and_returns_what_clopper_pearson_returns():
    replacement = jnwb.clopper_pearson(3, 10, alpha=0.10)
    assert replacement[0] < 0.3 < replacement[1], "fixture must give a real interval"
    with pytest.warns(DeprecationWarning, match="clopper_pearson"):
        value = jnwb.StatisticalAnalysis.clopper_pearson_ci(3, 10, alpha=0.10)
    np.testing.assert_array_equal(value, replacement)
