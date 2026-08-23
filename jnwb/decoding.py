"""
jnwb.decoding -- generic nested cross-validated linear-SVM population decoding: takes a plain
(n_trials, n_features) matrix and integer labels, returns accuracy/F1/AUC/majority-baseline
with no fabricated metrics under degenerate conditions.

PROMOTED 2026-08-23 from omission.jnwb_ext.decoding (99%-jnwb-sufficiency normalization):
``nested_cv_linear_svm`` (formerly the private ``_nested_cv_linear_svm``) and its majority-
baseline helpers never touch a session object, condition code, or feature-construction
method -- they operate purely on ``X``/``labels`` arrays, so they generalize to any population
decoding problem (spike counts, band power, TFR features, ...). ``build_spike_count_matrix``,
``decode_stimulus_identity``, and ``decode_omission_presence`` stay in
omission.jnwb_ext.decoding: they are irreducibly coupled to ``OmissionSession``'s API and this
task's condition-pair semantics (e.g. "AAAB" vs "BBBA"), and now call this module instead of
duplicating the CV/scoring logic.

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Union

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

log = logging.getLogger(__name__)


def majority_baseline(labels: np.ndarray) -> float:
    """Accuracy of always predicting the most frequent class in ``labels``."""
    labels = np.asarray(labels)
    if len(labels) == 0:
        return float("nan")
    counts = np.bincount(labels.astype(int))
    return float(counts.max() / len(labels))


def fold_majority_baseline(y_train: np.ndarray, y_test: np.ndarray) -> float:
    """Accuracy of predicting the training-fold majority class on the held-out fold."""
    counts = np.bincount(np.asarray(y_train).astype(int))
    majority_class = int(np.argmax(counts))
    return float(np.mean(np.asarray(y_test).astype(int) == majority_class))


def nested_cv_linear_svm(
    X: np.ndarray,
    labels: np.ndarray,
    n_splits: int,
) -> Dict[str, Union[float, np.ndarray, dict, str]]:
    """Outer stratified CV; inner GridSearchCV for C. No synthetic metrics.

    In addition to mean outer-fold accuracy, pools out-of-fold predictions and
    decision scores across all outer folds to report a single F1 score and
    ROC-AUC, plus a per-fold majority-class baseline accuracy (mean across
    folds) so callers can check whether the classifier beats chance/imbalance
    on the same splits used for accuracy.

    Args:
        X: (n_trials, n_features) feature matrix.
        labels: (n_trials,) integer class labels (binary).
        n_splits: requested number of outer folds; clipped to the minority
            class count when there are too few trials per class.

    Returns:
        dict with accuracy, fold_accuracies, best_params, status, cv_scheme,
        f1, auc, majority_baseline_accuracy. ``status`` is
        ``"insufficient_trials_for_cv"`` (all metrics NaN) when the minority
        class has fewer than 2 trials, else ``"success"``.
    """
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    n_per_class = np.bincount(labels.astype(int))
    max_splits = int(n_per_class.min()) if len(n_per_class) else 0
    if max_splits < 2:
        return {
            "accuracy": float("nan"),
            "fold_accuracies": np.array([]),
            "best_params": {},
            "status": "insufficient_trials_for_cv",
            "cv_scheme": "nested_stratified",
            "f1": float("nan"),
            "auc": float("nan"),
            "majority_baseline_accuracy": float("nan"),
        }

    n_outer = min(n_splits, max_splits)
    outer = StratifiedKFold(n_splits=n_outer, shuffle=True, random_state=42)
    param_grid = {"clf__C": [0.01, 0.1, 1.0, 10.0]}
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", SVC(kernel="linear", random_state=42)),
        ]
    )

    outer_scores: List[float] = []
    chosen_C: List[float] = []
    fold_majority_accs: List[float] = []
    oof_y_true: List[np.ndarray] = []
    oof_y_pred: List[np.ndarray] = []
    oof_y_score: List[np.ndarray] = []

    for train_idx, test_idx in outer.split(X, labels):
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = labels[train_idx], labels[test_idx]
        fold_majority_accs.append(fold_majority_baseline(y_train, y_test))

        inner_splits = min(3, int(np.bincount(y_train.astype(int)).min()))
        if inner_splits < 2:
            # Fall back to fixed C when inner CV is impossible
            clf = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("clf", SVC(kernel="linear", C=1.0, random_state=42)),
                ]
            )
            clf.fit(X_train, y_train)
            outer_scores.append(float(clf.score(X_test, y_test)))
            chosen_C.append(1.0)
            oof_y_true.append(y_test)
            oof_y_pred.append(clf.predict(X_test))
            oof_y_score.append(clf.decision_function(X_test))
            continue

        inner = StratifiedKFold(n_splits=inner_splits, shuffle=True, random_state=42)
        grid = GridSearchCV(pipeline, param_grid, cv=inner, scoring="accuracy")
        grid.fit(X_train, y_train)
        outer_scores.append(float(grid.score(X_test, y_test)))
        chosen_C.append(float(grid.best_params_["clf__C"]))
        oof_y_true.append(y_test)
        oof_y_pred.append(grid.predict(X_test))
        oof_y_score.append(grid.decision_function(X_test))

    # Modal best C across outer folds (reporting convenience, not re-fit score)
    values, counts = np.unique(chosen_C, return_counts=True)
    best_c = float(values[int(np.argmax(counts))])

    y_true_pooled = np.concatenate(oof_y_true)
    y_pred_pooled = np.concatenate(oof_y_pred)
    y_score_pooled = np.concatenate(oof_y_score)

    # F1/AUC require both classes present among pooled out-of-fold predictions
    # and true labels; otherwise sklearn's metrics are undefined and we report
    # NaN rather than a fabricated number.
    if len(np.unique(y_true_pooled)) < 2:
        f1 = float("nan")
        auc = float("nan")
    else:
        f1 = float(f1_score(y_true_pooled, y_pred_pooled, zero_division=0))
        try:
            auc = float(roc_auc_score(y_true_pooled, y_score_pooled))
        except ValueError:
            auc = float("nan")

    return {
        "accuracy": float(np.mean(outer_scores)),
        "fold_accuracies": np.asarray(outer_scores, dtype=float),
        "best_params": {"C": best_c},
        "status": "success",
        "cv_scheme": "nested_stratified",
        "accuracy_source": "outer_cv_mean",
        "f1": f1,
        "auc": auc,
        "majority_baseline_accuracy": float(np.mean(fold_majority_accs)),
    }
