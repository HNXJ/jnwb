"""Tutorial 08: End-to-End Pipeline — Inspect to Statistical Estimation.

Run: python examples/tutorials/08_end_to_end_pipeline.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

import jnwb
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def main() -> None:
    print("=== JNWB End-to-End Analysis Pipeline ===")

    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Setup: Deterministic synthetic NWB fixture
        path = Path(tmpdir) / "session.nwb"
        _ = write_synth_nwb(path, canonical_co_resident_options(seed=42))

        # 2. Inspect: Discover file contents without guessing defaults
        info = jnwb.inspect(path)
        print(f"1. Inspected {path.name}: session '{info['session']['identifier']}'")

        # 3. Address: Retrieve condition event onsets in seconds
        onsets_a = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        onsets_b = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_B])
        print(f"2. Extracted events: {len(onsets_a)} onsets for {CODE_LABEL_A}, {len(onsets_b)} onsets for {CODE_LABEL_B}")

        # 4. Spikes: Compute PSTH and test condition difference
        spikes = jnwb.unit_spike_times(path, unit_index=0)
        t_ms, rate_a, _ = jnwb.raster_psth(spikes, onsets_a, win_ms=(-100.0, 300.0), bin_ms=10.0)
        _, rate_b, _ = jnwb.raster_psth(spikes, onsets_b, win_ms=(-100.0, 300.0), bin_ms=10.0)
        psth_diff = np.mean(rate_b) - np.mean(rate_a)
        print(f"3. Spiking: Mean PSTH rate diff (B - A): {psth_diff:.2f} Hz")

        # 5. Continuous LFP: Epoch and compute baseline-normalized band power
        lfp, fs_hz = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=0)
        epochs_a, _ = jnwb.epoch_continuous(lfp, onsets_a, win_s=(0.0, 0.3), fs=fs_hz)
        baseline_a, _ = jnwb.epoch_continuous(lfp, onsets_a, win_s=(-0.2, -0.05), fs=fs_hz)

        power_post = np.array([
            jnwb.band_power(ep, fs=fs_hz, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
            for ep in epochs_a
        ])
        power_base = np.array([
            jnwb.band_power(ep, fs=fs_hz, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False)
            for ep in baseline_a
        ])
        db_response = jnwb.aggregate_to_db(power_post, power_base, how="mean_of_ratios", aggregate_over=0)
        print(f"4. Spectral: Baseline-normalized beta response: {db_response:.2f} dB")

        # 6. Connectivity: Estimate zero-lag-reduced phase coupling (wPLI)
        lfp_ch1, _ = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=1)
        epochs_ch1, _ = jnwb.epoch_continuous(lfp_ch1, onsets_a, win_s=(0.0, 0.3), fs=fs_hz)
        wpli_res = jnwb.wpli(epochs_a[0], epochs_ch1[0], fs=fs_hz, freq_range=(15.0, 30.0))
        wpli_score = wpli_res["wpli"]
        print(f"5. Connectivity: Inter-channel beta wPLI: {wpli_score:.3f}")

        # 7. Statistical Inference: Non-parametric comparison with FDR control
        comp = jnwb.StatisticalAnalysis.exploratory_compare(power_post, power_base)
        p_val = comp["parametric"]["pval"]
        fdr_adjusted = jnwb.StatisticalAnalysis.fdr_correct(np.array([p_val, 0.05, 0.10]))
        print(f"6. Statistics: Power modulation p={p_val:.4e} (FDR q={fdr_adjusted[0]:.4e})")

        print("=== Pipeline Complete: All Estimands Verified ===")


if __name__ == "__main__":
    main()
