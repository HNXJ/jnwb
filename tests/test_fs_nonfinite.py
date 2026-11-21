import numpy as np
import pytest

from jnwb import filtering, tfr


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_bandpass_refuses_nonfinite_fs(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="fs"):
        filtering.bandpass_filter(x, fs=bad, low_cut=1.0, high_cut=10.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_notch_refuses_nonfinite_fs(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="fs"):
        filtering.notch_filter(x, fs=bad, freq=60.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_complex_tfr_refuses_nonfinite_fs(bad):
    x = np.ones(400)
    with pytest.raises(ValueError, match="fs"):
        tfr.complex_tfr(x, fs=bad, freqs=np.array([10.0, 20.0]))
