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
    with pytest.raises(ValueError, match="epoch_continuous: fs must be finite"):
        continuous.epoch_continuous(x, [0.5], win_s=(0.0, 0.1), fs=bad)


@pytest.mark.parametrize("bad", ["1000", b"1000"])
def test_a_numeric_string_fs_is_refused_where_it_reached_arithmetic(bad):
    from jnwb.testing.synth import synth_phase_gradient

    with pytest.raises(ValueError, match="fs must be a number in Hz"):
        synth_phase_gradient(4, 1000, bad, rng=0)
    x = np.ones(2000)
    with pytest.raises(ValueError, match="epoch_continuous: fs must be a number in Hz"):
        continuous.epoch_continuous(x, [0.5], win_s=(0.0, 0.1), fs=bad)


@pytest.mark.parametrize("bad", [None, [1000.0], "1000", b"1000"])
def test_filters_refuse_nonnumeric_fs_as_value_error(bad):
    x = np.ones((2, 2000))
    with pytest.raises(ValueError, match="fs must be a number in Hz"):
        filtering.bandpass_filter(x, fs=bad, low_cut=1.0, high_cut=10.0)
    with pytest.raises(ValueError, match="fs must be a number in Hz"):
        filtering.notch_filter(x, fs=bad, freq=60.0)


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_complex_tfr_refuses_nonfinite_fs_by_name(bad):
    from jnwb.tfr import complex_tfr

    with pytest.raises(ValueError, match="complex_tfr: fs must be finite"):
        complex_tfr(np.ones(200), fs=bad, freqs=np.array([10.0]))


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_synth_laminar_motif_refuses_nonfinite_fs_by_name(bad):
    from jnwb.testing.synth import synth_laminar_motif

    with pytest.raises(ValueError, match="synth_laminar_motif: fs must be finite"):
        synth_laminar_motif(fs=bad, rng=0)
