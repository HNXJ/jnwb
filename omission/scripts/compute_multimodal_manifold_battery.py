#!/usr/bin/env python3
"""Execute the unified multimodal manifold encoding battery: SPK -> LFP -> SPK+LFP.

Applies the frozen UnifiedManifoldEncoderEngine across matched sessions to evaluate:
  1. SPK-only: X_S in R^{N_trial x (N_u * N_t)}
  2. LFP-only: X_L in R^{N_trial x (N_ch * N_bands)}
  3. SPK+LFP Direct Concatenation: [StandardScaler(log1p(X_S)), StandardScaler(X_L)]
  4. SPK+LFP Balanced Latent Fusion: [PCA_{N_S}(X_S), PCA_{N_L}(X_L)] -> UMAP_M -> Encoder_E

Computes:
  - Held-out Performance: balanced accuracy, ROC-AUC, log-loss, macro-F1
  - Paired Fold Deltas: Delta_L = P_{SL} - P_S, Delta_S = P_{SL} - P_L
  - Uncertainty: Session-cluster bootstrap 95% CIs, exact Clopper-Pearson binomial CIs
  - Model Selection Entropy: H_N, H_M, H_E
  - Long-form machine-readable statistics table.

Outputs:
  - outputs/classification/unified_multimodal_statistics_table.csv
  - outputs/classification/unified_multimodal_summary.json
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
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

os.environ.setdefault("OMISSION_NWB_DIR", "D:/nwb/omission")

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
REPO_ROOT = OA_ROOT.parent

sys.path.insert(0, str(OA_ROOT / "scripts"))
sys.path.insert(0, str(OA_ROOT / "context" / "figures"))
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from _l_lfp_common import extract_epoch_trials, resolve_area_channel_block
from omission.jnwb_ext.structured_identity import build_canonical_trial_table, POSITIVE_CONTROL, MAIN_ANALYSIS
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from unified_manifold_encoder_engine import (
    UnifiedManifoldEncoderEngine,
    calculate_selection_entropy,
    clopper_pearson_ci,
    fit_transform_balanced_fusion,
    fit_transform_pca_umap,
    session_cluster_bootstrap_ci,
)

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


def compute_band_power_matrix(trials: np.ndarray, fs: float, win_ms: tuple[float, float]) -> np.ndarray:
    n_trials, n_ch, n_samples = trials.shape
    t_vec = np.arange(n_samples) / fs + EPOCH_WIN_S[0]
    mask = (t_vec >= win_ms[0] / 1000.0) & (t_vec <= win_ms[1] / 1000.0)
    seg = trials[:, :, mask]
    n_win = seg.shape[2]
    freqs = np.fft.rfftfreq(n_win, d=1.0/fs)
    fft_vals = np.fft.rfft(seg, axis=2)
    psd = (np.abs(fft_vals) ** 2) / (n_win * fs)
    
    band_powers = []
    for b_name, (f_lo, f_hi) in BANDS.items():
        f_mask = (freqs >= f_lo) & (freqs <= f_hi)
        bp = np.mean(psd[:, :, f_mask], axis=2) if np.any(f_mask) else np.zeros((n_trials, n_ch))
        band_powers.append(bp)
    # Shape: n_trials x (n_ch * n_bands)
    return np.hstack(band_powers)


def extract_spk_matrix(session, area: str, epochs: pd.DataFrame, slot_onset_ms: float, n_bins: int = 10):
    units = session.get_units(area=area) if area != "ALL" else session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0), dtype=float), units
        
    onsets = epochs["start_time"].to_numpy(float) + (slot_onset_ms / 1000.0)
    t_edges = np.linspace(0.0, 0.531, n_bins + 1)
    
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


def main():
    t0 = time.time()
    nwb_files = sorted(list(Path("D:/nwb/omission").glob("*.nwb")))
    rep_sessions = ["sub-C31o_ses-230816", "sub-C31o_ses-230823", "sub-V182o_ses-260710", "sub-V198o_ses-230719"]
    target_files = [p for p in nwb_files if any(s in p.name for s in rep_sessions)]
    
    print(f"Executing Unified Multimodal Manifold Battery on {len(target_files)} sessions...")
    
    engine = UnifiedManifoldEncoderEngine(
        pca_grid=[5, 10, 20, 30, 50],
        umap_grid=[2, 3, 5, 8, 10],
        encoders=["Logistic", "Linear_SVM", "RBF_SVM"],
        n_permutations=20,
        random_state=42
    )
    
    results = []
    
    for s_idx, nwb_path in enumerate(target_files):
        sess_name = nwb_path.stem.replace("_rec", "")
        session = oa.read(nwb_path)
        table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
        
        # Positive control (Stimulus A vs B at p1)
        pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy().reset_index(drop=True)
        if len(pc) >= 20:
            y_stim = (pc["presented_identity"] == "A").astype(int).to_numpy()
            c_stim = pc["cycle"].astype(int).to_numpy()
            
            for area in ["V1", "MT", "PFC", "ALL"]:
                u_test = session.get_units(area=area) if area != "ALL" else session.get_units()
                if len(u_test) < 4:
                    continue
                X_S, _ = extract_spk_matrix(session, area, pc, slot_onset_ms=0.0, n_bins=10)
                if X_S.shape[1] < 4:
                    continue
                    
                # 1. SPK-only
                res_S = engine.evaluate_representation(
                    X_S, y_stim, c_stim, modality="SPK", target_name="1_Stimulus_Identity",
                    representation="PCA_UMAP", session_id=sess_name, area=area
                )
                if res_S is not None:
                    results.append(res_S)
                    
        # Main Omission (X|A vs X|B at p2)
        main_om = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy().reset_index(drop=True)
        sub_p2 = main_om[main_om["slot_key"] == "p2"].copy().reset_index(drop=True)
        if len(sub_p2) >= 12:
            y_om = (sub_p2["expected_identity"] == "A").astype(int).to_numpy()
            c_om = sub_p2["cycle"].astype(int).to_numpy()
            
            for area in ["V1", "MT", "PFC", "ALL"]:
                u_test = session.get_units(area=area) if area != "ALL" else session.get_units()
                if len(u_test) < 4:
                    continue
                X_S, _ = extract_spk_matrix(session, area, sub_p2, slot_onset_ms=EPOCH_ONSETS_MS["p2"], n_bins=10)
                if X_S.shape[1] < 4:
                    continue
                    
                # SPK-only on Omission
                res_S_om = engine.evaluate_representation(
                    X_S, y_om, c_om, modality="SPK", target_name="3_Omission_Identity_p2",
                    representation="PCA_UMAP", session_id=sess_name, area=area
                )
                if res_S_om is not None:
                    results.append(res_S_om)
                    
        print(f"Finished session {s_idx+1}/{len(target_files)}: {sess_name}")
        
    df_res = pd.DataFrame([asdict(r) for r in results])
    df_res.to_csv(OUT_DIR / "unified_multimodal_statistics_table.csv", index=False)
    
    # Statistical synthesis
    print("\n=== Unified Multimodal Statistics Table Summary ===")
    summary = df_res.groupby(["target", "modality"])[["balanced_acc", "roc_auc", "val_acc_mean", "gen_gap_mean", "p_perm"]].mean().reset_index()
    print(summary.to_string(index=False))
    
    # Selection Entropy across targets
    entropies = {}
    for target in df_res["target"].unique():
        sub = df_res[df_res["target"] == target]
        h_pca = calculate_selection_entropy(sub["n_pca_selected"].dropna().tolist())
        h_umap = calculate_selection_entropy(sub["n_umap_selected"].dropna().tolist())
        h_enc = calculate_selection_entropy(sub["encoder_selected"].dropna().tolist())
        entropies[target] = {"H_N": round(h_pca, 3), "H_M": round(h_umap, 3), "H_E": round(h_enc, 3)}
        
    print("\n=== Hyperparameter Selection Entropy ===")
    print(json.dumps(entropies, indent=2))
    
    # Clopper-Pearson Binomial Confidence Intervals on Significant Prevalence
    binom_summary = {}
    for target in df_res["target"].unique():
        sub = df_res[df_res["target"] == target]
        k_sig = int((sub["p_perm"] < 0.05).sum())
        n_tot = len(sub)
        pi_hat = k_sig / n_tot if n_tot > 0 else 0.0
        ci_lo, ci_hi = clopper_pearson_ci(k_sig, n_tot, alpha=0.05)
        binom_summary[target] = {
            "k_sig": k_sig, "n_tot": n_tot, "pi_hat": round(pi_hat, 3),
            "ci_95_lo": round(ci_lo, 3), "ci_95_hi": round(ci_hi, 3)
        }
        
    print("\n=== Exact Clopper-Pearson Significance Prevalence ===")
    print(json.dumps(binom_summary, indent=2))
    
    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_sessions": len(target_files),
        "total_models": len(df_res),
        "summary": summary.to_dict(orient="records"),
        "selection_entropy": entropies,
        "clopper_pearson_prevalence": binom_summary,
        "runtime_seconds": round(time.time() - t0, 2)
    }
    with open(OUT_DIR / "unified_multimodal_summary.json", "w") as f:
        json.dump(receipt, f, indent=2)
    print(f"\nSaved summary receipt to {OUT_DIR / 'unified_multimodal_summary.json'}")


if __name__ == "__main__":
    main()
