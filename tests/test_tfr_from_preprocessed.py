"""Tests for tfr_from_preprocessed loader (no synthetic fallback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from jnwb.session import OmissionSession


def _session_stub(stem: str = "sub-C31o_ses-230823_rec") -> OmissionSession:
    """Build OmissionSession without opening NWB."""
    obj = OmissionSession.__new__(OmissionSession)
    obj.nwb_path = Path(f"D:/analysis/nwb/{stem}.nwb")
    obj.context = "omission_glo_passive"
    obj.nwb = None
    obj._metadata = {}
    obj._units_df = None
    obj._electrodes_df = None
    obj._intervals_df = None
    obj._spike_cache = {}
    return obj


def test_tfr_from_preprocessed_loads_existing(tmp_path: Path):
    sess = _session_stub("sub-C31o_ses-230823_rec")
    arr = np.zeros((3, 128, 99, 500), dtype=np.float32)
    arr[0, 0, 0, 0] = 1.5
    path = tmp_path / "sub-C31o_ses-230823-A-FEF-RRRR.npy"
    np.save(path, arr)
    loaded = sess.tfr_from_preprocessed("FEF", band=None, condition="RRRR", tfr_dir=tmp_path)
    assert loaded is not None
    assert loaded.shape == (3, 128, 99, 500)
    assert float(loaded[0, 0, 0, 0]) == 1.5


def test_tfr_from_preprocessed_missing_returns_none(tmp_path: Path):
    sess = _session_stub("sub-V182o_ses-260629")
    loaded = sess.tfr_from_preprocessed("PFC", band=None, condition="RRRR", tfr_dir=tmp_path)
    assert loaded is None


def test_plot_tfr_missing_does_not_synthesize(tmp_path: Path, monkeypatch):
    sess = _session_stub("sub-V182o_ses-260629")
    monkeypatch.setenv("OMISSION_TFR_DIR", str(tmp_path))
    out = sess.plot_tfr(area="PFC", condition="RRRR")
    assert out["status"] == "missing_tfr"
    assert out["figure"] is None
    assert "error" in out
