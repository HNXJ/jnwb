# 05 — Figures and Pipelines

Generated 2026-08-17. Source: `context/figures/README.md`, per-directory READMEs and script
docstrings. **This document is a snapshot of heavy in-flight, uncommitted work** — see the git
status summary at the end before trusting any currently-rendered number.

## Top-level conventions

- One directory per figure: `figNN_<desc>.py` (only script that draws panels), `svg/` (every
  panel + receipts), assembled `figNN.svg` written by the script.
- Shared modules (no analysis, no drawing): `figstyle.py`, `svgassemble.py`, `figstats.py`.
- Every figure script calls `figstats.write()` → `svg/figNN[_variant]_stats.{md,csv}`.
- Editing rule: hand edits go in `figNN.svg`; re-running the script overwrites it — freeze a
  figure by not re-running once template-matched.
- Supplements have no code/dir of their own — `build_supplements.py` assembles them from panels
  already in `svg/` folders into `supplements/`. Registry declares 30 supplement slots
  (S01–S30).
- The README's hand-maintained status table **has gone stale before** (2026-08-01 example cited
  in the doc itself) — trust `INVENTORY.md` (auto-generated) for structural facts, the README
  table only for human judgement calls (locked/reviewed/pending).
- **Renumbered 2026-08-06**: `figS24_omission_identity_decoding` promoted to the `fig04` slot;
  old fig04 (V1/PFC TFR) → fig06; old fig06 (SPK-SPK) → demoted to
  `spk_spk_coupling_supplement/`. **Directory names are the source of truth for figure
  identity** — internal filenames inside moved directories were deliberately not renamed
  (`fig06_v1_pfc_condition_tfr/` still contains `fig04_*.py` files).
- Falsifier for "figure done": `fig0N_finalized.svg` **and** `.png` both exist (headless-Chrome
  white-bg render) **and** Hamm has explicitly confirmed panel content since the script last ran.
  A finalized file existing is necessary but not sufficient — fig06 is a documented example of a
  finalized file now stale relative to the current `.svg`.
- Figures 2 and 3 both read `outputs/classification/omission_grand_units.csv` — re-running
  `scripts/classify_omission_units_grand.py` changes both; check receipts before quoting either.

## Shared infrastructure

- **`figstyle.py`** — the template every figure draws against. Timing constants (`STIM_MS=531`,
  `DELAY_MS=500`, `SLOT_PERIOD_MS=1031`, `EPOCH_ONSETS_MS`), `BANDS`/`BAND_COLORS` (the 5 house
  bands — theta 4-8, alpha 8-14, beta 14-30, low-gamma 30-50, high-gamma 50-80 — "do not
  re-drift"), `AREA_ORDER`/`AREA_COLORS`/`AREA_POOL`, `CLASS_ORDER`/`CLASS_COLORS`
  (O++/O+/ns/O−/O−−), shading/marking helpers, `save()` (writes the `.png` companion beside
  every `.svg` — the only reliable way to view output on this machine). Re-exports
  `jnwb.statistics.clopper_pearson`.
- **`figstats.py`** — the statistical harness every figure reports through. `holm(p)`/`bh(p)`
  report **both** `p_holm` (FWER) and `q_bh` (FDR) per test — explicitly documented as not the
  same guarantee, never conflate. `SHAPIRO_MIN_N=8`; `paired_location`/`group_location` choose
  parametric-vs-nonparametric by Shapiro-Wilk+Levene rather than habit.
  `INFERENTIAL_UNITS = {session, animal}` — a pseudo-replication guard, unit/channel-level n on
  a population claim must be flagged descriptive, not inferential.
- **`svgassemble.py`** — panel-SVG assembly. `namespace(svg, pfx)` prefixes every id/CSS class
  per panel to prevent id collisions across panels (the bug that caused a duplicate-id failure
  in the first fig01 build). `assemble(panels, out_path, ncol=1, ...)` is the grid-layout entry
  point.

## Numbered manuscript figures (fig01–fig08)

| Fig | Analysis | Status (top-level README) | Key caveat |
|---|---|---|---|
| **fig01** recording_topology_and_paradigm | Recording topology, hardware, design (not statistical) | Locked, 90/100 | No data table read — pure vector/schematic. |
| **fig02** spiking_exemplar_rasters | 4×4 exemplar raster grid (RRRR/RXRR/RRXR/RRRX × S+ V1/S− V3a/d/O+ V4/O++ FEF) | Locked, 100/100 | Hard `SystemExit` if a required area's candidate unit is missing — never falls back silently. n=1 per column by design, no test reported. Reads legacy `grand_s_and_o_units.csv` + `omission_grand_units.csv`. |
| **fig03** unit_census | Unit census — presence, functionality, RXRR template traces | **Not locked**, 80/100 | Most recently touched fig0N script (2026-08-17). README explicitly walks back a past "synthetic/uncitable" status — now real-data throughout. **Currently uncommitted, active in-flight** (see git status below). See doc03 for the O++ definition history in this figure specifically. |
| **fig04** omission_identity_decoding | Leakage-safe omission-identity decoding (SPK/SUA only) | `truth_safe_unverified` — **do not cite** | The old random-CV result (~0.601) is confounded; cycle-deconfounded result is ~chance (0.495). Renderer refuses missing/incomplete leakage-safe artifacts, no scientific fallback. Reference implementation for the `used_placeholder` red-flag pattern. |
| **fig05** v1_area_hierarchy_glmm | LFP band-power hierarchy vs V1/V4/PFC, subject-controlled GLMM | Semi, 60/100 | Built after 3 LFP-LFP connectivity methods (imaginary coherency, Granger, transfer entropy) all came back null at group level. **2/45 cells survive Holm-Bonferroni** (FEF, PFC low-gamma vs V1); 11/45 survive BH-FDR. |
| **fig06** v1_pfc_condition_tfr | V1/V3a-d/TEO/PFC time-frequency, RXRR vs RRRR | **Stale**, 50/100 | `fig04_finalized.*` (2026-08-03 lock) no longer matches the current `.svg` — panel layout, SEM estimator, and a GLMM section all changed since the lock. Main script's `CONDITION_MAPS` constant still points at a dead `D:/` drive path reading the **superseded** v1 TFR extraction; a newer untracked supplement (`fig04xx_3d_condition_tfr.py`) reads the current v2 path — flagged, not fixed. Currently uncommitted. |
| **fig07** lfp_spike_coupling | Population firing rate × LFP band-power (GLMM headline) + spike-LFP PPC (demoted supplement) | Semi label but **revision score 10/100** (major revision) — internal inconsistency, flagged | Band effect dominant (high/low gamma ≫ theta/alpha/beta, Holm p<1e-5); O+ units **less** coupled than Null/S+ (Holm p<2e-5); no condition-group effect. README flags "3 different O++ tables exist in this repo" — resolved here by using the strict 15-unit definition (matches doc03 §5's 52... **note: fig07's README cites 15 units, doc03's current fig03/unified definition is 52 — these may be different vintages; verify before citing fig07's O++ n**). |
| **fig08** neuron_type_layer_lfp | Supplemental: functional class × layer × firing rate × LFP band-power/phase-locking during omission | No README yet — status from docstring only, not in the top-level status table | Panel C (PPC hit-rate) excludes V4 (n=3 sessions, "too fragile to draw at the same visual weight" though present in the underlying CSV). Panel E is exploratory, explicitly non-confirmatory, not a headline panel. One of only two scripts in the tree matching `used_placeholder` (with fig04) — confirm no panel is currently flagged before citing. Untracked in git. |

## Renumbered/demoted slots (formerly numbered, now supplements)

- **`band_power_hierarchy_supplement`** (was fig05) — band-power hierarchy, RXRR vs RRRR, all 10
  areas × 5 bands. Demoted same day the GLMM fig05 was built: "not group-significant." Uncommitted.
- **`lfp_lfp_connectivity_supplement`** (was fig06/briefly fig05) — undirected imaginary-coherency
  (0/240 survive correction, honest null, not deleted) + directed Granger LFP-LFP (built
  2026-08-04, briefly the fig05 slot before the GLMM redesign — this directory has had **two**
  different fig05 identities historically, now fully demoted).
- **`spk_spk_coupling_supplement`** (was fig06) — SPK-SPK lead/lag correlation (headline) +
  directed Granger (supplement). **[DEMOTED 2026-08-06]**: "4/12033 Holm survivors, all near lag
  0 — a real, correctly-reported near-simultaneous-coupling finding, but demoted to make room
  for the fig04 promotion."

## Supplement-only / exploratory directories (not in the fig0N sequence)

- **`supp_identity_reversal_generalization`** — FEF/V3a-d are "the ONLY two areas that pass the
  p2+p3-train/p4-test cross-position generalization test." Explicitly flagged exploratory,
  single-pass, uncorrected across 27 area×analysis cells (nominal cluster alpha=0.05, no
  family-level correction) — both significant clusters are small (1-2 bins). Untracked.
- **`supplement_lfp_artifact_qc`** (2026-08-17, newest in the tree alongside fig03) — % trials/
  channels excluded per monkey/session. **Built from scratch this session** — an Explore-agent
  search found no partial-correlation channel QC, no deviant-channel detection, and no
  corpus-wide trial-exclusion table anywhere in the repo prior to this; the "6× RMS, ~40/960
  trials" figure quoted in `context/analysis_spec_SPK.md` had **no code behind it**.
- **`fig_omission_band_dampening_onset`** (exploratory, not yet numbered) — magnitude barplot
  (area×band, dB re baseline in p2 omission window) + onset-timing panel (dampening onset vs
  each area's real-stimulus response onset, causal floor). Non-significant cells drawn hatched/
  reduced-alpha rather than hidden — "a non-significant cell is a result, not a gap."
- **`fig_v1_omission_band_dynamics`** (exploratory, not yet numbered) — spectral band-power
  dynamics + TFR spectrograms per area, all 10 canonical areas (started V1-only, generalized
  after per-band artifact repair 2026-08-13). Not wired into the manuscript pipeline (no
  svgassemble scaffolding), still a standalone script. **Unresolved ambiguity flagged in its own
  docstring**: the user's stated omission-family window "d1-p2-d2-p3-d2" doesn't parse (d2
  repeated, d3 missing); the script guesses the self-consistent reading (ending at d3) but
  states this was **not independently confirmed with the user**.

## L-track — LFP connectivity spec (L0–L10), all untracked

Spec-driven, separate numbering from fig0N. L1–L10 gate on reading `canonical_pooling_method`
from L0's stats JSON and fail loudly if absent. All ship a `--test` self-test with a
synthetic-data acceptance criterion, run before trusting real-data output.

| Step | Target | Result |
|---|---|---|
| L0 pooling_reconciliation | — | Reconciles the Andre-vs-Hamed "does omission LFP response survive channel pooling" discrepancy — 4 pooling methods on one session/area/band; (a)/(b)/(c) agree, (d) CSD smaller but same sign. Explicitly scoped as "a single honest data point, not a general resolution." |
| L1 tfr_grid | Fig 4 | Area × condition TFR grid. Notes an area substitution: the spec's "8A" doesn't exist in the corpus; substituted FEF/PFC. |
| L2 band_power_traces | Fig 5 | Band × area traces, session-level (not trial-level) bootstrap CI. |
| L3 laminar_power_profile | — | Depth × frequency heatmap + sup/deep contrast index. Flags a known perf inefficiency (5× redundant npz reload per session), not fixed. |
| L4 csd_omission_response | — | CSD response to omission in V1/V2/V4. "A correct, real, self-tested CSD pipeline, not yet a publication-quality figure." Documents a known edge-channel artifact (Laplacian boundary handling) as visual-QC, not a bug. |
| L5 onset_latency_hierarchy | — | "The highest-stakes script in the LFP track." **Every band returns `H3_simultaneous_or_ambiguous`** (not significant, n≤6 sessions/area) — an honest null, triggers L6 as now-required follow-up. |
| L6 volume_conduction_control | — | Built specifically because L5 was ambiguous. Bipolar/Laplacian re-referencing + imaginary-coherency zero-lag-fraction control. "No clean within-vs-across-probe separation." |
| L7 cross_area_power_correlation | Fig 6 | Trial-paired Pearson correlation of band power across area×layer nodes. **Two real bugs found and fixed**: (1) a node-key collision (area+layer string, no probe) caused **silent data loss** via dict-overwrite for sessions with FEF on two probes — fixed by probe-qualifying every key; matrix/significant-pair counts changed materially after the fix. (2) a figure-layout bug (colorbar overlap, clipped suptitle) fixed with explicit GridSpec. |
| L8 cross_area_coherence | — | Standard + imaginary coherence per node. Same node-key-collision bug independently found/fixed here (label-ambiguous, not data-losing this time). Result: same-probe pairs show high standard coherence but near-zero imaginary coherency — "conducted, not interacting," consistent with L6. |
| L9 directed_lfp_lfp_influence | — | Granger (Geweke) + phase-slope index, directed. Bug found/fixed: pseudoreplication in session-aggregation CI (FEF-on-two-probes session silently counted as 2-3 "sessions") — fixed by averaging to one point-estimate per session before bootstrapping; did not require rerunning the ~19-minute GC computation. |
| L10 mutual_information_convergence | — | Explicitly "not an independent result... a model-free complement to L7's Pearson correlation," computed on L7's exact same per-trial vectors. MI vs \|Pearson r\| agreement strongly positive (Spearman rho 0.32-0.95, median ~0.8) — reads as corroborating L7, not an independent finding. |

## S-track — spiking spec (S2/S5/S6), all untracked

- **S2 population_responses_by_class** (targets Fig 3) — population PSTHs for S+/S−/O+ per area,
  z-scored per unit before averaging, CI bootstrapped over sessions not trials. Reads S1's
  `unit_inclusion_v1.csv` ("reviewed and approved 2026-08-17" — note this approval date is
  literally the audit date, extremely fresh). **Explicitly uses the new O+ criterion**
  (`is_omission_inclusion_new`), not either older O+ definition — names the distinction
  explicitly.
- **S5 onset_latency_hierarchy_spk** — labelled **[THESIS FALSIFIER]** in its own docstring.
  Cross-area spiking onset latency, forward-smoothing-only (acausal smoothing explicitly called
  out as "the single most likely way to get the wrong FF/FB answer"). Reuses L5's causal-onset
  machinery unchanged. Acceptance criterion: if pairwise CIs overlap zero, must report
  `discriminating:false` rather than force a hierarchy claim.
- **S6 directionality_controls_spk** — positive control for S5: reruns S5's method on S+/S−
  populations (expected feedforward ordering) as a validation gate — "if S+ does not show the
  expected feedforward latency ordering, the latency method itself is not working and the O+
  result cannot be trusted either." Calls S5's `run()` directly with `class_col` swapped, no
  reimplementation.

## Other loose items in `context/figures/`

`INVENTORY.md` (auto-generated structural registry — trust for code/panels/dimensions/stats),
`FIGURE_SUMMARY.md`, `RESULTS_DISCUSSION.md`, `REVISION_PLAN.md`,
`PLAN_sliding_window_connectivity.md` (top-level planning docs, not deep-read this pass),
`build_inventory.py`/`build_supplements.py` (generators), `_l_lfp_common.py` (untracked L-track
shared helper, analogous role to figstyle/figstats/svgassemble but L-track-scoped),
`_handout25_runtime_audit/` (working/handout directory, not further inspected),
`figure_asset_manifest_2026-07-27.json`, `render_fig0{2,3}_wrapper.html` (rendering support),
`supplements/` (output of `build_supplements.py`, own README with superseded/retired language,
not deep-read).

## Git status — in-flight work as of this audit (2026-08-17)

**Modified (tracked, uncommitted)**: `band_power_hierarchy_supplement/fig05_band_power_hierarchy.py`;
`fig03_unit_census/{README.md, fig03.svg, fig03_unit_census.py, svg/fig03_stats.md}` (**`fig03.png`
deleted on disk** — the finalized PNG companion is currently missing); `fig06_v1_pfc_condition_tfr/
{README.md, fig04_v1_pfc_condition_tfr.py}`; **`figstats.py`, `figstyle.py`, `svgassemble.py` —
all three shared infrastructure modules have uncommitted edits right now**, affecting every
figure that imports them.

**Untracked (new, never committed)**: the entire 11-directory L-track (L0–L10); the 3-directory
S-track additions (S2/S5/S6); `_l_lfp_common.py`; `fig03_unit_census/fig03_supp_area_composition_battery.py`;
`fig06_v1_pfc_condition_tfr/{fig04_glmm_all_areas_timeresolved.py (+_v2,_v3),
fig04xx_3d_condition_tfr.py (+.svg)}`; `fig08_neuron_type_layer_lfp/` (whole dir);
`fig_omission_band_dampening_onset/`; `fig_v1_omission_band_dynamics/`;
`supp_identity_reversal_generalization/`; `supplement_lfp_artifact_qc/`.

**Read as a signal**: this is a large amount of simultaneous in-flight work — an entire 11-file
L-track, a 3-file S-track, edits to all 3 shared infrastructure modules, and a missing
`fig03.png` — all uncommitted at once. Given the shared-infra edits are uncommitted alongside
dozens of new/modified figure files, **any currently-rendered number from fig03, fig06, or
band_power_hierarchy_supplement may reflect an in-progress, not-yet-reviewed state of
figstyle/figstats/svgassemble**. `git diff` the three shared modules before trusting any current
output from them. This matches the memory note about a concurrent Cursor session sharing this
uncommitted tree — check before editing any shared file.
