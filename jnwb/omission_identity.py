"""
Omission Identity Decoding & GLMM Encoding Engine

Provides noise-controlled, class-balanced, cross-validated classification
and GLMM feature modeling to evaluate whether and where population neural
activity (spikes) and LFP band powers encode "what was omitted?" (e.g., A in AXAB
vs. B in BXBA vs. R in RXRR).

Author: Google DeepMind Antigravity Agent
Date: 2026-08-02
"""

from __future__ import annotations

import logging
import pathlib
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

import jnwb as oa

log = logging.getLogger(__name__)

# Canonical Omission Pairs by Slot Position
OMISSION_IDENTITY_CONDITIONS = {
    "p2": {"A": "AXAB", "B": "BXBA", "R": "RXRR", "slot_onset_ms": 1031.0, "slot_end_ms": 1562.0},
    "p3": {"A": "AAXB", "B": "BBXA", "R": "RRXR", "slot_onset_ms": 2062.0, "slot_end_ms": 2593.0},
    "p4": {"A": "AAAX", "B": "BBBX", "R": "RRRX", "slot_onset_ms": 3093.0, "slot_end_ms": 3624.0},
}

LFP_BANDS = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (14.0, 30.0),
    "gamma": (30.0, 80.0),
}


def build_noise_controlled_spike_matrix(
    session,
    area: str,
    epochs_cond_a: pd.DataFrame,
    epochs_cond_b: pd.DataFrame,
    time_window_ms: Tuple[float, float],
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray, List[int]]:
    """
    Build a noise-controlled, trial-balanced spike count matrix X and label vector y.
    
    Noise Control:
    - Equalizes trial counts between Class A and Class B by downsampling to min(N_A, N_B).
    - Z-scores / standardizes features within CV folds.
    """
    n_a = len(epochs_cond_a)
    n_b = len(epochs_cond_b)
    
    if n_a == 0 or n_b == 0:
        return np.zeros((0, 0)), np.array([]), []
        
    n_min = min(n_a, n_b)
    rng = np.random.default_rng(random_state)
    
    idx_a = rng.choice(n_a, size=n_min, replace=False) if n_a > n_min else np.arange(n_a)
    idx_b = rng.choice(n_b, size=n_min, replace=False) if n_b > n_min else np.arange(n_b)
    
    sub_a = epochs_cond_a.iloc[idx_a].reset_index(drop=True)
    sub_b = epochs_cond_b.iloc[idx_b].reset_index(drop=True)
    
    epochs_df = pd.concat([sub_a, sub_b], ignore_index=True)
    labels = np.array([0] * n_min + [1] * n_min)
    
    units_df = session.get_units(area=area)
    if len(units_df) == 0:
        return np.zeros((len(labels), 0)), labels, []
        
    unit_ids = units_df["unit_id"].tolist()
    n_trials = len(labels)
    n_units = len(unit_ids)
    X = np.zeros((n_trials, n_units))
    
    win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)
    onsets = epochs_df["start_time"].values
    
    for j, u_id in enumerate(unit_ids):
        spike_times = session.get_spike_times(u_id)
        if spike_times is None or len(spike_times) == 0:
            continue
        st = np.sort(spike_times)
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
            
    return X, labels, unit_ids


def decode_omission_identity_slot(
    session,
    area: str,
    slot_key: str = "p2",
    contrast: Tuple[str, str] = ("A", "B"),
    time_window_ms: Tuple[float, float] = (1031.0, 1562.0),
    n_splits: int = 5,
    n_permutations: int = 100,
    random_state: int = 42,
) -> Dict[str, Union[float, np.ndarray, str, int]]:
    """
    Perform 5-fold cross-validated Linear SVM / Logistic Regression decoding of Omitted Identity.
    """
    cond_cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    cond_a_code = cond_cfg[contrast[0]]
    cond_b_code = cond_cfg[contrast[1]]
    
    epochs_a = session.get_epochs(condition=cond_a_code)
    epochs_b = session.get_epochs(condition=cond_b_code)
    
    X, labels, unit_ids = build_noise_controlled_spike_matrix(
        session, area, epochs_a, epochs_b, time_window_ms, random_state=random_state
    )
    
    n_units = len(unit_ids)
    n_trials = len(labels)
    
    if n_units < 2 or n_trials < 6:
        return {
            "status": "insufficient_data",
            "accuracy": float("nan"),
            "f1": float("nan"),
            "auc": float("nan"),
            "p_val": float("nan"),
            "chance_baseline": 0.50,
            "n_units": n_units,
            "n_trials": n_trials,
            "area": area,
            "slot_key": slot_key,
        }
        
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", SVC(kernel="linear", C=1.0, random_state=random_state))
    ])
    
    scores = []
    oof_y_true = []
    oof_y_pred = []
    oof_y_score = []
    
    for train_idx, test_idx in cv.split(X, labels):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = labels[train_idx], labels[test_idx]
        
        pipeline.fit(X_tr, y_tr)
        acc = pipeline.score(X_te, y_te)
        scores.append(acc)
        
        preds = pipeline.predict(X_te)
        dec_scores = pipeline.decision_function(X_te)
        
        oof_y_true.extend(y_te)
        oof_y_pred.extend(preds)
        oof_y_score.extend(dec_scores)
        
    mean_acc = float(np.mean(scores))
    f1 = float(f1_score(oof_y_true, oof_y_pred, zero_division=0))
    try:
        auc = float(roc_auc_score(oof_y_true, oof_y_score))
    except ValueError:
        auc = float("nan")
        
    # Permutation Test for null distribution
    perm_accs = []
    rng = np.random.default_rng(random_state)
    for p_i in range(n_permutations):
        perm_labels = rng.permutation(labels)
        p_scores = []
        for train_idx, test_idx in cv.split(X, perm_labels):
            pipeline.fit(X[train_idx], perm_labels[train_idx])
            p_scores.append(pipeline.score(X[test_idx], perm_labels[test_idx]))
        perm_accs.append(np.mean(p_scores))
        
    p_val = float(np.mean(np.array(perm_accs) >= mean_acc))
    if p_val == 0.0:
        p_val = 1.0 / (n_permutations + 1)
        
    return {
        "status": "success",
        "accuracy": mean_acc,
        "f1": f1,
        "auc": auc,
        "p_val": p_val,
        "chance_baseline": 0.50,
        "n_units": n_units,
        "n_trials": n_trials,
        "area": area,
        "slot_key": slot_key,
        "perm_null_mean": float(np.mean(perm_accs)),
        "perm_null_std": float(np.std(perm_accs)),
    }
