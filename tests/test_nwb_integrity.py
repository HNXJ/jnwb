"""Probes for the ragged-index integrity check and its guarded repair (jnwb.nwb_integrity).

Files are minimal HDF5 tables written directly, so each index is known by construction.
"""

from __future__ import annotations

import h5py
import numpy as np
import pytest

import jnwb
from jnwb import RaggedIndexRepairRefused, check_ragged_indices, repair_ragged_index

# Probe 0: 2 units; probe 1: 3 units; probe 2: 1 unit. Row lengths per unit:
LENGTHS = np.array([3, 2, 4, 1, 5, 2])
STARTS = [0, 2, 5]
CORRECT = np.cumsum(LENGTHS)  # [3 5 9 10 15 17]


def _buggy(lengths, starts):
    """Per-probe cumulative sum, offset for probes after the first by the first element of the
    index (the first unit's end) instead of the running total."""
    out = np.empty(len(lengths), dtype=np.int64)
    bounds = list(starts) + [len(lengths)]
    for p in range(len(starts)):
        seg = slice(bounds[p], bounds[p + 1])
        out[seg] = np.cumsum(lengths[seg]) + (0 if p == 0 else lengths[0])
    return out


def _write(path, index, *, dtype="int64", data_len=None, colnames=("spike_times",),
           labels=None):
    n = len(LENGTHS)
    with h5py.File(path, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.arange(n))
        g.create_dataset("spike_times", data=np.arange(int(LENGTHS.sum()) if data_len is None
                                                       else data_len, dtype="f8"))
        g.create_dataset("spike_times_index", data=np.asarray(index).astype(dtype))
        g.attrs["colnames"] = np.array(list(colnames), dtype="S")
        if labels is not None:
            g.create_dataset("probe", data=np.asarray(labels))


def test_symbols_are_public():
    for name in ("check_ragged_indices", "repair_ragged_index",
                 "RaggedIndexReport", "RaggedIndexRepair", "RaggedIndexRepairRefused"):
        assert name in jnwb.__all__ and hasattr(jnwb, name)


def test_correct_index_is_ok(tmp_path):
    p = tmp_path / "a.nwb"
    _write(p, CORRECT)
    rep = check_ragged_indices(p, probe_starts=STARTS)
    (c,) = rep.columns
    assert (c.monotonic, c.ends_at_data_len, c.length_fits, c.offset_bug) == (
        True, True, True, "absent")
    assert rep.ok and c.ok and rep.n_rows == 6 and c.n_rows == 6 and c.data_len == 17


def test_defect_is_detected_and_corrected_matches(tmp_path):
    p = tmp_path / "b.nwb"
    bad = _buggy(LENGTHS, STARTS)
    assert not np.array_equal(bad, CORRECT)
    _write(p, bad)
    (c,) = check_ragged_indices(p, probe_starts=STARTS).columns
    assert c.offset_bug == "detected" and not c.ok
    np.testing.assert_array_equal(c.corrected_index, CORRECT)


def test_probe_column_equals_probe_starts(tmp_path):
    p = tmp_path / "c.nwb"
    _write(p, _buggy(LENGTHS, STARTS), labels=[7, 7, 9, 9, 9, 4])
    a = check_ragged_indices(p, probe_column="probe").columns[0]
    b = check_ragged_indices(p, probe_starts=STARTS).columns[0]
    assert a.offset_bug == b.offset_bug == "detected"
    np.testing.assert_array_equal(a.corrected_index, b.corrected_index)


def test_without_segmentation_defect_is_not_tested(tmp_path):
    p = tmp_path / "d.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    (c,) = check_ragged_indices(p).columns
    assert c.offset_bug == "not_tested" and c.corrected_index is None
    assert not c.ends_at_data_len  # still reported structurally


def test_single_probe_cannot_show_the_defect(tmp_path):
    p = tmp_path / "e.nwb"
    _write(p, CORRECT[:-1].tolist() + [CORRECT[-1] + 3])
    (c,) = check_ragged_indices(p, probe_starts=[0]).columns
    assert c.offset_bug == "inconsistent"


def test_unrelated_damage_is_inconsistent_not_detected(tmp_path):
    p = tmp_path / "f.nwb"
    _write(p, _buggy(LENGTHS, STARTS), data_len=int(LENGTHS.sum()) + 1)
    (c,) = check_ragged_indices(p, probe_starts=STARTS).columns
    assert c.offset_bug == "inconsistent" and not c.ends_at_data_len


def test_non_monotonic_flag(tmp_path):
    p = tmp_path / "g.nwb"
    _write(p, [3, 2, 9, 10, 15, 17])
    (c,) = check_ragged_indices(p).columns
    assert c.monotonic is False


def test_dtype_overflow_flag(tmp_path):
    p = tmp_path / "h.nwb"
    _write(p, [1, 2, 3, 4, 5, 100], dtype="int8", data_len=200)
    (c,) = check_ragged_indices(p).columns
    assert c.length_fits is False and c.index_type == "int8"


def test_unlisted_ragged_column_is_reported(tmp_path):
    p = tmp_path / "i.nwb"
    _write(p, CORRECT, colnames=())
    rep = check_ragged_indices(p, probe_starts=STARTS)
    assert rep.unlisted_ragged_columns == ("spike_times",) and not rep.ok


def test_empty_table_boundary(tmp_path):
    p = tmp_path / "j.nwb"
    with h5py.File(p, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.zeros(0, dtype="i8"))
        g.create_dataset("spike_times", data=np.zeros(0))
        g.create_dataset("spike_times_index", data=np.zeros(0, dtype="i8"))
        g.attrs["colnames"] = np.array([b"spike_times"])
    (c,) = check_ragged_indices(p, probe_starts=[0]).columns
    assert c.n_rows == 0 and c.ends_at_data_len is False


def test_check_never_writes(tmp_path):
    p = tmp_path / "k.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    check_ragged_indices(p, probe_starts=STARTS)
    assert p.read_bytes() == before


def test_bad_segmentation_raises(tmp_path):
    p = tmp_path / "l.nwb"
    _write(p, CORRECT)
    with pytest.raises(ValueError, match="beginning at 0"):
        check_ragged_indices(p, probe_starts=[1, 3])
    with pytest.raises(ValueError, match="not both"):
        check_ragged_indices(p, probe_starts=STARTS, probe_column="x")


def test_repair_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "m.nwb"
    bad = _buggy(LENGTHS, STARTS)
    _write(p, bad)
    before = p.read_bytes()
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS)
    assert r.written is False and p.read_bytes() == before
    np.testing.assert_array_equal(r.new_index, CORRECT)
    assert r.rows_changed == int(np.count_nonzero(bad != CORRECT))


def test_repair_writes_same_dtype_shape_and_backup(tmp_path):
    p = tmp_path / "n.nwb"
    _write(p, _buggy(LENGTHS, STARTS), dtype="int32")
    bk = tmp_path / "bk.npz"
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False, backup_path=bk)
    assert r.written
    with h5py.File(p, "r") as f:
        ds = f["units/spike_times_index"]
        assert ds.dtype == np.int32 and ds.shape == (6,)
        np.testing.assert_array_equal(ds[()], CORRECT)
        assert f["units/spike_times"].shape == (17,)
    np.testing.assert_array_equal(np.load(bk)["old_index"], _buggy(LENGTHS, STARTS))
    assert check_ragged_indices(p, probe_starts=STARTS).ok
    # A second repair now refuses: the index is no longer the defect.
    with pytest.raises(RaggedIndexRepairRefused, match="absent"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS)


def test_repair_refusals_leave_file_untouched(tmp_path):
    p = tmp_path / "o.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    with pytest.raises(RaggedIndexRepairRefused, match="backup_path"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False)
    with pytest.raises(RaggedIndexRepairRefused, match="not_tested"):
        repair_ragged_index(p, "spike_times", dry_run=False, backup_path=tmp_path / "x.npz")
    with pytest.raises(RaggedIndexRepairRefused, match="no ragged column"):
        repair_ragged_index(p, "waveform_mean", probe_starts=STARTS)
    existing = tmp_path / "exists.npz"
    existing.write_bytes(b"x")
    with pytest.raises(RaggedIndexRepairRefused, match="exists"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            backup_path=existing)
    assert p.read_bytes() == before and existing.read_bytes() == b"x"


def test_repair_refuses_inconsistent_index(tmp_path):
    p = tmp_path / "q.nwb"
    _write(p, _buggy(LENGTHS, STARTS), data_len=int(LENGTHS.sum()) + 1)
    with pytest.raises(RaggedIndexRepairRefused, match="inconsistent"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS)


def test_repair_refuses_when_corrected_does_not_fit_dtype(tmp_path):
    p = tmp_path / "r.nwb"
    lengths = np.array([5, 50, 60, 70])
    starts = [0, 1, 3]
    bad = _buggy(lengths, starts)  # [5, 55, 115, 75]: fits int8; the corrected end, 185, does not
    with h5py.File(p, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.arange(4))
        g.create_dataset("spike_times", data=np.zeros(int(lengths.sum())))
        g.create_dataset("spike_times_index", data=bad.astype("int8"))
        g.attrs["colnames"] = np.array([b"spike_times"])
    (c,) = check_ragged_indices(p, probe_starts=starts).columns
    assert c.offset_bug == "detected" and c.length_fits is False
    with pytest.raises(RaggedIndexRepairRefused, match="does not fit"):
        repair_ragged_index(p, "spike_times", probe_starts=starts, dry_run=False,
                            backup_path=tmp_path / "bk.npz")
    assert not (tmp_path / "bk.npz").exists()
