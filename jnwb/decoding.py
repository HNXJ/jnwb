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

PROMOTED 2026-08-23 (same normalization pass) from omission.jnwb_ext.structured_identity:
``assign_outer_folds``, ``build_inner_validation_partitions``, and ``build_representation_ladder``
operate on a plain trial DataFrame (grouped by caller-supplied ``analysis_cols``/``group_col``)
or a plain ``(n_trials, n_space, n_time)`` array -- no reference to omission's condition codes,
sequence semantics, or session objects. They generalize to any grouped leave-one-group-out CV
geometry / representation-contract problem. ``build_canonical_trial_table``,
``build_milestone_receipt``, and the positive-control row builders stay in
omission.jnwb_ext.structured_identity: they are irreducibly coupled to this task's trial
ontology and condition semantics.

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Mapping, Union

import numpy as np
import pandas as pd
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


def assign_outer_folds(
    trials: pd.DataFrame,
    *,
    analysis_cols: tuple = ("session", "analysis", "slot_key"),
    group_col: str = "cycle",
) -> pd.DataFrame:
    """Assign deterministic leave-one-group-out outer folds without touching features.

    Args:
        trials: DataFrame with at least ``analysis_cols``, ``group_col``, and ``trial_id``
            columns.
        analysis_cols: columns identifying an independent analysis stratum (folds are assigned
            separately within each combination of these columns).
        group_col: column giving the group id (e.g. a repetition/cycle id) that outer folds hold
            out whole groups of.

    Returns:
        A copy of ``trials`` with added ``outer_fold`` (int, -1 if unassigned),
        ``outer_group`` (the group id), and ``outer_fold_status`` (``"valid"`` or
        ``"insufficient_groups"`` when a stratum has fewer than 2 distinct groups).
    """
    required = set(analysis_cols) | {group_col, "trial_id"}
    missing = required.difference(trials.columns)
    if missing:
        raise ValueError(f"trial table missing fold columns: {sorted(missing)}")
    out = trials.copy()
    out["outer_fold"] = -1
    out["outer_group"] = out[group_col]
    out["outer_fold_status"] = "unassigned"
    for _, index in out.groupby(list(analysis_cols), sort=True, dropna=False).groups.items():
        groups = sorted(out.loc[index, group_col].unique().tolist())
        if len(groups) < 2:
            out.loc[index, "outer_fold_status"] = "insufficient_groups"
            continue
        mapping = {group: fold for fold, group in enumerate(groups)}
        out.loc[index, "outer_fold"] = out.loc[index, group_col].map(mapping).astype(int)
        out.loc[index, "outer_fold_status"] = "valid"
    return out


def build_inner_validation_partitions(
    outer_trials: pd.DataFrame,
    *,
    analysis_cols: tuple = ("session", "analysis", "slot_key"),
) -> pd.DataFrame:
    """Build nested inner train/validation partitions from outer-training groups.

    The outer test group is never used in an inner partition. If only one training group
    remains, an explicit ``"insufficient_training_groups"`` row is emitted instead of inventing
    a validation split.

    Args:
        outer_trials: output of ``assign_outer_folds`` (must have ``outer_fold``,
            ``outer_group``, ``trial_id``, and ``analysis_cols`` columns).
        analysis_cols: columns identifying an independent analysis stratum.

    Returns:
        Long-format DataFrame, one row per (stratum, outer_fold, inner_fold, trial_id), with
        ``inner_role`` in {"inner_train", "inner_validation", "insufficient_training_groups"}.
    """
    rows: list = []
    for key, group in outer_trials.groupby(list(analysis_cols), sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        key_values = dict(zip(analysis_cols, key))
        for outer_fold in sorted(group["outer_fold"].unique()):
            train = group[group["outer_fold"] != outer_fold]
            train_groups = sorted(train["outer_group"].unique().tolist())
            if len(train_groups) < 2:
                rows.append(
                    {
                        **key_values,
                        "outer_fold": int(outer_fold),
                        "inner_fold": -1,
                        "trial_id": -1,
                        "inner_role": "insufficient_training_groups",
                        "inner_group": None,
                        "trial_group": None,
                        "validation_group": None,
                    }
                )
                continue
            for inner_fold, inner_group in enumerate(train_groups):
                for _, trial in train.iterrows():
                    rows.append(
                        {
                            **key_values,
                            "outer_fold": int(outer_fold),
                            "inner_fold": int(inner_fold),
                            "trial_id": int(trial["trial_id"]),
                            "inner_role": (
                                "inner_validation"
                                if trial["outer_group"] == inner_group
                                else "inner_train"
                            ),
                            "inner_group": int(inner_group),
                            "trial_group": int(trial["outer_group"]),
                            "validation_group": int(inner_group),
                        }
                    )
    return pd.DataFrame(rows)


def build_representation_ladder(
    raster: np.ndarray,
    *,
    modality: str = "SPK",
    spatial_axis_metadata: Union[Mapping[str, object], None] = None,
) -> Dict[str, object]:
    """Return R0/R1/R2 representation contracts without fitting a model.

    ``raster`` is ``(n_trials, n_space, n_time)`` with an explicit time axis. R0 collapses
    time; R1 vectorizes without discarding samples; R2 preserves the tensor and records the
    space-axis topology constraint. SPK units are unordered unless metadata supplies a
    preregistered order.

    Args:
        raster: (n_trials, n_space, n_time) finite array.
        modality: "SPK" or "LFP".
        spatial_axis_metadata: required when modality="LFP" (explicit channel/probe topology);
            optional for "SPK".

    Returns:
        dict with X_rate, X_vec, X_structured, and a ``contract`` sub-dict documenting the
        R0/R1/R2 semantics and space-axis topology.
    """
    x = np.asarray(raster)
    if x.ndim != 3:
        raise ValueError("raster must have shape (n_trials, n_space, n_time)")
    if not np.isfinite(x).all():
        raise ValueError("raster contains NaN or Inf")
    modality = modality.upper()
    if modality not in {"SPK", "LFP"}:
        raise ValueError("modality must be 'SPK' or 'LFP'")
    if modality == "LFP" and spatial_axis_metadata is None:
        raise ValueError("LFP R2 requires explicit channel/probe spatial metadata")
    if modality == "SPK":
        topology = (
            "metadata_ordered_units"
            if spatial_axis_metadata is not None
            else "unordered_units_permutation_equivariant_required"
        )
    else:
        topology = "channel_probe_order_from_metadata"
    return {
        "X_rate": np.mean(x, axis=2, dtype=np.float64),
        "X_vec": x.reshape(x.shape[0], -1),
        "X_structured": x.copy(),
        "contract": {
            "modality": modality,
            "input_shape": list(x.shape),
            "r0": "X_rate: temporal aggregation; information may be discarded",
            "r1": "X_vec: bijective vectorization of the selected raster",
            "r2": "X_structured: preserved space x time organization",
            "space_axis_topology": topology,
            "vectorization_order": "C: space-major then time within each trial",
            "dtype": str(x.dtype),
            "training_authorized": False,
        },
    }
