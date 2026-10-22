"""Probes for jnwb.nwb_write.verify_nwb: re-reading a written NWB file.

Each test writes its NWB file with pynwb into tmp_path. No writer exists yet, so the
against-comparison builds its MutationReport by hand.
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
from jnwb.nwb_write import (
    AppliedOperation,
    MutationCheck,
    MutationIssue,
    MutationReport,
    verify_nwb,
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
