"""Entry point for ``python -m jnwb.mcp_server``.

``__init__.py`` used to end with ``if __name__ == "__main__": mcp.run()``, which cannot run:
``python -m jnwb.mcp_server`` imports the package as ``jnwb.mcp_server`` and then looks for a
``__main__`` submodule, so the guard was never true and the documented command failed with
"'jnwb.mcp_server' is a package and cannot be directly executed".
"""

from __future__ import annotations

from jnwb.mcp_server import mcp


def main() -> None:
    """Serve the jnwb MCP tools over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
