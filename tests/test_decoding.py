"""Unit tests for jnwb.decoding -- nested cross-validated linear-SVM population decoding.

Takes plain (X, labels) arrays; no session object or task semantics.
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


def _rng_probe_data():
    g = np.random.default_rng(0)
    X = g.normal(size=(60, 5))
    y = np.repeat([0, 1], 30)
    X[y == 1, 0] += 1.0
    return X, y, np.tile(np.arange(6), 10)


class TestNestedCvRng:
    @pytest.mark.parametrize("grouped", [False, True])
    def test_rng_none_leaves_the_global_random_state_alone(self, grouped):
        """`rng=None` reached scikit-learn as `random_state=None`, which draws the folds,
        and the grouped path's group order, from NumPy's global RandomState."""
        X, y, groups = _rng_probe_data()
        np.random.seed(123)
        before = np.random.get_state()
        nested_cv_linear_svm(X, y, n_splits=3, rng=None,
                             groups=groups if grouped else None)
        after = np.random.get_state()
        assert before[0] == after[0] and before[2:] == after[2:]
        np.testing.assert_array_equal(before[1], after[1])

    @pytest.mark.parametrize("grouped, folds, f1, auc, c", [
        (False, [0.8, 0.7, 0.8], 0.75, 0.8788888888888888, 1.0),
        (True, [0.95, 0.85, 0.85], 0.8852459016393442, 0.9233333333333333, 0.1),
    ])
    def test_an_int_rng_reproduces_its_folds(self, grouped, folds, f1, auc, c):
        """Pinned before `rng=None` stopped passing through: an int seed is unchanged."""
        X, y, groups = _rng_probe_data()
        r = nested_cv_linear_svm(X, y, n_splits=3, rng=7, groups=groups if grouped else None)
        np.testing.assert_allclose(r["fold_accuracies"], folds, rtol=1e-12)
        np.testing.assert_allclose([r["f1"], r["auc"]], [f1, auc], rtol=1e-12)
        assert r["best_params"] == {"C": c}


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


class TestCrossValidationIsolation:
    """0.2.4-05: the decoder must not see its own test folds.

    Nested CV was exercised but never asserted leak-free. The discriminating regime is
    many features and few trials: if any step that sees the labels or the full feature
    matrix -- scaling, feature selection, hyperparameter choice -- were fitted outside the
    outer fold, accuracy on labels that carry no information would sit well above chance
    rather than at it.
    """

    N_TRIALS = 60
    N_FEATURES = 200
    SEEDS = range(10)

    def test_uninformative_labels_decode_at_chance(self):
        accuracies = []
        for seed in self.SEEDS:
            rng = np.random.default_rng(seed)
            X = rng.normal(size=(self.N_TRIALS, self.N_FEATURES))
            labels = rng.integers(0, 2, size=self.N_TRIALS)
            accuracies.append(nested_cv_linear_svm(X, labels, n_splits=5)["accuracy"])
        mean_accuracy = float(np.mean(accuracies))
        assert 0.40 <= mean_accuracy <= 0.60, (
            f"labels independent of features decoded at {mean_accuracy:.3f}; "
            f"per-seed {np.round(accuracies, 3).tolist()}"
        )

    def test_shuffling_labels_destroys_a_real_effect(self):
        """The paired control: the same features decode when the labels mean something."""
        rng = np.random.default_rng(1)
        labels = np.array([0] * 30 + [1] * 30)
        X = rng.normal(size=(self.N_TRIALS, 20)) + labels[:, None] * 2.0
        intact = nested_cv_linear_svm(X, labels, n_splits=5)["accuracy"]

        shuffled = []
        for seed in self.SEEDS:
            permuted = np.random.default_rng(seed).permutation(labels)
            shuffled.append(nested_cv_linear_svm(X, permuted, n_splits=5)["accuracy"])
        mean_shuffled = float(np.mean(shuffled))

        assert intact > 0.9, f"a separable effect decoded at only {intact:.3f}"
        assert mean_shuffled <= 0.65, (
            f"shuffled labels still decoded at {mean_shuffled:.3f} on the same features"
        )
        assert intact - mean_shuffled > 0.25

    def test_the_majority_class_baseline_is_reported_on_the_same_splits(self):
        """Without it a caller cannot tell an imbalanced dataset from a real effect."""
        rng = np.random.default_rng(3)
        labels = np.array([0] * 48 + [1] * 12)
        X = rng.normal(size=(60, 20))
        out = nested_cv_linear_svm(X, labels, n_splits=4)
        assert "majority_baseline_accuracy" in out
        assert out["majority_baseline_accuracy"] == pytest.approx(0.8, abs=0.1)
        # An 80/20 split decodes at the baseline here, so accuracy alone would read as a
        # strong result. The baseline on the same splits is what makes that visible.
        assert out["accuracy"] == pytest.approx(out["majority_baseline_accuracy"], abs=0.1)


def _noisy_two_class():
    rng = np.random.default_rng(20260925)
    labels = np.array([0] * 26 + [1] * 22)
    X = rng.normal(size=(48, 6))
    X[labels == 1, :2] += 0.6
    return X, labels


def _group_offset_data(n_groups=20, n_per_group=6, n_features=30, seed=0):
    """Labels constant within a group, features a per-group offset with no class signal.

    A decoder that has seen other trials of the test trial's group can identify the
    group, and through it the label; one that has not can only guess.
    """
    rng = np.random.default_rng(seed)
    groups = np.repeat(np.arange(n_groups), n_per_group)
    labels = np.repeat(np.arange(n_groups) % 2, n_per_group)
    offsets = rng.normal(scale=3.0, size=(n_groups, n_features))
    X = offsets[groups] + rng.normal(scale=0.3, size=(groups.size, n_features))
    return X, labels, groups


def _record_grouped_splits(monkeypatch):
    """Record every grouped split the decoder draws: trial count, fold count and folds."""
    import jnwb.decoding as decoding

    calls = []
    original = decoding._grouped_splits

    def recording(X, y, codes, n_splits, random_state):
        folds = original(X, y, codes, n_splits, random_state)
        calls.append({"n": len(codes), "n_splits": n_splits, "folds": folds})
        return folds

    monkeypatch.setattr(decoding, "_grouped_splits", recording)
    return calls


class TestNestedCvGroups:
    # Computed by running the pre-`groups` implementation (commit 27f400a2) on
    # `_noisy_two_class()`. The data is noisy enough that every fold changes the numbers,
    # so a changed partition cannot reproduce them.
    PINNED = {
        42: dict(
            accuracy=0.7244444444444443,
            fold_accuracies=[0.8, 0.7, 0.9, 0.7777777777777778, 0.4444444444444444],
            f1=0.7111111111111111, auc=0.7797202797202797, C=0.1,
            majority=0.5422222222222223,
        ),
        7: dict(
            accuracy=0.6666666666666666,
            fold_accuracies=[0.8, 0.5, 0.7, 0.5555555555555556, 0.7777777777777778],
            f1=0.5789473684210527, auc=0.736013986013986, C=0.1,
            majority=0.5422222222222223,
        ),
    }

    @pytest.mark.parametrize("seed", [42, 7])
    @pytest.mark.parametrize("pass_none", [False, True])
    def test_a_call_without_groups_is_numerically_unchanged(self, seed, pass_none):
        X, labels = _noisy_two_class()
        kwargs = {"groups": None} if pass_none else {}
        if seed != 42:
            kwargs["rng"] = seed
        res = nested_cv_linear_svm(X, labels, n_splits=5, **kwargs)
        want = self.PINNED[seed]
        exact = dict(rel=0, abs=1e-12)
        assert res["status"] == "success" and res["cv_scheme"] == "nested_stratified"
        assert res["fold_accuracies"].tolist() == pytest.approx(want["fold_accuracies"], **exact)
        assert res["accuracy"] == pytest.approx(want["accuracy"], **exact)
        assert res["f1"] == pytest.approx(want["f1"], **exact)
        assert res["auc"] == pytest.approx(want["auc"], **exact)
        assert res["best_params"] == {"C": want["C"]}
        assert res["majority_baseline_accuracy"] == pytest.approx(want["majority"], **exact)

    def test_grouped_folds_never_split_a_group(self, monkeypatch):
        """Asserted on the folds the decoder iterated, captured at the splitter."""
        import jnwb.decoding as decoding

        calls = _record_grouped_splits(monkeypatch)
        X, labels, groups = _group_offset_data(n_groups=12)
        ids = np.array([f"block-{g}" for g in groups], dtype=object)  # opaque ids, encoded
        res = nested_cv_linear_svm(X, labels, n_splits=4, groups=ids)
        assert res["status"] == "success"
        assert res["cv_scheme"] == "nested_stratified_group"

        outer = [c for c in calls if c["n"] == groups.size]
        assert len(outer) == 1, "the outer folds were not drawn by the grouped splitter"
        outer_folds = outer[0]["folds"]
        assert len(outer_folds) == len(res["fold_accuracies"]) == 4
        tested = np.concatenate([test for _, test in outer_folds])
        assert np.array_equal(np.sort(tested), np.arange(groups.size))
        # Checked against the caller's ids, not the codes the splitter saw.
        for train, test in outer_folds:
            assert not set(ids[train]) & set(ids[test])

        # Inner behaviour: C is searched over folds that hold out groups of the outer
        # training set, one grouped search per outer fold.
        inner = [c for c in calls if c["n"] != groups.size]
        assert len(inner) == len(outer_folds)
        for call, (train, _test) in zip(inner, outer_folds):
            assert call["n"] == train.size
            inner_ids = ids[train]
            for i_train, i_test in call["folds"]:
                assert not set(inner_ids[i_train]) & set(inner_ids[i_test])

    def test_grouped_outer_folds_keep_class_balance(self):
        """``StratifiedGroupKFold(shuffle=True)`` before scikit-learn 1.8 shuffled the
        per-group class counts without their groups, so its folds were not stratified;
        on 1.3.1 this design averaged 0.218 against 0.106 for the route used here."""
        import jnwb.decoding as decoding

        groups = np.repeat(np.arange(12), 6)
        n_class1 = np.tile(np.arange(1, 7), 2)
        labels = np.concatenate([np.r_[np.ones(k), np.zeros(6 - k)] for k in n_class1]).astype(int)
        X = np.zeros((groups.size, 1))
        worst = []
        for rs in range(40):
            folds = decoding._grouped_splits(X, labels, groups, 4, rs)
            worst.append(max(abs(labels[te].mean() - labels.mean()) for _, te in folds))
        assert np.mean(worst) <= 0.15, np.mean(worst)

    def test_grouped_folds_are_pinned_per_seed_and_differ_between_seeds(self):
        """The same held-out groups on every supported scikit-learn: checked on 1.3.1
        and 1.8.0. A seed that stopped reaching the folds, or a splitter left to shuffle
        on its own, changes them."""
        import jnwb.decoding as decoding

        groups = np.repeat(np.arange(12), 6)
        n_class1 = np.tile(np.arange(1, 7), 2)
        labels = np.concatenate([np.r_[np.ones(k), np.zeros(6 - k)] for k in n_class1]).astype(int)
        X = np.zeros((groups.size, 1))

        def held_out(rs):
            folds = decoding._grouped_splits(X, labels, groups, 4, rs)
            return [sorted(set(groups[te].tolist())) for _, te in folds]

        assert held_out(0) == [[3, 9, 11], [1, 5, 7], [0, 2, 10], [4, 6, 8]]
        assert held_out(1) == [[0, 2, 11], [1, 5, 9], [6, 8, 10], [3, 4, 7]]

    def test_n_splits_is_clipped_to_groups_and_to_the_minority_class(self, monkeypatch):
        calls = _record_grouped_splits(monkeypatch)
        rng = np.random.default_rng(0)
        groups = np.repeat(np.arange(3), 12)
        labels = np.tile([0, 1], 18)
        res = nested_cv_linear_svm(rng.normal(size=(36, 4)), labels, n_splits=10, groups=groups)
        assert len(res["fold_accuracies"]) == 3 and calls[0]["n_splits"] == 3

        # Two class-1 trials in six groups: the minority count caps the folds, as it does
        # without groups.
        calls.clear()
        groups = np.repeat(np.arange(6), 4)
        labels = np.zeros(24, dtype=int)
        labels[[0, 4]] = 1
        res = nested_cv_linear_svm(rng.normal(size=(24, 4)), labels, n_splits=5, groups=groups)
        assert len(res["fold_accuracies"]) == 2 and calls[0]["n_splits"] == 2

    def test_inner_folds_are_capped_by_the_training_groups(self, monkeypatch):
        calls = _record_grouped_splits(monkeypatch)
        rng = np.random.default_rng(0)
        groups = np.repeat(np.arange(3), 12)
        labels = np.tile([0, 1], 18)
        nested_cv_linear_svm(rng.normal(size=(36, 4)), labels, n_splits=3, groups=groups)
        inner = [c for c in calls if c["n"] != groups.size]
        assert [c["n_splits"] for c in inner] == [2, 2, 2]

    def test_an_inner_split_that_would_hold_one_class_falls_back_to_fixed_c(self, monkeypatch):
        """Group 2 is all class 0, so an outer fold that trains on groups {1, 2} or {0, 2}
        has an inner split training on group 2 alone; only the fold that holds out group 2
        can search C."""
        import jnwb.decoding as decoding

        searches = []

        class Counting(decoding.GridSearchCV):
            def fit(self, X, y=None, **kw):
                searches.append(len(y))
                return super().fit(X, y, **kw)

        monkeypatch.setattr(decoding, "GridSearchCV", Counting)
        rng = np.random.default_rng(0)
        groups = np.repeat(np.arange(3), 6)
        labels = np.r_[np.tile([0, 1], 6), np.zeros(6)].astype(int)
        res = nested_cv_linear_svm(rng.normal(size=(18, 3)), labels, n_splits=3, groups=groups)
        assert res["status"] == "success" and len(res["fold_accuracies"]) == 3
        assert searches == [12], searches

    def test_grouped_folds_remove_the_group_identity_shortcut(self):
        X, labels, groups = _group_offset_data()
        rowwise = nested_cv_linear_svm(X, labels, n_splits=5)
        grouped = nested_cv_linear_svm(X, labels, n_splits=5, groups=groups)
        assert rowwise["accuracy"] > 0.9, rowwise["accuracy"]
        assert grouped["accuracy"] < 0.7, grouped["accuracy"]

    def test_fewer_than_two_groups_is_a_status(self):
        X, labels = _noisy_two_class()
        res = nested_cv_linear_svm(X, labels, n_splits=5, groups=np.zeros(len(labels)))
        assert res["status"] == "insufficient_groups_for_cv" and np.isnan(res["accuracy"])

    @pytest.mark.parametrize(
        "bad",
        [
            np.arange(47),
            np.r_[np.arange(47.0), np.nan],
            np.array([*range(47), float("nan")], dtype=object),
            np.array([*range(47), None], dtype=object),
            np.array([*range(24), *[f"b{i}" for i in range(24)]], dtype=object),
        ],
        ids=["short", "float-nan", "object-nan", "object-none", "unorderable"],
    )
    def test_groups_need_one_comparable_id_per_trial(self, bad):
        X, labels = _noisy_two_class()
        with pytest.raises(ValueError, match="groups"):
            nested_cv_linear_svm(X, labels, n_splits=5, groups=bad)

    def test_groups_is_keyword_only(self):
        X, labels = _noisy_two_class()
        with pytest.raises(TypeError):
            nested_cv_linear_svm(X, labels, 5, 42, np.arange(len(labels)) % 4)
