from __future__ import annotations

import numpy as np

from src.analysis.visualization.fig07_slotwise_local_lfp_tfr import _slice_time_rebased


def test_slice_time_rebased_nonempty():
    times = np.linspace(-2000, 2000, 4001, dtype=float)
    power_db = np.zeros((10, times.size), dtype=float)

    times_disp, power_disp = _slice_time_rebased(
        times,
        power_db,
        display_window_ms=(-1031, 1031),
    )

    assert times_disp.size > 0
    assert power_disp.shape == (10, times_disp.size)
    assert times_disp.min() >= -1031
    assert times_disp.max() <= 1031

