# The declared high-risk composition subset for 0.2.6

Ruled by Hamm, 2026-09-20, on the proposal at `artifacts/composition_subset_proposal_0.2.6.md`.
**All ten chains ratified as proposed.** Eleven exclusions ratified with them.

This file is the ruled subset. It names the chains and records the ruling; the six fields per
chain — producer, consumer, risk, failure class, existing evidence, proposed discriminator — live
in the proposal and are not restated here. A second home for a chain's evidence is how the
evidence and the ruling drift apart.

## The subset

| Chain | Producer → consumer | Measured today |
|---|---|---|
| H1 | `vflip_from_lfp` / `vflip` → `label_layers` | **Live defect.** 18 of 24 contacts receive a different layer, `accepted=True`, no warning |
| H2 | `bandpass_filter` → `current_source_density_1d`, `voltage_curvature_1d` | **Live defect.** RMS ratio 0.104; the second derivative is taken along time |
| H3 | trials-by-time array, `as_trials` → `granger`, `granger_spectral`, `transfer_entropy`, `phase_slope_index` | **Live defect.** 1.848782 against 0.000301 — a 6141× understatement that reads as "no coupling" |
| H4 | `channel_correlation_matrix` → `bad_channels_from_correlation` | **Live defect.** A 6000-entry verdict flagging 0 "channels"; the QC gate tests nothing |
| H5 | `band_power` → `aggregate_to_db` | **Live defect.** 0.912209 dB between log-last and mean-of-decibels |
| H6 | `complex_tfr` → `TFRAccumulator` → `aggregate_to_db`, `to_db` | **Live defect.** 5.221199 dB; `how="mean_of_ratios"` is accepted and cannot be delivered |
| H7 | `epoch_continuous(boundary_policy="nan")` → six spectral and rate consumers | **Live defect in one leg.** Five of six refuse; `gaussian_smooth_rate` widens one NaN bin into 17, silently |
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
