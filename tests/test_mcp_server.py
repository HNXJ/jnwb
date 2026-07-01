import os
os.environ["ALLOW_DYNAMIC_TOOLS"] = "1"
import unittest
from pathlib import Path
from jnwb.mcp_server import inspect_nwb, get_event_codes_and_timings, prepare_signal_reference, add_tool

# Use a real NWB file from the analysis folder for testing
TEST_NWB = "D:/analysis/nwb/sub-C31o_ses-230831_rec.nwb"

class TestMCPServer(unittest.TestCase):
    def setUp(self):
        self.file_path = TEST_NWB
        
    def test_inspect_nwb_success(self):
        if not os.path.exists(self.file_path):
            self.skipTest(f"Test file not found: {self.file_path}")
            
        res = inspect_nwb(self.file_path)
        self.assertNotIn("error", res)
        self.assertIn("session_description", res)
        self.assertIn("identifier", res)
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
        if not os.path.exists(self.file_path):
            self.skipTest(f"Test file not found: {self.file_path}")
            
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
        if not os.path.exists(self.file_path):
            self.skipTest(f"Test file not found: {self.file_path}")
            
        res = get_event_codes_and_timings(self.file_path, event_group_path="/intervals/omission_glo_passive")
        self.assertNotIn("error", res)
        self.assertEqual(res["event_group_path"], "/intervals/omission_glo_passive")
        self.assertTrue(len(res["events"]) > 0)

    def test_prepare_signal_reference_success(self):
        if not os.path.exists(self.file_path):
            self.skipTest(f"Test file not found: {self.file_path}")
            
        # Standard acquisition LFP data path in Omission NWB files
        # Let's inspect inspect_nwb output to find a valid dataset path
        inspect_res = inspect_nwb(self.file_path)
        ds_paths = [ds["path"] for ds in inspect_res["datasets"]]
        
        # Look for ElectricalSeries/data or similar
        target_ds = None
        for p in ds_paths:
            if "ElectricalSeries" in p and p.endswith("data"):
                target_ds = p
                break
                
        if not target_ds:
            # Fall back to first available dataset
            target_ds = ds_paths[0] if ds_paths else None
            
        if not target_ds:
            self.skipTest("No datasets found in NWB to reference")
            
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
        if not os.path.exists(self.file_path):
            self.skipTest(f"Test file not found: {self.file_path}")
            
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
        # Backup the current custom_tools file content
        custom_tools_path = Path(__file__).parents[1] / "jnwb" / "mcp_server" / "custom_tools.py"
        original_content = custom_tools_path.read_text()
        
        new_tool_code = '''
def test_temp_dummy_tool(a: int) -> str:
    """A dummy test tool."""
    return f"val_{a}"
'''
        try:
            res = add_tool(new_tool_code)
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res.get("added_tool"), "test_temp_dummy_tool")
            
            # Check if it was written to custom_tools.py
            updated_content = custom_tools_path.read_text()
            self.assertIn("def test_temp_dummy_tool", updated_content)
            self.assertIn("@mcp.tool()", updated_content)
            
            # Try adding again to verify duplicate error
            dup_res = add_tool(new_tool_code)
            self.assertIn("error", dup_res)
            self.assertEqual(dup_res["error_type"], "DuplicateTool")
            
        finally:
            # Revert changes to keep repo clean
            custom_tools_path.write_text(original_content)

if __name__ == "__main__":
    unittest.main()
