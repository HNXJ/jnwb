"""Reproducers for each HDMF BuildManager.construct repair in jnwb/__init__.py.

These tests document which malformed-builder cases the import-time patch currently
recovers. They do not assert desired end-state semantics (e.g. session_description
fabrication is covered only to pin present behaviour before 0.1.6 scoping).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from datetime import datetime

import h5py
import numpy as np
import pytest
from dateutil.tz import tzlocal
from pynwb import NWBFile, NWBHDF5IO

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))


def _run_isolated(prelude: str, body: str) -> str:
    code = prelude + body
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return (result.stdout + result.stderr).strip()


def _minimal_units_nwb(path: str, *, with_waveform: bool = False) -> None:
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
    if with_waveform:
        nwb.add_unit(
            spike_times=[0.1, 0.2],
            electrodes=[0],
            waveform_mean=[[0.0] * 4, [1.0] * 4],
        )
    else:
        nwb.add_unit(spike_times=[0.1, 0.2], electrodes=[0])
    with NWBHDF5IO(path, "w") as io:
        io.write(nwb)


class TestRepairReproducers:
    def test_repair1_one_element_string_ndarray_attribute(self):
        body = """
import numpy as np
from hdmf.build.builders import GroupBuilder
from hdmf.build.manager import BuildManager
from pynwb import get_type_map
mgr = BuildManager(get_type_map())
gb = GroupBuilder(
    name='device',
    attributes={
        'namespace': 'core',
        'neurodata_type': 'Device',
        'description': np.array(['probe desc'], dtype=object),
    },
)
try:
    obj = mgr.construct(gb)
    print('OK', repr(obj.description))
except Exception as e:
    print('FAIL', type(e).__name__)
"""
        assert "FAIL" in _run_isolated("", body)
        assert "OK 'probe desc'" in _run_isolated("import jnwb\n", body)

    def test_repair2_missing_session_description_fabricates_literal(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            nwb = NWBFile(
                session_description="real description",
                identifier="id",
                session_start_time=datetime(2020, 1, 1, tzinfo=tzlocal()),
            )
            with NWBHDF5IO(path, "w") as io:
                io.write(nwb)
            with h5py.File(path, "a") as f:
                del f["session_description"]
            body = f"""
from pynwb import NWBHDF5IO
try:
    with NWBHDF5IO(r"{path}", "r") as io:
        n = io.read()
    print("OK", repr(n.session_description))
except Exception:
    print("FAIL")
"""
            assert "FAIL" in _run_isolated("", body)
            assert "OK 'NWB session'" in _run_isolated("import jnwb\n", body)
        finally:
            os.remove(path)

    def test_repair3_units_colnames_lists_index_columns(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _minimal_units_nwb(path)
            with h5py.File(path, "a") as f:
                cols = ["spike_times_index"] + list(f["units"].attrs["colnames"])
                f["units"].attrs["colnames"] = np.array(cols, dtype=object)
            body = f"""
from pynwb import NWBHDF5IO
try:
    with NWBHDF5IO(r"{path}", "r") as io:
        n = io.read()
    print("OK", list(n.units.colnames))
except Exception:
    print("FAIL")
"""
            assert "FAIL" in _run_isolated("", body)
            assert "OK ['spike_times', 'electrodes']" in _run_isolated("import jnwb\n", body)
        finally:
            os.remove(path)

    def test_repair4_waveform_mean_index_missing_type_target_float_data(self):
        with tempfile.NamedTemporaryFile(suffix=".nwb", delete=False) as tmp:
            path = tmp.name
        try:
            _minimal_units_nwb(path, with_waveform=True)
            with h5py.File(path, "a") as f:
                units = f["units"]
                g = units.create_group("waveform_mean_index")
                g.create_dataset("data", data=np.array([0.0, 1.0], dtype=np.float64))
                cols = list(units.attrs["colnames"]) + ["waveform_mean_index"]
                units.attrs["colnames"] = np.array(cols, dtype=object)
            body = f"""
from pynwb import NWBHDF5IO
try:
    with NWBHDF5IO(r"{path}", "r") as io:
        n = io.read()
    print("OK", tuple(n.units.colnames))
except Exception:
    print("FAIL")
"""
            assert "FAIL" in _run_isolated("", body)
            assert "OK ('spike_times', 'electrodes', 'waveform_mean')" in _run_isolated(
                "import jnwb\n", body
            )
        finally:
            os.remove(path)


class TestPatchScope:
    def test_import_jnwb_replaces_buildmanager_construct_process_wide(self):
        out = _run_isolated(
            "import jnwb\n",
            """
from hdmf.build.manager import BuildManager
print(BuildManager.construct.__name__)
""",
        )
        assert "patched_manager_construct" in out
