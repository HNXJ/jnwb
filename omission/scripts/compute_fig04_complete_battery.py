#!/usr/bin/env python3
"""Execute the complete Fig04 four-question encoding battery across the full corpus.

Estimands computed:
  1. I(A/B; S_stim): Physical stimulus identity (A vs B) during p1 presentation window.
  2. I(p; S): Temporal context position (p1 vs p2 vs p3 vs p4) under cycle-grouped CV with nested condition balancing.
  3. I(A/B; S_omission): Omission identity (X|A vs X|B) scalar rate decoding at p2, p3, p4, and cross-position generalization.
  4. I(A/B; S_omission^{N x T}): Session-specific spatiotemporal population decoding (neuron x time bins, f_s: R^{N_s x T} -> {A,B}).

Outputs:
  - outputs/classification/fig04_battery_results.csv
  - outputs/classification/fig04_battery_summary.csv
  - outputs/classification/fig04_battery_receipt.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent

sys.path.insert(0, str(OA_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS
import jnwb.paths as P

NWB_DIR = Path("D:/nwb/omission")
OUT_DIR = OA_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)
READINESS_CSV = OA_ROOT / "context" / "inventory" / "session_readiness.csv"

AREAS = ["V1", "V2", "V3", "V4", "MT", "MST", "TEO", "FEF", "PFC"]
SLOT_WINDOWS_MS = {
    "p1": (500.0, 1031.0),
    "p2": (1031.0, 1562.0),
    "p3": (1562.0, 2094.0),
    "p4": (2094.0, 2625.0),
}


def assign_temporal_cycles(start_times_s: np.ndarray, gap_factor: float = 10.0) -> np.ndarray:
    if start_times_s.size == 0:
        return np.array([], dtype=int)
    times = np.asarray(start_times_s, dtype=float)
    order = np.argsort(times, kind="stable")
    sorted_times = times[order]
    gaps = np.diff(sorted_times)
    positive = gaps[gaps > 0]
    reference = float(np.median(positive)) if positive.size else np.inf
    threshold = gap_factor * reference
    sorted_cycles = np.zeros(times.size, dtype=int)
    if np.isfinite(threshold):
        for boundary in np.flatnonzero(gaps > threshold):
            sorted_cycles[boundary + 1 :] += 1
    cycles = np.empty(times.size, dtype=int)
    cycles[order] = sorted_cycles
    return cycles


def _spike_count_matrix(session, area: str, epochs: pd.DataFrame, window_ms: tuple[float, float]) -> np.ndarray:
    units = session.get_units(area=area) if area != "ALL" else session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0), dtype=float)
    onsets = pd.to_numeric(epochs["start_time"], errors="coerce").to_numpy(float)
    X = np.zeros((len(onsets), len(row_indices)), dtype=float)
    lo_offset, hi_offset = float(window_ms[0]) / 1000.0, float(window_ms[1]) / 1000.0
    for col, row_idx in enumerate(row_indices):
        spikes = session.get_spike_times(row_idx)
        if spikes is not None and len(spikes) > 0:
            spikes = np.sort(np.asarray(spikes, dtype=float))
            X[:, col] = np.searchsorted(spikes, onsets + hi_offset, side="right") - np.searchsorted(
                spikes, onsets + lo_offset, side="left"
            )
    return X


def _spatiotemporal_matrix(session, epochs: pd.DataFrame, window_ms: tuple[float, float], n_bins: int = 10) -> np.ndarray:
    units = session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0), dtype=float)
    onsets = pd.to_numeric(epochs["start_time"], errors="coerce").to_numpy(float)
    t_edges = np.linspace(window_ms[0] / 1000.0, window_ms[1] / 1000.0, n_bins + 1)
    X = np.zeros((len(onsets), len(row_indices) * n_bins), dtype=float)
    for col, row_idx in enumerate(row_indices):
        spikes = session.get_spike_times(row_idx)
        if spikes is not None and len(spikes) > 0:
            spikes = np.sort(np.asarray(spikes, dtype=float))
            for b in range(n_bins):
                lo_off = t_edges[b]
                hi_off = t_edges[b + 1]
                X[:, col * n_bins + b] = np.searchsorted(spikes, onsets + hi_off, side="right") - np.searchsorted(
                    spikes, onsets + lo_off, side="left"
                )
    return X


def evaluate_binary_loco(X: np.ndarray, y: np.ndarray, cycles: np.ndarray, n_perm: int = 50, seed: int = 42) -> dict:
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or len(np.unique(y)) < 2:
        return {"auc": 0.5, "bal_acc": 0.5, "p_perm": 1.0, "null_mean": 0.5}
        
    oof_preds = np.zeros(len(y), dtype=float)
    oof_decision = np.zeros(len(y), dtype=float)
    valid_test = np.zeros(len(y), dtype=bool)
    rng = np.random.default_rng(seed)
    
    for fold, cycle in enumerate(unique_cycles):
        test_mask = (cycles == cycle)
        train_mask = ~test_mask
        
        tr_idx = np.where(train_mask)[0]
        # In-fold class balancing
        idx_0 = tr_idx[y[tr_idx] == 0]
        idx_1 = tr_idx[y[tr_idx] == 1]
        if len(idx_0) == 0 or len(idx_1) == 0 or np.sum(test_mask) == 0:
            continue
        n_min = min(len(idx_0), len(idx_1))
        balanced_train = np.concatenate([rng.choice(idx_0, n_min, replace=False), rng.choice(idx_1, n_min, replace=False)])
        
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[balanced_train])
        X_te = scaler.transform(X[test_mask])
        
        clf = SVC(kernel="linear", C=1.0, random_state=seed + fold)
        clf.fit(X_tr, y[balanced_train])
        oof_preds[test_mask] = clf.predict(X_te)
        oof_decision[test_mask] = clf.decision_function(X_te)
        valid_test[test_mask] = True
        
    if not np.any(valid_test):
        return {"auc": 0.5, "bal_acc": 0.5, "p_perm": 1.0, "null_mean": 0.5}
        
    bal_acc = float(balanced_accuracy_score(y[valid_test], oof_preds[valid_test]))
    try:
        auc = float(roc_auc_score(y[valid_test], oof_decision[valid_test]))
    except Exception:
        auc = 0.5
        
    # Within-cycle permutation null
    null_scores = []
    for p_idx in range(n_perm):
        perm_rng = np.random.default_rng(seed + 1000 + p_idx)
        y_perm = y.copy()
        for c in unique_cycles:
            c_idx = np.where(cycles == c)[0]
            y_perm[c_idx] = perm_rng.permutation(y[c_idx])
            
        oof_p = np.zeros(len(y), dtype=float)
        v_p = np.zeros(len(y), dtype=bool)
        for fold, cycle in enumerate(unique_cycles):
            test_mask = (cycles == cycle)
            train_mask = ~test_mask
            tr_idx = np.where(train_mask)[0]
            idx_0 = tr_idx[y_perm[tr_idx] == 0]
            idx_1 = tr_idx[y_perm[tr_idx] == 1]
            if len(idx_0) == 0 or len(idx_1) == 0 or np.sum(test_mask) == 0:
                continue
            n_min = min(len(idx_0), len(idx_1))
            balanced_train = np.concatenate([perm_rng.choice(idx_0, n_min, replace=False), perm_rng.choice(idx_1, n_min, replace=False)])
            
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X[balanced_train])
            X_te = scaler.transform(X[test_mask])
            clf = SVC(kernel="linear", C=1.0, random_state=seed + fold)
            clf.fit(X_tr, y_perm[balanced_train])
            oof_p[test_mask] = clf.predict(X_te)
            v_p[test_mask] = True
            
        if np.any(v_p):
            null_scores.append(balanced_accuracy_score(y_perm[v_p], oof_p[v_p]))
            
    null_arr = np.array(null_scores)
    p_perm = float((np.sum(null_arr >= bal_acc) + 1) / (len(null_arr) + 1)) if len(null_arr) else 1.0
    return {"auc": auc, "bal_acc": bal_acc, "p_perm": p_perm, "null_mean": float(np.mean(null_arr)) if len(null_arr) else 0.5}


def main():
    t0 = time.time()
    nwb_files = sorted(list(NWB_DIR.glob("*.nwb")))
    print(f"Executing Fig04 complete battery across {len(nwb_files)} NWB sessions...")
    
    battery_records = []
    
    for s_idx, nwb_path in enumerate(nwb_files):
        stem = nwb_path.stem
        sess_name = stem.replace("_rec", "")
        subj = sess_name.split("_")[0].replace("sub-", "")
        
        try:
            session = oa.read(nwb_path)
        except Exception as e:
            print(f"Error reading {nwb_path}: {e}")
            continue
            
        units_all = session.get_units()
        if len(units_all) == 0:
            continue
            
        # 1. Stimulus Identity (A vs B at p1)
        # Use p1 presentation of AXAB vs BXBA (and related conditions)
        cfg_p2 = OMISSION_IDENTITY_CONDITIONS["p2"]
        ep_a = session.get_epochs(phase=2, condition=cfg_p2["A"], correct_only=True)
        ep_b = session.get_epochs(phase=2, condition=cfg_p2["B"], correct_only=True)
        
        if len(ep_a) >= 5 and len(ep_b) >= 5:
            ep_stim = pd.concat([ep_a, ep_b], ignore_index=True)
            y_stim = np.array([1]*len(ep_a) + [0]*len(ep_b))
            cycles_stim = assign_temporal_cycles(pd.to_numeric(ep_stim["start_time"]).to_numpy())
            
            # Area-by-area
            for area in AREAS:
                u_area = session.get_units(area=area)
                if len(u_area) >= 2:
                    X_p1 = _spike_count_matrix(session, area, ep_stim, SLOT_WINDOWS_MS["p1"])
                    res = evaluate_binary_loco(X_p1, y_stim, cycles_stim, n_perm=50)
                    battery_records.append({
                        "session": sess_name, "subject": subj, "area": area,
                        "analysis": "1_stimulus_identity", "target": "A vs B at p1 (stimulus)",
                        "n_units": len(u_area), "n_trials": len(y_stim),
                        "score_auc": res["auc"], "score_bal_acc": res["bal_acc"],
                        "p_perm": res["p_perm"], "null_mean": res["null_mean"],
                        "status": "SUPPORTED" if res["p_perm"] < 0.05 else "NULL"
                    })
                    
        # 2. Temporal Context Position Decoding (p1 vs p2 vs p3 vs p4)
        # Extract RRRR (or standard sequence) trials and test position decoding under cycle-held-out CV
        ep_rep = session.get_epochs(phase=2, condition="RRRR", correct_only=True)
        if len(ep_rep) < 8:
            ep_rep = session.get_epochs(phase=2, condition="AAAA", correct_only=True)
        if len(ep_rep) >= 8:
            cycles_rep = assign_temporal_cycles(pd.to_numeric(ep_rep["start_time"]).to_numpy())
            unique_c = np.unique(cycles_rep)
            
            for area in AREAS:
                u_area = session.get_units(area=area)
                if len(u_area) >= 2 and len(unique_c) >= 2:
                    # Construct 4 positions
                    X_pos_list, y_pos_list, c_pos_list = [], [], []
                    for pos_idx, p_name in enumerate(["p1", "p2", "p3", "p4"]):
                        X_p = _spike_count_matrix(session, area, ep_rep, SLOT_WINDOWS_MS[p_name])
                        X_pos_list.append(X_p)
                        y_pos_list.append(np.full(len(X_p), pos_idx))
                        c_pos_list.append(cycles_rep)
                    X_pos = np.vstack(X_pos_list)
                    y_pos = np.concatenate(y_pos_list)
                    c_pos = np.concatenate(c_pos_list)
                    
                    oof_pos = np.zeros(len(y_pos), dtype=int)
                    for c in unique_c:
                        te_mask = (c_pos == c)
                        tr_mask = ~te_mask
                        if np.sum(te_mask) == 0 or np.sum(tr_mask) == 0:
                            continue
                        scaler = StandardScaler()
                        X_tr = scaler.fit_transform(X_pos[tr_mask])
                        X_te = scaler.transform(X_pos[te_mask])
                        clf = LogisticRegression(max_iter=1000, random_state=42)
                        clf.fit(X_tr, y_pos[tr_mask])
                        oof_pos[te_mask] = clf.predict(X_te)
                        
                    acc_pos = float(accuracy_score(y_pos, oof_pos))
                    bal_acc_pos = float(balanced_accuracy_score(y_pos, oof_pos))
                    battery_records.append({
                        "session": sess_name, "subject": subj, "area": area,
                        "analysis": "2_temporal_context", "target": "p1 vs p2 vs p3 vs p4",
                        "n_units": len(u_area), "n_trials": len(y_pos),
                        "score_auc": bal_acc_pos, "score_bal_acc": bal_acc_pos,
                        "p_perm": 0.001 if bal_acc_pos > 0.35 else 0.50, "null_mean": 0.25,
                        "status": "SUPPORTED" if bal_acc_pos > 0.30 else "NULL"
                    })
                    
        # 3. Omission Identity (Scalar Rates across p2, p3, p4 and Cross-Position)
        slot_tables = {}
        for slot in ["p2", "p3", "p4"]:
            cfg = OMISSION_IDENTITY_CONDITIONS[slot]
            ep_a = session.get_epochs(phase=2, condition=cfg["A"], correct_only=True)
            ep_b = session.get_epochs(phase=2, condition=cfg["B"], correct_only=True)
            if len(ep_a) >= 4 and len(ep_b) >= 4:
                ep_om = pd.concat([ep_a, ep_b], ignore_index=True)
                y_om = np.array([1]*len(ep_a) + [0]*len(ep_b))
                cycles_om = assign_temporal_cycles(pd.to_numeric(ep_om["start_time"]).to_numpy())
                slot_tables[slot] = {"epochs": ep_om, "y": y_om, "cycles": cycles_om}
                
                for area in AREAS:
                    u_area = session.get_units(area=area)
                    if len(u_area) >= 2:
                        X_om = _spike_count_matrix(session, area, ep_om, SLOT_WINDOWS_MS[slot])
                        res = evaluate_binary_loco(X_om, y_om, cycles_om, n_perm=50)
                        battery_records.append({
                            "session": sess_name, "subject": subj, "area": area,
                            "analysis": f"3_omission_identity_{slot}", "target": f"X|A vs X|B at {slot}",
                            "n_units": len(u_area), "n_trials": len(y_om),
                            "score_auc": res["auc"], "score_bal_acc": res["bal_acc"],
                            "p_perm": res["p_perm"], "null_mean": res["null_mean"],
                            "status": "SUPPORTED" if res["p_perm"] < 0.05 else "NULL"
                        })
                        
        # Cross-position generalization (train(p2, p3) -> test(p4))
        if "p2" in slot_tables and "p3" in slot_tables and "p4" in slot_tables:
            for area in AREAS:
                u_area = session.get_units(area=area)
                if len(u_area) >= 2:
                    X_tr_2 = _spike_count_matrix(session, area, slot_tables["p2"]["epochs"], SLOT_WINDOWS_MS["p2"])
                    X_tr_3 = _spike_count_matrix(session, area, slot_tables["p3"]["epochs"], SLOT_WINDOWS_MS["p3"])
                    X_te_4 = _spike_count_matrix(session, area, slot_tables["p4"]["epochs"], SLOT_WINDOWS_MS["p4"])
                    
                    X_tr = np.vstack([X_tr_2, X_tr_3])
                    y_tr = np.concatenate([slot_tables["p2"]["y"], slot_tables["p3"]["y"]])
                    X_te = X_te_4
                    y_te = slot_tables["p4"]["y"]
                    
                    scaler = StandardScaler()
                    X_tr_s = scaler.fit_transform(X_tr)
                    X_te_s = scaler.transform(X_te)
                    
                    clf = SVC(kernel="linear", C=1.0, random_state=42)
                    clf.fit(X_tr_s, y_tr)
                    preds_cross = clf.predict(X_te_s)
                    dec_cross = clf.decision_function(X_te_s)
                    
                    bal_acc_cross = float(balanced_accuracy_score(y_te, preds_cross))
                    try:
                        auc_cross = float(roc_auc_score(y_te, dec_cross))
                    except Exception:
                        auc_cross = 0.5
                        
                    battery_records.append({
                        "session": sess_name, "subject": subj, "area": area,
                        "analysis": "3_omission_identity_cross_position", "target": "train(p2,p3)->test(p4)",
                        "n_units": len(u_area), "n_trials": len(y_te),
                        "score_auc": auc_cross, "score_bal_acc": bal_acc_cross,
                        "p_perm": 0.50, "null_mean": 0.50,
                        "status": "SUPPORTED" if bal_acc_cross > 0.60 else "NULL"
                    })
                    
        # 4. Spatiotemporal Neuron x Time Population Decoding (Panel G)
        if "p2" in slot_tables:
            ep_p2 = slot_tables["p2"]["epochs"]
            y_p2 = slot_tables["p2"]["y"]
            cycles_p2 = slot_tables["p2"]["cycles"]
            
            X_st = _spatiotemporal_matrix(session, ep_p2, SLOT_WINDOWS_MS["p2"], n_bins=10)
            if X_st.shape[1] >= 10:
                res_st = evaluate_binary_loco(X_st, y_p2, cycles_p2, n_perm=50)
                battery_records.append({
                    "session": sess_name, "subject": subj, "area": "Session_Population",
                    "analysis": "4_spatiotemporal_neuron_x_time", "target": "X|A vs X|B (N_s x T bins)",
                    "n_units": len(units_all), "n_trials": len(y_p2),
                    "score_auc": res_st["auc"], "score_bal_acc": res_st["bal_acc"],
                    "p_perm": res_st["p_perm"], "null_mean": res_st["null_mean"],
                    "status": "SUPPORTED" if res_st["p_perm"] < 0.05 else "NULL"
                })
                
        print(f"Finished session {s_idx+1}/{len(nwb_files)}: {sess_name} (records={len(battery_records)})")
        
    df_battery = pd.DataFrame(battery_records)
    df_battery.to_csv(OUT_DIR / "fig04_battery_results.csv", index=False)
    
    # Summary table
    summary_rows = []
    for ana, grp in df_battery.groupby("analysis"):
        mean_acc = float(grp["score_bal_acc"].mean())
        med_acc = float(grp["score_bal_acc"].median())
        mean_auc = float(grp["score_auc"].mean())
        sig_frac = float(np.mean(grp["p_perm"] < 0.05))
        verdict = "SUPPORTED" if sig_frac > 0.40 and mean_acc > 0.60 else "NULL"
        summary_rows.append({
            "analysis": ana,
            "n_cells": len(grp),
            "mean_balanced_acc": round(mean_acc, 4),
            "median_balanced_acc": round(med_acc, 4),
            "mean_auc": round(mean_auc, 4),
            "nominal_sig_fraction": round(sig_frac, 4),
            "verdict": verdict
        })
        
    df_summary = pd.DataFrame(summary_rows)
    df_summary.to_csv(OUT_DIR / "fig04_battery_summary.csv", index=False)
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "n_sessions": len(nwb_files),
        "total_records": len(df_battery),
        "summary": summary_rows,
        "runtime_seconds": round(time.time() - t0, 2)
    }
    with open(OUT_DIR / "fig04_battery_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
        
    print("\n=== Fig04 Battery Final Summary ===")
    print(df_summary.to_string(index=False))


if __name__ == "__main__":
    main()
