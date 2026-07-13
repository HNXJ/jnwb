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
| Precomputed TFR | `D:/workspace/data/tfr_arrays/` (`{session_prefix}-{probe_letter}-{area}-{cond}.npy`) |
| Array caches | `D:/workspace/data/nwb-arrays/` (optional materializations) |

**Env overrides:** `OMISSION_NWB_DIR`, `OMISSION_TFR_DIR`, `OMISSION_META_DIR`, `OMISSION_SESSION`.

**Inventory reality (2026-07-13 receipt):** 17 NWB files (C31o / V182o / V198o).  
**TFR readiness:** 15/17 sessions `suite_tfr_ready=True` (V182o TFR now present).  
Only `sub-C31o_ses-230630` and `sub-V198o_ses-230629` are `suite_tfr_ready=False`.  
Always gate on `artifacts/data/session_readiness.csv` before loading any TFR array.

## Hard scientific footguns (omission-specific)

1. **`tfr_from_preprocessed` must not silently return mock data.** If TFR files are missing,
   fail or label synthetic. Wire to `OMISSION_TFR_DIR` / readiness gates.
2. **V182o PyNWB Device metadata can break `pynwb` construct.** Prefer **h5py** for LFP/pupil
   (`acquisition/probe_*_lfp/...`) and sidecars; do not require a full clean PyNWB load for
   metadata indexing.
3. **Dual-area probes:** label `"Y, Z"` / `"Y/Z"` → channels **1–64 = Y**, **65–128 = Z**.
   Bare `"V3"` alone → `(V3d, V3a)`. Dual `"V3, V1"` keeps **V3** as the first half (does not
   expand to V3d/V3a). Canonical helper: `jnwb.addressing.map_peak_channel_to_area` (resolves
   multi-area probes by real channel position via `jnwb.sequence_layout.parse_probe_areas`,
   `channel_slice_for_area` — **do not** re-implement by taking `location.split(',')[0]`; that
   bug shipped once and silently mislabeled 1965/6655 rows in the grand unit table).
4. **Sequence timing (ms, p1 = 0):** fx=-500; p1=0; d1=531; p2=1031; d2=1562; p3=2062; d3=2593;
   p4=3093; d4=3624; full span **4624 ms** (−500…4124). Canonical dict:
   `jnwb.sequence_layout.EPOCH_ONSETS_MS`. Layout shapes: `jnwb.sequence_layout` (Plotly vector
   objects, not a background PNG). Per-slot omission-window definition (what the real O+
   classifier tests): `jnwb.unit_classification.SLOT_WINDOW_MS` = `(onset, onset+531)` per slot.
5. **Intervals are event-level**, not one-row-per-trial. Filter with `correct`, `stimulus_number`,
   `task_condition_number`; do not count raw rows as trials.
6. **Signal classes stay separate:** SPK/SUA, MUAe, LFP. Do not conflate convolved spike trains
   with sparse `spike_times`.
7. **Stability / O+ definitions:** prefer canonical pipelines over ad hoc Mann-Whitney shortcuts
   (see `jnwb.unit_classification.is_o_plus` vs deprecated ad hoc scripts). Note the classifier's
   `is_o_plus` test pools across all omission slots with FDR — it is **not** the same comparison
   as "does this one row visibly show elevated firing at this one slot" that a per-condition
   figure displays. A unit can pass the pooled classifier while showing the weakest single-slot
   effect of all real candidates (found directly: unit 41 passed `is_o_plus` but had only a
   1.23x omission/control ratio vs unit 51's ~2x, consistent across all 3 omission rows) — when
   picking one exemplar unit per class for a figure, verify the specific comparison the figure
   makes, don't trust classifier pass/fail alone.
8. **Decode accuracy without class baseline is misleading** (suite_08 flat ~0.85 including pre-stim).
9. **`session.get_spike_times(unit_id)` indexes by raw DataFrame row position
   (`units_df.index`), NOT the `unit_id` column.** The `unit_id` column is a per-probe-local
   kilosort id — it can have gaps and is not globally unique across probes/sessions. Confirmed
   real bug pattern, found twice in different code paths (`jnwb/trajectory.py::
   build_time_resolved_matrix` was using the `unit_id` column; a `grand_unit_table_shuffle_sso.csv`
   consumer had the same issue). Before writing any new code that fetches spikes for a unit,
   confirm which id you're holding — a DataFrame index vs. a `unit_id` column value are not
   interchangeable.
10. **h5py-backed columns on some sessions are bytes-encoded** (`b'2.0'`, `b'nan'` as literal
    byte strings, not floats) — `stimulus_number`/`correct`/`task_condition_number`/`start_time`
    silently produced wrong trial counts on `sub-C31o_ses-230816`/`230901` (370 vs real 246
    trials) until parsed with an explicit bytes-aware numeric coercion. Any new code reading raw
    intervals columns via h5py (not through `session.get_epochs`) must handle this — verify
    trial counts against a known session rather than trusting a clean run.
11. **"Executes without error" is not verification of content.** Two notebooks
    (`suite_06`, `suite_07`) scored 97-100 for months on exit-code success alone while containing
    100% fabricated output (`suite_06`: hardcoded `corrs = [0.12, 0.05, 0.28, 0.42]`; `suite_07`:
    `np.random.uniform`/`np.random.normal`-simulated PCA trajectories with a real NWB session
    loaded but never used downstream). Before scoring any notebook/script ≥90, actually read the
    code that produces the reported numbers — confirm every plotted/reported value traces to a
    real computation on loaded data, not a literal or an RNG draw dressed as one.
12. **Stability/consistency metrics: coefficient of variation (CV = std/mean) is scale-invariant
    and does NOT catch trial-order drift.** A unit whose rate ramps up/down monotonically across
    the real trial sequence can still score a low CV. Caught only by rendering and visually
    inspecting a raster (S- unit 238: moderate CV, visibly non-stationary when actually plotted).
    Use `|spearmanr(trial_index, per_trial_spike_count).correlation|` (worst-case across
    conditions) instead when "stable across trials" is a selection criterion.
13. **Template-correlation classification supersedes CV/drift-only unit selection.** The canonical
    method for assigning S+/S−/O+/Null labels is Spearman correlation of the 9-element per-epoch
    firing rate vector against binary templates (S+: `[0,1,0,1,0,1,0,1,0]`; S−:
    `[1,0,1,0,1,0,1,0,1]`; O+: one-hot at omitted slot) with permutation-test significance
    (5000 shuffles, p<0.05). Implementation: `scripts/template_correlation_selection.py`,
    output: `outputs/classification/figure3_template_correlation_scan.csv`.
    Confirmed best picks for `sub-C31o_ses-230823_rec`: S+=unit 337 (r=0.985, p=0.008),
    S−=unit 261 (r=0.985, p=0.003), O+=unit 51 (r_mean=0.769, only session with real O+).
    **Open discrepancy:** units 240, 359, 360 labeled "Other" by shuffle classifier but score
    r=0.92–0.95 on S− template (p<0.01) — not yet resolved.

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

**PRP state (2026-07-13 receipts):**

- `plans.json` (34 items, bare list — legacy shape), `progress.json`
  (92 entries, `{schema_version, description, last_updated, entries}` wrapper),
  `review.json` (**93 entries** — fully populated this session, first real independent review).
- **All 93 entries now have a verified verdict** (56 ACCEPTED / 37 ACCEPTED WITH CAVEATS / 0 NOT REVIEWED).
  See `review_results_2026-07-13.md` artifact for full receipts.
- **The self-assigned progress.json scores (97-100) remain unverified until matched by review.json.**
  `review.json` is now the authoritative score source.
- Schema is still v1 (entries[]). Migration to v2 `{summary, table[]}` needs Hamm's go-ahead.
- Stray files still present: `pv.json`, `walkthrough.md`, `progress_report.md`, `reports/`,
  `reports_goal_verify/`, `reports_test_verify/`. Re-verify before trusting.

## Git / worktree discipline (project)

- Report branch, SHA, dirty status before edits.
- Do not commit/push/merge unless Hamm asks.
- Dirty `main` may block fast-forward to `origin/dev` — say so; do not force.

## Before claiming a publication figure

Checklist:
- [ ] Session row in `session_readiness.csv` has required gates (`nwb_ok`, `sidecar_ok`, `suite_tfr_ready` as needed)
- [ ] TFR array exists at expected path: `D:/workspace/data/tfr_arrays/{prefix}-{probe}-{area}-{cond}.npy`
- [ ] Area membership used dual-area rule (footgun #3) — not first comma-token of location string
- [ ] Palette indices from omission palette rule (`.cursor/rules/omission-palette.mdc`)
- [ ] Timing aligned to p1 / full sequence per `EPOCH_ONSETS_MS` or stated omission window
- [ ] For spike figures: unit picks verified by template correlation (footgun #13), not CV alone
- [ ] Stats annotations (N, test, window) present when claiming effects
- [ ] Visual output physically inspected (not just "executed without error")

## Legacy note

`legacy/markdowns/CLAUDE.md` is historical orientation (counts, spectral pipeline notes). Prefer
**this file + live catalog/readiness** over legacy session counts (e.g. "13 NWB" is stale).
