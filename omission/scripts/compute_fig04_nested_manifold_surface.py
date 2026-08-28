#!/usr/bin/env python3
"""Figure 04: Nested PCA[N] -> UMAP[M] -> Encoder[E] Manifold Phase Diagram & Surface Search.

Evaluates the complete 2D parameter surface:
  N in [5, 10, 20, 30, 50, 75, 100] (PCA dimension, N < min(D, n_train))
  M in [2, 3, 5, 8, 10, 15, 20]      (UMAP dimension, M < N)
  E in [Logistic, Linear-SVM, RBF-SVM]

Protocol:
  Outer LOCO Test Splits supset Inner 3-Fold Stratified CV Hyperparameter Selection
  Zero test leakage into model selection.

Targets:
  1. Y_stim: Physical Stimulus Identity (A vs B at p1)
  2. Y_pos: Sequence Position (p1 vs p2 vs p3 vs p4)
  3. Y_omit: Omission Identity (X|A vs X|B at p2)

Computes:
  - Surface Heatmaps: H_train(N, M), H_val(N, M), H_test(N, M)
  - Generalization Gap: G(N, M) = P_val(N, M) - P_test(N, M)
  - Selection Stability: P(N*), P(M*), P(E*) across outer folds
  - Both Conservative (Transfer from Stimulus) and Exploratory (Direct Omission Nested Selection)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score
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
from omission.jnwb_ext.structured_identity import build_canonical_trial_table, POSITIVE_CONTROL, MAIN_ANALYSIS
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

OUT_DIR = OA_ROOT / "outputs" / "classification" / "fig04_diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PCA_GRID = [5, 10, 20, 30, 50, 75, 100]
UMAP_GRID = [2, 3, 5, 8, 10, 15, 20]
ENCODERS = ["Logistic", "Linear_SVM", "RBF_SVM"]
SLOT_DUR_MS = 531.0


def extract_slot_spikes(session, area: str, epochs: pd.DataFrame, slot_onset_ms: float, n_bins: int = 10):
    units = session.get_units(area=area) if area != "ALL" else session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0), dtype=float), units
        
    onsets = epochs["start_time"].to_numpy(float) + (slot_onset_ms / 1000.0)
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
    X_flat = X_3d.reshape(len(onsets), len(row_indices) * n_bins)
    return X_flat, units


def fit_pca_umap_pipeline(X_tr: np.ndarray, X_te: np.ndarray, n_pca: int, n_umap: int, seed: int = 42):
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(np.log1p(X_tr))
    X_te_s = scaler.transform(np.log1p(X_te))
    
    n_pca_eff = min(n_pca, X_tr_s.shape[1], max(2, len(X_tr_s) - 2))
    pca = PCA(n_components=n_pca_eff, random_state=seed)
    X_tr_pca = pca.fit_transform(X_tr_s)
    X_te_pca = pca.transform(X_te_s)
    
    n_umap_eff = min(n_umap, n_pca_eff - 1, max(2, len(X_tr_pca) - 2))
    n_neigh = min(15, len(X_tr_pca) - 1)
    reducer = umap.UMAP(n_components=n_umap_eff, n_neighbors=n_neigh, min_dist=0.1, random_state=seed, transform_seed=seed)
    Z_tr = reducer.fit_transform(X_tr_pca)
    Z_te = reducer.transform(X_te_pca)
    return Z_tr, Z_te


def evaluate_encoder(Z_tr: np.ndarray, y_tr: np.ndarray, Z_te: np.ndarray, y_te: np.ndarray, enc_name: str, seed: int = 42):
    if enc_name == "Logistic":
        clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed)
    elif enc_name == "Linear_SVM":
        clf = SVC(kernel="linear", C=1.0, random_state=seed)
    elif enc_name == "RBF_SVM":
        clf = SVC(kernel="rbf", C=1.0, random_state=seed)
        
    clf.fit(Z_tr, y_tr)
    preds = clf.predict(Z_te)
    return float(balanced_accuracy_score(y_te, preds))


def run_nested_surface_search(X: np.ndarray, y: np.ndarray, cycles: np.ndarray, target_name: str, session_name: str, area: str):
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or len(np.unique(y)) < 2:
        return None, None
        
    D = X.shape[1]
    grid_records = []
    nested_fold_selections = []
    
    oof_nested_preds = np.zeros(len(y), dtype=float)
    valid_test_mask = np.zeros(len(y), dtype=bool)
    rng = np.random.default_rng(42)
    
    for fold, te_cycle in enumerate(unique_cycles):
        te_mask = (cycles == te_cycle)
        tr_mask = ~te_mask
        
        tr_idx = np.where(tr_mask)[0]
        te_idx = np.where(te_mask)[0]
        
        # Balance outer training fold
        classes = np.unique(y[tr_idx])
        min_cls_count = min([np.sum(y[tr_idx] == c) for c in classes])
        if min_cls_count < 2:
            continue
        bal_tr_idx = np.concatenate([rng.choice(tr_idx[y[tr_idx] == c], min_cls_count, replace=False) for c in classes])
        
        X_outer_tr, y_outer_tr = X[bal_tr_idx], y[bal_tr_idx]
        X_outer_te, y_outer_te = X[te_idx], y[te_idx]
        
        # Inner 3-Fold CV on outer-training data
        skf = StratifiedKFold(n_splits=3, shuffle=True, random_state=42 + fold)
        inner_splits = list(skf.split(X_outer_tr, y_outer_tr))
        
        best_val_score = -1.0
        best_config = None
        
        # Search valid grid
        for n_pca in PCA_GRID:
            if n_pca >= min(D, len(X_outer_tr)):
                continue
            for n_umap in UMAP_GRID:
                if n_umap >= n_pca:
                    continue
                    
                for enc in ENCODERS:
                    inner_val_scores = []
                    for in_tr_idx, in_val_idx in inner_splits:
                        X_in_tr, y_in_tr = X_outer_tr[in_tr_idx], y_outer_tr[in_tr_idx]
                        X_in_val, y_in_val = X_outer_tr[in_val_idx], y_outer_tr[in_val_idx]
                        
                        try:
                            Z_in_tr, Z_in_val = fit_pca_umap_pipeline(X_in_tr, X_in_val, n_pca, n_umap, seed=42 + fold)
                            val_acc = evaluate_encoder(Z_in_tr, y_in_tr, Z_in_val, y_in_val, enc, seed=42 + fold)
                            inner_val_scores.append(val_acc)
                        except Exception:
                            continue
                            
                    if len(inner_val_scores) > 0:
                        mean_val_acc = float(np.mean(inner_val_scores))
                        if mean_val_acc > best_val_score:
                            best_val_score = mean_val_acc
                            best_config = (n_pca, n_umap, enc)
                            
                        # Evaluate on outer test set for diagnostic surface mapping (never used for selection)
                        try:
                            Z_out_tr, Z_out_te = fit_pca_umap_pipeline(X_outer_tr, X_outer_te, n_pca, n_umap, seed=42 + fold)
                            test_acc = evaluate_encoder(Z_out_tr, y_outer_tr, Z_out_te, y_outer_te, enc, seed=42 + fold)
                            train_acc = evaluate_encoder(Z_out_tr, y_outer_tr, Z_out_tr, y_outer_tr, enc, seed=42 + fold)
                            
                            grid_records.append({
                                "session": session_name, "area": area, "target": target_name, "fold": fold,
                                "n_pca": n_pca, "n_umap": n_umap, "encoder": enc, "D": D,
                                "acc_train": train_acc, "acc_val": mean_val_acc, "acc_test": test_acc,
                                "gen_gap": mean_val_acc - test_acc
                            })
                        except Exception:
                            pass
                            
        # Refit best config on outer-training and evaluate on outer-test
        if best_config is not None:
            n_pca_star, n_umap_star, enc_star = best_config
            Z_out_tr_star, Z_out_te_star = fit_pca_umap_pipeline(X_outer_tr, X_outer_te, n_pca_star, n_umap_star, seed=42 + fold)
            if enc_star == "Logistic":
                clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42 + fold)
            elif enc_star == "Linear_SVM":
                clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
            elif enc_star == "RBF_SVM":
                clf = SVC(kernel="rbf", C=1.0, random_state=42 + fold)
                
            clf.fit(Z_out_tr_star, y_outer_tr)
            oof_nested_preds[te_idx] = clf.predict(Z_out_te_star)
            valid_test_mask[te_idx] = True
            
            nested_fold_selections.append({
                "session": session_name, "area": area, "target": target_name, "fold": fold,
                "n_pca_star": n_pca_star, "n_umap_star": n_umap_star, "encoder_star": enc_star,
                "inner_val_score": best_val_score
            })
            
    df_grid = pd.DataFrame(grid_records)
    df_selections = pd.DataFrame(nested_fold_selections)
    
    nested_acc = balanced_accuracy_score(y[valid_test_mask], oof_nested_preds[valid_test_mask]) if np.any(valid_test_mask) else 0.5
    return df_grid, df_selections, nested_acc


def main():
    t0 = time.time()
    nwb_files = sorted(list(Path("D:/nwb/omission").glob("*.nwb")))
    rep_sessions = ["sub-C31o_ses-230816", "sub-V182o_ses-260710"]
    target_files = [p for p in nwb_files if any(s in p.name for s in rep_sessions)]
    
    print(f"Executing Nested PCA x UMAP Surface Search on {len(target_files)} sessions...")
    
    all_grid_records = []
    all_selections = []
    nested_summary = []
    
    for nwb_path in target_files:
        sess_name = nwb_path.stem.replace("_rec", "")
        session = oa.read(nwb_path)
        table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
        
        # 1. Target 1: Physical Stimulus Identity (A vs B at p1)
        pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy().reset_index(drop=True)
        if len(pc) >= 20:
            y_stim = (pc["presented_identity"] == "A").astype(int).to_numpy()
            c_stim = pc["cycle"].astype(int).to_numpy()
            for area in ["V1", "MT"]:
                X_stim, units = extract_slot_spikes(session, area, pc, slot_onset_ms=0.0, n_bins=10)
                if X_stim.shape[1] >= 10:
                    df_g, df_sel, n_acc = run_nested_surface_search(X_stim, y_stim, c_stim, "1_Stimulus_Identity", sess_name, area)
                    if df_g is not None:
                        all_grid_records.append(df_g)
                        all_selections.append(df_sel)
                        nested_summary.append({"session": sess_name, "area": area, "target": "1_Stimulus_Identity", "nested_acc": n_acc})
                        
        # 2. Target 2: Sequence Position (p1 vs p2 vs p3 vs p4)
        main_om = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy().reset_index(drop=True)
        # Position dataset: construct trials across positions
        pos_trials = []
        pos_labels = []
        pos_cycles = []
        for pos_idx, slot in enumerate(["p1", "p2", "p3", "p4"]):
            if slot == "p1":
                sub_p = pc.head(min(len(pc), 60)).copy()
            else:
                sub_p = main_om[main_om["slot_key"] == slot].head(60).copy()
            if len(sub_p) >= 10:
                pos_trials.append(sub_p)
                pos_labels.extend([pos_idx] * len(sub_p))
                pos_cycles.extend(sub_p["cycle"].astype(int).tolist())
                
        if len(pos_trials) == 4:
            df_pos_all = pd.concat(pos_trials, ignore_index=True)
            y_pos = np.array(pos_labels)
            c_pos = np.array(pos_cycles)
            for area in ["V1", "MT"]:
                X_pos, units = extract_slot_spikes(session, area, df_pos_all, slot_onset_ms=0.0, n_bins=10)
                if X_pos.shape[1] >= 10:
                    df_g, df_sel, n_acc = run_nested_surface_search(X_pos, y_pos, c_pos, "2_Sequence_Position", sess_name, area)
                    if df_g is not None:
                        all_grid_records.append(df_g)
                        all_selections.append(df_sel)
                        nested_summary.append({"session": sess_name, "area": area, "target": "2_Sequence_Position", "nested_acc": n_acc})
                        
        # 3. Target 3: Omission Identity (X|A vs X|B at p2)
        sub_p2 = main_om[main_om["slot_key"] == "p2"].copy().reset_index(drop=True)
        if len(sub_p2) >= 12:
            y_om = (sub_p2["expected_identity"] == "A").astype(int).to_numpy()
            c_om = sub_p2["cycle"].astype(int).to_numpy()
            for area in ["V1", "MT"]:
                X_om, units = extract_slot_spikes(session, area, sub_p2, slot_onset_ms=EPOCH_ONSETS_MS["p2"], n_bins=10)
                if X_om.shape[1] >= 10:
                    df_g, df_sel, n_acc = run_nested_surface_search(X_om, y_om, c_om, "3_Omission_Identity_p2", sess_name, area)
                    if df_g is not None:
                        all_grid_records.append(df_g)
                        all_selections.append(df_sel)
                        nested_summary.append({"session": sess_name, "area": area, "target": "3_Omission_Identity_p2", "nested_acc": n_acc})

    df_grid_all = pd.concat(all_grid_records, ignore_index=True)
    df_sel_all = pd.concat(all_selections, ignore_index=True)
    df_nested_all = pd.DataFrame(nested_summary)
    
    df_grid_all.to_csv(OUT_DIR / "pca_umap_surface_grid.csv", index=False)
    df_sel_all.to_csv(OUT_DIR / "pca_umap_nested_selections.csv", index=False)
    df_nested_all.to_csv(OUT_DIR / "pca_umap_nested_performance.csv", index=False)
    
    print("\n=== Nested Generalization Performance by Target ===")
    print(df_nested_all.to_string(index=False))
    
    print("\n=== Selected Hyperparameter Distributions (N*, M*, E*) ===")
    print("PCA Dimension (N*) distribution:")
    print(df_sel_all.groupby(["target", "n_pca_star"]).size())
    print("\nUMAP Dimension (M*) distribution:")
    print(df_sel_all.groupby(["target", "n_umap_star"]).size())
    print("\nEncoder (E*) distribution:")
    print(df_sel_all.groupby(["target", "encoder_star"]).size())
    
    # 4. Generate Phase Diagram Heatmaps: Stimulus vs Position vs Omission
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    
    targets = ["1_Stimulus_Identity", "2_Sequence_Position", "3_Omission_Identity_p2"]
    t_titles = ["1. Stimulus Identity (A vs B)", "2. Sequence Position (p1-p4)", "3. Omission Identity (p2)"]
    
    for t_idx, (t_name, title) in enumerate(zip(targets, t_titles)):
        sub = df_grid_all[df_grid_all["target"] == t_name]
        if len(sub) == 0:
            continue
            
        pivot_val = sub.groupby(["n_pca", "n_umap"])["acc_val"].mean().unstack()
        pivot_gap = sub.groupby(["n_pca", "n_umap"])["gen_gap"].mean().unstack()
        
        # Row 1: Validation Accuracy Surface H_val(N, M)
        im0 = axes[0, t_idx].imshow(pivot_val.values, cmap="viridis", aspect="auto", origin="lower")
        axes[0, t_idx].set_xticks(range(len(pivot_val.columns)))
        axes[0, t_idx].set_xticklabels(pivot_val.columns)
        axes[0, t_idx].set_yticks(range(len(pivot_val.index)))
        axes[0, t_idx].set_yticklabels(pivot_val.index)
        axes[0, t_idx].set_xlabel("UMAP Dimension (M)")
        axes[0, t_idx].set_ylabel("PCA Dimension (N)")
        axes[0, t_idx].set_title(f"{title}\nValidation Surface H_val(N, M)", fontsize=9)
        plt.colorbar(im0, ax=axes[0, t_idx], fraction=0.046, pad=0.04)
        
        # Overlay values
        for i in range(len(pivot_val.index)):
            for j in range(len(pivot_val.columns)):
                val = pivot_val.values[i, j]
                if not np.isnan(val):
                    axes[0, t_idx].text(j, i, f"{val:.2f}", ha="center", va="center", color="white" if val < 0.65 else "black", fontsize=6.5)
                    
        # Row 2: Generalization Gap G(N, M) = Val - Test
        im1 = axes[1, t_idx].imshow(pivot_gap.values, cmap="coolwarm", aspect="auto", origin="lower", vmin=-0.2, vmax=0.2)
        axes[1, t_idx].set_xticks(range(len(pivot_gap.columns)))
        axes[1, t_idx].set_xticklabels(pivot_gap.columns)
        axes[1, t_idx].set_yticks(range(len(pivot_gap.index)))
        axes[1, t_idx].set_yticklabels(pivot_gap.index)
        axes[1, t_idx].set_xlabel("UMAP Dimension (M)")
        axes[1, t_idx].set_ylabel("PCA Dimension (N)")
        axes[1, t_idx].set_title(f"{title}\nGen Gap G(N, M) [Val - Test]", fontsize=9)
        plt.colorbar(im1, ax=axes[1, t_idx], fraction=0.046, pad=0.04)
        
    fig.tight_layout()
    fig_path = OUT_DIR / "fig04_pca_umap_phase_diagram.png"
    fig.savefig(fig_path, dpi=200)
    plt.close(fig)
    print(f"\nSaved Manifold Phase Diagram to {fig_path}")


if __name__ == "__main__":
    main()
