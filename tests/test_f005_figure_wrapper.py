"""Tests for f005 artifact-only PSTH category figure wrapper."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import json

import numpy as np
import pandas as pd
import pytest

import jnwb
from scripts.classify_units_s_s_o import assign_display_class
from src.analysis.visualization.f005 import (
    AFAMILY_CONDITIONS,
    BLOCKED_F005_AREA_METADATA_MISSING,
    BLOCKED_F005_ARTIFACT_MISSING,
    BLOCKED_F005_CLASSIFICATION_MISSING,
    CLASSIFY_COMMAND,
    EPOCH_BUILD_COMMAND,
    F005FigureBlockedError,
    compute_class_condition_psths,
    load_f005_inputs,
    run_f005_figure,
    validate_f005_anchor_provenance,
)


FORBIDDEN_IN_FIGURE_LAYER = (
    "list_nwb_files",
    "address_events",
    "address_signals",
    "load_epochs",
    "pynwb",
    "NWBHDF5IO",
)


def _make_epoch_batch(session: str = "sub_test_ses_001", n_trials: int = 8) -> jnwb.EpochBatch:
    n_units = 6
    n_time = 500
    data = np.random.poisson(2, size=(n_trials, n_units, n_time)).astype(np.float32)
    time_ms = np.linspace(-100, 400, n_time, endpoint=False)
    cond_nums = [1, 3, 4, 5]
    trial_meta = pd.DataFrame(
        {
            "trial_global": list(range(n_trials)),
            "session_id": [session] * n_trials,
            "condition": [AFAMILY_CONDITIONS[i % 4] for i in range(n_trials)],
            "condition_number": [cond_nums[i % 4] for i in range(n_trials)],
        }
    )
    signal_meta = pd.DataFrame(
        {
            "session_id": [session] * n_units,
            "signal_id": list(range(n_units)),
            "unit_id": [str(i) for i in range(n_units)],
            "area": ["V1", "V2", "V1", "V2", "PM", "unknown"][:n_units],
            "signal_class": ["SPK"] * n_units,
        }
    )
    return jnwb.EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest={
            "spec": {"signal": "SPK", "window_ms": (-100, 400), "backend": "numpy"},
            "conditions": AFAMILY_CONDITIONS,
            "sessions": [session],
            "session_id": session,
            "anchor": "p1",
            "p1_code": 101,
            "bin_ms": 1.0,
        },
    )


def _make_classification(session: str = "sub_test_ses_001", n_units: int = 6) -> pd.DataFrame:
    is_s_plus = np.array([True, False, False, False, False, False])
    is_s_minus = np.array([False, True, False, False, False, False])
    is_ox = np.array([False, False, True, False, False, False])
    display = assign_display_class(is_s_plus, is_s_minus, is_ox)
    return pd.DataFrame(
        {
            "unit_idx": list(range(n_units)),
            "unit_id": [str(i) for i in range(n_units)],
            "session": [session] * n_units,
            "area": ["V1", "V2", "V1", "V2", "PM", "unknown"][:n_units],
            "display_class": display,
            "is_s_plus": is_s_plus,
            "is_s_minus": is_s_minus,
            "is_ox": is_ox,
        }
    )


def _write_fixture(tmp_path: Path, *, bad_anchor: bool = False, all_unknown_area: bool = False) -> dict[str, Path]:
    session = "sub_test_ses_001"
    epochs_path = tmp_path / "afamily_spk_p1_epochs.npz"
    manifest_path = tmp_path / "afamily_spk_p1_epochs_manifest.json"
    classification_path = tmp_path / "unit_classification.csv"

    batch = _make_epoch_batch(session=session)
    manifest = jnwb.save_epoch_artifact(
        batch,
        out=epochs_path,
        manifest=manifest_path,
        command="pytest",
        input_nwb_paths=["/fake/session.nwb"],
    )
    if bad_anchor:
        manifest["p1_code"] = 100
        manifest["time_base"] = "fixation_relative"
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    cls = _make_classification(session=session)
    if all_unknown_area:
        cls["area"] = "unknown"
    cls.to_csv(classification_path, index=False)

    return {
        "epochs": epochs_path,
        "manifest": manifest_path,
        "classification": classification_path,
    }


def test_figure_script_refuses_missing_artifact(tmp_path: Path):
    with pytest.raises(F005FigureBlockedError) as exc:
        load_f005_inputs(
            tmp_path / "missing.npz",
            tmp_path / "cls.csv",
        )
    assert exc.value.code == BLOCKED_F005_ARTIFACT_MISSING
    assert EPOCH_BUILD_COMMAND in exc.value.details.get("build_command", "")


def test_figure_script_refuses_missing_classification(tmp_path: Path):
    paths = _write_fixture(tmp_path)
    with pytest.raises(F005FigureBlockedError) as exc:
        load_f005_inputs(paths["epochs"], tmp_path / "missing.csv")
    assert exc.value.code == BLOCKED_F005_CLASSIFICATION_MISSING
    assert "classify_units_s_s_o" in CLASSIFY_COMMAND


def test_figure_script_refuses_bad_anchor_provenance():
    with pytest.raises(F005FigureBlockedError) as exc:
        validate_f005_anchor_provenance(
            {"anchor_code": 100, "time_base": "fixation_relative", "anchor_type": "fixation_cue"}
        )
    assert exc.value.code in (
        "BLOCKED_ANCHOR_CODE100",
        "BLOCKED_ANCHOR_NOT_CODE101",
    )


def test_figure_script_refuses_all_unknown_area(tmp_path: Path):
    paths = _write_fixture(tmp_path, all_unknown_area=True)
    with pytest.raises(F005FigureBlockedError) as exc:
        load_f005_inputs(paths["epochs"], paths["classification"], allow_unknown_area=False)
    assert exc.value.code == BLOCKED_F005_AREA_METADATA_MISSING


def test_psth_grouping_preserves_condition_labels(tmp_path: Path):
    paths = _write_fixture(tmp_path)
    inputs = load_f005_inputs(paths["epochs"], paths["classification"], allow_unknown_area=True)
    curves = compute_class_condition_psths(inputs, "S+")
    for cond in AFAMILY_CONDITIONS:
        assert cond in curves


def test_class_count_table_matches_classification_csv(tmp_path: Path):
    paths = _write_fixture(tmp_path)
    cls = pd.read_csv(paths["classification"])
    inputs = load_f005_inputs(paths["epochs"], paths["classification"], allow_unknown_area=True)
    expected = cls["display_class"].value_counts().to_dict()
    assert inputs.classification["display_class"].value_counts().to_dict() == expected


def test_figure_manifest_includes_paths_and_counts(tmp_path: Path, monkeypatch):
    paths = _write_fixture(tmp_path)
    out_dir = tmp_path / "fig"
    monkeypatch.setattr(
        "src.analysis.visualization.f005._write_static_image",
        lambda fig, path, fmt: path.write_bytes(b"stub") or True,
    )
    manifest = run_f005_figure(
        paths["epochs"],
        paths["classification"],
        output_png=out_dir / "fig.png",
        output_svg=out_dir / "fig.svg",
        output_html=out_dir / "fig.html",
        manifest_path=out_dir / "fig_manifest.json",
        qa_csv_path=out_dir / "fig_qa.csv",
        allow_unknown_area=True,
    )
    assert manifest["input_artifact_path"]
    assert manifest["input_artifact_hash_sha256"]
    assert manifest["class_counts"]
    assert manifest["condition_trial_counts"]
    assert manifest["artifact_schema_version"] == "jnwb_epoch_artifact_v1"
    assert Path(manifest["output_html"]).exists()
    assert Path(out_dir / "fig_qa.csv").exists()


def test_no_extraction_imports_in_figure_layer():
    repo = Path(__file__).parent.parent
    sources = [
        repo / "figures" / "f005_unit_psth_categories.py",
        repo / "src" / "analysis" / "visualization" / "f005.py",
    ]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IN_FIGURE_LAYER:
            assert token not in text, f"{token} found in {path.name}"


def test_load_with_allow_unknown_area(tmp_path: Path):
    paths = _write_fixture(tmp_path, all_unknown_area=True)
    inputs = load_f005_inputs(paths["epochs"], paths["classification"], allow_unknown_area=True)
    assert len(inputs.sessions) == 1
    assert inputs.bin_ms == 1.0
