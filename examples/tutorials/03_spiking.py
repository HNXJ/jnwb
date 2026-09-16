"""Tutorial 03: Spiking Dynamics — Raster, PSTH, Causal Smoothing, and Onset Latency.

Run: python examples/tutorials/03_spiking.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

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
        _ = write_synth_nwb(path, canonical_co_resident_options(seed=42))

        # 1. Retrieve condition onsets (seconds)
        onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
        assert len(onsets) > 0

        # 2. Extract spike timestamps for unit 0 (seconds)
        spike_times = jnwb.unit_spike_times(path, unit_index=0)
        assert len(spike_times) > 0
        print(f"Unit 0: {len(spike_times)} spikes across recording")

        # 3. Peri-Stimulus Time Histogram (PSTH)
        # Spike times in seconds, win_ms in milliseconds, bin_ms in milliseconds
        t_ms, rate_hz, sem_hz = jnwb.raster_psth(
            spike_times,
            onsets,
            win_ms=(-100.0, 400.0),
            bin_ms=10.0,
        )
        assert t_ms.shape == rate_hz.shape == sem_hz.shape
        assert np.all(np.isfinite(rate_hz))
        print(f"PSTH computed: {rate_hz.size} bins from {t_ms[0]} to {t_ms[-1]} ms")
        print(f"Peak firing rate: {np.max(rate_hz):.2f} +/- {sem_hz[np.argmax(rate_hz)]:.2f} Hz")

        # 4. Causal Exponential Smoothing
        # Prevents future acausal leakage into pre-stimulus baseline
        smooth_hz = jnwb.causal_exp_smooth(rate_hz, bin_ms=10.0, tau_ms=25.0)
        assert smooth_hz.shape == rate_hz.shape
        print(f"Causal smoothed peak rate: {np.max(smooth_hz):.2f} Hz")

        # 5. Exponential Onset Latency Fitting
        fit = jnwb.fit_exponential_onset(t_ms, smooth_hz, t0_bounds_ms=(0.0, 200.0))
        assert "t0" in fit and "bound_status" in fit
        print(f"Onset latency fit: t0={fit['t0']:.1f} ms, R2={fit['r2']:.3f}, status={fit['bound_status']}")

        # 6. Response Metrics and Significance
        # Every window parameter names its unit. This script mixes both scales in one
        # body -- `win_ms` above is milliseconds, these are seconds -- and the names are
        # what keep that straight.
        metrics = jnwb.compute_response_metrics(
            spike_times,
            onsets,
            baseline_window_s=(-0.2, 0.0),
            response_window_s=(0.0, 0.2),
        )
        assert "response_rate" in metrics and "baseline_rate" in metrics
        sig = jnwb.classify_response_significance(metrics)
        print(f"Response rate: {metrics['response_rate']:.2f} Hz vs Baseline: {metrics['baseline_rate']:.2f} Hz")
        print(f"Significant modulation: {sig['is_significant']}")


if __name__ == "__main__":
    main()
