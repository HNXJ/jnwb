# 08 — Project State and Open Items

Generated 2026-08-17, synthesized from `context/PROJECT_STATE.md` (384 lines, read in full) and
`context/EVIDENCE_ARCHITECTURE.md` (98 lines, read in full). **`PROJECT_STATE.md` remains the
canonical source for what is scientifically established, superseded, or blocked** — this
document indexes and cross-references it against the rest of this audit; it does not replace it.
Re-read `PROJECT_STATE.md` directly before restating any of its content, per CLAUDE.md's
explicit instruction that prose in a doctrine file is never the source of truth for what a claim
earns its standing from.

## Evidence architecture — the claim ladder

`EVIDENCE_ARCHITECTURE.md` defines four claim quantities (prevalence, magnitude, information,
mechanism), an L0–L4 claim ladder, and the canonical evidence chain: data source →
preprocessing → parameters → software/environment → seed (if any randomness) → outputs. A
receipt is this chain made explicit and attached to a number. Graph edges use the vocabulary
`derived_from`/`tested_by`/`supports`/`contradicts`/`qualifies`/`supersedes`/`blocks` (see doc07's
`labyrinth` summary for the schema itself). **Where the evidence architecture's own acceptance
conditions conflict with a receipted result in `PROJECT_STATE.md`, `PROJECT_STATE.md` wins** — it
is explicitly `proposed` status, not yet the final word on its own procedural rules.

## Corpus status — see doc01 for full detail

22 sessions, 3 subjects (Cajal/C31o, Ivan/V182o, Joule/V198o), 9,061 units as of 2026-08-14/17.
`tfr_ok=22/22`; `suite_tfr_ready=0/22` — **still an open readiness-gate question**, not resolved
by this audit (doc01 flags this for a direct read of `scripts/build_session_readiness.py`).

### TFR-readiness-gate bug history (fixed 2026-08-14)

Two stale scan patterns previously caused `discover_corpus.py` to undercount TFR-ready sessions
(matching on raw NWB stem instead of `session_prefix`) — this produced the 2026-08-12 incident
where the readiness table claimed zero TFR-ready sessions while hundreds of arrays sat on disk.
Fixed; see doc01 for the mechanism.

## Paradigm section (see doc00 for the full trial-grammar reference)

12 conditions (structured A/B families + R-family random controls), "ten analysis areas"
convention (V3 subdivisions pooled to V3a/d). AAAB is the structured **standard**, not a random
control — a terminology precision worth restating in any manuscript prose per the `manuscript`
skill.

## Superseded/retracted claims — do not restate these numbers

`PROJECT_STATE.md`'s superseded/retracted table, receipts in
`artifacts/.lab/census_provenance_synthetic_finding_20260728.json`:

- The 2026-07-27 handout's **synthetic 8,597-unit census** — fabricated, not measured.
- **O+=421/8,597 (4.90%)** — retracted synthetic prevalence figure. `omission.jnwb_ext.unit_classification`'s
  own `assign_o_plusplus_from_template_table` docstring explicitly warns against restoring this
  number (doc02/doc03).
- **GLMM OR=3.08** — "never fitted." Do not cite as a real model output under any circumstance.

These three numbers are the project's most dangerous residual risk: they read as plausible,
specific, and precise, and have no computation behind them. Cross-reference doc03's "six
different O+ counts" table before ever writing an O+ prevalence number in prose — none of the
six legitimate counts is 421/8597.

## Current findings with receipts (as of `PROJECT_STATE.md`'s last update)

- **LFP band census v2** — see doc04/doc05 for the current connectivity and GLMM state
  (fig05: 2/45 Holm survivors, 11/45 BH-FDR survivors).
- **V3a/d vs V1 elevation GLMM** — feeds fig05.
- **Spiking onset-latency hierarchy** (H1/H2/H3) — see doc05's L5/S5/S6 entries; L5's own result
  is `H3_simultaneous_or_ambiguous` (honest null, triggered L6). S5 is explicitly labelled
  **[THESIS FALSIFIER]** and gates on the same acceptance criterion (report
  `discriminating:false` rather than force a hierarchy claim if CIs overlap zero).

## Structural facts

- Area and subject are confounded corpus-wide but the area×animal design graph is connected
  (every area in ≥2 animals, V4 in all 3) — see doc01's full coverage table and doc06's
  statistical-inference rule this fact feeds.
- 27/51 probes span multiple areas at the channel-64 boundary (doc01: 26/28 multi-area probes
  split at channel 64; one three-area probe splits at 42/85; one probe's area mapping is
  undeterminable and excluded).
- vFLIP layer coverage is imbalanced (53.9% overall, differs by animal and ~3× by area — doc01).
- All 6,655 legacy sidecar-labelled units carry `layer=Superficial` — a **constant column**,
  CLAUDE.md tripwire #8 violation if ever interpreted as real (doc01/doc03's `grand_s_and_o_units.csv`
  layer-column note references the same underlying defect in a different table).
- **"Four passes report four different O+ counts"** (386, 19, 7, 421-retracted, per
  `PROJECT_STATE.md`'s own count as of its last update) — superseded in scope by this audit's
  doc03, which found **six** distinct O+ numbers once the S1 and modern-native classifiers are
  included (265, 1207, 68, 359/307, 31, 319). `PROJECT_STATE.md`'s four-number table predates the
  S1 and modern-native classification work documented in doc03 — treat doc03 as the more current
  and complete accounting, `PROJECT_STATE.md`'s four-number table as a historical snapshot worth
  reconciling on its next edit.

## Blocked/gated items (per `PROJECT_STATE.md`'s table, cross-referenced against this audit)

| Item | Status per PROJECT_STATE.md | This audit's cross-check |
|---|---|---|
| fig03 O+ prevalence | still owed | doc03 now documents the full O+/O++ count landscape; fig03's own current O++ definition (52 units, V4/TEO/FEF/PFC, r≥0.65) is the most current single number, but "O+ prevalence" as a headline still needs an explicit choice among the six candidates in doc03 |
| fig04 do-not-promote 0.601 accuracy | blocked, `truth_safe_unverified` | Confirmed still blocked in doc05 — cycle-deconfounded result ~chance (0.4960), do-not-promote conclusion holds |
| fig05–fig07 caveats | various | doc05 has current status/scores for all three; fig07's revision-score-vs-status-label inconsistency (labelled "semi" but scored 10/100) is newly flagged there |

## §6a LFP-primary spec (L0–L17) — status vs this audit

`PROJECT_STATE.md` records L0–L10 done, L11/L12 unblocked as of 2026-08-17 but not yet built,
L13–L17 deferred. **This audit's doc05 confirms L0–L10 exist on disk and are all untracked
(uncommitted)** — matches "done" in the sense of "code exists and has run," not necessarily
"reviewed and locked." L7 and L9 each had a real bug found and fixed during their own build (node
-key collision causing silent data loss; pseudoreplication in session-aggregation CI) — both
already reflected in the current L-track output, not separately pending.

## §6b SPK-primary spec (S1–S17) — status vs this audit

`PROJECT_STATE.md` records S1 done/reviewed/approved 2026-08-17 (new criterion passes 281/9061,
3.1%, vs old template-correlation criterion's 68/9061, 0.75% — net +213 units); S2/S4-S8/S10/S11
unblocked not yet built; S3 needs a non-hand-picked selection rule; S9/S12-S17 not yet reviewed.

**Cross-check against doc03's live numbers**: doc03's own recomputation of S1's inclusion count
from `unit_inclusion_v1.csv` reads `is_omission_inclusion_new=319` (full corpus, all quality
tiers) — not 281. This is very likely a **population-scope difference** (281/9061 in
`PROJECT_STATE.md` may be quality-filtered or an earlier run; 319 in this audit's direct CSV read
is the unfiltered full-corpus count) rather than a contradiction, but it was **not reconciled by
this audit** — flagged in doc09 as needing a direct check of which population each number
describes before either is restated as the S1 headline number.

**This audit's doc05 additionally found S2, S5, and S6 already exist on disk** (untracked,
mtime 2026-08-17) — `PROJECT_STATE.md`'s "S2/S4-S8/S10/S11 unblocked not yet built" statement is
stale relative to the current working tree for at least S2, S5, S6. S5 is labelled **[THESIS
FALSIFIER]** in its own docstring and S6 is its required positive-control companion — both
appear to be recently built, not merely unblocked. Flagged in doc09; `PROJECT_STATE.md`'s S-track
status table should be refreshed against the actual `context/figures/` directory listing before
its next citation.

## Figure-4 identity-decoding bug fix (RESOLVED 2026-08-16)

`unit_id`-vs-row-position bug fixed; mean LOCO accuracy 0.4960 post-fix; "do not promote 0.601"
conclusion holds. Confirmed consistent with doc05's fig04 entry (`truth_safe_unverified` pending
full-corpus receipt + permutation null + visual review — the bug fix itself is resolved, the
figure's overall promotion status is not).

## Open questions (per `PROJECT_STATE.md`, 6 items as of last update)

Including **"Graph health — re-derive, do not inherit... graph now holds 395 JSON nodes"** — per
`labyrinth`'s own rule (doc07), this count should be re-verified via
`scripts/validate_labyrinth_claim_status.py` rather than restated from memory; not re-run by this
audit (scope was documentation, not graph validation).

## Manuscript lineage

`context/drafts/omission-a-draft-v3.md` is current; DOCX lineage retained for history; a Word
lock file has been observed on disk (a live edit in progress in Word, separate from this
session's own working tree — treat as another concurrent editor, same caution as the concurrent
Cursor-session memory note in doc07).

## §9 model choice — "currently unsettled" per `PROJECT_STATE.md`

Not resolved by this audit; see doc06 for the general model-choice rules
(three-subjects-cannot-identify-a-random-effect-variance, area/subject confounding) that bound
what any eventual resolution can look like.
