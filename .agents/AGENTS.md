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

Prefer `jnwb` public APIs (`oa.read`, analyzers, `StatisticalAnalysis`) over one-off notebook math.

## PRP protocol — Canonical PRP Protocol (Developer Standard) adopted 2026-07-10

This repo now follows the **Canonical PRP Protocol** (see `.cursor/rules/prp-protocol.mdc` and
`.agents/skills/progress-review-plan/SKILL.md` for the full definition): exactly three JSON files
under `artifacts/developer/` — `plans.json`, `review.json`, `progress.json` — mapping the same list
of files, with auxiliary/derived files confined to `artifacts/developer/.cache/`. Five phased
actions: `proceed with brainstorm` → `proceed with plan` → `proceed with review` →
`proceed with progress`, plus `inspect` (structural compliance + drift repair) runnable any time.

**Adopting the spec is not the same as the data complying with it yet.** As of this update:

- `artifacts/developer/plans.json` (33 items), `progress.json` (71 entries), `review.json`
  (4 entries, wrapped) are three **different bare/wrapped shapes** with different field names
  (`filename`/`tbis`/`tbds` vs `path`/`tbi`/`tbd`) and do **not** yet share the same row-set across
  all three files, as the canonical spec requires.
- Stray files not in the target shape are still present (verified 2026-07-10 via `ls artifacts/`):
  `artifacts/pv.json`, `artifacts/walkthrough.md`, `artifacts/progress_report.md`,
  `artifacts/reports/`. The top-level `artifacts/review.json` alias and top-level `artifacts/plans.json`
  are both already gone — `plans.json` now lives correctly at `artifacts/developer/plans.json`.
  Re-verify with `ls artifacts/ artifacts/developer/` before trusting this list; the repo has
  drifted between sessions before.
- Running `inspect` to reconcile the row-sets and clean up the stray files is real,
  data-mutating work that hasn't been done yet — don't assume a future session already ran it
  without checking `git log`/`ls` first. Get Hamm's go-ahead before reshaping the existing 71+33+4
  entries, since that's live backlog content, not just documentation.

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
