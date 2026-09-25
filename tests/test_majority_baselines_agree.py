"""Two exported functions computing one estimand must not answer differently.

`majority_baseline(labels)` and `fold_majority_baseline(y_train, y_test)` both document the
accuracy of predicting the majority class. Handed the same labels as both folds they are
computing the same quantity and must return the same number. On labels containing NaN they
returned 0.75 and 0.0.

The mechanism was that `np.unique` collects NaNs into one group, so `majority_baseline`
counted "missing" as a class and scored it, while `fold_majority_baseline` picked that same
NaN as the majority class and then tested it with `y_test == nan`, false everywhere. Neither
answer was right, so the repair refuses the input rather than choosing between them.

`nested_cv_linear_svm` never reached either number -- scikit-learn rejects a NaN `y` before
the baseline is computed -- so what is closed here is the direct route, and the test below
records that the pipeline's own behaviour is unchanged.
"""

from __future__ import annotations

import numpy as np
import pytest

import jnwb
from jnwb.decoding import fold_majority_baseline, majority_baseline

# Label sets with no missing values: the two functions must already agree on these, and
# must keep agreeing. `fold_majority_baseline(y, y)` is `majority_baseline(y)` by definition
# when the folds are the same set.
AGREEING = [
    pytest.param(np.array([0, 0, 1, 1]), id="balanced"),
    pytest.param(np.array([0, 0, 0, 1]), id="three-to-one"),
    pytest.param(np.array([-1, -1, 1]), id="negative-labels"),
    pytest.param(np.array([2, 5, 5, 5, 9]), id="non-contiguous-integers"),
    pytest.param(np.array(["a", "b", "b"]), id="string-labels"),
    pytest.param(np.array([1.5, 1.5, 2.5]), id="float-labels"),
]

MISSING = [
    pytest.param(np.full(8, np.nan), id="all-missing"),
    pytest.param(np.array([np.nan] * 6 + [1.0, 1.0]), id="mostly-missing"),
    pytest.param(np.array([0.0, 1.0, np.nan]), id="one-missing"),
    pytest.param(np.array([0.0, 1.0, np.inf]), id="infinite"),
]


class TestTheTwoAgreeOnLabelsThatNameClasses:
    @pytest.mark.parametrize("labels", AGREEING)
    def test_the_same_set_as_both_folds_gives_the_same_number(self, labels):
        assert fold_majority_baseline(labels, labels) == pytest.approx(
            majority_baseline(labels))


class TestNeitherScoresAMissingLabel:
    @pytest.mark.parametrize("labels", MISSING)
    def test_majority_baseline_refuses(self, labels):
        with pytest.raises(ValueError, match="non-finite label"):
            majority_baseline(labels)

    @pytest.mark.parametrize("labels", MISSING)
    def test_fold_majority_baseline_refuses(self, labels):
        with pytest.raises(ValueError, match="non-finite label"):
            fold_majority_baseline(labels, labels)

    def test_a_clean_training_fold_does_not_excuse_a_missing_test_label(self):
        """Both arguments are checked: the estimand is undefined either way round."""
        clean = np.array([0.0, 0.0, 1.0])
        with pytest.raises(ValueError, match="y_test"):
            fold_majority_baseline(clean, np.array([0.0, np.nan, 1.0]))

    def test_a_clean_test_fold_does_not_excuse_a_missing_training_label(self):
        """The other way round, and it has to be asserted separately.

        Passing one array as both folds -- which every other case here does -- cannot tell
        the two checks apart: dropping the `y_train` check entirely left those cases
        passing, because the identical `y_test` still raised.
        """
        clean = np.array([0.0, 0.0, 1.0])
        with pytest.raises(ValueError, match="y_train"):
            fold_majority_baseline(np.array([0.0, np.nan, 1.0]), clean)

    def test_the_message_counts_what_is_missing(self):
        with pytest.raises(ValueError, match="2 non-finite label\\(s\\) of 5"):
            majority_baseline(np.array([0.0, np.nan, 1.0, np.nan, 1.0]))


class TestTheBehaviourThatWasAlreadyPinnedIsUnchanged:
    def test_no_labels_is_still_not_an_error(self):
        """05-36 chose NaN for the empty case; that is explicit, not fabricated."""
        assert np.isnan(majority_baseline(np.array([])))

    def test_string_labels_still_never_touch_the_finiteness_check(self):
        """`np.isfinite` raises on a string dtype, so the guard must not reach them."""
        assert majority_baseline(np.array(["a", "b", "b"])) == pytest.approx(2 / 3)

    def test_object_labels_are_left_alone(self):
        """Object dtype has no finiteness to test, so the guard must pass it through.

        Homogeneous on purpose: `np.unique` sorts, and a mixed `{str, None}` object array
        raises out of the comparison long before any of this code is reached. That is
        numpy's behaviour and predates the guard.
        """
        labels = np.array(["x", "y", "x"], dtype=object)
        assert majority_baseline(labels) == pytest.approx(2 / 3)


class TestThePipelineIsUnchanged:
    def test_nan_labels_still_fail_before_a_baseline_is_computed(self):
        """Recorded, not repaired: scikit-learn already rejects a NaN `y`."""
        rng = np.random.default_rng(0)
        labels = np.array([0.0] * 10 + [1.0] * 10)
        features = rng.standard_normal((20, 4)) + labels[:, None] * 2.0
        labels[:3] = np.nan
        with pytest.raises(ValueError, match="NaN"):
            jnwb.nested_cv_linear_svm(features, labels, n_splits=3)

    def test_clean_labels_still_report_a_baseline(self):
        rng = np.random.default_rng(0)
        labels = np.array([0.0] * 10 + [1.0] * 10)
        features = rng.standard_normal((20, 4)) + labels[:, None] * 2.0
        out = jnwb.nested_cv_linear_svm(features, labels, n_splits=3)
        assert out["status"] == "success"
        assert np.isfinite(out["majority_baseline_accuracy"])
