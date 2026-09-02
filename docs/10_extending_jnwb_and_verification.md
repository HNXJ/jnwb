# 10. Extending `jnwb`, Domain Packages & Verification Gates

This document describes best practices for building domain-specific analysis pipelines on top of `jnwb`, structuring package facades, and integrating automated regression gates.

---

## 1. Building Domain-Specific Projects on `jnwb`

`jnwb` is designed as the generic mathematical engine for high-level neurophysiology workflows.

### Architecture Pattern: The Domain Package Facade

When analyzing an experiment with unique trial sequences, task conditions, or unit taxonomy rules:
1. Keep `jnwb/` generic, frozen, and dataset-agnostic.
2. Build an experiment-specific package (e.g., `omission/`) that imports `jnwb` and exposes specialized functions.
3. Provide a unified package facade (e.g. `import omission as oa`) that surfaces both generic `jnwb` capabilities and project-specific extensions.

```mermaid
graph TD
    subgraph "Generic Foundation (jnwb/)"
        JCore[jnwb.jrsa / jnwb.spectral / jnwb.statistics / jnwb.connectivity]
    end

    subgraph "Downstream Project / Experiment"
        ExtLayout[Task Structure & Sequence Layouts]
        ExtClass[Custom Unit Classification Taxonomies]
        ExtFacade[Project Pipeline Scripts]
    end

    JCore --> ExtClass
    JCore --> ExtFacade
    ExtLayout --> ExtFacade
    ExtClass --> ExtFacade
```

---

## 2. Automated Verification Gates & Regression Infrastructure

To prevent architectural drift and coordinate corruption across collaborative workflows, `jnwb` relies on automated, deterministic gates:

### Automated Test Matrix
1. **Frozen Boundary Gate (`tests/test_jnwb_frozen_boundary.py`)**: Asserts that `jnwb` contains zero unauthorized imports from downstream project folders.
2. **Skill Tree Consolidation (`tests/test_skill_tree_consolidation.py`)**: Guards against duplicate or conflicting skill trees.
3. **Reproducibility Regressions (`tests/test_batch_a_regressions.py`)**: Asserts cross-process seed determinism, RNG isolation, and mathematical latency invariants.

### Running Verification Gates

```bash
# Execute pre-flight verification gate
python scripts/harness_gate.py

# Run full core test suite
pytest -v tests/
```

---

## 3. Appendix: Developer Tooling & MCP Server (`jnwb/mcp_server`)

For AI assistants and IDE integrations, `jnwb` includes local Model Context Protocol (MCP) server tooling in `jnwb/mcp_server`. These tools operate as developer-facing inspection sidecars and remain strictly isolated from scientific runtime imports:
- `read_nwb_metadata`: Inspects session headers and channel counts.
- `query_units_by_area`: Fast lookup of filtered unit tables.
- `compute_quick_psth`: Instant PSTH calculation for interactive visualization.
