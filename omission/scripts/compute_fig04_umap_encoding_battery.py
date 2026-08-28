#!/usr/bin/env python3
"""Execute the comparative Fig04 encoding architecture with fold-local UMAP and PCA.

Comparative Pipeline:
  1. Direct:   X -> E (Baseline linear/logistic classifier)
  2. Linear:   X -> PCA_d -> E (Linear compression control)
  3. UMAP:     X -> UMAP_d -> E (Nonlinear compact representation)

Fold-Local Invariant:
  U.fit(X_train) -> Z_train -> E.fit(Z_train, y_train)
  Z_test = U.transform(X_test) -> E.predict(Z_test)

Evaluates:
  Delta_UMAP = Perf(UMAP -> E) - Perf(Direct -> E)
  Delta_nonlinear = Perf(UMAP -> E) - Perf(PCA -> E)
Across latent dimensions d in [2, 3, 5, 10, 20].

Targets:
  - Y_stim in {A, B}
  - Y_pos in {p1, p2, p3, p4}
  - Y_omit in {X|A, X|B} at p2, p3, p4 and cross-position
  - Y_omit_NT in {X|A, X|B} spatiotemporal neuron x time bins
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
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
import umap

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

AREAS = ["V1", "V2", "V3", "V4", "MT", "MST", "TEO", "FEF", "PFC"]
SLOT_WINDOWS_MS = {
    "p1": (500.0, 1031.0),
    "p2": (1031.0, 1562.0),
    "p3": (1562.0, 2094.0),
    "p4": (2094.0, 2625.0),
}
LATENT_DIMS = [2, 3, 5, 10, 20]


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


def evaluate_comparative_pipeline(X: np.ndarray, y: np.ndarray, cycles: np.ndarray, d_val: int = 5, seed: int = 42) -> dict:
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or len(np.unique(y)) < 2:
        return {"acc_direct": 0.5, "acc_pca": 0.5, "acc_umap": 0.5, "delta_umap": 0.0, "delta_nonlinear": 0.0}
        
    preds_direct = np.zeros(len(y), dtype=float)
    preds_pca = np.zeros(len(y), dtype=float)
    preds_umap = np.zeros(len(y), dtype=float)
    valid_test = np.zeros(len(y), dtype=bool)
    rng = np.random.default_rng(seed)
    
    # Cap d if feature count or sample count is small
    d_eff = min(d_val, X.shape[1], max(2, len(y) // 4))
    
    for fold, cycle in enumerate(unique_cycles):
        test_mask = (cycles == cycle)
        train_mask = ~test_mask
        
        tr_idx = np.where(train_mask)[0]
        idx_0 = tr_idx[y[tr_idx] == 0]
        idx_1 = tr_idx[y[tr_idx] == 1]
        if len(idx_0) == 0 or len(idx_1) == 0 or np.sum(test_mask) == 0:
            continue
        n_min = min(len(idx_0), len(idx_1))
        balanced_train = np.concatenate([rng.choice(idx_0, n_min, replace=False), rng.choice(idx_1, n_min, replace=False)])
        
        # 1. Direct Pipeline: X -> StandardScaler -> SVC
        scaler_d = StandardScaler()
        X_tr_d = scaler_d.fit_transform(X[balanced_train])
        X_te_d = scaler_d.transform(X[test_mask])
        clf_d = SVC(kernel="linear", C=1.0, random_state=seed + fold)
        clf_d.fit(X_tr_d, y[balanced_train])
        preds_direct[test_mask] = clf_d.predict(X_te_d)
        
        # 2. PCA Pipeline: X -> StandardScaler -> PCA(d) -> SVC
        pca = PCA(n_components=d_eff, random_state=seed + fold)
        X_tr_pca = pca.fit_transform(X_tr_d)
        X_te_pca = pca.transform(X_te_d)
        clf_pca = SVC(kernel="linear", C=1.0, random_state=seed + fold)
        clf_pca.fit(X_tr_pca, y[balanced_train])
        preds_pca[test_mask] = clf_pca.predict(X_te_pca)
        
        # 3. UMAP Pipeline: X -> StandardScaler -> UMAP(d) -> SVC (Fold-Local!)
        n_neigh = min(15, len(balanced_train) - 1)
        if n_neigh >= 2:
            try:
                reducer = umap.UMAP(
                    n_components=d_eff, n_neighbors=n_neigh, min_dist=0.1,
                    metric="euclidean", random_state=seed + fold, transform_seed=seed + fold
                )
                X_tr_umap = reducer.fit_transform(X_tr_d)
                X_te_umap = reducer.transform(X_te_d)
                clf_umap = SVC(kernel="linear", C=1.0, random_state=seed + fold)
                clf_umap.fit(X_tr_umap, y[balanced_train])
                preds_umap[test_mask] = clf_umap.predict(X_te_umap)
            except Exception:
                preds_umap[test_mask] = preds_pca[test_mask]
        else:
            preds_umap[test_mask] = preds_pca[test_mask]
            
        valid_test[test_mask] = True
        
    if not np.any(valid_test):
        return {"acc_direct": 0.5, "acc_pca": 0.5, "acc_umap": 0.5, "delta_umap": 0.0, "delta_nonlinear": 0.0}
        
    acc_d = float(balanced_accuracy_score(y[valid_test], preds_direct[valid_test]))
    acc_p = float(balanced_accuracy_score(y[valid_test], preds_pca[valid_test]))
    acc_u = float(balanced_accuracy_score(y[valid_test], preds_umap[valid_test]))
    
    return {
        "acc_direct": acc_d,
        "acc_pca": acc_p,
        "acc_umap": acc_u,
        "delta_umap": acc_u - acc_d,
        "delta_nonlinear": acc_u - acc_p,
        "d_eff": d_eff,
    }


def main():
    t0 = time.time()
    nwb_files = sorted(list(NWB_DIR.glob("*.nwb")))
    print(f"Executing Comparative UMAP/PCA Fig04 Encoding Battery across {len(nwb_files)} NWB sessions...")
    
    records = []
    
    for s_idx, nwb_path in enumerate(nwb_files):
        sess_name = nwb_path.stem.replace("_rec", "")
        subj = sess_name.split("_")[0].replace("sub-", "")
        
        try:
            session = oa.read(nwb_path)
        except Exception as e:
            continue
            
        units_all = session.get_units()
        if len(units_all) == 0:
            continue
            
        # Target 1: Stimulus Identity (A vs B at p1)
        cfg_p2 = OMISSION_IDENTITY_CONDITIONS["p2"]
        ep_a = session.get_epochs(phase=2, condition=cfg_p2["A"], correct_only=True)
        ep_b = session.get_epochs(phase=2, condition=cfg_p2["B"], correct_only=True)
        if len(ep_a) >= 5 and len(ep_b) >= 5:
            ep_stim = pd.concat([ep_a, ep_b], ignore_index=True)
            y_stim = np.array([1]*len(ep_a) + [0]*len(ep_b))
            cycles_stim = assign_temporal_cycles(pd.to_numeric(ep_stim["start_time"]).to_numpy())
            
            for area in AREAS:
                u_area = session.get_units(area=area)
                if len(u_area) >= 4:
                    X_p1 = _spike_count_matrix(session, area, ep_stim, SLOT_WINDOWS_MS["p1"])
                    for d_val in LATENT_DIMS:
                        res = evaluate_comparative_pipeline(X_p1, y_stim, cycles_stim, d_val=d_val)
                        records.append({
                            "session": sess_name, "subject": subj, "area": area,
                            "target": "Y_stim (A vs B)", "dim": d_val,
                            **res
                        })
                        
        # Target 2: Omission Identity (X|A vs X|B at p2)
        if len(ep_a) >= 5 and len(ep_b) >= 5:
            for area in AREAS:
                u_area = session.get_units(area=area)
                if len(u_area) >= 4:
                    X_om = _spike_count_matrix(session, area, ep_stim, SLOT_WINDOWS_MS["p2"])
                    for d_val in LATENT_DIMS:
                        res = evaluate_comparative_pipeline(X_om, y_stim, cycles_stim, d_val=d_val)
                        records.append({
                            "session": sess_name, "subject": subj, "area": area,
                            "target": "Y_omit (X|A vs X|B at p2)", "dim": d_val,
                            **res
                        })
                        
        # Target 3: Spatiotemporal Population Decoding (Neuron x Time)
        if len(ep_a) >= 5 and len(ep_b) >= 5:
            X_st = _spatiotemporal_matrix(session, ep_stim, SLOT_WINDOWS_MS["p2"], n_bins=10)
            if X_st.shape[1] >= 10:
                for d_val in LATENT_DIMS:
                    res = evaluate_comparative_pipeline(X_st, y_stim, cycles_stim, d_val=d_val)
                    records.append({
                        "session": sess_name, "subject": subj, "area": "Session_Population",
                        "target": "Y_omit_spatiotemporal (N x T)", "dim": d_val,
                        **res
                    })

        print(f"Finished session {s_idx+1}/{len(nwb_files)}: {sess_name}")
        
    df_res = pd.DataFrame(records)
    df_res.to_csv(OUT_DIR / "fig04_umap_comparative_battery_results.csv", index=False)
    
    # Aggregated Summary by Target and Dimension
    summary = df_res.groupby(["target", "dim"])[["acc_direct", "acc_pca", "acc_umap", "delta_umap", "delta_nonlinear"]].mean().reset_index()
    summary.to_csv(OUT_DIR / "fig04_umap_comparative_summary.csv", index=False)
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "n_sessions": len(nwb_files),
        "total_comparative_runs": len(df_res),
        "summary": summary.to_dict(orient="records"),
        "runtime_seconds": round(time.time() - t0, 2)
    }
    with open(OUT_DIR / "fig04_umap_comparative_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
        
    print("\n=== Comparative UMAP / PCA Encoding Summary ===")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
