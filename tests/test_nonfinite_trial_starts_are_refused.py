"""A NaN trial start or epoch onset is refused at every site that reads one.

A non-finite trial time made its trial count zero spikes, or merged every trial into one cycle,
with no error. Each site is driven twice: with one NaN, which must raise a ValueError naming the
function, the argument and the first bad index; and with finite times, which must still return a
result holding something to examine. The finite case is the control: a refusal that fires on
every input proves nothing, and an empty result proves nothing either.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from jnwb import build_time_resolved_matrix
from jnwb.analyzers import UnitAnalyzer
from jnwb.connectivity import bin_spikes
from jnwb.spiking import compute_response_metrics
from jnwb.statistics import assign_subblock_quartiles, detect_trial_cycles
from jnwb.viz import raster_psth

SPIKES = np.array([0.01, 0.05, 1.01, 2.02])
STARTS = np.array([0.0, 1.0, 2.0, 1000.0])


class _Session:
    """One area with two units, each firing at the same times."""

    def get_units(self, quality=None, area=None):
        return pd.DataFrame({"unit_id": [0, 1], "area": ["V1", "V1"]})

    def get_spike_times(self, unit_id):
        return SPIKES


def _bin(starts):
    return bin_spikes(SPIKES, window_s=(0.0, 0.2), bin_size_ms=100.0, trial_starts=starts)


def _trajectory(starts):
    epochs = pd.DataFrame({"start_time": starts})
    X, _, _ = build_time_resolved_matrix(_Session(), area="V1", epochs_df=epochs,
                                         time_window_ms=(0.0, 100.0), bin_size_ms=20.0)
    return X


def _response(onsets):
    return compute_response_metrics(SPIKES, onsets)["response_counts"]


def _cycles(starts):
    return detect_trial_cycles(pd.DataFrame({"start_time": starts}))


def _quartiles(starts):
    return assign_subblock_quartiles(pd.DataFrame({"start_time": starts}))


def _raster(onsets):
    raster = UnitAnalyzer.raster(SPIKES, onsets, window_ms=(-100, 100))["raster"]
    return np.array([len(trial["spike_times"]) for trial in raster])


def _psth(onsets):
    return UnitAnalyzer.psth(SPIKES, onsets, bin_size_ms=50, window_ms=(-100, 100))["psth"]


def _raster_psth(onsets):
    return raster_psth(SPIKES, onsets, (-100, 100), bin_ms=50.0)[1]


SITES = [
    pytest.param(_bin, "bin_spikes", "trial_starts", id="bin_spikes"),
    pytest.param(_trajectory, "build_time_resolved_matrix", "start_time",
                 id="build_time_resolved_matrix"),
    pytest.param(_response, "compute_response_metrics", "epoch_onsets",
                 id="compute_response_metrics"),
    pytest.param(_cycles, "detect_trial_cycles", "start_time", id="detect_trial_cycles"),
    pytest.param(_quartiles, "assign_subblock_quartiles", "start_time",
                 id="assign_subblock_quartiles"),
    pytest.param(_raster, "UnitAnalyzer.raster", "trial_onsets", id="UnitAnalyzer.raster"),
    pytest.param(_psth, "UnitAnalyzer.psth", "trial_onsets", id="UnitAnalyzer.psth"),
    pytest.param(_raster_psth, "raster_psth", "onsets", id="raster_psth"),
]


@pytest.mark.parametrize("call, func, arg", SITES)
def test_one_nan_start_is_refused_by_name_and_index(call, func, arg):
    bad = STARTS.copy()
    bad[1] = np.nan
    with pytest.raises(ValueError) as err:
        call(bad)
    message = str(err.value)
    assert "nan" in message
    assert f"{func}: {arg}[1] is nan" in message


@pytest.mark.parametrize("call, func, arg", SITES)
def test_finite_starts_still_return_a_result(call, func, arg):
    result = np.asarray(call(STARTS))
    assert result.size > 0 and np.any(result), f"{func}({arg}=finite) returned nothing to examine"
