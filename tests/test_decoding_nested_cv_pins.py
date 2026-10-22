"""Pins on ``nested_cv_linear_svm``'s full return dict, one grouped and one ungrouped fixture.

The values were read from the implementation before its pipeline was moved into a shared
helper (AGENTS.md 4.7). Refactoring must leave every key unchanged: floats are compared at
``rtol=1e-12``, everything else by equality.
"""

from __future__ import annotations

import numpy as np
from numpy.testing import assert_allclose
from sklearn.model_selection import StratifiedKFold

from jnwb.decoding import nested_cv_linear_svm


def _ungrouped_fixture():
    y = np.array([0] * 3 + [1] * 20)
    X = np.random.default_rng(3).normal(size=(23, 4)) + y[:, None] * 1.0
    return X, y


def _grouped_fixture():
    y = np.tile([0, 1], 30)
    groups = np.repeat(np.arange(6), 10)
    X = np.random.default_rng(4).normal(size=(60, 4)) + y[:, None] * 0.8
    return X, y, groups


PINNED_UNGROUPED = {
    "accuracy": 0.8712121212121212,
    "fold_accuracies": [0.8333333333333334, 0.9090909090909091],
    "best_params": {"C": 1.0},
    "status": "success",
    "cv_scheme": "nested_stratified",
    "accuracy_source": "outer_cv_mean",
    "f1": 0.9302325581395349,
    "auc": 0.3166666666666667,
    "majority_baseline_accuracy": 0.8712121212121212,
    "seed": 5,
}

PINNED_GROUPED = {
    "accuracy": 0.7833333333333333,
    "fold_accuracies": [0.85, 0.75, 0.75],
    "best_params": {"C": 0.01},
    "status": "success",
    "cv_scheme": "nested_stratified_group",
    "accuracy_source": "outer_cv_mean",
    "f1": 0.7868852459016393,
    "auc": 0.8266666666666667,
    "majority_baseline_accuracy": 0.5,
    "seed": 7,
}


def _assert_pinned(result, pinned):
    assert set(result) == set(pinned), f"return keys changed: {sorted(set(result) ^ set(pinned))}"
    for key, expected in pinned.items():
        actual = result[key]
        if isinstance(expected, float):
            assert_allclose(actual, expected, rtol=1e-12, atol=0.0, err_msg=key)
        elif isinstance(expected, list):
            assert_allclose(np.asarray(actual), np.asarray(expected), rtol=1e-12, atol=0.0,
                            err_msg=key)
        elif isinstance(expected, dict):
            assert set(actual) == set(expected), key
            for k, v in expected.items():
                assert_allclose(actual[k], v, rtol=1e-12, atol=0.0, err_msg=f"{key}.{k}")
        else:
            assert actual == expected, f"{key}: {actual!r} != {expected!r}"


def test_ungrouped_return_dict_is_pinned():
    X, y = _ungrouped_fixture()
    # The fixture must build the case it is named after: 3 minority trials, two outer
    # folds, and training folds holding one and two minority trials, so both the fixed-C
    # fallback and the inner grid search run.
    assert np.bincount(y).tolist() == [3, 20]
    train_minority = {
        int(np.sum(y[tr] == 0))
        for tr, _ in StratifiedKFold(n_splits=2, shuffle=True, random_state=5).split(X, y)
    }
    assert train_minority == {1, 2}, train_minority

    result = nested_cv_linear_svm(X, y, 2, rng=5)
    assert result["status"] == "success"
    _assert_pinned(result, PINNED_UNGROUPED)


def test_grouped_return_dict_is_pinned():
    X, y, groups = _grouped_fixture()
    # Six groups of ten trials, each holding both labels: outer folds of two groups, and an
    # inner grouped search with three inner splits.
    assert len(np.unique(groups)) == 6
    assert all(len(np.unique(y[groups == g])) == 2 for g in np.unique(groups))

    result = nested_cv_linear_svm(X, y, 3, rng=7, groups=groups)
    assert result["status"] == "success"
    assert result["cv_scheme"] == "nested_stratified_group"
    _assert_pinned(result, PINNED_GROUPED)
