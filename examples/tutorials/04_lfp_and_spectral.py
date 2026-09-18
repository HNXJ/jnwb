"""Tutorial 04: LFP and Spectral Dynamics — Epoching, Wavelets, Decibels, and wPLI.

Run: python examples/tutorials/04_lfp_and_spectral.py
"""

from __future__ import annotations

import sys

import tempfile
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root.
_CHECKOUT = Path(__file__).resolve().parents[2]
if (_CHECKOUT / "jnwb" / "__init__.py").exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "synthetic_recording.nwb"
        receipt = write_synth_nwb(path, canonical_co_resident_options(seed=42))

        # 1. Retrieve continuous LFP acquisition and event onsets
        lfp, fs_hz = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=0)
        assert fs_hz == receipt.fs_hz
        onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        print(f"Loaded continuous LFP: {lfp.size} samples at {fs_hz} Hz")

        # 2. Continuous Epoching
        # win_s=(-0.1, 0.4) extracts 500 ms peri-event windows
        epochs, t_axis_s = jnwb.epoch_continuous(
            lfp,
            onsets,
            win_s=(-0.1, 0.4),
            fs=fs_hz,
            boundary_policy="drop",
        )
        assert epochs.ndim == 2
        print(f"Extracted {len(epochs)} epochs of length {epochs.shape[1]} samples")

        # 3. Welch Power Spectral Density
        freqs_psd, psd = jnwb.compute_psd(epochs[0], fs=fs_hz)
        assert len(freqs_psd) == len(psd)
        print(f"Welch PSD: {len(freqs_psd)} frequency bins ({freqs_psd[0]:.1f} to {freqs_psd[-1]:.1f} Hz)")

        # 4. Complex Morlet Time-Frequency Representation (TFR)
        tfr_freqs = np.linspace(10.0, 60.0, 6)
        tfr_res = jnwb.complex_tfr(epochs[0], fs=fs_hz, freqs=tfr_freqs, n_cycles=5.0)
        assert tfr_res.power.shape == (len(tfr_freqs), epochs.shape[1])
        print(f"Complex TFR power shape: {tfr_res.power.shape} (masked valid points: {np.sum(tfr_res.coi_mask)})")

        # 5. Band Power
        beta_power = jnwb.band_power(
            epochs[0],
            fs=fs_hz,
            freq_range=jnwb.CANONICAL_BANDS["beta"],
            normalize=False,
        )
        assert np.isfinite(beta_power) and beta_power >= 0.0
        print(f"Raw beta band power: {beta_power:.4f}")

        # 6. Baseline Normalization — Take the Logarithm Last (Invariant 2)
        baseline_epochs, _ = jnwb.epoch_continuous(
            lfp,
            onsets,
            win_s=(-0.1, 0.0),
            fs=fs_hz,
        )
        base_power = [
            jnwb.band_power(ep, fs=fs_hz, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
            for ep in baseline_epochs
        ]
        post_power = [
            jnwb.band_power(ep, fs=fs_hz, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
            for ep in epochs
        ]
        # Aggregate linear power first, divide, then apply 10 * log10 once
        db_change = jnwb.aggregate_to_db(
            np.array(post_power),
            np.array(base_power),
            how="mean_of_ratios",
            aggregate_over=0,
        )
        assert np.isfinite(db_change)
        print(f"Baseline-normalized beta response: {db_change:.2f} dB")

        # 7. Weighted Phase Lag Index (wPLI) — Reduces zero-lag sensitivity (Invariant 8)
        lfp_ch1, _ = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=1)
        epochs_ch1, _ = jnwb.epoch_continuous(lfp_ch1, onsets, win_s=(0.0, 0.3), fs=fs_hz)
        epochs_ch0, _ = jnwb.epoch_continuous(lfp, onsets, win_s=(0.0, 0.3), fs=fs_hz)
        wpli_res = jnwb.wpli(epochs_ch0[0], epochs_ch1[0], fs=fs_hz, freq_range=(15.0, 30.0))
        wpli_score = wpli_res["wpli"]
        assert 0.0 <= wpli_score <= 1.0
        print(f"Inter-channel beta wPLI: {wpli_score:.3f}")


if __name__ == "__main__":
    main()
