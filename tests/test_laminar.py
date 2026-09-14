"""Tests for jnwb.laminar: Vectorized Frequency-based Laminar Identity Profile (vFLIP)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb.laminar import VFlipResult, vflip, vflip_from_lfp, label_layers


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


class TestVFlipFromLFP:
    """Test strict composition and invariants of vflip_from_lfp."""

    def _generate_synthetic_laminar_lfp(
        self,
        n_channels: int = 24,
        n_times: int = 4000,
        fs: float = 1000.0,
        crossover_idx: float = 11.5,
        seed: int = 42,
    ) -> np.ndarray:
        """Synthesize multi-channel LFP with depth-dependent spectrolaminar oscillations."""
        rng = np.random.default_rng(seed)
        t = np.arange(n_times) / fs
        lfp = np.zeros((n_channels, n_times), dtype=np.float64)

        for c in range(n_channels):
            # Background 1/f-like noise
            noise = rng.standard_normal(n_times)
            # Add gamma oscillation (70 Hz) in superficial contacts (c < crossover_idx)
            gamma_weight = max(0.0, 1.0 - abs(c - 5.0) / 7.0)
            gamma = gamma_weight * 2.0 * np.sin(2 * np.pi * 70.0 * t + rng.uniform(0, 2 * np.pi))

            # Add alpha/beta oscillation (18 Hz) in deep contacts (c > crossover_idx)
            beta_weight = max(0.0, 1.0 - abs(c - 18.0) / 7.0)
            beta = beta_weight * 2.5 * np.sin(2 * np.pi * 18.0 * t + rng.uniform(0, 2 * np.pi))

            lfp[c, :] = noise + gamma + beta

        return lfp

    def test_strict_welch_composition_equivalence(self):
        """vflip_from_lfp(X) is strictly identical to vflip(welch(X))."""
        from scipy import signal

        fs = 1000.0
        lfp = self._generate_synthetic_laminar_lfp(n_channels=20, n_times=3000, fs=fs, seed=0)

        # 1. Direct call to vflip_from_lfp
        res_comp = vflip_from_lfp(
            lfp,
            fs=fs,
            nperseg=1000,
            noverlap=500,
            contact_spacing=50.0,
            min_support_score=0.0,
        )

        # 2. Manual Welch PSD computation followed by vflip
        freqs, psd = signal.welch(
            lfp,
            fs=fs,
            window="hann",
            nperseg=1000,
            noverlap=500,
            detrend="constant",
            scaling="density",
            axis=1,
        )
        res_manual = vflip(
            psd,
            freqs,
            contact_spacing=50.0,
            min_support_score=0.0,
        )

        # Invariant: identical outputs
        assert res_comp.accepted == res_manual.accepted
        assert res_comp.crossover_contact == pytest.approx(res_manual.crossover_contact, abs=1e-12)
        assert res_comp.crossover_depth_um == pytest.approx(res_manual.crossover_depth_um, abs=1e-12)
        assert res_comp.support_score == pytest.approx(res_manual.support_score, abs=1e-12)
        assert res_comp.low_peak_contact == res_manual.low_peak_contact
        assert res_comp.high_peak_contact == res_manual.high_peak_contact
        assert res_comp.orientation == res_manual.orientation
        np.testing.assert_allclose(res_comp.profile, res_manual.profile, atol=1e-12)

    def test_welch_parameter_propagation(self):
        """Welch segment parameters (nperseg, noverlap, window, detrend) propagate deterministically."""
        from scipy import signal

        fs = 1000.0
        lfp = self._generate_synthetic_laminar_lfp(n_channels=16, n_times=2000, fs=fs, seed=1)

        res_custom = vflip_from_lfp(
            lfp,
            fs=fs,
            nperseg=500,
            noverlap=250,
            window="boxcar",
            detrend=False,
            min_support_score=0.0,
        )

        freqs_m, psd_m = signal.welch(
            lfp,
            fs=fs,
            nperseg=500,
            noverlap=250,
            window="boxcar",
            detrend=False,
            axis=1,
        )
        res_m = vflip(psd_m, freqs_m, min_support_score=0.0)

        assert res_custom.crossover_contact == pytest.approx(res_m.crossover_contact, abs=1e-12)
        assert res_custom.support_score == pytest.approx(res_m.support_score, abs=1e-12)
        np.testing.assert_allclose(res_custom.profile, res_m.profile, atol=1e-12)

    def test_bad_channel_masking_and_interpolation(self):
        """Masked channels and NaN rows in LFP are masked, interpolated in profile, and counted."""
        fs = 1000.0
        lfp = self._generate_synthetic_laminar_lfp(n_channels=20, n_times=3000, fs=fs, seed=2)
        # Channel 3 is NaN in LFP
        lfp[3, :] = np.nan
        # Channel 10 is explicitly marked bad
        bad_mask = np.zeros(20, dtype=bool)
        bad_mask[10] = True

        res = vflip_from_lfp(
            lfp,
            fs=fs,
            bad_channel_mask=bad_mask,
            min_support_score=0.0,
        )
        assert res.n_missing == 2
        assert res.n_channels == 20
        assert np.all(np.isfinite(res.profile))

    def test_probe_geometry_integration(self):
        """vflip_from_lfp accepts ProbeGeometry and calculates physical depth in um."""
        fs = 1000.0
        n_ch = 20
        lfp = self._generate_synthetic_laminar_lfp(n_channels=n_ch, n_times=3000, fs=fs, seed=3)
        pitch_um = 40.0
        z = np.arange(n_ch) * pitch_um
        df = pd.DataFrame({"x": np.zeros(n_ch), "y": np.zeros(n_ch), "z": z})
        geom = jnwb.probe_geometry(df, units="um", nominal_pitch=pitch_um)

        res = vflip_from_lfp(lfp, fs=fs, probe_geometry=geom, min_support_score=0.0)
        assert res.crossover_contact is not None
        assert res.crossover_depth_um == pytest.approx(res.crossover_contact * pitch_um, abs=1e-6)

    def test_input_dimension_validation(self):
        """1D and 3D arrays raise ValueError; invalid fs raises ValueError."""
        with pytest.raises(ValueError, match="2D array"):
            vflip_from_lfp(np.ones(1000), fs=1000.0)

        with pytest.raises(ValueError, match="2D array"):
            vflip_from_lfp(np.ones((2, 10, 100)), fs=1000.0)

        with pytest.raises(ValueError, match="fs must be strictly positive"):
            vflip_from_lfp(np.ones((10, 1000)), fs=-100.0)

        with pytest.raises(ValueError, match="fs must be strictly positive"):
            vflip_from_lfp(np.ones((10, 1000)), fs=np.nan)


class TestLabelLayers:
    """Test layer assignment and strict failure invariants for label_layers."""

    def _make_probe_geom(self, n_channels: int = 24, pitch_um: float = 50.0):
        """Helper to construct linear ProbeGeometry."""
        z = np.arange(n_channels) * pitch_um
        df = pd.DataFrame({
            "x": np.zeros(n_channels),
            "y": np.zeros(n_channels),
            "z": z,
            "channel_id": [f"ch_{i}" for i in range(n_channels)],
        })
        return jnwb.probe_geometry(df, units="um", nominal_pitch=pitch_um)

    def test_accepted_superficial_to_deep_layer_labels(self):
        """Accepted superficial_to_deep fit correctly assigns superficial, input, and deep."""
        n_ch = 24
        pitch = 50.0
        geom = self._make_probe_geom(n_channels=n_ch, pitch_um=pitch)
        crossover = 10.0  # contact index 10 (depth 500 um)

        # Granular thickness 400 um -> 400/50 = 8 channels total span (half-span = 4 channels)
        # Input zone: [10 - 4, 10 + 4] = [6, 14] inclusive
        res = VFlipResult(
            crossover_contact=crossover,
            crossover_depth_um=crossover * pitch,
            support_score=10.0,
            profile=np.zeros(n_ch),
            low_peak_contact=18,
            high_peak_contact=2,
            orientation="superficial_to_deep",
            accepted=True,
            rejection_reason=None,
            n_channels=n_ch,
            n_missing=0,
        )

        labels = label_layers(res, geom, granular_thickness_um=400.0)
        assert len(labels) == n_ch

        # Under superficial_to_deep:
        # contacts 0..5 -> superficial
        for ch_idx in range(6):
            assert labels[f"ch_{ch_idx}"] == "superficial"

        # contacts 6..14 -> input
        for ch_idx in range(6, 15):
            assert labels[f"ch_{ch_idx}"] == "input"

        # contacts 15..23 -> deep
        for ch_idx in range(15, 24):
            assert labels[f"ch_{ch_idx}"] == "deep"

    def test_accepted_deep_to_superficial_layer_labels(self):
        """Accepted deep_to_superficial fit inverts superficial and deep relative to crossover."""
        n_ch = 24
        pitch = 50.0
        geom = self._make_probe_geom(n_channels=n_ch, pitch_um=pitch)
        crossover = 12.0

        # Granular thickness 300 um -> 300/50 = 6 channels total (half-span = 3)
        # Input zone: [12 - 3, 12 + 3] = [9, 15]
        res = VFlipResult(
            crossover_contact=crossover,
            crossover_depth_um=crossover * pitch,
            support_score=10.0,
            profile=np.zeros(n_ch),
            low_peak_contact=2,
            high_peak_contact=20,
            orientation="deep_to_superficial",
            accepted=True,
            rejection_reason=None,
            n_channels=n_ch,
            n_missing=0,
        )

        labels = label_layers(res, geom, granular_thickness_um=300.0)

        # Under deep_to_superficial:
        # contacts 0..8 -> deep
        for ch_idx in range(9):
            assert labels[f"ch_{ch_idx}"] == "deep"

        # contacts 9..15 -> input
        for ch_idx in range(9, 16):
            assert labels[f"ch_{ch_idx}"] == "input"

        # contacts 16..23 -> superficial
        for ch_idx in range(16, 24):
            assert labels[f"ch_{ch_idx}"] == "superficial"

    def test_rejected_fit_strictly_yields_all_na(self):
        """Critical invariant: rejected fit yields 'na' for all channels, never guessed layers."""
        n_ch = 20
        geom = self._make_probe_geom(n_channels=n_ch, pitch_um=40.0)

        # Rejected fit with crossover=None
        res_rejected = VFlipResult(
            crossover_contact=None,
            crossover_depth_um=None,
            support_score=2.5,
            profile=np.zeros(n_ch),
            low_peak_contact=15,
            high_peak_contact=14,
            orientation="undetermined",
            accepted=False,
            rejection_reason="insufficient_support",
            n_channels=n_ch,
            n_missing=0,
        )

        labels = label_layers(res_rejected, geom)
        assert len(labels) == n_ch
        assert all(label == "na" for label in labels.values())

    def test_validation_errors_fail_loud(self):
        """Invalid granular thickness, non-linear geometry, or mismatched channel counts raise ValueError."""
        geom = self._make_probe_geom(n_channels=20, pitch_um=50.0)
        res = VFlipResult(
            crossover_contact=10.0,
            crossover_depth_um=500.0,
            support_score=10.0,
            profile=np.zeros(20),
            low_peak_contact=18,
            high_peak_contact=2,
            orientation="superficial_to_deep",
            accepted=True,
            rejection_reason=None,
            n_channels=20,
            n_missing=0,
        )

        # Negative or non-finite thickness
        with pytest.raises(ValueError, match="granular_thickness_um must be strictly positive"):
            label_layers(res, geom, granular_thickness_um=-100.0)

        with pytest.raises(ValueError, match="granular_thickness_um must be strictly positive"):
            label_layers(res, geom, granular_thickness_um=np.nan)

        # Channel count mismatch (res has 20, geom_short has 10)
        geom_short = self._make_probe_geom(n_channels=10, pitch_um=50.0)
        with pytest.raises(ValueError, match="does not match"):
            label_layers(res, geom_short)

        # Non-linear geometry
        df_2d = pd.DataFrame({"x": [0, 50, 0, 50], "y": [0, 0, 50, 50], "z": [0, 0, 0, 0]})
        geom_2d = jnwb.probe_geometry(df_2d, units="um", nominal_pitch=50.0, strict_linear=False)
        with pytest.raises(ValueError, match="linear electrode shaft"):
            label_layers(res, geom_2d)


class TestVFlipRecoveryAndRejectionBroad:
    """Comprehensive recovery and rejection test suite for vFLIP (0.2.2-05).

    Directly verifies:
      1. Known crossover recovery across varied probe depths.
      2. Reversed probe orientation recovery and inversion symmetry.
      3. Rejection of no-motif 1/f background power spectra.
      4. Rejection of uncorrelated white noise spectra.
      5. Robustness to missing interior and boundary contacts.
      6. Invariance across regular frequency grid resolutions.
      7. Support for irregular (e.g. geometrically spaced) frequency axes.
      8. Structured rejection on insufficient valid channels.
      9. Fail-loud validation on invalid spacing and non-linear geometry.
      10. Clean rejection when support metric fails threshold under weak SNR.
    """

    def _generate_synthetic_psd(
        self,
        n_channels: int = 24,
        c_crossover: float = 11.5,
        freqs: Optional[np.ndarray] = None,
        gamma_peak_f: float = 75.0,
        beta_peak_f: float = 18.0,
        noise_level: float = 0.05,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Helper to generate a clean synthetic PSD with known crossover contact."""
        if freqs is None:
            freqs = np.linspace(2.0, 150.0, 100)
        psd = np.zeros((n_channels, len(freqs)), dtype=np.float64)
        for c in range(n_channels):
            # Superficial gamma component (peaks at c < c_crossover)
            gamma_w = max(0.0, 1.0 - (c - (c_crossover - 4.0)) ** 2 / 40.0)
            # Deep alpha/beta component (peaks at c > c_crossover)
            beta_w = max(0.0, 1.0 - (c - (c_crossover + 4.0)) ** 2 / 40.0)
            psd[c] = (
                noise_level
                + 2.0 * gamma_w * np.exp(-((freqs - gamma_peak_f) ** 2) / 200.0)
                + 2.0 * beta_w * np.exp(-((freqs - beta_peak_f) ** 2) / 50.0)
            )
        return freqs, psd

    def test_known_crossover_recovery_multiple_depths(self):
        """vFLIP accurately recovers known crossover across superficial, middle, and deep sites."""
        n_ch = 24
        spacing = 50.0
        # Probe various crossover positions along the shaft
        for c_true in [6.5, 11.5, 17.0]:
            freqs, psd = self._generate_synthetic_psd(n_channels=n_ch, c_crossover=c_true)
            res = vflip(psd, freqs, contact_spacing=spacing)

            assert res.accepted is True
            assert res.rejection_reason is None
            assert res.orientation == "superficial_to_deep"
            assert abs(res.crossover_contact - c_true) <= 0.25
            assert res.crossover_depth_um == pytest.approx(res.crossover_contact * spacing, abs=1e-4)
            assert res.support_score >= 6.0

    def test_reversed_probe_orientation_recovery(self):
        """vFLIP correctly identifies deep_to_superficial orientation and preserves symmetry."""
        n_ch = 24
        c_true = 11.5
        freqs, psd = self._generate_synthetic_psd(n_channels=n_ch, c_crossover=c_true)

        # Reverse probe shaft indexing: contact 0 is deep, contact 23 is superficial
        psd_rev = psd[::-1].copy()
        c_true_rev = (n_ch - 1) - c_true

        # Auto-orientation
        res_auto = vflip(psd_rev, freqs, orientation="auto", contact_spacing=40.0)
        assert res_auto.accepted is True
        assert res_auto.orientation == "deep_to_superficial"
        assert abs(res_auto.crossover_contact - c_true_rev) <= 0.25

        # Explicit deep_to_superficial
        res_deep = vflip(psd_rev, freqs, orientation="deep_to_superficial", contact_spacing=40.0)
        assert res_deep.accepted is True
        assert res_deep.crossover_contact == pytest.approx(res_auto.crossover_contact, abs=1e-12)

        # Incompatible orientation requirement must reject
        res_sup = vflip(psd_rev, freqs, orientation="superficial_to_deep", contact_spacing=40.0)
        assert res_sup.accepted is False
        assert res_sup.rejection_reason == "orientation_mismatch"
        assert res_sup.crossover_contact is None

    def test_no_motif_1_over_f_background_rejected(self):
        """Power spectra with smooth 1/f background and no spectrolaminar dissociation are rejected."""
        n_ch = 24
        freqs = np.linspace(2.0, 150.0, 100)
        rng = np.random.default_rng(42)

        # 1/f^1.5 background with channel variance but no spectral dissociation
        psd_1f = np.zeros((n_ch, len(freqs)))
        for c in range(n_ch):
            scale = 1.0 + 0.1 * rng.standard_normal()
            psd_1f[c] = scale * (freqs ** -1.5)

        # Default orientation
        res = vflip(psd_1f, freqs)
        assert res.accepted is False
        assert res.rejection_reason in ("insufficient_support", "orientation_mismatch", "no_crossover")
        assert res.crossover_contact is None

        # Auto orientation
        res_auto = vflip(psd_1f, freqs, orientation="auto")
        assert res_auto.accepted is False
        assert res_auto.rejection_reason in ("insufficient_support", "orientation_mismatch", "no_crossover")
        assert res_auto.crossover_contact is None

    def test_white_noise_rejection(self):
        """Uncorrelated white noise spectra are rejected by the support gate."""
        n_ch = 24
        freqs = np.linspace(2.0, 150.0, 100)
        rejection_count = 0
        total_runs = 5

        for seed in range(total_runs):
            rng = np.random.default_rng(seed)
            psd_white = rng.exponential(scale=1.0, size=(n_ch, len(freqs)))
            res = vflip(psd_white, freqs, min_support_score=6.0, orientation="auto")
            if not res.accepted:
                rejection_count += 1
                assert res.rejection_reason in ("insufficient_support", "no_crossover", "ambiguous_crossover")
                assert res.crossover_contact is None

        # White noise must reject across the overwhelming majority of draws
        assert rejection_count >= 4

    def test_missing_interior_and_boundary_contacts(self):
        """vFLIP recovers crossover accurately despite multiple missing interior and boundary contacts."""
        n_ch = 24
        c_true = 11.5
        freqs, psd = self._generate_synthetic_psd(n_channels=n_ch, c_crossover=c_true)

        # Mask boundary contacts (0, 23) AND multiple interior contacts, including
        # contacts adjacent to and spanning the crossover (e.g. 5, 6, 11, 12, 18)
        bad_indices = [0, 5, 6, 11, 12, 18, 23]
        bad_mask = np.zeros(n_ch, dtype=bool)
        bad_mask[bad_indices] = True
        psd[bad_mask] = np.nan

        res = vflip(psd, freqs, bad_channel_mask=bad_mask, contact_spacing=50.0)

        assert res.accepted is True
        assert res.n_missing == len(bad_indices)
        assert res.n_channels == n_ch
        assert abs(res.crossover_contact - c_true) <= 0.25
        assert np.all(np.isfinite(res.profile))
        assert res.crossover_depth_um == pytest.approx(res.crossover_contact * 50.0, abs=1e-4)

    def test_frequency_grid_resolution_invariance(self):
        """Crossover estimate and support metric are invariant to frequency bin resolution."""
        n_ch = 24
        c_true = 11.5
        results = []

        # Compare fine (0.5 Hz), medium (1.0 Hz), and coarse (2.0 Hz) regular grids
        for df in [0.5, 1.0, 2.0]:
            f_grid = np.arange(2.0, 150.0 + df, df)
            _, psd = self._generate_synthetic_psd(n_channels=n_ch, c_crossover=c_true, freqs=f_grid)
            res = vflip(psd, f_grid)
            assert res.accepted is True
            results.append(res)

        crossovers = [r.crossover_contact for r in results]
        scores = [r.support_score for r in results]

        # Crossover estimates agree within 0.05 channels across all grids
        assert max(crossovers) - min(crossovers) < 0.05
        # Support scores agree within 1.0 (no explosion with bin count)
        assert max(scores) - min(scores) < 1.0

    def test_irregular_frequency_axis_support(self):
        """vFLIP correctly processes non-uniformly spaced (e.g. logarithmic) frequency coordinates."""
        n_ch = 24
        c_true = 11.5
        freqs_geom = np.geomspace(4.0, 150.0, 80)
        _, psd = self._generate_synthetic_psd(n_channels=n_ch, c_crossover=c_true, freqs=freqs_geom)

        res = vflip(psd, freqs_geom)
        assert res.accepted is True
        assert abs(res.crossover_contact - c_true) <= 0.25
        assert res.orientation == "superficial_to_deep"
        assert res.support_score >= 6.0

    def test_insufficient_channels_structured_rejection(self):
        """Fewer than min_channels valid contacts immediately yields structured rejection."""
        freqs = np.linspace(2.0, 150.0, 50)

        # 1. Total channel count below threshold (6 < 8)
        psd_small = np.ones((6, 50))
        res1 = vflip(psd_small, freqs, min_channels=8)
        assert res1.accepted is False
        assert res1.rejection_reason == "insufficient_channels"
        assert res1.crossover_contact is None
        assert res1.support_score == -np.inf
        assert res1.n_channels == 6

        # 2. Total channels 24, but 18 flagged as bad -> 6 valid (< 8)
        psd_large = np.ones((24, 50))
        bad_mask = np.zeros(24, dtype=bool)
        bad_mask[:18] = True
        res2 = vflip(psd_large, freqs, bad_channel_mask=bad_mask, min_channels=8)
        assert res2.accepted is False
        assert res2.rejection_reason == "insufficient_channels"
        assert res2.crossover_contact is None
        assert res2.support_score == -np.inf
        assert res2.n_channels == 24
        assert res2.n_missing == 18

    def test_invalid_spacing_and_geometry_validation(self):
        """Invalid contact spacing or non-linear probe geometry raises ValueError."""
        freqs = np.linspace(2.0, 150.0, 50)
        psd = np.ones((16, 50))

        # Negative and zero spacing
        with pytest.raises(ValueError, match="contact_spacing"):
            vflip(psd, freqs, contact_spacing=-10.0)

        with pytest.raises(ValueError, match="contact_spacing"):
            vflip(psd, freqs, contact_spacing=0.0)

        # Non-finite spacing
        with pytest.raises(ValueError, match="contact_spacing"):
            vflip(psd, freqs, contact_spacing=np.nan)

        with pytest.raises(ValueError, match="contact_spacing"):
            vflip(psd, freqs, contact_spacing=np.inf)

        # Non-linear 2D ProbeGeometry
        df_2d = pd.DataFrame({
            "x": [0, 50, 0, 50] * 4,
            "y": [0, 0, 50, 50] * 4,
            "z": np.arange(16),
        })
        geom_2d = jnwb.probe_geometry(df_2d, units="um", strict_linear=False)
        assert geom_2d.is_linear is False

        with pytest.raises(ValueError, match="linear electrode shaft"):
            vflip(psd, freqs, probe_geometry=geom_2d)

    def test_failed_support_gate_on_weak_snr(self):
        """Sub-threshold SNR motif is rejected with reason 'insufficient_support'."""
        n_ch = 24
        freqs = np.linspace(2.0, 150.0, 100)
        rng = np.random.default_rng(42)

        # Noise background
        noise = 1.0 + 0.5 * rng.exponential(scale=1.0, size=(n_ch, len(freqs)))

        # Sub-threshold signal (scale=0.05)
        psd_weak = noise.copy()
        for c in range(n_ch):
            g_w = max(0.0, 1.0 - (c - 7.0) ** 2 / 40.0)
            b_w = max(0.0, 1.0 - (c - 16.0) ** 2 / 40.0)
            psd_weak[c] += 0.05 * g_w * np.exp(-((freqs - 75.0) ** 2) / 200.0) + 0.05 * b_w * np.exp(-((freqs - 18.0) ** 2) / 50.0)

        res_weak = vflip(psd_weak, freqs, min_support_score=6.0)
        assert res_weak.accepted is False
        assert res_weak.rejection_reason == "insufficient_support"
        assert res_weak.crossover_contact is None
        assert np.isfinite(res_weak.support_score)
        assert res_weak.support_score < 6.0

        # Strong signal (scale=2.0) with identical noise background
        psd_strong = noise.copy()
        for c in range(n_ch):
            g_w = max(0.0, 1.0 - (c - 7.0) ** 2 / 40.0)
            b_w = max(0.0, 1.0 - (c - 16.0) ** 2 / 40.0)
            psd_strong[c] += 2.0 * g_w * np.exp(-((freqs - 75.0) ** 2) / 200.0) + 2.0 * b_w * np.exp(-((freqs - 18.0) ** 2) / 50.0)

        res_strong = vflip(psd_strong, freqs, min_support_score=6.0)
        assert res_strong.accepted is True
        assert res_strong.rejection_reason is None
        assert res_strong.crossover_contact is not None
        assert res_strong.support_score >= 6.0



