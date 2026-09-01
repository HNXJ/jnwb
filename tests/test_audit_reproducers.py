"""Audit Verification Probes for Resolved jnwb Defects F1 and F2.

Asserts that:
  F1: Calling extract_band without explicit frequency coordinates is impossible (TypeError).
      Consuming true frequency coordinates extracts the correct physical oscillation.
  F2: TFRAnalyzer.BANDS and spectral.CANONICAL_BANDS agree across shared bands.
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.analyzers import TFRAnalyzer
from jnwb.spectral import CANONICAL_BANDS


class TestResolvedJnwbDefects:
    def test_f1_extract_band_requires_explicit_freqs(self):
        """F1: Calling extract_band without freqs must raise TypeError."""
        tfr_data = np.zeros((1, 30, 10, 1))
        with pytest.raises(TypeError):
            TFRAnalyzer.extract_band(tfr_data, "theta")  # type: ignore

    def test_f1_extract_band_resolves_true_physical_coordinates(self):
        """F1: With true frequencies supplied, a 13.1 Hz signal is recognized as Alpha, not Theta."""
        true_freqs = np.linspace(10.0, 100.0, 30)
        tfr_data = np.zeros((1, 30, 10, 1))
        # Power at all bins in Alpha range [8, 14] Hz (bins 0 and 1: 10.0 and 13.1 Hz)
        alpha_mask = (true_freqs >= 8.0) & (true_freqs <= 14.0)
        tfr_data[0, alpha_mask, :, :] = 100.0

        # Theta (4-8 Hz) has no samples in true_freqs [10, 100], so it must fail fast
        with pytest.raises(ValueError, match="No sampled frequencies fall within requested band 'theta'"):
            TFRAnalyzer.extract_band(tfr_data, "theta", freqs=true_freqs)

        # Alpha (8-14 Hz) captures bins 0 and 1 correctly with 100.0 mean power
        extracted_alpha = TFRAnalyzer.extract_band(tfr_data, "alpha", freqs=true_freqs)
        assert extracted_alpha.mean() == 100.0

    def test_f2_band_definitions_reconciled(self):
        """F2: TFRAnalyzer.BANDS and spectral.CANONICAL_BANDS agree across all canonical bands."""
        for band in ("theta", "alpha", "beta", "low_gamma", "high_gamma"):
            assert TFRAnalyzer.BANDS[band] == CANONICAL_BANDS[band]

        # 14.5 Hz is consistently Beta across both tables
        f_probe = 14.5
        tfr_alpha = TFRAnalyzer.BANDS["alpha"][0] <= f_probe <= TFRAnalyzer.BANDS["alpha"][1]
        canonical_alpha = CANONICAL_BANDS["alpha"][0] <= f_probe <= CANONICAL_BANDS["alpha"][1]
        assert tfr_alpha == canonical_alpha == False

        tfr_beta = TFRAnalyzer.BANDS["beta"][0] <= f_probe <= TFRAnalyzer.BANDS["beta"][1]
        canonical_beta = CANONICAL_BANDS["beta"][0] <= f_probe <= CANONICAL_BANDS["beta"][1]
        assert tfr_beta == canonical_beta == True
