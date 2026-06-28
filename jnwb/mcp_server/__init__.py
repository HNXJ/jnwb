from jnwb.mcp_server.server import mcp
from jnwb.mcp_server.nwb_tools import inspect_nwb, prepare_signal_reference
from jnwb.mcp_server.event_tools import get_event_codes_and_timings
from jnwb.mcp_server.meta_tools import add_tool

__all__ = [
    "mcp",
    "inspect_nwb",
    "prepare_signal_reference",
    "get_event_codes_and_timings",
    "add_tool"
]

if __name__ == "__main__":
    mcp.run()
