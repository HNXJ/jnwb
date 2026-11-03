"""phase_locking_index refuses non-finite LFP timestamps by name.

A NaN step compares False to 0, so the strictly-increasing check let a NaN timestamp through and
the NaN phase it produced was blamed on lfp_phase.
"""

from __future__ import annotations

import numpy as np
import pytest

from jnwb.spiking import phase_locking_index

FS = 1000.0


def _inputs():
    t = np.arange(2000) / FS
    phase = np.angle(np.exp(1j * 2 * np.pi * 8.0 * t))
    spikes = np.linspace(0.1, 1.9, 40)
    return spikes, phase, t


@pytest.mark.parametrize("bad", [np.nan, np.inf])
def test_a_non_finite_timestamp_is_refused_by_name(bad):
    spikes, phase, t = _inputs()
    t[700] = bad
    assert np.any((spikes > t[699]) & (spikes < t[701])), "fixture must put a spike beside it"
    with pytest.raises(ValueError, match=r"phase_locking_index: lfp_timestamps\[700\] is"):
        phase_locking_index(spikes, phase, t)


def test_finite_timestamps_still_give_a_phase_estimate():
    spikes, phase, t = _inputs()
    out = phase_locking_index(spikes, phase, t)
    assert out["n_spikes"] == 40
    assert np.isfinite(out["rayleigh_z"]) and np.isfinite(out["preferred_phase"])
