"""Probes for the ragged-index integrity check and its guarded repair (jnwb.nwb_integrity).

Files are minimal HDF5 tables written directly, so each index is known by construction.
"""

from __future__ import annotations

import os
import re
import stat
from pathlib import Path

import h5py
import numpy as np
import pytest

import jnwb
from jnwb import RaggedIndexRepairRefused, check_ragged_indices, repair_ragged_index

DOCS = Path(__file__).resolve().parents[1] / "docs"

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


def _index(path):
    with h5py.File(path, "r") as f:
        return f["units/spike_times_index"][()]


def test_symbols_are_public():
    for name in ("check_ragged_indices", "repair_ragged_index",
                 "RaggedIndexReport", "RaggedIndexRepair", "RaggedIndexRepairRefused"):
        assert name in jnwb.__all__ and hasattr(jnwb, name)


def test_correct_index_is_ok(tmp_path):
    p = tmp_path / "a.nwb"
    _write(p, CORRECT)
    rep = check_ragged_indices(p, probe_starts=STARTS)
    (c,) = rep.columns
    assert (c.monotonic, c.nonnegative, c.ends_at_data_len, c.length_fits, c.offset_bug) == (
        True, True, True, True, "absent")
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


def test_empty_row_keeps_the_index_monotonic(tmp_path):
    # A repeated end offset is an empty row: non-decreasing, not strictly increasing.
    p = tmp_path / "rep.nwb"
    _write(p, [3, 3, 9, 10, 15, 17])
    (c,) = check_ragged_indices(p).columns
    assert c.monotonic and c.ok
    (c,) = check_ragged_indices(p, probe_starts=STARTS).columns
    assert c.offset_bug == "absent" and c.ok


def test_negative_index_is_not_ok(tmp_path):
    # Non-decreasing and ending at the data length; only the lower bound is violated.
    p = tmp_path / "neg.nwb"
    _write(p, [-3, 5, 9, 10, 15, 17])
    (c,) = check_ragged_indices(p).columns
    assert c.monotonic and c.ends_at_data_len and c.nonnegative is False and not c.ok
    (c,) = check_ragged_indices(p, probe_starts=STARTS).columns
    assert c.offset_bug == "inconsistent" and not c.ok


def test_dtype_overflow_flag(tmp_path):
    p = tmp_path / "h.nwb"
    _write(p, [1, 2, 3, 4, 5, 100], dtype="int8", data_len=200)
    (c,) = check_ragged_indices(p).columns
    assert c.length_fits is False and c.index_type == "int8"


def test_length_fits_at_the_dtype_maximum(tmp_path):
    p = tmp_path / "max.nwb"
    with h5py.File(p, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.arange(1))
        g.create_dataset("spike_times", data=np.zeros(127))
        g.create_dataset("spike_times_index", data=np.array([127], dtype="int8"))
        g.attrs["colnames"] = np.array([b"spike_times"])
    (c,) = check_ragged_indices(p).columns
    assert c.length_fits and c.ok


def test_unlisted_ragged_column_is_reported(tmp_path):
    p = tmp_path / "i.nwb"
    _write(p, CORRECT, colnames=())
    rep = check_ragged_indices(p, probe_starts=STARTS)
    assert rep.unlisted_ragged_columns == ("spike_times",) and not rep.ok


def _write_empty_index(path, data_len):
    with h5py.File(path, "w") as f:
        g = f.create_group("units")
        g.create_dataset("id", data=np.zeros(0, dtype="i8"))
        g.create_dataset("spike_times", data=np.zeros(data_len))
        g.create_dataset("spike_times_index", data=np.zeros(0, dtype="i8"))
        g.attrs["colnames"] = np.array([b"spike_times"])


def test_empty_index_over_empty_data_is_ok(tmp_path):
    p = tmp_path / "j.nwb"
    _write_empty_index(p, 0)
    rep = check_ragged_indices(p, probe_starts=[0])
    (c,) = rep.columns
    assert c.n_rows == 0 and c.ends_at_data_len and c.nonnegative and c.ok and rep.ok


def test_empty_index_over_nonempty_data_is_not_ok(tmp_path):
    p = tmp_path / "j2.nwb"
    _write_empty_index(p, 4)
    (c,) = check_ragged_indices(p).columns
    assert c.ends_at_data_len is False and not c.ok


def test_check_never_writes(tmp_path):
    p = tmp_path / "k.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    check_ragged_indices(p, probe_starts=STARTS)
    assert p.read_bytes() == before


def test_check_reads_a_read_only_file(tmp_path):
    p = tmp_path / "ro.nwb"
    _write(p, CORRECT)
    before = p.read_bytes()
    os.chmod(p, stat.S_IREAD)
    try:
        assert check_ragged_indices(p, probe_starts=STARTS).ok
    finally:
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    assert p.read_bytes() == before


#: Each check error: the call's keyword arguments, the exception type, and a fragment of its
#: message that docs/errors.md quotes.
CHECK_ERRORS = [
    (dict(table="trials"), KeyError, "no table group"),
    (dict(probe_column="shank"), KeyError, "is not a column of the table"),
    (dict(probe_starts=[1, 3]), ValueError, "beginning at 0"),
    (dict(probe_starts=STARTS, probe_column="probe"), ValueError, "not both"),
]


@pytest.mark.parametrize("kwargs, exc, fragment", CHECK_ERRORS)
def test_check_errors_are_pinned(tmp_path, kwargs, exc, fragment):
    p = tmp_path / "l.nwb"
    _write(p, CORRECT, labels=[7, 7, 9, 9, 9, 4])
    with pytest.raises(exc, match=fragment):
        check_ragged_indices(p, **kwargs)


def test_probe_column_of_wrong_length_raises(tmp_path):
    p = tmp_path / "l2.nwb"
    _write(p, CORRECT)
    with h5py.File(p, "a") as f:
        f["units"].create_dataset("probe", data=np.array([1, 2]))
    with pytest.raises(ValueError, match="values for 6 rows"):
        check_ragged_indices(p, probe_column="probe")


# --- repair ----------------------------------------------------------------------------------


def test_repair_dry_run_writes_nothing(tmp_path):
    p = tmp_path / "m.nwb"
    bad = _buggy(LENGTHS, STARTS)
    _write(p, bad)
    before = p.read_bytes()
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS)
    assert r.written is False and r.output_path is None and p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["m.nwb"]
    np.testing.assert_array_equal(r.new_index, CORRECT)
    assert r.rows_changed == int(np.count_nonzero(bad != CORRECT))


def test_repair_writes_a_new_file_and_leaves_the_input(tmp_path):
    p = tmp_path / "n.nwb"
    _write(p, _buggy(LENGTHS, STARTS), dtype="int32")
    before = p.read_bytes()
    out = tmp_path / "n_repaired.nwb"
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            output_path=out)
    assert r.written and r.output_path == str(out) and p.read_bytes() == before
    with h5py.File(out, "r") as f:
        ds = f["units/spike_times_index"]
        assert ds.dtype == np.int32 and ds.shape == (6,)
        np.testing.assert_array_equal(ds[()], CORRECT)
        assert f["units/spike_times"].shape == (17,)
    assert check_ragged_indices(out, probe_starts=STARTS).ok
    assert sorted(os.listdir(tmp_path)) == ["n.nwb", "n_repaired.nwb"]


def test_repair_in_place_keeps_dtype_and_backs_up_the_old_index(tmp_path):
    p = tmp_path / "n2.nwb"
    _write(p, _buggy(LENGTHS, STARTS), dtype="int32")
    bk = tmp_path / "bk.npz"
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            in_place=True, backup_path=bk)
    assert r.written and r.output_path == str(p)
    assert _index(p).dtype == np.int32
    np.testing.assert_array_equal(_index(p), CORRECT)
    np.testing.assert_array_equal(np.load(bk)["old_index"], _buggy(LENGTHS, STARTS))
    assert sorted(os.listdir(tmp_path)) == ["bk.npz", "n2.nwb"]
    # A second repair now refuses: the index is no longer the defect.
    with pytest.raises(RaggedIndexRepairRefused, match="absent"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS)


def test_backup_is_written_at_the_path_given(tmp_path):
    # np.savez appends ".npz" to a bare name; the guard must test the path actually written.
    p = tmp_path / "bp.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    precious = tmp_path / "bk.npz"
    precious.write_bytes(b"PRECIOUS")
    repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False, in_place=True,
                        backup_path=tmp_path / "bk")
    assert precious.read_bytes() == b"PRECIOUS"
    np.testing.assert_array_equal(np.load(tmp_path / "bk")["old_index"], _buggy(LENGTHS, STARTS))


def _setitem_injection(monkeypatch, behaviour):
    """Replace h5py's dataset write; returns the list of calls it received."""
    calls = []
    original = h5py.Dataset.__setitem__

    def fake(self, key, value):
        calls.append(self.name)
        behaviour(original, self, key, value)

    monkeypatch.setattr(h5py.Dataset, "__setitem__", fake)
    return calls


def _partial_then_fail(original, ds, key, value):
    original(ds, slice(0, 3), np.asarray(value)[:3])
    raise OSError("injected mid-write failure")


def _silently_wrong(original, ds, key, value):
    original(ds, key, np.asarray(value) + 1)


def _valid_but_not_the_correction(original, ds, key, value):
    # Passes every structural check, so only the comparison with the correction can catch it.
    original(ds, key, np.array([1, 2, 3, 4, 5, 17], dtype=ds.dtype))


@pytest.mark.parametrize("mode", ["output", "in_place"])
def test_interrupted_write_leaves_the_input_byte_identical(tmp_path, monkeypatch, mode):
    p = tmp_path / "s.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    dest = (dict(output_path=tmp_path / "out.nwb") if mode == "output"
            else dict(in_place=True, backup_path=tmp_path / "bk.npz"))
    calls = _setitem_injection(monkeypatch, _partial_then_fail)
    with pytest.raises(OSError, match="injected"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False, **dest)
    assert calls == ["/units/spike_times_index"]
    assert p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["s.nwb"]


@pytest.mark.parametrize("behaviour", [_silently_wrong, _valid_but_not_the_correction])
@pytest.mark.parametrize("mode", ["output", "in_place"])
def test_a_wrong_write_is_refused_not_reported_written(tmp_path, monkeypatch, mode, behaviour):
    p = tmp_path / "w.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    dest = (dict(output_path=tmp_path / "out.nwb") if mode == "output"
            else dict(in_place=True, backup_path=tmp_path / "bk.npz"))
    calls = _setitem_injection(monkeypatch, behaviour)
    with pytest.raises(RaggedIndexRepairRefused, match="did not verify"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False, **dest)
    assert calls == ["/units/spike_times_index"]
    assert p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["w.nwb"]


def test_a_failed_replace_leaves_no_backup(tmp_path, monkeypatch):
    p = tmp_path / "x.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    calls = []

    def fail(src, dst):
        calls.append(dst)
        raise OSError("injected replace failure")

    monkeypatch.setattr("jnwb.nwb_integrity.os.replace", fail)
    with pytest.raises(OSError, match="injected replace"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            in_place=True, backup_path=tmp_path / "bk.npz")
    assert calls == [p]
    assert p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["x.nwb"]


def test_read_only_target_is_refused_before_any_backup(tmp_path):
    p = tmp_path / "ro.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    os.chmod(p, stat.S_IREAD)
    try:
        with pytest.raises(RaggedIndexRepairRefused, match="is not writable"):
            repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                                in_place=True, backup_path=tmp_path / "bk.npz")
        # The new-file mode needs only read access to the input.
        out = tmp_path / "ro_repaired.nwb"
        assert repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                                   output_path=out).written
    finally:
        os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    assert p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["ro.nwb", "ro_repaired.nwb"]


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
                            in_place=True, backup_path=tmp_path / "bk.npz")
    assert sorted(os.listdir(tmp_path)) == ["r.nwb"]


#: Each refusal: the call's keyword arguments (``tmp`` is replaced by the test directory), and
#: a fragment of the message that docs/errors.md quotes.
REFUSALS = [
    (dict(column="waveform_mean"), "has no ragged column"),
    (dict(probe_starts=None), "is not the known offset defect"),
    (dict(dry_run=False), "needs output_path or in_place=True"),
    (dict(dry_run=False, output_path="tmp/o.nwb", in_place=True),
     "output_path and in_place=True exclude each other"),
    (dict(dry_run=False, in_place=True), "in_place=True needs backup_path"),
    (dict(dry_run=False, output_path="tmp/o.nwb", backup_path="tmp/b.npz"),
     "backup_path applies only with in_place=True"),
    (dict(dry_run=False, output_path="tmp/exists"), "output_path .* exists"),
    (dict(dry_run=False, in_place=True, backup_path="tmp/exists"), "backup_path .* exists"),
]


@pytest.mark.parametrize("kwargs, fragment", REFUSALS)
def test_refusals_are_pinned_and_write_nothing(tmp_path, kwargs, fragment):
    p = tmp_path / "o.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    (tmp_path / "exists").write_bytes(b"x")
    before = p.read_bytes()
    call = dict(column="spike_times", probe_starts=STARTS)
    call.update({k: (tmp_path / v[4:] if isinstance(v, str) and v.startswith("tmp/") else v)
                 for k, v in kwargs.items()})
    with pytest.raises(RaggedIndexRepairRefused, match=fragment):
        repair_ragged_index(p, **call)
    assert p.read_bytes() == before and (tmp_path / "exists").read_bytes() == b"x"
    assert sorted(os.listdir(tmp_path)) == ["exists", "o.nwb"]


def test_every_pinned_message_is_on_the_errors_page():
    page = (DOCS / "errors.md").read_text(encoding="utf-8")
    fragments = [f for _, _, f in CHECK_ERRORS] + [f for _, f in REFUSALS] + [
        "values for", "does not fit", "did not verify", "is not writable"]
    text = page.replace("`", "")
    missing = [f for f in fragments if not re.search(f, text)]
    assert not missing, missing
