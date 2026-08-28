#!/usr/bin/env python3
"""Synthesize Figure 04 Latent Manifold Search results and generate summary tables and plots."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]
OUT_DIR = OA_ROOT / "outputs" / "classification" / "fig04_diagnostics"

df_dec = pd.read_csv(OUT_DIR / "manifold_search_results.csv")
df_traj = pd.read_csv(OUT_DIR / "manifold_trajectory_separation.csv")
df_cp = pd.read_csv(OUT_DIR / "manifold_crossposition_geometry.csv")

print("=== Manifold Search Total Runs ===")
print(f"Decoding records: {len(df_dec)}")
print(f"Trajectory records: {len(df_traj)}")
print(f"Cross-position records: {len(df_cp)}")

# 1. Synthesis & Aggregated Summary
summary_dec = df_dec.groupby(["target", "method", "encoder", "d"])[["acc", "auc"]].mean().reset_index()
summary_cp = df_cp.groupby(["method"])[["acc_transfer", "R_ratio"]].mean().reset_index() if len(df_cp) else pd.DataFrame()

print("\n=== Manifold Decodability across Methods & Encoders (d=5) ===")
sub_d5 = summary_dec[summary_dec["d"] == 5].sort_values(["target", "method", "encoder"])
print(sub_d5.to_string(index=False))

print("\n=== Cross-Position Manifold Generalization & R-Ratio ===")
print(summary_cp.to_string(index=False))

# 2. Plot Synthesis Figure
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))

# Panel 1: Stimulus vs Omission across Manifold Methods (d=5, Logistic Regression)
sub_dec = summary_dec[(summary_dec["d"] == 5) & (summary_dec["encoder"] == "Logistic_Regression")]
methods = ["Direct", "PCA", "UMAP", "PCA_UMAP"]
x_m = np.arange(len(methods))

stim_vals = [sub_dec[(sub_dec["target"]=="1_Positive_Control_Stimulus") & (sub_dec["method"]==m)]["acc"].mean() for m in methods]
omit_p2_vals = [sub_dec[(sub_dec["target"]=="3_Omission_Identity_p2") & (sub_dec["method"]==m)]["acc"].mean() for m in methods]
omit_p3_vals = [sub_dec[(sub_dec["target"]=="3_Omission_Identity_p3") & (sub_dec["method"]==m)]["acc"].mean() for m in methods]

axes[0].bar(x_m - 0.25, stim_vals, 0.25, label="Stimulus (A vs B)", color="#1f77b4")
axes[0].bar(x_m, omit_p2_vals, 0.25, label="Omission p2 (X|A vs X|B)", color="#e377c2")
axes[0].bar(x_m + 0.25, omit_p3_vals, 0.25, label="Omission p3 (X|A vs X|B)", color="#7f7f7f")
axes[0].axhline(0.5, color="black", ls="--")
axes[0].set_xticks(x_m)
axes[0].set_xticklabels(methods)
axes[0].set_ylabel("LOCO Balanced Accuracy")
axes[0].set_title("1. Manifold Decodability: Stim vs Omit (d=5)", fontsize=9.5)
axes[0].set_ylim(0.3, 1.05)
axes[0].legend(fontsize=7.5)
axes[0].grid(True, alpha=0.3, axis="y")

# Panel 2: Trajectory Separation D_AB(t) across 10 temporal bins during p2 Omission
if len(df_traj):
    traj_mean = df_traj.groupby("time_ms")[["d_ab_observed", "d_ab_null"]].mean().reset_index()
    axes[1].plot(traj_mean["time_ms"], traj_mean["d_ab_observed"], "o-", label="Observed ||mu_A(t) - mu_B(t)||", color="#d62728", lw=2)
    axes[1].plot(traj_mean["time_ms"], traj_mean["d_ab_null"], "--", label="Within-Cycle Null", color="gray", lw=1.5)
    axes[1].fill_between(traj_mean["time_ms"], traj_mean["d_ab_null"]*0.9, traj_mean["d_ab_null"]*1.1, color="gray", alpha=0.2)
    axes[1].set_xlabel("Time from Omission Onset (ms)")
    axes[1].set_ylabel("Population Distance (L2 norm)")
    axes[1].set_title("2. Trajectory Dynamics: D_AB(t) in Omission Window", fontsize=9.5)
    axes[1].legend(fontsize=7.5)
    axes[1].grid(True, alpha=0.3)
    
# Panel 3: Cross-Position Generalization Transfer & Geometric Ratio R
if len(summary_cp):
    axes[2].bar(x_m - 0.15, summary_cp["acc_transfer"], 0.3, label="Transfer Acc (p2->p3)", color="#2ca02c")
    axes[2].axhline(0.5, color="gray", ls="--")
    ax2_twin = axes[2].twinx()
    ax2_twin.plot(x_m + 0.15, summary_cp["R_ratio"], "s-", color="purple", label="Geometric Ratio R")
    ax2_twin.axhline(1.0, color="purple", ls=":")
    axes[2].set_xticks(x_m)
    axes[2].set_xticklabels(methods)
    axes[2].set_ylabel("Transfer Accuracy")
    ax2_twin.set_ylabel("Ratio R (Between / Within-Across)", color="purple")
    axes[2].set_title("3. Cross-Position Manifold Invariance (p2 -> p3)", fontsize=9.5)
    axes[2].set_ylim(0.2, 0.8)
    ax2_twin.set_ylim(0.0, 2.0)
    axes[2].legend(loc="upper left", fontsize=7.5)
    ax2_twin.legend(loc="upper right", fontsize=7.5)
    axes[2].grid(True, alpha=0.3, axis="y")
    
fig.tight_layout()
synth_path = OUT_DIR / "fig04_manifold_search_synthesis.png"
fig.savefig(synth_path, dpi=120)
plt.close(fig)
print(f"\nSaved Fig04 manifold search synthesis figure to {synth_path}")

receipt = {
    "generated_utc": datetime.now(timezone.utc).isoformat(),
    "python": sys.version,
    "n_sessions": 4,
    "total_decoding_runs": len(df_dec),
}
with open(OUT_DIR / "manifold_search_receipt.json", "w") as f:
    json.dump(receipt, f, indent=2)
