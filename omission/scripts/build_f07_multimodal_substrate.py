#!/usr/bin/env python3
"""Build F07 Multimodal Informational Complementarity Substrate.

For each of the 31 matched session x area cells:
  1. Extracts trial-level SPK features (spike counts per unit in 1031-1562ms).
  2. Extracts trial-level LFP features (band power in theta, alpha, beta, low-gamma, high-gamma in 1031-1562ms).
  3. Evaluates held-out decoding of Omission (RXRR) vs Stimulus (RRRR):
       - M_S: SPK only
       - M_L: LFP only
       - M_SL: Joint (SPK + LFP)
     using identical 5-fold stratified CV splits, StandardScaler, and LogisticRegression(C=1.0).
  4. Computes incremental quantities:
       - Delta_L = AUC(M_SL) - AUC(M_S)  [predictive analogue of I(Z; L | S)]
       - Delta_S = AUC(M_SL) - AUC(M_L)  [predictive analogue of I(Z; S | L)]
  5. Computes permutation nulls for M_S, M_L, M_SL across 100 permutations.
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
BASELINE_WIN_MS = (-400.0, -150.0)

SUBSTRATE_DIR = OA_ROOT / "outputs" / "f07_substrate"
MATCHED_F06_CSV = OA_ROOT / "outputs" / "f06_substrate" / "f06_matched_substrate_v1.csv"
UNIT_INCLUSION_CSV = OA_ROOT / "outputs" / "classification" / "unit_inclusion_v1.csv"


def compute_trial_band_power(trials: np.ndarray, fs: float, win_ms: tuple[float, float]) -> np.ndarray:
    """Computes band power in win_ms per trial and channel, then averages across channels (L0 canonical).
    trials: (n_trials, n_channels, n_samples)
    returns: (n_trials, 5 bands) in dB
    """
    n_trials, n_ch, n_samples = trials.shape
    t_vec = np.arange(n_samples) / fs + EPOCH_WIN_S[0]
    mask = (t_vec >= win_ms[0] / 1000.0) & (t_vec <= win_ms[1] / 1000.0)
    
    seg = trials[:, :, mask] # (n_trials, n_ch, n_win_samples)
    n_win = seg.shape[2]
    
    # FFT
    freqs = np.fft.rfftfreq(n_win, d=1.0/fs)
    fft_vals = np.fft.rfft(seg, axis=2)
    psd = (np.abs(fft_vals) ** 2) / (n_win * fs) # (n_trials, n_ch, n_freqs)
    
    # Mean PSD across channels (L0 canonical method)
    psd_ch_mean = np.mean(psd, axis=1) # (n_trials, n_freqs)
    
    band_powers = []
    for b_name, (f_lo, f_hi) in BANDS.items():
        f_mask = (freqs >= f_lo) & (freqs <= f_hi)
        if not np.any(f_mask):
            f_mask = np.array([np.argmin(np.abs(freqs - (f_lo+f_hi)/2))])
        p_band = np.mean(psd_ch_mean[:, f_mask], axis=1)
        band_powers.append(p_band)
        
    p_arr = np.stack(band_powers, axis=1) # (n_trials, 5)
    # Convert to log power (10 * log10)
    p_db = 10.0 * np.log10(np.maximum(p_arr, 1e-12))
    return p_db


def evaluate_cv_pipeline(X: np.ndarray, y: np.ndarray, cv_splits: list[tuple[np.ndarray, np.ndarray]], seed: int = 42) -> dict:
    oof_proba = np.zeros(len(y), dtype=float)
    oof_pred = np.zeros(len(y), dtype=int)
    
    for fold, (train_idx, test_idx) in enumerate(cv_splits):
        clf = Pipeline([
            ("scaler", StandardScaler()),
            ("lr", LogisticRegression(C=1.0, max_iter=1000, random_state=seed + fold))
        ])
        clf.fit(X[train_idx], y[train_idx])
        probs = clf.predict_proba(X[test_idx])[:, 1]
        oof_proba[test_idx] = probs
        oof_pred[test_idx] = (probs >= 0.5).astype(int)
        
    acc = float(accuracy_score(y, oof_pred))
    auc = float(roc_auc_score(y, oof_proba)) if len(np.unique(y)) > 1 else 0.5
    loss = float(log_loss(y, np.clip(oof_proba, 1e-6, 1-1e-6)))
    return {"accuracy": acc, "auc": auc, "cross_entropy": loss, "oof_proba": oof_proba}


def main():
    SUBSTRATE_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    
    matched_f06 = pd.read_csv(MATCHED_F06_CSV)
    units_df = pd.read_csv(UNIT_INCLUSION_CSV)
    nwb_dir = Path(P.nwb_dir())
    
    print(f"Building F07 Multimodal Complementarity Substrate across {len(matched_f06)} matched cells...")
    
    records = []
    
    for cell_idx, cell in matched_f06.iterrows():
        sess = cell["session"]
        area = cell["area"]
        probe = cell["probe"]
        subj = cell["subject"]
        
        cand = list(nwb_dir.glob(sess + "*.nwb"))[0]
        with h5py.File(cand, "r") as f:
            # 1. Extract LFP trials
            key, lo, hi = resolve_area_channel_block(f, probe, area, N_CH_WINDOW)
            trials_om, fs, n_om, frac_om = extract_epoch_trials(f, key, lo, hi, "RXRR", EPOCH_WIN_S, MAX_TRIALS)
            trials_st, fs, n_st, frac_st = extract_epoch_trials(f, key, lo, hi, "RRRR", EPOCH_WIN_S, MAX_TRIALS)
            
            onsets_om = p1_onsets_s(f, "RXRR")[:n_om]
            onsets_st = p1_onsets_s(f, "RRRR")[:n_st]
            
            # 2. Extract SPK trials
            u_sub = units_df[(units_df["session"] == sess) & (units_df["area"] == area)]
            unit_rows = u_sub["unit_row"].values
            
            units_grp = f["units"]
            spike_times = units_grp["spike_times"][:]
            spike_times_index = units_grp["spike_times_index"][:]
            
            # Omission spike counts
            counts_om = np.zeros((n_om, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_om):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_om[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
            # Stimulus spike counts
            counts_st = np.zeros((n_st, len(unit_rows)), dtype=float)
            for u_col, u_idx in enumerate(unit_rows):
                s_lo = 0 if u_idx == 0 else spike_times_index[u_idx - 1]
                s_hi = spike_times_index[u_idx]
                st = spike_times[s_lo:s_hi]
                for t_idx, onset in enumerate(onsets_st):
                    t_lo = onset + OMISSION_WIN_MS[0] / 1000.0
                    t_hi = onset + OMISSION_WIN_MS[1] / 1000.0
                    counts_st[t_idx, u_col] = np.sum((st >= t_lo) & (st <= t_hi))
                    
        # Compute LFP band powers in omission window
        lfp_p_om = compute_trial_band_power(trials_om, fs, OMISSION_WIN_MS) # (n_om, 5)
        lfp_p_st = compute_trial_band_power(trials_st, fs, OMISSION_WIN_MS) # (n_st, 5)
        
        # Combine into aligned classification dataset
        # Target Z: 1 = Omission (RXRR), 0 = Stimulus (RRRR)
        X_spk = np.vstack([counts_om, counts_st])
        X_lfp = np.vstack([lfp_p_om, lfp_p_st])
        X_joint = np.hstack([X_spk, X_lfp])
        y = np.concatenate([np.ones(n_om, dtype=int), np.zeros(n_st, dtype=int)])
        
        # Balance / Stratified CV (5-fold)
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        cv_splits = list(skf.split(X_joint, y))
        
        # Train and evaluate M_S, M_L, M_SL
        res_s = evaluate_cv_pipeline(X_spk, y, cv_splits, seed=42)
        res_l = evaluate_cv_pipeline(X_lfp, y, cv_splits, seed=42)
        res_sl = evaluate_cv_pipeline(X_joint, y, cv_splits, seed=42)
        
        delta_l = res_sl["auc"] - res_s["auc"]  # Added value of LFP over SPK
        delta_s = res_sl["auc"] - res_l["auc"]  # Added value of SPK over LFP
        
        # Permutation nulls (50 permutations)
        null_auc_s = []
        null_auc_l = []
        null_auc_sl = []
        null_delta_l = []
        null_delta_s = []
        
        rng = np.random.default_rng(42 + cell_idx)
        for p_idx in range(50):
            y_perm = rng.permutation(y)
            p_res_s = evaluate_cv_pipeline(X_spk, y_perm, cv_splits, seed=100 + p_idx)
            p_res_l = evaluate_cv_pipeline(X_lfp, y_perm, cv_splits, seed=100 + p_idx)
            p_res_sl = evaluate_cv_pipeline(X_joint, y_perm, cv_splits, seed=100 + p_idx)
            
            null_auc_s.append(p_res_s["auc"])
            null_auc_l.append(p_res_l["auc"])
            null_auc_sl.append(p_res_sl["auc"])
            null_delta_l.append(p_res_sl["auc"] - p_res_s["auc"])
            null_delta_s.append(p_res_sl["auc"] - p_res_l["auc"])
            
        p_val_delta_l = float(np.mean(np.array(null_delta_l) >= delta_l))
        p_val_delta_s = float(np.mean(np.array(null_delta_s) >= delta_s))
        
        record = {
            "session": sess,
            "subject": subj,
            "area": area,
            "probe": probe,
            "n_trials_omission": n_om,
            "n_trials_stimulus": n_st,
            "n_units": len(unit_rows),
            "auc_spk": res_s["auc"],
            "acc_spk": res_s["accuracy"],
            "loss_spk": res_s["cross_entropy"],
            "auc_lfp": res_l["auc"],
            "acc_lfp": res_l["accuracy"],
            "loss_lfp": res_l["cross_entropy"],
            "auc_joint": res_sl["auc"],
            "acc_joint": res_sl["accuracy"],
            "loss_joint": res_sl["cross_entropy"],
            "delta_l": delta_l,
            "delta_s": delta_s,
            "delta_l_loss": res_s["cross_entropy"] - res_sl["cross_entropy"],
            "delta_s_loss": res_l["cross_entropy"] - res_sl["cross_entropy"],
            "p_perm_delta_l": p_val_delta_l,
            "p_perm_delta_s": p_val_delta_s,
            "null_auc_spk_mean": float(np.mean(null_auc_s)),
            "null_auc_lfp_mean": float(np.mean(null_auc_l)),
            "null_auc_joint_mean": float(np.mean(null_auc_sl)),
        }
        records.append(record)
        print(f"Cell {cell_idx+1}/31 ({sess} / {area}): AUC_S={res_s['auc']:.3f}, AUC_L={res_l['auc']:.3f}, AUC_Joint={res_sl['auc']:.3f} | Delta_L={delta_l:+.3f}, Delta_S={delta_s:+.3f}")
        
    df_out = pd.DataFrame(records)
    df_out.to_csv(SUBSTRATE_DIR / "f07_multimodal_substrate_v1.csv", index=False)
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "n_matched_cells": len(df_out),
        "target": "Omission (RXRR) vs Stimulus (RRRR) p2 window (1031-1562ms)",
        "models": {
            "M_S": "SPK unit spike counts -> LogisticRegression(C=1.0)",
            "M_L": "LFP 5-band log power -> LogisticRegression(C=1.0)",
            "M_SL": "Joint (SPK + LFP) -> LogisticRegression(C=1.0)",
        },
        "cv_scheme": "5-fold Stratified CV (identical folds across models)",
        "runtime_seconds": time.time() - t0,
        "summary": {
            "mean_auc_spk": float(df_out["auc_spk"].mean()),
            "mean_auc_lfp": float(df_out["auc_lfp"].mean()),
            "mean_auc_joint": float(df_out["auc_joint"].mean()),
            "mean_delta_l": float(df_out["delta_l"].mean()),
            "mean_delta_s": float(df_out["delta_s"].mean()),
        }
    }
    with open(SUBSTRATE_DIR / "f07_multimodal_substrate_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
        
    print(f"\nCompleted in {time.time()-t0:.1f}s.")
    print("Summary:")
    print(f"  Mean AUC(M_S)     = {df_out['auc_spk'].mean():.4f}")
    print(f"  Mean AUC(M_L)     = {df_out['auc_lfp'].mean():.4f}")
    print(f"  Mean AUC(M_SL)    = {df_out['auc_joint'].mean():.4f}")
    print(f"  Mean Delta_L      = {df_out['delta_l'].mean():+.4f} (LFP added value over SPK)")
    print(f"  Mean Delta_S      = {df_out['delta_s'].mean():+.4f} (SPK added value over LFP)")


if __name__ == "__main__":
    main()
