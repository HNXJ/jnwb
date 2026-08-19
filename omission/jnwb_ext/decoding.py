"""
Population Decoding using Support Vector Machines (SVM)

Provides classifiers to decode stimulus properties (identity and omission presence)
from population spike count vectors across trials.

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

log = logging.getLogger(__name__)


def build_spike_count_matrix(
    session,
    area: str,
    epochs_df: pd.DataFrame,
    time_window_ms: Tuple[float, float] = (0.0, 150.0),
    quality: Optional[str] = None,
) -> Tuple[np.ndarray, List[int]]:
    """
    Build a trial-by-trial population spike count matrix.

    Args:
        session: OmissionSession object
        area: Brain area to select units from
        epochs_df: DataFrame of trials/epochs (must have 'start_time')
        time_window_ms: (start_ms, end_ms) relative to epoch onset
        quality: Filter units by quality tier ('stable_plus', 'stable', etc.)

    Returns:
        X: Feature matrix of shape (n_trials, n_units)
        unit_ids: List of unit IDs represented in the columns of X
    """
    units_df = session.get_units(quality=quality, area=area)
    if len(units_df) == 0:
        log.warning(f"No units found in area {area}")
        return np.zeros((len(epochs_df), 0)), []

    unit_ids = units_df["unit_id"].tolist()
    n_trials = len(epochs_df)
    n_units = len(unit_ids)
    X = np.zeros((n_trials, n_units))

    win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)
    onsets = epochs_df["start_time"].values

    for j, unit_id in enumerate(unit_ids):
        spike_times = session.get_spike_times(unit_id)
        if len(spike_times) == 0:
            continue
        st = np.sort(spike_times)
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo

    return X, unit_ids


def _majority_baseline(labels: np.ndarray) -> float:
    if len(labels) == 0:
        return float("nan")
    counts = np.bincount(labels.astype(int))
    return float(counts.max() / len(labels))


def _fold_majority_baseline(y_train: np.ndarray, y_test: np.ndarray) -> float:
    """Accuracy of predicting the training-fold majority class on the held-out fold."""
    counts = np.bincount(y_train.astype(int))
    majority_class = int(np.argmax(counts))
    return float(np.mean(y_test.astype(int) == majority_class))


def _nested_cv_linear_svm(
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
    """
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
        fold_majority_accs.append(_fold_majority_baseline(y_train, y_test))

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


def decode_stimulus_identity(
    session,
    area: str,
    condition_pairs: Tuple[str, str] = ("AAAB", "BBBA"),
    time_window_ms: Tuple[float, float] = (0.0, 150.0),
    baseline_window_ms: Optional[Tuple[float, float]] = None,
    n_splits: int = 5,
    quality: Optional[str] = None,
    device: str = "cpu",
) -> Dict[str, Union[float, str, np.ndarray, dict]]:
    """
    Decode stimulus identity (Condition A vs. Condition B) from population activity.

    Returns NaN accuracy with status ``insufficient_trials`` when either class has
    fewer than 2 trials. Never fabricates performance metrics.

    CPU path uses nested stratified CV (outer eval / inner C tuning).
    ``device='cuda'`` currently falls back to the same nested CPU path (GPU hinge
    GD without convergence criteria is not used for reported accuracy).

    Returns a dict with (at minimum) the following keys:
        accuracy: mean outer-fold accuracy (NaN if CV could not run).
        fold_accuracies: per-outer-fold accuracy array.
        f1: F1 score computed on pooled out-of-fold predictions across all outer
            folds (NaN if fewer than 2 classes are present in the pooled labels
            or predictions, e.g. insufficient trials).
        auc: ROC-AUC computed on pooled out-of-fold decision-function scores
            across all outer folds (NaN under the same degenerate conditions
            as ``f1``).
        majority_baseline_accuracy: mean, across outer folds, of the accuracy a
            trivial classifier would get by always predicting the training
            fold's majority class on the held-out fold. Compare directly
            against ``accuracy`` to check whether the classifier beats
            chance/imbalance rather than just tracking class proportions.
        majority_baseline: the majority-class fraction over the full label set
            (dataset-level; distinct from the per-fold ``majority_baseline_accuracy``).
        n_units, n_trials, n_per_class, best_params, status, cv_scheme: as before.
    """
    epochs_cond1 = session.get_epochs(phase=2, condition=condition_pairs[0])
    epochs_cond2 = session.get_epochs(phase=2, condition=condition_pairs[1])

    n1, n2 = len(epochs_cond1), len(epochs_cond2)
    n_per_class = {condition_pairs[0]: int(n1), condition_pairs[1]: int(n2)}

    if n1 < 2 or n2 < 2:
        log.warning(
            "Insufficient trials for decoding (%s=%d, %s=%d); returning NaN.",
            condition_pairs[0],
            n1,
            condition_pairs[1],
            n2,
        )
        return {
            "accuracy": float("nan"),
            "fold_accuracies": np.array([]),
            "n_units": 0,
            "n_trials": int(n1 + n2),
            "n_per_class": n_per_class,
            "majority_baseline": float("nan"),
            "best_params": {},
            "status": "insufficient_trials",
            "cv_scheme": None,
            "f1": float("nan"),
            "auc": float("nan"),
            "majority_baseline_accuracy": float("nan"),
        }

    epochs_df = pd.concat([epochs_cond1, epochs_cond2], ignore_index=True)
    labels = np.array([0] * n1 + [1] * n2)
    majority = _majority_baseline(labels)

    X, unit_ids = build_spike_count_matrix(session, area, epochs_df, time_window_ms, quality)
    if baseline_window_ms is not None:
        X_base, _ = build_spike_count_matrix(
            session, area, epochs_df, baseline_window_ms, quality
        )
        X = X - X_base
    n_units = len(unit_ids)

    if n_units == 0:
        return {
            "accuracy": float("nan"),
            "fold_accuracies": np.array([]),
            "n_units": 0,
            "n_trials": len(labels),
            "n_per_class": n_per_class,
            "majority_baseline": majority,
            "best_params": {},
            "status": "no_units",
            "cv_scheme": None,
            "f1": float("nan"),
            "auc": float("nan"),
            "majority_baseline_accuracy": majority,
        }

    if device == "cuda":
        log.info(
            "device='cuda' requested; using nested CPU LinearSVC path for reported "
            "accuracy (GPU hinge GD without convergence is disabled)."
        )

    nested = _nested_cv_linear_svm(X, labels, n_splits=n_splits)
    nested.update(
        {
            "n_units": n_units,
            "n_trials": len(labels),
            "n_per_class": n_per_class,
            "majority_baseline": majority,
        }
    )
    return nested


def decode_omission_presence(
    session,
    area: str,
    standard_condition: str = "AAAB",
    omission_condition: str = "AAXB",
    time_window_ms: Tuple[float, float] = (0.0, 150.0),
    baseline_window_ms: Optional[Tuple[float, float]] = None,
    n_splits: int = 5,
    quality: Optional[str] = None,
    device: str = "cpu",
) -> Dict[str, Union[float, str, np.ndarray]]:
    """
    Decode omission presence (Standard tone vs. Omission trial) from population activity.

    Thin wrapper around :func:`decode_stimulus_identity`; returns the same dict
    shape, including the ``f1``, ``auc``, and ``majority_baseline_accuracy``
    keys documented there.
    """
    return decode_stimulus_identity(
        session=session,
        area=area,
        condition_pairs=(standard_condition, omission_condition),
        time_window_ms=time_window_ms,
        baseline_window_ms=baseline_window_ms,
        n_splits=n_splits,
        quality=quality,
        device=device,
    )
