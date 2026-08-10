# `jnwb` — Omission analysis package

Python package for the **Omission** project: hierarchical visual prediction and omission
responses recorded across V1, V2, V3, V4, MT, MST, TEO, FEF, PFC. Everything in this repo is
built on `jnwb`; the rest of the tree is its inputs, outputs, and doctrine.

Active research code. Treat confirmatory inference (family-wise FDR, nested-CV decoding,
Granger diagnostics) as work in progress, and re-run tests rather than trusting counts in docs.

---

## Install

```bash
pip install -e ".[test]"
```

## Paths — do this first after any drive remap

Repo-internal paths resolve from the package's own location and always work. External data
roots live on a separate volume and are set by environment variable:

| Root | Env var | Fallback |
|---|---|---|
| NWB session files | `OMISSION_NWB_DIR` | `D:/nwb/omission` |
| All derived data | `OMISSION_ANALYSIS_DIR` | `D:/analysis` |
| — TFR arrays | `OMISSION_TFR_DIR` | `<analysis>/tfr_arrays` |
| — metadata sidecars | `OMISSION_META_DIR` | `<analysis>/metadata` |
| — connectivity databases | `OMISSION_CONNDB_DIR` | `<analysis>/connectivity_databases` |

Two volumes, one rule: **NWBs are read-only inputs under `D:/nwb/omission`; everything the
pipeline produces goes under `D:/analysis`, never into the repo.** `D:/nwb/mglo/` is a
different experiment — do not glob across `D:/nwb`.

```python
import jnwb as oa
oa.paths.describe()   # every root + whether it currently resolves
```

If a root shows `exists: false`, set its env var — do not edit source, and do not write a new
absolute literal into a script. See [`jnwb/paths.py`](jnwb/paths.py).

Repo-internal paths (`REPO_ROOT`, `outputs_dir()`, `artifacts_dir()`, `layer_masks_path()`)
derive from the package's own location and are not configurable.

---

## Quick start

```python
import jnwb as oa

session = oa.read(oa.paths.nwb_dir() / "sub-C31o_ses-230630_rec.nwb")
units   = session.find_single_units(quality="stable_plus", area="V1")
res     = session.raster_suite(unit_id=2.0, condition="AAAB")
res["figure"].savefig("outputs/raster.png")
```

`oa.read()` returns an `OmissionSession` — the single object every analysis hangs off.
`oa.batch_read(dir)` returns a list of them.

---

## Module map

The public surface is `jnwb/__init__.py` (`__all__`, 117 symbols). Modules, by what they do:

**Session I/O and addressing**
| Module | Role |
|---|---|
| `session.py` | `OmissionSession` — epoching, unit queries, LFP/MUAe access, plot shortcuts |
| `paths.py` | Repo and data root resolution; the only place absolute paths live |
| `addressing.py` | Peak-channel → area mapping, depth → layer classification |
| `ontology.py`, `factories.py` | `Dataset`/`AlignedDataset`/`Question`/`Result` objects and their constructors |
| `metadata.py`, `diagnostics.py` | Unit tables, SNR, quality tiers, session audits |

**Signal analysis**
| Module | Role |
|---|---|
| `spectral.py` | Band power, cross-area coherence, spectrolaminar mapping |
| `complex_tfr.py` | Complex TFR preprocessing and complex-valued metrics |
| `spiking.py` | Response metrics, omission-response classification, phase locking |
| `unit_classification.py` | Shuffle-controlled S+ / S− / O+ classification, O++ templates |
| `connectivity.py` | Granger, spectral Granger, PSI, transfer entropy, mutual information |
| `jrsa.py` | Joint Relationship & Spectral Analysis — unified RSA engine |

**Decoding and population**
| Module | Role |
|---|---|
| `decoding.py` | SVM stimulus-identity and omission-presence decoders |
| `bilinear.py` | Rank-K matrix-factorized logistic regression for (N×T) trials |
| `nam.py` | Neural Additive Model with per-unit attribution |
| `omission_identity.py` | Omission-identity decoding engine and condition mappings |
| `trajectory.py`, `gpu_pca.py` | Population trajectories via GPU SVD |

**Statistics, figures, reports**
| Module | Role |
|---|---|
| `statistics.py` | `StatisticalAnalysis` — paired parametric + non-parametric + effect size |
| `analyzers.py` | `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer`, `StatisticalAnalysis` |
| `functions.py` | 22 canonical top-level functions (`tfr_*`, `raster_plot`, `pie_charts`, …) |
| `viz.py`, `visual_qc.py` | Publication figures and visual QC |
| `sequence_layout.py` | Omission sequence layout as vector objects |
| `report.py`, `markdown_report.py` | Session report suites, multi-page markdown with embedded SVG |
| `mcp_server/` | stdio MCP server: `inspect_nwb`, `get_event_codes_and_timings`, `prepare_signal_reference`, `add_tool` |

---

## Repository layout

| Path | Contents |
|---|---|
| `jnwb/` | The package (above) |
| `tests/` | Pytest suite — run it, don't trust pass counts in docs |
| `scripts/` | 57 one-off analysis and aggregation scripts; outputs land in `outputs/`. `scripts/historical/confounded/` holds 12 decoding scripts quarantined 2026-08-10 for invalid/ungrouped CV — do not use as empirical sources, see `artifacts/.lab/agent-harness-audit-20260810.json` |
| `notebooks/` | `suite_01`–`suite_08` figure suites. `notebooks/historical/reproducibility_master_pipeline` is quarantined (asserts the retracted 4.90%/421/8597 census) — do not run as a current reproducibility check |
| `outputs/` | Derived data and figure assets |
| `context/` | Manuscript drafts, figures, inventory — `context/docs/CONTEXT.md` is authoritative |
| `artifacts/` | `data/` catalogs, `.lab/` knowledge graph nodes |
| `legacy/` | Archived context, scripts, tests — historical, superseded |

---

## Before you change anything

- **`CLAUDE.md`** — repo doctrine: footguns, band definitions, verification checks that caught
  real errors, the placeholder-figure rule.
- **`context/docs/CONTEXT.md`** — authoritative project context: paradigm, corpus, data topology,
  analysis contracts, current findings with receipts.
- **`.claude/skills/jnwb-*`** — task-scoped API guides (core, spiking, tfr, population,
  statistics, metadata, visualization, functional-connectivity, jrsa).
- **`artifacts/.lab/`** — the knowledge graph. Read before, write after.

Prefer `artifacts/data/nwb_catalog.json` and `artifacts/data/session_readiness.csv` over any
session count written into prose.
