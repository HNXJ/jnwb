import numpy as np
import pytest

from jnwb import continuous, filtering


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_bandpass_refuses_nonfinite_fs(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="bandpass_filter: fs must be finite"):
        filtering.bandpass_filter(x, fs=bad, low_cut=1.0, high_cut=10.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_notch_refuses_nonfinite_fs(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="notch_filter: fs must be finite"):
        filtering.notch_filter(x, fs=bad, freq=60.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_epoch_continuous_refuses_nonfinite_fs(bad):
    x = np.ones(2000)
    with pytest.raises(ValueError, match="Sampling rate fs must be positive"):
        continuous.epoch_continuous(x, [0.5], win_s=(0.0, 0.1), fs=bad)


@pytest.mark.parametrize("bad", [None, [1000.0]])
def test_filters_refuse_nonnumeric_fs_as_value_error(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="fs must be a number in Hz"):
        filtering.bandpass_filter(x, fs=bad, low_cut=1.0, high_cut=10.0)
    with pytest.raises(ValueError, match="fs must be a number in Hz"):
        filtering.notch_filter(x, fs=bad, freq=60.0)
