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
- Backlog / Graph: Labyrinth Protocol under `artifacts/.lab/` (see global `AGENTS.md` + `labyrinth-protocol` skill).
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

**Inventory reality (2026-07-26 receipt):** 21 NWB files (C31o / V182o / V198o).  
**TFR readiness:** 15/21 sessions `suite_tfr_ready=True` (C31o 7/7, V182o 4/10, V198o 4/4).  
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
    (5000 shuffles, p<0.05). Implementation: `scripts/archive_oneoff/template_correlation_selection.py`,
    output: `outputs/classification/figure3_template_correlation_scan.csv`.
    Confirmed best picks for `sub-C31o_ses-230823_rec`: S+=unit 337 (r=0.985, p=0.008),
    S−=unit 261 (r=0.985, p=0.003), O+=unit 51 (r_mean=0.769, only session with real O+).
    **Open discrepancy:** units 240, 359, 360 labeled "Other" by shuffle classifier but score
    r=0.92–0.95 on S− template (p<0.01) — not yet resolved.
14. **NaN Omission vs Imputation:** Ensure listwise exclusion of NaN entries across paired signals instead of zero-filling them.
15. **PSI scale preservation:** Phase Slope Index must return the raw sum to preserve magnitude context for quantitative comparisons instead of normalising by amplitude.
16. **`_parallel_map` pickling** — `_permutation_test` and `_bootstrap` now use `_parallel_map` with `n_jobs`. The worker closures capture `metric_fn`, which may not be picklable when `n_jobs != 1` with `loky` backend (lambda, local inner functions). Before any permutation run with `n_jobs > 1`, confirm the metric function is a module-level callable. Symptom: silent fallback or `PicklingError`. Smoke-test: `jrsa(x, y, metric="pearson", n_jobs=2, permutations=50)` must complete without error.
17. **`_apply_lag` multi-lag + stats interaction** — When `lag` is a list of >1 values, `_apply_lag` stacks shifted copies into shape `(n_lags, ...)`. `_permutation_test` and `_bootstrap` currently receive the full stacked array and produce a single shared null distribution across all lags, not one per lag. Any p-values reported when `lag=[...]` and `stats=True` are therefore **not lag-segregated** and are statistically incorrect. Do not interpret permutation p-values from multi-lag calls until this is fixed with a per-lag loop in `jrsa()` around the metric + stats block.
18. **`batch_size` is a silent no-op** — `jrsa()` accepts and stores `batch_size` in `params` but never passes it to `_stack_batches`. The parameter is cosmetic. Do not document it as functional until wired. Remove it from public API examples until then.
19. **`window` parameter is sample-index, not milliseconds** — `jrsa(window=(-500, 500))` treats values as raw sample indices, not ms. The docstring example is misleading. Until a `window_unit` parameter is added, always pass sample counts explicitly and add a comment stating the sample rate assumption.
20. **`_multiple_correction` silently falls back on unknown method** — Passing `correction="invalid"` does not raise; it silently applies `fdr_bh`. Always validate the correction string against `_CORRECTION_METHOD_MAP` and warn if unrecognised.
21. **`statistics.py` uses global `np.random.seed(42)`** — `StatisticalAnalysis.bootstrap_ci` and `StatisticalAnalysis.permutation_test` both call `np.random.seed(42)`, a global state mutation. This silently reseeds NumPy's legacy RNG and will interfere with any test that sets its own seed. Use `np.random.default_rng(42)` with a local RNG instance.
22. **`StatisticalAnalysis.correlate` and `jrsa._pearson/_spearman` are duplicates** — Both compute Pearson+Spearman with NaN removal. `_pearson`/`_spearman` in `jrsa.py` do not delegate to `StatisticalAnalysis.correlate`. Any bug fixed in one will not propagate to the other. Planned consolidation: make `_pearson`/`_spearman` delegate to `StatisticalAnalysis.correlate` on CPU paths.
23. **`_compute_statistics` is a dead stub** — The function body is `return value` and is never called anywhere. It exists only as a leftover stub. Do not add logic to it; delete it on the next refactoring pass.
24. **`mcp_server/` does not belong inside `jnwb/`** — The MCP server subdirectory is an infrastructure component, not part of the neural analysis library. It should live at repo root or in a separate package. Having it inside `jnwb/` pollutes the package namespace and import graph.
25. **Memory-mapped TFR downsampling slicing** — When processing multi-session 4D TFR arrays `(n_trials, n_ch, n_freqs, n_times)` (2.23 GB per file), downsample trials and channels using slicing (`arr[::4, ::8, :, :]`) before averaging. Slicing memory-mapped arrays prevents loading full files into RAM, reducing disk I/O by 32x and boosting script execution speeds from minutes to seconds.
26. **DOCX figure insertion order must match ascending figure number** — When assembling a multi-figure manuscript DOCX (via `python-docx` or any script), always insert image+caption blocks in ascending figure order (Fig1 → Fig2 → … → FigN). Never append in code-generation order (which may process TFR/LFP figures after spiking figures and produce out-of-sequence placement). Caught 2026-07-27: Figs 6 & 7 were placed after Fig 8 in the master DOCX, causing the PDF reviewer to report them missing. Remedy script: use `body.insert(idx_before_next_figure, deepcopy(elem))` to reorder without rebuilding the entire document.

## Skills to load before reinventing

`.claude/skills/<name>/SKILL.md` is now the single tracked canonical skill source (2026-08-10 —
per `artifacts/.lab/agent-harness-audit-20260810.json`, the prior two-tree setup, `.claude/`
gitignored + `.agents/skills/` as a "reference" copy that was supposed to be kept in sync, had
already drifted 348 lines apart on one skill alone and contained stale D:-drive paths from
before the 2026-08-08 path-centralization work. `.agents/skills/` is retired; `.claude/skills/`
is un-gitignored and tracked directly, so there is exactly one location and no sync step to
forget. `scripts/sync_claude_skills.py` is now historical — see its own docstring.) Backlog/PRP
tracking (`progress-review-plan`) is retired — it was a pure redirect stub to Labyrinth with no
unique content, deleted 2026-07-31.

| Need | Skill file |
|------|-----------|
| Backlog / graph / context optimization | `.claude/skills/labyrinth-protocol/SKILL.md` |
| NWB I/O | `.claude/skills/jnwb-core/SKILL.md` |
| Unit metadata & quality | `.claude/skills/jnwb-metadata/SKILL.md` |
| Spikes / rasters | `.claude/skills/jnwb-spiking/SKILL.md` |
| TFR / LFP | `.claude/skills/jnwb-tfr/SKILL.md` |
| Population analysis | `.claude/skills/jnwb-population/SKILL.md` |
| Stats | `.claude/skills/jnwb-statistics/SKILL.md` |
| Viz | `.claude/skills/jnwb-visualization/SKILL.md` |
| Forms / pipelines | `.claude/skills/nwb-analysis-forms/SKILL.md` |
| Functional connectivity (jrsa) | `.claude/skills/jnwb-jrsa/SKILL.md` |
| Functional connectivity (MI) | `.claude/skills/jnwb-functional-connectivity/SKILL.md` |
| DOCX layout & editing | `.claude/skills/docx-editing/SKILL.md` |
| Writing in Hamm's voice (manuscripts, captions) | `.claude/skills/match-my-writing-style/SKILL.md` |
| Knowledge-graph rendering/export | `.claude/skills/lab-graph-export/SKILL.md` |


Prefer `jnwb` public APIs (`oa.read`, analyzers, `StatisticalAnalysis`) over one-off notebook math.

### jrsa skill spec

The jrsa skill file must cover:
- Public API: `jrsa(x1, x2, metric=..., lag=..., nan_policy=..., stats=..., backend=..., n_jobs=..., return_null=..., return_input=...)`
- All 14 metric names and their return conventions `(value, statistic, effect, p, df)`
- NaN omit policy: listwise joint exclusion on last axis before metric dispatch
- Multi-lag usage: `lag=[0,1,2]` returns stacked `(n_lags,...)` value; **permutation p-values are not lag-segregated until further fix**
- Backend dispatch: `_get_xp`, `_to_backend`, `_backend_torch`; always use `_get_xp(arr)` not hardcoded `np`
- GPU safety rules: no CPU-GPU copy per permutation iteration; use `xp.roll`, `xp.take`, device-side RNG
- Known dead code: `_compute_statistics` (stub, never called), `batch_size` (no-op)
- Known merge targets: `_pearson`/`_spearman` should delegate to `StatisticalAnalysis.correlate`; `_reduce_dimensions` should use the `_OPS` dispatch table pattern
- Known caveats: `_hsic` centering assumes symmetric kernel matrix; `_granger` AIC indexing is statsmodels-version-specific

## Dead code and refactoring register

Track known dead / no-op / duplicate code here so the agent doesn't add logic to stubs
or re-implement things that already exist.

| Symbol | File | Status | Action |
|--------|------|--------|--------|
| `_compute_statistics` | `jnwb/jrsa.py` | Dead stub — `return value`, never called | Delete on next refactor pass |
| `_stack_batches` | `jnwb/jrsa.py` | Defined, never called; `batch_size` param is a no-op | Wire or remove both |
| `StatisticalAnalysis.permutation_test` | `jnwb/statistics.py` | Superseded by `jrsa._permutation_test` for metric similarity use cases | Add deprecation warning |
| `StatisticalAnalysis.bootstrap_ci` | `jnwb/statistics.py` | Uses `np.random.seed(42)` global mutation | Migrate to `default_rng`; add deprecation for jrsa callers |
| `_pearson` / `_spearman` (CPU path) | `jnwb/jrsa.py` | Duplicates `StatisticalAnalysis.correlate` | Delegate to it on CPU path |
| `_reduce_dimensions` | `jnwb/jrsa.py` | 80-line if/elif duplication for x1 and x2 | Replace with `_OPS` dispatch table |
| `_interp` (linear) / `_interp_cubic` | `jnwb/jrsa.py` inside `_resample_axis` | Two identical inner functions differing only by `kind=` | Collapse to one inner function with `kind` parameter |
| `markdown_report.py` vs `report.py` | `jnwb/` | Likely redundant pair — audit before any new reporting work | Confirm overlap; collapse or tombstone the smaller one |
| `diagnostics.py` vs `visual_qc.py` | `jnwb/` | Possibly overlapping QC roles | Audit; merge if purposes are identical |
| `mcp_server/` | `jnwb/mcp_server/` | Infrastructure, not analysis library | Move to repo root or separate package |

## jrsa debugging protocol

When a `jrsa()` call produces unexpected results, work through this checklist before touching
the metric implementation:

1. **Check NaN count first.** Run `np.isnan(x1).sum(), np.isnan(x2).sum()`. With
   `nan_policy="omit"`, the effective N after joint exclusion may be much smaller than expected.
   Print `result.aligned_x1.shape` with `return_input=True` to confirm.

2. **Verify backend.** Print `result.execution["backend"]`. If you expect GPU but see `numpy`,
   CuPy is not installed or the array was not a `cp.ndarray` at call time.

3. **Multi-lag + stats.** If `lag` is a list and `result.p` is reported, those p-values are from
   a single shared null distribution across all lags (footgun #17). Do not interpret them as
   per-lag significance until the per-lag stats loop is implemented.

4. **Parallelism smoke test.** Before using `n_jobs > 1` in a new environment, run:
   ```python
   import numpy as np, jnwb as oa
   rng = np.random.default_rng(0)
   x, y = rng.normal(size=200), rng.normal(size=200)
   r = oa.jrsa(x, y, metric="pearson", permutations=50, n_jobs=2)
   assert r.p is not None
   ```
   If this raises `PicklingError`, `n_jobs` must stay at 1 for this metric until the
   worker closure is made picklable (footgun #16).

5. **Window is samples, not ms.** If results look wrong after setting `window=(a,b)`, confirm
   `a` and `b` are sample indices, not milliseconds (footgun #19).

6. **Correction fallback.** If you expect a specific correction method and results look like
   BH-adjusted values even though you passed a different string, the method string may have
   fallen through silently (footgun #20). Print `_CORRECTION_METHOD_MAP.get(your_string)`.

7. **Granger best-lag.** Print `best_lag` inside `_granger` (add a `verbose` branch) if the
   F-statistic looks implausibly high or low — confirm AIC extraction from statsmodels result
   object matches the current version of `statsmodels.tsa.stattools.grangercausalitytests`.

## Labyrinth Protocol (ACMP & Knowledge Graph Optimizer)

This repo follows the **Labyrinth Protocol (ACMP & Knowledge Graph Optimizer)** (see global `AGENTS.md` and `.claude/skills/labyrinth-protocol/SKILL.md` for the full definition): graph state lives under `artifacts/.lab/`. The 7 fundamental actions (**Evolve**, Plan, Progress, Review, Prune, Adapt, Seal) operate over the 3-level system model (State, Actions, Regulation) and track context optimization via the loop: `Knowledge → Prediction → Observation → Error → Evolution → Knowledge`.

**Binding Directives (Hamm's Operational Agreement):**
Labyrinth is the shared brain and knowledge graph between agent and Hamm, reflecting the past, present, and future of the project.
* **Continuous Synchronization**: On EVERY action, update and consult the Labyrinth graph (`artifacts/.lab/`).
* **Four Core Labyrinth Objectives**:
  1. Minimize mismatches and frictions (Omission, Redundancy, Disconnection, Staleness, Contradiction).
  2. Identify repetitions and over-mentions (Prune/Compact redundant nodes).
  3. Organize, merge, and unmerge via an adaptive, Hebbian-evolving graph.
  4. Align multiple asynchronous agents using the SQLite hash-chain ledger (`labyrinth.db`) and `.lab/` graph state.
* **Zero-Context "Proceed" Directive**: If a turn receives `"proceed"` (or similar approval) with zero additional context or active plan, immediately perform a full review of workspace state, identify high-leverage actions to improve/minimize/stabilize the project, and record it as a Labyrinth Plan/Progress node under `artifacts/.lab/` — **not** `artifacts/developer/plans.json`/`progress.json`, which are retired PRP files (see `RETIRED_prp_*` in `artifacts/developer/`); this line itself used to say those files and was corrected 2026-07-31 after being found still live and contradicting the retirement doctrine elsewhere in this file.

**Graph state is a live measurement, not a frozen number** — the 2026-07-25 snapshot that used
to sit here (93 nodes, 100% predictive accuracy) went stale the moment the graph grew past it,
which is the exact failure mode Rule 3 of `figures/README.md`'s statistics doctrine and the
global CLAUDE.md's "graph health is itself measurable" section both warn about. Re-run the scan
instead of reading a cached count: latest full health audit is
`artifacts/.lab/graph_health_audit_20260729.json` (0 dangling edges, 0 unreceipted `confirmed`
claims, 181/296 nodes pre-date `schema_version` — a literature-review layer, not yet migrated).
Interactive Canvas Visualizer, if still current, compiled at `artifacts/lab_graph.html`.

### Self-Evolving & Self-Supervised Adaptation
During Labyrinth's **Adapt** phase (not "the PRP loop" — PRP is retired, corrected 2026-07-31), pay attention to the active workspace skills (`.claude/skills/` — single tracked canonical source since 2026-08-10, see the "Skills to load before reinventing" section above), project instructions (`.agents/AGENTS.md`), and historical adaptation files/memories to propose guidelines and code refinements. This ensures that the agent's behavior and constraints continuously improve, adapt, and self-evolve to prevent repeating historical mistakes or regressions. Rules and memories must be dynamically upvoted or downvoted based on their usage frequency and overall effectiveness.



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
- [ ] If `jrsa()` was used: confirm `nan_policy`, check effective N via `return_input=True`, and confirm `lag` was scalar (not a list) if per-lag p-values are being reported
- [ ] If `statistics.py` bootstrap or permutation was used: confirm it was not called after any other code set `np.random.seed()`; prefer `jrsa()` with `permutations=` for neural similarity p-values

## Common vs. Divergent Features Matrix

### Common Features (Shared Across All Sessions & Pipelines)
* **Epoch Timing Overlay**: Visual stimulus, delay, and omission windows follow the precise parameters of `jnwb.sequence_layout.EPOCH_ONSETS_MS` (`fx=-500`, `p1=0`, `d1=531`, `p2=1031`, `d2=1562`, `p3=2062`, `d3=2593`, `p4=3093`, `d4=3624` ms).
* **Color Schemes**: Matplotlib and Plotly figures map to `omission-palette.mdc` (`Theta/p1` -> `GOLD`, `Alpha` -> `BLUE`, `Beta/p2` -> `VIOLET`, `Gamma` -> `GREEN`, `delays` -> `GRAY`).
* **Dual-test statistics**: Every group-level contrast requires parametric (ANOVA/t-test) and non-parametric counterparts (Wilcoxon/Friedman) to prevent false-positive claims.
* **Sidecar Metadata Topology**: Directory `D:/workspace/data/metadata/{stem}/` always holds raw tabular files: `electrodes.csv`, `units.csv`, `events.csv`, `h5_paths.json`.

### Divergent Features (Session-Specific Exceptions & Critical Divergences)
* **Probe Location Maps**: Probe letters map to different brain areas depending on the session (e.g. `probeA` can map to `FEF` or `PFC`). Resolving areas requires querying `jnwb.addressing.map_peak_channel_to_area` rather than splitting strings.
* **Device metadata blockages**: Older sessions (e.g. `V182o`) contain PyNWB format builder anomalies. LFP and pupil dataset reads must fallback to direct `h5py` access (`acquisition/probe_*_lfp/data`).
* **Epoch table differences**: Older visual sessions do not have `'is_omission'` column in their epochs table, and instead use `'oddball_status'` (where `1.0` = standard, `3.0` = omission slot).
* **Unit ID Indices**: Firing rate table indices (`units_df.index`) do not match local kilosort `unit_id` column values. All spike-retrieval calls must index using row index labels, not Kilosort IDs.
* **h5py Bytes Encoding**: Direct queries to raw `h5py` dataset attributes on some sessions return bytes (`b'2.0'`) instead of floats. Explicit bytes-aware decoding checks are required.

## Fast but Shallow Agent Execution Rules (FSA Rules)

If you are a fast, shallow agent with limited context window or planning depth, adhere strictly to this ruleset to operate safely:

1. **Verify Session Readiness first**: Never hardcode NWB sessions. Load `artifacts/data/session_readiness.csv`, verify that `nwb_ok` and `sidecar_ok` are true, and iterate through the active rows.
2. **Never assume Probe mappings**: Use `jnwb.addressing` methods to map channels to V1/PFC areas dynamically. Dual-area channels 1-64 map to the first labeled area; 65-128 map to the second.
3. **Use the ordered Omission Palette**: Never specify custom color strings. Map parameters to index offsets of `omission-palette.mdc`.
4. **Fallback to h5py for LFP data**: If standard NWB load fails, use `with h5py.File(path, 'r') as f:` and access the LFP matrix at `acquisition/probe_{idx}_lfp/data`.
5. **Always double-test group statistics**: When plotting PSTHs or TFR traces, perform Wilcoxon signed-rank or Friedman Chi-square tests across trials/binned conditions and display the exact adjusted p-values.

## Legacy note

`legacy/markdowns/CLAUDE.md` is historical orientation (counts, spectral pipeline notes). Prefer
**this file + live catalog/readiness** over legacy session counts (e.g. "13 NWB" is stale).

**Doctrine-file note (2026-07-29):** this repo's doctrine is split across three files —
`C:\Users\nejath\.claude\CLAUDE.md` (Claude Code, machine-wide ACMP wording), this file (Gemini
CLI's stated "global working agreement", per its header), and `D:\workspace\omission\CLAUDE.md`
(Claude Code, project-specific). The Labyrinth Reflex text used to appear twice inside this file
alone — condensed to the single copy above. It has not been reconciled against the Claude Code
global file's wording because that file is a different tool's doctrine surface, not this repo's
to silently overwrite; flagging the cross-tool duplication here rather than merging it.

## Draft Citation Rule (Mandatory across all document drafts)

When writing or editing manuscript drafts (in .docx, .tex, .md, or any text format), ALWAYS format citation placeholders in front of the sentence or object as:
- (###) or
- (NEED_REF) or
- (NameYYYY, TITLE-SHORT) (e.g. (Bastos2020, LAMINAR-GATING), (Garrett2020, VIP-DISINHIBITION), (Mendoza-Halliday2024, SPECTROLAMINAR-MOTIF))

The bibliography will be compiled and formatted automatically at the final submission stage.
