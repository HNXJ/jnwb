"""Unit tests for jnwb.decoding -- generic nested cross-validated linear-SVM population
decoding, promoted 2026-08-23 from omission.jnwb_ext.decoding (99%-jnwb-sufficiency
normalization). Takes plain (X, labels) arrays; no session object or task semantics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from jnwb.decoding import (
    majority_baseline,
    fold_majority_baseline,
    nested_cv_linear_svm,
    assign_outer_folds,
    build_inner_validation_partitions,
    build_representation_ladder,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        import jnwb
        assert jnwb.majority_baseline is majority_baseline
        assert jnwb.fold_majority_baseline is fold_majority_baseline
        assert jnwb.nested_cv_linear_svm is nested_cv_linear_svm
        assert jnwb.assign_outer_folds is assign_outer_folds
        assert jnwb.build_inner_validation_partitions is build_inner_validation_partitions
        assert jnwb.build_representation_ladder is build_representation_ladder

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("majority_baseline", "fold_majority_baseline", "nested_cv_linear_svm",
                     "assign_outer_folds", "build_inner_validation_partitions",
                     "build_representation_ladder"):
            assert name in jnwb.__all__

    def test_omission_decoding_delegates_to_jnwb(self):
        decoding = pytest.importorskip("omission.jnwb_ext.decoding")
        assert decoding._majority_baseline is majority_baseline
        assert decoding._nested_cv_linear_svm is nested_cv_linear_svm

    def test_omission_structured_identity_delegates_to_jnwb(self):
        si = pytest.importorskip("omission.jnwb_ext.structured_identity")
        assert si.assign_outer_folds is assign_outer_folds
        assert si.build_inner_validation_partitions is build_inner_validation_partitions
        assert si.build_representation_ladder is build_representation_ladder


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


def _trials(n_groups=3, n_per_group=2, n_analyses=1):
    rows = []
    trial_id = 0
    for analysis in range(n_analyses):
        for group in range(n_groups):
            for _ in range(n_per_group):
                trial_id += 1
                rows.append({
                    "trial_id": trial_id, "session": "s1", "analysis": f"a{analysis}",
                    "slot_key": "p2", "cycle": group,
                })
    return pd.DataFrame(rows)


class TestAssignOuterFolds:
    def test_raises_on_missing_columns(self):
        with pytest.raises(ValueError, match="fold columns"):
            assign_outer_folds(pd.DataFrame({"session": ["s1"]}))

    def test_valid_stratum_gets_one_fold_per_group(self):
        out = assign_outer_folds(_trials(n_groups=3))
        assert (out["outer_fold_status"] == "valid").all()
        assert sorted(out["outer_fold"].unique().tolist()) == [0, 1, 2]

    def test_insufficient_groups_marked_and_unassigned(self):
        trials = _trials(n_groups=1, n_per_group=3)
        out = assign_outer_folds(trials)
        assert (out["outer_fold_status"] == "insufficient_groups").all()
        assert (out["outer_fold"] == -1).all()

    def test_folds_assigned_independently_per_analysis_stratum(self):
        out = assign_outer_folds(_trials(n_groups=2, n_analyses=2))
        for analysis in out["analysis"].unique():
            sub = out[out["analysis"] == analysis]
            assert sorted(sub["outer_fold"].unique().tolist()) == [0, 1]


class TestBuildInnerValidationPartitions:
    def test_insufficient_training_groups_row_when_only_one_group_left(self):
        outer = assign_outer_folds(_trials(n_groups=2, n_per_group=2))
        inner = build_inner_validation_partitions(outer)
        assert (inner["inner_role"] == "insufficient_training_groups").all()

    def test_outer_test_group_never_used_in_inner_partition(self):
        outer = assign_outer_folds(_trials(n_groups=4, n_per_group=2))
        inner = build_inner_validation_partitions(outer)
        real = inner[inner["inner_role"] != "insufficient_training_groups"]
        for outer_fold, sub in real.groupby("outer_fold"):
            held_out_group = outer[outer["outer_fold"] == outer_fold]["outer_group"].iloc[0]
            assert held_out_group not in sub["trial_group"].values

    def test_each_inner_fold_has_exactly_one_validation_group(self):
        outer = assign_outer_folds(_trials(n_groups=4, n_per_group=2))
        inner = build_inner_validation_partitions(outer)
        real = inner[inner["inner_role"] != "insufficient_training_groups"]
        for (outer_fold, inner_fold), sub in real.groupby(["outer_fold", "inner_fold"]):
            val_groups = sub.loc[sub["inner_role"] == "inner_validation", "trial_group"].unique()
            assert len(val_groups) == 1


class TestBuildRepresentationLadder:
    def test_rejects_wrong_ndim(self):
        with pytest.raises(ValueError, match="n_space, n_time"):
            build_representation_ladder(np.zeros((5, 5)))

    def test_rejects_non_finite(self):
        raster = np.zeros((2, 3, 4))
        raster[0, 0, 0] = np.nan
        with pytest.raises(ValueError, match="NaN or Inf"):
            build_representation_ladder(raster)

    def test_rejects_unknown_modality(self):
        with pytest.raises(ValueError, match="modality"):
            build_representation_ladder(np.zeros((2, 3, 4)), modality="EEG")

    def test_lfp_requires_spatial_metadata(self):
        with pytest.raises(ValueError, match="channel/probe"):
            build_representation_ladder(np.zeros((2, 3, 4)), modality="LFP")

    def test_shapes_of_r0_r1_r2(self):
        raster = np.arange(2 * 3 * 4, dtype=float).reshape(2, 3, 4)
        result = build_representation_ladder(raster)
        assert result["X_rate"].shape == (2, 3)
        assert result["X_vec"].shape == (2, 12)
        assert result["X_structured"].shape == (2, 3, 4)
        assert result["contract"]["training_authorized"] is False

    def test_spk_topology_depends_on_metadata_presence(self):
        raster = np.zeros((2, 3, 4))
        no_meta = build_representation_ladder(raster, modality="SPK")
        with_meta = build_representation_ladder(raster, modality="SPK", spatial_axis_metadata={"order": [0, 1, 2]})
        assert no_meta["contract"]["space_axis_topology"] == "unordered_units_permutation_equivariant_required"
        assert with_meta["contract"]["space_axis_topology"] == "metadata_ordered_units"
