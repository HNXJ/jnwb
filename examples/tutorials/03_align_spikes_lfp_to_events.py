"""Tutorial 3: Align spikes and LFP to retrieved event onsets.

Run: python examples/tutorials/03_align_spikes_lfp_to_events.py
"""

from __future__ import annotations

import numpy as np

import jnwb
from examples.tutorials._support import (
    CODE_LABEL_A,
    TASK_TABLE,
    build_canonical_fixture,
    lfp_channel,
    spike_times_for_unit,
)


def main() -> None:
    path, receipt = build_canonical_fixture()
    onsets = jnwb.event_onsets(path, table=TASK_TABLE, codes=[CODE_LABEL_A])
    np.testing.assert_allclose(onsets, receipt.task_onsets_s[::2])

    spike_times = spike_times_for_unit(path, unit_index=0)
    t_ms, rate_hz, sem_hz = jnwb.raster_psth(
        spike_times,
        onsets,
        win_ms=(-100.0, 400.0),
        bin_ms=10.0,
    )
    assert t_ms.shape == rate_hz.shape == sem_hz.shape
    assert rate_hz.size > 0
    assert np.all(np.isfinite(rate_hz))

    lfp, fs_hz = lfp_channel(path, channel=0)
    assert fs_hz == receipt.fs_hz

    # Epoch-average band power in a short post-onset window for the first event.
    onset_s = float(onsets[0])
    i0 = int(onset_s * fs_hz)
    i1 = int((onset_s + 0.4) * fs_hz)
    segment = lfp[i0:i1]
    beta = jnwb.band_power(
        segment,
        fs=fs_hz,
        freq_range=jnwb.CANONICAL_BANDS["beta"],
        normalize=False,
    )
    assert np.isfinite(beta) and beta >= 0.0

    print(f"PSTH: {rate_hz.size} bins around {len(onsets)} onsets")
    print(f"beta power (post-onset segment): {beta:.3f}")


if __name__ == "__main__":
    main()
