# `jnwb`

Dataset-agnostic Python library for NWB (Neurodata Without Borders) electrophysiology analysis:
session I/O, addressing (channel→area, depth→layer), representational similarity analysis (JRSA),
TFR accumulation/compression, generic statistics, and visual QC.

`jnwb` makes no assumptions about task structure, condition codes, or experiment design. For a
worked example of building a full project on top of it — including a task-specific extension
package, scripts, notebooks, and a manuscript pipeline — see [`omission/`](omission/README.md),
this repo's native large-dataset example project.

---

## Install

```bash
pip install -e ".[test]"
```

## Paths — do this first after any drive remap

Repo-internal paths (`REPO_ROOT`, `outputs_dir()`, `artifacts_dir()`) resolve from the package's
own location and always work. External data roots live on a separate volume and are set by
environment variable — see [`jnwb/paths.py`](jnwb/paths.py) for the full list and defaults.

```python
import jnwb
jnwb.paths.describe()   # every root + whether it currently resolves
```

If a root shows `exists: false`, set its env var — do not edit source, and do not write a new
absolute literal into a script.

---

## Quick start

```python
import jnwb

result = jnwb.jrsa(x1, x2, metric='rsa', stats=True)
result.summary()
result.plot()
```

---

## Module map

The public surface is `jnwb/__init__.py` (`__all__`).

| Module | Role |
|---|---|
| `paths.py` | Repo and data root resolution; the only place absolute paths live |
| `addressing.py` | Peak-channel → area mapping, depth → layer classification |
| `ontology.py`, `jrsa.py` | `Dataset`/`AlignedDataset`/`Question`/`Result` objects; unified RSA engine |
| `statistics.py`, `analyzers.py` | `StatisticalAnalysis`, `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer` |
| `tfr_accumulator.py`, `compression.py` | Poolable TFR summary statistics; NWB fp32 compression |
| `trajectory.py`, `gpu_pca.py` | Population trajectories via GPU SVD |
| `visual_qc.py` | Generic visual QC plotting |
| `bilinear.py`, `nam.py`, `permutation.py` | Generic modeling/statistical primitives |
| `mcp_server/` | stdio MCP server: `inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`, `add_tool` |

Task-specific functionality (condition codes, unit classification, decoding, connectivity,
figure suites) lives in [`omission/jnwb_ext/`](omission/README.md), not here.

---

## MCP server

`jnwb` includes a stdio Model Context Protocol server for NWB inspection from Claude and other
MCP-compatible clients: `inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`,
`add_tool`. Depends on `mcp`, `h5py`, `pynwb`, `pandas`, `numpy` (installed via `pip install -e .`).

```bash
python -m jnwb.mcp_server
```

```json
{
  "mcpServers": {
    "jnwb-mcp-server": {
      "command": "python",
      "args": ["-m", "jnwb.mcp_server"]
    }
  }
}
```

---

## Repository layout

| Path | Contents |
|---|---|
| `jnwb/` | The library (above) |
| `tests/` | Pytest suite for the generic library — run it, don't trust pass counts in docs |
| `omission/` | The example project built on `jnwb` — see [`omission/README.md`](omission/README.md) |
| `.claude/skills/` | Task-scoped API guides |

---

## Before you change anything

- **`CLAUDE.md`** — repo doctrine: library invariants, footguns, verification checks that caught
  real errors.
- **`omission/.claude/skills/`** — task-scoped API guides (`omission-data`, `omission-signal`,
  `omission-spiking`, `omission-statistics`, `omission-figures`, `manuscript`, `labyrinth`). There
  is no repo-root `.claude/skills/` — `jnwb/` itself has no dedicated skill yet (see
  `numerical-computing` / `biophysical-modeling`, which are general-purpose, not jnwb-specific).
