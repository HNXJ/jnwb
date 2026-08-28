#!/usr/bin/env python3
"""Run exact nested PCA -> UMAP -> Encoder on LFP-only, SPK-only, and SPK+LFP (Balanced Fusion).

Answers:
  1. Can LFP bandpower-time or spectral array encode X|A vs X|B via PCA -> UMAP?
  2. Can SPK + LFP balanced multimodal fusion encode X|A vs X|B via PCA -> UMAP?
  3. Compare against Positive Control (A vs B stimulus).

Outputs:
  - outputs/classification/lfp_multimodal_pca_umap_results.csv
  - outputs/classification/lfp_multimodal_pca_umap_receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
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
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from _l_lfp_common import extract_epoch_trials, resolve_area_channel_block
from precompute_tfr_arrays import p1_onsets_s
import jnwb.paths as P

OUT_DIR = OA_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BANDS = {
    "theta": (4.0, 8.0),
    "alpha": (8.0, 14.0),
    "beta": (15.0, 30.0),
    "low_gamma": (30.0, 50.0),
    "high_gamma": (50.0, 90.0),
}
EPOCH_WIN_S = (-0.6, 2.2)
MAX_TRIALS = 60
N_CH_WINDOW = 32
OMISSION_WIN_MS = (1031.0, 1562.0)
STIM_WIN_MS = (0.0, 531.0)


def compute_band_power_features(trials: np.ndarray, fs: float, win_ms: tuple[float, float]) -> np.ndarray:
    n_trials, n_ch, n_samples = trials.shape
    t_vec = np.arange(n_samples) / fs + EPOCH_WIN_S[0]
    mask = (t_vec >= win_ms[0] / 1000.0) & (t_vec <= win_ms[1] / 1000.0)
    seg = trials[:, :, mask]
    n_win = seg.shape[2]
    freqs = np.fft.rfftfreq(n_win, d=1.0/fs)
    fft_vals = np.fft.rfft(seg, axis=2)
    psd = (np.abs(fft_vals) ** 2) / (n_win * fs)
    psd_ch_mean = np.mean(psd, axis=1) # trials x freqs
    
    band_powers = []
    for b_name, (f_lo, f_hi) in BANDS.items():
        f_mask = (freqs >= f_lo) & (freqs <= f_hi)
        if not np.any(f_mask):
            f_mask = np.array([np.argmin(np.abs(freqs - (f_lo+f_hi)/2))])
        p_band = np.mean(psd_ch_mean[:, f_mask], axis=1)
        band_powers.append(p_band)
    p_arr = np.stack(band_powers, axis=1)
    return 10.0 * np.log10(np.maximum(p_arr, 1e-12))


def fit_pca_umap_encoder_cv(X: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], n_pca: int = 5, n_umap: int = 3, encoder_name: str = "Logistic", seed: int = 42):
    oof_preds = np.zeros(len(y), dtype=float)
    oof_probs = np.zeros(len(y), dtype=float)
    
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X[train_idx])
        X_te_s = scaler.transform(X[test_idx])
        
        # PCA
        d_p_eff = min(n_pca, X_tr_s.shape[1], max(2, len(train_idx) - 2))
        pca = PCA(n_components=d_p_eff, random_state=seed + fold)
        X_tr_pca = pca.fit_transform(X_tr_s)
        X_te_pca = pca.transform(X_te_s)
        
        # UMAP
        d_u_eff = min(n_umap, d_p_eff - 1, max(2, len(train_idx) - 2))
        n_neigh = min(15, len(train_idx) - 1)
        reducer = umap.UMAP(n_components=d_u_eff, n_neighbors=n_neigh, min_dist=0.1, random_state=seed + fold, transform_seed=seed + fold)
        Z_tr = reducer.fit_transform(X_tr_pca)
        Z_te = reducer.transform(X_te_pca)
        
        # Encoder
        if encoder_name == "Logistic":
            clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold)
        elif encoder_name == "Linear_SVM":
            clf = SVC(kernel="linear", C=1.0, probability=True, random_state=seed + fold)
        elif encoder_name == "RBF_SVM":
            clf = SVC(kernel="rbf", C=1.0, probability=True, random_state=seed + fold)
            
        clf.fit(Z_tr, y[train_idx])
        oof_preds[test_idx] = clf.predict(Z_te)
        if hasattr(clf, "predict_proba"):
            oof_probs[test_idx] = clf.predict_proba(Z_te)[:, 1]
        elif hasattr(clf, "decision_function"):
            oof_probs[test_idx] = clf.decision_function(Z_te)
            
    acc = float(balanced_accuracy_score(y, oof_preds))
    try:
        auc = float(roc_auc_score(y, oof_probs))
    except Exception:
        auc = acc
    return {"acc": acc, "auc": auc}


def fit_balanced_fusion_cv(X_S: np.ndarray, X_L: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], n_pca_S: int = 5, n_pca_L: int = 5, n_umap: int = 3, encoder_name: str = "Logistic", seed: int = 42):
    oof_preds = np.zeros(len(y), dtype=float)
    oof_probs = np.zeros(len(y), dtype=float)
    
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        # Scale separately
        scaler_S = StandardScaler()
        X_S_tr = scaler_S.fit_transform(np.log1p(np.maximum(0, X_S[train_idx])))
        X_S_te = scaler_S.transform(np.log1p(np.maximum(0, X_S[test_idx])))
        
        scaler_L = StandardScaler()
        X_L_tr = scaler_L.fit_transform(X_L[train_idx])
        X_L_te = scaler_L.transform(X_L[test_idx])
        
        # PCA on S
        d_S_eff = min(n_pca_S, X_S_tr.shape[1], max(2, len(train_idx) - 2))
        pca_S = PCA(n_components=d_S_eff, random_state=seed + fold)
        Z_S_tr = pca_S.fit_transform(X_S_tr)
        Z_S_te = pca_S.transform(X_S_te)
        
        # PCA on L
        d_L_eff = min(n_pca_L, X_L_tr.shape[1], max(2, len(train_idx) - 2))
        pca_L = PCA(n_components=d_L_eff, random_state=seed + fold)
        Z_L_tr = pca_L.fit_transform(X_L_tr)
        Z_L_te = pca_L.transform(X_L_te)
        
        # Fused Subspace
        Z_joint_tr = np.hstack([Z_S_tr, Z_L_tr])
        Z_joint_te = np.hstack([Z_S_te, Z_L_te])
        
        # Joint UMAP
        d_u_eff = min(n_umap, Z_joint_tr.shape[1] - 1, max(2, len(train_idx) - 2))
        n_neigh = min(15, len(train_idx) - 1)
        reducer = umap.UMAP(n_components=d_u_eff, n_neighbors=n_neigh, min_dist=0.1, random_state=seed + fold, transform_seed=seed + fold)
        Z_fuse_tr = reducer.fit_transform(Z_joint_tr)
        Z_fuse_te = reducer.transform(Z_joint_te)
        
        # Encoder
        if encoder_name == "Logistic":
            clf = LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold)
        elif encoder_name == "Linear_SVM":
            clf = SVC(kernel="linear", C=1.0, probability=True, random_state=seed + fold)
        elif encoder_name == "RBF_SVM":
            clf = SVC(kernel="rbf", C=1.0, probability=True, random_state=seed + fold)
            
        clf.fit(Z_fuse_tr, y[train_idx])
        oof_preds[test_idx] = clf.predict(Z_fuse_te)
        if hasattr(clf, "predict_proba"):
            oof_probs[test_idx] = clf.predict_proba(Z_fuse_te)[:, 1]
        elif hasattr(clf, "decision_function"):
            oof_probs[test_idx] = clf.decision_function(Z_fuse_te)
            
    acc = float(balanced_accuracy_score(y, oof_preds))
    try:
        auc = float(roc_auc_score(y, oof_probs))
    except Exception:
        auc = acc
    return {"acc": acc, "auc": auc}


def main():
    t0 = time.time()
    MATCHED_F06_CSV = OA_ROOT / "outputs" / "substrates" / "f06_substrate" / "f06_matched_substrate_v1.csv"
    UNIT_INCLUSION_CSV = OA_ROOT / "outputs" / "classification" / "unit_inclusion_v1.csv"
    matched_f06 = pd.read_csv(MATCHED_F06_CSV)
    units_df = pd.read_csv(UNIT_INCLUSION_CSV)
    nwb_dir = Path(P.nwb_dir())
    
    print(f"Executing PCA -> UMAP Battery on SPK, LFP, and Balanced Fusion across {len(matched_f06)} matched cells...")
    
    records = []
    
    for cell_idx, cell in matched_f06.iterrows():
        sess = cell["session"]
        area = cell["area"]
        probe = cell["probe"]
        subj = cell["subject"]
        
        cand = list(nwb_dir.glob(sess + "*.nwb"))[0]
        with h5py.File(cand, "r") as f:
            key, lo, hi = resolve_area_channel_block(f, probe, area, N_CH_WINDOW)
            trials_om, fs, n_om, _ = extract_epoch_trials(f, key, lo, hi, "RXRR", EPOCH_WIN_S, MAX_TRIALS)
            trials_st, fs, n_st, _ = extract_epoch_trials(f, key, lo, hi, "RRRR", EPOCH_WIN_S, MAX_TRIALS)
            
            onsets_om = p1_onsets_s(f, "RXRR")[:n_om]
            onsets_st = p1_onsets_s(f, "RRRR")[:n_st]
            
            u_sub = units_df[(units_df["session"] == sess) & (units_df["area"] == area)]
            unit_rows = u_sub["unit_row"].values
            
            units_grp = f["units"]
            spike_times = units_grp["spike_times"][:]
            spike_times_index = units_grp["spike_times_index"][:]
            
            # Omission window spiking
            counts_om = np.zeros((n_om, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_om):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_om[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
            # Stimulus window spiking
            counts_st = np.zeros((n_st, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_st):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_st[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
        # 5-band LFP power
        lfp_p_om = compute_band_power_features(trials_om, fs, OMISSION_WIN_MS)
        lfp_p_st = compute_band_power_features(trials_st, fs, OMISSION_WIN_MS)
        
        X_spk = np.vstack([counts_om, counts_st])
        X_lfp = np.vstack([lfp_p_om, lfp_p_st])
        y = np.concatenate([np.ones(n_om, dtype=int), np.zeros(n_st, dtype=int)])
        
        if len(y) < 10 or len(np.unique(y)) < 2:
            continue
            
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_splits = list(skf.split(X_spk, y))
        
        # 1. SPK PCA -> UMAP
        res_spk_umap = fit_pca_umap_encoder_cv(X_spk, y, cv_splits, n_pca=5, n_umap=3, encoder_name="Logistic")
        # 2. LFP PCA -> UMAP
        res_lfp_umap = fit_pca_umap_encoder_cv(X_lfp, y, cv_splits, n_pca=4, n_umap=2, encoder_name="Logistic")
        # 3. SPK+LFP Balanced Fusion PCA -> UMAP
        res_fusion_umap = fit_balanced_fusion_cv(X_spk, X_lfp, y, cv_splits, n_pca_S=5, n_pca_L=4, n_umap=3, encoder_name="Logistic")
        
        # Linear Baselines for comparison
        from sklearn.linear_model import LogisticRegression
        def eval_linear(X_mat):
            oof_p = np.zeros(len(y))
            for tr, te in cv_splits:
                sc = StandardScaler()
                X_tr = sc.fit_transform(X_mat[tr])
                X_te = sc.transform(X_mat[te])
                clf = LogisticRegression(C=1.0, max_iter=1000)
                clf.fit(X_tr, y[tr])
                oof_p[te] = clf.predict_proba(X_te)[:, 1]
            return float(roc_auc_score(y, oof_p)), float(balanced_accuracy_score(y, (oof_p >= 0.5).astype(int)))
            
        auc_spk_lin, acc_spk_lin = eval_linear(X_spk)
        auc_lfp_lin, acc_lfp_lin = eval_linear(X_lfp)
        auc_joint_lin, acc_joint_lin = eval_linear(np.hstack([X_spk, X_lfp]))
        
        records.append({
            "cell_idx": cell_idx, "session": sess, "subject": subj, "area": area, "probe": probe,
            "spk_linear_auc": auc_spk_lin, "spk_linear_acc": acc_spk_lin,
            "lfp_linear_auc": auc_lfp_lin, "lfp_linear_acc": acc_lfp_lin,
            "joint_linear_auc": auc_joint_lin, "joint_linear_acc": acc_joint_lin,
            "spk_pca_umap_auc": res_spk_umap["auc"], "spk_pca_umap_acc": res_spk_umap["acc"],
            "lfp_pca_umap_auc": res_lfp_umap["auc"], "lfp_pca_umap_acc": res_lfp_umap["acc"],
            "fusion_pca_umap_auc": res_fusion_umap["auc"], "fusion_pca_umap_acc": res_fusion_umap["acc"],
            "delta_lfp_gain_manifold": res_fusion_umap["auc"] - res_spk_umap["auc"],
            "delta_spk_gain_manifold": res_fusion_umap["auc"] - res_lfp_umap["auc"],
        })
        
    df_out = pd.DataFrame(records)
    df_out.to_csv(OUT_DIR / "lfp_multimodal_pca_umap_results.csv", index=False)
    
    print("\n=== Matched SPK, LFP, and Multimodal PCA -> UMAP Summary (N=31 cells) ===")
    print(f"SPK Linear AUC:             {df_out['spk_linear_auc'].mean():.4f} +/- {df_out['spk_linear_auc'].sem():.4f}")
    print(f"LFP Linear AUC:             {df_out['lfp_linear_auc'].mean():.4f} +/- {df_out['lfp_linear_auc'].sem():.4f}")
    print(f"Joint Linear AUC:           {df_out['joint_linear_auc'].mean():.4f} +/- {df_out['joint_linear_auc'].sem():.4f}")
    print(f"----------------------------------------------------------------------------------")
    print(f"SPK PCA->UMAP AUC:          {df_out['spk_pca_umap_auc'].mean():.4f} +/- {df_out['spk_pca_umap_auc'].sem():.4f}")
    print(f"LFP PCA->UMAP AUC:          {df_out['lfp_pca_umap_auc'].mean():.4f} +/- {df_out['lfp_pca_umap_auc'].sem():.4f}")
    print(f"Balanced Fusion UMAP AUC:   {df_out['fusion_pca_umap_auc'].mean():.4f} +/- {df_out['fusion_pca_umap_auc'].sem():.4f}")
    print(f"----------------------------------------------------------------------------------")
    print(f"Delta_L (LFP gain on manifold): {df_out['delta_lfp_gain_manifold'].mean():.4f} +/- {df_out['delta_lfp_gain_manifold'].sem():.4f}")
    print(f"Delta_S (SPK gain on manifold): {df_out['delta_spk_gain_manifold'].mean():.4f} +/- {df_out['delta_spk_gain_manifold'].sem():.4f}")
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_matched_cells": len(df_out),
        "mean_metrics": {
            "spk_linear_auc": float(df_out["spk_linear_auc"].mean()),
            "lfp_linear_auc": float(df_out["lfp_linear_auc"].mean()),
            "joint_linear_auc": float(df_out["joint_linear_auc"].mean()),
            "spk_pca_umap_auc": float(df_out["spk_pca_umap_auc"].mean()),
            "lfp_pca_umap_auc": float(df_out["lfp_pca_umap_auc"].mean()),
            "fusion_pca_umap_auc": float(df_out["fusion_pca_umap_auc"].mean()),
            "delta_l_manifold": float(df_out["delta_lfp_gain_manifold"].mean()),
            "delta_s_manifold": float(df_out["delta_spk_gain_manifold"].mean()),
        },
        "runtime_seconds": round(time.time() - t0, 2)
    }
    with open(OUT_DIR / "lfp_multimodal_pca_umap_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\nSaved multimodal PCA->UMAP results to {OUT_DIR / 'lfp_multimodal_pca_umap_results.csv'}")


if __name__ == "__main__":
    main()
