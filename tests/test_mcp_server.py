"""Tests for the jnwb MCP server tools.

The server exposes three tools and all of them ingest. A fourth, `add_tool`, wrote
caller-supplied Python into the installed package and was removed in 0.2.5; the tests that
exercised it went with it. What replaced them is a check that the documented tool table and
the live registry are the same set, which is the thing that was actually wrong.
"""
import importlib
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone

import numpy as np
import pynwb
import pytest

pytest.importorskip("mcp")
from jnwb.mcp_server import (  # noqa: E402
    get_event_codes_and_timings,
    inspect_nwb,
    prepare_signal_reference,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: The tool source every `add_tool` success path in this file registers.
DUMMY_TOOL_CODE = '''
def test_temp_dummy_tool(a: int) -> str:
    """A dummy test tool."""
    return f"val_{a}"
'''


class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = str(pathlib.Path(self.temp_dir.name) / "test_synthetic.nwb")

        nwbfile = pynwb.NWBFile(
            session_description="Synthetic session for MCP testing",
            identifier="SYNTH_MCP_001",
            session_start_time=datetime.now(timezone.utc)
        )
        device = nwbfile.create_device(name="probe0")
        eg = nwbfile.create_electrode_group(name="eg0", description="desc", location="V1", device=device)
        nwbfile.add_electrode(x=0.0, y=0.0, z=0.0, imp=0.0, location="V1", filtering="none", group=eg)
        region = nwbfile.create_electrode_table_region(region=[0], description="all electrodes")

        es = pynwb.ecephys.ElectricalSeries(
            name="ElectricalSeries",
            data=np.random.randn(100, 1).astype(np.float32),
            electrodes=region,
            starting_time=0.0,
            rate=1000.0
        )
        nwbfile.add_acquisition(es)

        epochs = pynwb.epoch.TimeIntervals(name="stim_events", description="events")
        epochs.add_column(name="code", description="event code")
        epochs.add_row(start_time=1.0, stop_time=2.0, code="STIM_A")
        epochs.add_row(start_time=3.0, stop_time=4.0, code="STIM_B")
        nwbfile.add_time_intervals(epochs)

        with pynwb.NWBHDF5IO(self.file_path, "w") as io:
            io.write(nwbfile)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_inspect_nwb_success(self):
        res = inspect_nwb(self.file_path)
        self.assertNotIn("error", res)
        self.assertEqual(
            res["session"]["session_description"],
            "Synthetic session for MCP testing",
        )
        self.assertEqual(res["session"]["identifier"], "SYNTH_MCP_001")
        self.assertIn("session_start_time", res["session"])
        self.assertIn("interval_tables", res)
        self.assertIn("acquisitions", res)
        self.assertTrue(len(res["interval_tables"]) >= 1)
        self.assertTrue(len(res["acquisitions"]) >= 1)

    def test_inspect_nwb_file_not_found(self):
        res = inspect_nwb("non_existent_file.nwb")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "FileNotFound")

    def test_get_event_codes_and_timings_autodiscover(self):
        res = get_event_codes_and_timings(self.file_path)
        self.assertNotIn("error", res)
        self.assertIn("event_group_path", res)
        self.assertIn("events", res)
        self.assertIn("total_events", res)
        self.assertIn("time_unit", res)

        self.assertTrue(len(res["events"]) > 0)
        first_event = res["events"][0]
        self.assertIn("code", first_event)
        self.assertIn("start_time", first_event)
        self.assertIn("stop_time", first_event)

    def test_get_event_codes_and_timings_explicit(self):
        res = get_event_codes_and_timings(self.file_path, event_group_path="/intervals/stim_events")
        self.assertNotIn("error", res)
        self.assertEqual(res["event_group_path"], "/intervals/stim_events")
        self.assertEqual(len(res["events"]), 2)

    def test_event_table_is_never_chosen_by_project_name(self):
        """With several tables and no 'trials', the caller must choose; jnwb never guesses."""
        path = str(pathlib.Path(self.temp_dir.name) / "two_tables.nwb")
        nwbfile = pynwb.NWBFile(session_description="two tables", identifier="TWO",
                                session_start_time=datetime.now(timezone.utc))
        for name in ("omission_glo_passive", "other_events"):
            t = pynwb.epoch.TimeIntervals(name=name, description="events")
            t.add_row(start_time=1.0, stop_time=2.0)
            nwbfile.add_time_intervals(t)
        with pynwb.NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)

        res = get_event_codes_and_timings(path)
        self.assertEqual(res.get("error_type"), "AmbiguousPath")
        self.assertIn("other_events", res["error"])

    def test_missing_explicit_path_errors_instead_of_substituting(self):
        res = get_event_codes_and_timings(self.file_path, event_group_path="/intervals/absent")
        self.assertEqual(res.get("error_type"), "PathNotFound")

    def test_prepare_signal_reference_success(self):
        target_ds = "/acquisition/ElectricalSeries/data"
        res = prepare_signal_reference(self.file_path, target_ds)
        self.assertNotIn("error", res)
        self.assertEqual(res["dataset_path"], target_ds)
        self.assertIn("dtype", res)
        self.assertIn("shape", res)
        self.assertIn("chunk_shape", res)
        self.assertIn("compression", res)
        self.assertIn("estimated_size_mb", res)
        self.assertIn("access_hint", res)
        self.assertIsInstance(res["estimated_size_mb"], float)

    def _scaled_file(self):
        """Two int16 channels with every NWB scaling and timing field set away from its default."""
        path = str(pathlib.Path(self.temp_dir.name) / "scaled.nwb")
        nwbfile = pynwb.NWBFile(session_description="scaled", identifier="SCALED",
                                session_start_time=datetime.now(timezone.utc))
        device = nwbfile.create_device(name="probe0")
        eg = nwbfile.create_electrode_group(name="eg0", description="d", location="V1", device=device)
        for _ in range(2):
            nwbfile.add_electrode(x=0.0, y=0.0, z=0.0, imp=0.0, location="V1", filtering="none", group=eg)
        region = nwbfile.create_electrode_table_region(region=[0, 1], description="both")
        stored = np.random.default_rng(0).integers(-500, 500, size=(100, 2)).astype(np.int16)
        nwbfile.add_acquisition(pynwb.ecephys.ElectricalSeries(
            name="Scaled", data=stored, electrodes=region, conversion=2.5e-6, offset=0.125,
            channel_conversion=[1.0, 4.0], starting_time=3.0, rate=1000.0,
        ))
        with pynwb.NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)
        return path, stored

    def test_the_reference_carries_what_turns_stored_values_into_physical_ones(self):
        import jnwb

        path, stored = self._scaled_file()
        res = prepare_signal_reference(path, "/acquisition/Scaled/data")
        self.assertNotIn("error", res)
        self.assertEqual(res["conversion"], 2.5e-6)
        self.assertEqual(res["offset"], 0.125)
        self.assertEqual(res["channel_conversion"], [1.0, 4.0])
        self.assertEqual((res["rate_hz"], res["starting_time"]), (1000.0, 3.0))
        self.assertEqual((res["layout"], res["layout_basis"]), ("time_by_channel", "electrode_count"))
        self.assertEqual(res["reader"], f"jnwb.acquisition_channel({path!r}, name='Scaled', channel=k)")
        for field in ("conversion", "channel_conversion", "offset", "starting_time"):
            self.assertIn(field, res["access_hint"])
        # The fields alone reproduce what the named reader returns, channel by channel.
        for k in range(2):
            by_fields = res["conversion"] * res["channel_conversion"][k] * stored[:, k] + res["offset"]
            with pytest.warns(UserWarning, match="starting_time"):
                by_reader, rate = jnwb.acquisition_channel(path, name="Scaled", channel=k)
            np.testing.assert_allclose(by_reader, by_fields, rtol=0, atol=1e-12)
            self.assertEqual(rate, res["rate_hz"])

    def test_the_reference_says_the_layout_is_unknown_instead_of_guessing_it(self):
        import h5py

        # No type and no electrode region: nothing in the file says which axis is channels.
        with h5py.File(self.file_path, "a") as f:
            group = f["acquisition"].create_group("untyped")
            group.create_dataset("data", data=np.zeros((10, 50), dtype=np.float32))
            group.create_dataset("starting_time", data=0.0).attrs["rate"] = 1000.0
        res = prepare_signal_reference(self.file_path, "/acquisition/untyped/data")
        self.assertNotIn("error", res)
        self.assertEqual((res["layout"], res["layout_basis"], res["reader"]), ("unknown", None, None))
        self.assertIn("layout is unknown", res["access_hint"])
        self.assertNotIn("channels, time", res["access_hint"])

    def test_the_reader_is_named_only_where_it_reads(self):
        """No reader for a series without a rate, or one the resolver cannot name; a reader
        wherever one is named returns the series."""
        import warnings

        import jnwb
        from pynwb.behavior import Position

        path = str(pathlib.Path(self.temp_dir.name) / "readers.nwb")
        nwbfile = pynwb.NWBFile(session_description="r", identifier="R",
                                session_start_time=datetime.now(timezone.utc))
        nwbfile.add_acquisition(pynwb.TimeSeries(
            name="stamped", data=np.arange(20.0), unit="m", timestamps=np.linspace(0, 1, 20)))
        mod = nwbfile.create_processing_module(name="behavior", description="b")
        position = Position(name="Position")
        position.create_spatial_series(name="xy", data=np.ones((50, 2)), reference_frame="r", rate=60.0)
        mod.add(position)
        mod.add(pynwb.TimeSeries(name="direct", data=np.arange(50.0), unit="a", rate=60.0))
        with pynwb.NWBHDF5IO(path, "w") as io:
            io.write(nwbfile)

        stamped = prepare_signal_reference(path, "/acquisition/stamped/data")
        self.assertEqual((stamped["rate_hz"], stamped["reader"]), (None, None))
        self.assertEqual(stamped["timestamps_path"], "/acquisition/stamped/timestamps")
        wrapped = prepare_signal_reference(path, "/processing/behavior/Position/xy/data")
        self.assertEqual(wrapped["rate_hz"], 60.0)
        self.assertIsNone(wrapped["reader"])
        with self.assertRaises(jnwb.NWBInspectError):
            jnwb.acquisition_channel(path, name="behavior/Position/xy")
        direct = prepare_signal_reference(path, "/processing/behavior/direct/data")
        self.assertEqual(direct["reader"],
                         f"jnwb.acquisition_channel({path!r}, name='behavior/direct', channel=k)")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            values, rate = jnwb.acquisition_channel(path, name="behavior/direct")
        np.testing.assert_array_equal(values, np.arange(50.0))
        self.assertEqual(rate, 60.0)

    def test_no_reader_for_a_series_the_reader_refuses(self):
        """A NaN rate and a channel_conversion of the wrong length each make
        `acquisition_channel` raise, so neither gets a reader; the rest of the reference stays."""
        import h5py

        import jnwb

        path, _ = self._scaled_file()
        with h5py.File(path, "a") as f:
            f["acquisition/Scaled/starting_time"].attrs["rate"] = float("nan")
        res = prepare_signal_reference(path, "/acquisition/Scaled/data")
        self.assertNotIn("error", res)
        self.assertTrue(np.isnan(res["rate_hz"]))
        self.assertIsNone(res["reader"])
        with self.assertRaises(jnwb.NWBInspectError):
            jnwb.acquisition_channel(path, name="Scaled", channel=0)

        with h5py.File(path, "a") as f:
            f["acquisition/Scaled/starting_time"].attrs["rate"] = 1000.0
            del f["acquisition/Scaled/channel_conversion"]
            f["acquisition/Scaled"].create_dataset("channel_conversion", data=[1.0, 2.0, 3.0])
        res = prepare_signal_reference(path, "/acquisition/Scaled/data")
        self.assertNotIn("error", res)
        self.assertEqual((res["rate_hz"], res["channel_conversion"]), (1000.0, [1.0, 2.0, 3.0]))
        self.assertIsNone(res["reader"])
        with self.assertRaisesRegex(ValueError, "channel_conversion"):
            jnwb.acquisition_channel(path, name="Scaled", channel=0)

    def test_a_file_the_resolver_cannot_open_still_gets_its_reference(self):
        """HDF5 that is not NWB: pynwb refuses it, which means no reader, not an error."""
        import h5py

        path = str(pathlib.Path(self.temp_dir.name) / "plain.h5")
        with h5py.File(path, "w") as f:
            group = f.create_group("acquisition/X")
            group.create_dataset("data", data=np.arange(10.0))
            group.create_dataset("starting_time", data=0.0).attrs["rate"] = 100.0
        res = prepare_signal_reference(path, "/acquisition/X/data")
        self.assertNotIn("error", res)
        self.assertEqual((res["rate_hz"], res["starting_time"], res["layout"]), (100.0, 0.0, "time"))
        self.assertIsNone(res["reader"])

    def test_prepare_signal_reference_not_found(self):
        res = prepare_signal_reference(self.file_path, "/non/existent/path")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "PathNotFound")

    def test_every_registered_tool_leaves_the_file_and_working_directory_unchanged(self):
        """`docs/agents.md` says the server writes nothing. A source scan for one writer's
        name cannot hold that: `open(..., "w")`, an h5py or pynwb write mode and a sidecar
        file all pass it. This runs every registered tool on its success path and compares
        the bytes on disk before and after.
        """
        import asyncio
        import hashlib
        import os

        import jnwb.mcp_server as package

        calls = {
            "inspect_nwb": {"file_path": self.file_path},
            "get_event_codes_and_timings": {"file_path": self.file_path},
            "prepare_signal_reference": {
                "file_path": self.file_path,
                "dataset_path": "/acquisition/ElectricalSeries/data",
            },
        }
        live = {tool.name for tool in asyncio.run(package.mcp.list_tools())}
        self.assertEqual(set(calls), live, "a registered tool has no call in this test")

        def snapshot(*roots):
            return {
                path: hashlib.sha256(path.read_bytes()).hexdigest()
                for root in roots
                for path in pathlib.Path(root).rglob("*")
                if path.is_file()
            }

        with tempfile.TemporaryDirectory() as cwd:
            before = snapshot(self.temp_dir.name, cwd)
            self.assertIn(pathlib.Path(self.file_path), before)
            previous = os.getcwd()
            os.chdir(cwd)
            try:
                for name, kwargs in sorted(calls.items()):
                    result = getattr(package, name)(**kwargs)
                    self.assertNotIn("error", result, f"{name} did not reach its success path")
            finally:
                os.chdir(previous)
            after = snapshot(self.temp_dir.name, cwd)
        self.assertEqual(before, after, "an MCP tool created or changed a file")

class TestMCPServerEntrypoint(unittest.TestCase):
    def test_server_module_exposes_fastmcp_instance(self):
        from jnwb.mcp_server import server
        from mcp.server.fastmcp import FastMCP

        self.assertIsInstance(server.mcp, FastMCP)
        self.assertEqual(server.mcp.name, "jnwb-mcp-server")

    def test_the_documented_launch_command_actually_launches(self):
        """`docs/agents.md` tells the reader to run
        `python -m jnwb.mcp_server`. That failed with "'jnwb.mcp_server' is a package and
        cannot be directly executed", including against the published wheel with the `mcp`
        extra installed, because the package had no `__main__` submodule -- the
        `if __name__ == "__main__": mcp.run()` guard sat in `__init__.py`, where it can
        never be true. The class above passed throughout: it checked that a FastMCP object
        exists, not that the server starts.
        """
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "-m", "jnwb.mcp_server"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=120,
        )
        self.assertNotIn("cannot be directly executed", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_the_entry_point_is_a_module_not_an_unreachable_guard(self):
        import importlib.util

        self.assertIsNotNone(importlib.util.find_spec("jnwb.mcp_server.__main__"))
        init = (
            pathlib.Path(__file__).resolve().parents[1]
            / "jnwb" / "mcp_server" / "__init__.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("mcp.run()", init)


class TestTheDocumentedSurfaceIsTheLiveSurface(unittest.TestCase):
    """Three sources gave three different tool counts, and none of them asked the server.

    `docs/agents.md` said three, `mcp.list_tools()` returned four, and
    `jnwb.mcp_server.__all__` had five entries. A count written down is a claim about code
    that drifts silently; these read the registry.
    """

    def _live_tool_names(self):
        import asyncio

        from jnwb.mcp_server import mcp

        return {tool.name for tool in asyncio.run(mcp.list_tools())}

    def _documented_tool_names(self):
        page = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
        section = page.partition("## The MCP server")[2]
        self.assertTrue(section.strip(), "docs/agents.md has no MCP server section")
        # The tool table only: the page carries a skills table further down whose first
        # column is shaped the same way.
        table = section.partition("| Tool | Signature | Returns |")[2]
        table = table.partition("\n\n")[0]
        names = set(re.findall(r"^\| `(\w+)` \|", table, re.M))
        self.assertTrue(names, "the MCP tool table has no rows; this test checks nothing")
        return names

    def test_the_documented_table_lists_exactly_the_registered_tools(self):
        documented = self._documented_tool_names()
        live = self._live_tool_names()
        self.assertEqual(
            documented, live,
            f"documented {sorted(documented)} but the server registers {sorted(live)}",
        )

    def test_the_data_skill_names_every_registered_tool(self):
        """`jnwb-nwb-data` named two of the three tools after `prepare_signal_reference` landed."""
        skill = (ROOT / "skills" / "jnwb-nwb-data" / "SKILL.md").read_text(encoding="utf-8")
        unnamed = sorted(name for name in self._live_tool_names() if f"`{name}`" not in skill)
        self.assertEqual(unnamed, [], f"jnwb-nwb-data never names the MCP tools {unnamed}")

    def test_the_prose_count_matches_the_number_of_tools(self):
        page = (ROOT / "docs" / "agents.md").read_text(encoding="utf-8")
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
        stated = {
            words[m.lower()]
            for m in re.findall(r"\b(One|Two|Three|Four|Five|Six|two|three|four|five|six)\b"
                                r"(?= tools)", page)
        }
        self.assertTrue(stated, "no page prose states a tool count; this test checks nothing")
        self.assertEqual(
            stated, {len(self._live_tool_names())},
            f"the page says {sorted(stated)} tools; the server registers "
            f"{len(self._live_tool_names())}",
        )

    def test_the_package_exports_exactly_the_registered_tools_and_the_server(self):
        import jnwb.mcp_server as package

        exported = set(package.__all__)
        self.assertIn("mcp", exported, "the server object is not exported")
        self.assertEqual(
            exported - {"mcp"}, self._live_tool_names(),
            f"__all__ carries {sorted(exported - {'mcp'})} against a registry of "
            f"{sorted(self._live_tool_names())}",
        )

    def test_no_tool_writes_executable_code_into_the_package(self):
        """`add_tool` appended caller-supplied Python to a module inside the install.

        The gate was one environment variable, the validation was `ast.parse` plus "has a
        function in it", and nothing imported the file it wrote, so the tool it registered
        never loaded at any restart. Its absence is the contract now.
        """
        package_dir = pathlib.Path(
            importlib.import_module("jnwb.mcp_server").__file__
        ).parent
        for module in sorted(package_dir.glob("*.py")):
            source = module.read_text(encoding="utf-8")
            self.assertNotIn(
                "write_text", source,
                f"{module.name} writes into the installed package directory",
            )
        self.assertFalse(
            (package_dir / "custom_tools.py").exists(),
            "custom_tools.py is back; it is a write target inside the install",
        )


if __name__ == "__main__":
    unittest.main()
