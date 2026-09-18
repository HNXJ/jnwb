"""05-37: jnwb could not read a units table that plain pynwb reads.

The smallest units table a foreign lab writes has one column, `spike_times`, which on
disk is `colnames = array(['spike_times'])`. jnwb's builder repair scalarizes any
length-1 array attribute -- written for `description = array(['probe desc'])` -- and that
turned `colnames` into the string `'spike_times'`. The next line does
`list(builder.attributes["colnames"])`, which spells a string out:

    ConstructError ... 'colnames': array(['s','p','i','k','e','_','t','i','m','e','s',
                                          'spike_times'])

Reproduced: pynwb reads the file and reports `units n = 2, colnames = ('spike_times',)`,
while `inspect`, `unit_spike_times`, `events`, `acquisition_channel`,
`get_all_units_metadata` and `electrode_inventory` all raised `ConstructError`.

`colnames` is specified as a sequence, so a length-1 value is a one-element list and not
a wrapped scalar. It is excluded from the scalarization, and the `list(...)` is guarded
as well, so a bare string from any other source cannot be spelled out either.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

import jnwb
from jnwb.nwb_io import _SEQUENCE_ATTRIBUTES, nwb_read_io


def _write_units(path, columns=("spike_times",), n_units=2):
    """A units table written with plain pynwb and nothing else."""
    import pynwb

    nwb = pynwb.NWBFile(session_description="minimal", identifier="min-1",
                        session_start_time=datetime.now(timezone.utc))
    extra = [c for c in columns if c != "spike_times"]
    for name in extra:
        nwb.add_unit_column(name=name, description=f"{name} column")
    for i in range(n_units):
        row = {"spike_times": [0.1 * (i + 1), 0.5 * (i + 1), 0.9]}
        for name in extra:
            row[name] = float(i)
        nwb.add_unit(**row)
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return str(path)


@pytest.fixture
def minimal(tmp_path):
    return _write_units(tmp_path / "minimal_units.nwb")


class TestTheSmallestUnitsTableIsReadable:

    def test_pynwb_and_jnwb_agree_on_the_column_list(self, minimal):
        import pynwb

        with pynwb.NWBHDF5IO(minimal, "r") as io:
            assert tuple(io.read().units.colnames) == ("spike_times",)
        with nwb_read_io(minimal) as io:
            nwb = io.read()
            assert tuple(nwb.units.colnames) == ("spike_times",)
            assert len(nwb.units) == 2

    def test_the_column_name_is_not_spelled_out_one_character_per_column(self, minimal):
        with nwb_read_io(minimal) as io:
            nwb = io.read()
            assert "s" not in nwb.units.colnames, list(nwb.units.colnames)
            assert len(nwb.units.colnames) == 1

    def test_inspect_reads_it(self, minimal):
        info = jnwb.inspect(minimal)
        assert info["units"]["n_rows"] == 2
        assert "spike_times" in [c["name"] for c in info["units"]["columns"]]

    def test_unit_spike_times_reads_it(self, minimal):
        np.testing.assert_allclose(jnwb.unit_spike_times(minimal, unit_index=0),
                                   [0.1, 0.5, 0.9])
        np.testing.assert_allclose(jnwb.unit_spike_times(minimal, unit_index=1),
                                   [0.2, 1.0, 0.9])

    def test_get_all_units_metadata_reads_it(self, minimal):
        df = jnwb.get_all_units_metadata([minimal])
        assert len(df) == 2

    def test_electrode_inventory_reads_it(self, minimal):
        jnwb.electrode_inventory([minimal])  # no electrodes, but it must not raise

    @pytest.mark.parametrize("call,error", [
        ("events", jnwb.IntervalTableNotFoundError),
        ("acquisition_channel", jnwb.AcquisitionNotFoundError),
    ])
    def test_the_entry_points_with_nothing_to_read_say_so_specifically(
            self, minimal, call, error):
        """These two still raise, because the file genuinely has no interval table and
        no acquisition. What matters is that it is the typed error about the missing
        thing, not a ConstructError about the units column list."""
        with pytest.raises(error):
            getattr(jnwb, call)(minimal)


class TestWiderTablesStillWork:

    @pytest.mark.parametrize("columns", [
        ("spike_times", "quality"),
        ("spike_times", "quality", "snr"),
    ])
    def test_a_multi_column_table_is_unaffected(self, tmp_path, columns):
        path = _write_units(tmp_path / f"u{len(columns)}.nwb", columns=columns)
        with nwb_read_io(path) as io:
            nwb = io.read()
            assert set(columns) <= set(nwb.units.colnames)
        assert jnwb.inspect(path)["units"]["n_rows"] == 2

    def test_a_one_unit_one_column_table_works_too(self, tmp_path):
        """Length 1 in both directions, which is where a wrapped scalar would hide."""
        path = _write_units(tmp_path / "one.nwb", n_units=1)
        with nwb_read_io(path) as io:
            nwb = io.read()
            assert tuple(nwb.units.colnames) == ("spike_times",)
            assert len(nwb.units) == 1


class TestAnySingleColumnTableNotOnlyUnits:
    """Found while mutation-testing 05-37, and broader than the audit reported.

    The units-specific guard cannot help a table that is not called `units`. A
    `DynamicTable` with one column, anywhere in the file, has
    `colnames = array(['value'])`, and at HEAD it failed exactly the same way:

        ConstructError (root/processing/misc/scores ... 'colnames': 'value' ...)

    Only excluding `colnames` from the scalarization fixes this one, which is why that
    exclusion is the primary repair and the bare-string guard is the backstop.
    """

    @staticmethod
    def _write(path):
        from datetime import datetime, timezone

        import pynwb
        from hdmf.common import DynamicTable, VectorData

        nwb = pynwb.NWBFile(session_description="m", identifier="i",
                            session_start_time=datetime.now(timezone.utc))
        table = DynamicTable(
            name="scores", description="one column",
            columns=[VectorData(name="value", description="v", data=[1.0, 2.0, 3.0])],
        )
        nwb.create_processing_module(name="misc", description="d").add(table)
        with pynwb.NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
        return str(path)

    def test_a_one_column_processing_table_reads(self, tmp_path):
        path = self._write(tmp_path / "one_col.nwb")
        with nwb_read_io(path) as io:
            table = io.read().processing["misc"]["scores"]
            assert tuple(table.colnames) == ("value",)
            assert list(table["value"].data) == [1.0, 2.0, 3.0]

    def test_inspect_reads_the_whole_file(self, tmp_path):
        path = self._write(tmp_path / "one_col2.nwb")
        assert jnwb.inspect(path)["session"]["identifier"] == "i"


class TestTheScalarRepairStillDoesItsJob:
    """It exists for `description = array(['probe desc'])`; only sequence-valued
    attributes are exempted."""

    def test_only_colnames_is_exempt(self):
        assert _SEQUENCE_ATTRIBUTES == frozenset({"colnames"})

    def test_a_length_one_string_array_attribute_is_still_scalarized(self):
        from hdmf.build import BuildManager, GroupBuilder
        from pynwb import get_type_map

        from jnwb.nwb_io import hdmf_build_repair_context

        mgr = BuildManager(get_type_map())
        gb = GroupBuilder(
            name="device",
            attributes={"namespace": "core", "neurodata_type": "Device",
                        "description": np.array(["probe desc"], dtype=object)},
        )
        with hdmf_build_repair_context():
            assert mgr.construct(gb).description == "probe desc"

    def test_a_bare_string_colnames_is_not_iterated_character_by_character(self):
        """The second guard: whatever puts a bare string there, it is one column."""
        from hdmf.build import GroupBuilder

        from jnwb.nwb_io import _repair_builder

        gb = GroupBuilder(name="units", attributes={"colnames": "spike_times"})
        _repair_builder(gb, None)
        assert list(gb.attributes["colnames"]) == ["spike_times"]
