"""Caller-held execution records and a filesystem result cache.

Each test below fails before the change (``jnwb.execution`` is absent, so every
``jnwb.<name>`` below raises ``AttributeError``) and passes after.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest

import jnwb


def test_execution_record_is_a_frozen_dataclass():
    assert dataclasses.is_dataclass(jnwb.ExecutionRecord)
    assert jnwb.ExecutionRecord.__dataclass_params__.frozen is True
    rec = jnwb.ExecutionRecord(device="cpu", n_jobs=1)
    assert (rec.device, rec.n_jobs) == ("cpu", 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.device = "cuda"


def test_execution_record_device_and_worker_count_are_required():
    with pytest.raises(TypeError):
        jnwb.ExecutionRecord()
    with pytest.raises(TypeError):
        jnwb.ExecutionRecord(device="cpu")


def test_execution_record_refuses_a_worker_count_below_one():
    with pytest.raises(ValueError):
        jnwb.ExecutionRecord(device="cpu", n_jobs=0)


def test_execution_record_refuses_a_non_string_device():
    with pytest.raises(TypeError):
        jnwb.ExecutionRecord(device=0, n_jobs=1)


def test_execution_record_crosses_device_and_worker_counts():
    assert jnwb.ExecutionRecord(device="cpu", n_jobs=1).n_jobs == 1
    assert jnwb.ExecutionRecord(device="cpu", n_jobs=2).n_jobs == 2
    assert jnwb.ExecutionRecord(device="cuda", n_jobs=2).device == "cuda"


def test_cache_key_is_a_stable_64_char_hex_digest():
    key = jnwb.cache_key("band_power", np.arange(8), {"normalize": True})
    assert isinstance(key, str) and len(key) == 64
    assert all(c in "0123456789abcdef" for c in key)
    assert key == jnwb.cache_key("band_power", np.arange(8), {"normalize": True})


def test_cache_key_moves_with_name_inputs_and_params():
    base = jnwb.cache_key("op", np.arange(3), {"a": 1})
    assert jnwb.cache_key("other", np.arange(3), {"a": 1}) != base
    assert jnwb.cache_key("op", np.arange(3) + 1, {"a": 1}) != base
    assert jnwb.cache_key("op", np.arange(3), {"a": 2}) != base


def test_cache_key_ignores_mapping_order_but_not_version(monkeypatch):
    first = jnwb.cache_key("op", {"x": 1}, {"a": 1, "b": 2})
    assert jnwb.cache_key("op", {"x": 1}, {"b": 2, "a": 1}) == first
    monkeypatch.setattr(jnwb, "__version__", "0.0.0-test")
    assert jnwb.cache_key("op", {"x": 1}, {"a": 1, "b": 2}) != first


def test_cache_key_refuses_an_unhashable_param_type():
    with pytest.raises(TypeError, match="set"):
        jnwb.cache_key("op", np.arange(3), {"a": {1, 2}})


def test_store_then_load_returns_the_value(tmp_path):
    key = jnwb.cache_key("op", np.arange(4), {"a": 1})
    path = jnwb.cache_store(tmp_path, key, {"v": np.arange(3)})
    assert isinstance(path, Path) and path.is_file()
    assert path.parent == tmp_path
    loaded = jnwb.cache_load(tmp_path, key)
    assert loaded["v"] is not None and np.array_equal(loaded["v"], np.arange(3))


def test_store_then_load_roundtrips_scalars_lists_and_tuples(tmp_path):
    key = jnwb.cache_key("op", np.arange(4), {"a": 2})
    value = {"n": 3, "xs": [1.5, 2.5], "pair": (np.arange(2), "s")}
    jnwb.cache_store(tmp_path, key, value)
    loaded = jnwb.cache_load(tmp_path, key)
    assert loaded["n"] == 3 and loaded["xs"] == [1.5, 2.5]
    assert np.array_equal(loaded["pair"][0], np.arange(2)) and loaded["pair"][1] == "s"
    assert isinstance(loaded["pair"], tuple)


def test_load_of_a_missing_key_is_none(tmp_path):
    assert jnwb.cache_load(tmp_path, "ab" * 32) is None


def test_load_of_a_stale_version_is_none(tmp_path, monkeypatch):
    key = jnwb.cache_key("op", np.arange(4), {"a": 1})
    jnwb.cache_store(tmp_path, key, np.arange(3))
    monkeypatch.setattr(jnwb, "__version__", "0.0.0-test")
    assert jnwb.cache_load(tmp_path, key) is None


def test_load_of_a_rewritten_key_is_none(tmp_path):
    key = jnwb.cache_key("op", np.arange(4), {"a": 1})
    path = jnwb.cache_store(tmp_path, key, np.arange(3))
    with np.load(path, allow_pickle=False) as archive:
        other = {name: archive[name] for name in archive.files}
    other["__key__"] = np.asarray("0" * 64)
    tmp_name = path.parent / ("." + path.name + ".rewrite.tmp")
    with open(tmp_name, "wb") as handle:
        np.savez(handle, **other)
    tmp_name.replace(path)
    assert jnwb.cache_load(tmp_path, key) is None


def test_store_refuses_a_value_outside_the_supported_types(tmp_path):
    key = jnwb.cache_key("op", np.arange(3), {})
    with pytest.raises(TypeError):
        jnwb.cache_store(tmp_path, key, {1, 2, 3})


def test_store_refuses_a_key_that_escapes_the_directory(tmp_path):
    for bad in ("../away", "a/b", "", ".", ".."):
        with pytest.raises(ValueError):
            jnwb.cache_store(tmp_path, bad, 1)
        with pytest.raises(ValueError):
            jnwb.cache_load(tmp_path, bad)


def test_store_refuses_an_object_array(tmp_path):
    with pytest.raises(TypeError, match="object arrays"):
        jnwb.cache_store(tmp_path, "objects", np.array([1, "a"], dtype=object))
    assert not (tmp_path / "objects.npz").exists()


def test_cache_key_tells_apart_the_pairs_that_used_to_share_a_key():
    pairs = [
        ((1, 2), [1, 2]),
        ({1: 0}, {"1": 0}),
        (np.float64(1.0), 1.0),
        (np.str_("a"), "a"),
        ({"__bytes__": "616263"}, b"abc"),
    ]
    for first, second in pairs:
        assert jnwb.cache_key("op", first, {}) != jnwb.cache_key("op", second, {})


def test_store_refuses_a_value_that_would_not_load_back_equal(tmp_path):
    key = jnwb.cache_key("op", np.arange(3), {})
    lossy = [
        ({1: "a"}, TypeError),
        ([1, {2: 3}], TypeError),
        (np.float64(1.0), TypeError),
        (np.int64(3), TypeError),
        (2**63, ValueError),
        (-(2**63) - 1, ValueError),
        (b"ab\x00", ValueError),
        (b"a\x00b", ValueError),
        ("ab\x00", ValueError),
    ]
    for value, error in lossy:
        with pytest.raises(error):
            jnwb.cache_store(tmp_path, key, value)
    assert not (tmp_path / f"{key}.npz").exists()


def _same_type_and_value(loaded, stored) -> bool:
    if type(loaded) is not type(stored):
        return False
    if isinstance(stored, np.ndarray):
        return loaded.dtype == stored.dtype and loaded.shape == stored.shape and np.array_equal(loaded, stored)
    if isinstance(stored, dict):
        return loaded.keys() == stored.keys() and all(
            _same_type_and_value(loaded[name], stored[name]) for name in stored)
    if isinstance(stored, (list, tuple)):
        return len(loaded) == len(stored) and all(
            _same_type_and_value(a, b) for a, b in zip(loaded, stored))
    return loaded == stored


def test_every_accepted_value_loads_equal_in_type_and_value(tmp_path):
    key = jnwb.cache_key("op", np.arange(3), {})
    accepted = [
        3, -(2**63), 2**63 - 1, True, 1.5, 2 + 3j, "", "ab", "a\x00b", b"", b"abc",
        [1, "a"], (1, 2), {"k": (1, [2.0])}, np.asarray(1.5), np.asarray(b"ab"),
        np.arange(3, dtype=np.int16),
    ]
    for value in accepted:
        jnwb.cache_store(tmp_path, key, value)
        assert _same_type_and_value(jnwb.cache_load(tmp_path, key), value), value


def test_clear_removes_only_cache_entries_and_counts_them(tmp_path):
    keep = tmp_path / "notes.txt"
    keep.write_text("not a cache entry", encoding="utf-8")
    foreign = tmp_path / "user_data.npz"
    np.savez(foreign, x=np.arange(3))
    keys = [jnwb.cache_key("op", [i], {}) for i in range(3)]
    for n, key in enumerate(keys):
        jnwb.cache_store(tmp_path, key, n)
    assert jnwb.cache_clear(tmp_path) == 3
    assert keep.is_file()
    assert foreign.is_file()
    assert jnwb.cache_clear(tmp_path) == 0
    assert jnwb.cache_clear(tmp_path / "absent") == 0


def test_coherence_runs_the_same_numbers_across_device_and_workers():
    from jnwb import cross_area_coherence

    rng = np.random.default_rng(7)
    x = rng.standard_normal(4096)
    y = rng.standard_normal(4096)
    one = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical", device="cpu", n_jobs=1)
    two = cross_area_coherence(x, y, fs=1000.0, freq_bands="canonical", device="cpu", n_jobs=2)
    assert set(one) == set(two)
    for name in one:
        first, second = one[name], two[name]
        if isinstance(first, np.ndarray):
            assert np.array_equal(first, second, equal_nan=True)
        else:
            assert first == second
