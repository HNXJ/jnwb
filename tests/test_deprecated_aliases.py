"""The removed mutual-information aliases are in no export; their replacement estimators carry information."""

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


@pytest.mark.parametrize("estimator", ["binary_occupancy", "spike_count"])
def test_the_replacement_estimators_carry_information(estimator):
    s1, s2 = _spike_trains()
    replacement = jnwb.spike_mutual_information(
        s1, s2, time_window_s=WINDOW, bin_size_ms=10.0, estimator=estimator)
    assert replacement > 0, "fixture must carry mutual information"


def test_the_spike_estimator_is_the_only_mutual_information_name_reached():
    reached = [name for name in dir(jnwb) if name.endswith("mutual_information")]
    assert reached == ["spike_mutual_information"], reached
    exported = [name for name in jnwb.__all__ if name.endswith("mutual_information")]
    assert exported == ["spike_mutual_information"], exported
    connected = [name for name in dir(jnwb.connectivity) if name.endswith("mutual_information")]
    assert connected == ["spike_mutual_information"], connected
