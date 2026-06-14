"""Tests for jnwb visual QC control suite."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import jnwb
from src.analysis.visualization.jnwb_qc import (
    BLOCKED_QC_ANCHOR_PROVENANCE,
    BLOCKED_QC_EMPTY_EVENTS,
    BLOCKED_QC_NWB_ROOT_MISSING,
    BLOCKED_QC_SHAPE_CONTRACT,
    JnwbQCBlockedError,
    QCConfig,
    build_artifact_readback_qc,
    build_f005_readiness_qc,
    build_spk_visual_smoke,
    run_synthetic_fixture_qc,
    validate_epoch_shape,
    validate_event_address,
    validate_nwb_root,
)
from src.jnwb.schema import EventAddress

NWB_ROOT = Path(r"D:/analysis/nwb")


def _event_addr(*, p1_code: int = 101, n_events: int = 4) -> EventAddress:
    skey = "sub_test_ses"
    events = [
        {
            "condition": "AAAB",
            "onset_s": 1.0 + i * 0.5,
            "anchor": "p1",
            "condition_number": 1,
        }
        for i in range(n_events)
    ]
    return EventAddress(
        task="omission_glo_passive",
        conditions=["AAAB"],
        condition_numbers=[1],
        anchor="p1",
        sessions=[skey],
        events_by_session={skey: events},
        time_unit="s",
        p1_code=p1_code,
        correct_only=True,
    )


def _spk_batch(shape=(6, 3, 40)) -> jnwb.EpochBatch:
    data = np.random.poisson(1, shape).astype(np.float32)
    time_ms = np.linspace(-50, 50, shape[2], endpoint=False)
    return jnwb.EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=pd.DataFrame({"condition": ["AAAB"] * shape[0], "session_id": ["s1"] * shape[0]}),
        signal_metadata=pd.DataFrame({"area": ["V1"] * shape[1]}),
        manifest={"spec": {"signal": "SPK"}, "p1_code": 101},
    )


def test_refuses_missing_nwb_root():
    with pytest.raises(JnwbQCBlockedError) as exc:
        validate_nwb_root(Path("/nonexistent/nwb/root"))
    assert exc.value.code == BLOCKED_QC_NWB_ROOT_MISSING


def test_refuses_empty_events():
    ev = _event_addr(n_events=0)
    ev.events_by_session = {"sub_test_ses": []}
    with pytest.raises(JnwbQCBlockedError) as exc:
        validate_event_address(ev)
    assert exc.value.code == BLOCKED_QC_EMPTY_EVENTS


def test_rejects_code100_anchor():
    with pytest.raises(JnwbQCBlockedError) as exc:
        validate_event_address(_event_addr(p1_code=100))
    assert exc.value.code == BLOCKED_QC_ANCHOR_PROVENANCE


def test_spk_shape_contract_accepts_trial_unit_time():
    validate_epoch_shape("SPK", (4, 3, 50))


def test_spk_shape_contract_rejects_bad_shape():
    with pytest.raises(JnwbQCBlockedError) as exc:
        validate_epoch_shape("SPK", (0, 3, 50))
    assert exc.value.code == BLOCKED_QC_SHAPE_CONTRACT


def test_lfp_shape_contract_accepts_trial_channel_time():
    validate_epoch_shape("LFP", (4, 8, 100))


def test_analog_shape_contract_rejects_2d():
    with pytest.raises(JnwbQCBlockedError):
        validate_epoch_shape("MUAe", (4, 8))


def test_spk_visual_manifest_fields(tmp_path: Path):
    cfg = QCConfig(nwb_root=None, out_dir=tmp_path, data_label="SYNTHETIC_FIXTURE", command="pytest")
    manifest = build_spk_visual_smoke(_spk_batch(), cfg)
    for field in (
        "signal_class",
        "shape",
        "alignment_event",
        "time_base",
        "output_html",
        "data_label",
    ):
        assert field in manifest
    assert manifest["signal_class"] == "SPK"
    assert Path(manifest["output_html"]).exists()


def test_artifact_readback_roundtrip(tmp_path: Path):
    cfg = QCConfig(nwb_root=None, out_dir=tmp_path, data_label="SYNTHETIC_FIXTURE", command="pytest")
    manifest = build_artifact_readback_qc({"SPK": _spk_batch()}, cfg)
    assert manifest["panel"] == "06_artifact_readback_qc"
    assert (tmp_path / "artifacts" / "qc_spk_epochs.npz").exists()


def test_f005_readiness_no_nwb_extraction(tmp_path: Path):
    source = (REPO / "src" / "analysis" / "visualization" / "jnwb_qc.py").read_text(encoding="utf-8")
    start = source.index("def build_f005_readiness_qc")
    end = source.index("def run_visual_qc", start)
    block = source[start:end]
    assert "load_epochs" not in block
    assert "address_events" not in block
    assert "list_nwb_files" not in block

    cfg = QCConfig(nwb_root=None, out_dir=tmp_path, command="pytest")
    cfg.f005_epochs = tmp_path / "missing_epochs.npz"
    cfg.f005_classification = tmp_path / "missing_cls.csv"
    manifest = build_f005_readiness_qc(cfg)
    assert manifest["f005_status"] == "BLOCKED"
    assert manifest["blockers"]


def test_synthetic_fixture_labeled(tmp_path: Path):
    bundle = run_synthetic_fixture_qc(tmp_path / "syn", command="pytest")
    assert bundle["data_label"] == "SYNTHETIC_FIXTURE"
    manifest_path = tmp_path / "syn" / "bundle_manifest.json"
    assert manifest_path.exists()
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["data_label"] == "SYNTHETIC_FIXTURE"


@pytest.mark.skipif(not NWB_ROOT.exists(), reason="NWB root unavailable")
def test_real_nwb_visual_qc_smoke(tmp_path: Path):
    from src.analysis.visualization.jnwb_qc import run_visual_qc

    cfg = QCConfig(
        nwb_root=NWB_ROOT,
        out_dir=tmp_path / "real_qc",
        max_sessions=1,
        max_units=8,
        max_channels=8,
        command="pytest_real_smoke",
        data_label="REAL_NWB",
    )
    bundle = run_visual_qc(cfg)
    assert "inventory" in bundle["panels"]
    assert (cfg.out_dir / "bundle_manifest.json").exists()
