#!/usr/bin/env python3
"""
Tests for scripts/materialize_session_arrays.py.

These exercise the real pipeline against a real session (sidecar + NWB + jnwb
disk cache) when available on this machine, and are skipped otherwise -- no
synthetic/mocked spike data is substituted for the "matches live computation"
check, since the whole point of the script is numerical agreement with
jnwb.session.OmissionSession on real data.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "materialize_session_arrays.py"
CATALOG = REPO / "artifacts" / "data" / "nwb_catalog.json"
META_ROOT = Path("D:/workspace/data/metadata")

SESSION = "sub-C31o_ses-230823_rec"


def _catalog_session_path(stem: str):
    if not CATALOG.is_file():
        return None
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for s in data.get("sessions", []):
        if s.get("stem") == stem:
            return Path(s["path"])
    return None


def _real_data_available() -> bool:
    nwb_path = _catalog_session_path(SESSION)
    if nwb_path is None or not nwb_path.is_file():
        return False
    if not (META_ROOT / SESSION / "units.csv").is_file():
        return False
    return True


requires_real_data = pytest.mark.skipif(
    not _real_data_available(),
    reason=(
        f"Real NWB + sidecar for {SESSION} not available on this machine "
        f"(checked catalog={CATALOG}, meta_root={META_ROOT})"
    ),
)


@requires_real_data
def test_script_runs_and_produces_scoped_output(tmp_path):
    out_root = tmp_path / "materialized"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--session",
            SESSION,
            "--area",
            "V1",
            "--out-root",
            str(out_root),
            "--overwrite",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    out_dir = out_root / SESSION / "phase2_all_w-1000_4000_V1"
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Scoped: only spike arrays for one condition/window, MB-scale, nowhere near
    # the ~172 GB source NWB.
    total_bytes = sum(manifest["file_bytes"].values())
    assert total_bytes < 50 * 1024 * 1024  # well under 50 MB for a single-area slice
    assert manifest["n_units"] > 0
    assert manifest["n_trials"] > 0

    for name in ("unit_ids.npy", "trial_onsets.npy", "offsets.npy", "spike_times_ms.npy"):
        assert (out_dir / name).is_file()


@requires_real_data
def test_idempotent_skip_without_overwrite(tmp_path):
    out_root = tmp_path / "materialized"
    common_args = [
        sys.executable,
        str(SCRIPT),
        "--session",
        SESSION,
        "--area",
        "V1",
        "--out-root",
        str(out_root),
    ]
    first = subprocess.run(common_args, cwd=str(REPO), capture_output=True, text=True, timeout=600)
    assert first.returncode == 0, first.stdout + first.stderr

    out_dir = out_root / SESSION / "phase2_all_w-1000_4000_V1"
    manifest_path = out_dir / "manifest.json"
    mtime_before = manifest_path.stat().st_mtime_ns

    second = subprocess.run(common_args, cwd=str(REPO), capture_output=True, text=True, timeout=600)
    assert second.returncode == 0, second.stdout + second.stderr
    assert "skipping" in second.stdout.lower()
    assert manifest_path.stat().st_mtime_ns == mtime_before


@requires_real_data
def test_materialized_spikes_match_live_jnwb_computation(tmp_path):
    """The core correctness check: materialized per-trial spike windows must
    exactly match what OmissionSession.get_spike_times() + get_epochs() compute
    directly, for real units/trials."""
    import jnwb as oa

    out_root = tmp_path / "materialized"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--session",
            SESSION,
            "--area",
            "V1",
            "--max-units",
            "3",
            "--out-root",
            str(out_root),
            "--overwrite",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    out_dir = out_root / SESSION / "phase2_all_w-1000_4000_V1"
    unit_ids = np.load(out_dir / "unit_ids.npy")
    trial_onsets = np.load(out_dir / "trial_onsets.npy")
    offsets = np.load(out_dir / "offsets.npy")
    spike_times_ms = np.load(out_dir / "spike_times_ms.npy", mmap_mode="r")

    nwb_path = _catalog_session_path(SESSION)
    session = oa.read(nwb_path)
    epochs = session.get_epochs(phase=2, condition=None, correct_only=True).reset_index(drop=True)

    assert len(epochs) == len(trial_onsets)
    np.testing.assert_allclose(
        epochs["start_time"].to_numpy(dtype=np.float64), trial_onsets, rtol=0, atol=1e-9
    )

    checked_any = False
    for u_i, uid in enumerate(unit_ids):
        live_spikes = session.get_spike_times(int(uid))
        if live_spikes is None or len(live_spikes) == 0:
            continue
        live_spikes = np.sort(np.asarray(live_spikes, dtype=np.float64))
        for t_i in range(min(5, len(trial_onsets))):
            onset = trial_onsets[t_i]
            lo = np.searchsorted(live_spikes, onset - 1.0, side="left")
            hi = np.searchsorted(live_spikes, onset + 4.0, side="right")
            expected_rel_ms = (live_spikes[lo:hi] - onset) * 1000.0

            off_lo, off_hi = offsets[u_i, t_i], offsets[u_i, t_i + 1]
            materialized_rel_ms = np.asarray(spike_times_ms[off_lo:off_hi], dtype=np.float64)

            np.testing.assert_allclose(materialized_rel_ms, expected_rel_ms, rtol=0, atol=1e-3)
            checked_any = True

    assert checked_any, "no unit/trial pair with spikes was found to verify against"


@requires_real_data
def test_condition_and_phase_flags_produce_a_scoped_matching_subset(tmp_path):
    """Regression test for the docked TBI: --condition/--phase were real
    argparse options but had no test coverage exercising them explicitly
    (only the all-conditions default path was tested)."""
    import jnwb as oa

    out_root = tmp_path / "materialized"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--session",
            SESSION,
            "--area",
            "V1",
            "--condition",
            "AAXB",
            "--phase",
            "3",
            "--max-units",
            "3",
            "--out-root",
            str(out_root),
            "--overwrite",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    out_dir = out_root / SESSION / "phase3_AAXB_w-1000_4000_V1"
    manifest_path = out_dir / "manifest.json"
    assert manifest_path.is_file()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["n_trials"] > 0

    trial_onsets = np.load(out_dir / "trial_onsets.npy")

    nwb_path = _catalog_session_path(SESSION)
    session = oa.read(nwb_path)
    condition_epochs = session.get_epochs(phase=3, condition="AAXB", correct_only=True).reset_index(drop=True)

    # A condition-scoped materialization must be a strict subset of the
    # all-conditions trial set, matching exactly for that one condition.
    assert len(condition_epochs) == len(trial_onsets)
    np.testing.assert_allclose(
        condition_epochs["start_time"].to_numpy(dtype=np.float64), trial_onsets, rtol=0, atol=1e-9
    )
