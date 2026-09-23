"""A caller who can catch a read's refusal by name can reach its remedy by name.

``MissingRequiredNWBFieldError`` is public and meant to be caught. The waiver that clears it --
``read_nwb`` for the object, ``nwb_read_io`` for the object with its file still open -- and the
warning a repaired read emits, ``SqueezedAttributeWarning``, must be reachable the same way: as
``jnwb.<name>`` after ``import jnwb`` and nothing else. Everything here goes through the top-level
namespace only.
"""

from __future__ import annotations

import h5py
import numpy as np
import pytest

import jnwb

REMEDY = ("MissingRequiredNWBFieldError", "read_nwb", "nwb_read_io", "SqueezedAttributeWarning")


@pytest.mark.parametrize("name", REMEDY)
def test_the_name_is_exported_and_listed(name):
    assert name in jnwb.__all__
    assert name in dir(jnwb)
    assert getattr(jnwb, name).__module__ == "jnwb.nwb_io"


@pytest.fixture
def incomplete(tmp_path):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path / "incomplete.nwb"
    write_synth_nwb(str(path))
    with h5py.File(path, "a") as handle:
        del handle["session_description"]
    return path


def test_a_caller_catching_the_refusal_reaches_the_waiver(incomplete):
    path = incomplete
    try:
        jnwb.read_nwb(str(path))
    except jnwb.MissingRequiredNWBFieldError as exc:
        nwbfile = jnwb.read_nwb(str(path), allow_missing=(exc.field_name,))
    else:  # pragma: no cover - the refusal is the premise
        pytest.fail("a file without session_description was not refused")

    assert nwbfile.session_description == ""
    assert nwbfile.jnwb_waived_requirements == ("session_description",)


def test_the_open_file_route_records_the_waiver_and_reads_data(incomplete):
    """The object ``read_nwb`` returns has a closed file; this route is how a waived file's data
    is read, so it must carry the same record of the waiver."""
    with pytest.raises(jnwb.MissingRequiredNWBFieldError):
        with jnwb.nwb_read_io(str(incomplete)) as io:
            io.read()

    with jnwb.nwb_read_io(str(incomplete), allow_missing=("session_description",)) as io:
        nwbfile = io.read()
        spikes = np.asarray(nwbfile.units["spike_times"][0])

    assert nwbfile.session_description == ""
    assert nwbfile.jnwb_waived_requirements == ("session_description",)
    assert spikes.size > 0


def test_the_squeeze_warning_is_catchable_by_its_public_name(tmp_path):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path / "squeezed.nwb"
    write_synth_nwb(str(path))
    with h5py.File(path, "a") as handle:
        handle["/general/devices/synth_device_0"].attrs["description"] = np.array(
            ["probe desc"], dtype=object)

    with pytest.warns(jnwb.SqueezedAttributeWarning):
        jnwb.read_nwb(str(path))
