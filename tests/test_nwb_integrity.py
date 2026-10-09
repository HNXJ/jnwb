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
                 "RaggedIndexReport", "RaggedIndexRepair", "RaggedIndexRepairRefused",
                 "check_waveform_blocks", "WaveformBlockReport"):
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


def test_an_output_created_after_the_check_is_not_overwritten(tmp_path, monkeypatch):
    p = tmp_path / "r.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    out = tmp_path / "r_repaired.nwb"
    real_copy = jnwb.nwb_integrity.shutil.copyfile

    def copy_then_race(src, dst):
        real_copy(src, dst)
        out.write_bytes(b"someone else's file")

    monkeypatch.setattr("jnwb.nwb_integrity.shutil.copyfile", copy_then_race)
    with pytest.raises(RaggedIndexRepairRefused, match="output_path .* exists"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            output_path=out)
    assert out.read_bytes() == b"someone else's file" and p.read_bytes() == before
    assert sorted(os.listdir(tmp_path)) == ["r.nwb", "r_repaired.nwb"]


def test_a_failed_replace_to_a_new_file_leaves_no_output(tmp_path, monkeypatch):
    p = tmp_path / "s.nwb"
    _write(p, _buggy(LENGTHS, STARTS))

    def fail(src, dst):
        raise OSError("injected replace failure")

    monkeypatch.setattr("jnwb.nwb_integrity.os.replace", fail)
    with pytest.raises(OSError, match="injected replace"):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            output_path=tmp_path / "s_repaired.nwb")
    assert sorted(os.listdir(tmp_path)) == ["s.nwb"]


def test_an_interrupt_during_replace_leaves_no_output_and_the_input_intact(tmp_path, monkeypatch):
    p = tmp_path / "k.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()

    def interrupt(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr("jnwb.nwb_integrity.os.replace", interrupt)
    with pytest.raises(KeyboardInterrupt):
        repair_ragged_index(p, "spike_times", probe_starts=STARTS, dry_run=False,
                            output_path=tmp_path / "k_repaired.nwb")
    assert sorted(os.listdir(tmp_path)) == ["k.nwb"] and p.read_bytes() == before


def test_a_dry_run_in_place_needs_no_backup_path(tmp_path):
    p = tmp_path / "d.nwb"
    _write(p, _buggy(LENGTHS, STARTS))
    before = p.read_bytes()
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS, in_place=True)
    assert r.written is False and p.read_bytes() == before
    np.testing.assert_array_equal(r.new_index, CORRECT)
    (tmp_path / "bk.npz").write_bytes(b"x")
    r = repair_ragged_index(p, "spike_times", probe_starts=STARTS, in_place=True,
                            backup_path=tmp_path / "bk.npz")
    assert r.written is False and (tmp_path / "bk.npz").read_bytes() == b"x"
    assert sorted(os.listdir(tmp_path)) == ["bk.npz", "d.nwb"]


def test_the_repair_page_makes_no_claim_about_what_a_third_party_tool_reports():
    page = (DOCS / "repairing_nwb.md").read_text(encoding="utf-8")
    lines = [ln for ln in page.splitlines() if "nwbinspector" in ln.lower()]
    assert lines and not [ln for ln in lines if re.search(r"\bnone\b|\bnot\b|\bcannot\b", ln)]
    assert "the previous one cannot" not in page and "do not." not in page


_W27_AMPS = (25.0, 40.0, 55.0, 70.0)
_W27_ROWS = (2, 3, 4, 5)


def _w27_block(amp, nrows, nsamp=4):
    """One unit's true block: row 0 carries exactly `amp` peak-to-peak, the rest flat."""
    b = np.zeros((nrows, nsamp))
    if nrows:
        b[0, -1] = float(amp)
    return b


def _w27_write(path, order=(0, 1, 2, 3), amps=_W27_AMPS, rows=_W27_ROWS):
    """Valid NWB file whose stored block order is `order`: unit `i` stores the block of
    unit `order[i]` while its amplitude stays its own. `order=(1, 0, 2, 3)` swaps the
    first two units' blocks and leaves the index consistent with what is stored."""
    from datetime import datetime, timezone

    import pynwb

    nwb = pynwb.NWBFile(session_description="w", identifier="w27",
                        session_start_time=datetime.now(timezone.utc))
    nwb.add_unit_column(name="waveform_mean", description="mean waveform", index=True)
    nwb.add_unit_column(name="amplitude", description="spike amplitude")
    nwb.add_unit_column(name="peak_channel_id", description="peak channel")
    blocks = [_w27_block(a, r) for a, r in zip(amps, rows)]
    for i, b in enumerate(order):
        nwb.add_unit(spike_times=[0.1 * (i + 1)], waveform_mean=blocks[b],
                     amplitude=amps[i], peak_channel_id=i)
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def test_pynwb_index_read_returns_another_units_block_without_warning(tmp_path):
    """The defect #27 repairs nothing of: on a file whose blocks are stored out of unit
    order, pynwb's indexed read returns another unit's block and warns nothing. Unit 0's
    truth is 2 rows; it reads 3, the exact values of unit 1's block."""
    import warnings

    import pynwb

    path = _w27_write(tmp_path / "perm.nwb", order=(1, 0, 2, 3))
    with pynwb.NWBHDF5IO(str(path), "r") as io:
        units = io.read().units
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            got = [np.asarray(units["waveform_mean"][i]) for i in range(4)]
    assert caught == []
    assert got[0].shape == (3, 4)
    np.testing.assert_array_equal(got[0], _w27_block(40.0, 3))
    np.testing.assert_array_equal(got[1], _w27_block(25.0, 2))


class TestCheckWaveformBlocks:
    """#27: `check_waveform_blocks` detects index-sliced blocks that are not the unit's.

    Ownership is the stored amplitude matched on some row within tolerance, nothing
    more: the check never reassigns a block, and `peak_channel_id` is carried for the
    caller, never used as a criterion (on DANDI:000253 it indexes a larger electrode
    space than the block rows, measured 2..5281 against 384 rows).
    """

    def test_swapped_units_are_unowned_and_the_rest_owned(self, tmp_path):
        from jnwb import check_waveform_blocks

        rep = check_waveform_blocks(_w27_write(tmp_path / "perm.nwb", order=(1, 0, 2, 3)),
                                    rtol=1e-9)
        assert [u.status for u in rep.units] == ["unowned", "unowned", "owned", "owned"]
        assert (rep.n_owned, rep.n_unowned, rep.n_unknown) == (2, 2, 0)
        assert not rep.ok
        owned = rep.units[2]
        assert (owned.matched_row, owned.largest_row, owned.best_dev) == (0, 0, 0.0)
        assert owned.stored_amplitude == 55.0 and owned.n_rows == 4
        assert (owned.index, owned.unit_id, owned.peak_channel_id) == (2, 2, 2)

    def test_an_ordered_file_passes_exact(self, tmp_path):
        from jnwb import check_waveform_blocks

        rep = check_waveform_blocks(_w27_write(tmp_path / "ok.nwb"), rtol=0.0)
        assert rep.ok and [u.status for u in rep.units] == ["owned"] * 4
        assert all(u.matched_row == 0 and u.best_dev == 0.0 for u in rep.units)

    def test_a_nan_amplitude_and_an_empty_block_are_unknown_not_unowned(self, tmp_path):
        from jnwb import check_waveform_blocks

        path = _w27_write(tmp_path / "edge.nwb", order=(0, 1, 2),
                          amps=(25.0, float("nan"), 55.0), rows=(2, 3, 0))
        rep = check_waveform_blocks(path, rtol=1e-9)
        assert [u.status for u in rep.units] == ["owned", "unknown", "unknown"]
        assert (rep.n_owned, rep.n_unowned, rep.n_unknown) == (1, 0, 2)
        assert not rep.ok
        assert np.isnan(rep.units[1].stored_amplitude)
        assert rep.units[2].n_rows == 0
        for u in rep.units[1:]:
            assert u.matched_row is None and u.best_dev is None

    def test_missing_columns_and_table_raise(self, tmp_path):
        from jnwb import check_waveform_blocks

        path = _w27_write(tmp_path / "ok.nwb")
        with pytest.raises(KeyError, match="no_such_table"):
            check_waveform_blocks(path, table="no_such_table", rtol=1e-9)
        no_wave = tmp_path / "no_wave.nwb"
        import shutil

        shutil.copy(path, no_wave)
        with h5py.File(no_wave, "a") as handle:
            del handle["units/waveform_mean"]
            del handle["units/waveform_mean_index"]
        with pytest.raises(KeyError, match="waveform_mean"):
            check_waveform_blocks(no_wave, rtol=1e-9)
        no_amp = tmp_path / "no_amp.nwb"
        shutil.copy(path, no_amp)
        with h5py.File(no_amp, "a") as handle:
            del handle["units/amplitude"]
        with pytest.raises(KeyError, match="amplitude"):
            check_waveform_blocks(no_amp, rtol=1e-9)

    def test_an_integer_amplitude_column_reads_and_a_string_one_is_refused(self, tmp_path):
        from jnwb import check_waveform_blocks

        ints = _w27_write(tmp_path / "ints.nwb", amps=(25, 40, 55, 70))
        with h5py.File(ints, "r") as handle:
            assert handle["units/amplitude"].dtype.kind == "i"
        assert check_waveform_blocks(ints, rtol=0.0).ok
        import shutil

        strings = tmp_path / "strings.nwb"
        shutil.copy(ints, strings)
        with h5py.File(strings, "a") as handle:
            del handle["units/amplitude"]
            handle.create_dataset("units/amplitude",
                                  data=np.array(["a", "b", "c", "d"], dtype=object),
                                  dtype=h5py.string_dtype())
        with pytest.raises(ValueError, match="amplitude.*not numeric"):
            check_waveform_blocks(strings, rtol=1e-9)

    def test_a_bad_tolerance_is_refused(self, tmp_path):
        from jnwb import check_waveform_blocks

        path = _w27_write(tmp_path / "ok.nwb")
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError):
                check_waveform_blocks(path, rtol=bad)
        for bad in (None, True, "1e-9"):
            with pytest.raises(TypeError):
                check_waveform_blocks(path, rtol=bad)
        with pytest.raises(ValueError, match="rtol"):
            check_waveform_blocks(path, rtol=-1e-9)
        with pytest.raises(ValueError, match="atol"):
            check_waveform_blocks(path, rtol=1e-9, atol=-1.0)

    def test_a_broken_index_refuses_instead_of_attributing(self, tmp_path):
        from jnwb import check_waveform_blocks

        import shutil

        path = _w27_write(tmp_path / "ok.nwb")
        bad = tmp_path / "bad_index.nwb"
        shutil.copy(path, bad)
        with h5py.File(bad, "a") as handle:
            index = handle["units/waveform_mean_index"][()]
            handle["units/waveform_mean_index"][...] = index[::-1]
        with pytest.raises(ValueError, match="index"):
            check_waveform_blocks(bad, rtol=1e-9)

    def test_a_flat_waveform_mean_is_refused(self, tmp_path):
        from jnwb import check_waveform_blocks

        import shutil

        path = _w27_write(tmp_path / "ok.nwb")
        flat = tmp_path / "flat.nwb"
        shutil.copy(path, flat)
        with h5py.File(flat, "a") as handle:
            data = handle["units/waveform_mean"][()]
            del handle["units/waveform_mean"]
            handle.create_dataset("units/waveform_mean", data=data.ravel())
        with pytest.raises(ValueError, match="waveform_mean"):
            check_waveform_blocks(flat, rtol=1e-9)

    def test_report_carries_file_table_and_tolerances(self, tmp_path):
        from jnwb import check_waveform_blocks

        rep = check_waveform_blocks(_w27_write(tmp_path / "ok.nwb"), rtol=1e-9, atol=0.5)
        assert (rep.file, rep.table, rep.n_units) == ("ok.nwb", "units", 4)
        assert (rep.rtol, rep.atol) == (1e-9, 0.5)
    def test_a_column_with_no_value_per_unit_is_refused(self, tmp_path):
        from jnwb import check_waveform_blocks

        import shutil

        path = _w27_write(tmp_path / "ok.nwb")
        for col in ("id", "peak_channel_id", "amplitude"):
            short = tmp_path / f"short_{col}.nwb"
            shutil.copy(path, short)
            with h5py.File(short, "a") as handle:
                data = handle[f"units/{col}"][()]
                del handle[f"units/{col}"]
                handle.create_dataset(f"units/{col}", data=data[:-1])
            with pytest.raises(ValueError, match=col):
                check_waveform_blocks(short, rtol=1e-9)

    def test_atol_decides_a_sub_relative_mismatch(self, tmp_path):
        from jnwb import check_waveform_blocks

        import shutil

        path = _w27_write(tmp_path / "ok.nwb")
        bumped = tmp_path / "bumped.nwb"
        shutil.copy(path, bumped)
        with h5py.File(bumped, "a") as handle:
            amp = handle["units/amplitude"][()].astype(float)
            amp[0] += 1e-7
            handle["units/amplitude"][...] = amp
        assert check_waveform_blocks(bumped, rtol=0.0).units[0].status == "unowned"
        rep = check_waveform_blocks(bumped, rtol=0.0, atol=1e-6)
        assert rep.units[0].status == "owned"
        assert rep.units[0].matched_row == 0
        assert rep.ok

