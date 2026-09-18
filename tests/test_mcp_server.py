"""Tests for the jnwb MCP server tools.

This file used to set ``ALLOW_DYNAMIC_TOOLS=1`` in ``os.environ`` at import. That is
process-wide and was never undone, so importing it took the variable from unset to ``"1"``
for every test that ran afterwards -- and left the server's own security gate untested,
because with the variable forced on, `add_tool` could never take its refusal path. The
variable is now set per test and restored, including back to absent.
"""
import hashlib
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pynwb
import pytest

pytest.importorskip("mcp")
from jnwb.mcp_server import (  # noqa: E402
    add_tool,
    get_event_codes_and_timings,
    inspect_nwb,
    meta_tools,
    prepare_signal_reference,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: `add_tool` writes next to `meta_tools`, so this is resolved the same way the code under
#: test resolves it rather than by spelling the path out a second time.
CUSTOM_TOOLS = pathlib.Path(meta_tools.__file__).parent / "custom_tools.py"

#: Captured at import, before any test in this file runs, so a test that modifies the
#: tracked module is visible even when it is the cleanup that failed.
_CUSTOM_TOOLS_SHA_AT_IMPORT = hashlib.sha256(CUSTOM_TOOLS.read_bytes()).hexdigest()

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

    def test_add_tool_syntax_error(self):
        with patch.dict(os.environ, {"ALLOW_DYNAMIC_TOOLS": "1"}):
            res = add_tool("def invalid_syntax(:")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "ParseError")

    def test_add_tool_no_function(self):
        with patch.dict(os.environ, {"ALLOW_DYNAMIC_TOOLS": "1"}):
            res = add_tool("x = 42\nprint(x)")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "ParseError")

    def test_add_tool_refuses_when_dynamic_registration_is_disabled(self):
        """The refusal path, which had no test while the variable was forced on.

        `add_tool` writes executable code into the installed package, so its gate is the
        only thing standing between a prompt and an import-time side effect. Setting
        ALLOW_DYNAMIC_TOOLS=1 at module import meant this branch was unreachable for the
        whole file.
        """
        with patch.dict(os.environ):
            os.environ.pop("ALLOW_DYNAMIC_TOOLS", None)
            res = add_tool(DUMMY_TOOL_CODE)
        self.assertEqual(res["error_type"], "SecurityRestriction")
        self.assertEqual(
            hashlib.sha256(CUSTOM_TOOLS.read_bytes()).hexdigest(),
            _CUSTOM_TOOLS_SHA_AT_IMPORT,
            "a refused registration still wrote to the tracked module",
        )

    def test_add_tool_appends_and_rejects_a_duplicate(self):
        """Exercises `add_tool` against an isolated copy, not the tracked module.

        This used to append to `jnwb/mcp_server/custom_tools.py` and restore it in a
        `finally`. A `finally` survives a failing assertion but not a kill or a timeout:
        interrupted between the write and the restore, the run left
        `M jnwb/mcp_server/custom_tools.py` with 110 bytes appended. `pytest-xdist` is
        declared, so two workers would also race on that one file. The restore was byte
        exact only by luck -- `read_text` plus `write_text` round-trips through universal
        newlines, so it held because that file is CRLF and would have rewritten every
        line ending had it been LF.

        `add_tool` resolves its target as `Path(__file__).parent / "custom_tools.py"` at
        call time, so pointing the module at a temporary directory runs the same code --
        duplicate check and decorator insertion included -- with nothing tracked in reach.
        """
        before = CUSTOM_TOOLS.read_bytes()

        with tempfile.TemporaryDirectory() as tmp:
            sandbox = pathlib.Path(tmp)
            (sandbox / "custom_tools.py").write_bytes(before)

            with patch.object(meta_tools, "__file__", str(sandbox / "meta_tools.py")):
                with patch.dict(os.environ, {"ALLOW_DYNAMIC_TOOLS": "1"}):
                    res = add_tool(DUMMY_TOOL_CODE)
                    self.assertEqual(res.get("status"), "success")
                    self.assertEqual(res.get("added_tool"), "test_temp_dummy_tool")

                    updated = (sandbox / "custom_tools.py").read_text(encoding="utf-8")
                    self.assertIn("def test_temp_dummy_tool", updated)
                    self.assertIn("@mcp.tool()", updated)

                    dup_res = add_tool(DUMMY_TOOL_CODE)
                    self.assertIn("error", dup_res)
                    self.assertEqual(dup_res["error_type"], "DuplicateTool")

        self.assertEqual(
            CUSTOM_TOOLS.read_bytes(), before,
            "the tracked custom_tools.py was modified by a test that no longer writes it",
        )


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


if __name__ == "__main__":
    unittest.main()


class TestThisFileLeavesTheProcessAndTheTreeAsItFoundThem(unittest.TestCase):
    """The two contamination classes the 0.2.5 audit found in this file.

    Both were real. Importing the module took ALLOW_DYNAMIC_TOOLS from unset to "1"
    process-wide, and `add_tool`'s success test appended to a tracked module with a
    `finally` as its only protection -- killed between the write and the restore, a run
    left `M jnwb/mcp_server/custom_tools.py`, 101 bytes to 211.
    """

    def test_importing_this_module_does_not_enable_dynamic_tool_registration(self):
        """Measured in a child interpreter, so it holds wherever the assignment sits.

        The variable is stripped from the child's environment first, so this asserts the
        import does not set it rather than that it happens to be absent here.
        """
        script = (
            "import os, sys\n"
            f"sys.path.insert(0, {str(ROOT)!r})\n"
            f"sys.path.insert(0, {str(ROOT / 'tests')!r})\n"
            "print(repr(os.environ.get('ALLOW_DYNAMIC_TOOLS')))\n"
            "import test_mcp_server\n"
            "print(repr(os.environ.get('ALLOW_DYNAMIC_TOOLS')))\n"
        )
        env = {k: v for k, v in os.environ.items() if k != "ALLOW_DYNAMIC_TOOLS"}
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=300,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        lines = proc.stdout.strip().splitlines()
        self.assertEqual(len(lines), 2, f"unexpected child output: {proc.stdout!r}")
        self.assertEqual(lines[0], "None", "the child interpreter already had it set")
        self.assertEqual(
            lines[1], "None",
            "importing this module enabled dynamic tool registration for every test "
            "that runs after it, and hid the security gate's refusal path",
        )

    def test_the_tracked_custom_tools_module_is_byte_identical(self):
        """bytes before == bytes after, for the file a test used to rewrite in place."""
        self.assertEqual(
            hashlib.sha256(CUSTOM_TOOLS.read_bytes()).hexdigest(),
            _CUSTOM_TOOLS_SHA_AT_IMPORT,
            f"{CUSTOM_TOOLS} changed while this file's tests ran",
        )
