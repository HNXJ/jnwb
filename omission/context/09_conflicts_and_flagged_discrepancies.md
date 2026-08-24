# 09 — Conflicts and Flagged Discrepancies

Generated 2026-08-17, compiled last from the full audit (docs 00-08). Per Hamm's explicit
instruction, low-risk documentation-only conflicts were resolved directly (marked **DECISION
TAKEN** below, with the reasoning stated); anything touching a scientific claim, a doctrine file
(CLAUDE.md/memory), a skill file, or live code was left for Hamm (marked **FLAGGED, NOT
DECIDED**) — per `labyrinth`'s Amendment rule, skill and doctrine changes require independent
confirmation before human approval, an agent does not amend them unilaterally, and no audit
should quietly pick a winner among live scientific numbers.

## HIGH severity — needs Hamm's attention first

### 1. `omission/jnwb_ext/report.py::generate_report` fabricates data and globally seeds RNG

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

**RESOLVED 2026-08-24.** Confirmed (a): the corpus fully migrated to `.npz` on 2026-08-11
(`scripts/precompute_tfr_arrays.py`'s own docstring: "CONSUMERS MUST BE UPDATED... any other
consumer needs the same update"). Verified directly against the live analysis volume — which
had itself moved from `D:/analysis` to `E:/analysis` since this doc was written, a second,
independent drive remap — E:/analysis/tfr_arrays holds exactly 970 `.npz` files, 0 `.npy`,
matching this doc's original count. `OmissionSession.tfr_from_preprocessed()` globbed only
`*.npy` and was silently returning `None` for every real session.

**Fix applied**: `tfr_from_preprocessed()` now mirrors `scripts/compute_channel_band_power_
census.py`'s established dual-format precedent — globs both `*.npy` and `*.npz`, prefers `.npz`
on collision (a stale legacy `.npy` must not silently win by glob order), loads the `power` key
from `.npz`. All 8 real call sites (`factories.py`, `functions.py`) reduce over the channel axis
without indexing by raw physical-channel-id, so the new format's channel-subsetting (vs. the
legacy full-128-padded array) does not change their behavior — only the loader's glob pattern
needed to change. Raw-channel-id recovery via the `.npz`'s `channels` key is not exposed through
this function, since no current caller needs it. Tested against real `E:/analysis/tfr_arrays`
data plus new synthetic-data unit tests (`tests/test_tfr_from_preprocessed.py`:
`test_tfr_from_preprocessed_loads_npz`, `test_tfr_from_preprocessed_prefers_npz_over_stale_npy`).
Full detail: doc01/doc04 (original discovery).

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

**RESOLVED 2026-08-24.** The population-scope hypothesis (281 as a quality-filtered subset of
319) is **ruled out**: broken down by `quality_tier`, the inclusion counts are mua=105,
stable=48, unstable=166, none of which is 281 or combines to it as a clean subset. The live CSV
is self-consistent at 319 two independent ways — the `is_omission_inclusion_new` column sum and
the `transition` column's `gained + unchanged_included` (288 + 31 = 319) agree with each other,
but neither matches `PROJECT_STATE.md`'s cited breakdown (245 gained + 36 unchanged-included =
281). Both are genuinely different runs of the same deterministic (`cfg_new_seed=42`) pipeline,
not a subset relationship. The CSV is not git-tracked (`outputs/` is gitignored), so its edit
history isn't independently recoverable — but `PROJECT_STATE.md`'s own S1 row already designates
`unit_inclusion_v1.csv` as canonical; per Hamm, that designation wins over the prose summary,
which had simply gone stale relative to a later regeneration of its own canonical source.
`PROJECT_STATE.md` corrected to 319 with the full breakdown; 281 is recorded there as the earlier,
now-superseded figure rather than silently dropped. Detail: doc08 (original discovery).

### 5. `session_readiness.csv::suite_tfr_ready` is `False` for all 22 sessions

**RESOLVED 2026-08-24.** Root cause: `scripts/build_session_readiness.py` itself was already
correctly reading `.npz` (fixed 2026-08-14, predating this audit) and `tfr_ok` was already `True`
for all sessions once item 2's fix + correct env vars were in place. The actual blocker was
`sidecar_ok=False` for all 22 — `suite_tfr_ready` also requires per-session metadata sidecars
(`electrodes.csv`/`units.csv`/`events.csv`/`h5_paths.json`) that did not exist anywhere on the
currently-mounted data volumes. Their only generator,
`scripts/archive_oneoff/build_session_sidecars.py`, hardcoded the pre-2026-08-08-migration path
`D:/workspace/data/metadata/` (already on `PROJECT_STATE.md`'s own "Superseded paths -- do not
restore" list) — every sidecar write since the migration landed somewhere no downstream consumer
ever read from, and the step was simply never re-run against the current layout. This was a
correctly-reported unmet real prerequisite, not a stale/broken readiness column.

**Fix applied**: `build_session_sidecars.py`'s `--meta-root` default now resolves via
`jnwb.paths.meta_dir()` instead of the hardcoded literal. Ran the corrected script against the
full corpus (22/22 sessions, ~7.6s total — h5py reads only specific NWB groups, not full-file)
against the current `E:/analysis` volume (see item 2 / PROJECT_STATE.md for the D:->E: remap).
Re-ran `build_session_readiness.py`: `tfr_ok=22/22`, `sidecar_ok=22/22`,
`suite_tfr_ready=22/22` (was 0/22). `session_readiness.csv`/`.json` are gitignored local
artifacts (`omission/artifacts/*`), regenerated but not committed. Full omission test suite
re-verified after the code fix: 290 passed, 27 skipped, 0 failures. Detail: doc01 (original
discovery).

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
live replacements (`spectral.imaginary_coherency`, `omission.jnwb_ext.report`). **Not applied to the skill
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

**RESOLVED 2026-08-22**: independently confirmed by two direct checks, not arithmetic inference.
(1) `python omission/scripts/discover_corpus.py --check` (rerun live against the current
filesystem) resolves exactly 22 sessions from `D:\nwb\omission`. (2) Direct directory listing of
`D:\nwb\omission` shows all 22 of those sessions' `.nwb` files present, and confirms
`sub-C31o_ses-230630_rec.nwb` is absent. This is a genuinely missing NWB file, not a duplicate,
a different product corpus, or an eligibility filter — the session already showed an unresolved
`NWB (GB)` value in the 2026-07-28 inventory table, suggesting it may never have fully resolved
even then. `omission/context/inventory/{SESSIONS,CONDITIONS,UNITS}.md` (the 23-session source)
have been marked superseded in place, including noting that their own cited regeneration command,
`scripts/build_corpus_inventory.py`, does not exist in the current repo. Gap closed.

### 10. `build_oplusplus_census.py`'s module docstring is stale relative to its own code

**FLAGGED, NOT DECIDED (code file, out of scope for a documentation audit)**: the docstring
claims FEF/PFC restriction; `main()` sets `require_higher_order=False`, and live output spans
all 11 areas. Doc03 states the discrepancy plainly. A one-line docstring fix is genuinely
low-risk, but it is a code-file edit, which this audit's scope (documentation synthesis) did not
include — recommended, not applied.

### 11. `build_unified_class_census.py`'s docstring mislabels S+/S− as "S1-derived"

**FLAGGED, NOT DECIDED (code file, same reasoning as #10)**. The line "S+/S− (local-baseline,
likelihood-of-firing)... see omission/jnwb_ext/unit_inclusion.py for the classifier itself" is traced in doc03
to be incorrect — S+/S− actually come from `omission.jnwb_ext.unit_classification.classify_unit`, not
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
