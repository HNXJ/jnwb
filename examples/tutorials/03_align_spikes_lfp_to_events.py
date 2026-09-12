"""Tutorial 3: Align spikes and LFP to retrieved event onsets.

Run: python examples/tutorials/03_align_spikes_lfp_to_events.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_TUTORIALS = Path(__file__).resolve().parent
_REPO_ROOT = _TUTORIALS.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_TUTORIALS) not in sys.path:
    sys.path.insert(0, str(_TUTORIALS))

import jnwb
from _support import CODE_LABEL_A, TASK_TABLE, build_canonical_fixture


def main() -> None:
    path, receipt = build_canonical_fixture()
    onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    spike_times = jnwb.unit_spike_times(path, unit_index=0)
    t_ms, rate_hz, sem_hz = jnwb.raster_psth(
        spike_times,
        onsets,
        win_ms=(-100.0, 400.0),
        bin_ms=10.0,
    )
    assert t_ms.shape == rate_hz.shape == sem_hz.shape
    assert rate_hz.size > 0
    assert np.all(np.isfinite(rate_hz))

    lfp, fs_hz = jnwb.acquisition_channel(path, name="probe_0_lfp", channel=0)
    assert fs_hz == receipt.fs_hz

    # Extract continuous LFP epochs aligned to all onsets using epoch_continuous.
    epochs, time_axis_s = jnwb.epoch_continuous(
        lfp,
        onsets,
        win_s=(0.0, 0.4),
        fs=fs_hz,
    )
    assert epochs.shape == (len(onsets), int(0.4 * fs_hz))
    assert time_axis_s.shape == (int(0.4 * fs_hz),)

    beta = jnwb.band_power(
        epochs[0],
        fs=fs_hz,
        freq_range=jnwb.CANONICAL_BANDS["beta"],
        normalize=False,
    )
    assert np.isfinite(beta) and beta >= 0.0

    print(f"PSTH: {rate_hz.size} bins around {len(onsets)} onsets")
    print(f"Extracted {len(epochs)} LFP epochs of length {epochs.shape[1]}")
    print(f"beta power (post-onset epoch 0): {beta:.3f}")


if __name__ == "__main__":
    main()
