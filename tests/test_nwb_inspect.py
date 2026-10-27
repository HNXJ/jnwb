"""Tests for jnwb.inspect structured NWB discovery."""

from __future__ import annotations

import pytest

import h5py
import numpy as np
import jnwb
from jnwb.nwb_inspect import (
    AcquisitionNotFoundError,
    AmbiguousAcquisitionError,
    ChannelIndexError,
    NWBInspectError,
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

    @pytest.mark.parametrize("kind", ["EyeTracking", "PupilTracking", "BehavioralTimeSeries"])
    def test_behavior_container_acquisition_channel(self, tmp_path, kind):
        """A series wrapped in a behavior container is read like one wrapped in `LFP`:
        by container name, bare series name or `container/series`. These used to
        raise AcquisitionNotFoundError because only `LFP` was unwrapped."""
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBHDF5IO, NWBFile, behavior

        data = np.arange(20.0).reshape(10, 2) if kind == "EyeTracking" else np.arange(10.0)
        nwb = NWBFile("s", "behavior", datetime(2026, 1, 1, tzinfo=tzutc()))
        container = getattr(behavior, kind)(name="tracking")
        if kind == "EyeTracking":
            container.create_spatial_series(name="tracking_data", data=data, rate=1000.0,
                                            reference_frame="screen", unit="degrees",
                                            conversion=2.0)
        else:
            container.create_timeseries(name="tracking_data", data=data, rate=1000.0,
                                        unit="a.u.", conversion=2.0)
        nwb.add_acquisition(container)
        path = tmp_path / "behavior.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwb)

        expected = 2.0 * (data[:, 1] if data.ndim == 2 else data)
        for name in ("tracking", "tracking_data", "tracking/tracking_data"):
            got, fs_hz = acquisition_channel(path, name=name, channel=1 if data.ndim == 2 else 0)
            np.testing.assert_array_equal(got, expected)
            assert fs_hz == 1000.0

    @pytest.mark.parametrize("kind", ["TimeSeries", "AbstractFeatureSeries"])
    def test_a_series_without_electrodes_is_time_first(self, tmp_path, kind):
        """A series with no electrode region has nothing to arbitrate its layout, and the NWB
        schema puts time on the first axis of every TimeSeries subtype: five samples of ten
        values are read as ten channels of five samples, whichever side is longer."""
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBHDF5IO, NWBFile, TimeSeries
        from pynwb.behavior import BehavioralTimeSeries
        from pynwb.misc import AbstractFeatureSeries

        data = np.arange(50.0).reshape(5, 10)
        nwb = NWBFile("s", "short", datetime(2026, 1, 1, tzinfo=tzutc()))
        if kind == "TimeSeries":
            series = TimeSeries(name="values", data=data, rate=100.0, unit="a.u.")
        else:
            series = AbstractFeatureSeries(name="values", data=data, rate=100.0,
                                           features=[f"f{i}" for i in range(10)],
                                           feature_units=["a.u."] * 10)
        container = BehavioralTimeSeries(name="behavior", time_series=series)
        nwb.add_acquisition(container)
        path = tmp_path / "short.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwb)

        got, _ = acquisition_channel(path, name="values", channel=3)
        np.testing.assert_array_equal(got, data[:, 3])
        entry = next(e for e in inspect(path)["acquisitions"] if e["name"] == "behavior")
        assert entry["layout"] == "time_by_channel"

    def test_an_in_memory_series_without_electrodes_is_time_first(self):
        """The object walk, which only an `NWBFile` with no file behind it reaches, applies the
        same time-first rule as the file walk above."""
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBFile, TimeSeries

        nwb = NWBFile("s", "short", datetime(2026, 1, 1, tzinfo=tzutc()))
        nwb.add_acquisition(TimeSeries(name="values", data=np.arange(50.0).reshape(5, 10),
                                       rate=100.0, unit="a.u."))
        assert getattr(nwb, "container_source", None) is None  # else inspect reads the file
        entry = next(e for e in inspect(nwb)["acquisitions"] if e["name"] == "values")
        assert entry["layout"] == "time_by_channel"

    def test_both_call_forms_unwrap_a_behavior_container_alike(self, tmp_path):
        """The object walk unwrapped only `LFP`, so an in-memory behavior container reported no
        series, shape or layout, and one in a processing module was left out, while the file
        form of the same file reported all of them."""
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBHDF5IO, NWBFile, TimeSeries
        from pynwb.behavior import BehavioralTimeSeries, PupilTracking
        from jnwb.nwb_inspect import CONTINUOUS_KEYS

        def build():
            nwb = NWBFile("s", "forms", datetime(2026, 1, 1, tzinfo=tzutc()))
            nwb.add_acquisition(BehavioralTimeSeries(name="behavior", time_series=TimeSeries(
                name="values", data=np.arange(50.0).reshape(5, 10), rate=100.0, unit="a.u.")))
            pupil = PupilTracking(name="pupil")
            for side in ("left", "right"):
                pupil.create_timeseries(name=side, data=np.zeros(5), rate=100.0, unit="a.u.")
            nwb.add_acquisition(pupil)
            nwb.create_processing_module("behavior", "processed").add(BehavioralTimeSeries(
                name="speed", time_series=TimeSeries(name="speed", data=np.zeros(8), rate=50.0,
                                                     unit="m/s")))
            return nwb

        def view(info):
            return {key: {e["name"]: {k: e[k] for k in CONTINUOUS_KEYS} for e in info[key]}
                    for key in ("acquisitions", "processing_continuous")}

        path = tmp_path / "forms.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(build())
        from_file = view(inspect(path))
        assert from_file["acquisitions"]["behavior"]["layout"] == "time_by_channel"
        assert from_file["acquisitions"]["pupil"]["series"] == ["left", "right"]
        assert set(from_file["processing_continuous"]) == {"speed"}
        assert view(inspect(build())) == from_file

    def test_behavior_container_with_two_series_is_ambiguous(self, tmp_path):
        from datetime import datetime
        from dateutil.tz import tzutc
        from pynwb import NWBHDF5IO, NWBFile
        from pynwb.behavior import PupilTracking

        nwb = NWBFile("s", "two", datetime(2026, 1, 1, tzinfo=tzutc()))
        pupil = PupilTracking(name="pupil")
        for sname in ("left", "right"):
            pupil.create_timeseries(name=sname, data=np.zeros(5), rate=100.0, unit="a.u.")
        nwb.add_acquisition(pupil)
        path = tmp_path / "two.nwb"
        with NWBHDF5IO(path, "w") as io:
            io.write(nwb)
        with pytest.raises(AmbiguousAcquisitionError, match="wraps 2 series"):
            acquisition_channel(path, name="pupil")
        got, _ = acquisition_channel(path, name="pupil/right")
        assert got.size == 5

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
        raw_int = np.array([[1000], [-500], [0]], dtype=np.int16)
        conversion = 0.00005
        offset = -0.01
        es = pynwb.ecephys.ElectricalSeries(
            name="calibrated_lfp",
            data=raw_int,
            electrodes=region,
            rate=1000.0,
            starting_time=0.0,
            conversion=conversion,
            offset=offset,
        )
        nwb.add_acquisition(es)
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)

        # Confirm PyNWB raw storage semantics
        with NWBHDF5IO(str(path), "r") as io:
            read_nwb = io.read()
            s = read_nwb.acquisition["calibrated_lfp"]
            assert s.unit == "volts"
            assert s.conversion == conversion
            assert s.offset == offset
            # s.data[:] returns raw stored integers, NOT scaled physical values
            np.testing.assert_array_equal(s.data[:], raw_int)

        # Confirm jnwb applies physical scaling exactly once
        data, fs = acquisition_channel(path, channel=0)
        assert data.dtype == np.float64
        expected = raw_int[:, 0].astype(np.float64) * conversion + offset
        np.testing.assert_allclose(data, expected)
        assert fs == 1000.0

    def test_channel_conversion_scales_each_channel(self, tmp_path):
        """NWB: physical = data * conversion * channel_conversion[ch] + offset.

        The same stored count on three channels must come back as three different voltages.
        What would pass while the factor is ignored: a test whose factors are all 1, or one
        that reads only channel 0.
        """
        from datetime import datetime, timezone
        from pynwb import NWBFile, NWBHDF5IO
        from pynwb.ecephys import ElectricalSeries

        path = tmp_path / "channel_conversion.nwb"
        nwb = NWBFile(session_description="cc", identifier="cc",
                      session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc))
        dev = nwb.create_device(name="d")
        grp = nwb.create_electrode_group(name="g", description="g", location="x", device=dev)
        for _ in range(3):
            nwb.add_electrode(group=grp, location="x")
        region = nwb.create_electrode_table_region([0, 1, 2], "all")
        factors, conversion, offset = [1.0, 2.0, 0.5], 1e-6, 1e-3
        raw = np.full((50, 3), 100, dtype=np.int16)
        nwb.add_acquisition(ElectricalSeries(
            name="es", data=raw, electrodes=region, rate=1000.0, conversion=conversion,
            offset=offset, channel_conversion=factors))
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)

        for ch, factor in enumerate(factors):
            data, _ = acquisition_channel(path, name="es", channel=ch)
            np.testing.assert_allclose(data, 100 * conversion * factor + offset, rtol=0, atol=1e-15)


def _nwb(identifier):
    from datetime import datetime

    from dateutil.tz import tzutc
    from pynwb import NWBFile

    return NWBFile("s", identifier, datetime(2026, 1, 1, tzinfo=tzutc()))


def _region(nwb, n_channels):
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="g", description="g", location="CA1", device=device)
    for _ in range(n_channels):
        nwb.add_electrode(x=0.0, y=0.0, z=0.0, imp=0.0, location="CA1", filtering="none", group=group)
    return nwb.create_electrode_table_region(region=list(range(n_channels)), description="all")


def _written(path, nwb):
    from pynwb import NWBHDF5IO

    with NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


class TestProcessingBehaviorContainers:
    """A behavior container under `processing/` is read like one under `/acquisition`."""

    def test_eye_tracking_under_processing_is_read_by_bare_and_qualified_name(self, tmp_path):
        """`inspect` lists `processing/behavior/EyeTracking`, and `acquisition_channel` refused it
        with 'No acquisitions or processing continuous series found'. Both names read it now."""
        from pynwb.behavior import EyeTracking

        data = np.arange(20.0).reshape(10, 2)
        nwb = _nwb("eye")
        eye = EyeTracking(name="EyeTracking")
        eye.create_spatial_series(name="eye_xy", data=data, rate=1000.0,
                                  reference_frame="screen", unit="pixels")
        nwb.create_processing_module(name="behavior", description="b").add(eye)
        path = _written(tmp_path / "eye.nwb", nwb)

        assert [e["name"] for e in inspect(path)["processing_continuous"]] == ["EyeTracking"]
        for name in ("EyeTracking", "behavior/EyeTracking"):
            got, fs_hz = acquisition_channel(path, name=name, channel=1)
            np.testing.assert_array_equal(got, data[:, 1])
            assert fs_hz == 1000.0

    def test_filtered_ephys_under_processing_is_read_by_bare_and_qualified_name(self, tmp_path):
        """`FilteredEphys` under `processing/` was refused as having no readable data array; it is
        read like `LFP` is, by its container name and by its series' name."""
        from pynwb.ecephys import ElectricalSeries, FilteredEphys

        data = np.arange(40.0).reshape(20, 2)
        nwb = _nwb("filtered")
        ephys = FilteredEphys(name="FilteredEphys", electrical_series=ElectricalSeries(
            name="filtered_series", data=data, electrodes=_region(nwb, 2), rate=500.0))
        nwb.create_processing_module(name="ecephys", description="e").add(ephys)
        path = _written(tmp_path / "filtered.nwb", nwb)

        for name in ("FilteredEphys", "ecephys/FilteredEphys", "filtered_series",
                     "ecephys/FilteredEphys/filtered_series"):
            got, fs_hz = acquisition_channel(path, name=name, channel=1)
            np.testing.assert_array_equal(got, data[:, 1])
            assert fs_hz == 500.0

    def test_a_lone_filtered_ephys_under_processing_resolves_when_the_name_is_omitted(self, tmp_path):
        """A non-empty `FilteredEphys` is the one continuous container in the file; omitting the
        name must choose it, as it does for an `LFP`, not report that nothing is available."""
        from pynwb.ecephys import ElectricalSeries, FilteredEphys

        data = np.arange(40.0).reshape(20, 2)
        nwb = _nwb("filtered-lone")
        ephys = FilteredEphys(name="FilteredEphys", electrical_series=ElectricalSeries(
            name="filtered_series", data=data, electrodes=_region(nwb, 2), rate=500.0))
        nwb.create_processing_module(name="ecephys", description="e").add(ephys)
        path = _written(tmp_path / "filtered_lone.nwb", nwb)

        assert resolve_acquisition(path) == "FilteredEphys"
        got, fs_hz = acquisition_channel(path, channel=1)
        np.testing.assert_array_equal(got, data[:, 1])
        assert fs_hz == 500.0


def _mixed():
    """One file's worth of every container family: wrapped acquisition containers, a behavior
    container holding a nested series, two timestamp-only containers and a direct series."""
    from pynwb import TimeSeries
    from pynwb.behavior import BehavioralEpochs, BehavioralEvents, EyeTracking
    from pynwb.ecephys import LFP, ElectricalSeries
    from pynwb.misc import IntervalSeries

    nwb = _nwb("mixed")
    region = _region(nwb, 2)
    eye = EyeTracking(name="EyeTracking")
    eye.create_spatial_series(name="eye_xy", data=np.arange(40.0).reshape(20, 2), rate=1000.0,
                              reference_frame="screen", unit="pixels")
    nwb.add_acquisition(eye)
    nwb.add_acquisition(LFP(name="probe_lfp", electrical_series=ElectricalSeries(
        name="lfp_series", data=np.arange(40.0).reshape(20, 2), electrodes=region, rate=500.0)))
    behavior = nwb.create_processing_module(name="behavior", description="b")
    behavior.add(BehavioralEvents(name="BehavioralEvents", time_series=TimeSeries(
        name="events_ts", data=np.arange(5.0), unit="a.u.", timestamps=np.arange(5.0) * 0.1)))
    behavior.add(BehavioralEpochs(name="BehavioralEpochs", interval_series=IntervalSeries(
        name="epochs_is", data=np.array([1, 0, 1], dtype=np.int8),
        timestamps=np.array([0.0, 1.0, 2.0]))))
    behavior.add(TimeSeries(name="direct", data=np.arange(50.0), unit="a", rate=60.0))
    return nwb


class TestOneUnwrapRuleForBothCallForms:
    """`inspect` of a file and of the object model it was written from report the same containers."""

    def test_the_file_and_the_object_model_agree_on_every_container(self, tmp_path):
        from jnwb.nwb_inspect import CONTINUOUS_KEYS

        def view(info):
            return {key: {e["name"]: {k: e[k] for k in CONTINUOUS_KEYS} for e in info[key]}
                    for key in ("acquisitions", "processing_continuous")}

        path = _written(tmp_path / "mixed.nwb", _mixed())
        from_file = view(inspect(path))
        assert set(from_file["processing_continuous"]) == {
            "BehavioralEvents", "BehavioralEpochs", "direct"}
        assert set(from_file["acquisitions"]) == {"EyeTracking", "probe_lfp"}
        assert view(inspect(_mixed())) == from_file


def _acq_lfp():
    from pynwb.ecephys import LFP, ElectricalSeries

    nwb = _nwb("acq-lfp")
    nwb.add_acquisition(LFP(name="probe_lfp", electrical_series=ElectricalSeries(
        name="lfp_series", data=np.arange(40.0).reshape(20, 2), electrodes=_region(nwb, 2),
        rate=500.0)))
    return nwb


def _proc_lfp():
    from pynwb.ecephys import LFP, ElectricalSeries

    nwb = _nwb("proc-lfp")
    lfp = LFP(name="LFP", electrical_series=ElectricalSeries(
        name="lfp_series", data=np.arange(40.0).reshape(20, 2), electrodes=_region(nwb, 2),
        rate=500.0))
    nwb.create_processing_module(name="ecephys", description="e").add(lfp)
    return nwb


def _acq_pupil():
    from pynwb.behavior import PupilTracking

    nwb = _nwb("pupil")
    pupil = PupilTracking(name="PupilTracking")
    pupil.create_timeseries(name="pupil_ts", data=np.arange(50.0), rate=100.0, unit="a.u.")
    nwb.add_acquisition(pupil)
    return nwb


def _proc_eye():
    from pynwb.behavior import EyeTracking

    nwb = _nwb("proc-eye")
    eye = EyeTracking(name="EyeTracking")
    eye.create_spatial_series(name="eye_xy", data=np.arange(20.0).reshape(10, 2), rate=1000.0,
                              reference_frame="screen", unit="pixels")
    nwb.create_processing_module(name="behavior", description="b").add(eye)
    return nwb


def _events(where):
    from pynwb import TimeSeries
    from pynwb.behavior import BehavioralEvents

    nwb = _nwb(f"events-{where}")
    events = BehavioralEvents(name="BehavioralEvents", time_series=TimeSeries(
        name="events_ts", data=np.arange(5.0), unit="a.u.", timestamps=np.arange(5.0) * 0.1))
    if where == "processing":
        nwb.create_processing_module(name="behavior", description="b").add(events)
    else:
        nwb.add_acquisition(events)
    return nwb


def _epochs():
    from pynwb.behavior import BehavioralEpochs
    from pynwb.misc import IntervalSeries

    nwb = _nwb("epochs")
    epochs = BehavioralEpochs(name="BehavioralEpochs", interval_series=IntervalSeries(
        name="epochs_is", data=np.array([1, 0, 1], dtype=np.int8),
        timestamps=np.array([0.0, 1.0, 2.0])))
    nwb.create_processing_module(name="behavior", description="b").add(epochs)
    return nwb


def _fluorescence():
    from pynwb.ophys import Fluorescence, ImageSegmentation, OpticalChannel

    nwb = _nwb("ophys")
    device = nwb.create_device(name="scope")
    plane = nwb.create_imaging_plane(
        name="plane", optical_channel=OpticalChannel(name="green", description="g",
                                                     emission_lambda=520.0),
        description="p", device=device, excitation_lambda=488.0, indicator="GCaMP",
        location="V1", imaging_rate=30.0)
    seg = ImageSegmentation()
    rois = seg.create_plane_segmentation(name="PlaneSegmentation", description="rois",
                                         imaging_plane=plane)
    for k in range(2):
        mask = np.zeros((4, 4))
        mask[k, k] = 1.0
        rois.add_roi(image_mask=mask)
    region = rois.create_roi_table_region(region=[0, 1], description="both")
    fluor = Fluorescence(name="Fluorescence")
    fluor.create_roi_response_series(name="RoiResponse", data=np.arange(60.0).reshape(30, 2),
                                     rois=region, unit="n.a.", rate=30.0)
    ophys = nwb.create_processing_module(name="ophys", description="o")
    ophys.add(seg)
    ophys.add(fluor)
    return nwb


_READABLE = "readable"
_NO_RATE = "has no constant sampling rate"

#: Every container `inspect` reports, with the builder that plants it, the name `inspect` lists it
#: under and what `acquisition_channel` does with it: a value, or a refusal naming it and the reason.
CONTAINER_TABLE = {
    "acquisition LFP": (_acq_lfp, "probe_lfp", _READABLE),
    "processing LFP": (_proc_lfp, "LFP", _READABLE),
    "acquisition PupilTracking": (_acq_pupil, "PupilTracking", _READABLE),
    "processing EyeTracking": (_proc_eye, "EyeTracking", _READABLE),
    "processing Fluorescence": (_fluorescence, "Fluorescence", _READABLE),
    "processing BehavioralEvents": (lambda: _events("processing"), "BehavioralEvents", _NO_RATE),
    "acquisition BehavioralEvents": (lambda: _events("acquisition"), "BehavioralEvents", _NO_RATE),
    "processing BehavioralEpochs": (_epochs, "BehavioralEpochs", _NO_RATE),
}


class TestEveryContainerInspectReports:
    """One table covers every container `inspect` reports. The reader `inspect` names for a
    signal container is `acquisition_channel`; under each name `inspect` lists it, it either
    reads the container or refuses it with a message that names the container and the reason."""

    @pytest.mark.parametrize("row", list(CONTAINER_TABLE), ids=list(CONTAINER_TABLE))
    def test_each_reported_container_is_read_or_refused_by_name(self, tmp_path, row):
        build, container, outcome = CONTAINER_TABLE[row]
        path = _written(tmp_path / "row.nwb", build())
        info = inspect(path)
        reported = info["acquisitions"] + info["processing_continuous"]
        assert [e["name"] for e in reported] == [container]
        entry = reported[0]
        names = [entry["name"]]
        if "module" in entry:
            names.append(f"{entry['module']}/{entry['name']}")
        for name in names:
            if outcome == _READABLE:
                data, fs_hz = acquisition_channel(path, name=name, channel=0)
                assert data.ndim == 1 and data.size > 0 and fs_hz > 0
            else:
                with pytest.raises(NWBInspectError) as caught:
                    acquisition_channel(path, name=name, channel=0)
                assert container in str(caught.value), str(caught.value)
                assert outcome in str(caught.value), str(caught.value)


class TestChannelConversionLength:
    """A `channel_conversion` whose length is not the channel count is refused, not applied."""

    @pytest.mark.parametrize("shape, n_factors, n_channels", [
        ((50, 2), 3, 2), ((50,), 2, 1)], ids=["two-channels-three-factors",
                                              "one-channel-two-factors"])
    def test_a_length_that_is_not_the_channel_count_is_refused(
        self, tmp_path, shape, n_factors, n_channels
    ):
        from pynwb.ecephys import ElectricalSeries

        nwb = _nwb("cc")
        nwb.add_acquisition(ElectricalSeries(
            name="es", data=np.zeros(shape), electrodes=_region(nwb, n_channels), rate=1000.0,
            channel_conversion=[1.0] * n_factors))
        path = _written(tmp_path / "cc.nwb", nwb)
        with pytest.raises(ValueError, match=(
            f"stores {n_factors} channel_conversion factors for {n_channels} channels"
        )):
            acquisition_channel(path, name="es", channel=0)


class TestWarningsPointAtTheCaller:
    """The unit warning names both conversions it applies; both warnings name the caller's line."""

    def test_both_warnings_name_the_conversions_and_this_file(self, tmp_path):
        import sys
        import warnings
        from pathlib import Path

        from pynwb.ecephys import ElectricalSeries

        nwb = _nwb("warn")
        nwb.add_acquisition(ElectricalSeries(
            name="es", data=np.arange(100.0).reshape(50, 2), electrodes=_region(nwb, 2),
            rate=1000.0, conversion=1e-6, channel_conversion=[1.0, 2.0], starting_time=0.5))
        path = _written(tmp_path / "warn.nwb", nwb)
        with h5py.File(path, "r+") as f:
            f["acquisition/es/data"].attrs["unit"] = "uV"

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call_line = sys._getframe().f_lineno + 1
            acquisition_channel(path, name="es", channel=0)
        unit = [w for w in caught if issubclass(w.category, RuntimeWarning)]
        starting = [w for w in caught if "starting_time" in str(w.message)]
        assert len(unit) == 1 and len(starting) == 1, [str(w.message) for w in caught]
        for w in (unit[0], starting[0]):
            assert Path(w.filename).resolve() == Path(__file__).resolve(), w.filename
            assert w.lineno == call_line, (w.lineno, call_line)
        message = str(unit[0].message)
        assert "conversion=" in message and "channel_conversion=" in message, message


class TestABareNameTwoContainersHold:
    """A bare series name in two `/acquisition` containers is refused; the qualified name reads."""

    def test_the_bare_name_is_refused_and_the_qualified_name_reads(self, tmp_path):
        from pynwb.ecephys import LFP, ElectricalSeries

        nwb = _nwb("two")
        region = _region(nwb, 2)
        for container, offset in (("lfp_a", 0.0), ("lfp_b", 1e4)):
            nwb.add_acquisition(LFP(name=container, electrical_series=ElectricalSeries(
                name="lfp_series", data=np.arange(100.0).reshape(50, 2) + offset,
                electrodes=region, rate=500.0)))
        path = _written(tmp_path / "two.nwb", nwb)

        with pytest.raises(AmbiguousAcquisitionError, match="more than one container") as caught:
            resolve_acquisition(path, "lfp_series")
        assert "lfp_a/lfp_series" in str(caught.value)
        assert "lfp_b/lfp_series" in str(caught.value)
        with pytest.raises(AmbiguousAcquisitionError):
            acquisition_channel(path, name="lfp_series", channel=1)
        got, _ = acquisition_channel(path, name="lfp_b/lfp_series", channel=1)
        np.testing.assert_array_equal(got[:2], [10001.0, 10003.0])


class TestAnEmptyContainerIsRefused:
    """A container that holds no series and no data of its own is refused by name, with the
    wording it has always had."""

    @pytest.mark.parametrize("kind, wording", [
        ("LFP", "holds no electrical series"),
        ("FilteredEphys", "holds no electrical series"),
        ("EyeTracking", "holds no series"),
    ])
    def test_an_empty_container_names_itself_and_what_it_lacks(self, tmp_path, kind, wording):
        from pynwb.behavior import EyeTracking
        from pynwb.ecephys import FilteredEphys, LFP

        nwb = _nwb("empty")
        container = {"LFP": LFP, "FilteredEphys": FilteredEphys, "EyeTracking": EyeTracking}[kind]
        nwb.add_acquisition(container(name="empty"))
        path = _written(tmp_path / "empty.nwb", nwb)
        with pytest.raises(AcquisitionNotFoundError, match="Container 'empty'") as caught:
            acquisition_channel(path, name="empty", channel=0)
        assert wording in str(caught.value), str(caught.value)


class TestANonFiniteOrNonPositiveRateIsRefused:
    """A rate that is not finite and positive is refused by name, with the rate it carries."""

    @pytest.mark.parametrize("rate", [float("inf"), float("nan"), 0.0, -1.0])
    def test_acquisition_channel_refuses_the_series_and_names_its_rate(self, tmp_path, rate):
        from pynwb import TimeSeries

        nwb = _nwb("rate")
        nwb.add_acquisition(TimeSeries(name="ts", data=np.arange(50.0), unit="V", rate=1000.0))
        path = _written(tmp_path / "rate.nwb", nwb)
        with h5py.File(path, "r+") as f:
            f["acquisition/ts/starting_time"].attrs["rate"] = rate
        with pytest.raises(AcquisitionNotFoundError, match="not a finite positive rate") as caught:
            acquisition_channel(path, name="ts", channel=0)
        assert "'ts'" in str(caught.value), str(caught.value)
        assert repr(rate) in str(caught.value), str(caught.value)


class TestAnEmptyProcessingContainerIsNamed:
    """An empty electrical container under `processing/` is kept, so omitting the name names it
    and a name finds it, with the refusal it always had."""

    @pytest.mark.parametrize("kind", ["LFP", "FilteredEphys"])
    def test_the_empty_container_is_named_by_omission_and_by_name(self, tmp_path, kind):
        from pynwb.ecephys import FilteredEphys, LFP

        nwb = _nwb("empty-proc")
        container = {"LFP": LFP, "FilteredEphys": FilteredEphys}[kind]
        nwb.create_processing_module(name="ecephys", description="e").add(container(name=kind))
        path = _written(tmp_path / "empty_proc.nwb", nwb)

        assert resolve_acquisition(path) == kind
        with pytest.raises(AcquisitionNotFoundError, match=f"Container '{kind}' holds no electrical series"):
            acquisition_channel(path, channel=0)
        with pytest.raises(AcquisitionNotFoundError, match=f"Container 'ecephys/{kind}' holds no"):
            acquisition_channel(path, name=f"ecephys/{kind}", channel=0)

    def test_an_empty_behavior_container_is_named_but_not_chosen_by_omission(self, tmp_path):
        """An empty `EyeTracking` under `processing/` is refused by name with what it lacks. It
        is not a continuous series to choose when the name is omitted."""
        from pynwb.behavior import EyeTracking

        nwb = _nwb("empty-eye")
        nwb.create_processing_module(name="behavior", description="b").add(EyeTracking(name="Eye"))
        path = _written(tmp_path / "empty_eye.nwb", nwb)

        for name in ("Eye", "behavior/Eye"):
            with pytest.raises(AcquisitionNotFoundError, match=f"Container '{name}' holds no series"):
                acquisition_channel(path, name=name, channel=0)
        with pytest.raises(AcquisitionNotFoundError, match="No acquisitions or processing"):
            acquisition_channel(path, channel=0)


class TestTwoContainersOfOneNameInProcessing:
    """Two containers of one name under different processing modules: the bare name and an
    omitted name are refused, and the module-qualified name reads its own container."""

    def test_the_bare_and_omitted_names_are_refused_and_the_qualified_name_reads(self, tmp_path):
        from pynwb.ecephys import LFP, ElectricalSeries

        nwb = _nwb("two-lfp")
        region = _region(nwb, 2)
        for module, offset in (("probe0", 0.0), ("probe1", 1e4)):
            lfp = LFP(name="LFP", electrical_series=ElectricalSeries(
                name="lfp_series", data=np.arange(100.0).reshape(50, 2) + offset,
                electrodes=region, rate=500.0))
            nwb.create_processing_module(name=module, description=module).add(lfp)
        path = _written(tmp_path / "two_lfp.nwb", nwb)

        with pytest.raises(AmbiguousAcquisitionError) as caught:
            resolve_acquisition(path, "LFP")
        assert "probe0/LFP" in str(caught.value), str(caught.value)
        assert "probe1/LFP" in str(caught.value), str(caught.value)
        with pytest.raises(AmbiguousAcquisitionError):
            resolve_acquisition(path)
        got, _ = acquisition_channel(path, name="probe0/LFP", channel=1)
        np.testing.assert_array_equal(got[:2], [1.0, 3.0])


def _name_clash(order):
    """A behavior container named `Eye` and a processing LFP whose series is named `Eye`, in the
    module order given."""
    from pynwb.behavior import EyeTracking
    from pynwb.ecephys import LFP, ElectricalSeries

    nwb = _nwb("clash")
    region = _region(nwb, 2)
    eye = EyeTracking(name="Eye")
    eye.create_spatial_series(name="eye_xy", data=np.arange(20.0).reshape(10, 2), rate=1000.0,
                              reference_frame="screen", unit="pixels")
    lfp = LFP(name="probe", electrical_series=ElectricalSeries(
        name="Eye", data=np.arange(100.0).reshape(50, 2), electrodes=region, rate=500.0))
    modules = [("ecephys", lfp), ("behavior", eye)]
    if order == "behavior_first":
        modules.reverse()
    for mod_name, container in modules:
        nwb.create_processing_module(name=mod_name, description=mod_name).add(container)
    return nwb


class TestAContainerNamedLikeASeriesIsAmbiguous:
    """A container named like a series another container holds makes the bare name ambiguous,
    whichever module is listed first, and the qualified names read."""

    @pytest.mark.parametrize("order", ["ecephys_first", "behavior_first"])
    def test_the_bare_name_is_refused_and_both_qualified_names_are_listed(self, order):
        nwb = _name_clash(order)
        with pytest.raises(AmbiguousAcquisitionError, match="more than one processing entry") as caught:
            resolve_acquisition(nwb, "Eye")
        assert "behavior/Eye" in str(caught.value), str(caught.value)
        assert "ecephys/probe/Eye" in str(caught.value), str(caught.value)
        with pytest.raises(AmbiguousAcquisitionError):
            acquisition_channel(nwb, name="Eye", channel=1)
        got, fs_hz = acquisition_channel(nwb, name="behavior/Eye", channel=1)
        np.testing.assert_array_equal(got, np.arange(20.0).reshape(10, 2)[:, 1])
        assert fs_hz == 1000.0


def _series_starting_at(start_s):
    """An in-memory NWB file whose one ElectricalSeries starts at ``start_s`` seconds."""
    from datetime import datetime, timezone
    from pynwb import NWBFile
    from pynwb.ecephys import ElectricalSeries

    nwb = NWBFile(session_description="st", identifier="st",
                  session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc))
    dev = nwb.create_device(name="d")
    grp = nwb.create_electrode_group(name="g", description="g", location="x", device=dev)
    for _ in range(2):
        nwb.add_electrode(group=grp, location="x")
    region = nwb.create_electrode_table_region([0, 1], "all")
    nwb.add_acquisition(ElectricalSeries(name="lfp", data=np.zeros((100, 2)), electrodes=region,
                                         rate=1000.0, starting_time=start_s))
    return nwb


class TestStartingTime:
    """Sample 0 of an acquisition_channel array is at the series' starting_time, and event
    times are session times. jnwb reports the offset and warns; it does not shift anything.
    What would pass while the offset is lost: checking only a series that starts at 0."""

    @pytest.mark.parametrize("start_s", [0.0, 5.0])
    def test_inspect_reports_starting_time_in_both_forms(self, tmp_path, start_s):
        from pynwb import NWBHDF5IO
        nwb = _series_starting_at(start_s)
        in_memory = inspect(nwb)["acquisitions"][0]["starting_time"]
        path = tmp_path / "st.nwb"
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
        assert in_memory == inspect(path)["acquisitions"][0]["starting_time"] == start_s

    def test_a_nonzero_starting_time_warns_and_a_zero_one_does_not(self, tmp_path):
        import warnings
        from pynwb import NWBHDF5IO
        for start_s in (0.0, 5.0):
            path = tmp_path / f"st{start_s}.nwb"
            with NWBHDF5IO(str(path), "w") as io:
                io.write(_series_starting_at(start_s))
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                data, _ = acquisition_channel(path, name="lfp", channel=0)
            ours = [w for w in caught if "starting_time" in str(w.message)]
            assert data.shape == (100,)
            if start_s == 0.0:
                assert ours == [], [str(w.message) for w in ours]
            else:
                assert len(ours) == 1 and issubclass(ours[0].category, UserWarning)
                assert "5.0 s" in str(ours[0].message)
                assert "epoch_continuous" in str(ours[0].message)


def _described_columns():
    """An in-memory NWB file whose trials table has one documented column, `codes`, and
    one stored with an empty description, `blank`."""
    nwb = _series_starting_at(0.0)
    nwb.add_trial_column(name="codes", description="1 = face, 2 = house")
    nwb.add_trial_column(name="blank", description="")
    nwb.add_trial(start_time=0.1, stop_time=0.2, codes=1, blank=0)
    nwb.add_unit(spike_times=[0.1, 0.2])
    return nwb


class TestColumnDescriptions:
    """Each column record carries the stored NWB `description`: `""` when stored empty,
    `None` when the column stores none (`id`), never a filled-in text."""

    EXPECTED = {"blank": "", "codes": "1 = face, 2 = house", "id": None,
                "start_time": "Start time of epoch, in seconds",
                "stop_time": "Stop time of epoch, in seconds"}

    def _forms(self, tmp_path):
        from pynwb import NWBHDF5IO
        path = tmp_path / "described.nwb"
        with NWBHDF5IO(str(path), "w") as io:
            io.write(_described_columns())
        return {"file": inspect(path), "memory": inspect(_described_columns())}

    def test_interval_columns_report_the_stored_description(self, tmp_path):
        for form, result in self._forms(tmp_path).items():
            columns = result["interval_tables"][0]["columns"]
            got = {c["name"]: c["description"] for c in columns}
            assert got == self.EXPECTED, form

    def test_unit_and_electrode_columns_carry_the_key(self, tmp_path):
        for form, result in self._forms(tmp_path).items():
            units = {c["name"]: c["description"] for c in result["units"]["columns"]}
            assert units["id"] is None, form
            assert units["spike_times"] == "the spike times for each unit in seconds", form
            electrodes = {c["name"]: c["description"] for c in result["electrodes"]["columns"]}
            assert electrodes["id"] is None, form
            assert electrodes["location"], form


class TestNonnumericIntervalColumnsSurvive:
    """One nonnumeric interval column used to raise `TypeError` from `inspect` and make
    the whole file unreadable (GitHub issue #28).

    `np.isnan` is defined only for floats and complex, so a string, a compound row or any
    other scalar dtype raised instead of being sampled. The fix keeps the float-NaN-to-None
    reading and passes every other dtype through, so a malformed value stays visible as
    itself rather than becoming a plausible one.
    """

    def _with_columns(self, tmp_path, columns):
        """A written NWB file with extra raw columns added to its interval table, so the
        columns are read back exactly as a file on disk stores them."""
        path = tmp_path / "nonnumeric.nwb"
        write_synth_nwb(path, canonical_co_resident_options())
        with h5py.File(path, "r+") as handle:
            table = None
            for name in handle["intervals"].keys():
                if isinstance(handle["intervals"][name], h5py.Group):
                    table = handle["intervals"][name]
                    break
            assert table is not None, "the fixture must write an interval table"
            for name, values, dtype in columns:
                table.create_dataset(name, data=np.array(values, dtype=dtype))
        return path

    def _sampled(self, tmp_path, columns):
        tables = jnwb.inspect(self._with_columns(tmp_path, columns))["interval_tables"]
        return {c["name"]: c for t in tables for c in t["columns"]}

    def test_a_string_column_does_not_raise_and_matches_the_real_file(self, tmp_path):
        # The real DANDI:000253 file stores its text columns as variable-length UTF-8,
        # which h5py hands back as `bytes` inside an object array. Those elements are not
        # `np.generic`, so they never reached the broken `np.isnan` path; this test pins
        # that they keep being returned as stored.
        import h5py as _h5py

        got = self._sampled(
            tmp_path,
            [("label", ["alpha", "beta"], _h5py.string_dtype(encoding="utf-8"))],
        )
        assert [
            v.decode("utf-8") if isinstance(v, (bytes, np.bytes_)) else str(v)
            for v in got["label"]["sample_values"]
        ] == ["alpha", "beta"]

    def test_a_numeric_column_still_reads_its_own_values(self, tmp_path):
        got = self._sampled(tmp_path, [("count", [3, 1, 2], np.int32)])
        assert got["count"]["sample_values"] == [3, 1, 2]

    def test_a_bool_column_is_returned_as_bool(self, tmp_path):
        got = self._sampled(tmp_path, [("flag", [True, False, True], np.bool_)])
        assert got["flag"]["sample_values"] == [True, False, True]

    def test_a_float_nan_still_reads_as_none(self, tmp_path):
        """The one case the old code got right, kept by the fix."""
        got = self._sampled(tmp_path, [("score", [1.5, np.nan], np.float64)])
        assert got["score"]["sample_values"] == [1.5, None]

    def test_a_compound_row_does_not_raise(self, tmp_path):
        """A compound dtype is the shape that raised most directly: `np.isnan` cannot
        decide anything about a whole struct row."""
        compound = np.dtype([("seconds", np.int64), ("fraction", np.float64)])
        rows = np.array([(10, 0.5), (20, np.nan)], dtype=compound)
        got = self._sampled(tmp_path, [("stamp", list(rows), compound)])
        assert len(got["stamp"]["sample_values"]) == 2
        # `.item()` on a void scalar returns a plain tuple, not a named row.
        assert got["stamp"]["sample_values"][0][0] == 10
        assert np.isnan(got["stamp"]["sample_values"][1][1])

    def test_a_non_nan_nonfinite_float_is_not_coerced_to_none(self, tmp_path):
        """Only NaN reads as None. An infinity is not NaN and must pass through as
        itself, not be folded into the missing-value case."""
        got = self._sampled(tmp_path, [("score", [1.5, np.inf], np.float64)])
        assert got["score"]["sample_values"] == [1.5, np.inf]

    def test_an_empty_string_column_does_not_raise(self, tmp_path):
        import h5py as _h5py

        got = self._sampled(
            tmp_path, [("label", ["", "beta"], _h5py.string_dtype(encoding="utf-8"))]
        )
        assert [
            v.decode("utf-8") if isinstance(v, (bytes, np.bytes_)) else str(v)
            for v in got["label"]["sample_values"]
        ] == ["", "beta"]


class TestNoConstantRateNamesTheSeries:
    """A series stored with explicit timestamps is refused by name, and the message says why."""

    def test_the_refusal_names_the_series_and_the_timestamps(self, tmp_path):
        from pynwb import TimeSeries

        nwb = _nwb("stamped")
        nwb.add_acquisition(TimeSeries(name="stamped_es", data=np.zeros((50, 2)), unit="a.u.",
                                       timestamps=np.arange(50) * 0.01))
        path = _written(tmp_path / "stamped.nwb", nwb)
        with pytest.raises(AcquisitionNotFoundError) as info:
            acquisition_channel(path, name="stamped_es", channel=0)
        assert type(info.value) is AcquisitionNotFoundError
        message = str(info.value)
        assert "'stamped_es'" in message
        assert "stores explicit timestamps" in message
        assert "Epoching by sample index needs a constant rate" in message


class TestContainerTypeContradictionHeadlines:
    """A unit-scale contradiction and a type contradiction each open the warning with their own
    first sentence, so a reader can tell which of the two a file has."""

    @staticmethod
    def _first_sentence(path):
        import warnings

        from jnwb.nwb_io import ContainerTypeContradictionWarning

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            inspect(path)
        found = [str(w.message) for w in caught
                 if issubclass(w.category, ContainerTypeContradictionWarning)]
        assert len(found) == 1, found
        return found[0].split(". ", 1)[0]

    @staticmethod
    def _lfp_file(tmp_path, name):
        from pynwb.ecephys import LFP, ElectricalSeries

        nwb = _nwb(name)
        region = _region(nwb, 2)
        nwb.add_acquisition(LFP(name="probe_lfp", electrical_series=ElectricalSeries(
            name="lfp_uv", data=np.zeros((50, 2), dtype=np.int16), electrodes=region,
            rate=1000.0)))
        return _written(tmp_path / f"{name}.nwb", nwb)

    def _both_cases(self, tmp_path):
        unit_path = self._lfp_file(tmp_path, "unit_case")
        with h5py.File(unit_path, "r+") as f:
            f["acquisition/probe_lfp/lfp_uv/data"].attrs["unit"] = "uV"
        type_path = self._lfp_file(tmp_path, "type_case")
        with h5py.File(type_path, "r+") as f:
            del f["acquisition/probe_lfp/lfp_uv"].attrs["neurodata_type"]
        return self._first_sentence(unit_path), self._first_sentence(type_path)

    def test_a_unit_scale_contradiction_names_the_unit(self, tmp_path):
        unit_head, type_head = self._both_cases(tmp_path)
        assert unit_head != type_head
        assert unit_head.endswith(
            "declared unit disagrees with the unit the NWB schema fixes for the declared "
            "neurodata_type")
        assert "declared type disagrees" not in unit_head

    def test_a_type_contradiction_names_the_type(self, tmp_path):
        unit_head, type_head = self._both_cases(tmp_path)
        assert unit_head != type_head
        assert type_head.endswith("declared type disagrees with what the file stores")
        assert "declared unit disagrees" not in type_head


class TestPackagingLabelIsTheWrappedOne:
    """A container that wraps its series is `wrapped`, an LFP is `lfp_wrapped`, and a series with
    its own data is `direct`; a file and the object model it was written from agree."""

    def test_the_same_label_from_a_file_and_from_memory(self, tmp_path):
        expected = {
            "EyeTracking": "wrapped",
            "BehavioralEvents": "wrapped",
            "BehavioralEpochs": "wrapped",
            "probe_lfp": "lfp_wrapped",
            "direct": "direct",
        }

        def labels(info):
            return {e["name"]: e["packaging"]
                    for e in info["acquisitions"] + info["processing_continuous"]}

        path = _written(tmp_path / "mixed.nwb", _mixed())
        assert labels(inspect(path)) == expected
        assert labels(inspect(_mixed())) == expected
