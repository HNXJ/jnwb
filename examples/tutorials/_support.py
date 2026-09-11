"""Shared helpers for NWB workflow tutorials (synthetic fixtures only)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pynwb
from pynwb import NWBHDF5IO

from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    TASK_TABLE,
    canonical_co_resident_options,
    write_synth_nwb,
)


def build_canonical_fixture() -> tuple[Path, object]:
    """Write the co-resident synthetic NWB to a temp file; return path and receipt."""
    tmp = Path(tempfile.mkdtemp(prefix="jnwb_tutorial_"))
    path = tmp / "canonical.nwb"
    receipt = write_synth_nwb(path, canonical_co_resident_options())
    return path, receipt


def spike_times_for_unit(path: Path, unit_index: int = 0) -> np.ndarray:
    """Return sorted spike times (seconds) for one units-table row."""
    with NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        if nwb.units is None:
            raise ValueError("NWB file has no units table")
        return np.asarray(nwb.units["spike_times"][unit_index], dtype=np.float64)


def lfp_channel(path: Path, channel: int = 0) -> tuple[np.ndarray, float]:
    """Return one LFP channel (1-D) and its sampling rate in Hz."""
    with NWBHDF5IO(str(path), "r") as io:
        nwb = io.read()
        acq = nwb.acquisition["probe_0_lfp"]
        if hasattr(acq, "electrical_series"):
            series = next(iter(acq.electrical_series.values()))
        else:
            series = acq
        data = np.asarray(series.data[:, channel], dtype=np.float64)
        rate = float(series.rate)
    return data, rate


__all__ = [
    "CODE_LABEL_A",
    "CODE_LABEL_B",
    "TASK_TABLE",
    "build_canonical_fixture",
    "spike_times_for_unit",
    "lfp_channel",
]
