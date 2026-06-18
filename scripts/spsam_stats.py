"""
spsam_stats.py
==============
Perform paired Wilcoxon signed-rank tests comparing Spike-LFP coupling (PLV)
between Omission, Standard, and Baseline contexts for stable units.

Outputs a markdown summary to: outputs/spsam/spsam_stats_report.md
"""

import os
import numpy as np
import pandas as pd
import scipy.stats as stats

OUTPUT_DIR = "outputs/spsam"
COUPLING_CSV = f"{OUTPUT_DIR}/grand_unit_lfp_coupling.csv"
OUT_MD = f"{OUTPUT_DIR}/spsam_stats_report.md"

BANDS = ["theta", "alpha", "beta1", "beta2", "gamma1", "gamma2", "gamma3"]

def fdr_bh(p_vals):
    """Manual Benjamini-Hochberg FDR correction."""
    p_vals = np.asarray(p_vals)
    n = len(p_vals)
    if n == 0:
        return np.array([])
    sorted_idx = np.argsort(p_vals)
    sorted_p = p_vals[sorted_idx]
    
    q_vals = np.zeros(n)
    curr_min = 1.0
    for i in range(n - 1, -1, -1):
        # q = p * N / rank
        q = sorted_p[i] * n / (i + 1)
        curr_min = min(curr_min, q)
        q_vals[sorted_idx[i]] = curr_min
    return q_vals

def run_stats():
    if not os.path.exists(COUPLING_CSV):
        print(f"Error: {COUPLING_CSV} not found.")
        return
        
    df = pd.read_csv(COUPLING_CSV)
    # Filter stable only
    df = df[df["is_stable"]].copy()
    
    if len(df) == 0:
        print("Error: No stable units found.")
        return

    print(f"Loaded {len(df)} rows of stable unit coupling.")
    
    # Pivot contexts to get paired values per unit
    # Unit identifier is (session_id, unit_id)
    pivot_df = df.pivot(
        index=["session_id", "unit_id", "area", "layer", "group", "wf_class"],
        columns="context",
        values=[f"{b}_plv" for b in BANDS]
    )
    
    # We want to do two comparisons:
    # 1. Omission vs Standard
    # 2. Omission vs Baseline
    
    results = []
    
    # Run globally and per-area
    target_areas = ["GLOBAL", "PFC", "FEF", "V1", "V2"]
    
    for comp_name, (ctxA, ctxB) in [("Omission vs Standard", ("omission", "standard")), 
                                    ("Omission vs Baseline", ("omission", "baseline"))]:
        for area in target_areas:
            if area == "GLOBAL":
                area_sub = pivot_df
            else:
                area_sub = pivot_df[pivot_df.index.get_level_values("area") == area]
                
            n_units = len(area_sub)
            if n_units < 5:
                # Too few units for statistics
                continue
                
            for band in BANDS:
                valA = area_sub[(f"{band}_plv", ctxA)].values
                valB = area_sub[(f"{band}_plv", ctxB)].values
                
                # Filter out any NaNs
                mask = ~np.isnan(valA) & ~np.isnan(valB)
                valA_clean = valA[mask]
                valB_clean = valB[mask]
                
                n_paired = len(valA_clean)
                if n_paired < 5:
                    continue
                    
                meanA = np.mean(valA_clean)
                meanB = np.mean(valB_clean)
                mean_diff = meanA - meanB
                
                # Paired Wilcoxon
                try:
                    stat, pval = stats.wilcoxon(valA_clean, valB_clean)
                except ValueError:
                    # Occurs if all differences are zero
                    stat, pval = np.nan, 1.0
                    
                results.append({
                    "Comparison": comp_name,
                    "Area": area,
                    "Band": band,
                    "N": n_paired,
                    "Mean_A": meanA,
                    "Mean_B": meanB,
                    "Mean_Diff": mean_diff,
                    "Stat": stat,
                    "P_val": pval
                })
                
    # Apply FDR correction
    res_df = pd.DataFrame(results)
    res_df["Q_val"] = fdr_bh(res_df["P_val"].values)
    res_df["Significant"] = res_df["Q_val"] < 0.05
    
    # Save CSV for reference
    res_df.to_csv(f"{OUTPUT_DIR}/spsam_stats_results.csv", index=False)
    
    # Write Markdown report
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("# SpSAM Statistical Analysis Report\n\n")
        f.write(f"**Source Data**: `grand_unit_lfp_coupling.csv` (Stable units only)\n")
        f.write(f"**Method**: Paired Wilcoxon Signed-Rank Test per unit. FDR corrected using Benjamini-Hochberg (BH) method.\n\n")
        
        for comp_name in ["Omission vs Standard", "Omission vs Baseline"]:
            f.write(f"## {comp_name}\n\n")
            
            sub = res_df[res_df["Comparison"] == comp_name].copy()
            
            # Print Global first, then areas
            for area in target_areas:
                area_sub = sub[sub["Area"] == area].copy()
                if len(area_sub) == 0:
                    continue
                    
                f.write(f"### Area: {area} (N = {area_sub['N'].iloc[0]} units)\n\n")
                f.write("| Band | Mean Omission | Mean Comparison | Mean Diff | Wilcoxon W | P-value | FDR Q-value | Sig (FDR < 0.05) |\n")
                f.write("|------|---------------|-----------------|-----------|------------|---------|-------------|------------------|\n")
                
                for _, row in area_sub.iterrows():
                    sig_str = "**Yes**" if row["Significant"] else "No"
                    f.write(f"| {row['Band']} | {row['Mean_A']:.4f} | {row['Mean_B']:.4f} | {row['Mean_Diff']:.4f} | {row['Stat']:.1f} | {row['P_val']:.2e} | {row['Q_val']:.2e} | {sig_str} |\n")
                f.write("\n")
                
    print(f"Stats report written to {OUT_MD}")

if __name__ == "__main__":
    run_stats()
