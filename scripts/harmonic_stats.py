"""
harmonic_stats.py
=================
Perform Wilcoxon tests comparing PAC, n:m phase coupling, and spike-LFP coupling
across contexts for high SNR channels.

Outputs a markdown summary to: outputs/harmonic/harmonic_stats_report.md
"""

import os
import numpy as np
import pandas as pd
import scipy.stats as stats

OUTPUT_DIR = "outputs/harmonic"
LFP_CSV = f"{OUTPUT_DIR}/lfp_lfp_harmonic.csv"
SPK_CSV = f"{OUTPUT_DIR}/spk_lfp_harmonic.csv"
OUT_MD = f"{OUTPUT_DIR}/harmonic_stats_report.md"

def fdr_bh(p_vals):
    p_vals = np.asarray(p_vals)
    n = len(p_vals)
    if n == 0:
        return np.array([])
    sorted_idx = np.argsort(p_vals)
    sorted_p = p_vals[sorted_idx]
    
    q_vals = np.zeros(n)
    curr_min = 1.0
    for i in range(n - 1, -1, -1):
        q = sorted_p[i] * n / (i + 1)
        curr_min = min(curr_min, q)
        q_vals[sorted_idx[i]] = curr_min
    return q_vals

def run_stats():
    if not os.path.exists(LFP_CSV) or not os.path.exists(SPK_CSV):
        print("Error: Harmonic data files not found.")
        return
        
    df_lfp = pd.read_csv(LFP_CSV)
    df_spk = pd.read_csv(SPK_CSV)
    
    # Run stats for LFP-to-LFP (PAC + n:m coupling)
    # Pivot contexts per channel
    pivot_lfp = df_lfp.pivot(
        index=["session_id", "channel_global", "area"],
        columns="context",
        values=["pac_mi", "h2_plv", "h3_plv", "h4_plv", "h5_plv"]
    )
    
    comparisons = [
        ("omission", "standard"),
        ("omission", "baseline")
    ]
    
    lfp_metrics = ["pac_mi", "h2_plv", "h3_plv", "h4_plv", "h5_plv"]
    lfp_results = []
    
    for comp_name, (ctxA, ctxB) in [("Omission vs Standard", ("omission", "standard")), 
                                    ("Omission vs Baseline", ("omission", "baseline"))]:
        for metric in lfp_metrics:
            valA = pivot_lfp[(metric, ctxA)].values
            valB = pivot_lfp[(metric, ctxB)].values
            
            mask = ~np.isnan(valA) & ~np.isnan(valB)
            valA_clean = valA[mask]
            valB_clean = valB[mask]
            
            n_paired = len(valA_clean)
            if n_paired < 5:
                continue
                
            meanA = np.mean(valA_clean)
            meanB = np.mean(valB_clean)
            mean_diff = meanA - meanB
            
            try:
                stat, pval = stats.wilcoxon(valA_clean, valB_clean)
            except ValueError:
                stat, pval = np.nan, 1.0
                
            lfp_results.append({
                "Comparison": comp_name,
                "Metric": metric,
                "N": n_paired,
                "Mean_A": meanA,
                "Mean_B": meanB,
                "Mean_Diff": mean_diff,
                "Stat": stat,
                "P_val": pval
            })
            
    # FDR BH
    res_lfp = pd.DataFrame(lfp_results)
    if len(res_lfp) > 0:
        res_lfp["Q_val"] = fdr_bh(res_lfp["P_val"].values)
        res_lfp["Significant"] = res_lfp["Q_val"] < 0.05
    
    # Run stats for Spk-to-LFP (theta, h2, h3, h4, h5 PLVs)
    pivot_spk = df_spk.pivot(
        index=["session_id", "channel_global", "unit_id", "area", "group", "wf_class"],
        columns="context",
        values=["theta_plv", "h2_plv", "h3_plv", "h4_plv", "h5_plv"]
    )
    
    spk_metrics = ["theta_plv", "h2_plv", "h3_plv", "h4_plv", "h5_plv"]
    spk_results = []
    
    for comp_name, (ctxA, ctxB) in [("Omission vs Standard", ("omission", "standard")), 
                                    ("Omission vs Baseline", ("omission", "baseline"))]:
        for metric in spk_metrics:
            valA = pivot_spk[(metric, ctxA)].values
            valB = pivot_spk[(metric, ctxB)].values
            
            mask = ~np.isnan(valA) & ~np.isnan(valB)
            valA_clean = valA[mask]
            valB_clean = valB[mask]
            
            n_paired = len(valA_clean)
            if n_paired < 5:
                continue
                
            meanA = np.mean(valA_clean)
            meanB = np.mean(valB_clean)
            mean_diff = meanA - meanB
            
            try:
                stat, pval = stats.wilcoxon(valA_clean, valB_clean)
            except ValueError:
                stat, pval = np.nan, 1.0
                
            spk_results.append({
                "Comparison": comp_name,
                "Metric": metric,
                "N": n_paired,
                "Mean_A": meanA,
                "Mean_B": meanB,
                "Mean_Diff": mean_diff,
                "Stat": stat,
                "P_val": pval
            })
            
    res_spk = pd.DataFrame(spk_results)
    if len(res_spk) > 0:
        res_spk["Q_val"] = fdr_bh(res_spk["P_val"].values)
        res_spk["Significant"] = res_spk["Q_val"] < 0.05
        
    # Write MD report
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# SpSAM Harmonic Analysis Statistical Report\n\n")
        f.write("**Method**: Paired Wilcoxon Signed-Rank Test per high SNR channel/unit. FDR corrected using Benjamini-Hochberg.\n\n")
        
        f.write("## 1. LFP-to-LFP Harmonic Modulation (N = 9 channels)\n\n")
        for comp_name in ["Omission vs Standard", "Omission vs Baseline"]:
            f.write(f"### {comp_name}\n\n")
            f.write("| Metric | Mean Omission | Mean Comparison | Mean Diff | Wilcoxon W | P-value | FDR Q-value | Sig (FDR < 0.05) |\n")
            f.write("|------|---------------|-----------------|-----------|------------|---------|-------------|------------------|\n")
            
            sub = res_lfp[res_lfp["Comparison"] == comp_name]
            for _, row in sub.iterrows():
                sig_str = "**Yes**" if row["Significant"] else "No"
                f.write(f"| {row['Metric']} | {row['Mean_A']:.4f} | {row['Mean_B']:.4f} | {row['Mean_Diff']:.4f} | {row['Stat']:.1f} | {row['P_val']:.2e} | {row['Q_val']:.2e} | {sig_str} |\n")
            f.write("\n")
            
        f.write("## 2. Spiking-to-LFP Harmonic Coupling (N = 10 units)\n\n")
        for comp_name in ["Omission vs Standard", "Omission vs Baseline"]:
            f.write(f"### {comp_name}\n\n")
            f.write("| Metric | Mean Omission | Mean Comparison | Mean Diff | Wilcoxon W | P-value | FDR Q-value | Sig (FDR < 0.05) |\n")
            f.write("|------|---------------|-----------------|-----------|------------|---------|-------------|------------------|\n")
            
            sub = res_spk[res_spk["Comparison"] == comp_name]
            for _, row in sub.iterrows():
                sig_str = "**Yes**" if row["Significant"] else "No"
                f.write(f"| {row['Metric']} | {row['Mean_A']:.4f} | {row['Mean_B']:.4f} | {row['Mean_Diff']:.4f} | {row['Stat']:.1f} | {row['P_val']:.2e} | {row['Q_val']:.2e} | {sig_str} |\n")
            f.write("\n")
            
    print(f"Harmonic stats report written to {OUT_MD}")

if __name__ == "__main__":
    run_stats()
