"""Reproduce independent-review claims; print JSON-ish receipts. Harness-only."""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pynwb
from dateutil.tz import tzutc
from pynwb import NWBHDF5IO
from pynwb.epoch import TimeIntervals

import sys
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jnwb
from jnwb.nwb_events import event_onsets, events
from jnwb.nwb_inspect import acquisition_channel, inspect, resolve_acquisition


def _processing_lfp_path() -> Path:
    path = Path(tempfile.mkdtemp()) / "processing_lfp.nwb"
    nwb = pynwb.NWBFile(
        session_description="processing lfp probe",
        identifier="PROC_LFP",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    device = nwb.create_device(name="dev0")
    eg = nwb.create_electrode_group(name="eg0", description="", location="site", device=device)
    nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=1.0, location="site", filtering="none", group=eg)
    region = nwb.create_electrode_table_region(region=[0], description="ch0")
    data = np.arange(1000, dtype=np.float32).reshape(-1, 1)
    es = pynwb.ecephys.ElectricalSeries(
        name="LFP", data=data, electrodes=region, rate=1000.0, starting_time=0.0,
    )
    ecephys = pynwb.base.ProcessingModule(name="ecephys", description="ecephys")
    nwb.add_processing_module(ecephys)
    lfp_mod = pynwb.ecephys.LFP(name="LFP")
    lfp_mod.add_electrical_series(es)
    ecephys.add(lfp_mod)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


def main() -> None:
    out: dict = {}

    # 1 processing LFP
    p = _processing_lfp_path()
    info = inspect(p)
    out["processing_lfp"] = {
        "inspect_acquisitions": [a["name"] for a in info.get("acquisitions", [])],
        "inspect_processing": [a["name"] for a in info.get("processing_continuous", [])],
        "acquisition_channel": None,
    }
    try:
        acquisition_channel(p, channel=0)
        out["processing_lfp"]["acquisition_channel"] = "ok"
    except Exception as exc:
        out["processing_lfp"]["acquisition_channel"] = f"{type(exc).__name__}: {exc}"

    # 2 no codes column
    path = Path(tempfile.mkdtemp()) / "no_codes.nwb"
    table = TimeIntervals(name="trials", description="trials")
    table.add_row(start_time=1.0, stop_time=2.0)
    nwb = pynwb.NWBFile(
        session_description="no codes", identifier="NO_CODES",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    nwb.add_time_intervals(table)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    try:
        out["no_codes_event_onsets"] = event_onsets(path, codes=None).tolist()
    except Exception as exc:
        out["no_codes_event_onsets"] = f"{type(exc).__name__}: {exc}"
    try:
        out["no_codes_events"] = events(path).n_events
    except Exception as exc:
        out["no_codes_events"] = f"{type(exc).__name__}: {exc}"

    # 3 1D ES
    path = Path(tempfile.mkdtemp()) / "es1d.nwb"
    nwb = pynwb.NWBFile(
        session_description="1d", identifier="ES1D",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    device = nwb.create_device(name="d")
    eg = nwb.create_electrode_group(name="e", description="", location="s", device=device)
    nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=1.0, location="s", filtering="none", group=eg)
    region = nwb.create_electrode_table_region(region=[0], description="c")
    data = np.arange(500, dtype=np.float32)
    es = pynwb.ecephys.ElectricalSeries(
        name="voltage", data=data, electrodes=region, rate=1000.0, starting_time=0.0,
    )
    nwb.add_acquisition(es)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    with NWBHDF5IO(str(path), "r") as io:
        out["es1d_shape"] = list(io.read().acquisition["voltage"].data.shape)
    try:
        ch, fs = acquisition_channel(path, channel=0)
        out["es1d_ch0"] = {"len": len(ch), "fs": fs}
    except Exception as exc:
        out["es1d_ch0"] = f"{type(exc).__name__}: {exc}"

    # 4 conversion
    path = Path(tempfile.mkdtemp()) / "conv.nwb"
    nwb = pynwb.NWBFile(
        session_description="c", identifier="C",
        session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
    )
    device = nwb.create_device(name="d")
    eg = nwb.create_electrode_group(name="e", description="", location="s", device=device)
    nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=1.0, location="s", filtering="none", group=eg)
    region = nwb.create_electrode_table_region(region=[0], description="c")
    raw = np.array([[0.0], [1.0], [2.0], [3.0]], dtype=np.float32)
    es = pynwb.ecephys.ElectricalSeries(
        name="adc", data=raw, electrodes=region, rate=1000.0, starting_time=0.0,
        conversion=0.001, offset=0.5,
    )
    nwb.add_acquisition(es)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    with NWBHDF5IO(str(path), "r") as io:
        s = io.read().acquisition["adc"]
        stored = np.asarray(s.data).ravel().tolist()
        conv, off = float(s.conversion), float(s.offset)
    ch, _ = acquisition_channel(path, channel=0)
    out["conversion"] = {
        "pynwb_data": stored,
        "conversion": conv,
        "offset": off,
        "jnwb": ch.tolist(),
        "expected_physical": [v * conv + off for v in stored],
    }

    # 5 edge probes
    st = np.array([0.15, 0.25])
    onsets = np.array([0.1])
    _, rate, sem = jnwb.raster_psth(st, onsets, win_ms=(-50, 50), bin_ms=10.0)
    phases = np.linspace(-np.pi + 1e-15, np.pi - 1e-15, 8)
    sig = np.ones(8)
    out["psth_n1_sem_all_zero"] = bool(np.all(sem == 0))
    out["ppc_bound"] = float(jnwb.pairwise_phase_consistency(phases))
    try:
        jnwb.bandpass_filter(sig, fs=1000.0, low_cut=10.0, high_cut=40.0, order=4)
        out["short_sos_zero_phase"] = "ok"
    except Exception as exc:
        out["short_sos_zero_phase"] = f"{type(exc).__name__}"

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
