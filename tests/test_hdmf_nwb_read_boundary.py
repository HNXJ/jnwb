"""Scope and reproducer tests for jnwb.nwb_io read-boundary HDMF repairs."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime

import h5py
import numpy as np
import pytest
from dateutil.tz import tzlocal
from hdmf.build.builders import GroupBuilder
from hdmf.build.manager import BuildManager
from pynwb import NWBFile, NWBHDF5IO, get_type_map

from jnwb.nwb_io import (
    MissingRequiredNWBFieldError,
    hdmf_build_repair_context,
    read_nwb,
)

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))


def _run_isolated(prelude: str, body: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", prelude + body],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return (result.stdout + result.stderr).strip()


def _write_minimal_nwb(
    path: str,
    *,
    with_waveform: bool = False,
) -> None:
    nwb = NWBFile(
        session_description="t",
        identifier="id",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzlocal()),
    )
    device = nwb.create_device(name="dev")
    eg = nwb.create_electrode_group(
        name="eg", description="", location="", device=device
    )
    for _ in range(2):
        nwb.add_electrode(
            x=0.0,
            y=0.0,
            z=0.0,
            imp=0.0,
            location="loc",
            filtering="none",
            group=eg,
        )
    kwargs: dict = {"spike_times": [0.1, 0.2], "electrodes": [0]}
    if with_waveform:
        kwargs["waveform_mean"] = [[0.0] * 4, [1.0] * 4]
    nwb.add_unit(**kwargs)
    with NWBHDF5IO(path, "w") as io:
        io.write(nwb)


def _corrupt_missing_session_description(path: str) -> None:
    with h5py.File(path, "a") as f:
        del f["session_description"]


def _corrupt_units_colnames_index(path: str) -> None:
    with h5py.File(path, "a") as f:
        cols = ["spike_times_index"] + list(f["units"].attrs["colnames"])
        f["units"].attrs["colnames"] = np.array(cols, dtype=object)


def _corrupt_malformed_vector_index(path: str, index_name: str) -> None:
    with h5py.File(path, "a") as f:
        units = f["units"]
        g = units.create_group(index_name)
        g.create_dataset("data", data=np.array([0.0, 1.0], dtype=np.float64))
        cols = list(units.attrs["colnames"]) + [index_name]
        units.attrs["colnames"] = np.array(cols, dtype=object)


class TestImportDoesNotPatchGlobally:
    def test_import_jnwb_leaves_buildmanager_construct_unchanged(self):
        out = _run_isolated(
            "import jnwb\n",
            """
from hdmf.build.manager import BuildManager
print(BuildManager.construct.__name__)
""",
        )
        assert out.endswith("construct")

    def test_direct_pynwb_after_import_jnwb_unchanged_for_malformed_units(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path)
            _corrupt_units_colnames_index(path)
            body = f"""
from pynwb import NWBHDF5IO
path = r"{path}"
try:
    with NWBHDF5IO(path, "r") as io:
        io.read()
    print("OK")
except Exception:
    print("FAIL")
"""
            assert "FAIL" in _run_isolated("import jnwb\n", body)
        finally:
            os.remove(path)


class TestConstructRestoration:
    def test_restored_after_successful_read(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path)
            read_nwb(path)
            assert BuildManager.construct.__name__ == "construct"
        finally:
            os.remove(path)

    def test_restored_after_failed_read(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path)
            _corrupt_missing_session_description(path)
            with pytest.raises(MissingRequiredNWBFieldError):
                read_nwb(path)
            assert BuildManager.construct.__name__ == "construct"
        finally:
            os.remove(path)

    def test_nested_context_leaves_construct_restored(self):
        with hdmf_build_repair_context():
            with hdmf_build_repair_context():
                assert BuildManager.construct.__name__ == "jnwb_hdmf_repair_construct"
        assert BuildManager.construct.__name__ == "construct"


class TestRepairReproducersViaReadBoundary:
    def test_repair1_one_element_string_ndarray_attribute(self):
        mgr = BuildManager(get_type_map())
        gb = GroupBuilder(
            name="device",
            attributes={
                "namespace": "core",
                "neurodata_type": "Device",
                "description": np.array(["probe desc"], dtype=object),
            },
        )
        with pytest.raises(Exception):
            mgr.construct(gb)
        with hdmf_build_repair_context():
            obj = mgr.construct(gb)
        assert obj.description == "probe desc"

    def test_repair2_missing_session_description_fails_loudly(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path)
            _corrupt_missing_session_description(path)
            with pytest.raises(MissingRequiredNWBFieldError) as excinfo:
                read_nwb(path)
            assert excinfo.value.field_name == "session_description"
        finally:
            os.remove(path)

    def test_repair3_units_colnames_lists_index_columns(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path)
            _corrupt_units_colnames_index(path)
            with pytest.raises(Exception):
                with NWBHDF5IO(path, "r") as io:
                    io.read()
            nwb = read_nwb(path)
            assert list(nwb.units.colnames) == ["spike_times", "electrodes"]
        finally:
            os.remove(path)

    def test_repair4_waveform_mean_index_missing_type_target_float_data(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _write_minimal_nwb(path, with_waveform=True)
            _corrupt_malformed_vector_index(path, "waveform_mean_index")
            with pytest.raises(Exception):
                with NWBHDF5IO(path, "r") as io:
                    io.read()
            nwb = read_nwb(path)
            assert tuple(nwb.units.colnames) == (
                "spike_times",
                "electrodes",
                "waveform_mean",
            )
        finally:
            os.remove(path)

    def test_repair4_spike_amplitudes_index_missing_type_target_float_data(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            nwb = NWBFile(
                session_description="t",
                identifier="id",
                session_start_time=datetime(2020, 1, 1, tzinfo=tzlocal()),
            )
            device = nwb.create_device(name="dev")
            eg = nwb.create_electrode_group(
                name="eg", description="", location="", device=device
            )
            nwb.add_electrode(
                x=0.0, y=0.0, z=0.0, imp=0.0, location="loc", filtering="none", group=eg
            )
            nwb.add_unit_column("spike_amplitudes", description="test amplitudes")
            nwb.add_unit(
                spike_times=[0.1, 0.2], electrodes=[0], spike_amplitudes=[1.0, 2.0]
            )
            with NWBHDF5IO(path, "w") as io:
                io.write(nwb)
            _corrupt_malformed_vector_index(path, "spike_amplitudes_index")
            with pytest.raises(Exception):
                with NWBHDF5IO(path, "r") as io:
                    io.read()
            nwb = read_nwb(path)
            assert set(nwb.units.colnames) == {
                "spike_times",
                "electrodes",
                "spike_amplitudes",
            }
        finally:
            os.remove(path)
