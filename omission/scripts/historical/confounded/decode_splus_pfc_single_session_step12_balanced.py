#!/usr/bin/env python3

# === QUARANTINED 2026-08-10 -- do not use as an empirical source ===
# Per artifacts/.lab/agent-harness-audit-20260810.json (Sol/Hamm Handout 2, P0 item 1):
# this script uses invalid (ungrouped/random) cross-validation for omission-identity-style
# decoding on a corpus with real repeated-cycle structure -- same-cycle trials can land in
# both train and test, inflating apparent accuracy. It is preserved as forensic evidence of
# what was tried and why it was superseded, per this project's Conservation doctrine
# (reduction is valid only if prior state remains recoverable) -- NOT deleted.
# tests/test_quarantine_enforcement.py fails if any live (non-historical) script imports from
# this module.
scientific_status = "invalid_for_inference"
superseded_by = 'compute_omission_identity_leakage_safe.py'
reason = ['ungrouped_cv']
# === END QUARANTINE HEADER ===

r"""
Step 1 (real-stimulus positive control) + Step 2 (omission identity, now class-balanced),
same session and same 19 S+ PFC units throughout.

STEP 1 -- "does it encode the actually presented stimulus?" AAAB/BBBA/RRRR is the SAME
condition code across all three windows (a whole-sequence code, not slot-specific) -- same
trial onsets, different window read from each onset:
    d1-p2-d2 -> real stimulus at p2 is A (AAAB), B (BBBA), or R (RRRR)
    d2-p3-d3 -> real stimulus at p3 is A (AAAB), B (BBBA), or R (RRRR)
    d3-p4-d4 -> real stimulus at p4 is B (AAAB has B here!), A (BBBA has A here!), or R (RRRR)
    (AAAB's 4th slot is B and BBBA's 4th slot is A -- the class label at p4 flips relative to
    the condition-code name; handled explicitly below, not just re-using the p2/p3 mapping.)

STEP 2 -- omission identity (AXAB/BXBA/RXRR etc.), same wide windows as before, but NOW with
class-balanced downsampling to the smallest class's trial count per slot before the SVM --
the fix for step 2's p4 pathology (classifier collapsing to the majority class R).

Both steps: one-shot 3-way SVM (A vs B vs R), same half/half (2-fold) CV convention.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa  # noqa: E402
from jnwb import paths as _P

SESSION = "sub-C31o_ses-230818"
NWB_PATH = _P.nwb_dir() / "sub-C31o_ses-230818_rec.nwb"
RANDOM_STATE = 42

# STEP 2 -- omission identity, condition code differs per slot
OMISSION_SLOTS = {
    "p2": {"A": "AXAB", "B": "BXBA", "R": "RXRR", "window_ms": (531.0, 2062.0)},
    "p3": {"A": "AAXB", "B": "BBXA", "R": "RRXR", "window_ms": (1562.0, 3093.0)},
    "p4": {"A": "AAAX", "B": "BBBX", "R": "RRRX", "window_ms": (2593.0, 4124.0)},
}

# STEP 1 -- real stimulus, SAME condition codes at every slot, but the "which is A/B" label
# flips at p4 (AAAB's 4th real stimulus IS B; BBBA's 4th real stimulus IS A).
STIM_SLOTS = {
    "p2": {"A": "AAAB", "B": "BBBA", "R": "RRRR", "window_ms": (531.0, 2062.0)},
    "p3": {"A": "AAAB", "B": "BBBA", "R": "RRRR", "window_ms": (1562.0, 3093.0)},
    "p4": {"A": "BBBA", "B": "AAAB", "R": "RRRR", "window_ms": (2593.0, 4124.0)},  # flipped
}


def get_splus_pfc_unit_ids():
    s = pd.read_csv(REPO_ROOT / "outputs/classification/grand_s_and_o_units.csv")
    sub = s[(s.is_Splus == True) & (s.area == "PFC") & (s.session_prefix == SESSION)]
    return sub.unit_id.astype(float).tolist()


def build_matrix(session, unit_ids, epochs_by_class, win_ms, random_state):
    """Downsample every class to the smallest class's trial count before building X, y --
    the noise-controlled/equalized-N convention used throughout this project."""
    n_min = min(len(e) for e in epochs_by_class.values())
    rng = np.random.default_rng(random_state)
    onsets, labels = [], []
    n_by_class_used = {}
    for lab, (cls, epochs) in enumerate(epochs_by_class.items()):
        vals = epochs["start_time"].values
        idx = rng.choice(len(vals), size=n_min, replace=False) if len(vals) > n_min else np.arange(len(vals))
        onsets.append(vals[idx])
        labels.extend([lab] * len(idx))
        n_by_class_used[cls] = len(idx)
    onsets = np.concatenate(onsets)
    labels = np.array(labels)
    win_sec = (win_ms[0] / 1000.0, win_ms[1] / 1000.0)
    X = np.zeros((len(onsets), len(unit_ids)))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
    return X, labels, n_by_class_used


def run_slots(session, unit_ids, slots, title):
    print(f"\n{'='*20} {title} {'='*20}")
    for slot_key, cfg in slots.items():
        win = cfg["window_ms"]
        class_labels = ["A", "B", "R"]
        epochs_by_class = {c: session.get_epochs(phase=2, condition=cfg[c]) for c in class_labels}
        raw_n = {c: len(e) for c, e in epochs_by_class.items()}
        print(f"\n--- slot {slot_key}  (window {win[0]:.0f}-{win[1]:.0f} ms)  "
             f"A={cfg['A']} B={cfg['B']} R={cfg['R']} ---")
        print(f"  raw n trials: {raw_n}")

        X, y, n_used = build_matrix(session, unit_ids, epochs_by_class, win, RANDOM_STATE)
        print(f"  downsampled to n={n_used} per class -> feature matrix: {X.shape}")

        cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
        fold_accs = []
        all_true, all_pred = [], []
        for fold_i, (train_idx, test_idx) in enumerate(cv.split(X, y)):
            pipe = Pipeline([("scaler", StandardScaler()),
                             ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
            pipe.fit(X[train_idx], y[train_idx])
            preds = pipe.predict(X[test_idx])
            acc = np.mean(preds == y[test_idx])
            fold_accs.append(acc)
            all_true.extend(y[test_idx]); all_pred.extend(preds)
            print(f"  fold {fold_i}: train n={len(train_idx)}, test n={len(test_idx)}, "
                 f"accuracy = {acc:.3f}")

        print(f"  mean 2-fold accuracy: {np.mean(fold_accs):.3f}  (balanced chance = 0.333)")
        cm = confusion_matrix(all_true, all_pred, labels=[0, 1, 2])
        cm_norm = cm / cm.sum(axis=1, keepdims=True)
        print(f"  pooled confusion matrix (rows=true, cols=pred, order=A,B,R):")
        for row_lab, row in zip(class_labels, cm_norm):
            print(f"    {row_lab}: {np.round(row, 2)}")


def main():
    unit_ids = get_splus_pfc_unit_ids()
    print(f"Session {SESSION}: {len(unit_ids)} S+ PFC units")
    session = oa.read(NWB_PATH)

    run_slots(session, unit_ids, STIM_SLOTS,
             "STEP 1: real presented stimulus (AAAB/BBBA/RRRR)")
    run_slots(session, unit_ids, OMISSION_SLOTS,
             "STEP 2: omitted identity, class-balanced (AXAB/BXBA/RXRR etc.)")


if __name__ == "__main__":
    main()
