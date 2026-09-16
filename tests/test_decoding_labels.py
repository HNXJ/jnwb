"""05-36: `decoding` refused valid label sets and made false claims about the data.

`np.bincount(labels.astype(int))` counts every integer below the maximum as a class,
including ones that are absent, and refuses anything that is not a contiguous
non-negative integer. Reproduced on one separable `X` of shape (40, 5), 20 trials per
class, relabelled four ways:

    {0, 1}      accuracy 0.846, status "success"
    {1, 2}      status "insufficient_trials_for_cv", every metric NaN
    {0, 2}      status "insufficient_trials_for_cv", every metric NaN
    {-1, 1}     ValueError: 'list' argument must have no negative elements
    {'a', 'b'}  ValueError: invalid literal for int() with base 10: 'a'

`status` is a claim about the data. "insufficient_trials_for_cv" for 20 separable trials
per class is a false one, and it is the failure mode that matters: it does not raise, it
reports NaN metrics that a caller records as a real negative result.

A second defect surfaced while repairing the first. `f1` and `auc` were left to sklearn's
`pos_label=1` default, so the positive class depended on what the classes were called:
{0, 1} scored f1 = 0.857143 and the same trials as {1, 2} scored 0.842105, because 1 is
the higher class in one and the lower in the other. {0, 2} and {'a', 'b'} raised, and a
bare `except ValueError` turned the AUC into NaN for a value that is perfectly computable.

And the two-step partition pipeline could not consume its own output: `assign_outer_folds`
accepts string group ids and reports `outer_fold_status="valid"`, after which
`build_inner_validation_partitions` raised
`ValueError: invalid literal for int() with base 10: 'c2'` on that very frame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from jnwb.decoding import (
    assign_outer_folds,
    build_inner_validation_partitions,
    fold_majority_baseline,
    majority_baseline,
    nested_cv_linear_svm,
)


@pytest.fixture
def separable():
    """40 trials, 5 features, 20 per class, linearly separable."""
    g = np.random.default_rng(0)
    X = g.normal(size=(40, 5))
    base = np.array([0] * 20 + [1] * 20)
    X[base == 1] += 1.2
    return X, base


# The same two-class structure, spelled six ways.
SPELLINGS = {
    "0_1": lambda b: b,
    "1_2": lambda b: b + 1,
    "0_2": lambda b: b * 2,
    "neg1_1": lambda b: b * 2 - 1,
    "5_9": lambda b: np.where(b == 0, 5, 9),
    "strings": lambda b: np.array(["a", "b"])[b],
}


class TestAnyTwoClassLabelSetDecodes:

    @pytest.mark.parametrize("name", list(SPELLINGS))
    def test_it_succeeds(self, separable, name):
        X, base = separable
        res = nested_cv_linear_svm(X, SPELLINGS[name](base), n_splits=3)
        assert res["status"] == "success", (
            f"{name}: 20 separable trials per class reported {res['status']!r}"
        )
        assert np.isfinite(res["accuracy"])

    @pytest.mark.parametrize("name", [n for n in SPELLINGS if n != "0_1"])
    def test_renaming_the_classes_changes_no_number(self, separable, name):
        """The classes' names are not data. Every metric must be identical."""
        X, base = separable
        ref = nested_cv_linear_svm(X, base, n_splits=3)
        got = nested_cv_linear_svm(X, SPELLINGS[name](base), n_splits=3)
        for key in ("accuracy", "f1", "auc", "majority_baseline_accuracy"):
            assert got[key] == ref[key], (
                f"{name}: {key} = {got[key]!r}, but {key} = {ref[key]!r} for {{0, 1}}"
            )
        np.testing.assert_array_equal(got["fold_accuracies"], ref["fold_accuracies"])

    def test_the_positive_class_is_the_second_in_sorted_order(self, separable):
        """Not sklearn's `pos_label=1`, which is a different class in {1, 2} than in
        {0, 1}. `classes[1]` is also the class `decision_function` scores toward, since
        sklearn sorts `clf.classes_`, so f1 and AUC agree about which way is up."""
        X, base = separable
        res = nested_cv_linear_svm(X, base * 2, n_splits=3)   # {0, 2}: pos_label=1 absent
        assert res["auc"] > 0.5, "the AUC is inverted, so the positive class is wrong"
        assert np.isfinite(res["f1"])

    def test_an_auc_that_is_computable_is_not_reported_as_nan(self, separable):
        """A bare `except ValueError: auc = nan` hid the `pos_label` failure."""
        X, base = separable
        for name in SPELLINGS:
            res = nested_cv_linear_svm(X, SPELLINGS[name](base), n_splits=3)
            assert np.isfinite(res["auc"]), f"{name}: AUC reported NaN"


class TestStatusNeverAssertsSomethingFalse:

    def test_too_few_trials_in_a_class_still_reports_that(self, separable):
        """The status must remain available for the case it was written for."""
        X, base = separable
        labels = base.copy()
        labels[:19] = 1                       # one trial left in class 0
        res = nested_cv_linear_svm(X, labels, n_splits=3)
        assert res["status"] == "insufficient_trials_for_cv"
        assert np.isnan(res["accuracy"])

    def test_it_reports_that_for_the_renamed_labels_too(self, separable):
        X, base = separable
        labels = np.where(base == 0, 7, 9)
        labels[:19] = 9
        res = nested_cv_linear_svm(X, labels, n_splits=3)
        assert res["status"] == "insufficient_trials_for_cv"

    def test_one_class_is_its_own_status_not_a_trial_count_claim(self, separable):
        """40 trials of one class is not "insufficient trials"; it is one class."""
        X, _ = separable
        res = nested_cv_linear_svm(X, np.zeros(40, dtype=int), n_splits=3)
        assert res["status"] == "insufficient_classes_for_cv"
        assert np.isnan(res["accuracy"])

    def test_an_empty_label_set_does_not_claim_success(self, separable):
        X, _ = separable
        res = nested_cv_linear_svm(X[:0], np.array([], dtype=int), n_splits=3)
        assert res["status"] != "success"

    def test_the_documented_status_values_are_the_ones_returned(self, separable):
        X, base = separable
        doc = nested_cv_linear_svm.__doc__
        for status in ("insufficient_trials_for_cv", "insufficient_classes_for_cv",
                       "success"):
            assert status in doc, f"{status} is returned but not documented"


class TestTheBaselinesCountClassesNotIntegers:

    @pytest.mark.parametrize("labels,expected", [
        (np.array([0, 0, 0, 1]), 0.75),
        (np.array([1, 1, 1, 2]), 0.75),
        (np.array([-1, -1, -1, 5]), 0.75),
        (np.array(["a", "a", "a", "b"]), 0.75),
        (np.array([10, 10, 20, 20]), 0.5),
    ])
    def test_majority_baseline(self, labels, expected):
        assert majority_baseline(labels) == expected

    def test_majority_baseline_is_nan_for_no_labels(self):
        assert np.isnan(majority_baseline(np.array([])))

    @pytest.mark.parametrize("train,test,expected", [
        (np.array([0, 0, 1]), np.array([0, 0, 1, 1]), 0.5),
        (np.array([1, 1, 2]), np.array([1, 1, 2, 2]), 0.5),
        (np.array(["a", "a", "b"]), np.array(["a", "b"]), 0.5),
        (np.array([3, 3, 3]), np.array([3, 3, 3, 9]), 0.75),
    ])
    def test_fold_majority_baseline(self, train, test, expected):
        assert fold_majority_baseline(train, test) == expected


class TestThePipelineConsumesItsOwnOutput:

    @staticmethod
    def _trials(group_ids):
        return pd.DataFrame({
            "session": ["s1"] * 12, "analysis": ["a"] * 12, "slot_key": ["k"] * 12,
            "trial_id": list(range(12)), "cycle": list(group_ids) * 3,
        })

    @pytest.mark.parametrize("groups", [
        ["c1", "c2", "c3", "c4"],
        [10, 20, 30, 40],
        [0, 1, 2, 3],
    ])
    def test_it_round_trips(self, groups):
        outer = assign_outer_folds(self._trials(groups))
        assert set(outer["outer_fold_status"]) == {"valid"}
        inner = build_inner_validation_partitions(outer)
        assert len(inner) > 0

    def test_the_group_ids_survive_as_themselves(self):
        """They are opaque labels, not numbers -- `int('c2')` was the failure."""
        outer = assign_outer_folds(self._trials(["c1", "c2", "c3", "c4"]))
        inner = build_inner_validation_partitions(outer)
        assert set(inner["inner_group"]) <= {"c1", "c2", "c3", "c4"}
        assert set(inner["trial_group"]) <= {"c1", "c2", "c3", "c4"}
        assert set(inner["validation_group"]) <= {"c1", "c2", "c3", "c4"}

    def test_integer_group_ids_are_still_integers(self):
        outer = assign_outer_folds(self._trials([10, 20, 30, 40]))
        inner = build_inner_validation_partitions(outer)
        assert set(inner["inner_group"]) <= {10, 20, 30, 40}

    def test_the_fold_indices_are_still_ints(self):
        """Only the group ids stopped being cast; `outer_fold` and `inner_fold` are
        genuinely positional and stay integers."""
        outer = assign_outer_folds(self._trials(["c1", "c2", "c3", "c4"]))
        inner = build_inner_validation_partitions(outer)
        for col in ("outer_fold", "inner_fold", "trial_id"):
            assert all(isinstance(v, (int, np.integer)) for v in inner[col]), col
