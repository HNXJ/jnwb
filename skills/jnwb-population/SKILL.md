---
name: jnwb-population
description: Population decoding, nested CV linear SVM, neural trajectories, joint
  representational similarity analysis (jRSA), and subspace geometry.
---

# `jnwb-population` — Population Decoding, Trajectories & jRSA

## 1. Trigger
Activate this skill when training population decoders (linear SVM), computing cross-validated representational geometry, population state-space trajectories, or Joint RSA (jRSA).

## 2. Task-to-Operation Routing Matrix
- `jnwb.nested_cv_linear_svm(X, labels, n_splits, rng=42)`: Nested cross-validated linear SVM decoding with inner regularization tuning. `n_splits` has no default. The outer folds are stratified over rows and it takes no `groups` and no fold column, so it cannot hold out whole blocks or cycles: for that, build the partitions with `assign_outer_folds` and `build_inner_validation_partitions` and fit each fold yourself. The result carries `accuracy`, `fold_accuracies`, `f1`, `auc`, `best_params` and `majority_baseline_accuracy`, the training-fold majority baseline averaged over outer folds.
- `jnwb.assign_outer_folds(trials, *, analysis_cols=("session", "analysis", "slot_key"), group_col="cycle")`: Leave-one-group-out outer folds within each `analysis_cols` stratum. `trials` needs a `trial_id` column as well. Returns a copy with `outer_fold`, `outer_group` and `outer_fold_status`; a stratum with fewer than two groups gets `outer_fold=-1` and status `"insufficient_groups"` rather than a fold.
- `jnwb.build_representation_ladder(raster, *, modality="SPK", spatial_axis_metadata=None)`: Three feature representations of an `(n_trials, n_space, n_time)` raster, fitting nothing: `X_rate` collapses time, `X_vec` vectorizes every sample, `X_structured` keeps the tensor, and `contract` records the semantics and the space-axis topology. `modality="LFP"` requires `spatial_axis_metadata`.
- `jnwb.build_time_resolved_matrix(session, area, epochs_df, time_window_ms=..., bin_size_ms=20.0)` → `(X, unit_ids, bin_centers_ms)`: Spike counts shaped `(n_trials, n_units, n_bins)` from a session interface exposing `get_units` and `get_spike_times`, with bins in ms relative to each `start_time`. A `time_window_ms` span that is not whole `bin_size_ms` bins raises `ValueError`.
- `jnwb.compute_population_trajectory(session, area, epochs_df, n_components=3, device="cpu")`: Correlation PCA (units z-scored before the SVD) over time bins. Returns `trajectory` `(n_trials, n_components, n_bins)`, `explained_variance` as one fraction for all kept components together, `unit_ids` and `bin_centers`.
- `jnwb.rdm(X, metric="correlation", condensed=True)`: Representational Dissimilarity Matrix (RDM) computation with condensed or full square output.
- `jnwb.rdm_similarity(rdm1, rdm2, metric="spearman")` → `(statistic, p_value)`: Second-order representational similarity between two RDMs. The p-value treats RDM cells as independent observations, which they are not, so it is not a valid test: use a condition-label permutation for inference.
- `jnwb.jrsa(x1, x2, metric="rsa", stats=True)`: Unified Joint Representational Similarity Analysis with permutation nulls. `alternative` (`"two-sided"`, `"greater"` or `"less"`; anything else raises) sets the tail of `p`. With `permutations=0` or `stats=False`, `p` is the metric's two-sided parametric p, halved when `value` lies on the requested side and `1 - p/2` otherwise; `granger_ssr_ftest` raises for a one-sided alternative there, because its parametric p is an upper-tail F-test of a non-negative F, which has no side to halve on. `granger_ssr_ftest` and `transfer_entropy_histogram_nats` measure x2 -> x1, the reverse of `jnwb.granger(X, Y).x_to_y`; `phase_slope` is positive when x1 leads x2.

- `jnwb.fold_majority_baseline(y_train, y_test)`: Accuracy of predicting the training fold's majority class on the held-out fold. Report decoding accuracy against this, never against 1/n_classes, whenever classes are unbalanced.
- `jnwb.build_inner_validation_partitions(outer_trials, *, analysis_cols=("session", "analysis", "slot_key"))`: Inner train/validation partitions built from outer-training groups only, so hyperparameter selection never sees the outer test fold.

- `jnwb.majority_baseline(labels)`: Accuracy of always predicting the most frequent class in `labels`. This is the whole-set baseline; use `fold_majority_baseline` inside cross-validation, where the majority is a property of the training fold.

## 3. Invariants & Safeguards
1. **No CV Information Leakage**: Data preprocessing (centering, scaling) and hyperparameter selection must occur inside the training fold of `nested_cv_linear_svm`.
2. **Majority Baseline Verification**: Compare decoding accuracy against the `majority_baseline_accuracy` that `nested_cv_linear_svm` returns, or against `majority_baseline(labels)` outside cross-validation, rather than theoretical $1/K$ when class counts are unbalanced.
3. **jRSA Alignment Requirements**: Input feature matrices must share the same condition/trial dimension before computing second-order distance matrices.

## 4. Minimal Workflow
```python
import jnwb
import numpy as np

rng = np.random.default_rng(42)
X = rng.normal(size=(60, 20))  # 60 trials, 20 units
labels = np.array([0] * 30 + [1] * 30)

res = jnwb.nested_cv_linear_svm(X, labels, n_splits=3)
assert res["accuracy"] >= 0.0
```

## 5. Verification
- Verify `nested_cv_linear_svm` recovers known synthetic separability.
- Verify `jrsa` permutation null is centered at 0 for uncorrelated representation matrices.

## 6. Canonical Documentation Links
- [`docs/03_representational_similarity_jrsa.md`](../../docs/03_representational_similarity_jrsa.md)
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
