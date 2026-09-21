# The eight producers with no public consumer

Hamm ruled 06-85 on 2026-09-20: **decide each of the eight separately**, because one blanket rule
would be wrong for at least one of them. Measured by the 06-85 packet against `5b6a0935`, and the
load-bearing claims re-verified independently on integration.

**P-55 is false for two of the eight.** The row asserted that none of the eight has a public
consumer. Two do.

| # | Operation | Public consumer today | Reading | Recommendation |
|---|---|---|---|---|
| 1 | `assign_outer_folds` | **Yes.** `build_inner_validation_partitions(outer_trials)` declares a parameter for its output; a raw trial table raises `KeyError: 'outer_fold'` | Consumed link | Keep. P-55 correction, not a capability decision |
| 2 | `build_inner_validation_partitions` | No | **Unfinished chain** | The only genuine one. See below |
| 3 | `fit_exponential_onset` | No | Terminal output | Keep |
| 4 | `aperiodic_fit` | No | Terminal output | Keep |
| 5 | `xflip` | No | Terminal output | Keep; the gap is documentation |
| 6 | `zflip` | No | Terminal output | Keep |
| 7 | `consensus_bad_trials` | No | Terminal output | Keep |
| 8 | `detect_band_outliers` | **Yes.** Called at `jnwb/artifact_repair.py:391`, both returns used | Consumed rule | Keep. P-55 correction |

## Why each, in a reason that does not serve for the others

1. **`assign_outer_folds`** is the only one for which another public function *declares a parameter
   for its output*. The dependency is real rather than a `DataFrame`-to-`DataFrame` coincidence.
2. **`build_inner_validation_partitions`** is the only one whose non-consumption **contradicts a
   figure the repository ships**. See below.
3. **`fit_exponential_onset`** is the only one that is the subject of both a closed and an open item
   this release — P-58 closed via 06-93, and 06-95 open. Both repairs exist *because a user reads
   `fit["t0"]` as a final answer*, so the investment is in the correctness of the terminal read.
   Recommending withdrawal would contradict work in flight.
4. **`aperiodic_fit`** is the only one carrying a citation obligation: `docs/references.md:26`
   attributes it to Donoghue et al. 2020. A citable entry point is finished when it returns the
   published parameters.
5. **`xflip`** already returns a per-channel assignment — the kind of thing `label_layers`
   *produces*, so a labelling consumer would duplicate its own output. It is also the only one of
   the eight with **zero** documented call sites, which is what makes it read as unfinished.
6. **`zflip`** produces a propagation rate and a direction, dimensionally not a position on the
   shaft, so no laminar labeller could take them whatever its signature. Unlike `xflip` it has a
   worked example reading the fields directly, which is a terminal output by this item's own test.
7. **`consensus_bad_trials`** is the only one that is itself a consumer in an otherwise complete
   chain. Its output is a boolean selection over trials, and selection is applied by array
   indexing, which is a language operation rather than one a library exports.
8. **`detect_band_outliers`** is the only one whose separate export is argued for in prose as a
   defect-prevention measure: `docs/05:146-150` says the rule has exactly one implementation,
   citing a downstream reimplementation that drifted to a two-sided test.

### The one shared reason, declared rather than hidden

Rows 5 and 6 share a receipt. `label_layers` reads `vflip_result.crossover_contact`, and neither
`XFlipResult` nor `ZFlipResult` has that field; forcing `accepted=True` on either raises
`AttributeError`. That is the `vflip` asymmetry, and it applies to both. The rows diverge only on
why nothing *else* could consume them: redundant output shape for `xflip`, inapplicable physical
quantity for `zflip`.

## The unfinished chain, and why it is worse than unfinished

`docs/09_decoding_and_visual_qc.md` contradicts itself inside one page.

- **Line 15** draws `Inner --> Train[nested_cv_linear_svm]`.
- **Lines 35-40** state the opposite in bold: "**This call does not hold out groups.**
  `nested_cv_linear_svm(X, labels, n_splits, rng)` takes no `groups` argument". Verified: the
  parameters are exactly `{X, labels, n_splits, rng}`, and the body contains no `groups`,
  `group_col`, `GroupKFold`, `LeaveOneGroupOut` or `fold_col`.
- **Line 40** then instructs the reader to "pass its partitions rather than expecting this function
  to infer them" — an action with no parameter to receive it, in the same paragraph that has just
  explained why.
- **Line 64** computes `inner_splits = jnwb.build_inner_validation_partitions(outer_folds)` and
  **the name is never used again anywhere in the repository**. The page's own worked example
  computes the partitions and drops them.

The gap is not closable in user code either: the decoder returns no fitted estimator, so a caller
cannot apply it to a held-out group themselves.

This is recorded as P-122. The documentation repair is in 0.2.6 scope, because a page that
instructs an impossible action is a defect under release condition (1) whatever the API should
eventually do. Whether `nested_cv_linear_svm` should gain a `groups` or `cv` parameter is a
capability decision and is not taken here.

## What this ruling does not do

No export is withdrawn. Withdrawing a public name is a breaking change, and for six of the eight
the measured reading is that they terminate legitimately. Two of the eight should never have been
on the list.
