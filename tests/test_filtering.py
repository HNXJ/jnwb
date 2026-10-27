"""Adversarial and analytical recovery tests for jnwb.filtering (SOS bandpass and notch)."""
from __future__ import annotations

import numpy as np
import pytest
from scipy import signal

import jnwb
from jnwb.filtering import bandpass_filter, notch_filter


class TestBandpassFilter:
    def test_passband_preservation_and_stopband_attenuation(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        x_pass = np.sin(2 * np.pi * 20.0 * t)
        x_stop = np.sin(2 * np.pi * 70.0 * t)
        sig = x_pass + x_stop
        filtered = bandpass_filter(sig, fs=fs, low_cut=15.0, high_cut=25.0, order=4, zero_phase=True)
        pwr_20 = np.mean(x_pass[500:-500] ** 2)
        pwr_filt = np.mean(filtered[500:-500] ** 2)
        assert pwr_filt == pytest.approx(pwr_20, rel=0.1)

    def test_zero_phase_vs_causal_delay(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        sig = np.sin(2 * np.pi * 20.0 * t)
        y_zero = bandpass_filter(sig, fs=fs, low_cut=15.0, high_cut=25.0, order=4, zero_phase=True)
        y_causal = bandpass_filter(sig, fs=fs, low_cut=15.0, high_cut=25.0, order=4, zero_phase=False)
        corr_zero = signal.correlate(y_zero[500:1500], sig[500:1500], mode="same")
        lags = signal.correlation_lags(1000, 1000, mode="same")
        lag_zero = lags[np.argmax(corr_zero)]

        corr_causal = signal.correlate(y_causal[500:1500], sig[500:1500], mode="same")
        lag_causal = lags[np.argmax(corr_causal)]

        assert lag_zero == 0
        assert lag_causal > 0  # causal filter introduces group delay


    def test_multidimensional_axis(self):
        fs = 1000.0
        data = np.random.default_rng(0).standard_normal((4, 1000))
        f_axis1_pass = bandpass_filter(data, fs=fs, low_cut=10.0, high_cut=30.0, axis=-1)
        f_axis0_pass = bandpass_filter(data.T, fs=fs, low_cut=10.0, high_cut=30.0, axis=0)
        np.testing.assert_allclose(f_axis1_pass, f_axis0_pass.T)

    def test_nyquist_and_cutoff_tripwires(self):
        d = np.ones(1000)
        with pytest.raises(ValueError, match="strictly positive"):
            bandpass_filter(d, fs=0, low_cut=10, high_cut=20)
        with pytest.raises(ValueError, match="strictly positive"):
            bandpass_filter(d, fs=1000, low_cut=-5, high_cut=20)
        with pytest.raises(ValueError, match="Nyquist"):
            bandpass_filter(d, fs=1000, low_cut=10, high_cut=500)
        with pytest.raises(ValueError, match="strictly less"):
            bandpass_filter(d, fs=1000, low_cut=30, high_cut=20)

    def test_nan_propagation_raises(self):
        d = np.ones(1000)
        d[500] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            bandpass_filter(d, fs=1000, low_cut=10, high_cut=20)

    def test_inf_is_refused_like_nan(self):
        d = np.ones(1000)
        d[500] = np.inf
        with pytest.raises(ValueError, match="finite"):
            bandpass_filter(d, fs=1000, low_cut=10, high_cut=20)

    def test_short_signal_raises(self):
        d = np.ones(10)
        with pytest.raises(ValueError, match="too short"):
            bandpass_filter(d, fs=1000, low_cut=10, high_cut=20, order=4, zero_phase=True)


class TestNotchFilter:
    def test_line_noise_notch_suppressed(self):
        fs = 1000.0
        t = np.arange(0, 3.0, 1.0 / fs)
        sig_60 = np.sin(2 * np.pi * 60.0 * t)
        sig_10 = np.sin(2 * np.pi * 10.0 * t)
        mixed = sig_60 + sig_10
        filtered = notch_filter(mixed, fs=fs, freq=60.0, q=30.0, zero_phase=True)
        band10_pwr = jnwb.band_power(filtered[1000:-1000], fs=fs, freq_range=(8, 12), normalize=False)
        band60_pwr = jnwb.band_power(filtered[1000:-1000], fs=fs, freq_range=(59, 61), normalize=False)
        assert band60_pwr < band10_pwr * 0.01

    def test_inf_is_refused_like_nan(self):
        d = np.ones(1000)
        d[500] = np.inf
        with pytest.raises(ValueError, match="finite"):
            notch_filter(d, fs=1000.0)

