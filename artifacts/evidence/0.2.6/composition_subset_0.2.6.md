# The declared high-risk composition subset for 0.2.6

Ruled by Hamm, 2026-09-20, on the proposal at `artifacts/evidence/0.2.6/composition_subset_proposal_0.2.6.md`.
**All ten chains ratified as proposed.** Eleven exclusions ratified with them.

This file is the ruled subset. It names the chains and records the ruling; the six fields per
chain — producer, consumer, risk, failure class, existing evidence, proposed discriminator — live
in the proposal and are not restated here. A second home for a chain's evidence is how the
evidence and the ruling drift apart.

## The subset

| Chain | Producer → consumer | Measured today |
|---|---|---|
| H1 | `vflip_from_lfp` / `vflip` → `label_layers` | **Live defect.** 18 of 24 contacts receive a different layer, `accepted=True`, no warning. **Second leg struck 2026-09-20:** the proposal described `bad_channel_mask` as crossing the two index spaces; 06-20 measured that it does not — `vflip` stores `effective_bad_input` *before* the shaft reorder, so both ends read the mask in table-row space. Pinned as a passing regression guard instead |
| H2 | `bandpass_filter` → `current_source_density_1d`, `voltage_curvature_1d` | **Live defect.** RMS ratio **0.108993**, 9.17× — re-stamped from the committed generator, the proposal's 0.104 being unrecoverable (P-118). The second derivative is taken along time. The 1/f spectrum is load-bearing: on white noise the ratio is 1.86 and the defect looks mild. P-115 |
| H3 | trials-by-time array, `as_trials` → `granger`, `granger_spectral`, `transfer_entropy`, `phase_slope_index` | **Live defect in three of four.** 1.90 against 1.1e-07…3.7e-04 — 5,147× to 17,716,885× over six seeds, bracketing the proposal's unrecoverable 6141×. `transfer_entropy` also returns a negative value, which is impossible by construction. **`phase_slope_index` refuses and is correct today.** P-116 |
| H4 | `channel_correlation_matrix` → `bad_channels_from_correlation` | **Live defect**, reproduced exactly. A 6000-entry verdict flagging 0 "channels"; the QC gate tests nothing. P-117 |
| H5 | `band_power` → `aggregate_to_db` | **Live defect**, confirmed in class; magnitude re-stamped to **2.992632 dB** from the committed generator, the proposal's 0.912209 being unrecoverable (P-118). `band_power` returns a float, so `aggregate_over=0` raises `AxisError` — reproduced verbatim |
| H6 | `complex_tfr` → `TFRAccumulator` → `aggregate_to_db`, `to_db` | **Live defect**, now pinned as an exact identity: `max\|accumulator − ratio_of_means\| = 3.55e-15` over 980 cells, so `how="mean_of_ratios"` is accepted and provably cannot be delivered. Separation 1.43 dB minimum, 6.38 dB median, re-stamped (P-118). P-114 |
| H7 | `epoch_continuous(boundary_policy="nan")` → six spectral and rate consumers | **Live defect in one leg.** Five of six refuse, but only three share one message, so a discriminator matching the quoted sentence across all five fails on two; `gaussian_smooth_rate` accepts and widens silently — **1 bin into 9 as composed**, at an epoch edge, and into 17 only for an interior NaN. Corrected from the proposal by the 06-22 measurement |
| H8 | `map_peak_channel_to_area`, `classify_layer_from_depth` → `enrich_units_dataframe` | **Correct today.** Regression guard: no test permutes either frame's row order, so a positional join would pass every existing assertion |
| H9a | `build_permutation_plan` → `permute_labels` | **Correct today.** Regression guard: the existing test compares a plan against a plan, so it passes on any self-consistent digest including a wrong one |
| H9b | caller `rng` / `seed` → `cluster_permutation_test`, `directed_network` | **Correct today.** Regression guard: nothing asserts that two *different* seeds differ, which is the half a reseeding child would survive |

## Why the four correct-today chains are in the subset

They were ratified deliberately rather than dropped as passing. Each is correct today and is
protected by no test that could fail — H8's fixture passes identically under a positional join,
H9a's test compares the builder against itself, H9b pins same-seed reproducibility and never
different-seed difference. **A chain nothing could falsify is exactly the state "unknown is not a
pass" exists to forbid**, and dropping them would have declared a subset that certifies its own
blind spots.

## What this file binds

- Each of 06-19 through 06-23 and 06-27 cites chains from this file and **adds none of its own**.
  The coverage map is in the proposal's "Coverage against the blocked items".
- Within the declared subset, **unknown is not a pass**.
- The boundary is part of the acceptance record. The eleven exclusions, and the stop conditions
  proposed and then withdrawn for want of a public consumer, are in the proposal's own sections
  and are ratified as written.
- 06-18's stop condition fired correctly during the proposal and was honoured: chains whose
  producer has no public consumer were **not** proposed. Those eight producers are 06-85's
  question, ruled separately.

## What would falsify this subset

The proposal's "Method, and what would falsify this" section states it, and the ruling adopts it
unchanged: a chain whose measured magnitude does not reproduce, or a consumer that turns out not
to be reachable from the public API, removes that chain rather than weakening its discriminator.

## Amendments after measurement, 2026-09-20

The subset's falsification clause was exercised rather than waived. Five lanes re-measured the ten
chains against committed generators, and three cells did not survive: H1's second leg does not
cross index spaces, H3's `phase_slope_index` refuses and is correct, and H7's composed widening is
9 rather than 17. Each is corrected above rather than softened.

The magnitudes themselves are a separate finding. The proposal's receipts were git-ignored and
never committed (P-118), so its digits cannot be re-derived; every chain's *substance* reproduces,
so the clause's remedy is a re-stamp from the committed test generators, not removal. Where a cell
now carries a number, that number comes from a generator whose literals are in `tests/`.
