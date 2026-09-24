"""`inspect(path)` and `inspect(NWBFile)` were two implementations, two schemas.

An h5py walk and a pynwb walk, written independently, with nothing holding them to the
same answer. For one file they disagreed on which keys exist (`data_path`, `layout`),
on which columns a table has (`id` present from the file, absent from the object) and on
what a column's dtype is (`object` vs `str`).

Underneath that, `_find_series_leaf` walked a container's whole subtree with
`visititems` and took the first `data` leaf and the first `rate` leaf *independently*.
On an `LFP` container holding `lfp_alpha` at 1000 Hz and `lfp_beta` at 500 Hz:

    inspect(path) -> rate_hz 500.0, data_path .../lfp_alpha/data, data_shape [100, 4]
    inspect(nwb)  -> rate_hz 1000.0
    acquisition_channel(name="LFP") -> lfp_alpha, 1000 Hz

Three answers for one object, one of which paired `lfp_beta`'s sampling rate with
`lfp_alpha`'s array -- a rate that belongs to different samples, which is how a spectrum
comes out shifted by a factor of two with nothing to show for it.

And `acquisition_channel(name="shared")` resolved an acquisition/processing name
collision by the order of two `if` statements, silently.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

import jnwb


def _build(two_series: bool = False, collide: bool = False):
    import pynwb

    nwb = pynwb.NWBFile(session_description="one schema", identifier="i39",
                        session_start_time=datetime.now(timezone.utc))
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(name="g", description="d", location="V1",
                                       device=device)
    for i in range(4):
        nwb.add_electrode(x=0.0, y=float(i), z=0.0, imp=0.0, location="V1",
                          filtering="none", group=group)

    def region():
        return nwb.create_electrode_table_region(list(range(4)), "all")

    nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
        name="raw", data=np.zeros((200, 4)), electrodes=region(), rate=2000.0))

    series = [pynwb.ecephys.ElectricalSeries(
        name="lfp_alpha", data=np.zeros((100, 4)), electrodes=region(), rate=1000.0)]
    if two_series:
        series.append(pynwb.ecephys.ElectricalSeries(
            name="lfp_beta", data=np.zeros((50, 4)), electrodes=region(), rate=500.0))
    module = nwb.create_processing_module(name="ecephys", description="d")
    module.add(pynwb.ecephys.LFP(electrical_series=series))

    nwb.add_trial_column(name="codes", description="labels")
    nwb.add_trial(start_time=0.1, stop_time=0.4, codes="a")
    nwb.add_trial(start_time=0.6, stop_time=0.9, codes="b")
    nwb.add_unit(spike_times=[0.1, 0.2])
    nwb.add_unit(spike_times=[0.3])

    if collide:
        nwb.add_acquisition(pynwb.ecephys.ElectricalSeries(
            name="shared", data=np.zeros((10, 4)), electrodes=region(), rate=100.0))
        module.add(pynwb.ecephys.ElectricalSeries(
            name="shared", data=np.zeros((20, 4)), electrodes=region(), rate=200.0))
    return nwb


def _write(tmp_path, filename, **kwargs):
    import pynwb

    nwb = _build(**kwargs)
    path = tmp_path / filename
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return str(path)


def _inspect_both(path):
    import pynwb

    from_path = jnwb.inspect(path)
    with pynwb.NWBHDF5IO(path, "r") as io:
        from_object = jnwb.inspect(io.read())
    return from_path, from_object


class TestTheTwoCallFormsAgree:
    """The discriminator: one file, one answer, whichever way you ask."""

    @pytest.mark.parametrize("two_series", [False, True])
    def test_the_dicts_are_equal(self, tmp_path, two_series):
        path = _write(tmp_path, f"eq{int(two_series)}.nwb", two_series=two_series)
        from_path, from_object = _inspect_both(path)
        assert from_path == from_object

    def test_every_section_is_equal_section_by_section(self, tmp_path):
        """Stated per section so a failure says which one drifted."""
        path = _write(tmp_path, "sections.nwb")
        from_path, from_object = _inspect_both(path)
        for section in ("session", "acquisitions", "processing_continuous",
                        "electrodes", "units", "interval_tables", "time_unit"):
            assert from_path[section] == from_object[section], section

    def test_the_keys_that_only_one_form_used_to_have(self, tmp_path):
        """`data_path` and `layout` existed only on the file side; `series` is new and
        must exist on both."""
        path = _write(tmp_path, "keys.nwb")
        from_path, from_object = _inspect_both(path)
        for form in (from_path, from_object):
            entry = form["acquisitions"][0]
            for key in ("data_path", "layout", "series"):
                assert key in entry, (key, sorted(entry))

    def test_an_interval_table_reports_its_id_column_both_ways(self, tmp_path):
        """`to_dataframe()` makes `id` the index, so the object form reported one fewer
        column than the file form for the same table."""
        path = _write(tmp_path, "intervals.nwb")
        for form in _inspect_both(path):
            names = [c["name"] for c in form["interval_tables"][0]["columns"]]
            assert names == ["codes", "id", "start_time", "stop_time"]

    def test_column_dtypes_agree(self, tmp_path):
        """`codes` was `object` from the file and `str` from the object."""
        path = _write(tmp_path, "dtypes.nwb")
        from_path, from_object = _inspect_both(path)
        assert (from_path["interval_tables"][0]["columns"]
                == from_object["interval_tables"][0]["columns"])
        assert from_path["units"]["columns"] == from_object["units"]["columns"]


class TestAContainerHoldingSeveralSeries:
    """The rate and the array used to come from different places."""

    def test_the_rate_is_not_borrowed_from_another_series(self, tmp_path):
        """`inspect(path)` reported `rate_hz: 500.0` beside `lfp_alpha`'s shape and
        path. Whatever is reported now, it is not one series' rate with another's data."""
        path = _write(tmp_path, "two.nwb", two_series=True)
        entry = jnwb.inspect(path)["processing_continuous"][0]
        assert entry["rate_hz"] is None
        assert entry["data_path"] is None
        assert entry["data_shape"] is None

    def test_the_container_says_which_series_it_holds(self, tmp_path):
        path = _write(tmp_path, "two_named.nwb", two_series=True)
        entry = jnwb.inspect(path)["processing_continuous"][0]
        assert entry["name"] == "LFP"
        assert entry["series"] == ["lfp_alpha", "lfp_beta"]

    def test_reading_the_container_refuses_and_names_the_series(self, tmp_path):
        path = _write(tmp_path, "two_read.nwb", two_series=True)
        with pytest.raises(jnwb.AmbiguousAcquisitionError) as exc:
            jnwb.acquisition_channel(path, name="LFP", channel=0)
        message = str(exc.value)
        assert "lfp_alpha" in message and "lfp_beta" in message

    def test_the_refusal_is_actionable(self, tmp_path):
        """Naming a series must work, or the refusal is a dead end. Each one keeps its
        own rate and its own length."""
        path = _write(tmp_path, "two_pick.nwb", two_series=True)
        alpha, alpha_fs = jnwb.acquisition_channel(path, name="lfp_alpha", channel=0)
        beta, beta_fs = jnwb.acquisition_channel(path, name="lfp_beta", channel=0)
        assert (len(alpha), alpha_fs) == (100, 1000.0)
        assert (len(beta), beta_fs) == (50, 500.0)

    def test_a_single_series_container_still_answers(self, tmp_path):
        """The refusal is for ambiguity, not for wrapping."""
        path = _write(tmp_path, "one.nwb")
        entry = jnwb.inspect(path)["processing_continuous"][0]
        assert entry["name"] == "LFP"
        assert entry["series"] == ["lfp_alpha"]
        assert entry["rate_hz"] == 1000.0
        assert entry["data_path"] == "/processing/ecephys/LFP/lfp_alpha/data"
        data, rate = jnwb.acquisition_channel(path, name="LFP", channel=0)
        assert (len(data), rate) == (100, 1000.0)


class TestANameInTwoPlaces:

    def test_a_collision_is_refused_rather_than_resolved_by_precedence(self, tmp_path):
        """It used to return /acquisition/shared, decided by which `if` came first."""
        path = _write(tmp_path, "collide.nwb", collide=True)
        with pytest.raises(jnwb.AmbiguousAcquisitionError) as exc:
            jnwb.acquisition_channel(path, name="shared", channel=0)
        message = str(exc.value)
        assert "/acquisition/shared" in message
        assert "ecephys/shared" in message

    def test_resolve_acquisition_refuses_the_same_collision(self, tmp_path):
        path = _write(tmp_path, "collide2.nwb", collide=True)
        with pytest.raises(jnwb.AmbiguousAcquisitionError):
            jnwb.resolve_acquisition(path, name="shared")

    def test_a_name_in_one_place_only_still_resolves(self, tmp_path):
        path = _write(tmp_path, "nocollide.nwb", collide=True)
        assert jnwb.resolve_acquisition(path, name="raw") == "raw"
        data, rate = jnwb.acquisition_channel(path, name="raw", channel=0)
        assert (len(data), rate) == (200, 2000.0)


class TestTheSeriesWalkerItself:

    def test_data_and_rate_come_from_the_same_group(self, tmp_path):
        """Unit-level statement of the defect: one member per series, each carrying its
        own rate."""
        import h5py

        from jnwb.nwb_inspect import _series_members

        path = _write(tmp_path, "members.nwb", two_series=True)
        with h5py.File(path, "r") as handle:
            members = _series_members(handle["/processing/ecephys/LFP"])
            by_name = {name: (rel, ds.shape, rate) for name, rel, ds, rate in members}
        assert by_name["lfp_alpha"] == ("lfp_alpha/data", (100, 4), 1000.0)
        assert by_name["lfp_beta"] == ("lfp_beta/data", (50, 4), 500.0)

    def test_a_direct_series_is_one_unnamed_member(self, tmp_path):
        import h5py

        from jnwb.nwb_inspect import _series_members

        path = _write(tmp_path, "direct.nwb")
        with h5py.File(path, "r") as handle:
            members = _series_members(handle["/acquisition/raw"])
            assert len(members) == 1
            name, relpath, ds, rate = members[0]
            assert (name, relpath, ds.shape, rate) == (None, "data", (200, 4), 2000.0)


class TestAnObjectWithNoFileBehindIt:
    """A pure in-memory NWBFile has no dtypes-on-disk to report, but it reports the same
    schema rather than a different one."""

    def test_the_schema_is_the_same_key_set(self, tmp_path):
        in_memory = _build()
        written = _write(tmp_path, "schema.nwb")
        from_memory = jnwb.inspect(in_memory)
        from_file = jnwb.inspect(written)
        assert sorted(from_memory) == sorted(from_file)
        assert (sorted(from_memory["acquisitions"][0])
                == sorted(from_file["acquisitions"][0]))
        assert sorted(from_memory["units"]) == sorted(from_file["units"])
        assert ([c["name"] for c in from_memory["interval_tables"][0]["columns"]]
                == ["codes", "id", "start_time", "stop_time"])

    def test_it_refuses_an_ambiguous_container_too(self):
        entry = jnwb.inspect(_build(two_series=True))["processing_continuous"][0]
        assert entry["series"] == ["lfp_alpha", "lfp_beta"]
        assert entry["rate_hz"] is None
