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

import omission as oa
from jnwb.permutation import permute_labels

log = logging.getLogger(__name__)

# Canonical Omission Pairs by Slot Position
OMISSION_IDENTITY_CONDITIONS = {
    "p2": {"A": "AXAB", "B": "BXBA", "R": "RXRR", "slot_onset_ms": 1031.0, "slot_end_ms": 1562.0},
    "p3": {"A": "AAXB", "B": "BBXA", "R": "RRXR", "slot_onset_ms": 2062.0, "slot_end_ms": 2593.0},
    # 2026-08-06 BUG FIX: p4's A/B were swapped. AAAX's parent sequence is AAAB (p1=A,p2=A,p3=A,
    # p4=B) -- omitting p4 hides a B, not an A. BBBX's parent is BBBA (p4=A) -- omitting p4
    # hides an A. Verified against every other slot's own parent-sequence semantics (p2/p3 were
    # already correct: AXAB's parent AAAB has p2=A; AAXB's parent AAAB has p3=A) before fixing.
    # Every p4-specific number computed before this fix (v1/v2 slot-decode tables, the single-
    # session step2 script) used the wrong ground-truth label at p4 and must be treated as
    # unreliable until rerun; p2 (this week's headline slot) was never affected.
    "p4": {"A": "BBBX", "B": "AAAX", "R": "RRRX", "slot_onset_ms": 3093.0, "slot_end_ms": 3624.0},
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

    # Identity convention (jnwb/session.py's get_spike_times, jnwb/trajectory.py,
    # jnwb/unit_classification.py, jnwb/structured_identity_m2a.py): unit identity is the raw
    # units_df ROW POSITION, not the per-probe-local 'unit_id'/'cluster_id' column -- the
    # column can have gaps relative to row position (filtered kilosort clusters), and
    # get_spike_times's primary lookup is by row position, so a column value that happens to
    # equal another row's position silently returns that OTHER unit's real spike train.
    # Confirmed on sub-C31o_ses-230816_rec (see trajectory.py). This module used the column
    # here until 2026-08-15 -- fixed to match the established convention.
    unit_ids = units_df.index.tolist()
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

    scientific_status = "invalid_for_inference"  (audit 2026-08-10, agent-harness-audit-20260810.json)
    reason = ["ungrouped_cv"]  -- StratifiedKFold(shuffle=True) below does not respect the
        repeated-cycle structure in this corpus; same-cycle trials can land in both train and
        test. Only live callers are the quarantined scripts/historical/confounded/
        compute_omission_identity_encoding{,_v2}.py. Use
        scripts/compute_omission_identity_leakage_safe.py for current inference.
    """
    cond_cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    cond_a_code = cond_cfg[contrast[0]]
    cond_b_code = cond_cfg[contrast[1]]
    
    epochs_a = session.get_epochs(phase=2, condition=cond_a_code)
    epochs_b = session.get_epochs(phase=2, condition=cond_b_code)
    
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
        
    # Permutation Test for null distribution. scheme="global" here matches this function's own
    # ungrouped CV above (self-consistent, but see the invalid_for_inference docstring note --
    # the fold scheme itself is the problem, not this null).
    perm_accs = []
    rng = np.random.default_rng(random_state)
    for p_i in range(n_permutations):
        perm_labels = permute_labels(labels, scheme="global", rng=rng)
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


# ---------------------------------------------------------------------------
# 2026-08-06 additions (Figure 4 redesign). Additive only -- nothing above this
# line is modified, so any existing caller of decode_omission_identity_slot /
# build_noise_controlled_spike_matrix is unaffected.
#
# CONTEXT: task_block_number is perfectly confounded with condition identity in
# this design (every session presents AXAB/BXBA/RXRR as one whole, separate,
# contiguous block each -- verified empirically across 5 sessions, never
# interleaved). That makes the literal "block" nuisance variable / block-CV
# unusable: block IS the label. Per explicit direction, "block" below means a
# SUB-block temporal split within each condition's own trial run (quartiles by
# trial order), not task_block_number itself -- this is buildable and answers
# the same underlying question (does the decode survive/generalize across
# within-block time, and does within-block position alone look decodable).
# ---------------------------------------------------------------------------

from sklearn.linear_model import LogisticRegression as _LogisticRegression  # noqa: E402
from sklearn.metrics import accuracy_score as _accuracy_score  # noqa: E402


def detect_trial_cycles(epochs_df: pd.DataFrame, gap_factor: float = 10.0) -> np.ndarray:
    """REAL temporal cycle detection, added 2026-08-06 after a correction: the whole
    A-supergroup/B-supergroup/R-supergroup block-order confound documented above is real, but
    each condition's trials are NOT one single contiguous block -- verified directly against
    trial start_time gaps that each condition (AXAB/BXBA/RXRR, and likewise at p3/p4) actually
    occurs in ~3 widely-separated temporal clusters per session (median inter-trial gap ~60-130s,
    but 2-3 gaps of 3000-4400s -- the whole 5-condition micro-order repeats roughly 3 times
    across the session). `task_block_number` reuses the same integer label across all 3 repeats,
    which is why checking only its unique value (done earlier, before this correction) wrongly
    looked like one contiguous block. This function finds the real cluster boundaries via a
    gap-threshold on sorted start_time and returns a 0-indexed cycle id per trial (in the
    original row order of epochs_df, not sorted order)."""
    order = np.argsort(epochs_df["start_time"].values)
    t_sorted = epochs_df["start_time"].values[order]
    gaps = np.diff(t_sorted)
    thresh = gap_factor * np.median(gaps) if len(gaps) else np.inf
    breaks = np.where(gaps > thresh)[0]
    cycle_sorted = np.zeros(len(t_sorted), dtype=int)
    for b in breaks:
        cycle_sorted[b + 1:] += 1
    cycle = np.empty(len(order), dtype=int)
    cycle[order] = cycle_sorted
    return cycle


def assign_subblock_quartiles(epochs_df: pd.DataFrame, n_quantiles: int = 4) -> np.ndarray:
    """Assign each trial in epochs_df (already filtered to one condition) a quartile
    index 0..n_quantiles-1 by its own start_time order. This is the SUB-BLOCK unit
    used everywhere below as the stand-in for "block", since the real task_block_number
    is perfectly confounded with condition (see module note above)."""
    order = np.argsort(epochs_df["start_time"].values)
    n = len(order)
    q = np.empty(n, dtype=int)
    edges = np.linspace(0, n, n_quantiles + 1).astype(int)
    for k in range(n_quantiles):
        q[order[edges[k]:edges[k + 1]]] = k
    return q


def build_noise_controlled_spike_matrix_with_subblocks(
    session, area: str, epochs_cond_a: pd.DataFrame, epochs_cond_b: pd.DataFrame,
    time_window_ms: Tuple[float, float], n_quantiles: int = 4, random_state: int = 42,
):
    """Same trial-balancing as build_noise_controlled_spike_matrix, but also returns a
    per-trial sub-block quartile label (computed on each condition's OWN trial order
    before downsampling, then carried through the same subsample index)."""
    n_a, n_b = len(epochs_cond_a), len(epochs_cond_b)
    if n_a == 0 or n_b == 0:
        return np.zeros((0, 0)), np.array([]), [], np.array([])
    q_a_full = assign_subblock_quartiles(epochs_cond_a, n_quantiles)
    q_b_full = assign_subblock_quartiles(epochs_cond_b, n_quantiles)

    n_min = min(n_a, n_b)
    rng = np.random.default_rng(random_state)
    idx_a = rng.choice(n_a, size=n_min, replace=False) if n_a > n_min else np.arange(n_a)
    idx_b = rng.choice(n_b, size=n_min, replace=False) if n_b > n_min else np.arange(n_b)

    sub_a = epochs_cond_a.iloc[idx_a].reset_index(drop=True)
    sub_b = epochs_cond_b.iloc[idx_b].reset_index(drop=True)
    epochs_df = pd.concat([sub_a, sub_b], ignore_index=True)
    labels = np.array([0] * n_min + [1] * n_min)
    quartiles = np.concatenate([q_a_full[idx_a], q_b_full[idx_b]])

    units_df = session.get_units(area=area)
    if len(units_df) == 0:
        return np.zeros((len(labels), 0)), labels, [], quartiles
    # See build_noise_controlled_spike_matrix above: identity is row position, not the
    # 'unit_id' column.
    unit_ids = units_df.index.tolist()
    n_trials, n_units = len(labels), len(unit_ids)
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
    return X, labels, unit_ids, quartiles


def decode_omission_identity_full(
    session, area: str, slot_key: str = "p2", contrast: Tuple[str, str] = ("A", "B"),
    time_window_ms: Tuple[float, float] = (1031.0, 1562.0), n_splits: int = 5,
    n_permutations: int = 100, n_quantiles: int = 4, random_state: int = 42,
) -> Dict[str, Union[float, np.ndarray, str, int]]:
    """Extends decode_omission_identity_slot with everything requested for the fig04
    redesign, all scoped to ONE (session, area, slot):
      - X|A, X|B: same 5-fold random-subsample CV as the original function.
      - X|R: the classifier is refit on ALL A/B trials (post class-balancing), then
        applied to every available R-condition trial at the same window/units. Reports
        the fraction predicted "B" with an EXACT binomial (Clopper-Pearson) 95% CI
        against the 0.5/0.5 null this project's own doctrine prefers over a shuffle CI
        for a proportion built from counts.
      - Sub-block LOO: leave-one-quartile-out CV (4 folds, by within-condition trial
        order) as the second CV scheme, alongside the random-subsample one above --
        answers whether the decode generalizes across within-block time.
      - Sub-block (quartile) decodability: can quartile ID itself (0..3, i.e. "early or
        late in this condition's block") be decoded from the SAME features, regardless
        of A/B identity? A strong positive here is the disqualifying confound this
        redesign was built to check for (see decode_omission_identity_full's caller /
        REVISION_PLAN.md).
      - Per-trial decision-function scores are returned (OOF, random-CV) for the pooled
        mixed-effect model and R2-shuffle-CI steps computed at the corpus level, not
        per-cell (see fit_pooled_block_glmm / shuffle_r2_ci below).

    scientific_status = "invalid_for_inference"  (audit 2026-08-10, agent-harness-audit-20260810.json)
    reason = ["ungrouped_cv"]  -- the "random-subsample CV" scheme here is the same
        StratifiedKFold(shuffle=True)-family ungrouped split as decode_omission_identity_slot;
        the sub-block/quartile LOO scheme is a within-condition quartile split, not the real
        temporal-cycle grouping later found in detect_trial_cycles. Only live caller is
        scripts/historical/confounded/compute_omission_identity_encoding_v2.py. Use
        scripts/compute_omission_identity_leakage_safe.py for current inference.
    """
    cond_cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    cond_a_code, cond_b_code, cond_r_code = (cond_cfg[contrast[0]], cond_cfg[contrast[1]],
                                              cond_cfg.get("R"))
    epochs_a = session.get_epochs(phase=2, condition=cond_a_code)
    epochs_b = session.get_epochs(phase=2, condition=cond_b_code)

    X, labels, unit_ids, quartiles = build_noise_controlled_spike_matrix_with_subblocks(
        session, area, epochs_a, epochs_b, time_window_ms, n_quantiles=n_quantiles,
        random_state=random_state,
    )
    n_units, n_trials = len(unit_ids), len(labels)
    base = {"area": area, "slot_key": slot_key, "n_units": n_units, "n_trials": n_trials}
    if n_units < 2 or n_trials < 6:
        return {**base, "status": "insufficient_data"}

    scaler_pipe = lambda: Pipeline([("scaler", StandardScaler()),
                                     ("clf", SVC(kernel="linear", C=1.0, random_state=random_state))])

    # -- Random-subsample CV (X|A vs X|B), OOF scores kept for the pooled GLMM/R2 steps --
    cv_rand = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    rand_accs, oof_true, oof_score, oof_quartile = [], [], [], []
    for tr, te in cv_rand.split(X, labels):
        p = scaler_pipe()
        p.fit(X[tr], labels[tr])
        rand_accs.append(p.score(X[te], labels[te]))
        oof_true.extend(labels[te])
        oof_score.extend(p.decision_function(X[te]))
        oof_quartile.extend(quartiles[te])
    acc_random = float(np.mean(rand_accs))

    # -- Sub-block leave-one-quartile-out CV --
    subblock_accs = []
    for k in sorted(set(quartiles.tolist())):
        te = np.where(quartiles == k)[0]
        tr = np.where(quartiles != k)[0]
        if len(set(labels[te].tolist())) < 1 or len(set(labels[tr].tolist())) < 2 or len(te) < 2:
            continue
        p = scaler_pipe()
        p.fit(X[tr], labels[tr])
        subblock_accs.append(p.score(X[te], labels[te]))
    acc_subblock_loo = float(np.mean(subblock_accs)) if subblock_accs else float("nan")

    # -- Permutation null for the random-CV accuracy (unchanged design from the
    #    original function, kept as the headline significance test) --
    rng = np.random.default_rng(random_state)
    perm_accs = []
    for _ in range(n_permutations):
        perm_labels = permute_labels(labels, scheme="global", rng=rng)
        p_scores = [
            (lambda p_, tr_, te_: (p_.fit(X[tr_], perm_labels[tr_]), p_.score(X[te_], perm_labels[te_]))[1])(
                scaler_pipe(), tr, te)
            for tr, te in cv_rand.split(X, perm_labels)
        ]
        perm_accs.append(np.mean(p_scores))
    p_val = float(np.mean(np.array(perm_accs) >= acc_random))
    p_val = p_val if p_val > 0 else 1.0 / (n_permutations + 1)

    # -- X|R null stratum: refit on ALL A/B trials, apply to every R trial --
    r_result = {"n_trials_r": 0}
    if cond_r_code is not None:
        epochs_r = session.get_epochs(phase=2, condition=cond_r_code)
        if len(epochs_r) > 0:
            win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)
            X_r = np.zeros((len(epochs_r), n_units))
            onsets_r = epochs_r["start_time"].values
            for j, u_id in enumerate(unit_ids):
                st = session.get_spike_times(u_id)
                st = np.sort(st) if st is not None and len(st) else np.array([])
                for i, onset in enumerate(onsets_r):
                    lo = np.searchsorted(st, onset + win_sec[0], side="left")
                    hi = np.searchsorted(st, onset + win_sec[1], side="right")
                    X_r[i, j] = hi - lo
            final_pipe = scaler_pipe()
            final_pipe.fit(X, labels)
            preds_r = final_pipe.predict(X_r)
            n_r = len(preds_r)
            n_pred_b = int(np.sum(preds_r == 1))
            from scipy.stats import binomtest
            bt = binomtest(n_pred_b, n_r, p=0.5)
            ci = bt.proportion_ci(confidence_level=0.95, method="exact")
            r_result = {
                "n_trials_r": n_r,
                "frac_predicted_b_random_model": n_pred_b / n_r if n_r else float("nan"),
                "frac_predicted_b_ci_lo": float(ci.low), "frac_predicted_b_ci_hi": float(ci.high),
                "frac_predicted_b_p_vs_chance": float(bt.pvalue),
            }

    # -- Sub-block (quartile) decodability: can quartile itself be decoded, ignoring
    #    A/B identity entirely? Pooled across both conditions' own quartile labels. --
    clf_q = _LogisticRegression(C=1.0, max_iter=200)
    cv_q = StratifiedKFold(n_splits=min(n_quantiles, 4), shuffle=True, random_state=random_state)
    q_accs = []
    try:
        for tr, te in cv_q.split(X, quartiles):
            sc = StandardScaler().fit(X[tr])
            clf_q.fit(sc.transform(X[tr]), quartiles[tr])
            q_accs.append(_accuracy_score(quartiles[te], clf_q.predict(sc.transform(X[te]))))
        quartile_decode_acc = float(np.mean(q_accs))
    except ValueError:
        quartile_decode_acc = float("nan")

    return {
        **base, "status": "success",
        "accuracy_random_cv": acc_random,
        "accuracy_subblock_loo_cv": acc_subblock_loo,
        "p_val_random_cv": p_val,
        "perm_null_mean": float(np.mean(perm_accs)), "perm_null_std": float(np.std(perm_accs)),
        "chance_baseline": 0.50,
        "quartile_decode_accuracy": quartile_decode_acc,
        "quartile_decode_chance": 1.0 / n_quantiles,
        **r_result,
        "_oof_true": np.array(oof_true), "_oof_score": np.array(oof_score),
        "_oof_quartile": np.array(oof_quartile),
    }


def decode_identity_cycle_deconfound(
    session, area: str, slot_key: str = "p2", contrast: Tuple[str, str] = ("A", "B"),
    time_window_ms: Tuple[float, float] = (1031.0, 1562.0), n_permutations: int = 200,
    random_state: int = 42,
) -> Dict[str, object]:
    """2026-08-06 redesign, after the cycle-structure correction: each condition's trials
    actually occur in ~3 temporally separated repeats across the session (see
    detect_trial_cycles), not one contiguous block -- but WITHIN each repeat, the fixed
    A-then-B-then-R micro-order still holds (confirmed: every cycle, every session). This
    function:
      1. Assigns each A/B/R trial its real cycle id (0,1,2,...).
      2. PER-CYCLE MEAN-CENTERS every unit's spike count using ALL A+B+R trials in that same
         cycle, before scaling -- removes any per-cycle overall gain/excitability level (the
         "neuronal fatigue" explanation: a monotonic level drop across cycles), leaving only
         within-cycle relative differences for the classifier to use.
      3. Runs LEAVE-ONE-CYCLE-OUT CV for the 2-way A-vs-B decode on the centered features --
         tests whether a fixed discriminating pattern recurs across independently-repeated
         cycles, not just within one.
      4. Runs a genuine 3-WAY confusion-matrix decode (A vs B vs R, class-balanced, same
         leave-one-cycle-out folds) -- R has no true identity by design, so the diagnostic is
         whether A/B off-diagonal confusion stays low while R does not systematically skew
         into either the A or B column.
    HONEST LIMIT (stated, not hidden): this rules out a monotonic whole-session drift and a
    per-cycle mean/gain shift, but cannot by itself rule out a fixed, order-locked transient
    that recurs identically after every block transition regardless of content (since A always
    precedes B always precedes R in every cycle, every session -- verified, no exceptions).
    """
    cond_cfg = OMISSION_IDENTITY_CONDITIONS[slot_key]
    cond_a, cond_b, cond_r = cond_cfg[contrast[0]], cond_cfg[contrast[1]], cond_cfg.get("R")
    ea = session.get_epochs(phase=2, condition=cond_a)
    eb = session.get_epochs(phase=2, condition=cond_b)
    er = session.get_epochs(phase=2, condition=cond_r) if cond_r else ea.iloc[0:0]
    units_df = session.get_units(area=area)
    base = {"area": area, "slot_key": slot_key, "n_units": len(units_df)}
    if len(units_df) < 2 or len(ea) < 6 or len(eb) < 6 or len(er) < 6:
        return {**base, "status": "insufficient_data"}
    # See build_noise_controlled_spike_matrix above: identity is row position, not the
    # 'unit_id' column.
    unit_ids = units_df.index.tolist()
    win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)

    def spikemat(epochs):
        onsets = epochs["start_time"].values
        X = np.zeros((len(onsets), len(unit_ids)))
        for j, u_id in enumerate(unit_ids):
            st = session.get_spike_times(u_id)
            st = np.sort(st) if st is not None and len(st) else np.array([])
            for i, onset in enumerate(onsets):
                lo = np.searchsorted(st, onset + win_sec[0], side="left")
                hi = np.searchsorted(st, onset + win_sec[1], side="right")
                X[i, j] = hi - lo
        return X

    Xa, Xb, Xr = spikemat(ea), spikemat(eb), spikemat(er)
    ca, cb, cr = detect_trial_cycles(ea), detect_trial_cycles(eb), detect_trial_cycles(er)
    n_cycles = int(max(ca.max(initial=0), cb.max(initial=0), cr.max(initial=0)) + 1)
    if n_cycles < 2:
        return {**base, "status": "insufficient_cycles", "n_cycles": n_cycles}

    # per-cycle mean-centering: each unit's own A+B+R-pooled mean within that cycle
    def center(X, c):
        Xc = X.copy()
        for k in range(n_cycles):
            pooled_mean = np.concatenate([
                Xa[ca == k], Xb[cb == k], Xr[cr == k]]).mean(axis=0) if (
                (ca == k).any() or (cb == k).any() or (cr == k).any()) else np.zeros(X.shape[1])
            m = c == k
            Xc[m] = X[m] - pooled_mean
        return Xc

    Xa_c, Xb_c, Xr_c = center(Xa, ca), center(Xb, cb), center(Xr, cr)

    from sklearn.svm import SVC
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler as _SS

    # ---- 2-way A vs B, leave-one-cycle-out ----
    Xab = np.concatenate([Xa_c, Xb_c], axis=0)
    yab = np.array([0] * len(Xa_c) + [1] * len(Xb_c))
    cyc_ab = np.concatenate([ca, cb])
    accs = []
    for k in range(n_cycles):
        te = cyc_ab == k
        tr = ~te
        if len(set(yab[te].tolist())) < 1 or len(set(yab[tr].tolist())) < 2 or te.sum() < 2:
            continue
        p = Pipeline([("scaler", _SS()), ("clf", SVC(kernel="linear", C=1.0, random_state=random_state))])
        p.fit(Xab[tr], yab[tr])
        accs.append(p.score(Xab[te], yab[te]))
    acc_loco = float(np.mean(accs)) if accs else float("nan")

    # Within-cycle permutation, not a global one: the CV above holds out whole cycles
    # (leave-one-cycle-out), so the null must be exchangeable under that same grouping -- a
    # bare rng.permutation(yab) here was an audit-flagged bug (2026-08-10, see
    # artifacts/.lab/agent-harness-audit-20260810.json claim-p0-deconfound-null-ignores-cycle-
    # grouping) since it compared a cycle-respecting observed statistic against a
    # cycle-ignoring null.
    rng = np.random.default_rng(random_state)
    perm_accs = []
    for _ in range(n_permutations):
        y_perm = permute_labels(yab, groups=cyc_ab, scheme="within_group", rng=rng)
        p_accs = []
        for k in range(n_cycles):
            te = cyc_ab == k
            tr = ~te
            if len(set(y_perm[te].tolist())) < 1 or len(set(y_perm[tr].tolist())) < 2 or te.sum() < 2:
                continue
            p = Pipeline([("scaler", _SS()), ("clf", SVC(kernel="linear", C=1.0, random_state=random_state))])
            p.fit(Xab[tr], y_perm[tr])
            p_accs.append(p.score(Xab[te], y_perm[te]))
        if p_accs:
            perm_accs.append(np.mean(p_accs))
    p_val = float(np.mean(np.array(perm_accs) >= acc_loco)) if perm_accs else float("nan")
    p_val = p_val if (p_val and p_val > 0) else (1.0 / (n_permutations + 1) if perm_accs else float("nan"))

    # ---- 3-way A vs B vs R, leave-one-cycle-out, class-balanced per fold ----
    Xabr = np.concatenate([Xa_c, Xb_c, Xr_c], axis=0)
    yabr = np.array([0] * len(Xa_c) + [1] * len(Xb_c) + [2] * len(Xr_c))
    cyc_abr = np.concatenate([ca, cb, cr])
    conf = np.zeros((3, 3))
    n_conf_folds = 0
    for k in range(n_cycles):
        te = cyc_abr == k
        tr = ~te
        if te.sum() < 3 or len(set(yabr[tr].tolist())) < 3:
            continue
        n_min_tr = min((yabr[tr] == c).sum() for c in (0, 1, 2))
        if n_min_tr < 2:
            continue
        rng2 = np.random.default_rng(random_state + k)
        idx_bal = np.concatenate([
            rng2.choice(np.where(tr & (yabr == c))[0], n_min_tr, replace=False) for c in (0, 1, 2)])
        clf = _LogisticRegression(C=1.0, max_iter=500)
        sc = _SS().fit(Xabr[idx_bal])
        clf.fit(sc.transform(Xabr[idx_bal]), yabr[idx_bal])
        preds = clf.predict(sc.transform(Xabr[te]))
        for true_c, pred_c in zip(yabr[te], preds):
            conf[true_c, pred_c] += 1
        n_conf_folds += 1
    conf_row_norm = conf / np.maximum(conf.sum(axis=1, keepdims=True), 1)

    return {
        **base, "status": "success", "n_cycles": n_cycles,
        "acc_loco_meancentered": acc_loco, "p_val_loco": p_val,
        "perm_null_mean": float(np.mean(perm_accs)) if perm_accs else float("nan"),
        "n_trials_a": len(Xa), "n_trials_b": len(Xb), "n_trials_r": len(Xr),
        "confusion_matrix_counts": conf.tolist(),
        "confusion_matrix_row_normalized": conf_row_norm.tolist(),
        "confusion_labels": [contrast[0], contrast[1], "R"],
        "n_confusion_folds": n_conf_folds,
    }


def shuffle_r2_ci(y_true: np.ndarray, y_score: np.ndarray, groups: Optional[np.ndarray] = None,
                   n_shuffle: int = 200, random_state: int = 42) -> Dict[str, float]:
    """R^2 (squared Pearson correlation) between a continuous decision score and a
    0/1 label, with a shuffle-null 95% CI (percentile of the null, not of the estimate
    -- this project's own doctrine reserves exact/analytic CIs for proportions built
    from counts; R^2 has no such closed form, so shuffle is the documented choice here).
    If `groups` is given (e.g. session id), labels are shuffled WITHIN each group so the
    null preserves the group structure instead of pooling across it."""
    def _r2(y, s):
        if np.std(s) == 0 or np.std(y) == 0:
            return 0.0
        r = np.corrcoef(y, s)[0, 1]
        return float(r ** 2)

    r2_obs = _r2(y_true, y_score)
    rng = np.random.default_rng(random_state)
    null = np.empty(n_shuffle)
    scheme = "global" if groups is None else "within_group"
    for i in range(n_shuffle):
        y_perm = permute_labels(y_true, groups=groups, scheme=scheme, rng=rng)
        null[i] = _r2(y_perm, y_score)
    p_val = float(np.mean(null >= r2_obs))
    p_val = p_val if p_val > 0 else 1.0 / (n_shuffle + 1)
    return {
        "r2_observed": r2_obs,
        "r2_null_ci_lo": float(np.percentile(null, 2.5)),
        "r2_null_ci_hi": float(np.percentile(null, 97.5)),
        "r2_null_mean": float(np.mean(null)),
        "p_val": p_val,
        "n_shuffle": n_shuffle,
    }


def decode_time_from_features(
    session, area: str, epochs: pd.DataFrame, time_window_ms: Tuple[float, float],
    n_splits: int = 5, random_state: int = 42,
) -> Dict[str, float]:
    """'Is it real?' sanity check: can elapsed trial start_time (continuous, seconds
    from session start) be predicted from the SAME spike-count features used for
    identity decoding? A strong positive here means the population signal tracks
    generic session drift, not identity content specifically."""
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import KFold

    units_df = session.get_units(area=area)
    if len(units_df) < 2 or len(epochs) < 6:
        return {"status": "insufficient_data"}
    # See build_noise_controlled_spike_matrix above: identity is row position, not the
    # 'unit_id' column.
    unit_ids = units_df.index.tolist()
    win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)
    onsets = epochs["start_time"].values
    X = np.zeros((len(onsets), len(unit_ids)))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
    t = onsets - onsets.min()

    cv = KFold(n_splits=min(n_splits, len(onsets)), shuffle=True, random_state=random_state)
    oof_pred = np.zeros_like(t)
    for tr, te in cv.split(X):
        sc = StandardScaler().fit(X[tr])
        reg = Ridge(alpha=1.0).fit(sc.transform(X[tr]), t[tr])
        oof_pred[te] = reg.predict(sc.transform(X[te]))
    r2 = shuffle_r2_ci(t, oof_pred, n_shuffle=200, random_state=random_state)
    return {"status": "success", "n_trials": len(t), **r2}
