"""Tests for jnwb artifact save/load and manifest fields."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import omission
from src.jnwb.artifacts import (
    ARTIFACT_SCHEMA_VERSION,
    _array_key,
    _find_epoch_keys,
    _signal_metadata_csv_name,
)
from src.jnwb.errors import (
    BLOCKED_ARTIFACT_FORMAT_UNSUPPORTED,
    BLOCKED_ARTIFACT_SESSION_MISSING,
    BLOCKED_BACKEND_CUPY_UNAVAILABLE,
    JnwbBlockedError,
)


REQUIRED_MANIFEST_FIELDS = [
    "artifact_schema_version",
    "repo_sha",
    "command",
    "creation_time_utc",
    "signal_class",
    "signal_metadata_kind",
    "conditions",
    "alignment_event",
    "time_base",
    "window_ms",
    "shape",
    "dtype",
    "backend",
    "session_ids",
]


def _synthetic_batch(
    signal: str = "SPK",
    session: str = "s1",
    shape: tuple[int, int, int] = (4, 3, 10),
) -> jnwb.EpochBatch:
    data = np.random.randn(*shape).astype(np.float32)
    if signal == "SPK":
        data = np.random.poisson(1, size=shape).astype(np.float32)
    time_ms = np.linspace(-100, 300, shape[2], endpoint=False, dtype=np.float32)
    conditions = ["AAAB", "AXAB", "AAXB", "AAAX"]
    cond_nums = [1, 3, 4, 5]
    trial_meta = pd.DataFrame(
        {
            "trial_global": list(range(shape[0])),
            "session_id": [session] * shape[0],
            "condition": [conditions[i % len(conditions)] for i in range(shape[0])],
            "condition_number": [cond_nums[i % len(cond_nums)] for i in range(shape[0])],
        }
    )
    id_col = "signal_id" if signal == "SPK" else "channel_id"
    signal_meta = pd.DataFrame(
        {
            "session_id": [session] * shape[1],
            id_col: list(range(shape[1])),
            "area": ["V1"] * shape[1],
            "signal_class": [signal] * shape[1],
        }
    )
    manifest: dict = {
        "spec": {
            "signal": signal,
            "window_ms": (-100, 400),
            "backend": "numpy",
        },
        "conditions": ["AAAB", "AXAB", "AAXB", "AAAX"],
        "sessions": [session],
        "session_id": session,
        "anchor": "p1",
        "p1_code": 101,
    }
    if signal == "SPK":
        manifest["bin_ms"] = 1.0
    else:
        manifest["sampling_rate_hz"] = 1000.0
    return jnwb.EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest=manifest,
    )


def test_save_load_round_trip(tmp_path: Path):
    out = tmp_path / "epochs.npz"
    manifest_path = tmp_path / "epochs_manifest.json"
    jnwb.save_epoch_artifact(
        _synthetic_batch(),
        out=out,
        manifest=manifest_path,
        command="pytest",
        input_nwb_paths=["/fake.nwb"],
    )
    loaded = jnwb.load_epoch_artifact(out)
    assert loaded.data.shape == (4, 3, 10)
    assert len(loaded.trial_metadata) == 4
    assert _array_key("SPK", "s1") in np.load(out).files


def test_manifest_required_fields(tmp_path: Path):
    manifest_path = tmp_path / "epochs_manifest.json"
    jnwb.save_epoch_artifact(
        _synthetic_batch(),
        out=tmp_path / "epochs.npz",
        manifest=manifest_path,
        command="pytest",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in REQUIRED_MANIFEST_FIELDS:
        assert field in manifest, f"Missing manifest field: {field}"
    assert manifest["artifact_schema_version"] == ARTIFACT_SCHEMA_VERSION


def test_lfp_roundtrip(tmp_path: Path):
    out = tmp_path / "lfp_epochs.npz"
    manifest_path = tmp_path / "lfp_epochs_manifest.json"
    jnwb.save_epoch_artifact(
        _synthetic_batch(signal="LFP", shape=(5, 4, 400)),
        out=out,
        manifest=manifest_path,
        command="pytest",
    )
    assert (tmp_path / _signal_metadata_csv_name("lfp_epochs", "LFP")).exists()
    loaded = jnwb.load_epoch_artifact(out)
    assert loaded.data.shape == (5, 4, 400)
    assert loaded.manifest["signal_class"] == "LFP"
    assert _array_key("LFP", "s1") in np.load(out).files


def test_muae_roundtrip(tmp_path: Path):
    out = tmp_path / "muae_epochs.npz"
    jnwb.save_epoch_artifact(
        _synthetic_batch(signal="MUAe", shape=(3, 2, 200)),
        out=out,
        command="pytest",
    )
    loaded = jnwb.load_epoch_artifact(out, signal="MUAe")
    assert loaded.data.shape == (3, 2, 200)
    assert _array_key("MUAe", "s1") in np.load(out).files
    assert (tmp_path / _signal_metadata_csv_name("muae_epochs", "MUAe")).exists()


def test_backward_compat_spk_epochs_key(tmp_path: Path):
    data = np.ones((2, 3, 5), dtype=np.float32)
    out = tmp_path / "legacy_spk.npz"
    np.savez_compressed(
        out,
        spk_epochs=data,
        time_axis_ms=np.arange(5, dtype=np.float32),
        anchor_code=np.array(101),
        time_base=np.array("p1_relative"),
        trial_metadata_json=np.array("[]"),
        signal_metadata_json=np.array("[]"),
        multi_session=np.array(False),
    )
    loaded = jnwb.load_epoch_artifact(out)
    assert loaded.data.shape == (2, 3, 5)


def test_backward_compat_epochs_key(tmp_path: Path):
    data = np.ones((2, 3, 5), dtype=np.float32)
    out = tmp_path / "legacy_epochs.npz"
    np.savez_compressed(
        out,
        epochs=data,
        time_axis_ms=np.arange(5, dtype=np.float32),
        anchor_code=np.array(101),
        time_base=np.array("p1_relative"),
        trial_metadata_json=np.array("[]"),
        signal_metadata_json=np.array("[]"),
        multi_session=np.array(False),
    )
    loaded = jnwb.load_epoch_artifact(out)
    assert loaded.data.shape == (2, 3, 5)


def test_backward_compat_spk_epochs_session_key(tmp_path: Path):
    out = tmp_path / "legacy_session.npz"
    jnwb.save_epoch_artifact(_synthetic_batch(session="sub_C31o_ses_230816"), out=out)
    loaded = jnwb.load_epoch_artifact(out, session="sub_C31o_ses_230816")
    assert loaded.data.shape[0] == 4


def test_sidecar_hashes_in_manifest(tmp_path: Path):
    manifest_path = tmp_path / "epochs_manifest.json"
    jnwb.save_epoch_artifact(
        _synthetic_batch(),
        out=tmp_path / "epochs.npz",
        manifest=manifest_path,
        command="pytest",
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["trial_metadata_csv_hash_sha256"]
    assert manifest["signal_metadata_csv_hash_sha256"]
    assert Path(manifest["trial_metadata_csv"]).exists()
    assert Path(manifest["signal_metadata_csv"]).exists()


def test_missing_session_raises_typed_blocker(tmp_path: Path):
    out = tmp_path / "epochs.npz"
    jnwb.save_epoch_artifact(_synthetic_batch(session="s1"), out=out)
    with pytest.raises(JnwbBlockedError) as exc:
        jnwb.load_epoch_artifact(out, session="missing_session")
    assert exc.value.code == BLOCKED_ARTIFACT_SESSION_MISSING


def test_multi_session_load_all_preserves_identity(tmp_path: Path):
    out = tmp_path / "multi.npz"
    batches = [
        _synthetic_batch(session="s1", shape=(2, 3, 10)),
        _synthetic_batch(session="s2", shape=(3, 3, 10)),
    ]
    jnwb.save_epoch_artifact(batches, out=out, command="pytest")
    loaded = jnwb.load_epoch_artifact(out, load_all_sessions=True)
    assert isinstance(loaded, list)
    assert len(loaded) == 2
    sessions = {b.manifest.get("session_id") for b in loaded}
    assert sessions == {"s1", "s2"}
    shapes = sorted(b.data.shape[0] for b in loaded)
    assert shapes == [2, 3]


def test_find_epoch_keys_helpers():
    files = ["spk_epochs__s1", "lfp_epochs__s2", "time_axis_ms"]
    assert _find_epoch_keys(files, signal="LFP") == ["lfp_epochs__s2"]
    assert _find_epoch_keys(files, signal="SPK", session="s1") == ["spk_epochs__s1"]
    legacy = ["epochs", "time_axis_ms"]
    assert _find_epoch_keys(legacy) == ["epochs"]


def test_unsupported_format_blocks():
    with pytest.raises(JnwbBlockedError) as exc:
        jnwb.save_epoch_artifact(_synthetic_batch(), out="x.npz", format="zarr")
    assert exc.value.code == BLOCKED_ARTIFACT_FORMAT_UNSUPPORTED


def test_cupy_backend_lazy():
    try:
        import cupy  # noqa: F401
        pytest.skip("CuPy installed; skip unavailable test")
    except ImportError:
        with pytest.raises(JnwbBlockedError) as exc:
            jnwb.to_backend([1], backend="cupy")
        assert exc.value.code == BLOCKED_BACKEND_CUPY_UNAVAILABLE
