"""Tests for jnwb.inspect structured NWB discovery."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

import numpy as np
import jnwb
from jnwb.nwb_inspect import (
    AcquisitionNotFoundError,
    AmbiguousAcquisitionError,
    ChannelIndexError,
    acquisition_channel,
    inspect,
    resolve_acquisition,
    unit_spike_times,
)
from jnwb.testing.nwb_fixtures import (
    FLASH_TABLE,
    RF_TABLE,
    TASK_TABLE,
    canonical_co_resident_options,
    lfp_wrapped_options,
    processing_lfp_options,
    task_only_options,
    write_synth_nwb,
)


@pytest.fixture
def canonical_nwb(tmp_path):
    path = tmp_path / "canonical.nwb"
    receipt = write_synth_nwb(path, canonical_co_resident_options())
    return path, receipt


class TestInspect:
    def test_public_export(self):
        assert hasattr(jnwb, "inspect")
        assert jnwb.inspect is inspect

    def test_lists_all_interval_tables_without_selection(self, canonical_nwb):
        path, _ = canonical_nwb
        info = inspect(path)
        names = {t["name"] for t in info["interval_tables"]}
        assert TASK_TABLE in names
        assert RF_TABLE in names
        assert FLASH_TABLE in names
        assert len(info["interval_tables"]) >= 3

    def test_interval_columns_and_codes_samples(self, canonical_nwb):
        path, receipt = canonical_nwb
        info = inspect(path)
        task = next(t for t in info["interval_tables"] if t["name"] == TASK_TABLE)
        col_names = {c["name"] for c in task["columns"]}
        assert "codes" in col_names
        assert "task_condition_number" in col_names
        codes_col = next(c for c in task["columns"] if c["name"] == "codes")
        assert receipt.task_codes[0] in codes_col["sample_values"]

    def test_known_onsets_recoverable(self, canonical_nwb):
        path, receipt = canonical_nwb
        info = inspect(path)
        task = next(t for t in info["interval_tables"] if t["name"] == TASK_TABLE)
        start_col = next(c for c in task["columns"] if c["name"] == "start_time")
        assert start_col["sample_values"][0] == float(receipt.task_onsets_s[0])

    def test_acquisition_rate_and_channels(self, canonical_nwb):
        path, receipt = canonical_nwb
        info = inspect(path)
        lfp = next(a for a in info["acquisitions"] if a["name"] == "probe_0_lfp")
        assert lfp["rate_hz"] == receipt.fs_hz
        assert lfp["data_shape"][1] == receipt.n_channels
        assert lfp["packaging"] == "direct"
        assert lfp["neurodata_type"] == "ElectricalSeries"

    def test_lfp_wrapped_packaging(self, tmp_path):
        path = tmp_path / "wrapped.nwb"
        write_synth_nwb(path, lfp_wrapped_options())
        info = inspect(path)
        lfp = next(a for a in info["acquisitions"] if a["name"] == "probe_0_lfp")
        assert lfp["packaging"] == "lfp_wrapped"
        assert lfp["neurodata_type"] == "LFP"
        assert "probe_0_lfp_data" in lfp.get("data_path", "")

    def test_task_only_file(self, tmp_path):
        path = tmp_path / "task_only.nwb"
        write_synth_nwb(path, task_only_options())
        info = inspect(path)
        assert len(info["interval_tables"]) == 1
        assert info["interval_tables"][0]["name"] == TASK_TABLE

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            inspect("nonexistent_file.nwb")

    def test_in_memory_nwb(self):
        from jnwb.testing.nwb_fixtures import build_synth_nwb

        nwb, receipt = build_synth_nwb(canonical_co_resident_options())
        info = inspect(nwb)
        assert len(info["interval_tables"]) >= 3
        assert info["electrodes"]["n_rows"] == receipt.n_channels


class TestNWBReadHelpers:
    def test_unit_spike_times(self, canonical_nwb):
        path, receipt = canonical_nwb
        spikes = unit_spike_times(path, unit_index=0)
        expected = receipt.task_onsets_s + 0.01
        np.testing.assert_allclose(spikes, expected)

    def test_acquisition_channel(self, canonical_nwb):
        path, receipt = canonical_nwb
        data, fs_hz = acquisition_channel(path, name="probe_0_lfp", channel=0)
        assert data.ndim == 1
        assert fs_hz == receipt.fs_hz

    def test_lfp_wrapped_acquisition_channel(self, tmp_path):
        path = tmp_path / "wrapped.nwb"
        receipt = write_synth_nwb(path, lfp_wrapped_options())
        data, fs_hz = acquisition_channel(path, name="probe_0_lfp", channel=0)
        assert data.size > 0
        assert fs_hz == receipt.fs_hz

    def test_processing_lfp_discovery_and_channel(self, tmp_path):
        path = tmp_path / "proc_lfp.nwb"
        receipt = write_synth_nwb(path, processing_lfp_options())
        info = inspect(path)
        assert len(info["acquisitions"]) == 0
        assert len(info["processing_continuous"]) == 1
        entry = info["processing_continuous"][0]
        assert entry["name"] == "LFP"
        assert entry["module"] == "ecephys"
        assert entry["rate_hz"] == receipt.fs_hz

        # resolve_acquisition and acquisition_channel resolve processing LFP
        target = resolve_acquisition(path, None)
        assert target == "LFP"
        data, fs_hz = acquisition_channel(path, channel=0)
        assert data.ndim == 1
        assert len(data) > 0
        assert fs_hz == receipt.fs_hz

    def test_1d_electrical_series_channel_access(self, tmp_path):
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBFile, NWBHDF5IO
        import pynwb

        path = tmp_path / "es_1d.nwb"
        nwb = NWBFile(
            session_description="1D series test",
            identifier="TEST_1D",
            session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
        )
        dev = nwb.create_device(name="dev0")
        eg = nwb.create_electrode_group(name="eg0", description="", location="loc", device=dev)
        nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=1.0, location="loc", filtering="none", group=eg)
        region = nwb.create_electrode_table_region(region=[0], description="e0")
        raw = np.linspace(0.0, 10.0, 500, dtype=np.float32)
        es = pynwb.ecephys.ElectricalSeries(
            name="signal_1d",
            data=raw,
            electrodes=region,
            rate=500.0,
            starting_time=0.0,
        )
        nwb.add_acquisition(es)
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)

        # Channel 0 succeeds for 1D
        data, fs = acquisition_channel(path, channel=0)
        assert data.shape == (500,)
        assert fs == 500.0
        np.testing.assert_allclose(data, raw)

        # Out-of-range channel raises ChannelIndexError
        with pytest.raises(ChannelIndexError):
            acquisition_channel(path, channel=1)
        with pytest.raises(ChannelIndexError):
            acquisition_channel(path, channel=-1)

    def test_channel_index_error_2d_series(self, canonical_nwb):
        path, receipt = canonical_nwb
        with pytest.raises(ChannelIndexError):
            acquisition_channel(path, name="probe_0_lfp", channel=receipt.n_channels + 5)
        with pytest.raises(ChannelIndexError):
            acquisition_channel(path, name="probe_0_lfp", channel=-1)

    def test_conversion_and_offset_scaling(self, tmp_path):
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBFile, NWBHDF5IO
        import pynwb

        path = tmp_path / "scaled.nwb"
        nwb = NWBFile(
            session_description="Scaling test",
            identifier="TEST_SCALING",
            session_start_time=datetime(2020, 1, 1, tzinfo=tzutc()),
        )
        dev = nwb.create_device(name="dev0")
        eg = nwb.create_electrode_group(name="eg0", description="", location="loc", device=dev)
        nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=1.0, location="loc", filtering="none", group=eg)
        region = nwb.create_electrode_table_region(region=[0], description="e0")
        raw = np.array([[100.0], [200.0], [300.0]], dtype=np.float32)
        conversion = 0.001
        offset = 0.5
        es = pynwb.ecephys.ElectricalSeries(
            name="calibrated_lfp",
            data=raw,
            electrodes=region,
            rate=1000.0,
            starting_time=0.0,
            conversion=conversion,
            offset=offset,
        )
        nwb.add_acquisition(es)
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)

        data, fs = acquisition_channel(path, channel=0)
        expected = raw[:, 0] * conversion + offset
        np.testing.assert_allclose(data, expected)

