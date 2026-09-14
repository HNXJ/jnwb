"""Tests for jnwb.laminar: Vectorized Frequency-based Laminar Identity Profile (vFLIP)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.laminar import VFlipResult, vflip


class TestVFlipMotifRecovery:
    """Test vFLIP parameter and crossover recovery on synthetic spectrolaminar motifs."""

    def _create_synthetic_laminar_psd(
        self,
        n_channels: int = 24,
        n_freqs: int = 120,
        crossover_idx: float = 10.5,
        orientation: str = "superficial_to_deep",
        snr: float = 20.0,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Generate synthetic PSD with known spectrolaminar motif and continuous crossover."""
        freqs = np.linspace(2.0, 150.0, n_freqs)
        psd = np.zeros((n_channels, n_freqs), dtype=np.float64)

        for ch in range(n_channels):
            # Depth along probe from 0 to 1
            if orientation == "superficial_to_deep":
                # Contact 0 is superficial (gamma dominant), contact n_channels-1 is deep (alpha dominant)
                gamma_weight = max(0.0, 1.0 - (ch / crossover_idx) * 0.5) if ch <= crossover_idx else max(0.0, 0.5 * (1.0 - (ch - crossover_idx) / (n_channels - crossover_idx)))
                alpha_weight = max(0.0, (ch / crossover_idx) * 0.5) if ch <= crossover_idx else min(1.0, 0.5 + 0.5 * (ch - crossover_idx) / (n_channels - crossover_idx))
            else:
                # Inverted: contact 0 is deep, contact n_channels-1 is superficial
                alpha_weight = max(0.0, 1.0 - (ch / crossover_idx) * 0.5) if ch <= crossover_idx else max(0.0, 0.5 * (1.0 - (ch - crossover_idx) / (n_channels - crossover_idx)))
                gamma_weight = max(0.0, (ch / crossover_idx) * 0.5) if ch <= crossover_idx else min(1.0, 0.5 + 0.5 * (ch - crossover_idx) / (n_channels - crossover_idx))

            # Alpha/beta component (center 18 Hz, width 6 Hz)
            p_alpha = alpha_weight * np.exp(-((freqs - 18.0) ** 2) / (2 * (6.0 ** 2)))
            # Gamma component (center 75 Hz, width 20 Hz)
            p_gamma = gamma_weight * np.exp(-((freqs - 75.0) ** 2) / (2 * (20.0 ** 2)))
            # 1/f background
            p_bg = 1.0 / (freqs ** 1.0) / snr

            psd[ch] = p_alpha + p_gamma + p_bg

        return freqs, psd

    def test_recovers_known_superficial_to_deep_crossover(self):
        """Continuous crossover is accurately recovered on noise-free synthetic motif."""
        true_cross = 10.0
        n_ch = 24
        freqs, psd = self._create_synthetic_laminar_psd(
            n_channels=n_ch, crossover_idx=true_cross, orientation="superficial_to_deep"
        )

        res = vflip(psd, freqs, contact_spacing=50.0, orientation="superficial_to_deep")

        assert isinstance(res, VFlipResult)
        assert res.accepted is True
        assert res.rejection_reason is None
        assert res.orientation == "superficial_to_deep"
        assert res.crossover_contact is not None
        assert res.crossover_contact == pytest.approx(true_cross, abs=1.0)
        assert res.crossover_depth_um == pytest.approx(res.crossover_contact * 50.0, abs=1e-5)
        assert res.support_score >= 6.0
        assert res.high_peak_contact < res.low_peak_contact

    def test_auto_orientation_recovers_inverted_probe(self):
        """Auto orientation correctly detects deep-to-superficial inverted probe."""
        true_cross = 12.0
        n_ch = 24
        freqs, psd = self._create_synthetic_laminar_psd(
            n_channels=n_ch, crossover_idx=true_cross, orientation="deep_to_superficial"
        )

        res = vflip(psd, freqs, contact_spacing=25.0, orientation="auto")

        assert res.accepted is True
        assert res.orientation == "deep_to_superficial"
        assert res.crossover_contact is not None
        assert res.crossover_contact == pytest.approx(true_cross, abs=1.0)
        assert res.crossover_depth_um == pytest.approx(res.crossover_contact * 25.0, abs=1e-5)
        assert res.low_peak_contact < res.high_peak_contact

    def test_orientation_mismatch_rejects(self):
        """Declaring superficial_to_deep on an inverted deep_to_superficial probe rejects."""
        freqs, psd = self._create_synthetic_laminar_psd(orientation="deep_to_superficial")

        res = vflip(psd, freqs, orientation="superficial_to_deep")

        assert res.accepted is False
        assert res.crossover_contact is None
        assert res.crossover_depth_um is None
        assert res.rejection_reason == "orientation_mismatch"
        assert np.isfinite(res.support_score)

    def test_continuous_sub_contact_interpolation(self):
        """Crossover returns a real-valued sub-contact coordinate, not discrete integer."""
        # Contact 8 has delta > 0, Contact 9 has delta < 0
        freqs, psd = self._create_synthetic_laminar_psd(crossover_idx=8.4)
        res = vflip(psd, freqs)

        assert res.accepted is True
        assert isinstance(res.crossover_contact, float)
        # Check that it is not snapped to integer
        assert abs(res.crossover_contact - round(res.crossover_contact)) > 0.05


class TestVFlipRejectionAndFailLoud:
    """Test failure, non-identifiability, and boundary rejection behaviors."""

    def test_white_noise_psd_rejected(self):
        """Random white noise lacking spectrolaminar structure is rejected with support returned."""
        rng = np.random.default_rng(42)
        n_ch, n_f = 20, 100
        freqs = np.linspace(2.0, 150.0, n_f)
        psd_noise = rng.uniform(0.1, 1.0, size=(n_ch, n_f))

        res = vflip(psd_noise, freqs, min_support_score=6.0)

        assert res.accepted is False
        assert res.crossover_contact is None
        assert res.crossover_depth_um is None
        assert res.rejection_reason in ("insufficient_support", "no_crossover")
        assert np.isfinite(res.support_score)

    def test_pure_one_over_f_rejected(self):
        """Homogeneous 1/f spectrum with identical exponent across all contacts has no crossover."""
        n_ch, n_f = 20, 100
        freqs = np.linspace(2.0, 150.0, n_f)
        # Power is strictly identical across contacts
        psd_flat = np.repeat((100.0 / freqs)[None, :], n_ch, axis=0)

        res = vflip(psd_flat, freqs)

        assert res.accepted is False
        assert res.crossover_contact is None
        assert res.crossover_depth_um is None

    def test_insufficient_channels_rejects(self):
        """Probe with fewer than min_channels is rejected with specific diagnostic reason."""
        freqs = np.linspace(2.0, 150.0, 50)
        psd_short = np.ones((6, 50))  # 6 < min_channels=8

        res = vflip(psd_short, freqs, min_channels=8)

        assert res.accepted is False
        assert res.crossover_contact is None
        assert res.rejection_reason == "insufficient_channels"
        assert res.n_channels == 6

    def test_sentinel_min_support_score_raises(self):
        """Non-finite min_support_score (-inf, nan, inf) raises ValueError to prevent bypass."""
        freqs = np.linspace(2.0, 150.0, 50)
        psd = np.ones((16, 50))

        with pytest.raises(ValueError, match="finite float"):
            vflip(psd, freqs, min_support_score=-np.inf)

        with pytest.raises(ValueError, match="finite float"):
            vflip(psd, freqs, min_support_score=np.nan)

    def test_missing_contacts_interpolated_and_reported(self):
        """Missing or bad contacts are interpolated along depth and reported in n_missing."""
        n_ch = 20
        freqs = np.linspace(2.0, 150.0, 100)
        # Create valid motif
        psd = np.zeros((n_ch, 100))
        for ch in range(n_ch):
            g_w = 1.0 - ch / n_ch
            a_w = ch / n_ch
            psd[ch] = a_w * np.exp(-((freqs - 18) ** 2) / 50) + g_w * np.exp(-((freqs - 75) ** 2) / 200) + 0.01

        # Contacts 5 and 14 are corrupted/NaN
        bad_mask = np.zeros(n_ch, dtype=bool)
        bad_mask[5] = True
        bad_mask[14] = True
        psd[5] = np.nan
        psd[14] = 99999.0

        res = vflip(psd, freqs, bad_channel_mask=bad_mask)

        assert res.accepted is True
        assert res.n_missing == 2
        assert res.n_channels == n_ch
        assert res.crossover_contact is not None

    def test_invalid_parameters_raise_value_error(self):
        """Invalid inputs fail loudly with ValueError."""
        freqs = np.linspace(2.0, 150.0, 60)
        psd = np.ones((16, 60))

        # Negative power
        psd_neg = psd.copy()
        psd_neg[0, 0] = -1.0
        with pytest.raises(ValueError, match="non-negative"):
            vflip(psd_neg, freqs)

        # Non-monotonic freqs
        with pytest.raises(ValueError, match="strictly increasing"):
            vflip(psd, np.array([1, 5, 3, 10] * 15))

        # Overlapping bands
        with pytest.raises(ValueError, match="overlap"):
            vflip(psd, freqs, band_low=(10.0, 55.0), band_high=(50.0, 100.0))

        # Invalid orientation
        with pytest.raises(ValueError, match="orientation"):
            vflip(psd, freqs, orientation="invalid_choice")

        # Negative contact spacing
        with pytest.raises(ValueError, match="contact_spacing"):
            vflip(psd, freqs, contact_spacing=-50.0)


class TestVFlipProbeGeometryIntegration:
    """Test composition with jnwb.ProbeGeometry."""

    def test_probe_geometry_composition(self):
        """Passing ProbeGeometry automatically populates spacing and physical crossover depth."""
        n_ch = 16
        pitch_um = 30.0
        coords = np.zeros((n_ch, 3))
        coords[:, 2] = np.arange(n_ch) * pitch_um

        df = pd.DataFrame(coords, columns=["x", "y", "z"])
        geom = jnwb.probe_geometry(df, units="um", nominal_pitch=pitch_um, strict_linear=True)

        freqs = np.linspace(2.0, 150.0, 80)
        psd = np.zeros((n_ch, 80))
        for ch in range(n_ch):
            g_w = 1.0 - ch / n_ch
            a_w = ch / n_ch
            psd[ch] = a_w * np.exp(-((freqs - 18) ** 2) / 50) + g_w * np.exp(-((freqs - 75) ** 2) / 200) + 0.01

        res = vflip(psd, freqs, probe_geometry=geom)

        assert res.accepted is True
        assert res.crossover_contact is not None
        assert res.crossover_depth_um == pytest.approx(res.crossover_contact * pitch_um, abs=1e-4)

    def test_non_linear_probe_geometry_rejected(self):
        """Non-linear ProbeGeometry raises ValueError."""
        n_ch = 16
        # 2D square grid (4x4)
        x = np.repeat([0, 50, 100, 150], 4)
        y = np.tile([0, 50, 100, 150], 4)
        z = np.zeros(n_ch)
        df = pd.DataFrame({"x": x, "y": y, "z": z})
        geom_2d = jnwb.probe_geometry(df, units="um", nominal_pitch=50.0, strict_linear=False)
        assert geom_2d.is_linear is False

        freqs = np.linspace(2.0, 150.0, 50)
        psd = np.ones((n_ch, 50))

        with pytest.raises(ValueError, match="linear electrode shaft"):
            vflip(psd, freqs, probe_geometry=geom_2d)


class TestVFlipResultInterface:
    """Test mapping interface, serialization, and immutability of VFlipResult."""

    def test_dataclass_mapping_and_dict(self):
        """VFlipResult supports mapping access and .to_dict() serialization."""
        freqs = np.linspace(2.0, 150.0, 50)
        psd = np.ones((16, 50))
        res = vflip(psd, freqs)

        # Mapping access
        assert res["accepted"] == res.accepted
        assert res["support_score"] == res.support_score
        assert res.get("orientation") == res.orientation
        assert res.get("unknown_key", "default_val") == "default_val"

        # Dictionary serialization
        d = res.to_dict()
        assert isinstance(d, dict)
        assert d["accepted"] == res.accepted
        assert "profile" in d
        assert isinstance(d["profile"], np.ndarray)

    def test_frozen_immutability(self):
        """VFlipResult is immutable (frozen=True)."""
        freqs = np.linspace(2.0, 150.0, 50)
        psd = np.ones((16, 50))
        res = vflip(psd, freqs)

        with pytest.raises(Exception):  # FrozenInstanceError
            res.accepted = True  # type: ignore
