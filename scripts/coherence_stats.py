"""
coherence_stats.py
==================
Perform paired Wilcoxon signed-rank tests on cross-area LFP-to-LFP coherence
comparing Omission vs Stimulus and Omission vs Baseline.

Outputs to: outputs/coherence/coherence_stats_report.md
"""

import os
import numpy as np
import pandas as pd
import scipy.stats as stats

OUTPUT_DIR = "outputs/coherence"
RESULTS_CSV = f"{OUTPUT_DIR}/coherence_results.csv"
OUT_MD = f"{OUTPUT_DIR}/coherence_stats_report.md"

BANDS = ["theta", "alpha", "beta", "gamma"]

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
    if not os.path.exists(RESULTS_CSV):
        print("Error: Coherence results CSV not found.")
        return
        
    df = pd.read_csv(RESULTS_CSV)
    
    # We want to pivot contexts (epochs) to compare them per session and area pair
    pivot_df = df.pivot(
        index=["session_id", "area1", "area2"],
        columns="epoch",
        values=[f"{b}_coherence" for b in BANDS]
    )
    
    # We will test common area pairs that appear in at least 5 sessions
    area_pairs = pivot_df.index.to_frame()[["area1", "area2"]].drop_duplicates()
    
    results = []
    
    comparisons = [
        ("Omission vs Stimulus", "omission", "stimulus"),
        ("Omission vs Baseline", "omission", "baseline")
    ]
    
    for comp_name, epochA, epochB in comparisons:
        for _, (a1, a2) in area_pairs.iterrows():
            pair_sub = pivot_df[
                (pivot_df.index.get_level_values("area1") == a1) & 
                (pivot_df.index.get_level_values("area2") == a2)
            ]
            
            n_sessions = len(pair_sub)
            if n_sessions < 2:
                continue
                
            for band in BANDS:
                valA = pair_sub[(f"{band}_coherence", epochA)].values
                valB = pair_sub[(f"{band}_coherence", epochB)].values
                
                # Filter out NaNs
                mask = ~np.isnan(valA) & ~np.isnan(valB)
                valA_clean = valA[mask]
                valB_clean = valB[mask]
                
                n_paired = len(valA_clean)
                if n_paired < 2:
                    continue
                    
                meanA = np.mean(valA_clean)
                meanB = np.mean(valB_clean)
                mean_diff = meanA - meanB
                
                try:
                    stat, pval = stats.wilcoxon(valA_clean, valB_clean)
                except ValueError:
                    stat, pval = np.nan, 1.0
                    
                results.append({
                    "Comparison": comp_name,
                    "Area1": a1,
                    "Area2": a2,
                    "Band": band,
                    "N_sessions": n_paired,
                    "Mean_A": meanA,
                    "Mean_B": meanB,
                    "Mean_Diff": mean_diff,
                    "Stat": stat,
                    "P_val": pval
                })
                
    res_df = pd.DataFrame(results)
    if len(res_df) == 0:
        res_df = pd.DataFrame(columns=["Comparison", "Area1", "Area2", "Band", "N_sessions", "Mean_A", "Mean_B", "Mean_Diff", "Stat", "P_val", "Q_val", "Significant"])
    else:
        res_df["Q_val"] = fdr_bh(res_df["P_val"].values)
        res_df["Significant"] = res_df["Q_val"] < 0.05
        
    # Write report
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# LFP-to-LFP Cross-Area Coherence Stats Report\n\n")
        f.write("**Method**: Paired Wilcoxon Signed-Rank Test across sessions per area pair. FDR corrected using Benjamini-Hochberg.\n\n")
        
        for comp_name in ["Omission vs Stimulus", "Omission vs Baseline"]:
            f.write(f"## {comp_name}\n\n")
            f.write("| Area Pair | Band | Mean Omission | Mean Comparison | Mean Diff | Sessions | Wilcoxon W | P-value | FDR Q-value | Sig (FDR < 0.05) |\n")
            f.write("|---|---|---|---|---|---|---|---|---|---|\n")
            
            sub = res_df[res_df["Comparison"] == comp_name]
            for _, row in sub.iterrows():
                sig_str = "**Yes**" if row["Significant"] else "No"
                f.write(f"| {row['Area1']}-{row['Area2']} | {row['Band']} | {row['Mean_A']:.4f} | {row['Mean_B']:.4f} | {row['Mean_Diff']:.4f} | {row['N_sessions']} | {row['Stat']:.1f} | {row['P_val']:.2e} | {row['Q_val']:.2e} | {sig_str} |\n")
            f.write("\n")
            
    print(f"Coherence stats report written to {OUT_MD}")

if __name__ == "__main__":
    run_stats()
