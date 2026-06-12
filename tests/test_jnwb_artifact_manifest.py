"""Tests for jnwb artifact save/load and manifest fields."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb
from src.jnwb.errors import BLOCKED_BACKEND_CUPY_UNAVAILABLE, JnwbBlockedError


REQUIRED_MANIFEST_FIELDS = [
    "repo_sha",
    "command",
    "creation_time_utc",
    "signal_class",
    "conditions",
    "alignment_event",
    "time_base",
    "window_ms",
    "shape",
    "dtype",
    "backend",
    "session_ids",
]


def _synthetic_batch() -> jnwb.EpochBatch:
    data = np.random.poisson(1, size=(4, 3, 10)).astype(np.float32)
    time_ms = np.arange(10, dtype=np.float32)
    trial_meta = pd.DataFrame(
        {
            "trial_global": [0, 1, 2, 3],
            "session_id": ["s1", "s1", "s1", "s1"],
            "condition": ["AAAB", "AXAB", "AAXB", "AAAX"],
            "condition_number": [1, 3, 4, 5],
        }
    )
    signal_meta = pd.DataFrame(
        {"session_id": ["s1"], "signal_id": [0], "area": ["V1"], "signal_class": ["SPK"]}
    )
    return jnwb.EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest={
            "spec": {
                "signal": "SPK",
                "window_ms": (-100, 400),
                "backend": "numpy",
            },
            "conditions": ["AAAB", "AXAB", "AAXB", "AAAX"],
            "sessions": ["s1"],
            "session_id": "s1",
            "anchor": "p1",
            "p1_code": 101,
            "bin_ms": 1.0,
        },
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


def test_cupy_backend_lazy():
    try:
        import cupy  # noqa: F401
        pytest.skip("CuPy installed; skip unavailable test")
    except ImportError:
        with pytest.raises(JnwbBlockedError) as exc:
            jnwb.to_backend([1], backend="cupy")
        assert exc.value.code == BLOCKED_BACKEND_CUPY_UNAVAILABLE
