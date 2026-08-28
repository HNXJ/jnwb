#!/usr/bin/env python3
"""Audit and compute exact BH-FDR corrected inference for temporal context decoding (Panel B)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from statsmodels.stats.multitest import multipletests

HERE = Path(__file__).resolve()
OA_ROOT = HERE.parents[1]

df = pd.read_csv(OA_ROOT / "outputs" / "classification" / "fig04_battery_results.csv")
sub_ctx = df[df["analysis"] == "2_temporal_context"].copy().reset_index(drop=True)

p_vals = sub_ctx["p_perm"].to_numpy()
reject, q_vals, _, _ = multipletests(p_vals, alpha=0.05, method="fdr_bh")

sub_ctx["q_fdr"] = q_vals
sub_ctx["fdr_sig"] = reject

nominal_sig = (p_vals < 0.05).sum()
fdr_sig = reject.sum()
n_total = len(sub_ctx)

print(f"=== Temporal Context Full-Corpus Inference (n={n_total} area populations across 22 sessions) ===")
print(f"Mean Balanced Accuracy: {sub_ctx['score_bal_acc'].mean():.4f} +/- {sub_ctx['score_bal_acc'].sem():.4f} (Chance = 0.2500)")
print(f"Median Balanced Accuracy: {sub_ctx['score_bal_acc'].median():.4f}")
print(f"Nominally Significant (p_perm < 0.05): {nominal_sig}/{n_total} ({nominal_sig/n_total*100:.1f}%)")
print(f"BH-FDR Corrected Significant (q_fdr < 0.05): {fdr_sig}/{n_total} ({fdr_sig/n_total*100:.1f}%)")

# Save detailed inference audit
sub_ctx.to_csv(OA_ROOT / "outputs" / "classification" / "fig04_temporal_context_fdr_audit.csv", index=False)
