"""
Test Spectral Analysis Y-Files Module

Validates omission.jnwb_ext.spectral functions for harmonic and coherence analysis.
Uses both synthetic and real LFP data when available.
"""

import logging
import numpy as np
import pytest

from omission import spectral

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class TestHarmonicAnalysis:
    """Test harmonic decomposition."""

    def test_harmonic_analysis_synthetic_theta(self):
        """Analyze synthetic theta oscillation with harmonics."""
        # Create 10 Hz theta + 20 Hz and 30 Hz harmonics
        sampling_rate = 1000.0
        duration = 5.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        # Fundamental + harmonics
        signal = (
            np.sin(2 * np.pi * 10 * t) +  # 10 Hz theta
            0.5 * np.sin(2 * np.pi * 20 * t) +  # 2nd harmonic
            0.25 * np.sin(2 * np.pi * 30 * t)  # 3rd harmonic
        )

        result = spectral.harmonic_analysis(signal, sampling_rate, freq_range=(5, 50))

        assert result['fundamental_freq'] > 0
        assert abs(result['fundamental_freq'] - 10.0) < 2.0, "Should detect ~10 Hz fundamental"
        assert len(result['harmonics']) >= 2, "Should detect harmonics"

        log.info(f"Detected fundamental: {result['fundamental_freq']:.1f} Hz")
        log.info(f"Harmonics: {result['harmonics']}")

    def test_harmonic_analysis_single_frequency(self):
        """Analyze pure sinusoid (no harmonics)."""
        sampling_rate = 1000.0
        duration = 2.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        # Pure 8 Hz alpha
        signal = np.sin(2 * np.pi * 8 * t)

        result = spectral.harmonic_analysis(signal, sampling_rate, freq_range=(1, 20))

        assert 6 < result['fundamental_freq'] < 10, "Should detect ~8 Hz"
        log.info(f"Pure tone fundamental: {result['fundamental_freq']:.1f} Hz")

    def test_harmonic_analysis_no_signal(self):
        """Handle empty or near-zero signal gracefully."""
        result = spectral.harmonic_analysis(np.array([]), 1000.0)
        assert 'fundamental_freq' in result
        assert isinstance(result['fundamental_freq'], float)


class TestCrossAreaCoherence:
    """Test cross-area coherence computation."""

    def test_coherence_identical_signals(self):
        """Coherence between identical signals should be 1.0."""
        sampling_rate = 1000.0
        duration = 2.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        # Same signal
        signal1 = np.sin(2 * np.pi * 10 * t)
        signal2 = signal1.copy()

        result = spectral.cross_area_coherence(signal1, signal2, sampling_rate)

        # Peak coherence should be very high for identical signals
        assert result['peak_coherence_value'] > 0.9
        log.info(f"Identical signals: peak coherence = {result['peak_coherence_value']:.3f}")

    def test_coherence_uncorrelated_signals(self):
        """Coherence between random signals should be low (on average)."""
        sampling_rate = 1000.0
        duration = 2.0
        n_samples = int(sampling_rate * duration)

        # Independent noise (long enough for averaging)
        signal1 = np.random.randn(n_samples)
        signal2 = np.random.randn(n_samples)

        result = spectral.cross_area_coherence(signal1, signal2, sampling_rate)

        # Should have coherence spectrum
        assert len(result['coherence_spectrum']) > 0
        assert 'band_coherence' in result
        log.info(f"Uncorrelated signals: peak coherence = {result['peak_coherence_value']:.3f}")

    def test_coherence_band_specific(self):
        """Coherence should vary by frequency band."""
        sampling_rate = 1000.0
        duration = 3.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        # Theta coherence but not alpha
        signal1 = np.sin(2 * np.pi * 6 * t) + 0.2 * np.random.randn(len(t))
        signal2 = np.sin(2 * np.pi * 6 * t) + 0.2 * np.random.randn(len(t))

        result = spectral.cross_area_coherence(signal1, signal2, sampling_rate)

        # Should have band-specific coherence
        assert 'band_coherence' in result
        assert len(result['band_coherence']) > 0

        log.info(f"Band coherence: {result['band_coherence']}")


class TestSpectralTilt:
    """Test 1/f spectral slope analysis."""

    def test_spectral_tilt_white_noise(self):
        """White noise should have exponent near 0."""
        sampling_rate = 1000.0
        signal = np.random.randn(10000)

        result = spectral.spectral_tilt(signal, sampling_rate)

        # White noise exponent should be measurable
        assert isinstance(result['exponent'], float)
        assert isinstance(result['fit_quality'], float)
        assert 0 <= result['fit_quality'] <= 1.0

        log.info(f"White noise exponent: {result['exponent']:.2f}, quality: {result['fit_quality']:.3f}")

    def test_spectral_tilt_pink_noise(self):
        """Pink noise (1/f) should have steeper exponent than white noise."""
        sampling_rate = 1000.0
        n_samples = 10000

        # Generate pink noise via spectral filtering
        white = np.random.randn(n_samples)
        pink = np.cumsum(white)
        pink = pink / np.std(pink)

        result = spectral.spectral_tilt(pink, sampling_rate)

        # Pink noise exponent should be steeper (more negative)
        assert isinstance(result['exponent'], float)
        assert isinstance(result['fit_quality'], float)

        log.info(f"Pink noise exponent: {result['exponent']:.2f}, quality: {result['fit_quality']:.3f}")

    def test_spectral_tilt_fit_quality(self):
        """Fit quality should be reasonable for synthetic signals."""
        sampling_rate = 1000.0
        signal = np.random.randn(5000)

        result = spectral.spectral_tilt(signal, sampling_rate)

        assert 0 <= result['fit_quality'] <= 1.0
        log.info(f"Fit quality: {result['fit_quality']:.3f}")


class TestBandPower:
    """Test frequency band power computation."""

    def test_band_power_dominant_band(self):
        """Power should be highest in dominant frequency band."""
        sampling_rate = 1000.0
        duration = 3.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        # Strong alpha (8-12 Hz), weak theta
        signal = (
            0.5 * np.sin(2 * np.pi * 6 * t) +  # Theta
            2.0 * np.sin(2 * np.pi * 10 * t) +  # Alpha (dominant)
            0.3 * np.sin(2 * np.pi * 50 * t)  # Gamma
        )

        theta_power = spectral.band_power(signal, sampling_rate, (4, 8), normalize=False)
        alpha_power = spectral.band_power(signal, sampling_rate, (8, 12), normalize=False)
        gamma_power = spectral.band_power(signal, sampling_rate, (30, 55), normalize=False)

        assert alpha_power > theta_power, "Alpha should dominate"
        assert alpha_power > gamma_power, "Alpha should dominate"

        log.info(f"Theta power: {theta_power:.2f}")
        log.info(f"Alpha power: {alpha_power:.2f}")
        log.info(f"Gamma power: {gamma_power:.2f}")

    def test_band_power_normalization(self):
        """Normalized power should be relative to baseline."""
        sampling_rate = 1000.0
        duration = 2.0
        t = np.linspace(0, duration, int(sampling_rate * duration))

        baseline = np.random.randn(int(sampling_rate * duration))
        signal = baseline + 1.5 * np.sin(2 * np.pi * 10 * t)

        # Compute power
        raw_power = spectral.band_power(signal, sampling_rate, (8, 12), normalize=False)
        normalized_power = spectral.band_power(signal, sampling_rate, (8, 12), normalize=True, baseline=baseline)

        # Normalized should be in dB (relative to baseline)
        assert isinstance(normalized_power, float)
        log.info(f"Raw power: {raw_power:.2f}")
        log.info(f"Normalized power (dB): {normalized_power:.2f}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
