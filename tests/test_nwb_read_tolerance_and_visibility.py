"""The read path refuses by default, tolerates on request, and says what it repaired.

Two rulings, 2026-09-19.

``allow_missing`` exists because a consumer's 9 of 22 files lack ``session_description`` on disk.
jnwb refused them at ``nwb_io.py``, and so does bare pynwb. ``artifacts/goal.md`` section 4 was
read as mandating that refusal; it does not. It forbids substituting synthetic values "for missing
empirical data in an analysis path", and this is metadata outside one. So the opt-in is admissible
*provided it synthesizes nothing plausible* -- pynwb cannot build the object without the field, so
it reads ``""``, and the read records the waiver it actually used.

The last block holds the missingness table in ``docs/errors.md`` to what a read does: one test per
row, each reading the state both by default and with the waiver.

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

    pynwb requires the field, so it is present on the returned object and holds exactly ``""`` --
    never a plausible-looking string that a later reader would take for something the file said,
    and not merely something falsy, which ``None`` or ``[]`` would also satisfy.
    """
    path = _cell(base_file, tmp_path, has_description=False, array_attr=False)

    nwbfile = read_nwb(str(path), allow_missing=("session_description",))

    assert nwbfile.session_description == ""
    assert type(nwbfile.session_description) is str


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


# The missingness table in docs/errors.md. One test per row, in the table's order. Each builds the
# on-disk state with h5py, confirms it on disk without asking pynwb, and then reads it twice: by
# default and with the waiver. The waiver column is where a flag that recorded the request rather
# than the event would show, so every row asserts it.

_SD = "session_description"
_WAIVE = (_SD,)


def _state(base_file, tmp_path, name, mutate):
    """Copy the base file, replace its description with ``mutate(handle, original_bytes)``."""
    path = tmp_path / f"{name}.nwb"
    shutil.copy(base_file, path)
    with h5py.File(path, "a") as handle:
        original = handle[_SD][()]
        del handle[_SD]
        mutate(handle, original)
    return path


def _description(base_file) -> str:
    with h5py.File(base_file, "r") as handle:
        value = handle[_SD][()]
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _read(path, allow_missing=None):
    """The returned object and the names of the warning classes the read raised."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        nwbfile = read_nwb(str(path), allow_missing=allow_missing)
    return nwbfile, {type(w.message).__name__ for w in caught}


def _refusal(path, allow_missing=None):
    """The exception the read raised and the names of the warning classes raised with it."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with pytest.raises(Exception) as info:
            read_nwb(str(path), allow_missing=allow_missing)
    return info.value, {type(w.message).__name__ for w in caught}


def _assert_opens_both_ways_waiving_nothing(path, expected):
    for allow_missing in (None, _WAIVE):
        nwbfile, _ = _read(path, allow_missing)
        assert nwbfile.session_description == expected, allow_missing
        assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == (), allow_missing


def _assert_refused_both_ways_by_the_same_error(path):
    """The field is on disk, so the waiver has nothing to waive and cannot change the outcome."""
    default, _ = _refusal(path)
    waived, _ = _refusal(path, _WAIVE)
    assert not isinstance(default, MissingRequiredNWBFieldError)
    assert type(waived) is type(default)
    return default


def test_missingness_row_absent(base_file, tmp_path):
    path = _state(base_file, tmp_path, "absent", lambda handle, original: None)
    with h5py.File(path, "r") as handle:
        assert handle.get(_SD, getlink=True) is None

    refused, _ = _refusal(path)
    assert isinstance(refused, MissingRequiredNWBFieldError)
    assert refused.field_name == _SD

    nwbfile, _ = _read(path, _WAIVE)
    assert nwbfile.session_description == ""
    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == _WAIVE


_NULL_ENCODINGS = {
    "null_dataspace": lambda handle, original: handle.create_dataset(
        _SD, data=h5py.Empty(h5py.string_dtype())),
    "zero_length_array": lambda handle, original: handle.create_dataset(
        _SD, shape=(0,), dtype=h5py.string_dtype()),
    "null_reference": lambda handle, original: handle.create_dataset(
        _SD, data=h5py.Reference(), dtype=h5py.ref_dtype),
}


@pytest.mark.parametrize("encoding", sorted(_NULL_ENCODINGS))
def test_missingness_row_explicit_null(base_file, tmp_path, encoding):
    path = _state(base_file, tmp_path, encoding, _NULL_ENCODINGS[encoding])
    with h5py.File(path, "r") as handle:
        assert isinstance(handle.get(_SD, getlink=True), h5py.HardLink)
        assert handle[_SD].shape in (None, (0,), ())

    _assert_refused_both_ways_by_the_same_error(path)


def test_missingness_row_empty_string(base_file, tmp_path):
    path = _state(base_file, tmp_path, "empty", lambda handle, original: handle.create_dataset(
        _SD, data="", dtype=h5py.string_dtype()))
    with h5py.File(path, "r") as handle:
        assert handle[_SD].shape == () and handle[_SD][()] in (b"", "")

    _assert_opens_both_ways_waiving_nothing(path, "")


def test_missingness_row_length_one_array(base_file, tmp_path):
    path = _state(base_file, tmp_path, "len1", lambda handle, original: handle.create_dataset(
        _SD, data=np.array(["MALFORMED"], dtype=object), dtype=h5py.string_dtype()))
    with h5py.File(path, "r") as handle:
        assert handle[_SD].shape == (1,)

    _assert_opens_both_ways_waiving_nothing(path, "MALFORMED")
    # The flattening is pynwb's, on a dataset, and the squeeze repair walks attributes only.
    _, warned = _read(path)
    assert "SqueezedAttributeWarning" not in warned


_MALFORMED = {
    "integer": lambda handle, original: handle.create_dataset(_SD, data=np.int64(42)),
    "two_strings": lambda handle, original: handle.create_dataset(
        _SD, data=np.array(["a", "b"], dtype=object), dtype=h5py.string_dtype()),
}


@pytest.mark.parametrize("encoding", sorted(_MALFORMED))
def test_missingness_row_other_malformed_value(base_file, tmp_path, encoding):
    path = _state(base_file, tmp_path, encoding, _MALFORMED[encoding])
    with h5py.File(path, "r") as handle:
        assert _SD in handle

    refused = _assert_refused_both_ways_by_the_same_error(path)
    assert type(refused).__name__ == "ConstructError"


def test_missingness_row_present_and_valid(base_file, tmp_path):
    path = tmp_path / "valid.nwb"
    shutil.copy(base_file, path)
    expected = _description(base_file)
    assert expected

    _assert_opens_both_ways_waiving_nothing(path, expected)


@pytest.mark.parametrize("kind", ["soft", "external"])
def test_missingness_row_link_to_a_valid_description(base_file, tmp_path, kind):
    def link(handle, original):
        if kind == "soft":
            handle.create_dataset("/general/description_target", data=original,
                                  dtype=h5py.string_dtype())
            handle[_SD] = h5py.SoftLink("/general/description_target")
        else:
            with h5py.File(tmp_path / "description_target.h5", "w") as target:
                target.create_dataset("description", data=original, dtype=h5py.string_dtype())
            handle[_SD] = h5py.ExternalLink("description_target.h5", "/description")

    path = _state(base_file, tmp_path, f"{kind}_valid", link)
    link_class = h5py.SoftLink if kind == "soft" else h5py.ExternalLink
    with h5py.File(path, "r") as handle:
        assert isinstance(handle.get(_SD, getlink=True), link_class)
        resolved = handle[_SD][()]  # the link resolves, to the original description
    expected = _description(base_file)
    assert resolved.decode("utf-8") == expected

    _assert_opens_both_ways_waiving_nothing(path, expected)


def _assert_reads_as_absent_with_a_broken_link_warning(path):
    refused, warned = _refusal(path)
    assert isinstance(refused, MissingRequiredNWBFieldError)
    assert "BrokenLinkWarning" in warned

    nwbfile, warned = _read(path, _WAIVE)
    assert nwbfile.session_description == ""
    assert getattr(nwbfile, WAIVED_REQUIREMENTS_ATTR) == _WAIVE
    assert "BrokenLinkWarning" in warned


def test_missingness_row_dangling_soft_link(base_file, tmp_path):
    def link(handle, original):
        handle[_SD] = h5py.SoftLink("/no_such_target")

    path = _state(base_file, tmp_path, "soft_dangling", link)
    with h5py.File(path, "r") as handle:
        assert isinstance(handle.get(_SD, getlink=True), h5py.SoftLink)
        with pytest.raises(KeyError):  # the link does not resolve
            handle[_SD]

    _assert_reads_as_absent_with_a_broken_link_warning(path)


def test_missingness_row_broken_external_link(base_file, tmp_path):
    def link(handle, original):
        handle[_SD] = h5py.ExternalLink("no_such_file.h5", "/x")

    path = _state(base_file, tmp_path, "external_broken", link)
    with h5py.File(path, "r") as handle:
        assert isinstance(handle.get(_SD, getlink=True), h5py.ExternalLink)
        assert not (tmp_path / "no_such_file.h5").exists()

    _assert_reads_as_absent_with_a_broken_link_warning(path)


def test_missingness_row_nul_byte_string(base_file, tmp_path):
    path = _state(base_file, tmp_path, "nul", lambda handle, original: handle.create_dataset(
        _SD, data=np.array(b"\x00\x00", dtype="S2")))
    # h5py strips trailing NULs from a fixed-length string, so confirm the payload in raw bytes.
    with h5py.File(path, "r") as handle:
        dset = handle[_SD]
        assert dset.dtype == np.dtype("S2")
        offset, size = dset.id.get_offset(), dset.id.get_storage_size()
    assert size == 2
    with open(path, "rb") as raw:
        raw.seek(offset)
        assert raw.read(size) == b"\x00\x00"

    _assert_opens_both_ways_waiving_nothing(path, "")
