"""Independent integration verification test suite for all five 0.2.1 primitives.

Verifies:
1. aperiodic_fit & AperiodicFitResult
2. relative_power
3. exact statistics (exact_sign_flip, mann_whitney_p_floor, clopper_pearson)
4. stream_npz_array
5. probe_geometry & ProbeGeometry

Tests composition, cross-primitive assumptions, boundary neutrality, and failure semantics.
"""
from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

import jnwb


class TestIntegration021:
    """Integration and cross-primitive verification for 0.2.1 primitives."""

    def test_all_five_primitives_exported_at_top_level(self):
        """Verify export and availability of all new 0.2.1 symbols."""
        expected_symbols = [
            # 0.2.1-01
            "aperiodic_fit",
            "AperiodicFitResult",
            # 0.2.1-02
            "relative_power",
            # 0.2.1-03
            "exact_sign_flip",
            "mann_whitney_p_floor",
            "clopper_pearson",
            # 0.2.1-04
            "stream_npz_array",
            # 0.2.1-05
            "probe_geometry",
            "ProbeGeometry",
        ]
        for sym in expected_symbols:
            assert sym in jnwb.__all__, f"{sym} missing from jnwb.__all__"
            assert hasattr(jnwb, sym), f"{sym} missing from jnwb module namespace"

    def test_statistical_analysis_parity(self):
        """Verify StatisticalAnalysis exposes the exact statistics methods."""
        sa = jnwb.StatisticalAnalysis
        assert hasattr(sa, "exact_sign_flip")
        assert hasattr(sa, "mann_whitney_p_floor")
        assert hasattr(sa, "clopper_pearson")

        # Check equivalence of calling via top-level vs StatisticalAnalysis
        diffs = [0.5, 1.2, -0.3, 0.8, 0.4]
        res1 = jnwb.exact_sign_flip(diffs, alternative="greater")
        res2 = sa.exact_sign_flip(diffs, alternative="greater")
        assert res1 == res2

        floor1 = jnwb.mann_whitney_p_floor(5, 5, alternative="two-sided")
        floor2 = sa.mann_whitney_p_floor(5, 5, alternative="two-sided")
        assert floor1 == floor2

        ci1 = jnwb.clopper_pearson(7, 10, alpha=0.05)
        ci2 = sa.clopper_pearson(7, 10, alpha=0.05)
        assert ci1 == ci2

    def test_probe_geometry_vflip_readiness(self):
        """Verify probe_geometry outputs satisfy all structural preconditions for vFLIP."""
        # Create a 16-channel linear silicon probe with 20 um pitch along Z axis (0, 0, z)
        n_ch = 16
        pitch_um = 20.0
        # Channels intentionally shuffled in the table to test ordering recovery
        shuffled_idx = np.array([5, 2, 9, 0, 15, 7, 1, 14, 8, 3, 11, 4, 13, 6, 12, 10])
        z_coords = shuffled_idx * pitch_um

        df = pd.DataFrame({
            "x": np.zeros(n_ch),
            "y": np.zeros(n_ch),
            "z": z_coords,
            "group_name": ["shank0"] * n_ch,
        }, index=shuffled_idx)

        geom = jnwb.probe_geometry(df, units="um", nominal_pitch=20.0, strict_linear=True)

        assert isinstance(geom, jnwb.ProbeGeometry)
        assert geom.is_linear is True
        assert geom.is_uniform is True
        assert geom.nominal_pitch == pytest.approx(20.0)
        assert geom.units == "um"
        assert geom.orientation is not None
        # Orientation must be along Z axis: (0, 0, 1)
        assert np.allclose(np.abs(geom.orientation), [0.0, 0.0, 1.0], atol=1e-5)

        # Sorted channels along probe shaft: must reconstruct 0..15 monotonic order
        sorted_pos = geom.contact_positions[geom.linear_order]
        sorted_ch = geom.channel_ids[geom.linear_order]
        assert np.array_equal(sorted_ch, np.arange(n_ch))
        # Differences in z must strictly equal pitch_um
        diffs = np.diff(sorted_pos[:, 2])
        assert np.allclose(diffs, pitch_um)

    def test_spectral_conventions_shared(self):
        """Verify spectral conventions and estimand boundaries between aperiodic_fit and relative_power."""
        freqs = np.linspace(5.0, 100.0, 96)
        # Synthetic PSD: 1/f^2 (offset=4.0, exponent=2.0)
        true_offset = 4.0
        true_exponent = 2.0
        psd_baseline = 10.0 ** (true_offset - true_exponent * np.log10(freqs))

        # Condition: 20% power increase across all frequencies
        psd_condition = psd_baseline * 1.20

        # 1. Fit aperiodic model on baseline
        fit = jnwb.aperiodic_fit(freqs, psd_baseline, freq_range=(10.0, 80.0), mode="fixed")
        assert fit.accepted is True
        assert fit.offset == pytest.approx(true_offset, abs=1e-4)
        assert fit.exponent == pytest.approx(true_exponent, abs=1e-4)
        assert fit.knee is None
        assert fit.r_squared == pytest.approx(1.0, abs=1e-4)

        # 2. Compute relative power
        rel_mean_ratios = jnwb.relative_power(psd_condition, psd_baseline, model="mean_of_ratios", axis=0)
        rel_ratio_means = jnwb.relative_power(psd_condition, psd_baseline, model="ratio_of_means", axis=0)
        rel_log_ratio = jnwb.relative_power(psd_condition, psd_baseline, model="log_ratio")

        assert rel_mean_ratios == pytest.approx(1.20)
        assert rel_ratio_means == pytest.approx(1.20)
        # Log ratio must be in dB: 10 * log10(1.20) ~= 0.7918 dB
        assert np.allclose(rel_log_ratio, 10.0 * np.log10(1.20))

    def test_end_to_end_cross_primitive_pipeline(self, tmp_path):
        """End-to-end integration pipeline exercising all five primitives in composition."""
        rng = np.random.default_rng(12345)

        # Step 1: Probe Geometry
        n_contacts = 8
        coords = np.zeros((n_contacts, 3))
        coords[:, 2] = np.arange(n_contacts) * 50.0  # 50 um pitch in z
        df_electrodes = pd.DataFrame(coords, columns=["x", "y", "z"])
        geom = jnwb.probe_geometry(df_electrodes, units="um", nominal_pitch=50.0)
        assert geom.is_linear and geom.is_uniform

        # Step 2: Continuous multi-channel data written to compressed NPZ
        n_samples = 4000
        fs = 1000.0
        t = np.arange(n_samples) / fs
        # Generate 8-channel signals with 1/f background and 20 Hz oscillation
        lfp_raw = np.zeros((n_contacts, n_samples), dtype=np.float32)
        for ch in range(n_contacts):
            noise = rng.normal(size=n_samples)
            # Simple 1/f via cumulative sum + decay
            ar = np.zeros(n_samples)
            for i in range(1, n_samples):
                ar[i] = 0.95 * ar[i - 1] + noise[i]
            # Add 20 Hz oscillation
            osc = 2.0 * np.sin(2 * np.pi * 20.0 * t)
            lfp_raw[ch] = (ar + osc).astype(np.float32)

        npz_file = tmp_path / "lfp_archive.npz"
        np.savez_compressed(npz_file, lfp=lfp_raw)

        # Step 3: Stream array slice without full memory load
        # Stream first 4 channels, first 2000 samples
        streamed_lfp = jnwb.stream_npz_array(npz_file, "lfp", (slice(0, 4), slice(0, 2000)))
        assert streamed_lfp.shape == (4, 2000)
        assert np.array_equal(streamed_lfp, lfp_raw[0:4, 0:2000])

        # Step 4: Compute PSD on streamed channels
        from scipy import signal
        freqs, psd = signal.welch(streamed_lfp, fs=fs, nperseg=500, axis=1)
        assert psd.shape == (4, len(freqs))

        # Step 5: Aperiodic fit across channels (multidimensional batch)
        # Pass positive frequencies (excluding 0 Hz DC component)
        pos = freqs > 0
        fits = jnwb.aperiodic_fit(freqs[pos], psd[:, pos], freq_range=(5.0, 45.0), mode="fixed")
        assert len(fits) == 4
        for f in fits:
            assert isinstance(f, jnwb.AperiodicFitResult)
            assert f.accepted is True
            assert f.exponent > 0.0

        # Step 6: Relative power calculation against baseline
        baseline_psd = psd * 0.8  # baseline has 20% less power
        rel_power = jnwb.relative_power(psd, baseline_psd, model="mean_of_ratios", axis=0)
        # Ratio across channels: (psd / (0.8 * psd)) = 1 / 0.8 = 1.25
        assert np.allclose(rel_power, 1.25)

        # Step 7: Session-level exact hypothesis test on condition differences
        # Differences between condition and baseline for a band of interest
        band_mask = (freqs >= 18.0) & (freqs <= 22.0)
        cond_band = np.mean(psd[:, band_mask], axis=1)
        base_band = np.mean(baseline_psd[:, band_mask], axis=1)
        diffs = cond_band - base_band

        # All 4 channels show positive increase -> exact sign flip test
        obs_mean, p_val, p_floor = jnwb.exact_sign_flip(diffs, alternative="greater")
        assert obs_mean > 0
        # For N=4, one-sided floor is 1 / 2^4 = 1/16 = 0.0625
        assert p_floor == pytest.approx(1.0 / 16.0)
        assert p_val == pytest.approx(1.0 / 16.0)  # Most extreme configuration

        # Confirm exact combinatorial rank sum floor
        floor_rank = jnwb.mann_whitney_p_floor(4, 4, alternative="greater")
        assert floor_rank == pytest.approx(1.0 / 70.0)

    def test_invalid_input_fail_loud_across_all_primitives(self, tmp_path):
        """Verify strict fail-loud behavior for invalid inputs across all five primitives."""
        # 1. aperiodic_fit: invalid freq_range minimum <= 0
        with pytest.raises(ValueError, match="freq_range minimum must be strictly positive"):
            jnwb.aperiodic_fit(np.array([1.0, 2.0, 3.0, 4.0]), np.ones(4), freq_range=(0.0, 3.0))

        # 2. relative_power: negative power input
        with pytest.raises(ValueError, match="power contains negative values"):
            jnwb.relative_power(np.array([-1.0, 2.0]), np.array([1.0, 2.0]))

        # 3. exact_sign_flip: non-finite diffs
        with pytest.raises(ValueError, match="finite numerical values"):
            jnwb.exact_sign_flip([1.0, np.nan, 3.0])

        # 4. stream_npz_array: missing file
        with pytest.raises(FileNotFoundError, match="NPZ archive not found"):
            jnwb.stream_npz_array(tmp_path / "nonexistent.npz", "key")

        # 5. probe_geometry: duplicate coordinates
        dup_df = pd.DataFrame({"x": [0, 0], "y": [0, 0], "z": [10, 10]})
        with pytest.raises(ValueError, match="Duplicate contact coordinates"):
            jnwb.probe_geometry(dup_df, units="um")

    def test_probe_geometry_composition_with_layer_classification(self):
        """Verify probe_geometry coordinates directly feed depth classification."""
        # Contact depths from 100 to 1600 um
        n_contacts = 16
        z_um = np.linspace(100.0, 1600.0, n_contacts)
        df = pd.DataFrame({"x": np.zeros(n_contacts), "y": np.zeros(n_contacts), "z": z_um})

        geom = jnwb.probe_geometry(df, units="um", nominal_pitch=100.0, strict_linear=True)
        assert geom.is_linear is True

        # Classify each channel using jnwb.classify_layer_from_depth
        layers = [
            jnwb.classify_layer_from_depth(ch, df, depth_unit=geom.units, threshold=1000.0)
            for ch in geom.channel_ids
        ]
        assert len(layers) == n_contacts
        assert all(l in ("Superficial", "Deep") for l in layers)
        # Channel 0 (z=100 um) is Superficial, channel 15 (z=1600 um) is Deep
        assert layers[0] == "Superficial"
        assert layers[-1] == "Deep"

