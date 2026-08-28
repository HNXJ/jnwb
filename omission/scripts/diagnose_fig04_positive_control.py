#!/usr/bin/env python3
"""Diagnostic script to verify Fig04 positive-control A/B decoding and UMAP/PCA representation.

Audits:
  1. Canonical trial table & presented_identity (A vs B) in POSITIVE_CONTROL (0..531ms relative to p1).
  2. Class-conditional population PSTHs for A vs B.
  3. Time-resolved population matrix X in R^{N_trial x (N_units * N_t)} with N_t=10 bins (53ms each).
  4. Comparison of:
     - Direct SVC
     - PCA_d -> SVC
     - Fold-local UMAP_d -> SVC
     - Random Stratified CV vs LOCO CV
  5. 2D UMAP & PCA embeddings colored by A vs B.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
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
from omission.jnwb_ext.structured_identity import build_canonical_trial_table, POSITIVE_CONTROL

DIAG_DIR = OA_ROOT / "outputs" / "classification" / "fig04_diagnostics"
DIAG_DIR.mkdir(parents=True, exist_ok=True)


def extract_time_resolved_spikes(session, area: str, table: pd.DataFrame, window_ms: tuple[float, float], n_bins: int = 10):
    units = session.get_units(area=area)
    row_indices = list(units.index)
    onsets = table["start_time"].to_numpy(float)
    t_edges = np.linspace(window_ms[0]/1000.0, window_ms[1]/1000.0, n_bins + 1)
    
    # 3D: trials x units x bins
    X_3d = np.zeros((len(onsets), len(row_indices), n_bins), dtype=float)
    for u_col, row_idx in enumerate(row_indices):
        spikes = session.get_spike_times(row_idx)
        if spikes is not None and len(spikes) > 0:
            spikes = np.sort(np.asarray(spikes, dtype=float))
            for b in range(n_bins):
                lo_off = t_edges[b]
                hi_off = t_edges[b + 1]
                X_3d[:, u_col, b] = np.searchsorted(spikes, onsets + hi_off, side="right") - np.searchsorted(spikes, onsets + lo_off, side="left")
                
    # Flat 2D: trials x (units * bins)
    X_flat = X_3d.reshape(len(onsets), len(row_indices) * n_bins)
    # Rate 2D: trials x units (mean rate over window)
    X_rate = X_3d.sum(axis=2)
    return X_3d, X_flat, X_rate, units


def run_cv(X: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], model_type: str = "direct", d: int = 5):
    oof_preds = np.zeros(len(y), dtype=float)
    oof_decision = np.zeros(len(y), dtype=float)
    rng = np.random.default_rng(42)
    valid_test = np.zeros(len(y), dtype=bool)
    
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        idx_0 = train_idx[y[train_idx] == 0]
        idx_1 = train_idx[y[train_idx] == 1]
        if len(idx_0) == 0 or len(idx_1) == 0:
            continue
        n_min = min(len(idx_0), len(idx_1))
        bal_train = np.concatenate([rng.choice(idx_0, n_min, replace=False), rng.choice(idx_1, n_min, replace=False)])
        
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[bal_train])
        X_te = scaler.transform(X[test_idx])
        
        if model_type == "direct":
            clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
            clf.fit(X_tr, y[bal_train])
            oof_preds[test_idx] = clf.predict(X_te)
            oof_decision[test_idx] = clf.decision_function(X_te)
        elif model_type == "pca":
            d_eff = min(d, X_tr.shape[1], len(bal_train)-1)
            pca = PCA(n_components=d_eff, random_state=42 + fold)
            X_tr_pca = pca.fit_transform(X_tr)
            X_te_pca = pca.transform(X_te)
            clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
            clf.fit(X_tr_pca, y[bal_train])
            oof_preds[test_idx] = clf.predict(X_te_pca)
            oof_decision[test_idx] = clf.decision_function(X_te_pca)
        elif model_type == "umap":
            d_eff = min(d, X_tr.shape[1], len(bal_train)-1)
            n_neigh = min(15, len(bal_train)-1)
            reducer = umap.UMAP(n_components=d_eff, n_neighbors=n_neigh, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
            X_tr_u = reducer.fit_transform(X_tr)
            X_te_u = reducer.transform(X_te)
            clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
            clf.fit(X_tr_u, y[bal_train])
            oof_preds[test_idx] = clf.predict(X_te_u)
            oof_decision[test_idx] = clf.decision_function(X_te_u)
            
        valid_test[test_idx] = True
            
    if not np.any(valid_test):
        return 0.5, 0.5
    acc = float(balanced_accuracy_score(y[valid_test], oof_preds[valid_test]))
    try:
        auc = float(roc_auc_score(y[valid_test], oof_decision[valid_test]))
    except Exception:
        auc = 0.5
    return acc, auc


def main():
    nwb_files = list(Path("D:/nwb/omission").glob("*.nwb"))
    test_session_path = [p for p in nwb_files if "230816" in p.name][0]
    print(f"Testing positive-control A/B pipeline on: {test_session_path.name}")
    
    session = oa.read(test_session_path)
    table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
    pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy().reset_index(drop=True)
    
    print(f"POSITIVE_CONTROL trial count: {len(pc)}")
    print("Class distribution:", pc["presented_identity"].value_counts().to_dict())
    print("Columns in table:", pc.columns.tolist())
    
    y = (pc["presented_identity"] == "A").astype(int).to_numpy()
    cycles = pc["cycle"].astype(int).to_numpy()
    
    # 1. LOCO CV splits
    unique_cycles = np.unique(cycles)
    loco_splits = [(np.where(cycles != c)[0], np.where(cycles == c)[0]) for c in unique_cycles]
    
    # 2. Random Stratified 5-Fold CV splits
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    random_splits = list(skf.split(pc, y))
    
    results = []
    
    for area in ["V1", "V2", "MT", "MST", "FEF", "PFC"]:
        u_area = session.get_units(area=area)
        if len(u_area) < 2:
            continue
            
        X_3d, X_flat, X_rate, units = extract_time_resolved_spikes(session, area, pc, window_ms=(0.0, 531.0), n_bins=10)
        
        # Test Rate vs Time-Resolved Flat across CV schemes
        for rep_name, X_mat in [("Scalar_Rate", X_rate), ("Time_Resolved_NxT", X_flat)]:
            # LOCO CV
            acc_dir_loco, auc_dir_loco = run_cv(X_mat, y, loco_splits, "direct")
            acc_pca_loco, auc_pca_loco = run_cv(X_mat, y, loco_splits, "pca", d=5)
            acc_umap_loco, auc_umap_loco = run_cv(X_mat, y, loco_splits, "umap", d=5)
            
            # Random CV (diagnostic)
            acc_dir_rand, auc_dir_rand = run_cv(X_mat, y, random_splits, "direct")
            acc_pca_rand, auc_pca_rand = run_cv(X_mat, y, random_splits, "pca", d=5)
            acc_umap_rand, auc_umap_rand = run_cv(X_mat, y, random_splits, "umap", d=5)
            
            results.append({
                "area": area, "n_units": len(units), "rep": rep_name,
                "loco_dir_acc": round(acc_dir_loco, 3), "loco_dir_auc": round(auc_dir_loco, 3),
                "loco_pca5_acc": round(acc_pca_loco, 3), "loco_umap5_acc": round(acc_umap_loco, 3),
                "rand_dir_acc": round(acc_dir_rand, 3), "rand_dir_auc": round(auc_dir_rand, 3),
                "rand_pca5_acc": round(acc_pca_rand, 3), "rand_umap5_acc": round(acc_umap_rand, 3),
            })
            
    df_res = pd.DataFrame(results)
    print("\n=== Positive Control A vs B Diagnostic Results ===")
    print(df_res.to_string(index=False))
    
    # 3. Plot 2D UMAP and PCA embeddings for V1 time-resolved
    X_3d_v1, X_flat_v1, X_rate_v1, u_v1 = extract_time_resolved_spikes(session, "V1", pc, window_ms=(0.0, 531.0), n_bins=10)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_flat_v1)
    
    pca_2d = PCA(n_components=2, random_state=42).fit_transform(X_scaled)
    umap_2d = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1, random_state=42).fit_transform(X_scaled)
    
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
    for cls, label, col in [(1, "Stimulus A", "#1f77b4"), (0, "Stimulus B", "#ff7f0e")]:
        mask = (y == cls)
        axes[0].scatter(pca_2d[mask, 0], pca_2d[mask, 1], label=label, color=col, alpha=0.8, s=40)
        axes[1].scatter(umap_2d[mask, 0], umap_2d[mask, 1], label=label, color=col, alpha=0.8, s=40)
        
    axes[0].set_title("V1 Stimulus Response (PCA 2D)")
    axes[0].set_xlabel("PC 1")
    axes[0].set_ylabel("PC 2")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    axes[1].set_title("V1 Stimulus Response (UMAP 2D)")
    axes[1].set_xlabel("UMAP 1")
    axes[1].set_ylabel("UMAP 2")
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    
    fig.tight_layout()
    plot_path = DIAG_DIR / "v1_stimulus_positive_control_embeddings.png"
    fig.savefig(plot_path, dpi=120)
    plt.close(fig)
    print(f"\nSaved diagnostic embedding plot to {plot_path}")


if __name__ == "__main__":
    main()
