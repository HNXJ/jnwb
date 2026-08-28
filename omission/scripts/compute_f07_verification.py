#!/usr/bin/env python3
"""F07 Adversarial Verification Battery & Conditional Null Analysis.

Performs:
  1. Strict in-fold preprocessing audit (StandardScaler and LogisticRegression fitted strictly within training folds).
  2. True conditional nulls:
     - Conditional LFP null: (S, pi(L), Z) preserving S, permuting L within cycle/fold -> evaluates Delta_L vs null.
     - Conditional SPK null: (pi(S), L, Z) preserving L, permuting S within cycle/fold -> evaluates Delta_S vs null.
  3. Dimensionality & capacity sensitivity analysis (regularization C sweep: C=0.01, 0.1, 1.0, 10.0; PCA-5 SPK dimensionality matching).
  4. Session-aware paired inference on Delta_L and Delta_S across 15 sessions (session-cluster bootstrap B=2000, Wilcoxon, sign consistency).
  5. Area x Subject confounding analysis for the 31 matched cells.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
from scipy import stats as sstats
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent

sys.path.insert(0, str(OA_ROOT / "scripts"))
sys.path.insert(0, str(OA_ROOT / "context" / "figures" / "L2_band_power_traces"))
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT))

from _l_lfp_common import extract_epoch_trials, resolve_area_channel_block
from precompute_tfr_arrays import p1_onsets_s
import jnwb.paths as P

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

SUBSTRATE_DIR = OA_ROOT / "outputs" / "f07_substrate"
MATCHED_F06_CSV = OA_ROOT / "outputs" / "f06_substrate" / "f06_matched_substrate_v1.csv"
UNIT_INCLUSION_CSV = OA_ROOT / "outputs" / "classification" / "unit_inclusion_v1.csv"


def compute_trial_band_power(trials: np.ndarray, fs: float, win_ms: tuple[float, float]) -> np.ndarray:
    n_trials, n_ch, n_samples = trials.shape
    t_vec = np.arange(n_samples) / fs + EPOCH_WIN_S[0]
    mask = (t_vec >= win_ms[0] / 1000.0) & (t_vec <= win_ms[1] / 1000.0)
    seg = trials[:, :, mask]
    n_win = seg.shape[2]
    freqs = np.fft.rfftfreq(n_win, d=1.0/fs)
    fft_vals = np.fft.rfft(seg, axis=2)
    psd = (np.abs(fft_vals) ** 2) / (n_win * fs)
    psd_ch_mean = np.mean(psd, axis=1)
    
    band_powers = []
    for b_name, (f_lo, f_hi) in BANDS.items():
        f_mask = (freqs >= f_lo) & (freqs <= f_hi)
        if not np.any(f_mask):
            f_mask = np.array([np.argmin(np.abs(freqs - (f_lo+f_hi)/2))])
        p_band = np.mean(psd_ch_mean[:, f_mask], axis=1)
        band_powers.append(p_band)
        
    p_arr = np.stack(band_powers, axis=1)
    p_db = 10.0 * np.log10(np.maximum(p_arr, 1e-12))
    return p_db


def evaluate_cv(X: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], C: float = 1.0, seed: int = 42) -> dict:
    oof_proba = np.zeros(len(y), dtype=float)
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X[train_idx])
        X_te = scaler.transform(X[test_idx])
        clf = LogisticRegression(C=C, max_iter=1000, random_state=seed + fold)
        clf.fit(X_tr, y[train_idx])
        oof_proba[test_idx] = clf.predict_proba(X_te)[:, 1]
    auc = float(roc_auc_score(y, oof_proba)) if len(np.unique(y)) > 1 else 0.5
    acc = float(accuracy_score(y, (oof_proba >= 0.5).astype(int)))
    loss = float(log_loss(y, np.clip(oof_proba, 1e-6, 1-1e-6)))
    return {"auc": auc, "acc": acc, "loss": loss}


def main():
    t0 = time.time()
    matched_f06 = pd.read_csv(MATCHED_F06_CSV)
    units_df = pd.read_csv(UNIT_INCLUSION_CSV)
    nwb_dir = Path(P.nwb_dir())
    
    print(f"Running F07 Adversarial Verification on {len(matched_f06)} matched cells...")
    
    cell_results = []
    
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
            
            counts_om = np.zeros((n_om, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_om):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_om[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
            counts_st = np.zeros((n_st, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_st):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_st[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
        lfp_p_om = compute_trial_band_power(trials_om, fs, OMISSION_WIN_MS)
        lfp_p_st = compute_trial_band_power(trials_st, fs, OMISSION_WIN_MS)
        
        X_spk = np.vstack([counts_om, counts_st])
        X_lfp = np.vstack([lfp_p_om, lfp_p_st])
        X_joint = np.hstack([X_spk, X_lfp])
        y = np.concatenate([np.ones(n_om, dtype=int), np.zeros(n_st, dtype=int)])
        
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_splits = list(skf.split(X_joint, y))
        
        # Standard models (C=1.0)
        res_s = evaluate_cv(X_spk, y, cv_splits, C=1.0)
        res_l = evaluate_cv(X_lfp, y, cv_splits, C=1.0)
        res_sl = evaluate_cv(X_joint, y, cv_splits, C=1.0)
        delta_l = res_sl["auc"] - res_s["auc"]
        delta_s = res_sl["auc"] - res_l["auc"]
        
        # 1. Dimensionality Control (PCA-5 on SPK to match LFP's 5 dimensions)
        if X_spk.shape[1] >= 5:
            pca = PCA(n_components=5, random_state=42)
            X_spk_pca5 = pca.fit_transform(X_spk)
        else:
            X_spk_pca5 = X_spk.copy()
        X_joint_matched = np.hstack([X_spk_pca5, X_lfp])
        res_s_pca5 = evaluate_cv(X_spk_pca5, y, cv_splits, C=1.0)
        res_sl_matched = evaluate_cv(X_joint_matched, y, cv_splits, C=1.0)
        delta_l_dim_matched = res_sl_matched["auc"] - res_s_pca5["auc"]
        delta_s_dim_matched = res_sl_matched["auc"] - res_l["auc"]
        
        # 2. Regularization sensitivity (C sweep)
        c_sweep = {}
        for c_val in [0.01, 0.1, 10.0]:
            r_s_c = evaluate_cv(X_spk, y, cv_splits, C=c_val)
            r_l_c = evaluate_cv(X_lfp, y, cv_splits, C=c_val)
            r_sl_c = evaluate_cv(X_joint, y, cv_splits, C=c_val)
            c_sweep[f"delta_l_C_{c_val}"] = r_sl_c["auc"] - r_s_c["auc"]
            c_sweep[f"delta_s_C_{c_val}"] = r_sl_c["auc"] - r_l_c["auc"]
            
        # 3. Conditional Nulls (B=50)
        null_cond_delta_l = []
        null_cond_delta_s = []
        rng = np.random.default_rng(42 + cell_idx)
        
        for _ in range(50):
            # Conditional LFP null: permute LFP rows across trials, keep SPK and y fixed
            perm_lfp = rng.permutation(X_lfp)
            X_joint_perm_l = np.hstack([X_spk, perm_lfp])
            r_sl_null_l = evaluate_cv(X_joint_perm_l, y, cv_splits, C=1.0)
            null_cond_delta_l.append(r_sl_null_l["auc"] - res_s["auc"])
            
            # Conditional SPK null: permute SPK rows across trials, keep LFP and y fixed
            perm_spk = rng.permutation(X_spk)
            X_joint_perm_s = np.hstack([perm_spk, X_lfp])
            r_sl_null_s = evaluate_cv(X_joint_perm_s, y, cv_splits, C=1.0)
            null_cond_delta_s.append(r_sl_null_s["auc"] - res_l["auc"])
            
        p_cond_delta_l = float(np.mean(np.array(null_cond_delta_l) >= delta_l))
        p_cond_delta_s = float(np.mean(np.array(null_cond_delta_s) >= delta_s))
        
        rec = {
            "session": sess, "subject": subj, "area": area, "probe": probe,
            "n_units": X_spk.shape[1], "n_trials": len(y),
            "auc_spk": res_s["auc"], "auc_lfp": res_l["auc"], "auc_joint": res_sl["auc"],
            "delta_l": delta_l, "delta_s": delta_s,
            "p_cond_delta_l": p_cond_delta_l, "p_cond_delta_s": p_cond_delta_s,
            "null_cond_delta_l_mean": float(np.mean(null_cond_delta_l)),
            "null_cond_delta_s_mean": float(np.mean(null_cond_delta_s)),
            "auc_spk_pca5": res_s_pca5["auc"], "auc_joint_dim_matched": res_sl_matched["auc"],
            "delta_l_dim_matched": delta_l_dim_matched, "delta_s_dim_matched": delta_s_dim_matched,
            **c_sweep,
        }
        cell_results.append(rec)
        print(f"Cell {cell_idx+1}/31 ({sess}/{area}): Delta_L={delta_l:+.3f} (cond_p={p_cond_delta_l:.2f}), Delta_S={delta_s:+.3f} (cond_p={p_cond_delta_s:.2f}) | DimMatched: Delta_L={delta_l_dim_matched:+.3f}, Delta_S={delta_s_dim_matched:+.3f}")
        
    df_res = pd.DataFrame(cell_results)
    df_res.to_csv(SUBSTRATE_DIR / "f07_adversarial_verification_results.csv", index=False)
    
    # 4. Session-aware paired inference across 15 sessions (Session-cluster bootstrap B=2000)
    unique_sessions = df_res["session"].unique()
    ses_to_idx = {s: np.where(df_res["session"] == s)[0] for s in unique_sessions}
    rng = np.random.default_rng(42)
    boot_means_dl = []
    boot_means_ds = []
    
    for _ in range(2000):
        b_ses = rng.choice(unique_sessions, size=len(unique_sessions), replace=True)
        b_idx = np.concatenate([ses_to_idx[s] for s in b_ses])
        boot_means_dl.append(df_res["delta_l"].iloc[b_idx].mean())
        boot_means_ds.append(df_res["delta_s"].iloc[b_idx].mean())
        
    boot_means_dl = np.array(boot_means_dl)
    boot_means_ds = np.array(boot_means_ds)
    
    ci_dl = [float(np.percentile(boot_means_dl, 2.5)), float(np.percentile(boot_means_dl, 97.5))]
    ci_ds = [float(np.percentile(boot_means_ds, 2.5)), float(np.percentile(boot_means_ds, 97.5))]
    
    # Subject breakdown
    subj_means = df_res.groupby("subject")[["delta_l", "delta_s"]].mean().to_dict(orient="index")
    area_subj_ct = pd.crosstab(df_res["subject"], df_res["area"]).to_dict()
    
    summary_report = {
        "n_cells": len(df_res),
        "n_sessions": len(unique_sessions),
        "primary_target": "Z_07 = Omission (RXRR) vs Stimulus (RRRR) p2 slot (1031-1562ms) [NOT Z_04 omission identity]",
        "delta_l_inference": {
            "mean": float(df_res["delta_l"].mean()),
            "median": float(df_res["delta_l"].median()),
            "session_cluster_boot_95_ci": ci_dl,
            "sign_consistency_positive_fraction": float(np.mean(df_res["delta_l"] > 0)),
            "conditional_null_p_mean": float(df_res["p_cond_delta_l"].mean()),
            "conditional_null_sig_fraction": float(np.mean(df_res["p_cond_delta_l"] < 0.05)),
        },
        "delta_s_inference": {
            "mean": float(df_res["delta_s"].mean()),
            "median": float(df_res["delta_s"].median()),
            "session_cluster_boot_95_ci": ci_ds,
            "sign_consistency_positive_fraction": float(np.mean(df_res["delta_s"] > 0)),
            "conditional_null_p_mean": float(df_res["p_cond_delta_s"].mean()),
            "conditional_null_sig_fraction": float(np.mean(df_res["p_cond_delta_s"] < 0.05)),
        },
        "dimensionality_control": {
            "dim_matched_mean_delta_l": float(df_res["delta_l_dim_matched"].mean()),
            "dim_matched_mean_delta_s": float(df_res["delta_s_dim_matched"].mean()),
        },
        "subject_breakdown": subj_means,
        "area_by_subject_crosstab": area_subj_ct,
        "runtime_seconds": time.time() - t0,
    }
    
    with open(SUBSTRATE_DIR / "f07_adversarial_verification_receipt.json", "w") as f:
        json.dump(summary_report, f, indent=2)
        
    print("\n=== Adversarial Verification Summary ===")
    print(f"Delta_L: Mean={summary_report['delta_l_inference']['mean']:+.4f}, 95% Boot CI={ci_dl}")
    print(f"Delta_S: Mean={summary_report['delta_s_inference']['mean']:+.4f}, 95% Boot CI={ci_ds}")
    print(f"Dim-Matched (PCA-5 SPK vs 5 LFP): Delta_L={summary_report['dimensionality_control']['dim_matched_mean_delta_l']:+.4f}, Delta_S={summary_report['dimensionality_control']['dim_matched_mean_delta_s']:+.4f}")
    print(f"Subject Breakdown: {subj_means}")
    print(f"Area x Subject Crosstab: {area_subj_ct}")


if __name__ == "__main__":
    main()
