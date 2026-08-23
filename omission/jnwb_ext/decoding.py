"""
Population Decoding using Support Vector Machines (SVM)

Provides classifiers to decode stimulus properties (identity and omission presence)
from population spike count vectors across trials.

The generic nested-CV linear-SVM decoder and its majority-baseline helpers were promoted
2026-08-23 to jnwb.decoding (99%-jnwb-sufficiency normalization) -- they took plain
(X, labels) arrays and never touched a session object, so they generalize beyond this task.
What remains here (build_spike_count_matrix, decode_stimulus_identity,
decode_omission_presence) is irreducibly coupled to OmissionSession's API and this task's
condition-pair semantics (e.g. "AAAB" vs "BBBA").

Author: Claude Code
Date: 2026-06-30
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from jnwb.decoding import majority_baseline as _majority_baseline
from jnwb.decoding import nested_cv_linear_svm as _nested_cv_linear_svm

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
