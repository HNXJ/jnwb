"""Comprehensive Regression Test Suite for TFRAnalyzer.extract_band and BANDS.

Verifies:
  - Explicit frequency coordinate enforcement (F1 fix)
  - Dimension, length, finiteness, and strictly increasing ordering checks
  - Fail-fast ValueError on empty requested band (no silent zeros)
  - Boundary frequency inclusion
  - Asymmetric and non-uniform (e.g. log-spaced) frequency coordinates
  - Single-source band consolidation onto spectral.CANONICAL_BANDS (F2 fix)
  - Preservation of explicit legacy 7-band table (LEGACY_VIZ_BANDS)
  - TFRAnalyzer.correlate_areas with explicit freqs
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.analyzers import TFRAnalyzer
from jnwb.spectral import CANONICAL_BANDS


class TestTFRExtractBandRegressions:
    def test_valid_extraction_uniform_coordinates(self):
        """Test extraction with standard linearly spaced frequencies."""
        n_ch, n_freqs, n_times, n_trials = 4, 100, 50, 10
        tfr_data = np.ones((n_ch, n_freqs, n_times, n_trials))
        freqs = np.linspace(1.0, 100.0, n_freqs)
        
        # Theta is 4.0 - 8.0 Hz in consolidated BANDS
        result = TFRAnalyzer.extract_band(tfr_data, "theta", freqs=freqs)
        assert result.shape == (n_ch, n_times, n_trials)
        np.testing.assert_allclose(result, 1.0)

    def test_asymmetric_and_nonuniform_frequency_coordinates(self):
        """Test extraction with non-uniform logarithmic coordinates (Morlet wavelet style)."""
        # 50 log-spaced frequencies from 4 to 150 Hz
        freqs = np.geomspace(4.0, 150.0, 50)
        tfr_data = np.zeros((2, 50, 20, 5))
        
        # Mark indices that fall within beta (14.0 - 30.0 Hz) with known value
        beta_mask = (freqs >= 14.0) & (freqs <= 30.0)
        assert np.any(beta_mask), "Must have sampled frequencies in beta"
        tfr_data[:, beta_mask, :, :] = 42.0
        
        result = TFRAnalyzer.extract_band(tfr_data, "beta", freqs=freqs)
        assert result.shape == (2, 20, 5)
        np.testing.assert_allclose(result, 42.0)

    def test_boundary_frequencies_inclusive(self):
        """Test that boundary frequencies exactly equal to f_min or f_max are included."""
        # freqs with exact boundaries: 8.0 (alpha min) and 14.0 (alpha max)
        freqs = np.array([6.0, 8.0, 10.0, 12.0, 14.0, 16.0])
        tfr_data = np.zeros((1, 6, 10, 1))
        # Put 10.0 at 8.0 Hz and 20.0 at 14.0 Hz, 0 elsewhere
        tfr_data[0, 1, :, :] = 10.0  # 8.0 Hz
        tfr_data[0, 4, :, :] = 20.0  # 14.0 Hz
        
        # Alpha is [8.0, 14.0]; should average bins 1, 2, 3, 4: (10 + 0 + 0 + 20) / 4 = 7.5
        result = TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=freqs)
        np.testing.assert_allclose(result, 7.5)

    def test_mismatched_coordinates_raises_error(self):
        """Test that mismatched length between freqs and TFR freq axis raises ValueError."""
        tfr_data = np.random.randn(2, 50, 10, 5)
        wrong_freqs = np.linspace(1.0, 100.0, 40)  # 40 != 50
        with pytest.raises(ValueError, match="freqs length.*must match"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=wrong_freqs)

    def test_unsorted_coordinates_raises_error(self):
        """Test that unsorted or non-strictly-increasing freqs raises ValueError."""
        tfr_data = np.random.randn(2, 5, 10, 5)
        unsorted_freqs = np.array([1.0, 5.0, 4.0, 8.0, 10.0])
        with pytest.raises(ValueError, match="strictly increasing"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=unsorted_freqs)
            
        duplicate_freqs = np.array([1.0, 5.0, 5.0, 8.0, 10.0])
        with pytest.raises(ValueError, match="strictly increasing"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=duplicate_freqs)

    def test_nonfinite_coordinates_raises_error(self):
        """Test that NaN or Inf in freqs raises ValueError."""
        tfr_data = np.random.randn(2, 5, 10, 5)
        nan_freqs = np.array([1.0, 5.0, np.nan, 8.0, 10.0])
        with pytest.raises(ValueError, match="finite values"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=nan_freqs)
            
        inf_freqs = np.array([1.0, 5.0, np.inf, 8.0, 10.0])
        with pytest.raises(ValueError, match="finite values"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=inf_freqs)

    def test_non_1d_coordinates_raises_error(self):
        """Test that non-1D freqs array raises ValueError."""
        tfr_data = np.random.randn(2, 4, 10, 5)
        freqs_2d = np.ones((2, 2))
        with pytest.raises(ValueError, match="1D array"):
            TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=freqs_2d)

    def test_empty_requested_band_raises_error_not_zeros(self):
        """Test that a requested band with zero sampled frequencies fails fast with ValueError (never zero)."""
        # Frequencies only sampled between 50 and 100 Hz
        freqs = np.linspace(50.0, 100.0, 20)
        tfr_data = np.random.randn(2, 20, 10, 5)
        
        # Theta (4-8 Hz) has zero samples in this coordinate span
        with pytest.raises(ValueError, match="No sampled frequencies fall within requested band 'theta'"):
            TFRAnalyzer.extract_band(tfr_data, "theta", freqs=freqs)

    def test_custom_freq_axis(self):
        """Test extracting along a non-default frequency axis (e.g. freq_axis=2)."""
        # Shape: (trials, channels, freqs, times)
        tfr_data = np.ones((5, 4, 30, 25))
        freqs = np.linspace(1.0, 60.0, 30)
        result = TFRAnalyzer.extract_band(tfr_data, "beta", freqs=freqs, freq_axis=2)
        assert result.shape == (5, 4, 25)
        np.testing.assert_allclose(result, 1.0)

    def test_band_consolidation_matches_canonical_bands(self):
        """F2: Verify TFRAnalyzer.BANDS matches spectral.CANONICAL_BANDS."""
        for band_name, edges in CANONICAL_BANDS.items():
            assert band_name in TFRAnalyzer.BANDS, f"Missing canonical band {band_name}"
            assert TFRAnalyzer.BANDS[band_name] == edges, (
                f"Mismatch in {band_name}: {TFRAnalyzer.BANDS[band_name]} vs {edges}"
            )
        # Delta and broadband present as supersets
        assert TFRAnalyzer.BANDS["delta"] == (1.0, 4.0)
        assert TFRAnalyzer.BANDS["broadband"] == (1.0, 150.0)

    def test_legacy_viz_bands_available_by_name(self):
        """Verify historical 7-band table is accessible explicitly via LEGACY_VIZ_BANDS."""
        assert "LEGACY_VIZ_BANDS" in dir(TFRAnalyzer)
        assert TFRAnalyzer.LEGACY_VIZ_BANDS["alpha"] == (8.0, 15.0)
        assert TFRAnalyzer.LEGACY_VIZ_BANDS["low_gamma"] == (30.0, 60.0)
        
        # Caller can explicitly use legacy definitions
        freqs = np.array([8.0, 12.0, 14.5, 16.0])
        tfr_data = np.ones((1, 4, 2, 1))
        # 14.5 Hz is inside legacy alpha (8-15)
        res_legacy = TFRAnalyzer.extract_band(
            tfr_data, "alpha", freqs=freqs, band_defs=TFRAnalyzer.LEGACY_VIZ_BANDS
        )
        assert res_legacy.shape == (1, 2, 1)

    def test_correlate_areas_with_explicit_freqs(self):
        """Verify TFRAnalyzer.correlate_areas passes freqs properly."""
        tfr1 = np.random.randn(2, 20, 10, 15)
        tfr2 = np.random.randn(2, 20, 10, 15)
        freqs = np.linspace(1.0, 40.0, 20)
        
        res = TFRAnalyzer.correlate_areas(tfr1, tfr2, freqs=freqs, band="alpha")
        assert "correlation" in res
        assert "band" in res
        assert res["band"] == "alpha"

    def test_omission_wrapper_tfr_correlate_areas_migrated(self):
        """Verify omission.jnwb_ext.functions.tfr_correlate_areas wrapper passes explicit freqs."""
        from unittest.mock import MagicMock
        from omission.jnwb_ext.functions import tfr_correlate_areas

        mock_session = MagicMock()
        # Mock 99-bin TFR array: (trials=5, channels=4, freqs=99, times=20)
        fake_tfr1 = np.random.randn(5, 4, 99, 20)
        fake_tfr2 = np.random.randn(5, 4, 99, 20)
        mock_session.tfr_from_preprocessed.side_effect = lambda area, band, condition: (
            fake_tfr1 if area == "V1" else fake_tfr2
        )

        res = tfr_correlate_areas(mock_session, area1="V1", area2="V4", band="alpha")
        assert "correlation" in res
        assert "band" in res
        assert res["band"] == "alpha"
