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
