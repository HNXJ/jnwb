from __future__ import annotations

import numpy as np

from src.analysis.visualization.fig05_slotwise_spk import _slice_rebase_time, SLOT_ONSET_MS


def test_slot_rebase_time_nonempty():
    # p1-relative axis similar to artifact: centers -499.5..4123.5 in 1ms steps
    time_ms_p1 = np.arange(-499.5, 4123.5 + 0.5, 1.0, dtype=float)

    # p2 onset should be 1031ms -> omission-relative window -1000..+1000 => p1 slice 31..2031
    time_rel, mask = _slice_rebase_time(
        time_ms_p1,
        slot_onset_ms=SLOT_ONSET_MS["p2"],
        window_ms=(-1000, 1000),
    )
    assert np.any(mask)
    assert time_rel.size > 0
    # Bounds should be approximately -1000..+1000 (edge handling depends on center conventions)
    assert time_rel.min() >= -1001.0
    assert time_rel.max() < 1001.0

