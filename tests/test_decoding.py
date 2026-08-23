"""Unit tests for jnwb.decoding -- generic nested cross-validated linear-SVM population
decoding, promoted 2026-08-23 from omission.jnwb_ext.decoding (99%-jnwb-sufficiency
normalization). Takes plain (X, labels) arrays; no session object or task semantics.
"""
from __future__ import annotations

import numpy as np
import pytest

from jnwb.decoding import majority_baseline, fold_majority_baseline, nested_cv_linear_svm


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.majority_baseline is majority_baseline
        assert jnwb.fold_majority_baseline is fold_majority_baseline
        assert jnwb.nested_cv_linear_svm is nested_cv_linear_svm

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("majority_baseline", "fold_majority_baseline", "nested_cv_linear_svm"):
            assert name in jnwb.__all__

    def test_omission_decoding_delegates_to_jnwb(self):
        decoding = pytest.importorskip("omission.jnwb_ext.decoding")
        assert decoding._majority_baseline is majority_baseline
        assert decoding._nested_cv_linear_svm is nested_cv_linear_svm


class TestMajorityBaseline:
    def test_empty_labels_is_nan(self):
        assert np.isnan(majority_baseline(np.array([])))

    def test_balanced_binary_is_half(self):
        labels = np.array([0, 0, 1, 1])
        assert majority_baseline(labels) == pytest.approx(0.5)

    def test_imbalanced_returns_majority_fraction(self):
        labels = np.array([0, 0, 0, 1])
        assert majority_baseline(labels) == pytest.approx(0.75)


class TestFoldMajorityBaseline:
    def test_predicts_train_majority_on_test(self):
        y_train = np.array([0, 0, 0, 1])
        y_test = np.array([0, 0, 1])
        # train majority class is 0; test has 2/3 zeros
        assert fold_majority_baseline(y_train, y_test) == pytest.approx(2.0 / 3.0)


class TestNestedCvLinearSvm:
    def test_insufficient_trials_returns_nan_status(self):
        X = np.zeros((3, 2))
        labels = np.array([0, 0, 1])  # minority class has only 1 trial
        result = nested_cv_linear_svm(X, labels, n_splits=5)
        assert result["status"] == "insufficient_trials_for_cv"
        assert np.isnan(result["accuracy"])

    def test_separable_classes_decode_near_perfectly(self):
        rng = np.random.default_rng(0)
        n_per_class = 30
        X0 = rng.normal(loc=-5.0, scale=0.5, size=(n_per_class, 5))
        X1 = rng.normal(loc=5.0, scale=0.5, size=(n_per_class, 5))
        X = np.vstack([X0, X1])
        labels = np.array([0] * n_per_class + [1] * n_per_class)
        result = nested_cv_linear_svm(X, labels, n_splits=5)
        assert result["status"] == "success"
        assert result["accuracy"] > 0.9
        assert result["f1"] > 0.9

    def test_returns_all_documented_keys(self):
        rng = np.random.default_rng(1)
        X = rng.standard_normal((20, 3))
        labels = rng.integers(0, 2, 20)
        result = nested_cv_linear_svm(X, labels, n_splits=3)
        for key in ("accuracy", "fold_accuracies", "best_params", "status", "cv_scheme",
                    "f1", "auc", "majority_baseline_accuracy"):
            assert key in result
