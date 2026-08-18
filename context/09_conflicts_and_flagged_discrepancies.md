# 09 — Conflicts and Flagged Discrepancies

Generated 2026-08-17, compiled last from the full audit (docs 00-08). Per Hamm's explicit
instruction, low-risk documentation-only conflicts were resolved directly (marked **DECISION
TAKEN** below, with the reasoning stated); anything touching a scientific claim, a doctrine file
(CLAUDE.md/memory), a skill file, or live code was left for Hamm (marked **FLAGGED, NOT
DECIDED**) — per `labyrinth`'s Amendment rule, skill and doctrine changes require independent
confirmation before human approval, an agent does not amend them unilaterally, and no audit
should quietly pick a winner among live scientific numbers.

## HIGH severity — needs Hamm's attention first

### 1. `jnwb/report.py::generate_report` fabricates data and globally seeds RNG

**FLAGGED, NOT DECIDED.** `generate_report`'s waveform/network sections draw synthetic firing
rates from `np.random.exponential` and print a real Mann-Whitney p-value computed on that fake
data as if it reflected measured units; separately, its Granger-network panel calls
`np.random.seed(42)` — the **only global RNG mutation found anywhere in `jnwb/`** — then
fabricates p-values via `np.random.uniform(0, 0.1)` for every directed area-pair edge, FDR-
corrects them, and renders them as real connectivity findings. This directly violates CLAUDE.md
tripwire #1 and the "no silent science" principle the rest of the package (e.g.
`session.plot_tfr`'s `status="missing_tfr"` refusal) follows. Full detail: doc02.

**Recommendation** (not applied): either gate `generate_report`'s network/waveform sections
behind a loud, unmissable synthetic-data warning matching the `PLACEHOLDER-DUMMY` figure
convention (`omission-figures` skill), or remove those two panels until backed by real
computation. This is a code change to a live module — out of scope for a documentation audit and
not low-risk (it changes what a report claims), so left for Hamm's decision.

### 2. `.npy` vs `.npz` — the TFR loader may be finding nothing

**FLAGGED, NOT DECIDED.** `corpus_manifest.json`'s live disk scan finds 970 `.npz` TFR files,
zero `.npy`. `OmissionSession.tfr_from_preprocessed()` globs only `*.npy`. If the TFR directory
genuinely holds only `.npz` today, every call to this loader (and everything built on top of it —
`plot_tfr`, `trial_averaged_plot`, `spectrolaminar_motif`) silently returns "missing," not an
error. Full detail: doc01/doc04.

**Not decided because**: this could mean either (a) TFR products were recently regenerated in a
new format and the loader is now stale, or (b) the loader was always right and the manifest scan
caught a transient/partial state. Resolving this requires knowing the TFR pipeline's recent
history, which only Hamm or a fresh run of `precompute_tfr_arrays_v2.py` can confirm.
**Recommended first step**: check whether any current figure that depends on
`tfr_from_preprocessed` (not the newer `precompute_tfr_arrays_v2.py`-based scripts) is silently
producing empty output.

### 3. Six incompatible O+ counts, four incompatible O++ counts

**FLAGGED, NOT DECIDED** (this is a scientific-claim decision, not a documentation one). Full
table in doc03. Every one of the four generations is a legitimate, differently-scoped
measurement — none is simply wrong. **What this audit did decide** (low-risk, purely about which
number this *documentation* cites as "the current fig03/unified number," not about which
generation is scientifically preferred): doc03 and doc08 both cite the **template-correlation,
current definition (52 O++ units, V4/TEO/FEF/PFC, r≥0.65)** as the number matching fig03's and
`build_unified_class_census.py`'s current output, because that is what those two live pipelines
actually compute today — this is a factual statement about current code output, not a scientific
ranking of the four methods. **Still open for Hamm**: which generation(s) the manuscript's
headline O+/O++ prevalence claim should actually use.

### 4. S1 inclusion count: `PROJECT_STATE.md` says 281/9061 (3.1%), this audit's live CSV read says 319

**FLAGGED, NOT DECIDED.** `PROJECT_STATE.md`'s S1-approval entry states 281/9061 passing the new
criterion. This audit's direct `pandas` read of `unit_inclusion_v1.csv::is_omission_inclusion_new`
(full corpus, all quality tiers) gives **319**. Most likely explanation is a population-scope
difference (281 may be a quality-filtered subset, or an earlier run predating a fix) rather than
a contradiction, but this was **not traced to ground** by this audit. Do not cite either number
as the S1 headline until reconciled — re-read `PROJECT_STATE.md`'s S1 section against a fresh
`unit_inclusion_v1_stats.json` before the next citation. Detail: doc08.

### 5. `session_readiness.csv::suite_tfr_ready` is `False` for all 22 sessions

**FLAGGED, NOT DECIDED.** Either a real unmet gate (e.g. missing AAAB/BBBA TFR products) or a
stale/never-updated column — `scripts/build_session_readiness.py` was not read by this audit.
Detail: doc01.

## MEDIUM severity — documentation-only conflicts, decisions taken

### 6. CLAUDE.md lists 9 skills; only 7 exist on disk

**DECISION TAKEN (documentation only)**: this document (doc07) states the confirmed 7-skill list
as current and flags `numerical-computing`/`biophysical-modeling` as named-but-absent. **Not
applied to CLAUDE.md itself** — per the Amendment rule, doctrine-file edits need Hamm's explicit
approval, so the fix (either remove the two names or create the two skills) is left as an
explicit recommendation, not an edit: **removing the two names from CLAUDE.md's skill list is
the lower-risk of the two options** (a skill that's referenced but doesn't exist can silently
mislead a future session into believing routing will fire when it won't; creating two new skill
files is a larger, content-bearing decision only Hamm should make). Stated as a recommendation
in doc07, no file changed.

### 7. Two skills reference quarantined `jnwb` modules

**DECISION TAKEN (documentation only)**: doc02/doc04/doc07 all state plainly that
`omission-signal`'s `jnwb.complex_tfr` example and `omission-figures`'s `jnwb.markdown_report`
example are both dead — quarantined to `jnwb/_unused/`, not importable as written — and name the
live replacements (`spectral.imaginary_coherency`, `jnwb.report`). **Not applied to the skill
files themselves** — same Amendment-rule reasoning as #6. Recommended fix (one-line import
correction in each skill) is low-risk in isolation, but skill files are doctrine-adjacent per
`labyrinth`, so left for Hamm's approval rather than edited directly.

### 8. `omission-signal` skill's PPC-retired stance is stale

**DECISION TAKEN (documentation only)**: doc04/doc07 state the current status plainly — the
2026-08-15 corrected-design PPC rebuild reversed the retirement with a provisional non-null
result, per Hamm's own explicit override request. **Not applied to the skill file** — same
Amendment-rule reasoning; the skill's §10 point 4 needs a real update, recommended in doc07, left
for Hamm.

### 9. Three historical corpus-size vintages (13/2, 23/3, 22/3 sessions/subjects)

**DECISION TAKEN**: doc01 treats the 22-session/9,061-unit vintage
(`corpus_manifest.json` + `unit_inclusion_v1.csv`, 2026-08-14/17) as authoritative throughout
this document set, and explicitly labels the 13-session legacy doc and the 23-session
2026-07-28 inventory as historical/superseded. This is a low-risk documentation decision — it
doesn't invent a number, it picks the most recent, most cross-validated source and says so. The
23→22 session change (removal of `sub-C31o_ses-230630`, 167 units — arithmetic 9228−167=9061
matches exactly) is stated as the most likely explanation but **not independently confirmed by
an explicit removal record** — flagged as a residual gap, not fully closed.

### 10. `build_oplusplus_census.py`'s module docstring is stale relative to its own code

**FLAGGED, NOT DECIDED (code file, out of scope for a documentation audit)**: the docstring
claims FEF/PFC restriction; `main()` sets `require_higher_order=False`, and live output spans
all 11 areas. Doc03 states the discrepancy plainly. A one-line docstring fix is genuinely
low-risk, but it is a code-file edit, which this audit's scope (documentation synthesis) did not
include — recommended, not applied.

### 11. `build_unified_class_census.py`'s docstring mislabels S+/S− as "S1-derived"

**FLAGGED, NOT DECIDED (code file, same reasoning as #10)**. The line "S+/S− (local-baseline,
likelihood-of-firing)... see jnwb/unit_inclusion.py for the classifier itself" is traced in doc03
to be incorrect — S+/S− actually come from `jnwb.unit_classification.classify_unit`, not
`unit_inclusion.py`. Recommended one-line fix, not applied.

### 12. `jnwb/__init__.py` version-metadata inconsistency

**DECISION TAKEN (trivial, cosmetic)**: doc02 notes `__release_date__` (2026-06-25) disagrees
with the module docstring's stated date (2025-06-24) and moves on — this has no scientific or
pipeline consequence and needed no further action beyond noting it.

### 13. Four non-identical frequency-band-edge tables live in the package simultaneously

**FLAGGED, NOT DECIDED.** `connectivity.CANONICAL_BANDS` (the "settled" table per CLAUDE.md),
`analyzers.TFRAnalyzer.BANDS`, `omission_identity.LFP_BANDS`, `artifact_repair.DEFAULT_BANDS` —
four different edge sets, doc02 full table. Consolidating around one canonical table is a real
code change with downstream numeric consequences for any script currently using a non-canonical
table (e.g. `omission_identity.py`'s single combined 30-80Hz gamma vs the canonical split
low/high gamma) — not low-risk, left for Hamm.

### 14. `fig07`'s status label ("semi") disagrees with its own revision score (10/100, "major revision")

**FLAGGED, NOT DECIDED.** Doc05 states the inconsistency. Given the large amount of concurrent
uncommitted work across the figures tree (see below), this audit did not touch any figure file
to correct a status table — flagged for Hamm or the next figure-focused session.

### 15. `fig03_unit_census.py`'s stats step crashes after writing the SVG

**DECISION TAKEN (no fix, correctly scoped)**: confirmed via code tracing during this session's
earlier fig03 work that the crash (`chi2_contingency` zero-expected-frequency cell in panel e's
contingency table) is pre-existing and unrelated to this session's O++ correction — the affected
`table8`/`class8()` codepath doesn't touch any column this session's edits changed. **Correctly
left unfixed** — this is a statistics-logic decision (how to handle a degenerate contingency
table), not a documentation fix, and CLAUDE.md's stop-conditions explicitly call for surfacing
rather than silently patching exactly this kind of issue. `fig03_stats.md`/`fig03_receipt.json`
are stale relative to the current `fig03.svg` as a direct consequence — noted in doc05.

### 16. Heavy concurrent uncommitted work across `context/figures/`

**DECISION TAKEN (caution, not a fix)**: doc05 documents the full git-status picture — all three
shared infra modules (`figstyle.py`, `figstats.py`, `svgassemble.py`) plus a large in-flight
L-track/S-track are uncommitted simultaneously. This audit did not edit any figure file, and
flags (per the existing memory note on a concurrent Cursor session) that any figure-pipeline
number should be re-verified against a fresh `git diff` before being cited as final.

## LOW severity — noted, no action needed

- `jrsa(metric="granger"/"transfer_entropy"/"phase_slope")` vs `connectivity.py`'s dedicated
  functions are two independent code paths computing nominally the same statistics, not confirmed
  to numerically agree (doc02/doc06). No consequence found yet; worth a reconciliation test if
  either is ever used interchangeably.
- `statistics.py`'s `bootstrap_ci`/`permutation_test` hardcode `np.random.default_rng(42)` inline
  with no seed parameter (local, not global — distinct from and less severe than #1 above), doc02.
- `grand_oplusplus_units.csv` is an orphaned artifact (superseded output still on disk, only its
  own writer script and one unmaintained archived script reference it) — correctly preserved per
  Conservation, no action needed (doc03).
- `fig02_spiking_exemplar_rasters.py` hardcodes a stale `D:/workspace/omission/...` path rather
  than routing through `jnwb.paths` — a path-convention inconsistency, not confirmed broken
  (doc03).
- `outputs/classification/unit_layers.csv`'s `quality` field (binary 0/1) and
  `unit_inclusion_v1.csv`'s `quality_tier` field (3-way mua/unstable/stable) share no common
  scheme despite adjacent naming — already treated as distinct throughout doc01/doc03, no further
  action needed beyond the existing caution.

## Summary — what changed as a result of this audit

Nothing outside `context/00_*.md`–`context/09_*.md` was edited. No code, skill, or doctrine file
was modified. Every "DECISION TAKEN" above is a documentation-scope choice (which number to cite
as current, which vintage to treat as authoritative, which stale reference to flag rather than
silently trust) — never a change to a live pipeline, a skill's routing content, or CLAUDE.md/
memory. Every conflict with a scientific or code consequence is marked **FLAGGED, NOT DECIDED**
above and awaits Hamm.
