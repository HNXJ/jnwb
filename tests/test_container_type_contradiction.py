"""A container whose declared `neurodata_type` contradicts its contents warns; one that agrees does not.

Ruled 2026-09-20 (06-84): jnwb warns and proceeds. Refusing would make jnwb the arbiter of a
corpus's metadata and would make a measured 9 of 22 real sessions unreadable without an override;
indifference would let a container declared `ElectricalSeries` hand back an int16 array that is
not extracellular voltage, substituting a signal class silently across a jnwb boundary.

Every assertion here is written against the failure mode that the warning carries no information.
A test that only asserts `pytest.warns(ContainerTypeContradictionWarning)` passes for a warning
raised about a different container, and passes for an implementation that warns on everything, so
the discriminating assertion is the exact *set* of containers warned about in one `inspect`, plus
the *content* of each message.
"""
from __future__ import annotations

import warnings
from datetime import datetime, timezone

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO, NWBFile, TimeSeries
from pynwb.ecephys import LFP, ElectricalSeries

import jnwb
from jnwb.nwb_io import ContainerTypeContradictionWarning

N_ELECTRODES = 4


def _base_file(identifier: str) -> NWBFile:
    nwbfile = NWBFile(
        session_description="contradiction fixture",
        identifier=identifier,
        session_start_time=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    device = nwbfile.create_device(name="dev")
    group = nwbfile.create_electrode_group(
        name="eg", description="d", location="loc", device=device
    )
    for _ in range(N_ELECTRODES):
        nwbfile.add_electrode(group=group, location="loc")
    return nwbfile


def _electrical(nwbfile: NWBFile, name: str, rate: float = 30000.0) -> ElectricalSeries:
    return ElectricalSeries(
        name=name,
        data=np.zeros((100, N_ELECTRODES), dtype=np.int16),
        electrodes=nwbfile.create_electrode_table_region(list(range(N_ELECTRODES)), "all"),
        rate=rate,
    )


def _write(nwbfile: NWBFile, path) -> None:
    with warnings.catch_warnings():
        # hdmf warns about the electrode region's ancestry while writing the fixture. That is
        # the fixture's own construction, not the behaviour under test.
        warnings.simplefilter("ignore")
        with NWBHDF5IO(str(path), "w") as io:
            io.write(nwbfile)


@pytest.fixture(scope="module")
def corpus_shapes(tmp_path_factory) -> str:
    """All three measured corpus shapes, plus a consistent control, in one file.

    The three shapes P-54 measured across 22 real sessions: a spike-train container declared
    `ElectricalSeries` (9 sessions, one of them int16), the same logical series declared
    `TimeSeries` (12), and one omitting `neurodata_type` entirely (1).

    The declared type is rewritten on disk after pynwb has written a valid file, because that is
    the only way to produce the measured shapes: pynwb refuses to construct an `ElectricalSeries`
    without an electrode region, and substitutes the schema's fixed `unit` on read.
    """
    path = tmp_path_factory.mktemp("ctc") / "corpus_shapes.nwb"
    nwbfile = _base_file("corpus_shapes")
    nwbfile.add_acquisition(_electrical(nwbfile, "mistyped_es"))
    nwbfile.add_acquisition(_electrical(nwbfile, "consistent_es"))
    nwbfile.add_acquisition(
        TimeSeries(name="consistent_ts", data=np.zeros(100, dtype=np.int16),
                   unit="n.a.", rate=30000.0)
    )
    nwbfile.add_acquisition(
        TimeSeries(name="untyped", data=np.zeros(100, dtype=np.int16),
                   unit="n.a.", rate=30000.0)
    )
    _write(nwbfile, path)

    with h5py.File(path, "r+") as handle:
        # A spike-train container wearing the ElectricalSeries label: the schema fixes that
        # type's data unit to volts, and this one stores counts.
        handle["acquisition/mistyped_es/data"].attrs["unit"] = "n.a."
        del handle["acquisition/untyped"].attrs["neurodata_type"]
    return str(path)


def _warnings_from_inspect(path: str):
    """Every ContainerTypeContradictionWarning raised by one `inspect`, as message strings."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        jnwb.inspect(path)
    return [
        str(w.message) for w in caught
        if issubclass(w.category, ContainerTypeContradictionWarning)
    ]


def _warned_containers(path: str) -> set[str]:
    """The container path each warning is about, taken from the head of its message."""
    return {message.split(":", 1)[0] for message in _warnings_from_inspect(path)}


def test_fixture_really_holds_the_shapes_it_is_named_for(corpus_shapes):
    """The fixture builds the case it is named after.

    A `nested-clone` fixture that built an empty `.git` once agreed with the defect it was
    supposed to discriminate and passed. If the mistyping below silently failed to apply, the
    no-warning half of this module would pass vacuously, so the shapes are asserted against the
    file rather than assumed from the code that wrote it.
    """
    with h5py.File(corpus_shapes, "r") as handle:
        acquisition = handle["acquisition"]

        mistyped = acquisition["mistyped_es"]
        assert mistyped.attrs["neurodata_type"] == "ElectricalSeries"
        assert mistyped["data"].attrs["unit"] == "n.a."
        assert mistyped["data"].dtype == np.int16
        assert "electrodes" in mistyped, "must stay readable, so the region must survive"

        untyped = acquisition["untyped"]
        assert "neurodata_type" not in untyped.attrs
        assert untyped["data"].attrs["unit"] == "n.a."

        consistent_ts = acquisition["consistent_ts"]
        assert consistent_ts.attrs["neurodata_type"] == "TimeSeries"
        assert consistent_ts["data"].attrs["unit"] == "n.a."

        consistent_es = acquisition["consistent_es"]
        assert consistent_es.attrs["neurodata_type"] == "ElectricalSeries"
        assert consistent_es["data"].attrs["unit"] == "volts"


def test_exactly_the_contradicting_containers_warn(corpus_shapes):
    """The discriminator: the mistyped and the untyped warn, and the two consistent ones do not.

    Asserted as set equality in a single `inspect` over all four containers. An implementation
    that warns on every container fails on the two consistent ones; one that warns on none fails
    on the two contradicting ones; one that warns about the wrong container fails on both halves.
    """
    assert _warned_containers(corpus_shapes) == {
        "/acquisition/mistyped_es",
        "/acquisition/untyped",
    }


def test_the_mistyped_warning_names_the_declared_type_and_the_contents(corpus_shapes):
    """The warning's content, not merely its class, carries the signal."""
    messages = [m for m in _warnings_from_inspect(corpus_shapes)
                if m.startswith("/acquisition/mistyped_es:")]
    assert len(messages) == 1, "warn once per container"
    message = messages[0]
    assert "ElectricalSeries" in message, "names the declared type"
    assert "'volts'" in message, "names what that declared type requires"
    assert "'n.a.'" in message, "names what the contents actually say"
    assert "int16" in message, "names the stored dtype, the int16 case P-54 measured"


def test_the_untyped_warning_says_nothing_declares_the_type(corpus_shapes):
    messages = [m for m in _warnings_from_inspect(corpus_shapes)
                if m.startswith("/acquisition/untyped:")]
    assert len(messages) == 1, "warn once per container"
    message = messages[0]
    assert "no neurodata_type" in message, "names the absence as the finding"
    assert "'n.a.'" in message, "names what the contents say in its place"


def test_all_three_shapes_still_read(corpus_shapes):
    """Warn, never refuse: every shape is still readable and reports its declared type as found."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        report = jnwb.inspect(corpus_shapes)
    declared = {entry["name"]: entry["neurodata_type"] for entry in report["acquisitions"]}
    assert declared == {
        "mistyped_es": "ElectricalSeries",
        "consistent_es": "ElectricalSeries",
        "consistent_ts": "TimeSeries",
        "untyped": None,
    }
    # The contradiction changes nothing downstream: the data still comes back.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        data, rate = jnwb.acquisition_channel(corpus_shapes, "mistyped_es", 0)
    assert data.shape == (100,)
    assert rate == pytest.approx(30000.0)


def test_a_clean_file_raises_no_contradiction_warning(tmp_path):
    """A warning that fires on everything carries no information."""
    path = tmp_path / "clean.nwb"
    nwbfile = _base_file("clean")
    nwbfile.add_acquisition(_electrical(nwbfile, "es"))
    nwbfile.add_acquisition(
        TimeSeries(name="ts", data=np.zeros(100, dtype=np.int16), unit="n.a.", rate=1000.0)
    )
    _write(nwbfile, path)
    assert _warnings_from_inspect(str(path)) == []


def test_a_container_wrapping_many_series_warns_once(tmp_path):
    """06-84's own stop condition, as a test.

    A warning nobody can read through is not the ruled behaviour. An `LFP` container wrapping
    three mistyped series is one container, so it produces one warning naming all three, not
    three warnings.
    """
    path = tmp_path / "wrapped.nwb"
    nwbfile = _base_file("wrapped")
    module = nwbfile.create_processing_module(name="ecephys", description="d")
    lfp = LFP(name="LFP")
    for index in range(3):
        lfp.add_electrical_series(_electrical(nwbfile, f"es{index}", rate=1000.0))
    module.add(lfp)
    _write(nwbfile, path)

    with h5py.File(path, "r+") as handle:
        for index in range(3):
            handle[f"processing/ecephys/LFP/es{index}/data"].attrs["unit"] = "n.a."

    messages = _warnings_from_inspect(str(path))
    assert len(messages) == 1, "one container, one warning"
    assert messages[0].startswith("/processing/ecephys/LFP:")
    for index in range(3):
        assert f"es{index}" in messages[0], "the single warning names every series it covers"


def test_a_series_with_no_unit_does_not_warn(tmp_path):
    """An absent unit contradicts nothing.

    The deliberate boundary: this warning reports a declared type disagreeing with a *stated*
    unit, not a file that is merely incomplete. Widening it to absence would make it fire on
    every partial file, which is the same as not firing at all.
    """
    path = tmp_path / "nounit.nwb"
    nwbfile = _base_file("nounit")
    nwbfile.add_acquisition(_electrical(nwbfile, "es"))
    _write(nwbfile, path)
    with h5py.File(path, "r+") as handle:
        del handle["acquisition/es/data"].attrs["unit"]
    assert _warnings_from_inspect(str(path)) == []
