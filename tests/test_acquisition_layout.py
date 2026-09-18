"""05-38: acquisition_channel sliced axis 1 whatever orientation the file was in.

The channel axis was decided by ``shape[0] >= shape[1]`` -- whichever side is longer --
and ``acquisition_channel`` did not consult even that. It always sliced ``data[:, channel]``
and bounds-checked ``shape[1]``.

Reproduced on a file written with plain pynwb: a (64, 1000) ElectricalSeries with 64
electrodes returned, for ``channel=0``, the 64 samples ``data[:, 0]`` -- one instant
across all channels -- labelled a 1000 Hz trace. ``channel=999`` returned another such
slice instead of raising, and ``channel=1000`` raised "out of range ... with 1000
channels" for a file with 64 of them. pynwb itself warns on write that such data "is
oriented incorrectly", so this orientation is a thing real files are in.

The arbiter is the series' own electrode region, not the longer side and not the whole
electrode table -- a series may cover a subset of a 384-channel probe. Where the electrode
count settles nothing (neither dimension matches, or both do) the layout is ``ambiguous``
and reading a channel raises, because a guess there returns a cross-channel slice as a
time course.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

import jnwb
from jnwb.nwb_inspect import (
    AMBIGUOUS_LAYOUT,
    CHANNEL_BY_TIME,
    TIME_BY_CHANNEL,
    _resolve_layout,
)


def _write(path, data, n_electrodes, name="es"):
    """An ElectricalSeries written with plain pynwb and nothing else."""
    import pynwb

    nwb = pynwb.NWBFile(session_description="layout", identifier="lay-1",
                        session_start_time=datetime.now(timezone.utc))
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="g", description="d", location="V1",
                                       device=device)
    for i in range(n_electrodes):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=0.0, location="V1",
                          filtering="none", group=group)
    region = nwb.create_electrode_table_region(list(range(n_electrodes)), "all")
    nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
        name=name, data=np.asarray(data), electrodes=region, rate=1000.0))
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return str(path)


CHANNEL_MAJOR = np.arange(64 * 1000, dtype=float).reshape(64, 1000)
TIME_MAJOR = np.arange(1000 * 64, dtype=float).reshape(1000, 64)


@pytest.fixture
def channel_major(tmp_path):
    """64 channels x 1000 samples. Wider than tall, which is what misled the heuristic."""
    return _write(tmp_path / "channel_major.nwb", CHANNEL_MAJOR, 64)


@pytest.fixture
def time_major(tmp_path):
    """1000 samples x 64 channels: the orientation that always worked."""
    return _write(tmp_path / "time_major.nwb", TIME_MAJOR, 64)


class TestAChannelMajorFileReturnsTheChannel:
    """The defect: a whole recording read out transposed, silently."""

    def test_channel_zero_is_the_first_row_not_the_first_column(self, channel_major):
        data, rate = jnwb.acquisition_channel(channel_major, channel=0)
        np.testing.assert_allclose(data, CHANNEL_MAJOR[0, :])
        assert rate == 1000.0

    def test_the_last_channel_is_the_last_row(self, channel_major):
        data, _ = jnwb.acquisition_channel(channel_major, channel=63)
        np.testing.assert_allclose(data, CHANNEL_MAJOR[63, :])

    def test_the_trace_is_as_long_as_the_recording_not_as_wide_as_the_probe(
            self, channel_major):
        """Before the repair this was 64 samples: one instant, called a trace."""
        data, _ = jnwb.acquisition_channel(channel_major, channel=0)
        assert len(data) == 1000

    def test_every_channel_round_trips(self, channel_major):
        for ch in (0, 1, 17, 62, 63):
            data, _ = jnwb.acquisition_channel(channel_major, channel=ch)
            np.testing.assert_allclose(data, CHANNEL_MAJOR[ch, :])

    def test_the_bound_is_the_channel_count_not_the_sample_count(self, channel_major):
        """It used to accept channel=999 and reject channel=1000 "with 1000 channels"."""
        with pytest.raises(jnwb.ChannelIndexError) as exc:
            jnwb.acquisition_channel(channel_major, channel=64)
        assert "64 channels" in str(exc.value)
        with pytest.raises(jnwb.ChannelIndexError):
            jnwb.acquisition_channel(channel_major, channel=999)

    def test_inspect_reports_the_orientation(self, channel_major):
        acq = jnwb.inspect(channel_major)["acquisitions"][0]
        assert acq["layout"] == CHANNEL_BY_TIME


class TestATimeMajorFileIsUnchanged:
    """The orientation that already worked must keep working, by the electrode count
    rather than by being taller than wide."""

    def test_channel_zero_is_the_first_column(self, time_major):
        data, rate = jnwb.acquisition_channel(time_major, channel=0)
        np.testing.assert_allclose(data, TIME_MAJOR[:, 0])
        assert rate == 1000.0

    def test_every_channel_round_trips(self, time_major):
        for ch in (0, 1, 17, 62, 63):
            data, _ = jnwb.acquisition_channel(time_major, channel=ch)
            np.testing.assert_allclose(data, TIME_MAJOR[:, ch])

    def test_the_bound_is_still_the_channel_count(self, time_major):
        with pytest.raises(jnwb.ChannelIndexError) as exc:
            jnwb.acquisition_channel(time_major, channel=64)
        assert "64 channels" in str(exc.value)

    def test_inspect_reports_the_orientation(self, time_major):
        assert jnwb.inspect(time_major)["acquisitions"][0]["layout"] == TIME_BY_CHANNEL


class TestTheElectrodeCountIsTheArbiterNotTheLongerSide:

    def test_a_short_wide_recording_is_read_by_its_electrode_count(self, tmp_path):
        """50 samples x 100 channels. Wider than tall, so the heuristic said
        ``channel_by_time`` while the same inspect dict carried 100 electrodes."""
        data = np.arange(50 * 100, dtype=float).reshape(50, 100)
        path = _write(tmp_path / "short_wide.nwb", data, 100)
        assert jnwb.inspect(path)["acquisitions"][0]["layout"] == TIME_BY_CHANNEL
        got, _ = jnwb.acquisition_channel(path, channel=7)
        np.testing.assert_allclose(got, data[:, 7])

    def test_a_tall_narrow_channel_major_recording_is_read_by_its_electrode_count(
            self, tmp_path):
        """1000 channels x 50 samples: taller than wide, so the heuristic said
        ``time_by_channel``, which is backwards."""
        data = np.arange(1000 * 50, dtype=float).reshape(1000, 50)
        path = _write(tmp_path / "tall_narrow.nwb", data, 1000)
        assert jnwb.inspect(path)["acquisitions"][0]["layout"] == CHANNEL_BY_TIME
        got, _ = jnwb.acquisition_channel(path, channel=7)
        np.testing.assert_allclose(got, data[7, :])


class TestWhatTheElectrodeCountCannotSettle:

    def test_a_square_array_is_ambiguous(self, tmp_path):
        """64 x 64 with 64 electrodes. Both dimensions match, so nothing decides."""
        data = np.arange(64 * 64, dtype=float).reshape(64, 64)
        path = _write(tmp_path / "square.nwb", data, 64)
        assert jnwb.inspect(path)["acquisitions"][0]["layout"] == AMBIGUOUS_LAYOUT
        with pytest.raises(jnwb.AmbiguousLayoutError) as exc:
            jnwb.acquisition_channel(path, channel=0)
        assert "64" in str(exc.value)

    def test_a_shape_matching_neither_dimension_is_ambiguous(self, tmp_path):
        """10 x 20 with 5 electrodes: the file is internally inconsistent, and
        returning either axis would be a guess."""
        data = np.arange(10 * 20, dtype=float).reshape(10, 20)
        path = _write(tmp_path / "mismatch.nwb", data, 5)
        assert jnwb.inspect(path)["acquisitions"][0]["layout"] == AMBIGUOUS_LAYOUT
        with pytest.raises(jnwb.AmbiguousLayoutError):
            jnwb.acquisition_channel(path, channel=0)

    def test_the_ambiguous_error_names_the_shape_and_the_electrode_count(self, tmp_path):
        data = np.arange(10 * 20, dtype=float).reshape(10, 20)
        path = _write(tmp_path / "mismatch2.nwb", data, 5)
        with pytest.raises(jnwb.AmbiguousLayoutError) as exc:
            jnwb.acquisition_channel(path, channel=0)
        message = str(exc.value)
        assert "(10, 20)" in message
        assert "5 electrodes" in message

    def test_ambiguity_is_refused_not_rounded_off_to_a_plausible_trace(self, tmp_path):
        """The point of the error: a guess here returns a cross-channel slice with the
        right dtype, the right length and the wrong meaning."""
        data = np.arange(64 * 64, dtype=float).reshape(64, 64)
        path = _write(tmp_path / "square2.nwb", data, 64)
        with pytest.raises(jnwb.AmbiguousLayoutError):
            jnwb.acquisition_channel(path, channel=3)

    def test_the_ambiguous_error_is_an_inspect_error(self):
        assert issubclass(jnwb.AmbiguousLayoutError, jnwb.NWBInspectError)


class TestTheResolverItself:
    """Unit-level, so the table of cases is readable without writing eight files."""

    @pytest.mark.parametrize("shape,n,layout,basis", [
        ((1000, 64), 64, TIME_BY_CHANNEL, "electrode_count"),
        ((64, 1000), 64, CHANNEL_BY_TIME, "electrode_count"),
        ((50, 100), 100, TIME_BY_CHANNEL, "electrode_count"),
        ((1000, 50), 1000, CHANNEL_BY_TIME, "electrode_count"),
        ((64, 64), 64, AMBIGUOUS_LAYOUT, "electrode_count"),
        ((10, 20), 5, AMBIGUOUS_LAYOUT, "electrode_count"),
    ])
    def test_the_electrode_count_decides_when_it_can(self, shape, n, layout, basis):
        assert _resolve_layout(shape, n) == (layout, basis)

    @pytest.mark.parametrize("shape,layout", [
        ((1000, 64), TIME_BY_CHANNEL),
        ((64, 1000), CHANNEL_BY_TIME),
        ((64, 64), TIME_BY_CHANNEL),
    ])
    def test_without_an_electrode_count_the_shape_guess_is_all_there_is(
            self, shape, layout):
        """Unchanged behaviour where there is nothing to arbitrate with -- but the basis
        records that it is a guess rather than a reading."""
        assert _resolve_layout(shape, None) == (layout, "shape")

    def test_a_zero_length_electrode_region_is_not_an_arbiter(self):
        assert _resolve_layout((64, 1000), 0) == (CHANNEL_BY_TIME, "shape")


class TestOneDimensionalSeriesAreUntouched:

    def test_a_1d_series_still_reads_and_still_rejects_channel_one(self, tmp_path):
        data = np.arange(500, dtype=float)
        path = _write(tmp_path / "one_d.nwb", data, 1)
        got, rate = jnwb.acquisition_channel(path, channel=0)
        np.testing.assert_allclose(got, data)
        assert rate == 1000.0
        with pytest.raises(jnwb.ChannelIndexError):
            jnwb.acquisition_channel(path, channel=1)


def _write_processing_lfp(path, data, n_electrodes):
    """A channel-major LFP inside processing/ecephys, written with plain pynwb."""
    import pynwb

    nwb = pynwb.NWBFile(session_description="layout", identifier="lay-2",
                        session_start_time=datetime.now(timezone.utc))
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="g", description="d", location="V1",
                                       device=device)
    for i in range(n_electrodes):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=0.0, location="V1",
                          filtering="none", group=group)
    region = nwb.create_electrode_table_region(list(range(n_electrodes)), "all")
    lfp = pynwb.ecephys.LFP(electrical_series=pynwb.ecephys.ElectricalSeries(
        name="lfp_series", data=np.asarray(data), electrodes=region, rate=1000.0))
    nwb.create_processing_module(name="ecephys", description="d").add(lfp)
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return nwb, str(path)


class TestProcessingModulesGetTheSameArbiter:
    """The layout is decided in three places -- the h5py acquisition walk, the h5py
    processing walk and the pynwb processing walk -- and a repair to one of them is not
    a repair to the others. Mutation testing found these two uncovered."""

    # 32 samples x 400 channels. Chosen so the electrode count and the old heuristic
    # disagree: `shape[0] >= shape[1]` is false here, so the heuristic says
    # `channel_by_time`, and the 400 electrodes say `time_by_channel`. A shape where
    # they happen to agree cannot tell the two implementations apart.
    WIDE = np.arange(32 * 400, dtype=float).reshape(32, 400)
    CHANNEL_MAJOR = np.arange(32 * 400, dtype=float).reshape(400, 32).T.copy()

    def test_the_h5py_path_reads_the_electrode_count(self, tmp_path):
        _, path = _write_processing_lfp(tmp_path / "proc.nwb", self.WIDE, 400)
        entry = jnwb.inspect(path)["processing_continuous"][0]
        assert entry["data_shape"] == [32, 400]
        assert entry["layout"] == TIME_BY_CHANNEL

    def test_the_pynwb_path_reads_the_electrode_count(self, tmp_path):
        nwb, _ = _write_processing_lfp(tmp_path / "proc2.nwb", self.WIDE, 400)
        entry = jnwb.inspect(nwb)["processing_continuous"][0]
        assert entry["data_shape"] == [32, 400]
        assert entry["layout"] == TIME_BY_CHANNEL

    def test_both_paths_agree_on_the_same_file(self, tmp_path):
        """Whichever walk reports it, the answer comes from the same arbiter."""
        nwb, path = _write_processing_lfp(tmp_path / "proc3.nwb", self.WIDE, 400)
        assert (jnwb.inspect(path)["processing_continuous"][0]["layout"]
                == jnwb.inspect(nwb)["processing_continuous"][0]["layout"])

    def test_a_channel_major_processing_channel_round_trips(self, tmp_path):
        _, path = _write_processing_lfp(tmp_path / "proc4.nwb", self.CHANNEL_MAJOR, 32)
        assert jnwb.inspect(path)["processing_continuous"][0]["layout"] == CHANNEL_BY_TIME
        got, rate = jnwb.acquisition_channel(path, channel=5)
        np.testing.assert_allclose(got, self.CHANNEL_MAJOR[5, :])
        assert rate == 1000.0
