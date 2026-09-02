import os
os.environ["ALLOW_DYNAMIC_TOOLS"] = "1"
import unittest
import tempfile
import pathlib
from datetime import datetime, timezone
import pytest
import numpy as np
import pynwb

pytest.importorskip("mcp")
from jnwb.mcp_server import inspect_nwb, get_event_codes_and_timings, prepare_signal_reference, add_tool


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

        epochs = pynwb.epoch.TimeIntervals(name="omission_glo_passive", description="events")
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
        self.assertEqual(res["session_description"], "Synthetic session for MCP testing")
        self.assertEqual(res["identifier"], "SYNTH_MCP_001")
        self.assertIn("session_start_time", res)
        self.assertIn("groups", res)
        self.assertIn("datasets", res)
        self.assertIn("neurodata_types", res)

        # Verify datasets schema
        self.assertTrue(len(res["datasets"]) > 0)
        for ds in res["datasets"]:
            self.assertIn("path", ds)
            self.assertIn("dtype", ds)
            self.assertIn("shape", ds)
            self.assertIsInstance(ds["shape"], list)

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
        res = get_event_codes_and_timings(self.file_path, event_group_path="/intervals/omission_glo_passive")
        self.assertNotIn("error", res)
        self.assertEqual(res["event_group_path"], "/intervals/omission_glo_passive")
        self.assertEqual(len(res["events"]), 2)

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
        res = add_tool("def invalid_syntax(:")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "ParseError")

    def test_add_tool_no_function(self):
        res = add_tool("x = 42\nprint(x)")
        self.assertIn("error", res)
        self.assertEqual(res["error_type"], "ParseError")

    def test_add_tool_success_and_cleanup(self):
        custom_tools_path = pathlib.Path(__file__).parents[1] / "jnwb" / "mcp_server" / "custom_tools.py"
        original_content = custom_tools_path.read_text(encoding="utf-8")

        new_tool_code = '''
def test_temp_dummy_tool(a: int) -> str:
    """A dummy test tool."""
    return f"val_{a}"
'''
        try:
            res = add_tool(new_tool_code)
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res.get("added_tool"), "test_temp_dummy_tool")

            updated_content = custom_tools_path.read_text(encoding="utf-8")
            self.assertIn("def test_temp_dummy_tool", updated_content)
            self.assertIn("@mcp.tool()", updated_content)

            # Try adding again to verify duplicate error
            dup_res = add_tool(new_tool_code)
            self.assertIn("error", dup_res)
            self.assertEqual(dup_res["error_type"], "DuplicateTool")

        finally:
            custom_tools_path.write_text(original_content, encoding="utf-8")


class TestMCPServerEntrypoint(unittest.TestCase):
    def test_server_module_exposes_fastmcp_instance(self):
        from jnwb.mcp_server import server
        from mcp.server.fastmcp import FastMCP

        self.assertIsInstance(server.mcp, FastMCP)
        self.assertEqual(server.mcp.name, "jnwb-mcp-server")


if __name__ == "__main__":
    unittest.main()
