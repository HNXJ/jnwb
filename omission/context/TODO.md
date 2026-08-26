# Pinned TODO — omission (F04 seal + open items)

Live checklist. Mark items done in place (do not delete history) when resolved; append new
items under the relevant section as they arise. Established 2026-08-26 per Hamm's standing
instruction: maintain this on every turn going forward.

## In progress — F04 statistical seal (Hamm's bounded task, 2026-08-26)

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
      earlier-cited "7/139" could not be reproduced under either threshold. Root cause remains
      UNRESOLVED — recommend citing 3/139 (raw) / 0/139 (FDR) until traced.
- [x] Built the one summary table Hamm specified (embedded in the receipt's `summary_table`
      field): rows {Decoding, RSA, Linear latent, Nonlinear latent} × columns {Y_stim,
      Y_position, Y_context, Y_expected}, actual estimates/statuses, no +/- symbols.
- [x] Confirmed no other currently-live Fig04-relevant artifact cites the three stale headline
      numbers (bal_acc=0.7244, AUC=0.8098, RSA Position beta=0.5772) as *current* — see receipt's
      `stale_value_verification`. One new finding: `omission/outputs/classification/fig04_rsa_regression_receipt.json`
      is correctly labeled `STATUS: INVALID_TIMING_DO_NOT_USE` but was never regenerated after
      the timing fix, so it is internally self-inconsistent with its own corrected underlying CSV
      (`fig04_rsa_model_regression.csv`). Not a live-citation risk (already marked invalid) but
      worth cleaning up — added below.
- [x] Hamm's ruling 2026-08-26: do NOT repair `fig04_rsa_regression_receipt.json` — it is
      quarantined, not authoritative, and repairing it for cosmetic consistency is not worth
      analysis time. The corrected CSV + `fig04-statistical-receipt-20260826.json` supersede it.
      Removed from this list as an action item; the stale receipt stays as immutable historical
      evidence of what was previously believed.
- [x] Reclassified the Y_omit historical "7/139" from `UNRESOLVED` to `HISTORICAL_UNREPRODUCED`
      in the receipt per Hamm's ruling — provenance preserved, but it no longer competes with
      the recomputed current evidence (3/139 raw p<.05, 0/139 BH q<.05), which is authoritative
      and now the manuscript-relevant statement for Y_expected.

## In progress — final scientific gate before Fig04 regeneration (Hamm's instruction, 2026-08-26)

Hamm downgraded `Y_context` from CONFIRMED to **PROVISIONAL**: the context decoder
(`compute_predictable_vs_random_omission_decoding.py`) used ungrouped `StratifiedKFold`, the
same class of leakage risk the Fig04 timing investigation surfaced elsewhere. This is now the
one remaining gate before Fig04 regeneration — no other estimand is in question.

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

All four estimands are now settled and adversarially checked:
$$Y_{\rm stim}:\text{SUPPORTED} \quad Y_{\rm position}:\text{SUPPORTED (grouping-verified)} \quad Y_{\rm context}:\text{NULL} \quad Y_{\rm expected}:\text{NULL}$$

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
      flagged explicitly per doctrine rather than presented as equally evidenced.

## Next: Fig04 regeneration (not yet started, awaiting Hamm's go-ahead)

Per Hamm's instruction: regenerate Fig04 exactly once from `fig04-statistical-receipt-20260826.json`,
then seal. No new models, targets, manifold searches, or exploratory analyses. The revised
headline to build the figure around:

> During omission, population spiking carries physical-identity and sequence-position
> information, but not detectably the predictability context of the omission or the expected
> omitted stimulus identity.

This is a materially different (weaker on Y_context) conclusion than the pre-gate 97/100
assessment assumed — flag this to Hamm explicitly before proceeding, since it changes the
manuscript's headline claim from "context vs content dissociation" to "identity/position vs
everything-else-during-omission dissociation."

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
- [ ] **Awaiting Hamm's review/acceptance of the corrected spec before any execution.**
- [ ] Once accepted, first concrete step (per the spec): enumerate real per-session probe->area
      coverage across all 22 sessions via each `metadata/{session}/probe_areas.json` sidecar
      (cheap JSON reads, no NWB/TFR loading) to determine actual SPK<->LFP session/area overlap
      before running anything.

## New — SPK companion task: Y_omission (occurrence), required before Fig04's final seal

Per Hamm, 2026-08-26: `Y_omission` (omission occurred O vs stimulus-present S, position-matched
per-position AND a position-balanced pooled cell so position cannot trivially solve occurrence)
is "the most important missing SPK cell." Must be run on SPK, using the identical
corrected/cycle-grouped operator already validated for the other four SPK targets, before Fig04
is declared fully sealed.

- [ ] Not started. Target pattern if it holds: `Y_omission > 0, Y_context ~ 0, Y_expected ~ 0`,
      giving: "SPK signals that an omission occurred, but not detectably why it occurred or what
      absent stimulus was expected." This would become the fifth cell/column addition to
      `fig04-statistical-receipt-20260826.json` before Fig04 regeneration.
- [ ] This is now a second gate ahead of Fig04 regeneration, alongside the LFP spec review —
      order between them not yet specified by Hamm; ask before starting either implementation.

## Explicitly forbidden for this seal (Hamm's instruction, 2026-08-26)

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

## Open, longer-horizon (not blocking F04 seal)

- [ ] `git push origin dev` has never succeeded — one attempt was blocked by the Claude Code
      auto-mode classifier; local commit `5f43a27` remains unpushed. Needs explicit retry/consent.
- [ ] Cycle-grouping / permutation-exchangeability audit: `detect_trial_cycles` is a
      temporal-gap block detector, not one-trial-per-cycle — plain `StratifiedKFold` (ungrouped)
      in the Antigravity context/RSA scripts is a potential unaudited leakage/exchangeability
      risk, structurally similar to a previously-fixed bug in
      `decode_identity_cycle_deconfound` (fixed 2026-08-10 per `omission-statistics` skill).
      Not yet investigated. Distinct from the timing bug.
- [ ] Solo (uncontended) rerun of `compute_multimodal_manifold_battery.py` — deprioritized,
      not required for F04; do only after F04 is sealed and only alone (do not run concurrently
      with other heavy NWB/UMAP scripts — see resource-contention lesson below).
- [ ] Carryover-safe / matched content decoder (`compute_context_vs_content_matched_contrast.py`)
      — outputs currently marked `INVALID_TIMING_DO_NOT_USE`. Hamm indicated this may not even
      be necessary for F04; revisit only if a future figure specifically needs `D_c`.
- [ ] F06 Stage B candidate atlas (see `omission/context/handoff/2026-08-24-f06-stage-a-complete/HANDOFF.md`).
- [ ] F07 substrate + atlas.
- [ ] Full `omission/tests/` suite rerun (only `test_sequence_timing_geometry.py` and
      `test_no_retracted_census_in_live_code.py` have been targeted-run this session).

## Operational lessons (keep in mind, not action items)

- Do not run multiple heavy NWB-reading / UMAP-fitting scripts concurrently on this machine —
  confirmed severe resource contention (3.5h wall-clock for ~35-39min actual CPU time) when 3
  manifold scripts ran at once. Prefer sequential execution.
