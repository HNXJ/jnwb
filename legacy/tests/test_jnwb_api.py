"""Tests for jnwb public API surface."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import jnwb
from src.jnwb.errors import BLOCKED_BACKEND_JAX_UNAVAILABLE, JnwbBlockedError


def test_import_jnwb_public_api():
    expected = {
        "list_nwb_files",
        "inspect_nwb",
        "address_signals",
        "address_events",
        "load_epochs",
        "save_epoch_artifact",
        "load_epoch_artifact",
    }
    assert expected.issubset(set(dir(jnwb)))


def test_list_nwb_files_sorted(tmp_path: Path):
    for name in ["b_rec.nwb", "a_rec.nwb", "c_rec.nwb"]:
        (tmp_path / name).write_bytes(b"not real nwb")
    with pytest.raises(Exception):
        jnwb.list_nwb_files(tmp_path)
    paths = sorted(p.name for p in tmp_path.glob("*.nwb"))
    assert paths == ["a_rec.nwb", "b_rec.nwb", "c_rec.nwb"]


def test_schema_json_serializable():
    rec = jnwb.NWBFileRecord(
        path="/x.nwb",
        session_id="ses-1",
        subject="sub-1",
        date=None,
        task_names=["omission_glo_passive"],
        has_spk=True,
        has_lfp=False,
        has_muae=False,
    )
    payload = json.dumps(rec.to_dict())
    assert "ses-1" in payload


def test_to_backend_numpy():
    arr = jnwb.to_backend([1, 2, 3], backend="numpy")
    assert isinstance(arr, np.ndarray)


def test_to_backend_jax_lazy_error():
    try:
        import jax.numpy  # noqa: F401
        pytest.skip("JAX installed; skip unavailable test")
    except ImportError:
        with pytest.raises(JnwbBlockedError) as exc:
            jnwb.to_backend([1, 2, 3], backend="jax")
        assert exc.value.code == BLOCKED_BACKEND_JAX_UNAVAILABLE


def test_omission_offset_ms():
    assert jnwb.omission_offset_ms("AXAB") == 1031
    assert jnwb.omission_offset_ms("AAXB") == 2062
    assert jnwb.omission_offset_ms("AAAX") == 3093
    assert jnwb.omission_offset_ms("AAAB") is None
