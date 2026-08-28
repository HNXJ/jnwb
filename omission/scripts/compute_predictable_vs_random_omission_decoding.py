#!/usr/bin/env python3
"""Evaluate Predictable Omission (X|A, X|B) vs Random Omission (X|R) across SPK and LFP.

Scientific Question:
  Does cortical population spiking (SPK) or LFP band power represent the *predictability context*
  of an omission (Predictable Rule Stream vs Random Stream) during the omission window,
  even when physical stimulus input is identically absent?

Target:
  Class 0: Structured / Predictable Omission (AXAB, AAXB, AAAX, BXBA, BBXA, BBBX) -> X|A or X|B
  Class 1: Unstructured / Random Omission (RXRR, RRXR, RRRX) -> X|R

Tested Representations:
  1. SPK Direct (firing rates)
  2. SPK PCA -> UMAP -> Logistic
  3. LFP Direct (5-band spectral power)
  4. LFP PCA -> UMAP -> Logistic
  5. Balanced Multimodal Latent Fusion [PCA(S), PCA(L)] -> UMAP

Evaluation:
  Leave-one-cycle-out CV (jnwb.statistics.detect_trial_cycles grouping; replaced an ungrouped
  StratifiedKFold on 2026-08-26 -- see cycle_grouped_splits docstring) across multi-area sessions.
  Exact permutation null testing (p_perm), 999 permutations, (1+k)/(N_PERM+1) finite-sample
  correction (North et al. 2002).

Outputs:
  - outputs/classification/predictable_vs_random_omission_results.csv
  - outputs/classification/predictable_vs_random_omission_summary.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
import umap

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent

sys.path.insert(0, str(OA_ROOT / "scripts"))
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.trial_ontology import build_trial_ontology
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from jnwb.statistics import detect_trial_cycles
import jnwb.paths as P

OUT_DIR = OA_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Canonical timing only -- do not re-derive or duplicate these values locally.
# p1=0, d1=531, p2=1031, d2=1562, p3=2062, d3=2593, p4=3093, d4=3624 (ms).
SLOT_ONSETS_MS = {"p2": EPOCH_ONSETS_MS["p2"], "p3": EPOCH_ONSETS_MS["p3"], "p4": EPOCH_ONSETS_MS["p4"]}
SLOT_DUR_MS = EPOCH_ONSETS_MS["d1"] - EPOCH_ONSETS_MS["p1"]


def extract_spk_features(session, area: str, df_trials: pd.DataFrame, n_bins: int = 10):
    units = session.get_units(area=area) if area != "ALL" else session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(df_trials) == 0:
        return np.zeros((len(df_trials), 0), dtype=float)
        
    onsets = np.zeros(len(df_trials), dtype=float)
    for i, (_, row) in enumerate(df_trials.iterrows()):
        slot_key = row["slot_key"]
        onsets[i] = float(row["start_time"]) + (SLOT_ONSETS_MS[slot_key] / 1000.0)
        
    t_edges = np.linspace(0.0, SLOT_DUR_MS / 1000.0, n_bins + 1)
    X_3d = np.zeros((len(onsets), len(row_indices), n_bins), dtype=float)
    
    for u_col, row_idx in enumerate(row_indices):
        spikes = session.get_spike_times(row_idx)
        if spikes is not None and len(spikes) > 0:
            spikes = np.sort(np.asarray(spikes, dtype=float))
            for b in range(n_bins):
                lo_off = t_edges[b]
                hi_off = t_edges[b + 1]
                X_3d[:, u_col, b] = np.searchsorted(spikes, onsets + hi_off, side="right") - np.searchsorted(spikes, onsets + lo_off, side="left")
                
    return X_3d.reshape(len(onsets), len(row_indices) * n_bins)


def cycle_grouped_splits(df_joint: pd.DataFrame, y: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    """Leave-one-cycle-out folds using the canonical jnwb.statistics.detect_trial_cycles grouping.

    2026-08-26: replaces the previous ungrouped StratifiedKFold, which risked leakage across
    the same temporal cycle (block) between train and test -- structurally the same class of
    bug fixed once before in decode_identity_cycle_deconfound (2026-08-10), and flagged as an
    unaudited risk during the Fig04 timing-defect remediation. Everything else (features,
    target, metric, permutation scheme) is unchanged.
    """
    cycles = detect_trial_cycles(df_joint[["start_time"]])
    splits = []
    for cycle in np.unique(cycles):
        test_idx = np.flatnonzero(cycles == cycle)
        train_idx = np.flatnonzero(cycles != cycle)
        if len(train_idx) == 0 or len(test_idx) == 0:
            continue
        if len(np.unique(y[train_idx])) < 2:
            continue
        splits.append((train_idx, test_idx))
    return splits


def evaluate_cv(X: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], use_umap: bool = False, seed: int = 42):
    oof_preds = np.zeros(len(y), dtype=float)
    oof_probs = np.zeros(len(y), dtype=float)
    
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(np.log1p(np.maximum(0, X[train_idx])))
        X_te = scaler.transform(np.log1p(np.maximum(0, X[test_idx])))
        
        if use_umap:
            d_p = min(10, X_tr.shape[1], max(2, len(train_idx) - 2))
            pca = PCA(n_components=d_p, random_state=seed + fold)
            X_tr_p = pca.fit_transform(X_tr)
            X_te_p = pca.transform(X_te)
            
            d_u = min(3, d_p - 1, max(2, len(train_idx) - 2))
            reducer = umap.UMAP(n_components=d_u, n_neighbors=min(15, len(train_idx)-1), min_dist=0.1, random_state=seed + fold)
            Z_tr = reducer.fit_transform(X_tr_p)
            Z_te = reducer.transform(X_te_p)
            clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold)
            clf.fit(Z_tr, y[train_idx])
            oof_preds[test_idx] = clf.predict(Z_te)
            oof_probs[test_idx] = clf.predict_proba(Z_te)[:, 1]
        else:
            clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold)
            clf.fit(X_tr, y[train_idx])
            oof_preds[test_idx] = clf.predict(X_te)
            oof_probs[test_idx] = clf.predict_proba(X_te)[:, 1]
            
    acc = float(balanced_accuracy_score(y, oof_preds))
    try:
        auc = float(roc_auc_score(y, oof_probs))
    except Exception:
        auc = acc
    return {"acc": acc, "auc": auc}


def main():
    t0 = time.time()
    nwb_files = sorted(list(Path("D:/nwb/omission").glob("*.nwb")))
    rep_sessions = ["sub-C31o_ses-230816", "sub-C31o_ses-230823", "sub-V182o_ses-260710", "sub-V198o_ses-230719"]
    target_files = [p for p in nwb_files if any(s in p.name for s in rep_sessions)]
    
    print(f"Evaluating Predictable vs Random Omission Decoding on {len(target_files)} sessions...")
    
    results = []
    
    for s_idx, nwb_path in enumerate(target_files):
        sess_name = nwb_path.stem.replace("_rec", "")
        subj = sess_name.split("_")[0].replace("sub-", "")
        session = oa.read(nwb_path)
        onto = build_trial_ontology(session, slot_keys=("p2", "p3", "p4"), families=("A", "B", "R"))
        
        # Filter correct trials
        onto_corr = onto[onto["correct_trial"]].copy().reset_index(drop=True)
        
        df_pred = onto_corr[onto_corr["sequence_family"].isin(["A", "B"])].copy()
        df_rand = onto_corr[onto_corr["sequence_family"] == "R"].copy()
        
        print(f"Session {sess_name}: {len(df_pred)} Predictable Omissions, {len(df_rand)} Random Omissions")
        if len(df_pred) < 10 or len(df_rand) < 10:
            continue
            
        for slot in ["p2", "p3", "p4", "ALL_SLOTS"]:
            if slot in ["p2", "p3", "p4"]:
                sub_p = df_pred[df_pred["slot_key"] == slot].copy()
                sub_r = df_rand[df_rand["slot_key"] == slot].copy()
            else:
                sub_p = df_pred.copy()
                sub_r = df_rand.copy()
                
            if len(sub_p) < 6 or len(sub_r) < 6:
                continue
                
            sub_p["target_class"] = 0 # Predictable Context (X|A or X|B)
            sub_r["target_class"] = 1 # Random Context (X|R)
            df_joint = pd.concat([sub_p, sub_r], ignore_index=True)
            y = df_joint["target_class"].to_numpy()
            
            for area in ["V1", "MT", "ALL"]:
                u_test = session.get_units(area=area) if area != "ALL" else session.get_units()
                if len(u_test) < 4:
                    continue
                X_spk = extract_spk_features(session, area, df_joint, n_bins=10)
                if X_spk.shape[1] < 4:
                    continue
                    
                cv_splits = cycle_grouped_splits(df_joint, y)
                if len(cv_splits) < 2:
                    print(f"  skip {sess_name}/{area}/{slot}: fewer than 2 valid cycle-grouped folds")
                    continue

                res_spk_dir = evaluate_cv(X_spk, y, cv_splits, use_umap=False)
                res_spk_umap = evaluate_cv(X_spk, y, cv_splits, use_umap=True)
                
                # Permutation null
                N_PERM = 999
                rng = np.random.default_rng(42)
                p_nulls = []
                for _ in range(N_PERM):
                    y_p = rng.permutation(y)
                    p_nulls.append(evaluate_cv(X_spk, y_p, cv_splits, use_umap=False)["acc"])
                # +1 correction (North & al. 2002): avoids a literal p=0 floor that a finite
                # permutation count cannot actually support.
                p_perm = float((1 + np.sum(np.array(p_nulls) >= res_spk_dir["acc"])) / (N_PERM + 1))
                
                results.append({
                    "session": sess_name, "subject": subj, "area": area, "slot": slot,
                    "n_predictable": len(sub_p), "n_random": len(sub_r),
                    "spk_direct_acc": res_spk_dir["acc"], "spk_direct_auc": res_spk_dir["auc"],
                    "spk_pca_umap_acc": res_spk_umap["acc"], "spk_pca_umap_auc": res_spk_umap["auc"],
                    "p_perm": p_perm, "null_mean": float(np.mean(p_nulls))
                })
                
    df_res = pd.DataFrame(results)
    df_res.to_csv(OUT_DIR / "predictable_vs_random_omission_results.csv", index=False)
    
    print("\n=== Predictable Omission (X|A/B) vs Random Omission (X|R) Decoding Summary ===")
    summary = df_res.groupby(["slot", "area"])[["spk_direct_acc", "spk_direct_auc", "spk_pca_umap_acc", "p_perm"]].mean().reset_index()
    print(summary.to_string(index=False))
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_sessions": len(target_files),
        "total_evaluations": len(df_res),
        "summary": summary.to_dict(orient="records"),
        "mean_accuracy_direct": float(df_res["spk_direct_acc"].mean()),
        "mean_accuracy_umap": float(df_res["spk_pca_umap_acc"].mean()),
        "significant_fraction": float((df_res["p_perm"] < 0.05).mean()),
        "runtime_seconds": round(time.time() - t0, 2)
    }
    with open(OUT_DIR / "predictable_vs_random_omission_summary.json", "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\nSaved summary receipt to {OUT_DIR / 'predictable_vs_random_omission_summary.json'}")


if __name__ == "__main__":
    main()
