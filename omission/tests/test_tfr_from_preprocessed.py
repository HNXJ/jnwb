"""Tests for tfr_from_preprocessed loader (no synthetic fallback)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from omission.jnwb_ext.session import OmissionSession


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


def test_tfr_from_preprocessed_loads_npz(tmp_path: Path):
    """The corpus fully migrated to .npz 2026-08-11 (precompute_tfr_arrays.py); this loader
    globbed only *.npy until 2026-08-24, silently returning None for every real session. Fixed
    per context/09_conflicts_and_flagged_discrepancies.md item 2."""
    sess = _session_stub("sub-C31o_ses-230823_rec")
    power = np.zeros((3, 96, 99, 500), dtype=np.float32)
    power[0, 0, 0, 0] = 2.5
    channels = np.arange(96, dtype=np.int32)
    path = tmp_path / "sub-C31o_ses-230823-A-FEF-RRRR.npz"
    np.savez_compressed(path, power=power, channels=channels,
                         fit_exponent=np.zeros(96, dtype=np.float32),
                         fit_r2=np.ones(96, dtype=np.float32))
    loaded = sess.tfr_from_preprocessed("FEF", band=None, condition="RRRR", tfr_dir=tmp_path)
    assert loaded is not None
    assert loaded.shape == (3, 96, 99, 500)
    assert float(loaded[0, 0, 0, 0]) == 2.5


def test_tfr_from_preprocessed_prefers_npz_over_stale_npy(tmp_path: Path):
    """When both formats exist for the same (session, probe, area, condition), .npz must win --
    it is the corrected regeneration; a stale legacy .npy must not win by glob order (matching
    scripts/compute_channel_band_power_census.py's established precedence)."""
    sess = _session_stub("sub-C31o_ses-230823_rec")
    stale = np.full((3, 128, 99, 500), fill_value=9.0, dtype=np.float32)
    np.save(tmp_path / "sub-C31o_ses-230823-A-FEF-RRRR.npy", stale)
    fresh_power = np.full((3, 96, 99, 500), fill_value=1.0, dtype=np.float32)
    np.savez_compressed(tmp_path / "sub-C31o_ses-230823-A-FEF-RRRR.npz",
                         power=fresh_power, channels=np.arange(96, dtype=np.int32),
                         fit_exponent=np.zeros(96, dtype=np.float32),
                         fit_r2=np.ones(96, dtype=np.float32))
    loaded = sess.tfr_from_preprocessed("FEF", band=None, condition="RRRR", tfr_dir=tmp_path)
    assert loaded.shape == (3, 96, 99, 500)
    assert float(loaded[0, 0, 0, 0]) == 1.0


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
