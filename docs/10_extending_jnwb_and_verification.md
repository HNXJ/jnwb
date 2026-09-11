# 10. Extending `jnwb` & verification (pointer)

This page is a short pointer. The maintained developer guide is **[11. Extending and development](11_extending_and_development.md)** — API changes, release gates, and how to add a function without breaking the public contract.

## Verification commands

```bash
python scripts/harness_gate.py   # gates 1–12
python -m pytest tests/ -q
mkdocs build --strict
python scripts/release_gate.py   # before tagging only
```

## Domain packages

Keep `jnwb/` generic and dataset-agnostic. Experiment-specific condition codes, session layouts, and findings belong in a **downstream project package** that imports `jnwb`, not inside the library tree.

For MCP inspection tools, run `python -m jnwb.mcp_server` and see `jnwb.mcp_server.__all__` for registered tools.
