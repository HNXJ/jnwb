import numpy as np
import pandas as pd
import pytest
import jnwb


class TestIntegration021:

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
