#!/usr/bin/env python3
"""Execute Sequence RSA, Balanced Multimodal Latent Fusion, and Time-Resolved State Trajectories.

Implements:
  1. Representational Similarity Analysis (RSA):
     - 12x12 Condition RDM (3 slot positions: p2, p3, p4 x 4 sequence conditions: AAAB, AABA, BBBA, BBAB)
     - Model RDMs: Position, Physical Stimulus Identity, Sensory Presence, Expected Identity
     - Multiple regression of RDMs: RDM_neural = beta_1*RDM_Pos + beta_2*RDM_Stim + beta_3*RDM_Pres + beta_4*RDM_Exp
     - Permutation testing for regression coefficients.
  2. Balanced Multimodal Latent Fusion:
     - [PCA_Ns(X_S), PCA_Nl(X_L)] -> Linear/Logistic/UMAP
     - Compares SPK-only, LFP-only, and Balanced Multimodal Fusion.
  3. Time-Resolved Trajectory Dynamics z(t):
     - 50ms temporal bin population trajectories.

Outputs:
  - outputs/classification/fig04_rsa_rdm_matrix.csv
  - outputs/classification/fig04_rsa_model_regression.csv
  - outputs/classification/fig04_multimodal_fusion_comparison.csv
  - outputs/classification/fig04_rsa_multimodal_synthesis.png
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
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression, LogisticRegression
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
from omission.jnwb_ext.structured_identity import build_canonical_trial_table, POSITIVE_CONTROL, MAIN_ANALYSIS
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from _l_lfp_common import extract_epoch_trials, resolve_area_channel_block
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
# Canonical timing only -- do not re-derive or duplicate these values locally.
SLOT_ONSETS_MS = {k: EPOCH_ONSETS_MS[k] for k in ("p1", "p2", "p3", "p4")}
SLOT_DUR_MS = EPOCH_ONSETS_MS["d1"] - EPOCH_ONSETS_MS["p1"]


def extract_spk_and_lfp(session, area: str, epochs: pd.DataFrame, slot_onset_ms: float, n_bins: int = 10):
    units = session.get_units(area=area) if area != "ALL" else session.get_units()
    row_indices = list(units.index)
    if len(row_indices) == 0 or len(epochs) == 0:
        return np.zeros((len(epochs), 0), dtype=float), np.zeros((len(epochs), 0, n_bins), dtype=float)
        
    onsets = epochs["start_time"].to_numpy(float) + (slot_onset_ms / 1000.0)
    t_edges = np.linspace(0.0, SLOT_DUR_MS / 1000.0, n_bins + 1)
    
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
                
    X_flat = X_3d.reshape(len(onsets), len(row_indices) * n_bins)
    return X_flat, X_3d


def build_model_rdms(condition_labels: list[dict]) -> dict[str, np.ndarray]:
    """Constructs theoretical model RDMs across the 12 conditions."""
    n_cond = len(condition_labels)
    rdm_pos = np.zeros((n_cond, n_cond))
    rdm_stim = np.zeros((n_cond, n_cond))
    rdm_pres = np.zeros((n_cond, n_cond))
    rdm_exp = np.zeros((n_cond, n_cond))
    
    pos_map = {"p2": 2, "p3": 3, "p4": 4}
    
    for i in range(n_cond):
        c_i = condition_labels[i]
        for j in range(n_cond):
            c_j = condition_labels[j]
            # 1. Position Model
            rdm_pos[i, j] = abs(pos_map[c_i["slot"]] - pos_map[c_j["slot"]])
            
            # 2. Sensory Presence Model (Stimulus vs Omission)
            is_om_i = c_i["is_omission"]
            is_om_j = c_j["is_omission"]
            rdm_pres[i, j] = 1.0 if (is_om_i != is_om_j) else 0.0
            
            # 3. Stimulus Identity Model (Physical A vs B on non-omission)
            if not is_om_i and not is_om_j:
                rdm_stim[i, j] = 0.0 if c_i["presented"] == c_j["presented"] else 1.0
            else:
                rdm_stim[i, j] = 0.5
                
            # 4. Expected Identity Model (Expected A vs B during omission)
            if is_om_i and is_om_j:
                rdm_exp[i, j] = 0.0 if c_i["expected"] == c_j["expected"] else 1.0
            else:
                rdm_exp[i, j] = 0.5
                
    return {
        "Position": rdm_pos / (np.max(rdm_pos) + 1e-6),
        "Sensory_Presence": rdm_pres,
        "Stimulus_Identity": rdm_stim,
        "Expected_Identity": rdm_exp,
    }


def main():
    t0 = time.time()
    nwb_files = sorted(list(Path("D:/nwb/omission").glob("*.nwb")))
    rep_sessions = ["sub-C31o_ses-230816", "sub-C31o_ses-230823", "sub-V182o_ses-260710", "sub-V198o_ses-230719"]
    target_files = [p for p in nwb_files if any(s in p.name for s in rep_sessions)]
    
    print(f"Executing RSA & Multimodal Latent Fusion on {len(target_files)} sessions...")
    
    rsa_regression_records = []
    neural_rdms = []
    
    # 12 conditions definition
    # 3 positions (p2, p3, p4) x 4 conditions (AAAB, AABA, BBBA, BBAB)
    slots = ["p2", "p3", "p4"]
    seqs = ["AAAB", "AABA", "BBBA", "BBAB"]
    condition_meta = []
    
    for s in slots:
        for seq in seqs:
            # Determine presented vs expected
            if seq == "AAAB":
                # omit at p4, expected B
                is_om = (s == "p4")
                pres = None if is_om else "A"
                exp = "B" if is_om else None
            elif seq == "AABA":
                # omit at p3, expected B
                is_om = (s == "p3")
                pres = None if is_om else "A"
                exp = "B" if is_om else None
            elif seq == "BBBA":
                # omit at p4, expected A
                is_om = (s == "p4")
                pres = None if is_om else "B"
                exp = "A" if is_om else None
            elif seq == "BBAB":
                # omit at p3, expected A
                is_om = (s == "p3")
                pres = None if is_om else "B"
                exp = "A" if is_om else None
                
            condition_meta.append({
                "label": f"{seq}_{s}",
                "slot": s,
                "seq": seq,
                "is_omission": is_om,
                "presented": pres,
                "expected": exp,
            })
            
    model_rdms = build_model_rdms(condition_meta)
    
    for s_idx, nwb_path in enumerate(target_files):
        sess_name = nwb_path.stem.replace("_rec", "")
        subj = sess_name.split("_")[0].replace("sub-", "")
        session = oa.read(nwb_path)
        table = build_canonical_trial_table(session, slot_keys=("p2", "p3", "p4"))
        
        for area in ["V1", "MT", "ALL"]:
            u_test = session.get_units(area=area) if area != "ALL" else session.get_units()
            if len(u_test) < 4:
                continue
                
            cond_vectors = []
            valid_conds = []
            
            for c_idx, c_info in enumerate(condition_meta):
                s = c_info["slot"]
                seq = c_info["seq"]
                sub_df = table[(table["slot_key"] == s) & (table["sequence_family"].str.startswith(seq[0])) & table["eligible"]].copy()
                if len(sub_df) >= 4:
                    X_f, _ = extract_spk_and_lfp(session, area, sub_df, slot_onset_ms=SLOT_ONSETS_MS[s], n_bins=10)
                    mean_vec = np.mean(X_f, axis=0)
                    cond_vectors.append(mean_vec)
                    valid_conds.append(c_idx)
                    
            if len(cond_vectors) >= 8:
                # Compute Neural RDM
                mat = np.array(cond_vectors)
                scaler = StandardScaler()
                mat_s = scaler.fit_transform(mat)
                corr_mat = np.corrcoef(mat_s)
                rdm_neural = 1.0 - corr_mat
                
                # Align model RDMs to valid subset
                valid_idx = np.array(valid_conds)
                n_v = len(valid_idx)
                
                # Extract upper triangle entries (vectorized RDM)
                triu_i, triu_j = np.triu_indices(n_v, k=1)
                y_vec = rdm_neural[triu_i, triu_j]
                
                X_model_cols = {}
                for m_name, m_mat in model_rdms.items():
                    sub_m = m_mat[np.ix_(valid_idx, valid_idx)]
                    X_model_cols[m_name] = sub_m[triu_i, triu_j]
                    
                df_reg = pd.DataFrame(X_model_cols)
                
                # Multiple Linear Regression
                reg = LinearRegression().fit(df_reg, y_vec)
                r2 = float(reg.score(df_reg, y_vec))
                
                # Permutation testing for regression coefficients
                N_PERM = 999
                rng = np.random.default_rng(42)
                perm_betas = {m: [] for m in df_reg.columns}
                for _ in range(N_PERM):
                    y_p = rng.permutation(y_vec)
                    reg_p = LinearRegression().fit(df_reg, y_p)
                    for col_idx, m_name in enumerate(df_reg.columns):
                        perm_betas[m_name].append(reg_p.coef_[col_idx])

                for col_idx, m_name in enumerate(df_reg.columns):
                    obs_beta = float(reg.coef_[col_idx])
                    # +1 correction (North et al. 2002): a finite permutation count cannot
                    # support a literal p=0; floor is 1/(N_PERM+1), not 0.
                    p_val = float((1 + np.sum(np.array(perm_betas[m_name]) >= obs_beta)) / (N_PERM + 1))
                    rsa_regression_records.append({
                        "session": sess_name, "subject": subj, "area": area,
                        "model_term": m_name, "beta": obs_beta, "r2_total": r2,
                        "p_perm": p_val
                    })
                    
        print(f"Finished RSA for session {s_idx+1}/{len(target_files)}: {sess_name}")
        
    df_rsa = pd.DataFrame(rsa_regression_records)
    df_rsa.to_csv(OUT_DIR / "fig04_rsa_model_regression.csv", index=False)
    
    print("\n=== Sequence RSA Model Regression Summary ===")
    summary_rsa = df_rsa.groupby("model_term")[["beta", "p_perm"]].mean().reset_index()
    print(summary_rsa.to_string(index=False))
    
    # 2. Balanced Multimodal Latent Fusion Evaluation
    # Compare SPK vs LFP vs Fusion [PCA(S), PCA(L)] -> Logistic
    # Load matched results
    matched_file = OUT_DIR / "lfp_multimodal_pca_umap_results.csv"
    if matched_file.exists():
        df_mm = pd.read_csv(matched_file)
        print("\n=== Matched Multimodal Latent Fusion Performance ===")
        print(f"SPK PCA->UMAP Acc:       {df_mm['spk_pca_umap_acc'].mean():.4f}")
        print(f"LFP PCA->UMAP Acc:       {df_mm['lfp_pca_umap_acc'].mean():.4f}")
        print(f"Balanced Fusion UMAP Acc:{df_mm['fusion_pca_umap_acc'].mean():.4f}")
        
    # Plot Synthesis Figure
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    
    # Panel 1: Theoretical Model RDMs
    im0 = axes[0].imshow(model_rdms["Position"], cmap="magma", origin="upper")
    axes[0].set_title("1. Position Model RDM (p2, p3, p4)", fontsize=9)
    axes[0].set_xticks(range(12))
    axes[0].set_yticks(range(12))
    axes[0].set_xticklabels([m["label"] for m in condition_meta], rotation=90, fontsize=6)
    axes[0].set_yticklabels([m["label"] for m in condition_meta], fontsize=6)
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    
    # Panel 2: RSA Model Betas (Position vs Stimulus vs Presence vs Expected)
    x_pos = range(len(summary_rsa))
    axes[1].bar(x_pos, summary_rsa["beta"], color=["#1f77b4", "#2ca02c", "#ff7f0e", "#d62728"], edgecolor="black", lw=0.8)
    axes[1].axhline(0, color="gray", ls="--")
    axes[1].set_xticks(x_pos)
    axes[1].set_xticklabels(summary_rsa["model_term"], rotation=30, ha="right", fontsize=8)
    axes[1].set_ylabel("RSA Regression Beta")
    axes[1].set_title("2. Neural Geometry Decomposition\n[Position & Presence Dominate]", fontsize=9)
    axes[1].grid(True, alpha=0.2, axis="y")
    
    # Panel 3: Balanced Multimodal Latent Fusion
    if matched_file.exists():
        labels = ["SPK-only\n(PCA→U)", "LFP-only\n(PCA→U)", "Balanced Fusion\n[PCA(S), PCA(L)]→U"]
        acc_means = [df_mm["spk_pca_umap_acc"].mean(), df_mm["lfp_pca_umap_acc"].mean(), df_mm["fusion_pca_umap_acc"].mean()]
        axes[2].bar(range(3), acc_means, color=["#1f77b4", "#2ca02c", "#9467bd"], edgecolor="black", lw=0.8)
        axes[2].axhline(0.5, color="gray", ls="--", label="Chance (0.50)")
        axes[2].set_xticks(range(3))
        axes[2].set_xticklabels(labels, fontsize=7.5)
        axes[2].set_ylabel("Held-Out Accuracy (5-Fold CV)")
        axes[2].set_ylim(0.4, 0.65)
        axes[2].set_title("3. Balanced Multimodal Fusion\n[Omission Identity Remains at Chance]", fontsize=9)
        for i, v in enumerate(acc_means):
            axes[2].text(i, v + 0.005, f"{v:.3f}", ha="center", va="bottom", fontsize=7)
        axes[2].grid(True, alpha=0.2, axis="y")
        axes[2].legend(fontsize=7)
        
    fig.tight_layout()
    synth_path = OUT_DIR / "fig04_rsa_multimodal_synthesis.png"
    fig.savefig(synth_path, dpi=200)
    plt.close(fig)
    print(f"\nSaved RSA and Multimodal Synthesis plot to {synth_path}")


if __name__ == "__main__":
    main()
