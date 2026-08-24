# `omission` — Omission analysis project

Project package for the **Omission** experiment: hierarchical visual prediction and omission
responses recorded across V1, V2, V3, V4, MT, MST, TEO, FEF, PFC. Built on the generic `jnwb`
library at the repo root; everything in this folder is specific to this experiment's task
structure (conditions, slots, S+/S-/O+ classification, decoding, connectivity, viz) or its data.

Active research code. Treat confirmatory inference (family-wise FDR, nested-CV decoding,
Granger diagnostics) as work in progress, and re-run tests rather than trusting counts in docs.

---

## Install

From the repo root:

```bash
pip install -e ".[test]"
```

## Paths — do this first after any drive remap

Repo-internal paths resolve from the `jnwb` package's own location and always work. External
data roots live on a separate volume and are set by environment variable:

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
import omission as oa
oa.paths.describe()   # every root + whether it currently resolves
```

If a root shows `exists: false`, set its env var — do not edit source, and do not write a new
absolute literal into a script. See [`jnwb/paths.py`](../jnwb/paths.py).

Repo-internal paths (`REPO_ROOT`, `outputs_dir()`, `artifacts_dir()`, `layer_masks_path()`)
derive from the `jnwb` package's own location and are not configurable.

---

## Quick start

```python
import omission as oa

session = oa.read(oa.paths.nwb_dir() / "sub-C31o_ses-230630_rec.nwb")
units   = session.find_single_units(quality="stable_plus", area="V1")
res     = session.raster_suite(unit_id=2.0, condition="AAAB")
res["figure"].savefig("outputs/raster.png")
```

`oa.read()` returns an `OmissionSession` — the single object every analysis hangs off.
`oa.batch_read(dir)` returns a list of them.

---

## Module map

The public surface is `omission/__init__.py` (`__all__`, matches the pre-2026-08-19 flat
`jnwb` surface exactly). Modules, by what they do:

**Session I/O and addressing**
| Module | Role |
|---|---|
| `jnwb_ext/session.py` | `OmissionSession` — epoching, unit queries, LFP/MUAe access, plot shortcuts |
| `jnwb_ext/metadata.py`, `jnwb_ext/diagnostics.py` | Unit tables, SNR, quality tiers, session audits |
| (generic, from `jnwb/`) `paths.py`, `addressing.py`, `ontology.py` | Path resolution, peak-channel→area mapping, `Dataset`/`Question`/`Result` objects |
| `jnwb_ext/factories.py` | Constructors bridging `OmissionSession` to the generic ontology objects |

**Signal analysis**
| Module | Role |
|---|---|
| `jnwb_ext/spectral.py` | Band power, cross-area coherence, spectrolaminar mapping (omission band conventions) |
| `jnwb_ext/spiking.py` | Response metrics, omission-response classification, phase locking |
| `jnwb_ext/unit_classification.py` | Shuffle-controlled S+ / S− / O+ classification, O++ templates |
| `jnwb_ext/connectivity.py` | Granger, spectral Granger, PSI, transfer entropy, mutual information |
| (generic, from `jnwb/`) `jrsa.py` | Joint Relationship & Spectral Analysis — unified RSA engine |

**Decoding and population**
| Module | Role |
|---|---|
| `jnwb_ext/decoding.py` | SVM stimulus-identity and omission-presence decoders |
| `jnwb_ext/omission_identity.py` | Omission-identity decoding engine and condition mappings |
| (generic, from `jnwb/`) `trajectory.py`, `gpu_pca.py` | Population trajectories via GPU SVD |

**Statistics, figures, reports**
| Module | Role |
|---|---|
| (generic, from `jnwb/`) `statistics.py`, `analyzers.py` | `StatisticalAnalysis`, `TFRAnalyzer`, `UnitAnalyzer`, `PopulationAnalyzer` |
| `jnwb_ext/functions.py` | Canonical top-level functions (`tfr_*`, `raster_plot`, `pie_charts`, …) |
| `jnwb_ext/viz.py`, (generic) `jnwb/visual_qc.py` | Publication figures and visual QC |
| `jnwb_ext/sequence_layout.py` | Omission sequence layout as vector objects |
| `jnwb_ext/report.py` | Session report suites, multi-page markdown with embedded SVG |

---

## Repository layout (this folder)

| Path | Contents |
|---|---|
| `jnwb_ext/` | Task-specific extension modules (above) |
| `tests/` | Pytest suite for this project's tests — run it, don't trust pass counts in docs |
| `scripts/` | One-off analysis and aggregation scripts; outputs land in `outputs/`. `scripts/historical/confounded/` holds decoding scripts quarantined 2026-08-10 for invalid/ungrouped CV — do not use as empirical sources, see `artifacts/.lab/agent-harness-audit-20260810.json` |
| `notebooks/` | Figure suites. `notebooks/historical/reproducibility_master_pipeline` is quarantined (asserts the retracted census) — do not run as a current reproducibility check |
| `outputs/` | Derived data and figure assets |
| `context/` | Manuscript drafts, figures, inventory — `context/PROJECT_STATE.md` is authoritative |
| `artifacts/` | `data/` catalogs, `.lab/` knowledge graph nodes |
| `legacy/` | Archived context, scripts, tests — historical, superseded |

---

## Before you change anything

- **`CLAUDE.md`** (repo root) and this folder's project-doctrine section — footguns, band
  definitions, verification checks that caught real errors, the placeholder-figure rule.
- **`context/PROJECT_STATE.md`** — authoritative current scientific/repository state: what's
  established, superseded, or blocked, with every number dated and re-resolvable.
  **`context/EVIDENCE_ARCHITECTURE.md`** — the semantics of evidence: how a measurement becomes a
  claim and what each level of claim costs. (`context/docs/CONTEXT.md` does not exist; an earlier
  version of this README pointed there.)
- **`context/00_paradigm_and_task.md` through `context/09_conflicts_and_flagged_discrepancies.md`**
  — a numbered domain-by-domain reference chain (generated 2026-08-17): paradigm/task, corpus
  topology, **`02_jnwb_api_reference.md`** (the jnwb bridge — self-flagged stale after
  2026-08-19's repo split, module paths mechanically corrected), classification pipelines, signal
  processing, figures/pipelines, statistics, skills/memory, open items, and
  **`09_conflicts_and_flagged_discrepancies.md`** (the one-authority-per-fact audit — still-open
  HIGH-severity items live there, check it before trusting a number this README or PROJECT_STATE.md
  doesn't itself carry a date on). Linked here 2026-08-24 after being found unreachable from both
  this README and PROJECT_STATE.md.
- **`omission/.claude/skills/`** — task-scoped API guides (`omission-*`, `labyrinth`, `manuscript`).
- **`artifacts/.lab/`** — the knowledge graph. Read before, write after.

Prefer `artifacts/data/nwb_catalog.json` and `artifacts/data/session_readiness.csv` over any
session count written into prose.
