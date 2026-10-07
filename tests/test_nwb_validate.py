"""Probes for jnwb.nwb_validate: layered NWB validation (read, pynwb schema, installed core schema,
integrity, NWB Inspector, DANDI) on small files written with pynwb."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile
from pynwb.ecephys import ElectricalSeries
from pynwb.file import Subject
from pynwb.misc import Units

import jnwb
from jnwb import NWBValidationReport, validate_nwb
from jnwb.nwb_validate import ValidationLayer


def _make_nwb(path, *, n_units=3):
    nwb = NWBFile(
        session_description="synthetic validation fixture", identifier="fixture-1",
        session_start_time=datetime(2026, 1, 1, tzinfo=timezone.utc), experimenter=["Doe, Jane"],
        lab="lab", institution="inst", session_id="s1",
        subject=Subject(subject_id="sub1", species="Macaca mulatta", sex="M", age="P5Y",
                        description="fixture subject"))
    dev = nwb.create_device(name="probe_dev", description="d", manufacturer="m")
    grp = nwb.create_electrode_group(name="probeA", description="g", location="V1", device=dev)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=1.0, location="V1", filtering="none",
                          group=grp, group_name="probeA")
    region = nwb.create_electrode_table_region(region=[0, 1, 2, 3], description="all")
    nwb.add_acquisition(ElectricalSeries(
        name="raw", data=np.zeros((20, 4), dtype="f4"), electrodes=region, rate=1000.0,
        conversion=1.0))
    nwb.units = Units(name="units", description="fixture units", resolution=1 / 30000.0)
    for u in range(n_units):
        nwb.add_unit(spike_times=0.0123 + 0.5 * np.arange(2 + u, dtype="f8"), id=u)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)


def test_symbols_are_public():
    for name in ("validate_nwb", "NWBValidationReport"):
        assert name in jnwb.__all__ and hasattr(jnwb, name)


def test_clean_file_passes_every_layer_that_runs(tmp_path):
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    rep = validate_nwb(p)
    assert isinstance(rep, NWBValidationReport) and all(isinstance(x, ValidationLayer) for x in rep.layers)
    assert [x.name for x in rep.layers] == list(jnwb.nwb_validate.LAYERS)
    for name in ("read", "pynwb_schema", "pynwb_core", "integrity"):
        assert rep.layer(name).status == "pass", rep.layer(name).messages
    assert rep.ok
    for name in ("nwbinspector", "dandi"):
        assert rep.layer(name).status in ("pass", "skipped"), rep.layer(name).messages
    assert rep.versions["pynwb"]


def test_dandi_ready_needs_the_dandi_layer_to_have_run(tmp_path, monkeypatch):
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    monkeypatch.setitem(sys.modules, "dandi", None)       # import dandi -> ImportError
    rep = validate_nwb(p)
    assert rep.layer("dandi").status == "skipped" and "not installed" in rep.layer("dandi").detail
    assert rep.ok and not rep.complete and not rep.dandi_ready


def test_dandi_ready_true_when_dandi_runs_clean(tmp_path):
    pytest.importorskip("dandi")
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    rep = validate_nwb(p, layers=("read", "pynwb_schema", "pynwb_core", "dandi"))
    assert rep.layer("dandi").status == "pass", rep.layer("dandi").messages
    assert rep.dandi_ready


def test_missing_subject_fails_the_dandi_layer(tmp_path):
    pytest.importorskip("dandi")
    p = tmp_path / "nosubject.nwb"
    _make_nwb(p)
    with h5py.File(p, "r+") as f:
        del f["general/subject"]
    rep = validate_nwb(p, layers=("dandi",))
    assert rep.layer("dandi").status == "fail" and rep.layer("dandi").n_errors >= 1
    assert not rep.dandi_ready and not rep.ok


def test_ragged_index_defect_fails_the_integrity_layer(tmp_path):
    p = tmp_path / "bad_index.nwb"
    _make_nwb(p)
    with h5py.File(p, "r+") as f:
        idx = f["units/spike_times_index"]
        idx[...] = np.array([2, 1, 6], dtype=idx.dtype)       # not monotonic, wrong end
    rep = validate_nwb(p, layers=("integrity",))
    lay = rep.layer("integrity")
    assert lay.status == "fail" and "spike_times_index" in lay.messages[0]
    assert not rep.ok


def test_electrode_region_outside_table_fails_the_integrity_layer(tmp_path):
    p = tmp_path / "bad_region.nwb"
    _make_nwb(p)
    with h5py.File(p, "r+") as f:
        f["acquisition/raw/electrodes"][...] = np.array([0, 1, 2, 9], dtype="i8")
    lay = validate_nwb(p, layers=("integrity",)).layer("integrity")
    assert lay.status == "fail" and "outside electrodes table" in lay.messages[0]


def test_repeated_electrode_row_in_a_region_is_allowed(tmp_path):
    # one column per unit, several units on one electrode
    p = tmp_path / "dup.nwb"
    _make_nwb(p)
    with h5py.File(p, "r+") as f:
        f["acquisition/raw/electrodes"][...] = np.array([0, 0, 1, 1], dtype="i8")
    assert validate_nwb(p, layers=("integrity",)).layer("integrity").status == "pass"


def test_unreadable_file_fails_read_without_raising(tmp_path):
    p = tmp_path / "junk.nwb"
    p.write_bytes(b"not an hdf5 file")
    rep = validate_nwb(p, layers=("read", "pynwb_schema"))
    assert rep.layer("read").status == "fail" and not rep.ok


def test_argument_errors(tmp_path):
    with pytest.raises(FileNotFoundError):
        validate_nwb(tmp_path / "missing.nwb")
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    with pytest.raises(ValueError, match="unknown layers"):
        validate_nwb(p, layers=("read", "nope"))
    with pytest.raises(KeyError):
        validate_nwb(p, layers=("read",)).layer("dandi")


def test_summary_names_every_layer(tmp_path):
    p = tmp_path / "ok.nwb"
    _make_nwb(p)
    s = validate_nwb(p, layers=("read", "integrity")).summary()
    assert "read" in s and "integrity" in s and "dandi_ready=False" in s
