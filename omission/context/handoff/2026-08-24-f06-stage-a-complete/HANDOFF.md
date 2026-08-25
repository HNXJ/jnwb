# Handoff: F06 Stage A complete, atlas phase in progress — 2026-08-24

Read this first if resuming this thread of work cold. Read `../../ANALYSIS_GOAL.md` (private,
gitignored) for the full F1-F7 goal skeleton this sits inside — this handout does not repeat it.

## Where we are

Manuscript coordinate system is **F1-F7** (new), distinct from old `fig01-fig07`/`L*`/`S*`
numbering — do not conflate. Structure is frozen (`omission/CLAUDE.md`
"Structural freeze + analysis-only"); this is pure analysis work now.

Pipeline in progress per Hamm's directive: build candidate-panel atlases for **F04-F07**
broadly (~100 candidate panels total) before any final panel selection. Final selection
happens only after all four figures reach candidate-space terminal state — **not yet
authorized**.

### Done
- **F04 atlas**: 19 panels generated, `omission/outputs/panel_atlas/F04/` +
  `registry.csv`. Script: `omission/scripts/generate_f04_atlas.py`.
- **F05 atlas**: 7 panels (reused from existing L1-L5 receipts + 2 synthesis panels).
  Script: `omission/scripts/generate_f05_atlas.py`.
- **F06 Stage A** (matched SPK-LFP substrate — genuinely new computation, explicitly
  authorized by Hamm as bounded scope, not atlas aggregation): **complete and receipted**.
  See "F06 Stage A results" below.

### Not started
- **F06 Stage B** (candidate atlas, ~20-30 panels) — gated on Hamm reviewing Stage A results
  below. Do not generate until that review lands.
- **F07** substrate design and atlas — explicitly deferred until after F06.
- **Outstanding from Hamm, not yet investigated**: F04's two different omission-decoding
  null counts (7/139 in `omission_identity_leakage_safe_receipt.json` vs 3/139 in
  `fig04_encoding_matrix_cells.csv`'s `Y_omit` target) need their definitional difference
  made explicit in the registry — "do not average or choose between them based on which
  tells the cleaner story." Not yet done.
- Final panel selection across F04-F07 — not authorized yet.

## F06 Stage A results (just reported to Hamm, awaiting review)

Substrate: `omission/outputs/f06_substrate/f06_matched_substrate_v1.csv` (31 rows = 31
matched session×area cells, all 6 areas, 3 subjects, 0 exclusions, 100% match rate).
Built by `omission/scripts/build_f06_matched_substrate_v1.py` — recomputes LFP at session
resolution from raw NWB (never from pooled L2 figures), preserves ratio-before-log,
aggregates SPK to session×area to avoid pseudoreplication. Receipt:
`f06_matched_substrate_v1_receipt.json` in the same directory.

Two contrasts: **OB** (omission vs local baseline) and **OS** (omission vs matched real
stimulus). Two baseline conventions kept separate throughout (`NATIVE_MODALITY` vs
`HARMONIZED`, never mixed) per Hamm's explicit requirement.

**Primary geometry** (`f06_primary_geometry.csv`, Pearson+Spearman, FDR-corrected over 10
tests): OB concordant with SPK in theta/alpha only; OS concordant in beta/low_gamma/
high_gamma only. A clean band×contrast dissociation, not a modality-agreement question.

**Direct interaction test** (`f06_direct_dissociation_test.csv`): first attempt (paired
t-test on per-cell z-score differences) was a **dead end** — mean of a difference between
two variables independently standardized to the same population is ≈0 by construction,
regardless of any real effect. Discarded, do not repeat this pattern. Replaced with
`z_LFP ~ z_SPK * contrast` (stacked OB+OS, cluster-robust SE by cell — each cell
contributes 2 correlated rows). FDR-significant interaction in **theta** (p_fdr=0.039) and
**low_gamma** (p_fdr=0.039); high_gamma suggestive only (p_fdr=0.088, does not survive).

Full methodology + caveats (n=31 spans only 3 subjects, no subject random effect fit yet,
om_vs_delay SPK contrast has no LFP analogue and was correctly excluded from the matched
substrate) in `omission/outputs/f06_substrate/f06_stage_a_receipt.json`.

## Immediate next step (once Hamm signs off on Stage A)

Generate the F06 Stage B candidate atlas (~20-30 panels) per the class list in Hamm's
2026-08-24 F06 directive (band-specific SPK-vs-LFP scatter per contrast, band×concordance
summary, subject-stratified geometry, area-stratified geometry, the interaction-test
result itself as a panel, null/control panels, opposite-direction cells, etc.) — mirror the
`generate_f04_atlas.py`/`generate_f05_atlas.py` pattern: `write_panel()` helper writing
svg/png/csv/stats/receipt.json + appending to the shared `registry.csv` at
`omission/outputs/panel_atlas/registry.csv` (18-column schema — read an existing row before
adding new ones). Then F06 contact sheet.

## Standing rules that bit us / worth re-stating

- `registry.csv`'s `result_status` column includes the literal string `NULL` as a valid
  value — `pd.read_csv` treats it as a missing-value sentinel by default and silently turns
  it to NaN. Always read with `pd.read_csv(..., keep_default_na=False, na_values=[""])`.
  See `omission/outputs/panel_atlas/README.md`.
- Do not standardize two variables to the same population and then test their paired
  difference from zero — see "dead end" above.
- `jnwb/` stays frozen/read-only; work through it, never extend it (repo-root `CLAUDE.md`).
- Protected concurrent work (`context/figures/`, `scripts/`, `omission-data/SKILL.md` as of
  2026-08-22) — never move/stage/revert/commit these regardless of phase.
