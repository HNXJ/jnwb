# ACTIVE GOAL — omission

## Current manuscript objective

Complete Figures 04–07 under one matched encoding/statistical grammar.

Scientific progression:

F04 — what population SPK encodes
F05 — what LFP encodes and how omission modulates field state
F06 — how matched SPK and LFP responses correspond/dissociate
F07 — what SPK+LFP predicts beyond either modality alone

Do not reopen repository normalization or unrelated analysis.

---

# Execution order

## GATE 1 — Complete SPK encoding / Fig04

Current verified SPK hierarchy:

- Y_stim: SUPPORTED
- Y_position: SUPPORTED, cycle-group verified
- Y_context: NO DETECTABLE INFORMATION under grouped held-out decoding
- Y_expected: NO DETECTABLE INFORMATION under grouped held-out decoding
- Y_omission: SUPPORTED (2026-08-27) — see below

### Y_omission — DONE (2026-08-27)

Result: SUPPORTED. O vs S (position-matched) decodable from population spiking at p2, p3, p4,
and a position-balanced pooled analysis; 59-71% FDR-significant cell prevalence, mean balanced
accuracy 0.66-0.71 (chance 0.50), consistent across all 3 subjects, no POSITION_SPECIFIC
restriction. Area gradient (early visual strongest, PFC weakest/marginal) is consistent with a
sensory-evoked-response confound Hamm flagged in advance — result establishes population
decodability of O-vs-S, not prediction-error encoding specifically. Full 21-field receipt block:
`omission/artifacts/.lab/fig04-statistical-receipt-20260826.json` → `Y_omission`.
Script: `omission/scripts/compute_fig04_omission_occurrence.py`.
Outputs: `omission/outputs/classification/fig04_omission_occurrence_{cells,nuisance,receipt}.{csv,json}`.

Caveat carried forward (not disqualifying, see receipt for full text): cycle-grouped LOCO fold
count is coarser than the other four SPK targets in ~20% of cells (2-4 folds vs typical 10-25),
because `assign_temporal_cycles` found few large temporal gaps in some sessions' combined O+S
trial stream. Permutation null uses the identical fold structure as the observed statistic in
every cell, so p-values remain valid conditional on that structure.

**Performance incident during this run** (see receipt's `Y_omission.performance_note` for full
detail): the first two attempts stalled — one >5h on a single session without completing serial
999-permutation refits on a 508-unit feature matrix on one core (24 idle); fixed by
parallelizing the independent per-permutation refits across cores (joblib/loky) in
`decode_omission_direct` — identical statistics/operator/seeds, wall-clock only. Verified against
the exact stalled case before relaunch. Total real runtime once fixed: ~6h55m across all 22
sessions (dominated by a handful of cycle-rich, unit-rich sessions — 999 permutations × up to ~25
folds × up to ~2,052 trials in the pooled cell is genuinely expensive even parallelized). This
performance fix is local to this one script; the serial-loop pattern was not audited elsewhere.

### Gate-1 stopping condition

Fig04 can seal when:

1. Y_omission has a terminal result; — ✅ DONE 2026-08-27
2. authoritative Fig04 statistical receipt contains all five targets; — ✅ DONE 2026-08-27
3. all displayed values derive from corrected canonical timing; — ✅ (Y_omission used canonical EPOCH_ONSETS_MS only)
4. no ungrouped-CV result is current; — ✅ (Y_omission used cycle-grouped LOCO throughout)
5. no invalid/superseded result appears in the figure;
6. Fig04 is regenerated once and visually/statistically audited. — NOT DONE. Per Hamm's explicit
   instruction ("Do not regenerate Fig04. Do not start LFP.") this step is deliberately deferred,
   not forgotten. Next actionable step for Gate 1 closure is Fig04 regeneration, pending Hamm's
   go-ahead.

No new Fig04 targets or model families after this gate.

---

## GATE 2 — LFP-only matched encoding battery

Status: SPEC WRITTEN, NOT EXECUTED.

First review/accept:
context/LFP_ENCODING_BATTERY_SPEC.md

Then enumerate real session/probe/area coverage from:
E:/analysis/tfr_arrays/metadata/

Do not trust stale corpus-manifest TFR counts.

Apply the same five targets:

- Y_stim
- Y_position
- Y_omission
- Y_context
- Y_expected

Use modality-appropriate LFP tensors, but the same downstream statistical grammar as SPK.

Required comparison:

target × SPK × LFP

Do not use pooled F05 products as substitutes for trial-level encoding.

---

## GATE 3 — SPK + LFP encoding

Only after SPK and LFP are independently sealed.

Use identical matched trials, targets, groups, and outer folds.

Compare:

P_S
P_L
P_SL

and:

Delta_L = P_SL - P_S
Delta_S = P_SL - P_L

Use session-aware paired inference.

Call these incremental held-out predictive gains, not synergy or mutual information.

Existing multimodal AUC=0.867 is UNAUDITED and must not be cited.

---

## GATE 4 — Figures 05–07 synthesis

F05:
LFP temporal/spectral response + LFP encoding results.

F06:
matched SPK-LFP response correspondence/dissociation.
Preserve the validated Stage-A substrate and complete Stage B only after LFP encoding is known.

F07:
SPK vs LFP vs SPK+LFP predictive complementarity using the matched encoding grammar.

Generate broad candidate-panel atlases first; final panel selection comes afterward.

---

# Universal analysis invariants

decodability != representation

significant(A) + nonsignificant(B) != significant(A-B)

association != directionality != causality

prevalence != magnitude != information != mechanism

All event timing comes from canonical sequence_layout.EPOCH_ONSETS_MS.

All CV must respect cycle/session dependence appropriate to the estimand.

All representation learning is fold-local.

Hyperparameter selection is nested inside outer training data.

Permutation p-values use:

p = (1+k)/(B+1)

Never report p=0 from finite permutations.

Declare multiplicity families before interpreting results.

Null, contradicted, and non-identifiable outcomes are valid terminal results.

---

# Known false-encoding hazards — actively defend against

OBSERVED:
1. wrong temporal addressing
2. sensory carryover / window contamination
3. cycle leakage from ungrouped CV
4. finite-permutation p-value floor

PROSPECTIVE / GENERAL:
5. task-position/state confounding
6. representation-selection optimism

Before accepting any positive encoding result, explicitly check these six classes.

---

# Compute rule

Run heavy NWB/TFR/UMAP jobs sequentially.

Do not run multiple heavy analyses concurrently on this machine.

---

# STOP RULE

Do not start the next gate until the current gate has:

- deterministic outputs
- statistical receipt
- provenance
- tests/checks
- terminal scientific verdict

When a new issue is discovered:

if it can invalidate the current estimand:
    stop and resolve it
else:
    log it and continue

Completed/superseded history remains below this ACTIVE GOAL block and does not control execution.

---
---

# HISTORY / EVIDENCE TRAIL (append-only; does not control execution)

Everything below this line is a chronological record, kept for provenance per Conservation
(`labyrinth` skill: reduce/supersede, never delete). The ACTIVE GOAL block above is the only
section that determines what to do next. Do not infer priority from ordering below.

## DEBT / LATER (explicitly not on the active critical path)

- [x] ~~`git push origin dev` has never succeeded~~ — **RESOLVED 2026-08-26**: commits `5f43a27`
      and `5e2d177` pushed successfully (`origin/dev` at `5e2d177`). Superseded the stale
      "never succeeded" note below.
- [x] ~~Cycle-grouping / permutation-exchangeability audit: not yet investigated~~ —
      **RESOLVED/SUPERSEDED 2026-08-26**: this was investigated. The context decoder
      (`compute_predictable_vs_random_omission_decoding.py`) was converted from ungrouped
      `StratifiedKFold` to cycle-grouped leave-one-cycle-out CV and rerun; the result collapsed
      (4/12 → 0/11 BH-FDR-significant cells). See "Closed — adversarial Y_position grouping
      check" and "final scientific gate" sections below for the full record. The stale
      "not yet investigated" wording that used to live here was the exact contradiction Hamm
      flagged on 2026-08-26 — corrected in this pass.
- [ ] Solo (uncontended) rerun of `compute_multimodal_manifold_battery.py` — deprioritized;
      do only after Gate 3, and only alone (see Compute rule above).
- [ ] Carryover-safe / matched content decoder (`compute_context_vs_content_matched_contrast.py`)
      — outputs currently marked `INVALID_TIMING_DO_NOT_USE`. Hamm indicated this may not even
      be necessary for Fig04; revisit only if a future figure specifically needs `D_c`.
- [ ] F06 Stage B candidate atlas (see `omission/context/handoff/2026-08-24-f06-stage-a-complete/HANDOFF.md`)
      — folded into Gate 4 above; tracked here as the concrete pointer.
- [ ] F07 substrate + atlas — folded into Gate 4 above; tracked here as the concrete pointer.
- [ ] Full `omission/tests/` suite rerun (only `test_sequence_timing_geometry.py` and
      `test_no_retracted_census_in_live_code.py` have been targeted-run this session).

## Superseded — "Next: Fig04 regeneration" (2026-08-26, superseded same day)

This section used to say Fig04 regeneration was the immediate next step once `Y_context` closed.
**Superseded 2026-08-26**: Hamm identified `Y_omission` as a required fifth SPK target before
Fig04's final seal — that is now Gate 1's current task (see ACTIVE GOAL above), not figure
regeneration. Kept here for provenance, not as a live instruction:

> Per Hamm's instruction: regenerate Fig04 exactly once from `fig04-statistical-receipt-20260826.json`,
> then seal. No new models, targets, manifold searches, or exploratory analyses. The revised
> headline to build the figure around: "During omission, population spiking carries
> physical-identity and sequence-position information, but not detectably the predictability
> context of the omission or the expected omitted stimulus identity."

## New — SPK companion task: Y_omission (occurrence) — this is Gate 1's current task

Per Hamm, 2026-08-26: `Y_omission` (omission occurred O vs stimulus-present S, position-matched
per-position AND a position-balanced pooled cell so position cannot trivially solve occurrence)
is "the most important missing SPK cell." Must be run on SPK, using the identical
corrected/cycle-grouped operator already validated for the other four SPK targets, before Fig04
is declared fully sealed. Full requirements now live in the ACTIVE GOAL block's Gate 1 section.

- [ ] Not started. Target pattern if it holds: `Y_omission > 0, Y_context ~ 0, Y_expected ~ 0`,
      giving: "SPK signals that an omission occurred, but not detectably why it occurred or what
      absent stimulus was expected." This would become the fifth cell/column addition to
      `fig04-statistical-receipt-20260826.json` before Fig04 regeneration.

## Explicitly forbidden for the Fig04 seal (Hamm's instruction, 2026-08-26)

- Do NOT rerun `compute_multimodal_manifold_battery.py` as part of Fig04 — its fixed-timing
  rerun was killed for resource contention; AUC=0.867 stays unaudited/uncited until a completed
  rerun exists.
- Do NOT spend further compute rescuing the n=1 nested phase diagram
  (`compute_fig04_nested_manifold_surface.py`'s Sequence_Position / Omission_Identity_p2 cells).
  Classified `DIAGNOSTIC_ONLY`, permanently, absent new population coverage.
- Do NOT force the matched context-vs-content contrast (`D_c`) back into scope — Hamm: "I would
  not require the direct matched D_c contrast for Fig04 to be valid."

## Durable, done, keep permanently

- [x] `omission/tests/test_sequence_timing_geometry.py` — permanent regression guard against the
      2026-08-25 timing defect (wrong 531ms-spaced `SLOT_ONSETS_MS` literals) and against any
      future local duplication of sequence timing outside `sequence_layout.EPOCH_ONSETS_MS`.
      6/6 passing as of last run. Keep permanently per Hamm's explicit instruction.
- [x] Timing-bug fix applied and reran clean across all 5 affected live scripts:
      `compute_predictable_vs_random_omission_decoding.py`,
      `compute_sequence_rsa_and_multimodal_fusion.py`,
      `compute_fig04_manifold_search.py`, `compute_fig04_nested_manifold_surface.py`,
      `compute_multimodal_manifold_battery.py` (fix applied; full rerun killed, see forbidden
      list above — the *fix* is done, the *rerun* is not).
- [x] Permutation-count / p=0-floor defect fixed in the two Antigravity decoders (999 perms,
      `(1+k)/(N_PERM+1)` finite-sample correction) — independently confirmed by Hamm's own math.

## Done — LFP encoding battery specification (scoping only, per Hamm's instruction, 2026-08-26)

- [x] Written: [`omission/context/LFP_ENCODING_BATTERY_SPEC.md`](LFP_ENCODING_BATTERY_SPEC.md)
      (full 10-item spec) + pointer node
      `omission/artifacts/.lab/lfp-encoding-battery-spec-20260826.json`. **NOT EXECUTED** — status
      `unconfirmed`, awaiting Hamm's review per his explicit "do not run the battery yet."
- [x] **CORRECTED 2026-08-26**: initial audit checked only `D:/analysis` and wrongly concluded
      the precomputed TFR cache doesn't exist. Hamm supplied the real path
      (`E:/analysis/tfr_arrays`); re-verified directly against the filesystem: 970 files, 735 GB,
      complete across all 22 sessions, plus a full `metadata/` sidecar set. `channel_area_vector.csv`
      also exists (`omission/outputs/connectivity/channel_area_vector/channel_area_vector.csv`,
      8,993 rows). `corpus_manifest.json`'s `n_sidecar_ok`/`n_tfr_ok`/`n_tfr_files_on_disk` fields
      (all 0) are themselves stale relative to `E:/analysis` — flagged in the spec, do not trust
      that manifest for this question without re-checking the filesystem. Spec §1/§2/§8 rewritten:
      the precomputed cache is now the primary tensor source, and the cost estimate dropped
      materially (the expensive extraction/spectrogram step is already done).
- [ ] **Awaiting Hamm's review/acceptance of the corrected spec before any execution.** This is
      Gate 2 in the ACTIVE GOAL block above.

## Done — false-encoding taxonomy preserved as durable methodological evidence (2026-08-26)

- [x] Built `omission/artifacts/.lab/fig04-false-encoding-taxonomy-20260826.json` per Hamm's
      instruction to log this as an explicit methodological result, not hide it as debugging.
      Contains: the 6-row failure-mode table (wrong temporal addressing, temporal
      carryover/adaptation, cycle leakage, permutation-floor error, position/task-state
      confounding, representation-selection risk), the central `decodability != representation`
      claim, the 8-step defense hierarchy, a draft Methods/Discussion paragraph, and the scoped
      (not-yet-started) LFP next-task spec. Each row carries an `evidence_status` field —
      rows 1-4 are DIRECTLY OBSERVED this session with receipts; rows 5-6 (position/task-state
      confounding, representation-selection risk) are recorded as Hamm's methodological framing
      / prospective risks, NOT independently caught-and-fixed bugs in this session's own record —
      flagged explicitly per doctrine rather than presented as equally evidenced. This is now
      folded into the ACTIVE GOAL block's "Known false-encoding hazards" section above.

## Closed — adversarial Y_position grouping check (Hamm's instruction, 2026-08-26)

- [x] Verified `Y_position`'s decoding CV (`compute_fig04_encoding_matrix.py`'s Y_pos cell) by
      reading the source directly (not recalled): `_cross_slot_table()` builds
      `cross_cycle_id = detect_trial_cycles(main[["start_time"]])` on the combined p2/p3/p4
      table, and `decode_multiclass_balanced_cycle_safe()` runs true leave-one-cycle-out folds
      with a within-cycle-permutation null — the same canonical `jnwb.statistics.detect_trial_cycles`
      grouping (re-exported, not duplicated, via `omission/jnwb_ext/omission_identity.py:31`) just
      used to fix `Y_context`. **VERIFIED EQUIVALENT — no rerun needed.** `Y_position` was never
      exposed to the ungrouped-CV shortcut; its CONFIRMED status stands as-is.
- [x] Recorded the full verification (file:line citations) in the receipt's
      `Y_position.Decoding.adversarial_grouping_verification` field.
- [x] Added a `manuscript_language_note` to the receipt per Hamm's terminology correction:
      internal `CONFIRMED_NULL` labels are fine as terminal analysis states, but manuscript prose
      for `Y_context`/`Y_expected` should read "no detectable [...] information under
      cycle-grouped held-out decoding," not a stronger zero-effect claim.

All four estimands settled and adversarially checked as of 2026-08-26 (before `Y_omission` was
added as a fifth target):
$$Y_{\rm stim}:\text{SUPPORTED} \quad Y_{\rm position}:\text{SUPPORTED (grouping-verified)} \quad Y_{\rm context}:\text{NULL} \quad Y_{\rm expected}:\text{NULL}$$

## In progress (historical) — final scientific gate before Fig04 regeneration (Hamm's instruction, 2026-08-26)

Hamm downgraded `Y_context` from CONFIRMED to **PROVISIONAL**: the context decoder
(`compute_predictable_vs_random_omission_decoding.py`) used ungrouped `StratifiedKFold`, the
same class of leakage risk the Fig04 timing investigation surfaced elsewhere.

- [x] Replaced `StratifiedKFold` with cycle-grouped leave-one-cycle-out CV in
      `compute_predictable_vs_random_omission_decoding.py`, using the canonical
      `jnwb.statistics.detect_trial_cycles` (the same grouping semantics already validated in
      `compute_fig04_encoding_matrix.py`/`compute_omission_identity_leakage_safe.py`). Everything
      else held fixed per Hamm's spec: same trials, same features (`extract_spk_features`
      unchanged), same target, same metric (`evaluate_cv` unchanged), same permutation scheme
      (999 perms, global label permutation, `(1+k)/(N_PERM+1)` correction, unchanged). Added a
      `cycle_grouped_splits` helper; skip a cell if fewer than 2 valid grouped folds remain.
      `omission/tests/test_sequence_timing_geometry.py` re-run clean (6/6) after the edit —
      timing imports untouched.
- [x] Archived the prior (timing-corrected but ungrouped-CV) outputs to
      `omission/outputs/classification/superseded_20260826_ungrouped_cv/` before rerunning, so
      `P_ungrouped` vs `P_grouped` can be compared explicitly, per Hamm's instruction.
- [x] Rerun complete. **Result: the effect COLLAPSED.** Grouped-CV accuracy falls to at-or-below
      chance in every cell (mean 0.4247 vs ungrouped mean 0.5847, chance=0.5); 0/11 cells
      significant at raw p<0.05 or BH q<0.05 (vs 5/12 raw-sig, 4/12 FDR-sig ungrouped). Every
      previously-significant cell (ALL_SLOTS-ALL, ALL_SLOTS-MT, p2-ALL, p4-ALL) drops to
      non-significance. The PCA->UMAP representation shows the same collapse (mean 0.4215).
      Ungrouped results archived at `omission/outputs/classification/superseded_20260826_ungrouped_cv/`
      for the record.
- [x] Built the explicit `P_ungrouped` vs `P_grouped` comparison — embedded in the receipt's
      `Y_context.Decoding.grouped_vs_ungrouped_comparison` field.
- [x] Updated `fig04-statistical-receipt-20260826.json`'s `Y_context` block: **downgraded to
      `CONFIRMED_NULL`** (not merely reverted to provisional — the grouped-CV evidence actively
      argues against the effect, not just fails to confirm it). This matches Hamm's "if it
      collapses, we caught another structural shortcut before publication" framing.
- [x] Updated `summary_table` and `headline` in the receipt to match: only Y_stim and
      Y_position remain positive findings; Y_context and Y_expected are both CONFIRMED_NULL.
      Top-level receipt `status` promoted to `confirmed` (all four estimands now settled).

## In progress (historical) — F04 statistical seal (Hamm's bounded task, 2026-08-26)

- [x] Supersede the two stale Antigravity `.lab` nodes (`f04-predictable-vs-random-context-receipt-20260824.json`,
      `f04-f07-rsa-multimodal-fusion-receipt-20260824.json`) via the `labyrinth` quarantine pattern —
      `status: superseded`, `scientific_status: invalid_for_inference`, `superseded_by`, `reason[]`,
      original values preserved verbatim. Done 2026-08-26.
- [x] Create this pinned todo list. Done 2026-08-26.
- [x] Construct authoritative `FIG04_STATISTICAL_RECEIPT`
      (`omission/artifacts/.lab/fig04-statistical-receipt-20260826.json`, 21-field-per-estimand
      schema verbatim from Hamm's spec, Y_stim / Y_position / Y_context / Y_expected ×
      Decoding/RSA/Linear-latent/Nonlinear-latent), corrected-timing evidence only, recomputed
      independently from the live CSVs this session (not copied from memory). n=1 nested phase
      diagram cells explicitly excluded and classified `DIAGNOSTIC_ONLY`. Done 2026-08-26.
- [x] Explicitly flagged (not silently picked) the Y_omit / Y_expected significant-cell-count
      discrepancy in the receipt's `known_discrepancy` field: current live
      `fig04_encoding_matrix_cells.csv` gives 3/139 (raw p<0.05) / 0/139 (BH-FDR q<0.05); an
      earlier-cited "7/139" could not be reproduced under either threshold. Reclassified
      `HISTORICAL_UNREPRODUCED` per Hamm's ruling — see below.
- [x] Built the one summary table Hamm specified (embedded in the receipt's `summary_table`
      field): rows {Decoding, RSA, Linear latent, Nonlinear latent} × columns {Y_stim,
      Y_position, Y_context, Y_expected}, actual estimates/statuses, no +/- symbols.
- [x] Confirmed no other currently-live Fig04-relevant artifact cites the three stale headline
      numbers (bal_acc=0.7244, AUC=0.8098, RSA Position beta=0.5772) as *current* — see receipt's
      `stale_value_verification`. One finding: `omission/outputs/classification/fig04_rsa_regression_receipt.json`
      is correctly labeled `STATUS: INVALID_TIMING_DO_NOT_USE` but was never regenerated after
      the timing fix, so it is internally self-inconsistent with its own corrected underlying CSV
      (`fig04_rsa_model_regression.csv`). Not a live-citation risk (already marked invalid).
      Per Hamm's ruling, NOT being repaired — quarantined, not authoritative, not worth analysis
      time; stays as immutable historical evidence of what was previously believed.
- [x] Reclassified the Y_omit historical "7/139" from `UNRESOLVED` to `HISTORICAL_UNREPRODUCED`
      in the receipt per Hamm's ruling — provenance preserved, but it no longer competes with
      the recomputed current evidence (3/139 raw p<.05, 0/139 BH q<.05), which is authoritative
      and now the manuscript-relevant statement for Y_expected.

## Operational lessons (folded into "Compute rule" above; kept here for provenance)

- Do not run multiple heavy NWB-reading / UMAP-fitting scripts concurrently on this machine —
  confirmed severe resource contention (3.5h wall-clock for ~35-39min actual CPU time) when 3
  manifold scripts ran at once. Prefer sequential execution.

## Git / push record

- [x] 2026-08-26: `git push origin dev` succeeded. Two commits pushed: `5f43a27` ("repo harness
      reorg + F06 matched SPK-LFP substrate v1") and `5e2d177` ("Fig04 statistical seal
      (cycle-grouped context CV) + LFP battery spec"). `origin/dev` confirmed at `5e2d177`.
      Excluded from the second commit, per `omission/CLAUDE.md`'s standing protected-paths
      doctrine: everything under `omission/scripts/*` and `omission/context/figures/*`, plus
      `omission-data/SKILL.md` — including several SPK script edits made this session (the
      `Y_context` CV fix, the timing fixes). Those remain uncommitted in the working tree.
