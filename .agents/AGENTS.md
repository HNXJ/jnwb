# Omission — Project AGENTS.md

Inherits the global working agreement:
`C:\Users\nejath\.gemini\config\AGENTS.md`

This file **specializes** omission. If it conflicts with global principles, flag the conflict;
do not silently override Core Principles / Verify Claims / No silent synthetic science.

**User address:** Hamm.  
**Role:** systems neuroscience (electrophysiology, NWB, spike + LFP, omission paradigm).

---

## What this repo is

- Package: `jnwb` — load/analyze/plot omission NWB sessions.
- Publication figures and suites: `scripts/`, `notebooks/suite_*.ipynb`, `outputs/`.
- Backlog: PRP under `artifacts/` (see global AGENTS + `.cursor/rules/prp-protocol.mdc`).
- Palette: `.cursor/rules/omission-palette.mdc` (canonical hex indices).

## Data topology (verify; do not memorize stale counts)

| Kind | Location |
|------|----------|
| Raw NWB | `D:/analysis/nwb/` (+ `short-nwb/`) |
| Catalog | `artifacts/data/nwb_catalog.json` (regenerate: `scripts/build_nwb_catalog.py`) |
| Sidecars | `D:/workspace/data/metadata/{stem}/` (`electrodes.csv`, `units.csv`, `events.csv`, `h5_paths.json`, `probe_areas.json`) |
| Readiness | `artifacts/data/session_readiness.csv` (`scripts/build_session_readiness.py`) |
| Precomputed TFR | `D:/workspace/data/tfr_arrays/` (`{session_prefix}-{A\|B\|C}-{area}-{cond}.npy`) |
| Array caches | `D:/workspace/data/nwb-arrays/` (optional materializations) |

**Env overrides:** `OMISSION_NWB_DIR`, `OMISSION_TFR_DIR`, `OMISSION_META_DIR`, `OMISSION_SESSION`.

**Inventory reality (2026-07-09 receipt):** 17 NWB files (C31o / V182o / V198o). V182o sessions
exist as NWB; **TFR npy for V182o may be absent** — check `session_readiness.csv` before claiming
spectrogram/trace suites.

## Hard scientific footguns (omission-specific)

1. **`tfr_from_preprocessed` must not silently return mock data.** If TFR files are missing,
   fail or label synthetic. Wire to `OMISSION_TFR_DIR` / readiness gates.
2. **V182o PyNWB Device metadata can break `pynwb` construct.** Prefer **h5py** for LFP/pupil
   (`acquisition/probe_*_lfp/...`) and sidecars; do not require a full clean PyNWB load for
   metadata indexing.
3. **Dual-area probes:** label `"Y, Z"` / `"Y/Z"` → channels **1–64 = Y**, **65–128 = Z**.
   Bare `"V3"` alone → `(V3d, V3a)`. Dual `"V3, V1"` keeps **V3** as the first half (does not
   expand to V3d/V3a). Canonical helpers: `jnwb.sequence_layout.parse_probe_areas`,
   `channel_slice_for_area`.
4. **Sequence timing (ms, p1 = 0):** fx=-500; p1=0; d1=531; p2=1031; … full span **4624 ms**
   (−500…4124). Layout shapes: `jnwb.sequence_layout` (Plotly vector objects, not a background PNG).
5. **Intervals are event-level**, not one-row-per-trial. Filter with `correct`, `stimulus_number`,
   `task_condition_number`; do not count raw rows as trials.
6. **Signal classes stay separate:** SPK/SUA, MUAe, LFP. Do not conflate convolved spike trains
   with sparse `spike_times`.
7. **Stability / O+ definitions:** prefer canonical pipelines over ad hoc Mann-Whitney shortcuts
   (see `examples/07_*` vs deprecated `examples/06_*`).
8. **Decode accuracy without class baseline is misleading** (suite_08 flat ~0.85 including pre-stim).

## Skills to load before reinventing

| Need | Skill |
|------|--------|
| Backlog | `.agents/skills/progress-review-plan/SKILL.md` |
| NWB I/O | `.agents/skills/jnwb-core/SKILL.md` |
| Spikes / rasters | `.agents/skills/jnwb-spiking/SKILL.md` |
| TFR / LFP | `.agents/skills/jnwb-tfr/SKILL.md` |
| Stats | `.agents/skills/jnwb-statistics/SKILL.md` |
| Viz | `.agents/skills/jnwb-visualization/SKILL.md` |
| Forms / pipelines | `.agents/skills/nwb-analysis-forms/SKILL.md` |
| Remote host | `.agents/skills/remote-ssh-and-file-management/SKILL.md` |

Prefer `jnwb` public APIs (`oa.read`, analyzers, `StatisticalAnalysis`) over one-off notebook math.

## PRP paths in this repo — v2 migration pending

Global doctrine (`C:\Users\nejath\.gemini\config\AGENTS.md` → "PRP Backlog Protocol (v2)") now
specifies the target shape: `artifacts/developer/{plan,progress,review}.json` +
matching `.md` (rendered by `misc/jn2md.py`) + `misc/` (+ optional `misc/archive/`), nothing
else. **This repo has not been migrated to that shape yet** — do not assume it has been.

Actual paths on disk (2026-07-10 receipt, `ls artifacts/` and `artifacts/developer/`):

| Role | Path (actual) | v2 mismatch |
|------|----------------|-------------|
| Plans | `artifacts/plans.json` | wrong dir (top-level, not `developer/`) and plural filename |
| Progress | `artifacts/developer/progress.json` | legacy array-of-`filename` shape, not yet `{summary, table[]}` |
| Review | `artifacts/developer/review.json` | present, needs shape check |
| Review alias | `artifacts/review.json` (top-level, 220 bytes) | stray duplicate — v2 forbids anything but the three JSONs + three `.md` + `misc/` in `artifacts/developer/` |
| Other stray files | `artifacts/pv.json`, `artifacts/walkthrough.md`, `artifacts/progress_report.md`, `artifacts/reports/`, `artifacts/developer/.cache/` | none of these exist in v2's target shape — do not delete without confirming with Hamm first, but do not treat them as canonical PRP state either |

**Until migration happens:** keep matching entries by `path` / legacy `filename` as before; do
not invent a parallel backlog; do not silently rename/move files into the v2 shape without
Hamm's go-ahead, since `progress.json`'s legacy array format and the stray files may hold
in-progress work. Flag the mismatch rather than pretending this repo already complies with v2.

## Git / worktree discipline (project)

- Report branch, SHA, dirty status before edits.
- Do not commit/push/merge unless Hamm asks.
- Dirty `main` may block fast-forward to `origin/dev` — say so; do not force.

## Before claiming a publication figure

Checklist:
- [ ] Session row in `session_readiness.csv` has required gates (`nwb_ok`, `sidecar_ok`, `tfr_ok` as needed)
- [ ] Area membership used dual-area rule above
- [ ] Palette indices from omission palette rule
- [ ] Timing aligned to p1 / full sequence or stated omission window
- [ ] Stats annotations (N, test, window) present when claiming effects
- [ ] Visual output inspected

## Legacy note

`legacy/markdowns/CLAUDE.md` is historical orientation (counts, spectral pipeline notes). Prefer
**this file + live catalog/readiness** over legacy session counts (e.g. "13 NWB" is stale).
