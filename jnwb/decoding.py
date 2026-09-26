"""
jnwb.decoding -- nested cross-validated linear-SVM population decoding on plain arrays.

``nested_cv_linear_svm`` and its majority-baseline helpers operate on ``(n_trials,
n_features)`` matrices and integer labels with no session object or task-specific feature
construction. Fold-partition helpers (``assign_outer_folds``,
``build_inner_validation_partitions``, ``build_representation_ladder``) operate on caller-
supplied trial tables or ``(n_trials, n_space, n_time)`` arrays. Session-bound feature
matrices and task-specific decoders belong in downstream project code.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Mapping, Union

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from sklearn.utils import check_random_state

from ._rng import DEFAULT_SEED, RNGLike, sklearn_random_state

log = logging.getLogger(__name__)


def _reject_missing_labels(labels: np.ndarray, func_name: str, name: str) -> np.ndarray:
    """A missing label is not a class, and the two baselines disagreed about it.

    ``np.unique`` collects NaNs into one group, so ``majority_baseline`` counted "missing"
    as the majority class and scored it: eight labels of which six were NaN returned 0.75.
    ``fold_majority_baseline`` selected the same NaN as the majority class and then tested
    it with ``y_test == nan``, which is False everywhere, so the same eight labels returned
    0.0. Two exported functions documenting one estimand answered 0.75 and 0.0 for the same
    input, and neither said anything.

    ``nested_cv_linear_svm`` never reached either number -- scikit-learn rejects a NaN ``y``
    first -- so this closes the direct route to a baseline computed from absent labels, and
    makes the two agree by refusing rather than by picking one of the two answers. Neither
    was right: accuracy of predicting the majority class is undefined when some labels name
    no class.
    """
    labels = np.asarray(labels)
    # Only inexact dtypes can carry NaN or infinity; object and string labels are compared
    # by equality and are left to `np.unique` exactly as before.
    if labels.dtype.kind in "fc" and not np.all(np.isfinite(labels)):
        n_missing = int(np.count_nonzero(~np.isfinite(labels)))
        raise ValueError(
            f"{func_name}: {name} contains {n_missing} non-finite label(s) of "
            f"{labels.size}. A missing label is not a class -- counting it as one scored "
            f"the absence itself. Drop those trials, or label them explicitly."
        )
    return labels


def majority_baseline(labels: np.ndarray) -> float:
    """Accuracy of always predicting the most frequent class in ``labels``.

    Raises:
        ValueError: If ``labels`` contains NaN or infinity.
    """
    labels = _reject_missing_labels(labels, "majority_baseline", "labels")
    if len(labels) == 0:
        return float("nan")
    # `np.bincount(labels.astype(int))` requires contiguous non-negative integers.
    # `np.unique` counts the classes that are present, whatever they are called, so
    # labels {1, 2}, {-1, 1} and {'a', 'b'} are counted rather than miscounted or refused.
    counts = np.unique(labels, return_counts=True)[1]
    return float(counts.max() / len(labels))


def fold_majority_baseline(y_train: np.ndarray, y_test: np.ndarray) -> float:
    """Accuracy of predicting the training-fold majority class on the held-out fold.

    Raises:
        ValueError: If either fold contains NaN or infinity.
    """
    y_train = _reject_missing_labels(y_train, "fold_majority_baseline", "y_train")
    y_test = _reject_missing_labels(y_test, "fold_majority_baseline", "y_test")
    classes, counts = np.unique(y_train, return_counts=True)
    majority_class = classes[int(np.argmax(counts))]
    return float(np.mean(y_test == majority_class))


def _group_codes(groups: np.ndarray, n_trials: int) -> np.ndarray:
    """Integer codes 0..n_groups-1 for ``groups``, after refusing ids that name no group.

    The dtype check alone missed NaN in an object array: ``np.unique`` then gave the
    NaN-bearing entries their own slots, one real group became several, and its trials
    were split across train and test while the call reported success.
    """
    groups = np.asarray(groups)
    if groups.shape != (n_trials,):
        raise ValueError(
            f"nested_cv_linear_svm: groups has shape {groups.shape}; it needs one group id "
            f"per trial, shape ({n_trials},)."
        )
    missing = np.asarray(pd.isna(groups), dtype=bool)
    if groups.dtype.kind in "fc":
        missing |= ~np.isfinite(groups)
    if missing.any():
        raise ValueError(
            f"nested_cv_linear_svm: groups contains {int(missing.sum())} missing or "
            f"non-finite id(s). A missing group id is not a group; label those trials "
            f"explicitly or drop them."
        )
    try:
        codes = np.unique(groups, return_inverse=True)[1]
    except TypeError as exc:
        raise ValueError(
            "nested_cv_linear_svm: groups mixes ids that cannot be compared with each "
            "other (for example numbers and strings); use one type of id."
        ) from exc
    return np.asarray(codes, dtype=np.intp).reshape(n_trials)


def _grouped_splits(
    X: np.ndarray, y: np.ndarray, codes: np.ndarray, n_splits: int, random_state
) -> list:
    """``StratifiedGroupKFold`` folds with the group order drawn from ``random_state``.

    ``StratifiedGroupKFold(shuffle=True)`` before scikit-learn 1.8 shuffles the per-group
    class counts without the matching group ids, so its folds are neither stratified nor
    the groups it reports on. Relabelling the groups with a random permutation and
    splitting unshuffled gives the randomized tie-breaking ``shuffle`` intends, on every
    supported version.
    """
    uniq, dense = np.unique(codes, return_inverse=True)
    perm = check_random_state(random_state).permutation(len(uniq))
    relabelled = perm[dense.reshape(-1)]
    return list(StratifiedGroupKFold(n_splits=n_splits, shuffle=False).split(X, y, relabelled))


def _single_class_error(fold: str, y_train: np.ndarray, classes: np.ndarray) -> ValueError:
    missing = sorted(set(classes.tolist()) - set(np.unique(y_train).tolist()))
    return ValueError(
        f"nested_cv_linear_svm: the grouped {fold} training set holds no trial of class "
        f"{missing}, because every group carrying that class is held out together. "
        f"Decoding across groups needs each class in at least two groups."
    )


def nested_cv_linear_svm(
    X: np.ndarray,
    labels: np.ndarray,
    n_splits: int,
    rng: RNGLike = DEFAULT_SEED,
    *,
    groups: Union[np.ndarray, None] = None,
) -> Dict[str, Union[float, np.ndarray, dict, str]]:
    """Outer stratified CV; inner GridSearchCV for C. No synthetic metrics.

    In addition to mean outer-fold accuracy, pools out-of-fold predictions and
    decision scores across all outer folds to report a single F1 score and
    ROC-AUC, plus a per-fold majority-class baseline accuracy (mean across
    folds) so callers can check whether the classifier beats chance/imbalance
    on the same splits used for accuracy.

    Args:
        X: (n_trials, n_features) feature matrix.
        labels: (n_trials,) class labels, two classes. Any dtype whose values
            ``np.unique`` can group -- integers need be neither contiguous nor
            non-negative, and strings work.
        n_splits: requested number of outer folds; clipped to the minority
            class count when there are too few trials per class, and with
            ``groups`` also to the number of distinct groups.
        groups: optional (n_trials,) group ids (block, cycle, session) of one
            comparable type, none missing. When given, outer folds are
            ``StratifiedGroupKFold`` over the groups in an order drawn from
            ``rng``: every group's trials land in one test fold, and class
            balance across folds is kept as far as the groups allow. The inner search for C is grouped
            the same way within each outer training set, and falls back to
            ``C=1.0`` when that set has fewer than two groups or an inner
            training split would hold one class. ``None`` (the default) gives
            row-wise ``StratifiedKFold`` folds, unchanged.

    Returns:
        dict with accuracy, fold_accuracies, best_params, status, cv_scheme,
        f1, auc, majority_baseline_accuracy. ``status`` is
        ``"insufficient_trials_for_cv"`` (all metrics NaN) when the minority
        class has fewer than 2 trials, ``"insufficient_classes_for_cv"`` when
        fewer than two distinct labels are present,
        ``"insufficient_groups_for_cv"`` when ``groups`` names fewer than two
        groups, else ``"success"``. ``cv_scheme`` is ``"nested_stratified"``,
        or ``"nested_stratified_group"`` with ``groups``.

    Raises:
        ValueError: If ``groups`` is not one id per trial, has a missing or
            non-finite id, mixes ids that cannot be compared, or if a grouped
            outer training set holds a single class.
    """
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels)
    grouped = groups is not None
    cv_scheme = "nested_stratified_group" if grouped else "nested_stratified"
    if grouped:
        groups = _group_codes(groups, len(labels))
        n_groups = len(np.unique(groups))
        if n_groups < 2:
            return {
                "accuracy": float("nan"),
                "fold_accuracies": np.array([]),
                "best_params": {},
                "status": "insufficient_groups_for_cv",
                "cv_scheme": cv_scheme,
                "f1": float("nan"),
                "auc": float("nan"),
                "majority_baseline_accuracy": float("nan"),
            }
    # This was `np.bincount(labels.astype(int)).min()`, which counts every integer
    # below the maximum as a class -- including ones that are absent. Labels {1, 2} scored
    # a class of size 0 and returned `status="insufficient_trials_for_cv"` for 20
    # separable trials per class; {-1, 1} and {'a', 'b'} raised out of `bincount` and
    # `int()`. `status` is a claim about the data, so it must not be one bincount made up.
    classes, n_per_class = np.unique(labels, return_counts=True)
    if len(classes) < 2:
        return {
            "accuracy": float("nan"),
            "fold_accuracies": np.array([]),
            "best_params": {},
            "status": "insufficient_classes_for_cv",
            "cv_scheme": cv_scheme,
            "f1": float("nan"),
            "auc": float("nan"),
            "majority_baseline_accuracy": float("nan"),
        }
    max_splits = int(n_per_class.min())
    if max_splits < 2:
        return {
            "accuracy": float("nan"),
            "fold_accuracies": np.array([]),
            "best_params": {},
            "status": "insufficient_trials_for_cv",
            "cv_scheme": cv_scheme,
            "f1": float("nan"),
            "auc": float("nan"),
            "majority_baseline_accuracy": float("nan"),
        }

    # The partition was fixed at `random_state=42` in four places with no way to
    # vary it, so partition sensitivity could not be assessed at all. An int `rng` is
    # handed to scikit-learn unchanged, so the default reproduces the old folds exactly.
    random_state = sklearn_random_state(rng, func_name="nested_cv_linear_svm")

    if grouped:
        # StratifiedGroupKFold rather than GroupKFold: group integrity is the hard
        # constraint, and it still keeps the class balance the ungrouped folds give,
        # as far as the groups allow. The fold count cannot exceed the group count, and
        # is clipped to the minority-class count exactly as the ungrouped folds are.
        n_outer = min(n_splits, max_splits, n_groups)
        outer_splits = _grouped_splits(X, labels, groups, n_outer, random_state)
    else:
        n_outer = min(n_splits, max_splits)
        outer = StratifiedKFold(n_splits=n_outer, shuffle=True, random_state=random_state)
        outer_splits = outer.split(X, labels)
    param_grid = {"clf__C": [0.01, 0.1, 1.0, 10.0]}
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", SVC(kernel="linear", random_state=random_state)),
        ]
    )

    outer_scores: List[float] = []
    chosen_C: List[float] = []
    fold_majority_accs: List[float] = []
    oof_y_true: List[np.ndarray] = []
    oof_y_pred: List[np.ndarray] = []
    oof_y_score: List[np.ndarray] = []

    for train_idx, test_idx in outer_splits:
        X_train, X_test = X[train_idx], X[test_idx]
        y_train, y_test = labels[train_idx], labels[test_idx]
        if grouped and len(np.unique(y_train)) < 2:
            raise _single_class_error("outer", y_train, classes)
        fold_majority_accs.append(fold_majority_baseline(y_train, y_test))

        inner_splits = min(3, int(np.unique(y_train, return_counts=True)[1].min()))
        inner_cv = None
        if grouped:
            # The inner search holds out groups too, so C is chosen for transfer to an
            # unseen group rather than to a neighbouring trial of a seen one.
            g_train = groups[train_idx]
            inner_splits = min(inner_splits, len(np.unique(g_train)))
            if inner_splits >= 2:
                inner_cv = _grouped_splits(
                    X_train, y_train, g_train, inner_splits, random_state
                )
                if any(len(np.unique(y_train[i_tr])) < 2 for i_tr, _ in inner_cv):
                    inner_splits = 1
        if inner_splits < 2:
            # Fall back to fixed C when inner CV is impossible
            clf = Pipeline(
                [
                    ("scaler", StandardScaler()),
                    ("clf", SVC(kernel="linear", C=1.0, random_state=random_state)),
                ]
            )
            clf.fit(X_train, y_train)
            outer_scores.append(float(clf.score(X_test, y_test)))
            chosen_C.append(1.0)
            oof_y_true.append(y_test)
            oof_y_pred.append(clf.predict(X_test))
            oof_y_score.append(clf.decision_function(X_test))
            continue

        if inner_cv is None:
            inner_cv = StratifiedKFold(
                n_splits=inner_splits, shuffle=True, random_state=random_state
            )
        grid = GridSearchCV(pipeline, param_grid, cv=inner_cv, scoring="accuracy")
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
        # Both metrics were left to sklearn's `pos_label=1` default, which is a
        # different class depending on what the classes are called. Labels {0, 1} scored
        # f1 = 0.8571 and the same trials relabelled {1, 2} scored 0.8421, because 1 is
        # the higher class in one and the lower in the other; labels {0, 2} and
        # {'a', 'b'} raised `pos_label=1 is not a valid label`, and the bare
        # `except ValueError` turned that into a NaN AUC for a value that is perfectly
        # computable. The positive class is `classes[1]` -- the second in sorted order,
        # which is also the class `decision_function` scores toward, since sklearn sorts
        # `clf.classes_`. So the metrics now depend on the data, not on the names.
        positive = classes[1]
        y_true_bin = (y_true_pooled == positive).astype(int)
        y_pred_bin = (y_pred_pooled == positive).astype(int)
        f1 = float(f1_score(y_true_bin, y_pred_bin, zero_division=0))
        auc = float(roc_auc_score(y_true_bin, y_score_pooled))

    return {
        "accuracy": float(np.mean(outer_scores)),
        "fold_accuracies": np.asarray(outer_scores, dtype=float),
        "best_params": {"C": best_c},
        "status": "success",
        "cv_scheme": cv_scheme,
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
                            # These were `int(...)`. `assign_outer_folds` accepts
                            # string group ids and reports `outer_fold_status="valid"`,
                            # and then its own documented successor raised
                            # `invalid literal for int() with base 10: 'c2'` on that
                            # output. The group id is an opaque label, not a number.
                            "inner_group": inner_group,
                            "trial_group": trial["outer_group"],
                            "validation_group": inner_group,
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
