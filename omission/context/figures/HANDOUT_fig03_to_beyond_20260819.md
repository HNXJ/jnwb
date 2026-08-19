Version: 2026-08-19
Status: handout for a fresh chat session — reconciles `REVISION_PLAN.md` (2026-08-09/11,
canonical sequencing), `FIG03_TO_FIG07_PLAN_20260817.md` (discussion draft, not yet adopted),
`context/PROJECT_STATE.md` (§6a/§6b, resolved 2026-08-17), and this session's uncommitted
fig03 work (2026-08-18/19). Not itself a canonical doctrine file — read it, then re-verify
anything load-bearing against the sources it cites, per CLAUDE.md's "never quote from memory"
rule.
Truth status: `truth_safe_unverified`

# Handout: fig03–fig07, their supplements, and the SPK/LFP analysis tracks

**Purpose.** A new chat session was about to start cold on this territory. This document is
the fastest path to the same picture — what's locked, what's mid-revision, what's blocked,
what's a live open bug, and what's a genuine unresolved discrepancy between two doctrine
sources. It intentionally does not resolve every discrepancy it names; those need Hamm.

**Before trusting any number here:** re-run `scripts/discover_corpus.py` or read
`artifacts/data/corpus_manifest.json` for corpus counts, `git status`/`git log` for what's
actually committed vs. uncommitted, and the cited `artifacts/.lab/*.json` receipts for any
claimed result. This file is a map, not the territory.

---

## 0. Where truth actually lives (repo doctrine, unchanged)

| Question | Source |
|---|---|
| Data paths, corpus counts | `scripts/discover_corpus.py` → `artifacts/data/corpus_manifest.json` |
| What's scientifically established / superseded / blocked | `context/PROJECT_STATE.md` |
| How a claim earns standing | `context/EVIDENCE_ARCHITECTURE.md`, `labyrinth` skill |
| Figure sequencing and scores | `context/figures/REVISION_PLAN.md` (canonical) |
| Figure pipeline conventions | `omission-figures` skill |

---

## 1. Canonical score table (`REVISION_PLAN.md`, 2026-08-09/11 — still the sequencing authority)

| # | Figure | Score | Blocking issue as last stated |
|---|---|---|---|
| 2 | Spiking exemplar rasters | 100/100 | none — final |
| 1 | Recording topology and paradigm | 90/100 | none stated |
| 3 | Unit census | 80/100 | "which subplots" — since substantially answered by this session's work, see §3 |
| 4 | Omission identity decoding | 70/100 | leakage-safe rerun landed; cycle-deconfounded accuracy ≈ chance (0.4960); do-not-promote conclusion holds |
| 5 | LFP band-power hierarchy GLMM | 60/100 | which subplot — still unscoped by Hamm as of 2026-08-17 |
| 6 | V1/PFC condition TFR | 50/100 | stale lock **and** a confirmed live bug (§4) |
| 7 | Population firing × LFP power | 10/100 | fully redesigned 2026-08-05, has a receipt now, but not yet re-scored by Hamm |

Original sequencing rule: score-ascending, **7 → 6 → 5 → 4 → 3 → 1 → 2**. The 2026-08-17
discussion draft (`FIG03_TO_FIG07_PLAN_20260817.md`) questions whether this order still holds
given fig03's live mid-revision state and fig07's now-receipted headline — **not decided,
flag it if a new session is about to pick a figure to work on next.**

**Standing rule from `REVISION_PLAN.md` itself:** no figure gets re-locked
(`fig0N_finalized.*` regenerated) until its score is agreed ≥90 **and** Hamm has visually
confirmed the re-rendered panels. A score only moves with a receipt, never by restating intent.

---

## 2. fig03 — Unit census (most current section; this session's work, all uncommitted)

**As of 2026-08-11** (`REVISION_PLAN.md` changelog): closure pass done, corpus-size change (21→22
sessions) re-verified, no discrepancy found, main-figure denominator 2,921 legacy-screened units.

**As of 2026-08-17** (`FIG03_TO_FIG07_PLAN_20260817.md` §1, §3, §4.1): O++ definition corrected
in place — `attach_template_corr_oplusplus`: r≥0.65 template correlation, restricted to
V4/TEO/FEF/PFC → **52 unique units** (was r≥0.60, no area restriction). A pre-existing stats
crash was found (still unfixed, see §4 below). A cross-cutting discrepancy with fig07 was
flagged (§5 below).

**This session (2026-08-18/19, all currently uncommitted — check `git status` before assuming
any of this is final):**

- **Panel A** (8-class composition by area): height/legend-offset layout bug fixed (was leaving
  ~20% blank space under the panel relative to Panel B's row height). No content change.
- **Panel B** (O++ distribution by area): redesigned per Hamm's direct request — was a floating
  CI bar showing each area's O++ share of its **own** R-family candidate pool (per-area
  denominator); now two bars grounded at 0 showing each area's share of the **corpus-wide 52-unit
  O++ total** (fixed denominator, sums to 100% across areas). Real counts: 0/52 for
  V1/V2/V3a-d/MT/MST+FST, 15/52 V4, 12/52 TEO, 11/52 FEF, 14/52 PFC.
- **Panels C-F** (S+/S++, S-/S--, O+, O++ grand averages by condition): two methodological
  fixes applied 2026-08-19 per Hamm's standing instruction that filters must not leak timing
  backward:
  1. `_gaussian_smooth()` changed from a symmetric/zero-phase (edge-reflected) kernel to a
     **causal, one-sided** kernel — output at bin t now depends only on bin t and earlier bins,
     never on the future. Confirmed on real data: Panel F's RXRR trace no longer rises during
     the d1 epoch before the true p2 omission boundary; the rise now begins at the boundary
     itself.
  2. The SEM/uncertainty band is now left **unsmoothed** while the mean line stays smoothed —
     previously both were smoothed with the same kernel, which made the error band look as tidy
     as the point estimate and understated real bin-to-bin uncertainty.
  - Also fixed (2026-08-18, found while double-checking, not requested): a real y-axis-label
    clipping bug on panels E/F (trial-pooled classes) — label text was overflowing the rotated
    axis height at fontsize 7; rewrapped to 3 shorter lines at fontsize 6.
- **New standing convention** (Hamm, 2026-08-18, scoped to fig03 only so far, not yet applied to
  fig01/02/04-08): every figure folder should hold both the full assembled `fig0N.svg`/`.png`
  **and** a matching `fig0NA.svg`/`.png`, `fig0NB.svg`/`.png`, ... per lettered panel, for fast
  precise iteration. Implemented via a new `emit_lettered` parameter on `svgassemble.assemble()`.
- **New capability**: `svgassemble.rasterize()` — a playwright/headless-Chromium SVG→PNG
  renderer, confirmed working on this machine (cairosvg, reportlab, and browser `file://`
  navigation all previously failed here per the `omission-figures` skill; this is a new, tested
  addition, not yet folded into that skill doc). Closes a real gap: `fig03.png` (the assembled
  figure's own PNG companion) had been missing since before this session.
- **New supplement**: `panel_grand_average_matched_n()` — a matched-N bootstrap sensitivity
  panel (percentile bootstrap, B=1000, seed=0, local RNG) recomputing every class's grand
  average at the same nominal N (52, O++'s real count) to check whether panels C-F's real,
  unequal-N band-width differences persist under matched precision. Explicitly a sensitivity
  supplement, not a replacement for the honest unequal-N primary panels — Hamm's own framing,
  confirmed via `AskUserQuestion`.
- **Open, NOT fixed**: Panel F (O++) still shows a modest early-rise pattern in its RXRR trace
  that could be residual smoothing bleed or genuine anticipatory ramping (O++ units are partly
  classified by ramp significance near omission) — ambiguous, flagged, not resolved. A separate
  background audit task was spawned (`task_c779e425`, "Audit TFR/smoothing filters for acausal
  lookahead") to check whether the same acausal-kernel pattern exists elsewhere in the project
  (confirmed already: `context/figures/fig06_v1_pfc_condition_tfr/fig04_v1_pfc_condition_tfr.py`
  has independent symmetric/reflect-padded smoothing on TFR data). Check whether that task has
  been started or dismissed before assuming it's still open.
- **Still unfixed**: the §4.1 stats crash below — same crash, same location, confirmed across
  every one of this session's ~7 full pipeline reruns, always occurring after every real output
  (SVGs, PNGs, assembly, rasterization) has already been written successfully.

**A new supplement not yet folded into this session's discussion**: per
`FIG03_TO_FIG07_PLAN_20260817.md` §2, `fig03_supp_area_composition_battery.py` — a 9-panel
per-area composition battery built the same week, status unreviewed by Hamm as "part of the
locked fig03 deliverable" vs. "standalone supplement."

---

## 3. fig04 — Omission identity decoding

70/100 per `REVISION_PLAN.md`. Per the 2026-08-08/09 audit and later fixes: the three real `_v2`
source tables exist (earlier "synthetic data" diagnosis was wrong); random-CV accuracy (~0.601)
is confounded by sequence/cycle structure; the leave-one-cycle-out, cycle-deconfounded accuracy
is **≈ chance (0.4960)** — a valid null, reported as such, do-not-promote conclusion holds. A
GLMM-mislabel item (rename artifacts/panel to describe an L2-logistic-regression, not a mixed
model, unless an actual mixed model is fit) was flagged and, per `PROJECT_STATE.md`'s
"RESOLVED 2026-08-16" note, a related unit-identity bug in the cycle-deconfounded estimate was
found and fixed — conclusion unchanged after the fix. **Re-verify current status directly from
`PROJECT_STATE.md`'s fig04 section before treating any of this as the latest word** — that
section has had multiple dated revisions (2026-08-13/14/16) not all reproduced here.

---

## 4. fig05 — LFP band-power hierarchy GLMM

60/100 per `REVISION_PLAN.md`, "which subplot" never named by Hamm. Per the 2026-08-17
discussion draft: now has a receipt — **2/45 cells survive Holm-Bonferroni** (FEF/PFC low-gamma
vs. V1), 11/45 survive the more permissive BH-FDR. The new L-track's `L2_band_power_traces`
targets this same figure slot (see §6). A separate `band_power_hierarchy_supplement` (an earlier,
different attempt) was demoted the same day fig05's GLMM landed — not group-significant, has
its own uncommitted edits, worth a `git diff` before assuming its state.

**Open:** Hamm still needs to name the specific subplot needing revision — outstanding since
`REVISION_PLAN.md`'s 2026-08-09 request, unanswered as of the last written record.

---

## 5. fig06 — V1/PFC condition TFR

50/100, flagged stale-lock in `REVISION_PLAN.md`. Confirmed still stale (panel layout / SEM
estimator / GLMM section have all diverged from the 2026-08-03 lock).

**Confirmed, live, unfixed bug** (verified directly against the file just now, 2026-08-19):
`context/figures/fig06_v1_pfc_condition_tfr/fig04_v1_pfc_condition_tfr.py:345` —

```python
CONDITION_MAPS = r"D:/workspace/omission/outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz"
```

This is a dead path (even if `D:/workspace/omission` existed on this machine, it would read the
pre-corpus-migration **v1** extraction, not the current canonical **v2**:
`outputs/condition_tfr_maps_p1d1p2d2p3_v2/maps.npz`, per `PROJECT_STATE.md`, resolved
2026-08-14). An untracked sibling script, `fig04xx_3d_condition_tfr.py`, already points at the
correct v2 path — the fix is mechanical (repoint the constant) but is a live shared-script edit,
so treat it as its own small commit, separate from any panel-layout work, and check the
concurrent-Cursor-session caution first (`project_concurrent_cursor_session` memory).

**Open:** subplot scoping from Hamm, same as fig05, still outstanding.

---

## 6. fig07 — Population firing × LFP power

10/100 in `REVISION_PLAN.md`'s original table, but that number is stale: fully redesigned
2026-08-05 with its own README (read in full — not reproduced here). Headline: **band is the
dominant factor** (high/low gamma ≫ theta/alpha/beta, Holm p<1e-5); **O+ units are less coupled
than Null/S+** (Holm p<2e-5); no condition-group effect. The original per-unit PPC plan was
demoted to `svg/fig07_supp_ppc.svg` (0/60 null). A 2026-08-06 relayout split **O++ out as its
own 15-unit group**.

**Unresolved cross-figure discrepancy (fig03 vs fig07), not fixed by this session:**
fig03's current O++ definition (r≥0.65, V4/TEO/FEF/PFC-restricted) yields **52 units**; fig07's
own O++ group (2026-08-06 relayout) is **15 units**. These are almost certainly two different
vintages of the same template-correlation method — fig07 predates fig03's r≥0.60→0.65 correction
and area restriction by roughly two weeks — but **neither figure's code cross-references the
other**, and each states its own number with no vintage note. Two options on the table, per the
2026-08-17 discussion draft, neither chosen yet:
1. Re-run fig07's O++ split against the current 52-unit definition and see whether the GLMM's
   "O++ not significant, n too small (p=0.71)" result changes with the larger population — a
   real scientific question, not bookkeeping.
2. Leave both as-is, state the vintage difference explicitly in both figures' captions, if
   Hamm judges fig07's headline doesn't depend on the exact O++ boundary (its main GLMM factor is
   O+ vs. Null vs. S+, not O++ specifically).

**Open:** subplot scoping from Hamm (same open item as fig05/fig06), and this O++ reconciliation.

---

## 7. fig08 and beyond — supplements, the L-track, and the S-track

### 7a. fig08 — neuron type × layer × firing rate × waveform × LFP relationships

Not in `REVISION_PLAN.md`'s original table at all (proposed for a future revision). Generated
2026-08-16, receipt at `context/figures/fig08_neuron_type_layer_lfp/receipt.json`. This is the
delivered result of an earlier multi-part plan (pre-registered confirmatory families + a
separately-labelled exploratory sweep) — **that plan is done, not pending**, if this handout is
read alongside an older saved plan describing it as future work, that plan is stale.

Four confirmatory panels, each its own pre-registered Holm/BH family:
- **A** — layer enrichment by class, Holm-significant cells only, within-animal × within-area
  scope, population = layer-informative units (sup/deep; na/mid/unmatched pooled to Null).
- **B** — firing rate vs. area's other units, Holm-significant cells only, within-area, SUA only.
- **C** — corrected PPC hit-rate, class × band × area (session = unit of inference, per-session-z
  + Clopper-Pearson pooling — the same corrected design used by the L-track's connectivity
  results); V4's n=3 hits excluded from the panel as fragile.
- **D** — LFP band-power onset latency at native 10ms resolution; 0/38 cells violate the 10ms
  general neural-delay floor.

An exploratory sweep (`outputs/relationship_search/exploratory_sweep_all_pairs.csv`) exists but
is deliberately reported only as caption text, never drawn as a panel, so it can't be mistaken
for a confirmatory result. `placeholder_used: false`; all four panels PNG-visually-reviewed per
the receipt. **Needs a score/slot assigned in the next `REVISION_PLAN.md` revision** — currently
invisible to that table.

### 7b. The LFP-primary track (L0–L10), all uncommitted

An 11-directory, spec-driven track (`context/figures/L0_pooling_reconciliation` through
`L10_mutual_information_convergence`). Per `PROJECT_STATE.md` (resolved 2026-08-17), **L0–L10
are all `done`**, with real results:

| Item | Headline |
|---|---|
| L2 band-power traces | targets the fig05 slot |
| L3 laminar power profile | done |
| L4 CSD omission response | done, not yet publication-quality (Hamm's own note) |
| L5 onset latency, cross-area | **honest null** — every band returned `H3_simultaneous_or_ambiguous` |
| L6 volume-conduction control | same-probe adjacent-depth pairs show high zero-lag coupling (0.6-0.9 raw, collapsing under Laplacian re-referencing) — needed to interpret L5's null |
| L7 cross-area power correlation | targets fig06 slot; same-probe volume-conduction pattern cross-validated; `sub-V182o_ses-260715` flagged as a likely session-wide artifact (13-15/15 pairs significant in every band) |
| L8 cross-area coherence | same-probe pairs show "conducted, not interacting" signature (high standard coherence, near-zero imaginary coherency) — L6/L7/L8 now three independent statistics agreeing on this |
| L9 directed LFP-LFP (GC+PSI) | only `FEFsup-FEFdeep` (same-probe) has a 3-session-replicated, zero-excluding CI (theta) — read with the L6/L7/L8 volume-conduction caveat, not as feedforward/feedback evidence |
| L10 mutual information convergence | MI and Pearson r agree strongly (Spearman rho 0.32-0.95, all positive, 30/30 combinations) — no missed nonlinear structure |
| L11, L12 (LFP→SPK) | **unblocked as of 2026-08-17** (S1 landed) but **not yet built** |
| L13-L17 | deferred by the spec's own text — do not build unless asked |

Two real bugs were found and fixed **during** this track's build, both already reflected in
current output, each with its own evidence node:
- **L7**: a node-key collision silently dropped one probe's data for FEF-on-two-probes sessions
  (`artifacts/.lab/L7-cross-area-power-correlation-20260817.json`).
- **L9**: a pseudoreplication bug let one session count as multiple independent bootstrap
  replicates (`artifacts/.lab/L9-directed-lfp-lfp-influence-20260817.json`).

**Do not treat any L-item as a manuscript figure number** — the mapping to `fig0N_*` slots is
not yet decided, beyond the informal L2→fig05 and L7→fig06 targeting noted above.

### 7c. The SPK-primary track (S1–S17)

Companion spec at `context/analysis_spec_SPK.md`. Per `PROJECT_STATE.md` §6b (resolved
2026-08-17):

- **S1 (unit inclusion criteria rework) — the declared BLOCKER for S2/S4-S8/S10/S11 — is
  done, reviewed and approved 2026-08-17.** This replaces the old fixation-baseline-contrast
  selection (which systematically rejected units firing strongly during both fixation and
  omission — a real, confirmed bug) with a paired fire-probability test against a randomly
  drawn other-epoch null. Full corpus (22/22 sessions, 9,061 units): new criterion passes
  281/9,061 (3.1%) vs. the old template-correlation criterion's 68/9,061 (0.75%) — net +213
  units (245 gained, 32 lost, 36 unchanged-included, 8,748 unchanged-excluded). Canonical
  output: `outputs/classification/unit_inclusion_v1.csv`.
  `stable_criterion_version=presence_ks_snr_v2` — still missing the spec's `FR<100Hz-at-any-1s`
  peak-rate check (no existing primitive in this repo), disclosed, not silently dropped.
  **If a saved plan describes S1 as not-yet-started, that plan is stale — S1 already landed.**
- **S2, S4, S5, S6, S7, S8, S10, S11**: per `PROJECT_STATE.md`'s table, listed **"unblocked, not
  yet built."** **This directly conflicts with the filesystem**: `S2_population_responses_by_class/`,
  `S5_onset_latency_hierarchy_spk/`, and `S6_directionality_controls_spk/` all exist with real
  content (S2 has a rendered `S2.png`/`S2.svg`/`S2_manifest.json`/`S2_stats.json`; S5/S6 have
  their `.py` scripts). Per the 2026-08-17 discussion draft, all three were said to be "built
  2026-08-17, same day as this document." **File mtimes**: `S2.png` at 12:10, S5's script at
  14:03, S6's script at 14:08 — all **before** S1's own approval evidence node
  (`artifacts/.lab/S1-unit-inclusion-rework-in-progress-20260817.json`, mtime 14:47) on the same
  day. **This is a genuine, unresolved discrepancy** — two doctrine-adjacent sources (
  `PROJECT_STATE.md`'s table vs. the actual files) disagree about whether S2/S5/S6 exist, and
  the timestamps raise a real, unverified concern that S2 in particular may have been built
  against a pre-S1-approval population rather than the now-canonical `unit_inclusion_v1.csv`.
  **Do not assume S2/S5/S6's current output reflects S1's final criterion without checking which
  inclusion table they actually read.** This is exactly the kind of two-sources-disagree
  situation CLAUDE.md says to stop and surface, not silently resolve.
- **S3**: unblocked, not yet built — needs a stated, non-hand-picked exemplar-selection rule per
  its own acceptance criterion before it can be built.
- **S9, S12-S17**: not yet reviewed against the spec text at all.
- **L11, L12 (cross-track)**: L11 reads SPK's S1 population; L12 (spike-field coherence) is
  LFP-spec-owned per the SPK spec's own §0.7 cross-track ownership rule — import the existing
  corrected-PPC design, don't reimplement it.

---

## 8. Confirmed open bugs, not yet fixed (as of 2026-08-19)

1. **fig03's stats step crashes after the SVG is already written** — `chi2_contingency` hits a
   zero-expected-frequency cell in panel e's contingency table (legacy Q1-based `class8()`
   codepath, untouched by any of fig03's recent O++/smoothing/panel-B edits — confirmed by code
   tracing). `fig03.svg`/`.png` still write successfully; `fig03_stats.md`/`fig03_receipt.json`
   are stale relative to the figure. This is a statistics-logic judgment call (drop the offending
   cell? collapse a sparse category? report the zero and why?), not a mechanical fix — needs
   Hamm's decision.
2. **fig06's `CONDITION_MAPS` points at a dead, superseded v1 path** — confirmed live in the file
   as of this session (§5 above). Mechanical fix, low risk, but touches shared/live infra — do
   as its own small commit.

---

## 9. Standing cautions that apply to any of this work

- **Everything above except fig08's receipt and the L-track/S-track's own `PROJECT_STATE.md`
  entries is currently uncommitted.** `figstyle.py`, `figstats.py`, and `svgassemble.py` — the
  three shared modules every fig01-fig08 script and supplement imports — all carry uncommitted
  edits right now, alongside fig03's own changes, the entire L-track, and the entire S-track.
  **`git diff` the three shared modules before treating any currently-rendered number from
  fig03-fig08 as final.**
- **This repo's working tree is shared with a concurrent Cursor session** (see the
  `project_concurrent_cursor_session` memory) — check `git status`/`git diff` for unexpected
  changes before editing any shared file, especially `figstyle.py`/`figstats.py`/`svgassemble.py`.
- **No commits have been made for any of this session's fig03 work.** Committing needs an
  explicit request from Hamm, not implied by "finalized for now."
- A background audit task, `task_c779e425` ("Audit TFR/smoothing filters for acausal lookahead"),
  was spawned during this session and may still be pending — check before duplicating it.

---

## 10. Open questions a fresh session should probably raise with Hamm, not guess at

1. Which specific subplot(s) are wrong in fig05, fig06, and fig07 — outstanding since
   `REVISION_PLAN.md`'s 2026-08-09 request, never answered.
2. How should fig03's panel-e contingency crash be resolved (§8.1)?
3. Approve the fig06 `CONDITION_MAPS` v1→v2 path fix (§8.2) as its own small commit?
4. fig03 vs. fig07's O++ definition mismatch (52 vs. 15 units, §6) — reconcile or caption-note?
5. Does the fig03A-F naming convention (fig0NA.svg/.png per panel) get extended to fig01/02/04-08,
   or stay fig03-only?
6. Does `REVISION_PLAN.md`'s original 7→6→5→4→3→1→2 sequencing still hold, or does fig03 (mid-
   revision, live bug) or fig07 (redesigned, receipted headline) move up?
7. fig08: assign it a score/slot in the next `REVISION_PLAN.md` revision.
8. Which of L0-L10 and S2/S5/S6 are ready to commit as-is vs. still exploratory — all 14+ files
   are untracked simultaneously right now, which makes "what's actually locked" unanswerable
   from git status alone.
9. **The S2/S5/S6 "not yet built" vs. filesystem-exists discrepancy (§7c)** — resolve which
   source is right, and if S2 was built before S1's approval, whether it needs a rerun against
   `unit_inclusion_v1.csv`.
