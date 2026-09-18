"""Tutorial 07: Ensembles — Representational Dissimilarity, JRSA, and Decoding.

Run: python examples/tutorials/07_ensembles.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root.
_CHECKOUT = Path(__file__).resolve().parents[2]
if (_CHECKOUT / "jnwb" / "__init__.py").exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb


def main() -> None:
    rng = np.random.default_rng(42)
    n_conditions = 6
    n_units = 30

    # Synthetic population response vectors for 6 conditions across 30 neurons
    patterns_v1 = rng.normal(loc=1.0, scale=0.5, size=(n_conditions, n_units))
    patterns_v2 = patterns_v1 + 0.3 * rng.normal(size=(n_conditions, n_units))

    # 1. Representational Dissimilarity Matrix (RDM)
    # Condensed 1D vector form of size C * (C - 1) / 2
    rdm_v1_condensed = jnwb.rdm(patterns_v1, metric="correlation", condensed=True)
    expected_len = n_conditions * (n_conditions - 1) // 2
    assert len(rdm_v1_condensed) == expected_len
    print(f"Condensed RDM length: {len(rdm_v1_condensed)} pairs for {n_conditions} conditions")

    # Square symmetric form of shape (C, C)
    rdm_v1_square = jnwb.rdm(patterns_v1, metric="correlation", condensed=False)
    assert rdm_v1_square.shape == (n_conditions, n_conditions)
    np.testing.assert_allclose(np.diag(rdm_v1_square), 0.0)
    print(f"Square RDM shape: {rdm_v1_square.shape} with zero diagonal")

    # 2. Second-Order RDM Similarity across Areas
    rdm_v2_condensed = jnwb.rdm(patterns_v2, metric="correlation", condensed=True)
    rho, p_val = jnwb.rdm_similarity(rdm_v1_condensed, rdm_v2_condensed, metric="spearman")
    assert -1.0 <= rho <= 1.0
    print(f"Representational similarity (Spearman rho) between V1 and V2: {rho:.3f} (p={p_val:.4f})")

    # 3. Joint Representational Similarity Analysis (JRSA) over Time
    # Temporal response arrays: (n_conditions, n_features, n_timepoints)
    time_series_1 = rng.normal(size=(n_conditions, n_units, 10))
    time_series_2 = time_series_1 + 0.2 * rng.normal(size=(n_conditions, n_units, 10))
    jrsa_res = jnwb.jrsa(time_series_1, time_series_2, metric="rsa")
    assert np.isfinite(jrsa_res.value)
    print(f"JRSA representational similarity: {float(jrsa_res.value):.3f}")

    # 4. Population Decoding: Nested Cross-Validated Linear SVM
    # Trials x Features matrix X, Trials binary label vector y
    n_trials = 40
    X = rng.normal(size=(n_trials, n_units))
    # Condition 1 has elevated firing in first 5 neurons
    X[:20, :5] += 0.8
    y = np.array([0] * 20 + [1] * 20)

    cv_results = jnwb.nested_cv_linear_svm(X, y, n_splits=3)
    assert "accuracy" in cv_results and "fold_accuracies" in cv_results
    print(f"Population decoding accuracy: {cv_results['accuracy'] * 100:.1f}% across {len(cv_results['fold_accuracies'])} CV folds")


if __name__ == "__main__":
    main()
