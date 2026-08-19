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
Step 1, deliberately minimal: one session, PFC S+ units only, decode "is it A or B" (the omitted
identity at P2: AXAB vs BXBA), single 50/50 train/test split, both directions (2-fold), no
cycle/block deconfounding yet -- that comes after this baseline is established.

Session: sub-C31o_ses-230818 (19 S+ PFC units, most of any session in this corpus, confirmed
against grand_s_and_o_units.csv's is_Splus/area=='PFC' rows, all 19 unit_ids verified present
in this session's live PFC unit table before use).
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
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
P2_WINDOW_MS = (1031.0, 1562.0)
RANDOM_STATE = 42


def get_splus_pfc_unit_ids():
    s = pd.read_csv(REPO_ROOT / "outputs/classification/grand_s_and_o_units.csv")
    sub = s[(s.is_Splus == True) & (s.area == "PFC") & (s.session_prefix == SESSION)]
    return sub.unit_id.astype(float).tolist()


def build_matrix(session, unit_ids, epochs_a, epochs_b, win_ms):
    onsets = np.concatenate([epochs_a["start_time"].values, epochs_b["start_time"].values])
    labels = np.array([0] * len(epochs_a) + [1] * len(epochs_b))
    win_sec = (win_ms[0] / 1000.0, win_ms[1] / 1000.0)
    X = np.zeros((len(onsets), len(unit_ids)))
    for j, u_id in enumerate(unit_ids):
        st = session.get_spike_times(u_id)
        st = np.sort(st) if st is not None and len(st) else np.array([])
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
    return X, labels


def main():
    unit_ids = get_splus_pfc_unit_ids()
    print(f"Session {SESSION}: {len(unit_ids)} S+ PFC units: {unit_ids}")

    session = oa.read(NWB_PATH)
    epochs_a = session.get_epochs(phase=2, condition="AXAB")
    epochs_b = session.get_epochs(phase=2, condition="BXBA")
    print(f"n AXAB trials: {len(epochs_a)}, n BXBA trials: {len(epochs_b)}")

    X, y = build_matrix(session, unit_ids, epochs_a, epochs_b, P2_WINDOW_MS)
    print(f"Feature matrix: {X.shape} (trials x units)")

    # 2-fold CV = exactly "split trials half and half, train/test, both directions"
    cv = StratifiedKFold(n_splits=2, shuffle=True, random_state=RANDOM_STATE)
    fold_accs = []
    for fold_i, (train_idx, test_idx) in enumerate(cv.split(X, y)):
        pipe = Pipeline([("scaler", StandardScaler()),
                         ("clf", SVC(kernel="linear", C=1.0, random_state=RANDOM_STATE))])
        pipe.fit(X[train_idx], y[train_idx])
        acc = pipe.score(X[test_idx], y[test_idx])
        fold_accs.append(acc)
        print(f"  fold {fold_i}: train n={len(train_idx)}, test n={len(test_idx)}, "
             f"test accuracy = {acc:.3f}")

    print(f"\nMean 2-fold (half/half) accuracy: {np.mean(fold_accs):.3f}  (chance = 0.50)")


if __name__ == "__main__":
    main()
