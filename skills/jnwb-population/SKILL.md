---
name: jnwb-population
description: Population decoding, nested CV linear SVM, neural trajectories, joint
  representational similarity analysis (jRSA), and subspace geometry.
---

# `jnwb-population` — Population Decoding, Trajectories & jRSA

## 1. Trigger
Activate this skill when training population decoders (linear SVM), computing cross-validated representational geometry, population state-space trajectories, or Joint RSA (jRSA).

## 2. Task-to-Primitive Routing Matrix
- `jnwb.nested_cv_linear_svm(X, labels, n_splits=5)`: Leakage-safe nested cross-validated linear SVM decoding with inner regularization tuning.
- `jnwb.assign_outer_folds(groups, n_folds)`: Group-preserving cross-validation fold assignment.
- `jnwb.build_representation_ladder(X, ...)`: Multi-scale representational geometry decomposition.
- `jnwb.build_time_resolved_matrix(units_data, time_bins)`: Construct time-resolved population tensors.
- `jnwb.compute_population_trajectory(tensor, method="pca", n_components=3)`: Reduce dimensionality to state-space trajectories.
- `jnwb.jrsa(x1, x2, metric="rsa", stats=True)`: Unified Joint Representational Similarity Analysis with permutation nulls.

## 3. Invariants & Safeguards
1. **No CV Information Leakage**: Data preprocessing (centering, scaling) and hyperparameter selection must occur inside the training fold of `nested_cv_linear_svm`.
2. **Majority Baseline Verification**: Always compare decoding accuracy against `majority_baseline(labels)` rather than theoretical $1/K$ when class counts are unbalanced.
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
