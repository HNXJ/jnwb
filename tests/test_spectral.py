"""Unit tests for jnwb.spectral -- generic spectral/oscillatory analysis (band power,
cross-area coherence, 1/f tilt, imaginary coherency, re-referencing), promoted 2026-08-23
from omission.jnwb_ext.spectral (99%-jnwb-sufficiency normalization).
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.spectral import (
    to_db,
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    band_power,
    imaginary_coherency,
    bipolar_reference,
    laplacian_reference,
    CANONICAL_BANDS,
    compute_psd,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.to_db is to_db
        assert jnwb.harmonic_analysis is harmonic_analysis
        assert jnwb.cross_area_coherence is cross_area_coherence
        assert jnwb.spectral_tilt is spectral_tilt
        assert jnwb.band_power is band_power
        assert jnwb.imaginary_coherency is imaginary_coherency
        assert jnwb.bipolar_reference is bipolar_reference
        assert jnwb.laplacian_reference is laplacian_reference
        assert jnwb.CANONICAL_BANDS is CANONICAL_BANDS
        assert jnwb.compute_psd is compute_psd

    def test_listed_in_jnwb_all(self):
        import jnwb
        assert "compute_psd" in jnwb.__all__


class TestComputePsd:
    def test_returns_freqs_and_psd_arrays(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        x = np.sin(2 * np.pi * 40.0 * t)
        freqs, psd = compute_psd(x, fs)
        assert freqs.shape == psd.shape
        assert freqs[0] == pytest.approx(0.0)

    def test_peak_frequency_recovered(self):
        fs = 1000.0
        t = np.arange(0, 2.0, 1.0 / fs)
        x = np.sin(2 * np.pi * 40.0 * t)
        freqs, psd = compute_psd(x, fs)
        peak = freqs[np.argmax(psd)]
        assert abs(peak - 40.0) < 2.0

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("to_db", "harmonic_analysis", "cross_area_coherence", "spectral_tilt",
                     "band_power", "imaginary_coherency", "bipolar_reference",
                     "laplacian_reference", "CANONICAL_BANDS"):
            assert name in jnwb.__all__


class TestCanonicalBands:
    def test_connectivity_reexports_same_object(self):
        omission_jnwb_ext = pytest.importorskip("omission.jnwb_ext.connectivity")
        assert omission_jnwb_ext.CANONICAL_BANDS is CANONICAL_BANDS

    def test_expected_band_edges(self):
        assert CANONICAL_BANDS["theta"] == (4.0, 8.0)
        assert CANONICAL_BANDS["alpha"] == (8.0, 14.0)
        assert CANONICAL_BANDS["beta"] == (14.0, 30.0)
        assert CANONICAL_BANDS["low_gamma"] == (30.0, 50.0)
        assert CANONICAL_BANDS["high_gamma"] == (50.0, 80.0)


class TestToDb:
    def test_unity_ratio_is_zero_db(self):
        assert to_db(1.0) == pytest.approx(0.0)

    def test_ten_x_ratio_is_ten_db(self):
        assert to_db(10.0) == pytest.approx(10.0)


def _sine(freq_hz, sampling_rate=1000.0, duration_s=2.0, amplitude=1.0, phase=0.0):
    t = np.arange(0, duration_s, 1.0 / sampling_rate)
    return amplitude * np.sin(2 * np.pi * freq_hz * t + phase), t


class TestHarmonicAnalysis:
    def test_empty_input_returns_zeroed_result(self):
        result = harmonic_analysis(np.array([]), sampling_rate=1000.0)
        assert result["fundamental_freq"] == 0.0
        assert result["harmonics"] == {}

    def test_finds_fundamental_frequency_of_pure_tone(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = harmonic_analysis(trace, sampling_rate=1000.0, freq_range=(1.0, 90.0))
        assert result["fundamental_freq"] == pytest.approx(10.0, abs=1.0)


class TestCrossAreaCoherence:
    def test_identical_signals_have_high_coherence(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = cross_area_coherence(trace, trace, sampling_rate=1000.0)
        assert result["band_coherence"]["theta"] > 0.9

    def test_mismatched_lengths_return_empty_result(self):
        result = cross_area_coherence(np.zeros(100), np.zeros(50), sampling_rate=1000.0)
        assert result["coherence_spectrum"].size == 0

    def test_default_freq_bands_is_canonical_bands(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0)
        result = cross_area_coherence(trace, trace, sampling_rate=1000.0)
        assert set(result["band_coherence"].keys()) == set(CANONICAL_BANDS.keys())


class TestSpectralTilt:
    def test_empty_input_returns_zeroed_result(self):
        result = spectral_tilt(np.array([]), sampling_rate=1000.0)
        assert result["exponent"] == 0.0

    def test_pink_noise_has_negative_exponent(self):
        rng = np.random.default_rng(0)
        white = rng.standard_normal(20000)
        # crude 1/f pink noise via cumulative sum (integrated white noise)
        pink = np.cumsum(white)
        pink -= pink.mean()
        result = spectral_tilt(pink, sampling_rate=1000.0, freq_range=(1.0, 100.0))
        assert result["exponent"] < 0


class TestBandPower:
    def test_empty_input_returns_zero(self):
        assert band_power(np.array([]), sampling_rate=1000.0, freq_range=(4, 8)) == 0.0

    def test_tone_in_band_has_higher_power_than_out_of_band(self):
        trace, _ = _sine(10.0, sampling_rate=1000.0, duration_s=4.0, amplitude=5.0)
        in_band = band_power(trace, 1000.0, (8, 12), normalize=False)
        out_of_band = band_power(trace, 1000.0, (60, 80), normalize=False)
        assert in_band > out_of_band


class TestImaginaryCoherency:
    def test_zero_lag_mixed_source_has_near_zero_icoh(self):
        rng = np.random.default_rng(1)
        source = rng.standard_normal(5000)
        x = source + 0.01 * rng.standard_normal(5000)
        y = source + 0.01 * rng.standard_normal(5000)
        result = imaginary_coherency(x, y, sampling_rate=1000.0, freq_range=(1, 100))
        assert result["coh_mag_mean"] > 0.5
        assert abs(result["icoh_mean"]) < 0.1

    def test_empty_input_returns_zeroed_result(self):
        result = imaginary_coherency(np.array([]), np.array([]), sampling_rate=1000.0, freq_range=(1, 100))
        assert result["n_freqs"] == 0


class TestBipolarReference:
    def test_drops_one_channel(self):
        data = np.arange(12, dtype=float).reshape(4, 3)
        out = bipolar_reference(data)
        assert out.shape == (3, 3)

    def test_common_signal_cancels(self):
        common = np.array([1.0, 2.0, 3.0])
        data = np.stack([common, common, common])
        out = bipolar_reference(data)
        assert np.allclose(out, 0.0)

    def test_rejects_non_2d_input(self):
        with pytest.raises(ValueError):
            bipolar_reference(np.zeros(5))


class TestLaplacianReference:
    def test_preserves_channel_count(self):
        data = np.arange(12, dtype=float).reshape(4, 3)
        out = laplacian_reference(data)
        assert out.shape == (4, 3)

    def test_common_signal_cancels_on_interior_channels(self):
        common = np.array([1.0, 2.0, 3.0])
        data = np.stack([common, common, common, common])
        out = laplacian_reference(data)
        assert np.allclose(out[1:-1], 0.0)
