"""Probes for jnwb.nwb_write.verify_nwb (re-reading a written NWB file) and write_nwb.

Each test builds its NWB file with pynwb into tmp_path. The against-comparison
builds its MutationReport by hand, since no writer exists for that path yet.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ecephys import ElectricalSeries

import jnwb
from jnwb.nwb_io import MissingRequiredNWBFieldError
from jnwb.nwb_write import (
    AmbiguousMappingError,
    AppliedOperation,
    MutationCheck,
    MutationIssue,
    MutationReport,
    NWBMutationError,
    NWBVerificationError,
    REPAIRS,
    UndeclaredUnitError,
    UnidentifiableRepairError,
    _attr_scalar_equal,
    _is_null,
    _version,
    repair_nwb,
    transform_nwb,
    verify_nwb,
    write_nwb,
)
from jnwb.ontology import Lineage, Provenance


def _make_nwb(path, *, scale=1.0, starting_time=0.0):
    nwb = NWBFile(
        session_description="synthetic verify fixture", identifier="verify-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1",
                                     device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1",
                          filtering="none", group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=scale * np.arange(80, dtype="f8").reshape(20, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=starting_time))
    nwb.add_unit(spike_times=np.array([0.1, 0.4, 0.9]))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def _make_nwbfile():
    nwb = NWBFile(
        session_description="synthetic write fixture", identifier="write-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1",
                                     device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1",
                          filtering="none", group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=np.arange(80, dtype="f8").reshape(20, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=0.0))
    return nwb


def test_write_nwb_and_errors_are_exported():
    for name in ("write_nwb", "NWBMutationError", "NWBVerificationError",
                 "AmbiguousMappingError", "UnidentifiableRepairError",
                 "UndeclaredUnitError"):
        assert name in jnwb.__all__, name
        assert hasattr(jnwb, name), name
    for name in ("NWBVerificationError", "AmbiguousMappingError",
                 "UnidentifiableRepairError", "UndeclaredUnitError"):
        assert issubclass(getattr(jnwb, name), NWBMutationError), name
    assert jnwb.write_nwb is write_nwb
    assert jnwb.NWBMutationError is NWBMutationError
    from jnwb import nwb_write
    assert nwb_write.MissingRequiredNWBFieldError is MissingRequiredNWBFieldError


def test_write_round_trip_passes_verify(tmp_path):
    dst = tmp_path / "written.nwb"
    rep = write_nwb(_make_nwbfile(), dst=dst)
    assert rep.ok
    assert rep.category == "write or create"
    assert rep.src is None and rep.src_sha256 is None
    assert rep.dst == str(dst) and rep.dst_sha256 is not None
    assert rep.applied == () and rep.issues == () and rep.waived == ()
    assert all(isinstance(c, MutationCheck) for c in rep.checks)
    check = verify_nwb(dst)
    assert check.ok, [c for c in check.checks if not c.ok]


def test_write_schema_failure_raises_and_writes_nothing(tmp_path, monkeypatch):
    import pynwb

    dst = tmp_path / "never.nwb"
    monkeypatch.setattr(pynwb, "validate", lambda **kwargs: ["planted: no such field"])
    with pytest.raises(NWBMutationError, match="planted"):
        write_nwb(_make_nwbfile(), dst=dst)
    assert not dst.exists(), "a refused write must leave no file behind"


def test_write_empty_session_description_raises_and_writes_nothing(tmp_path):
    dst = tmp_path / "never.nwb"
    nwb = NWBFile(
        session_description="", identifier="write-empty-desc",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    with pytest.raises(MissingRequiredNWBFieldError) as caught:
        write_nwb(nwb, dst=dst)
    assert caught.value.field_name == "session_description"
    assert not dst.exists(), "a refused write must leave no file behind"


def test_write_existing_dst_refuses_without_overwrite(tmp_path):
    dst = tmp_path / "written.nwb"
    first = write_nwb(_make_nwbfile(), dst=dst, verify=False)
    assert first.ok and dst.is_file(), "the fixture write must land first"
    with pytest.raises(FileExistsError, match="overwrite"):
        write_nwb(_make_nwbfile(), dst=dst)
    second = write_nwb(_make_nwbfile(), dst=dst, overwrite=True)
    assert second.ok


def test_write_verify_failure_raises_and_leaves_dst(tmp_path, monkeypatch):
    import jnwb.nwb_write as module

    dst = tmp_path / "written.nwb"
    bad = MutationReport(
        category="write or create", src=None, dst=str(dst),
        src_sha256=None, dst_sha256=None, applied=(),
        checks=(MutationCheck("pynwb read", False, "planted failure"),),
        issues=(), waived=(),
        provenance=Provenance(software_version=jnwb.__version__, backend="numpy"),
        lineage=Lineage(source_type="NWBFile", source_id="planted",
                        operation="write or create"),
        ok=False)
    monkeypatch.setattr(module, "verify_nwb", lambda path: bad)
    with pytest.raises(NWBVerificationError, match="planted failure"):
        write_nwb(_make_nwbfile(), dst=dst)
    assert dst.is_file(), "a failed verification leaves dst in place for inspection"


def _hand_report(*, applied=(), src="src", dst="dst"):
    return MutationReport(
        category="copy or transform", src=src, dst=dst,
        src_sha256=None, dst_sha256=None, applied=tuple(applied),
        checks=(), issues=(), waived=(),
        provenance=Provenance(software_version=jnwb.__version__, backend="numpy"),
        lineage=Lineage(source_type="NWBFile", source_id="hand-built",
                        operation="copy or transform"),
        ok=True)


def _failing(report):
    return [c for c in report.checks if not c.ok]


def test_only_verify_nwb_is_exported():
    assert "verify_nwb" in jnwb.__all__ and hasattr(jnwb, "verify_nwb")
    for name in ("MutationReport", "AppliedOperation", "MutationCheck", "MutationIssue"):
        assert name not in jnwb.__all__, name


def test_round_trip_without_against_passes(tmp_path):
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    with h5py.File(p, "r") as f:
        assert f["acquisition/raw/data"].size == 80, "fixture must carry data"
        assert len(f["acquisition/raw/data"]) == 20, "fixture must have 20 rows"
    rep = verify_nwb(p)
    assert rep.ok, [c for c in rep.checks if not c.ok]
    assert all(isinstance(c, MutationCheck) for c in rep.checks)
    assert all(isinstance(i, MutationIssue) for i in rep.issues)
    assert rep.dst == str(p) and rep.src is None and rep.src_sha256 is None
    assert rep.dst_sha256 is not None and rep.applied == () and rep.issues == ()


def test_identical_copy_with_an_empty_report_passes(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert np.array_equal(f["file_create_date"][:], g["file_create_date"][:]), \
            "a byte copy must share its write stamp"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert rep.ok, _failing(rep)
    assert rep.src == str(src) and rep.dst == str(dst)
    assert rep.src_sha256 is not None and rep.dst_sha256 is not None


def test_against_without_a_report_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    assert src.is_file() and dst.is_file(), "both files must exist for the refusal"
    with pytest.raises(ValueError, match="report"):
        verify_nwb(dst, against=src)


def test_undeclared_difference_is_reported_unexplained(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src, scale=1.0)
    _make_nwb(dst, scale=2.0)
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert not np.array_equal(f["acquisition/raw/data"][:],
                                  g["acquisition/raw/data"][:]), \
            "the fixtures must differ in the compared dataset"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    failed = _failing(rep)
    assert [c for c in failed if "acquisition/raw/data" in c.name], [c.name for c in failed]
    assert all("unexplained" in c.detail for c in failed), [(c.name, c.detail) for c in failed]


def test_identical_content_written_at_two_times_passes(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as g:
        g["file_create_date"][0] = b"2020-01-01T00:00:00.000000+00:00"
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert not np.array_equal(f["file_create_date"][:], g["file_create_date"][:]), \
            "the write stamps must differ for the content-not-storage check"
        assert np.array_equal(f["acquisition/raw/data"][:], g["acquisition/raw/data"][:]), \
            "the content must otherwise match"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert rep.ok, _failing(rep)


def test_scalars_are_read_whole(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src, starting_time=0.0)
    _make_nwb(dst, starting_time=5.0)
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert f["acquisition/raw/starting_time"].shape == (), "starting_time must be scalar"
        assert float(f["acquisition/raw/starting_time"][()]) != \
            float(g["acquisition/raw/starting_time"][()]), \
            "the scalar fixtures must differ"
    rep = verify_nwb(dst, against=src, report=_hand_report(), n_check=1)
    assert not rep.ok
    failed = _failing(rep)
    assert [c for c in failed if "acquisition/raw/starting_time" in c.name], \
        [c.name for c in failed]


def test_declared_cast_paths_are_exempt_and_checked_as_casts(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src, scale=1.0)
    _make_nwb(dst, scale=1.0)
    with h5py.File(dst, "r+") as g:
        old = g["acquisition/raw/data"]
        attrs = {k: old.attrs[k] for k in old.attrs}
        del g["acquisition/raw/data"]
        with h5py.File(src, "r") as f:
            new = g.create_dataset("acquisition/raw/data",
                                   data=f["acquisition/raw/data"][:].astype("f4"))
        for k, v in attrs.items():
            new.attrs[k] = v
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert str(g["acquisition/raw/data"].dtype) == "float32", \
            "the destination must hold the cast dtype"
    applied = (AppliedOperation(name="cast", changed=("acquisition/raw/data",)),)
    rep = verify_nwb(dst, against=src, report=_hand_report(applied=applied))
    assert rep.ok, _failing(rep)
    assert any("acquisition/raw/data" in c.name and "cast" in c.name
               for c in rep.checks), [c.name for c in rep.checks]


def _add_ref_dataset(path, *, target="acquisition/raw/data"):
    """A one-element object-reference dataset pointing at ``target`` in its own file."""
    with h5py.File(path, "r+") as handle:
        holder = handle.require_group("ref_holder")
        ds = holder.create_dataset("refs", shape=(1,), dtype=h5py.ref_dtype)
        ds[0] = handle[target].ref


def test_reference_targets_compared_by_value_not_identity(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as handle:
        handle["acquisition/raw/data"][:] = handle["acquisition/raw/data"][:] * 2.0
    _add_ref_dataset(src)
    _add_ref_dataset(dst)
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert f["acquisition/raw/data"].shape == g["acquisition/raw/data"].shape, \
            "the targets must share a shape"
        assert f["acquisition/raw/data"].dtype == g["acquisition/raw/data"].dtype, \
            "the targets must share a dtype"
        assert f["ref_holder/refs"].dtype == g["ref_holder/refs"].dtype, \
            "the reference datasets must share a dtype"
        assert not np.array_equal(f["acquisition/raw/data"][:],
                                  g["acquisition/raw/data"][:]), \
            "the target values must differ"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    failed = _failing(rep)
    refs_failed = [c for c in failed if "ref_holder/refs" in c.name]
    assert refs_failed, [c.name for c in failed]
    assert all("unexplained" in c.detail for c in refs_failed), \
        [(c.name, c.detail) for c in refs_failed]


def test_attribute_only_difference_is_reported_unexplained(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as handle:
        handle["acquisition/raw/data"].attrs["conversion"] = 2.0
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert np.array_equal(f["acquisition/raw/data"][:],
                              g["acquisition/raw/data"][:]), \
            "the values must match so only the attribute differs"
        assert f["acquisition/raw/data"].attrs["conversion"] != \
            g["acquisition/raw/data"].attrs["conversion"], \
            "the conversion attribute must differ"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    failed = _failing(rep)
    data_failed = [c for c in failed if "acquisition/raw/data" in c.name]
    assert data_failed, [c.name for c in failed]
    assert all("unexplained" in c.detail for c in data_failed), \
        [(c.name, c.detail) for c in data_failed]


def test_non_object_id_attribute_difference_is_reported_unexplained(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    _make_nwb(dst)
    with h5py.File(dst, "r+") as handle:
        current = str(handle["acquisition/raw/data"].attrs["unit"])
        handle["acquisition/raw/data"].attrs["unit"] = (
            "millivolts" if current != "millivolts" else "volts")
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert np.array_equal(f["acquisition/raw/data"][:],
                              g["acquisition/raw/data"][:]), \
            "the values must match so only the attribute differs"
        assert str(f["acquisition/raw/data"].attrs["unit"]) != \
            str(g["acquisition/raw/data"].attrs["unit"]), \
            "the unit attribute must differ"
        assert not np.array_equal(f["file_create_date"][:], g["file_create_date"][:]), \
            "independent writes must carry different write stamps"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    failed = _failing(rep)
    data_failed = [c for c in failed if "acquisition/raw/data" in c.name]
    assert data_failed, [c.name for c in failed]
    assert all("unexplained" in c.detail for c in data_failed), \
        [(c.name, c.detail) for c in data_failed]
    assert failed == data_failed, [(c.name, c.detail) for c in failed]


@pytest.mark.parametrize("key", ["description", "comments"])
def test_group_attribute_difference_is_reported_with_its_path(tmp_path, key):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as handle:
        assert key in handle["acquisition/raw"].attrs, \
            "the series group must carry the attribute"
        handle["acquisition/raw"].attrs[key] = "tampered"
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        assert _attr_str(f["acquisition/raw"].attrs[key]) != "tampered", \
            "the group attribute must differ"
        assert np.array_equal(f["acquisition/raw/data"][:], g["acquisition/raw/data"][:]), \
            "the datasets must match so only the group attribute differs"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    failed = _failing(rep)
    group_failed = [c for c in failed
                    if c.name == "/acquisition/raw attributes match the source as declared"]
    assert group_failed, [c.name for c in failed]
    assert failed == group_failed, [(c.name, c.detail) for c in failed]
    assert key in group_failed[0].detail and "unexplained" in group_failed[0].detail, \
        group_failed[0].detail


def test_root_attribute_difference_is_reported_at_the_root(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as handle:
        assert "comments" not in handle.attrs, "the root must not carry the attribute yet"
        handle.attrs["comments"] = "tampered"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert not rep.ok
    root_failed = [c for c in _failing(rep)
                   if c.name == "/ attributes match the source as declared"]
    assert root_failed, [c.name for c in _failing(rep)]
    assert "comments" in root_failed[0].detail, root_failed[0].detail


def test_declared_group_attribute_change_passes(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    shutil.copy(src, dst)
    with h5py.File(dst, "r+") as handle:
        handle["acquisition/raw"].attrs["description"] = "re-described"
    with h5py.File(src, "r") as f:
        assert _attr_str(f["acquisition/raw"].attrs["description"]) != "re-described", \
            "the group attribute must differ"
    applied = (AppliedOperation(name="squeeze_scalar_attributes",
                                changed=("acquisition/raw",)),)
    rep = verify_nwb(dst, against=src, report=_hand_report(applied=applied))
    assert rep.ok, _failing(rep)
    assert any(c.name == "/acquisition/raw declared by the report" for c in rep.checks), \
        [c.name for c in rep.checks]


def test_n_check_below_one_refuses(tmp_path):
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    assert p.is_file(), "the fixture file must exist for the refusal"
    with pytest.raises(ValueError, match="n_check"):
        verify_nwb(p, n_check=0)


def test_missing_file_refuses(tmp_path):
    missing = tmp_path / "absent.nwb"
    assert not missing.exists(), "the path must not exist for the refusal"
    with pytest.raises(FileNotFoundError):
        verify_nwb(missing)
    present = tmp_path / "ok.nwb"
    _make_nwb(present)
    assert present.is_file(), "the destination must exist for the against refusal"
    with pytest.raises(FileNotFoundError):
        verify_nwb(present, against=missing, report=_hand_report())


def test_identical_nan_content_passes(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    _make_nwb(dst)
    with h5py.File(src, "r+") as handle:
        handle["acquisition/raw/data"][0, 0] = np.nan
        handle["acquisition/raw/data"][1, 1] = np.nan
    with h5py.File(dst, "r+") as handle:
        handle["acquisition/raw/data"][0, 0] = np.nan
        handle["acquisition/raw/data"][1, 1] = np.nan
    with h5py.File(src, "r") as f, h5py.File(dst, "r") as g:
        first = f["acquisition/raw/data"][:]
        second = g["acquisition/raw/data"][:]
        assert bool(np.isnan(first).any()), "the stored array must contain NaN"
        assert bool(np.isnan(second).any()), "both files must contain NaN"
        both = ~(np.isnan(first) | np.isnan(second))
        assert bool(both.any()), "the fixture must hold non-NaN values"
        assert np.array_equal(first[both], second[both]), \
            "the non-NaN values must match"
    rep = verify_nwb(dst, against=src, report=_hand_report())
    assert rep.ok, _failing(rep)


def test_missing_distribution_warns_and_records_none():
    with pytest.warns(UserWarning, match="not installed"):
        assert _version("jnwb-no-such-distribution") is None


def test_unreadable_reference_warns_and_counts_as_non_null():
    class _Unreadable:
        def __bool__(self):
            raise RuntimeError("planted")

    with pytest.warns(UserWarning, match="unreadable reference"):
        assert _is_null(_Unreadable()) is False


def test_unreadable_reference_target_warns_and_counts_as_different(tmp_path, monkeypatch):
    import jnwb.nwb_write as module

    path = tmp_path / "ref.h5"
    with h5py.File(path, "w") as handle:
        data = handle.create_dataset("data", data=np.arange(4))
        ref = data.ref
    assert isinstance(ref, h5py.h5r.Reference), "the fixture must hold a real reference"

    def _planted(*args, **kwargs):
        raise RuntimeError("planted")

    monkeypatch.setattr(module, "_targets_equal", _planted)
    with pytest.warns(UserWarning, match="unreadable"):
        assert module._attr_scalar_equal(None, ref, None, ref, 200000) is False


class _NoEq:
    def __init__(self, tag):
        self.tag = tag

    def __eq__(self, other):
        raise RuntimeError("planted")

    def __repr__(self):
        return f"_NoEq({self.tag})"


def test_failing_equality_warns_and_falls_back_to_repr():
    with pytest.warns(UserWarning, match="comparing reprs"):
        assert _attr_scalar_equal(None, _NoEq("a"), None, _NoEq("a"), 200000) is True
    with pytest.warns(UserWarning, match="comparing reprs"):
        assert _attr_scalar_equal(None, _NoEq("a"), None, _NoEq("b"), 200000) is False


def _colnames(units):
    """The stored ``colnames`` decoded, whatever string dtype the file uses."""
    return [c.decode("utf-8") if isinstance(c, bytes) else str(c)
            for c in units.attrs["colnames"]]


def _attr_str(value):
    """An HDF5 string attribute as text, whether stored fixed or variable length."""
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _make_nwb_with_waveform(path):
    nwb = NWBFile(
        session_description="waveform repair fixture", identifier="waveform-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1",
                                     device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1",
                          filtering="none", group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=np.arange(80, dtype="f8").reshape(20, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=0.0))
    nwb.add_unit(spike_times=np.array([0.1, 0.4, 0.9]),
                 waveform_mean=[[0.0] * 4, [1.0] * 4])
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def test_transform_and_repair_are_exported():
    for name in ("transform_nwb", "repair_nwb"):
        assert name in jnwb.__all__, name
        assert hasattr(jnwb, name), name
    assert jnwb.transform_nwb is transform_nwb
    assert jnwb.repair_nwb is repair_nwb
    assert jnwb.REPAIRS == REPAIRS == ("squeeze_scalar_attributes", "units_colnames",
                                       "vector_index_types", "waveform_index_dtype")
    assert "REPAIRS" not in jnwb.__all__, "the repair vocabulary is reachable, not routed"


def test_transform_drop_and_cast_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert "units" in f, "the fixture must hold a units table to drop"
        assert str(f["acquisition/raw/data"].dtype) == "float64"
        before = f["acquisition/raw/data"][:]
    rep = transform_nwb(src, dst=dst, drop=["units"],
                        cast={"acquisition/raw/data": "float32"})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    assert rep.category == "copy or transform"
    assert any(a.name == "drop" for a in rep.applied)
    assert any(a.name == "cast" for a in rep.applied)
    with h5py.File(dst, "r") as f:
        assert "units" not in f, "the dropped table must be gone"
        assert str(f["acquisition/raw/data"].dtype) == "float32"
        assert np.array_equal(f["acquisition/raw/data"][:], before.astype("float32"))
    with h5py.File(src, "r") as f:
        assert "units" in f, "the source is never modified"
        assert str(f["acquisition/raw/data"].dtype) == "float64"


def test_transform_keep_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "keep.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        roots = sorted(f.keys())
    assert "acquisition" in roots and "units" in roots
    rep = transform_nwb(src, dst=dst, keep=[r for r in roots if r != "units"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    assert any(a.name == "keep" for a in rep.applied)
    with h5py.File(dst, "r") as f:
        assert "units" not in f, "the unkept table must be gone"
        assert "acquisition/raw/data" in f, "the kept series must stay"
        assert "session_description" in f, "the kept root datasets must stay"


def test_transform_compression_is_stored(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "zip.nwb"
    _make_nwb(src)
    rep = transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "float32"},
                        compression={"filter": "gzip", "level": 1, "shuffle": True})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert f["acquisition/raw/data"].compression == "gzip", \
            "the rewritten dataset must carry the declared storage"


def test_transform_compression_alone_keeps_scalar_datasets_whole(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "zip.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert f["acquisition/raw/starting_time"].shape == (), \
            "the rate-based series must hold a scalar starting_time"
        assert f["acquisition/raw/starting_time"].dtype.kind == "f"
        start = float(f["acquisition/raw/starting_time"][()])
    rep = transform_nwb(src, dst=dst,
                        compression={"filter": "gzip", "level": 1, "shuffle": True})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert f["acquisition/raw/data"].compression == "gzip", \
            "the float series must carry the declared storage"
        scalar = f["acquisition/raw/starting_time"]
        assert scalar.shape == (), "the scalar must keep its shape"
        assert scalar.chunks is None and scalar.compression is None, \
            "the scalar must keep its layout: no chunks or filters"
        assert float(scalar[()]) == start


def test_transform_keep_and_drop_together_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(ValueError, match="exclude each other"):
        transform_nwb(src, dst=dst, keep=["units"], drop=["units"])
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_unknown_path_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(KeyError, match="opens nothing"):
        transform_nwb(src, dst=dst, keep=["no/such/path"])
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_group_in_cast_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert isinstance(f["units"], h5py.Group), "the cast path must be a group"
    with pytest.raises(TypeError, match="which is a group"):
        transform_nwb(src, dst=dst, cast={"units": "float32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_dangling_drop_refuses_and_names_the_referrer(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as handle:
        holder = handle.require_group("ref_holder")
        refs = holder.create_dataset("refs", shape=(1,), dtype=h5py.ref_dtype)
        refs[0] = handle["acquisition/raw/data"].ref
    with h5py.File(src, "r") as f:
        assert f["ref_holder/refs"].shape == (1,), "the fixture must hold the reference"
    with pytest.raises(NWBMutationError, match="ref_holder/refs"):
        transform_nwb(src, dst=dst, drop=["acquisition/raw/data"])
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_cast_of_an_integer_dataset_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert f["units/id"].dtype.kind == "i", "the fixture column must be integral"
    with pytest.raises(TypeError, match="never integer"):
        transform_nwb(src, dst=dst, cast={"units/id": "float32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_cast_to_a_non_floating_dtype_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert f["acquisition/raw/data"].dtype.kind == "f"
    with pytest.raises(TypeError, match="stay floating"):
        transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "int32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_cast_on_a_dropped_path_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert "units/spike_times" in f
    with pytest.raises(ValueError, match="which the copy drops"):
        transform_nwb(src, dst=dst, drop=["units"],
                      cast={"units/spike_times": "float32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_dst_resolving_to_src_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    _make_nwb(src)
    assert src.is_file(), "the source must exist for the refusal"
    with pytest.raises(ValueError, match="resolves to src"):
        transform_nwb(src, dst=src, drop=["units"])


def test_transform_unknown_compression_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(ValueError, match="unknown compression filter"):
        transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "float32"},
                      compression={"filter": "bzip2"})
    with pytest.raises(ValueError, match="unknown compression key"):
        transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "float32"},
                      compression={"filter": "gzip", "strategy": 1})
    with pytest.raises(ValueError, match="compression level"):
        transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "float32"},
                      compression={"filter": "gzip", "level": 99})
    with pytest.raises(TypeError, match="must be a mapping"):
        transform_nwb(src, dst=dst, cast={"acquisition/raw/data": "float32"},
                      compression="gzip")
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_existing_dst_refuses_without_overwrite(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "dst.nwb"
    _make_nwb(src)
    first = transform_nwb(src, dst=dst, drop=["units"])
    assert first.ok and dst.is_file(), "the fixture copy must land first"
    with pytest.raises(FileExistsError, match="overwrite"):
        transform_nwb(src, dst=dst, drop=["units"])
    second = transform_nwb(src, dst=dst, drop=["units"], overwrite=True)
    assert second.ok


def test_repair_units_colnames_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["units"].attrs["colnames"] = np.array(
            ["spike_times_index"] + _colnames(f["units"]), dtype=object)
    with h5py.File(src, "r") as f:
        assert "spike_times_index" in _colnames(f["units"]), \
            "the index column must pollute colnames before the repair"
    rep = repair_nwb(src, dst=dst, repairs=["units_colnames"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    assert rep.category == "structural repair"
    assert any(a.name == "units_colnames" for a in rep.applied)
    with h5py.File(dst, "r") as f:
        fixed = _colnames(f["units"])
        assert "spike_times" in fixed, "the data column must be named again"
        assert not [c for c in fixed if c.endswith("_index")], \
            "no index column may stay in colnames"


def test_repair_squeeze_scalar_attributes_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["acquisition/raw"].attrs["description"] = np.array(["raw series"], dtype=object)
    with h5py.File(src, "r") as f:
        assert np.asarray(f["acquisition/raw"].attrs["description"]).shape == (1,), \
            "the attribute must be a length-1 array before the repair"
    rep = repair_nwb(src, dst=dst, repairs=["squeeze_scalar_attributes"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert _attr_str(f["acquisition/raw"].attrs["description"]) == "raw series"


def test_repair_vector_index_types_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        assert "waveform_mean" in f["units"], "the fixture must hold the target column"
        f["units"].create_dataset("waveform_mean_index", data=np.array([2], dtype="u1"))
        f["units/waveform_mean_index"].attrs["description"] = \
            "Index for VectorData 'waveform_mean'"
    with h5py.File(src, "r") as f:
        assert "neurodata_type" not in f["units/waveform_mean_index"].attrs, \
            "the index must be untyped before the repair"
    rep = repair_nwb(src, dst=dst, repairs=["vector_index_types"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        index = f["units/waveform_mean_index"]
        assert _attr_str(index.attrs["neurodata_type"]) == "VectorIndex"
        assert f[index.attrs["target"]].name == f["units/waveform_mean"].name


def test_repair_waveform_index_dtype_round_trip(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        assert "waveform_mean" in f["units"], "the fixture must hold the target column"
        assert "waveform_mean_index" not in f["units"]
        f["units"].create_dataset("waveform_mean_index", data=np.array([2], dtype="f8"))
    with h5py.File(src, "r") as f:
        assert f["units/waveform_mean_index"].dtype.kind == "f", \
            "the crafted index must be floating before the repair"
    rep = repair_nwb(src, dst=dst, repairs=["waveform_index_dtype"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    assert any(a.name == "waveform_index_dtype" for a in rep.applied)
    assert any(a.name == "cast" for a in rep.applied)
    with h5py.File(dst, "r") as f:
        index = f["units/waveform_mean_index"]
        assert index.dtype == np.dtype("uint8")
        assert np.array_equal(np.asarray(index[...]).ravel(), [2])
        assert _attr_str(index.attrs["neurodata_type"]) == "VectorIndex"
        assert _attr_str(index.attrs["description"]) == "Index for VectorData 'waveform_mean'"
        assert f[index.attrs["target"]].name == f["units/waveform_mean"].name


def test_a_typed_uint8_waveform_index_is_not_planned(tmp_path):
    """A uint8 index that already carries its type, target and description needs no repair."""
    src = tmp_path / "src.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        index = f["units"].create_dataset("waveform_mean_index", data=np.array([2], dtype="u1"))
        index.attrs["description"] = "Index for VectorData 'waveform_mean'"
        index.attrs["neurodata_type"] = "VectorIndex"
        index.attrs["target"] = f["units/waveform_mean"].ref
    with pytest.raises(jnwb.UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=tmp_path / "fixed.nwb", repairs=["waveform_index_dtype"])


def test_an_untyped_uint8_waveform_index_still_gets_its_attributes(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        f["units"].create_dataset("waveform_mean_index", data=np.array([2], dtype="u1"))
    with h5py.File(src, "r") as f:
        assert f["units/waveform_mean_index"].dtype == np.dtype("uint8"), "fixture is uint8"
        assert "neurodata_type" not in f["units/waveform_mean_index"].attrs, "fixture is untyped"
    rep = repair_nwb(src, dst=dst, repairs=["waveform_index_dtype"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        index = f["units/waveform_mean_index"]
        assert _attr_str(index.attrs["neurodata_type"]) == "VectorIndex"
        assert _attr_str(index.attrs["description"]) == "Index for VectorData 'waveform_mean'"
        assert f[index.attrs["target"]].name == f["units/waveform_mean"].name


def test_repair_contradiction_is_reported_never_rewritten(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["units"].attrs["colnames"] = np.array(
            ["spike_times_index"] + _colnames(f["units"]), dtype=object)
        f["acquisition/raw/data"].attrs["unit"] = "millivolts"
    with h5py.File(src, "r") as f:
        assert "spike_times_index" in _colnames(f["units"])
        assert _attr_str(f["acquisition/raw/data"].attrs["unit"]) == "millivolts"
    rep = repair_nwb(src, dst=dst, repairs=["units_colnames"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    flagged = [i for i in rep.issues
               if i.severity == "warning" and i.location == "/acquisition/raw"]
    assert flagged, rep.issues
    assert any("unit" in i.message for i in flagged), [i.message for i in flagged]
    with h5py.File(dst, "r") as f:
        assert _attr_str(f["acquisition/raw/data"].attrs["unit"]) == "millivolts", \
            "the contradiction is reported, never rewritten"
        assert "spike_times" in _colnames(f["units"])


def test_repair_unknown_name_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(ValueError, match="unknown repair"):
        repair_nwb(src, dst=dst, repairs=["no_such_repair"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_argument_shape_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(TypeError, match="repairs= is required"):
        repair_nwb(src, dst=dst, repairs=None)
    with pytest.raises(TypeError, match="not one string"):
        repair_nwb(src, dst=dst, repairs="units_colnames")
    with pytest.raises(ValueError, match="names no repair"):
        repair_nwb(src, dst=dst, repairs=[])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_missing_session_description_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        del f["session_description"]
    with h5py.File(src, "r") as f:
        assert "session_description" not in f, "the required field must be absent"
    with pytest.raises(MissingRequiredNWBFieldError):
        repair_nwb(src, dst=dst, repairs=["units_colnames"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_squeeze_with_nothing_to_change_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=dst, repairs=["squeeze_scalar_attributes"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_colnames_with_nothing_to_change_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert _colnames(f["units"]) == ["spike_times"], "the fixture colnames must be clean"
    with pytest.raises(UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=dst, repairs=["units_colnames"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_vector_index_with_nothing_to_change_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with pytest.raises(UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=dst, repairs=["vector_index_types"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_waveform_index_with_nothing_to_change_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb_with_waveform(src)
    with pytest.raises(UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=dst, repairs=["waveform_index_dtype"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_targetless_index_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["units"].create_dataset("waveform_mean_index", data=np.array([1], dtype="i8"))
    with h5py.File(src, "r") as f:
        assert "units/waveform_mean" not in f, "the index target must be absent"
    with pytest.raises(UnidentifiableRepairError, match="cannot identify a target"):
        repair_nwb(src, dst=dst, repairs=["vector_index_types"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_non_integral_waveform_index_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        f["units"].create_dataset("waveform_mean_index", data=np.array([1.5], dtype="f8"))
    with h5py.File(src, "r") as f:
        assert float(f["units/waveform_mean_index"][0]) == 1.5, \
            "the crafted index must be non-integral before the repair"
    with pytest.raises(UnidentifiableRepairError, match="not integral"):
        repair_nwb(src, dst=dst, repairs=["waveform_index_dtype"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_undeclared_squeeze_attribute_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["units"].attrs["custom"] = np.array(["x"], dtype=object)
    with h5py.File(src, "r") as f:
        assert np.asarray(f["units"].attrs["custom"]).shape == (1,)
    with pytest.raises(UnidentifiableRepairError, match="cannot identify"):
        repair_nwb(src, dst=dst, repairs=["squeeze_scalar_attributes"])
    assert not dst.exists(), "a refused repair must leave no file behind"


def test_repair_vector_index_refuses_valid_foreign_target(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        units = f["units"]
        units.create_dataset("waveform_mean", data=np.zeros((1, 4), dtype="f8"))
        units.create_dataset("bar", data=np.zeros((1, 4), dtype="f8"))
        index = units.create_dataset("waveform_mean_index", data=np.array([1], dtype="u1"))
        index.attrs["description"] = "Index for VectorData 'waveform_mean'"
        index.attrs["neurodata_type"] = "VectorIndex"
        index.attrs["target"] = units["bar"].ref
    with h5py.File(src, "r") as f:
        assert f[f["units/waveform_mean_index"].attrs["target"]].name == "/units/bar", \
            "the index must target a valid dataset beside its derived one"
        assert "/units/waveform_mean" in f, "the derived target must exist"
    with pytest.raises(UnidentifiableRepairError, match="not identifiable"):
        repair_nwb(src, dst=dst, repairs=["vector_index_types"])
    assert not dst.exists(), "a refused repair must leave no file behind"
    with h5py.File(src, "r") as f:
        assert f[f["units/waveform_mean_index"].attrs["target"]].name == "/units/bar", \
            "the refused repair must leave the stored reference alone"


def test_transform_cast_of_an_index_dataset_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        f["units"].create_dataset("waveform_mean_index", data=np.array([2], dtype="f8"))
    with h5py.File(src, "r") as f:
        assert f["units/waveform_mean_index"].dtype.kind == "f", \
            "the fixture index must be floating"
    with pytest.raises(TypeError, match="never cast"):
        transform_nwb(src, dst=dst, cast={"units/waveform_mean_index": "float32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_cast_of_integer_to_non_floating_dtype_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r") as f:
        assert f["units/id"].dtype.kind == "i", "the fixture column must be integral"
    with pytest.raises(TypeError, match="stay floating"):
        transform_nwb(src, dst=dst, cast={"units/id": "int32"})
    assert not dst.exists(), "a refused transform must leave no file behind"


def test_transform_scalar_cast_verifies(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "cast.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["acquisition/raw"].create_dataset("scalar_probe", data=np.float64(3.5))
    with h5py.File(src, "r") as f:
        assert f["acquisition/raw/scalar_probe"].shape == (), \
            "the fixture must hold a scalar float dataset"
        assert f["acquisition/raw/scalar_probe"].dtype.kind == "f"
    rep = transform_nwb(src, dst=dst, cast={"acquisition/raw/scalar_probe": "float32"})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert f["acquisition/raw/scalar_probe"].dtype == np.dtype("float32")
        assert float(f["acquisition/raw/scalar_probe"][()]) == np.float32(3.5)


def test_repair_integer_waveform_index_is_repaired(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb_with_waveform(src)
    with h5py.File(src, "r+") as f:
        f["units"].create_dataset("waveform_mean_index", data=np.array([0, 1, 2], dtype="i8"))
    with h5py.File(src, "r") as f:
        assert f["units/waveform_mean_index"].dtype.kind == "i", \
            "the crafted index must be integral but not floating"
    rep = repair_nwb(src, dst=dst, repairs=["waveform_index_dtype"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        index = f["units/waveform_mean_index"]
        assert index.dtype == np.dtype("uint8")
        assert np.array_equal(np.asarray(index[...]).ravel(), [0, 1, 2])


def test_transform_cast_with_a_leading_slash_succeeds(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "cast.nwb"
    _make_nwb(src)
    rep = transform_nwb(src, dst=dst, cast={"/acquisition/raw/data": "float32"})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert str(f["acquisition/raw/data"].dtype) == "float32", \
            "a leading slash must not false-refuse an existing dataset"


def test_transform_drop_with_an_unreadable_referrer_refuses(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        holder = f.require_group("ref_holder")
        target = holder.create_dataset("target_ds", data=np.arange(3, dtype="f8"))
        refs = holder.create_dataset("refs", shape=(1,), dtype=h5py.ref_dtype)
        refs[0] = target.ref
        del holder["target_ds"]
    with h5py.File(src, "r") as f:
        ref = f["ref_holder/refs"][0]
        try:
            f[ref]
        except Exception:
            pass
        else:
            raise AssertionError("the fixture referrer must not dereference")
    with pytest.raises(NWBMutationError, match="ref_holder/refs cannot be dereferenced"):
        transform_nwb(src, dst=dst, drop=["units"])
    assert not dst.exists(), "a refused transform must leave no file behind"


def _make_nwb_with_stimulus(path):
    nwb = NWBFile(
        session_description="stimulus repair fixture", identifier="stimulus-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1",
                                     device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1",
                          filtering="none", group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=np.arange(80, dtype="f8").reshape(20, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=0.0))
    nwb.add_stimulus(ElectricalSeries(
        name="estim", data=np.arange(40, dtype="f8").reshape(10, 4),
        electrodes=region, rate=1000.0, conversion=1.0, starting_time=0.0))
    nwb.add_unit(spike_times=np.array([0.1, 0.4, 0.9]))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def test_repair_contradiction_under_stimulus_is_reported(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "fixed.nwb"
    _make_nwb_with_stimulus(src)
    with h5py.File(src, "r+") as f:
        f["units"].attrs["colnames"] = np.array(
            ["spike_times_index"] + _colnames(f["units"]), dtype=object)
        f["stimulus/presentation/estim/data"].attrs["unit"] = "millivolts"
    rep = repair_nwb(src, dst=dst, repairs=["units_colnames"])
    assert rep.ok, [c for c in rep.checks if not c.ok]
    flagged = [i for i in rep.issues
               if i.severity == "warning" and i.location == "/stimulus/presentation"]
    assert flagged, rep.issues
    assert any("unit" in i.message for i in flagged), [i.message for i in flagged]
    with h5py.File(dst, "r") as f:
        assert _attr_str(f["stimulus/presentation/estim/data"].attrs["unit"]) == "millivolts", \
            "the contradiction is reported, never rewritten"


def test_transform_int32_to_float64_widening_succeeds(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "cast.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        f["acquisition/raw"].create_dataset("int32_data", data=np.arange(6, dtype="i4"))
    with h5py.File(src, "r") as f:
        assert f["acquisition/raw/int32_data"].dtype == np.dtype("int32")
    rep = transform_nwb(src, dst=dst, cast={"acquisition/raw/int32_data": "float64"})
    assert rep.ok, [c for c in rep.checks if not c.ok]
    with h5py.File(dst, "r") as f:
        assert f["acquisition/raw/int32_data"].dtype == np.dtype("float64")
        assert np.array_equal(f["acquisition/raw/int32_data"][:], np.arange(6))


def test_repair_vector_index_ignores_other_indices(tmp_path):
    src = tmp_path / "src.nwb"
    dst = tmp_path / "never.nwb"
    _make_nwb(src)
    with h5py.File(src, "r+") as f:
        del f["units/spike_times_index"].attrs["neurodata_type"]
        del f["units/spike_times_index"].attrs["target"]
    with h5py.File(src, "r") as f:
        assert "neurodata_type" not in f["units/spike_times_index"].attrs, \
            "the unlisted index must be untyped before the repair"
    with pytest.raises(UnidentifiableRepairError, match="changes nothing"):
        repair_nwb(src, dst=dst, repairs=["vector_index_types"])
    assert not dst.exists(), "a refused repair must leave no file behind"
    with h5py.File(src, "r") as f:
        assert "neurodata_type" not in f["units/spike_times_index"].attrs, \
            "the unlisted index must be left unchanged"
