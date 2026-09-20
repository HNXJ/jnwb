"""The read path refuses by default, tolerates on request, and says what it repaired.

Two rulings, 2026-09-19.

``allow_missing`` exists because a consumer's 9 of 22 files lack ``session_description`` on disk.
jnwb refused them at ``nwb_io.py``, and so does bare pynwb. ``artifacts/goal.md`` section 4 was
read as mandating that refusal; it does not. It forbids substituting synthetic values "for missing
empirical data in an analysis path", and this is metadata outside one. So the opt-in is admissible
*provided it synthesizes nothing* -- the field stays absent, and the read records what it waived.

The squeeze warning exists because ``_repair_builder`` collapsed length-1 array attributes in
silence. The repair is correct and the value is right, but a receipt written from a repaired file
could not record that the file needed repairing.

The fixtures build all four cells of the measured matrix: ``session_description`` present or
absent, crossed with a device attribute scalar or a length-1 object array.
"""

from __future__ import annotations

import shutil
import warnings

import h5py
import numpy as np
import pytest

from jnwb.nwb_io import (
    WAIVED_REQUIREMENTS_ATTR,
    MissingRequiredNWBFieldError,
    SqueezedAttributeWarning,
    nwb_read_io,
    read_nwb,
)

# No sys.path manipulation and no assertion that jnwb resolves to this checkout.
# `tests/test_the_suite_can_qualify_an_installed_copy.py` exists so this suite can be run against
# an installed wheel, and a module that pinned the import to the working tree would defeat it.
# Whichever jnwb is under test is the one these behaviours are asserted of, which is the point.

_DEVICE = "/general/devices/synth_device_0"


@pytest.fixture(scope="module")
def base_file(tmp_path_factory):
    from jnwb.testing.nwb_fixtures import write_synth_nwb

    path = tmp_path_factory.mktemp("nwbbase") / "base.nwb"
    write_synth_nwb(str(path))
    return path


def _cell(base_file, tmp_path, *, has_description: bool, array_attr: bool) -> pathlib.Path:
    """One cell of the 2x2, mutated with h5py and verified in bytes before it is returned."""
    path = tmp_path / f"cell_{int(has_description)}{int(array_attr)}.nwb"
    shutil.copy(base_file, path)
    with h5py.File(path, "a") as handle:
        if not has_description and "session_description" in handle:
            del handle["session_description"]
        if array_attr:
            handle[_DEVICE].attrs["description"] = np.array(["probe desc"], dtype=object)

    with h5py.File(path, "r") as handle:
        assert ("session_description" in handle) is has_description
        if array_attr:
            value = handle[_DEVICE].attrs["description"]
            assert isinstance(value, np.ndarray) and value.shape == (1,)
    return path


def test_a_complete_file_still_opens_and_waives_nothing(base_file, tmp_path):
    path = _cell(base_file, tmp_path, has_description=True, array_attr=False)

    nwbfile = read_nwb(str(path))

    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == ()


def test_a_missing_required_field_is_still_refused_by_default(base_file, tmp_path):
    """The default did not move. This is the regression that matters most."""
    path = _cell(base_file, tmp_path, has_description=False, array_attr=False)

    with pytest.raises(MissingRequiredNWBFieldError):
        read_nwb(str(path))


def test_the_opt_in_opens_it_and_records_what_it_waived(base_file, tmp_path):
    path = _cell(base_file, tmp_path, has_description=False, array_attr=False)

    nwbfile = read_nwb(str(path), allow_missing=("session_description",))

    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == ("session_description",)


def test_the_opt_in_synthesizes_nothing(base_file, tmp_path):
    """goal.md section 4 forbids substituting a value, which is not what this does.

    The field must be absent or empty on the returned object -- never a plausible-looking string
    that a later reader would take for something the file said.
    """
    path = _cell(base_file, tmp_path, has_description=False, array_attr=False)

    nwbfile = read_nwb(str(path), allow_missing=("session_description",))

    assert not getattr(nwbfile, "session_description", None)


def test_a_bare_string_is_accepted_as_one_field(base_file, tmp_path):
    path = _cell(base_file, tmp_path, has_description=False, array_attr=False)

    nwbfile = read_nwb(str(path), allow_missing="session_description")

    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == ("session_description",)


def test_a_field_jnwb_never_refuses_on_is_rejected_not_ignored():
    """A typo that quietly tolerates nothing is the failure mode the allowlist prevents."""
    with pytest.raises(ValueError, match="not a field jnwb refuses on"):
        read_nwb("unread.nwb", allow_missing=("sesion_description",))


def test_the_opt_in_is_refused_on_a_write_mode():
    with pytest.raises(ValueError, match="read-path option"):
        with nwb_read_io("unread.nwb", "w", allow_missing=("session_description",)):
            pass  # pragma: no cover - the raise happens before the body


def test_a_squeezed_attribute_warns_and_names_itself(base_file, tmp_path):
    """Measured reachable: bare pynwb fails this file and jnwb opens it."""
    path = _cell(base_file, tmp_path, has_description=True, array_attr=True)

    with pytest.warns(SqueezedAttributeWarning, match="description"):
        nwbfile = read_nwb(str(path))

    assert nwbfile.devices["synth_device_0"].description == "probe desc"


def test_a_clean_file_raises_no_squeeze_warning(base_file, tmp_path):
    """Otherwise the warning says nothing, which is the same as not having one."""
    path = _cell(base_file, tmp_path, has_description=True, array_attr=False)

    with warnings.catch_warnings():
        warnings.simplefilter("error", SqueezedAttributeWarning)
        read_nwb(str(path))


def test_the_refusal_still_precedes_the_squeeze_on_the_consumers_shape(base_file, tmp_path):
    """Cell D. Both defects present; the missing field is reported, and it is reported first.

    HDMF constructs the root NWBFile builder before the Device, so on this shape the squeeze is
    unreachable -- untested rather than broken. Pinning it here means a later reordering that
    changed which defect a user hears about could not pass unnoticed.
    """
    path = _cell(base_file, tmp_path, has_description=False, array_attr=True)

    with pytest.raises(MissingRequiredNWBFieldError):
        read_nwb(str(path))


def test_tolerating_the_field_then_reaches_the_squeeze(base_file, tmp_path):
    """And with the refusal waived, the second defect becomes visible rather than staying hidden."""
    path = _cell(base_file, tmp_path, has_description=False, array_attr=True)

    with pytest.warns(SqueezedAttributeWarning):
        nwbfile = read_nwb(str(path), allow_missing=("session_description",))

    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == ("session_description",)
    assert nwbfile.devices["synth_device_0"].description == "probe desc"
