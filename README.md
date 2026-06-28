# Omission: Single-Unit & Spectral Analysis

Production repository for the **Omission** project — hierarchical visual prediction and omission response in V1, PFC, MT/MST, and FEF across 13 recording sessions.

## 📁 Structure

**Core Analysis Module:**
- **`jnwb/`** — Production-grade NWB analysis framework (includes built-in MCP server for Claude integration)
  - `session.py` — Session loader, NWB access, area/layer enrichment
  - `functions.py` — Spike extraction, rasters, PSTHs, population analysis
  - `addressing.py` — Unit/channel mapping, addressing schemes
  - `mcp_server.py` — Stdio-based Model Context Protocol server exposing inspect_nwb, get_event_codes_and_timings, prepare_signal_reference, and add_tool
  - `tests/` — Validation suite (real NWB data)

**Project Context & Documentation:**
- **`context/info/`** — Authoritative data topology, NWB event model, condition groups
- **`context/sessions/`** — Per-session logs and maps

**Infrastructure & Outputs:**
- **`.agents/skills/`** — Agent skill definitions (spectral-relations pipeline, NWB-IO, spiking, etc.)
- **`outputs/`** — Analysis results, figures, archive, documentation
  - `publication_figures/` — Grand database, waveforms, layer masks
  - `archive/` — Legacy code, notebooks, execution logs (refactorization in progress)
  - `docs/` — Markdown handouts and specifications

**Testing & Config:**
- **`tests/`** — Unit tests for jnwb functions
- `setup.py`, `pyproject.toml` — Python package config

## 🚀 Quick Start

```python
from jnwb import OmissionSession

# Load session with area/layer enrichment
session = OmissionSession("sub-C31o_ses-230823_rec.nwb")

# Get epochs for a condition
epochs = session.get_epochs(
    phase=2,  # p1 (stimulus_number=2)
    condition_numbers=[1, 2],  # AAAB condition
    correct=True
)

# Extract spikes
spike_times = session.get_spike_times(unit_id=15)

# Plot raster
from jnwb.functions import raster_plot
raster_plot(session, unit_id=15, epochs=epochs)
```

## 📊 Current Status

**Real-data validation (13 NWB sessions):**
- ✅ 6/11 core functions validated
- ✅ Area/layer enrichment via peak_channel_id mapping
- ⚠️ Epoch filtering: type mismatch fix pending
- 📋 Milestone A: 87→90 (raster/PSTH unlock after epoch fix)
- 📋 Milestone B: 90→92 (spectral pipeline completion)

**Refactorization:**
- See `outputs/REFACTORIZATION_CLASSIFICATION.md` for legacy code assessment (X/Y/Z/W system)

## 📖 Documentation

- **[COOKBOOK.md](COOKBOOK.md)** — Working code + real output for every `jnwb` function (spiking, LFP, population, statistics)
- **MCP Server**: Refer to the MCP Server section in the [jnwb README](jnwb/README.md#mcp-server-setup) for setting up tools for Claude.
- **Data topology**: `context/info/07_authoritative_data_topology_single_units.md`
- **Figure provenance**: `context/info/08_pie_charts_summary_provenance.md`
- **Agent skills**: `.agents/skills/*/SKILL.md`
