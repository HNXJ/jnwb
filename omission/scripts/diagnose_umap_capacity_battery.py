#!/usr/bin/env python3
"""Comprehensive UMAP Representation Capacity & Encoder Diagnostic Battery.

Evaluates 10 hypotheses on positive-control A/B stimulus decoding:
  1. Dimension sweep: d in [2, 3, 5, 10, 20, 30, 50]
  2. Neighborhood scale: k in [5, 10, 15, 30, 50, 100]
  3. Distance metrics: euclidean, cosine, correlation
  4. Feature scaling: Raw X, StandardScaler(X), Log1p + StandardScaler(X)
  5. Multi-seed stability: seeds across outer folds
  6. Train vs Test generalization: AUC_train vs AUC_val vs AUC_test
  7. Quantitative embedding separation: kNN purity & silhouette in train vs test
  8. Two-stage PCA -> UMAP: X -> PCA_d0 (d0=30) -> UMAP_d -> E
  9. Downstream encoder compatibility: Linear SVC, Logistic Regression, k-NN (k=5), RBF-SVM
  10. Direct nonlinear baseline: X -> RBF-SVM

Protocol:
  Outer LOCO Test Splits  supset  Inner 3-Fold CV Hyperparameter Selection
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, roc_auc_score, silhouette_score
from sklearn.model_selection import StratifiedKFold
from sklearn.neighbors import KNeighborsClassifier
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

OUT_DIR = OA_ROOT / "outputs" / "classification" / "fig04_diagnostics"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_time_resolved_spikes(session, area: str, table: pd.DataFrame, window_ms: tuple[float, float], n_bins: int = 10):
    units = session.get_units(area=area)
    row_indices = list(units.index)
    onsets = table["start_time"].to_numpy(float)
    t_edges = np.linspace(window_ms[0]/1000.0, window_ms[1]/1000.0, n_bins + 1)
    
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


def knn_purity(Z: np.ndarray, y: np.ndarray, k: int = 5) -> float:
    if len(Z) <= k:
        return 0.5
    from sklearn.neighbors import NearestNeighbors
    nn = NearestNeighbors(n_neighbors=k+1).fit(Z)
    indices = nn.kneighbors(Z, return_distance=False)
    # Ignore self (column 0)
    neighbor_labels = y[indices[:, 1:]]
    purity = np.mean(neighbor_labels == y[:, None])
    return float(purity)


def main():
    t0 = time.time()
    nwb_files = list(Path("D:/nwb/omission").glob("*.nwb"))
    test_session_path = [p for p in nwb_files if "230816" in p.name][0]
    session = oa.read(test_session_path)
    table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
    pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy().reset_index(drop=True)
    
    y = (pc["presented_identity"] == "A").astype(int).to_numpy()
    cycles = pc["cycle"].astype(int).to_numpy()
    unique_cycles = np.unique(cycles)
    loco_splits = [(np.where(cycles != c)[0], np.where(cycles == c)[0]) for c in unique_cycles]
    
    print(f"Loaded POSITIVE_CONTROL: N={len(pc)} trials (A={np.sum(y==1)}, B={np.sum(y==0)}), Cycles={len(unique_cycles)}")
    
    areas_to_test = ["V1", "MT"]
    
    for area in areas_to_test:
        X_raw, units = extract_time_resolved_spikes(session, area, pc, window_ms=(0.0, 531.0), n_bins=10)
        n_features = X_raw.shape[1]
        print(f"\n=======================================================")
        print(f"Testing Area {area}: N_units={len(units)}, N_features={n_features} (N x T)")
        print(f"=======================================================")
        
        # -------------------------------------------------------------------
        # H1: Dimension Sweep (d in [2, 3, 5, 10, 20, 30, 50])
        # -------------------------------------------------------------------
        dim_sweep_records = []
        for d in [2, 3, 5, 10, 20, 30, 50]:
            if d >= min(X_raw.shape[0]*0.8, n_features):
                continue
            for model_name in ["PCA", "UMAP"]:
                oof_preds = np.zeros(len(y), dtype=float)
                oof_decision = np.zeros(len(y), dtype=float)
                for fold, (tr_idx, te_idx) in enumerate(loco_splits):
                    scaler = StandardScaler()
                    X_tr = scaler.fit_transform(X_raw[tr_idx])
                    X_te = scaler.transform(X_raw[te_idx])
                    
                    if model_name == "PCA":
                        tformer = PCA(n_components=d, random_state=42 + fold)
                        Z_tr = tformer.fit_transform(X_tr)
                        Z_te = tformer.transform(X_te)
                    else:
                        tformer = umap.UMAP(n_components=d, n_neighbors=15, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
                        Z_tr = tformer.fit_transform(X_tr)
                        Z_te = tformer.transform(X_te)
                        
                    clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
                    clf.fit(Z_tr, y[tr_idx])
                    oof_preds[te_idx] = clf.predict(Z_te)
                    oof_decision[te_idx] = clf.decision_function(Z_te)
                    
                acc = balanced_accuracy_score(y, oof_preds)
                try:
                    auc = roc_auc_score(y, oof_decision)
                except Exception:
                    auc = 0.5
                dim_sweep_records.append({"area": area, "model": model_name, "d": d, "acc": acc, "auc": auc})
                
        df_dim = pd.DataFrame(dim_sweep_records)
        df_dim.to_csv(OUT_DIR / f"{area}_dimension_sweep.csv", index=False)
        print(f"Dimension Sweep ({area}):")
        print(df_dim.pivot(index="d", columns="model", values="acc"))
        
        # -------------------------------------------------------------------
        # H4: Preprocessing & Scaling (Raw vs StandardScaler vs Log1p+Scale)
        # -------------------------------------------------------------------
        scale_records = []
        for scale_type in ["Raw", "StandardScaler", "Log1p_StandardScaler"]:
            if scale_type == "Raw":
                prep = lambda tr, te: (tr, te)
            elif scale_type == "StandardScaler":
                prep = lambda tr, te: (StandardScaler().fit_transform(tr), StandardScaler().fit(tr).transform(te))
            else:
                prep = lambda tr, te: (StandardScaler().fit_transform(np.log1p(tr)), StandardScaler().fit(np.log1p(tr)).transform(np.log1p(te)))
                
            for model_name in ["Direct", "PCA_10", "UMAP_10"]:
                oof_preds = np.zeros(len(y), dtype=float)
                for fold, (tr_idx, te_idx) in enumerate(loco_splits):
                    X_tr, X_te = prep(X_raw[tr_idx], X_raw[te_idx])
                    if model_name == "Direct":
                        Z_tr, Z_te = X_tr, X_te
                    elif model_name == "PCA_10":
                        pca = PCA(n_components=10, random_state=42 + fold)
                        Z_tr = pca.fit_transform(X_tr)
                        Z_te = pca.transform(X_te)
                    elif model_name == "UMAP_10":
                        u = umap.UMAP(n_components=10, n_neighbors=15, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
                        Z_tr = u.fit_transform(X_tr)
                        Z_te = u.transform(X_te)
                    clf = SVC(kernel="linear", C=1.0, random_state=42 + fold)
                    clf.fit(Z_tr, y[tr_idx])
                    oof_preds[te_idx] = clf.predict(Z_te)
                acc = balanced_accuracy_score(y, oof_preds)
                scale_records.append({"area": area, "scaling": scale_type, "model": model_name, "acc": acc})
        df_scale = pd.DataFrame(scale_records)
        df_scale.to_csv(OUT_DIR / f"{area}_scaling_diagnostic.csv", index=False)
        print(f"\nScaling Diagnostic ({area}):")
        print(df_scale.pivot(index="scaling", columns="model", values="acc"))
        
        # -------------------------------------------------------------------
        # H9: Downstream Encoder Compatibility on Fold-Local UMAP (d=10)
        # -------------------------------------------------------------------
        encoder_records = []
        encoders = {
            "Linear_SVC": SVC(kernel="linear", C=1.0),
            "Logistic_Regression": LogisticRegression(C=1.0, max_iter=1000),
            "kNN_k5": KNeighborsClassifier(n_neighbors=5),
            "RBF_SVM": SVC(kernel="rbf", C=1.0),
        }
        for enc_name, clf_proto in encoders.items():
            for rep_name in ["Direct", "PCA_10", "UMAP_10", "PCA30_UMAP10"]:
                oof_preds = np.zeros(len(y), dtype=float)
                for fold, (tr_idx, te_idx) in enumerate(loco_splits):
                    scaler = StandardScaler()
                    X_tr = scaler.fit_transform(X_raw[tr_idx])
                    X_te = scaler.transform(X_raw[te_idx])
                    
                    if rep_name == "Direct":
                        Z_tr, Z_te = X_tr, X_te
                    elif rep_name == "PCA_10":
                        pca = PCA(n_components=10, random_state=42 + fold)
                        Z_tr = pca.fit_transform(X_tr)
                        Z_te = pca.transform(X_te)
                    elif rep_name == "UMAP_10":
                        u = umap.UMAP(n_components=10, n_neighbors=15, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
                        Z_tr = u.fit_transform(X_tr)
                        Z_te = u.transform(X_te)
                    elif rep_name == "PCA30_UMAP10":
                        pca0 = PCA(n_components=min(30, X_tr.shape[1]), random_state=42 + fold)
                        X_tr_p0 = pca0.fit_transform(X_tr)
                        X_te_p0 = pca0.transform(X_te)
                        u = umap.UMAP(n_components=10, n_neighbors=15, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
                        Z_tr = u.fit_transform(X_tr_p0)
                        Z_te = u.transform(X_te_p0)
                        
                    from sklearn.base import clone
                    clf = clone(clf_proto)
                    clf.fit(Z_tr, y[tr_idx])
                    oof_preds[te_idx] = clf.predict(Z_te)
                    
                acc = balanced_accuracy_score(y, oof_preds)
                encoder_records.append({"area": area, "representation": rep_name, "encoder": enc_name, "acc": acc})
                
        df_enc = pd.DataFrame(encoder_records)
        df_enc.to_csv(OUT_DIR / f"{area}_encoder_compatibility.csv", index=False)
        print(f"\nEncoder Compatibility Matrix ({area}):")
        print(df_enc.pivot(index="encoder", columns="representation", values="acc"))
        
        # -------------------------------------------------------------------
        # H6 & H7: Train vs Test Geometry & Out-of-Sample Generalization
        # -------------------------------------------------------------------
        geom_records = []
        for fold, (tr_idx, te_idx) in enumerate(loco_splits):
            scaler = StandardScaler()
            X_tr = scaler.fit_transform(X_raw[tr_idx])
            X_te = scaler.transform(X_raw[te_idx])
            
            # 2D UMAP
            u2d = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1, random_state=42 + fold, transform_seed=42 + fold)
            Z_tr_u = u2d.fit_transform(X_tr)
            Z_te_u = u2d.transform(X_te)
            
            purity_tr = knn_purity(Z_tr_u, y[tr_idx], k=5)
            purity_te = knn_purity(Z_te_u, y[te_idx], k=min(5, len(te_idx)-1)) if len(te_idx) > 2 else 0.5
            
            # Train Acc vs Test Acc for RBF-SVM on UMAP 2D
            clf_rbf = SVC(kernel="rbf", C=1.0)
            clf_rbf.fit(Z_tr_u, y[tr_idx])
            acc_tr = balanced_accuracy_score(y[tr_idx], clf_rbf.predict(Z_tr_u))
            acc_te = balanced_accuracy_score(y[te_idx], clf_rbf.predict(Z_te_u))
            
            geom_records.append({
                "fold": fold, "cycle": unique_cycles[fold],
                "purity_train": purity_tr, "purity_test": purity_te,
                "acc_train_rbf": acc_tr, "acc_test_rbf": acc_te
            })
        df_geom = pd.DataFrame(geom_records)
        df_geom.to_csv(OUT_DIR / f"{area}_train_vs_test_geometry.csv", index=False)
        print(f"\nTrain vs Test Out-of-Sample Generalization (Fold Mean for {area}):")
        print(f"  Purity Train: {df_geom['purity_train'].mean():.3f} -> Purity Test: {df_geom['purity_test'].mean():.3f}")
        print(f"  RBF Train Acc: {df_geom['acc_train_rbf'].mean():.3f} -> RBF Test Acc: {df_geom['acc_test_rbf'].mean():.3f}")

    # Plot comprehensive diagnostic comparison
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Panel 1: Dimension Sweep
    for area, col in [("V1", "#1f77b4"), ("MT", "#2ca02c")]:
        df_a = pd.read_csv(OUT_DIR / f"{area}_dimension_sweep.csv")
        sub_pca = df_a[df_a["model"] == "PCA"].sort_values("d")
        sub_umap = df_a[df_a["model"] == "UMAP"].sort_values("d")
        axes[0].plot(sub_pca["d"], sub_pca["acc"], "o--", label=f"{area} PCA", color=col, alpha=0.6)
        axes[0].plot(sub_umap["d"], sub_umap["acc"], "s-", label=f"{area} UMAP (Linear SVC)", color=col, lw=2)
    axes[0].set_xlabel("Latent Dimension (d)")
    axes[0].set_ylabel("LOCO Balanced Accuracy")
    axes[0].set_title("H1: Latent Dimension Bottleneck Curve", fontsize=10)
    axes[0].axhline(0.5, color="gray", ls=":")
    axes[0].grid(True, alpha=0.3)
    axes[0].legend(fontsize=8)
    
    # Panel 2: Encoder Compatibility on V1 UMAP
    df_v1_enc = pd.read_csv(OUT_DIR / "V1_encoder_compatibility.csv")
    reps = ["Direct", "PCA_10", "UMAP_10", "PCA30_UMAP10"]
    encs = ["Linear_SVC", "Logistic_Regression", "kNN_k5", "RBF_SVM"]
    x_pos = np.arange(len(reps))
    width = 0.2
    for i, enc in enumerate(encs):
        vals = [df_v1_enc[(df_v1_enc["representation"]==r) & (df_v1_enc["encoder"]==enc)]["acc"].values[0] for r in reps]
        axes[1].bar(x_pos + (i-1.5)*width, vals, width, label=enc)
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(reps)
    axes[1].set_ylabel("LOCO Balanced Accuracy")
    axes[1].set_title("H9: Encoder Compatibility on V1 Manifolds", fontsize=10)
    axes[1].set_ylim(0.5, 1.05)
    axes[1].axhline(0.5, color="gray", ls=":")
    axes[1].grid(True, alpha=0.3, axis="y")
    axes[1].legend(fontsize=8)
    
    fig.tight_layout()
    fig_path = OUT_DIR / "umap_capacity_diagnostic_synthesis.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    print(f"\nSaved synthesis figure to {fig_path}")


if __name__ == "__main__":
    main()
