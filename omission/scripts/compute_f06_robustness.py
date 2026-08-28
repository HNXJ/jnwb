#!/usr/bin/env python3
"""F06 Stage A Robustness Battery and Validation.

Performs session-aware inference, Spearman sensitivity, leave-one-session-out,
subject sensitivity, leave-one-subject-out, and session-cluster bootstrap on the
matched SPK-LFP substrate (f06_matched_substrate_v1.csv).
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import pearsonr, spearmanr

SUBSTRATE_PATH = Path("omission/outputs/f06_substrate/f06_matched_substrate_v1.csv")
OUT_DIR = Path("omission/outputs/f06_substrate")
BANDS = ["theta", "alpha", "beta", "low_gamma", "high_gamma"]

def fdr_bh(p_values: np.ndarray) -> np.ndarray:
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    order = np.argsort(p)
    ranked = p[order]
    q = ranked * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    q_out = np.empty_like(q)
    q_out[order] = np.clip(q, 0, 1)
    return q_out

def main():
    df = pd.read_csv(SUBSTRATE_PATH)
    n_cells = len(df)
    n_sessions = df["session"].nunique()
    n_subjects = df["subject"].nunique()
    
    print(f"Loaded {n_cells} matched cells across {n_sessions} sessions and {n_subjects} subjects.")
    
    # 1. Basic descriptors
    cells_per_session = df["session"].value_counts().to_dict()
    cells_per_subject = df["subject"].value_counts().to_dict()
    cells_per_area = df["area"].value_counts().to_dict()
    
    # 2. Model Stack and Correlations
    results_primary = []
    loso_records = []
    losubj_records = []
    subj_strat_records = []
    
    # Standardize per contrast
    spk_ob_z = (df["spk_ob_effect_hz_mean"] - df["spk_ob_effect_hz_mean"].mean()) / df["spk_ob_effect_hz_mean"].std()
    spk_os_z = (df["spk_os_effect_hz_mean"] - df["spk_os_effect_hz_mean"].mean()) / df["spk_os_effect_hz_mean"].std()
    
    for band in BANDS:
        lfp_ob = df[f"{band}_ob_harmonized_db"]
        lfp_os = df[f"{band}_os_db"]
        lfp_ob_z = (lfp_ob - lfp_ob.mean()) / lfp_ob.std()
        lfp_os_z = (lfp_os - lfp_os.mean()) / lfp_os.std()
        
        # Pearson & Spearman
        r_ob, p_r_ob = pearsonr(spk_ob_z, lfp_ob_z)
        rho_ob, p_rho_ob = spearmanr(df["spk_ob_effect_hz_mean"], lfp_ob)
        r_os, p_r_os = pearsonr(spk_os_z, lfp_os_z)
        rho_os, p_rho_os = spearmanr(df["spk_os_effect_hz_mean"], lfp_os)
        
        # Stacked dataset
        stacked = pd.DataFrame({
            "cell": list(range(n_cells)) * 2,
            "session": list(df["session"]) * 2,
            "subject": list(df["subject"]) * 2,
            "area": list(df["area"]) * 2,
            "contrast": [0] * n_cells + [1] * n_cells, # 0=OB, 1=OS
            "z_spk": np.concatenate([spk_ob_z, spk_os_z]),
            "z_lfp": np.concatenate([lfp_ob_z, lfp_os_z]),
        })
        
        # OLS models:
        # 1) Clustered by cell
        mod_cell = smf.ols("z_lfp ~ z_spk * contrast", data=stacked).fit(
            cov_type="cluster", cov_kwds={"groups": stacked["cell"]}
        )
        # 2) Clustered by session
        mod_ses = smf.ols("z_lfp ~ z_spk * contrast", data=stacked).fit(
            cov_type="cluster", cov_kwds={"groups": stacked["session"]}
        )
        # 3) Clustered by session with subject fixed effect
        mod_ses_subj = smf.ols("z_lfp ~ z_spk * contrast + C(subject)", data=stacked).fit(
            cov_type="cluster", cov_kwds={"groups": stacked["session"]}
        )
        
        beta3 = mod_cell.params["z_spk:contrast"]
        se_cell = mod_cell.bse["z_spk:contrast"]
        p_cell = mod_cell.pvalues["z_spk:contrast"]
        se_ses = mod_ses.bse["z_spk:contrast"]
        p_ses = mod_ses.pvalues["z_spk:contrast"]
        se_ses_subj = mod_ses_subj.bse["z_spk:contrast"]
        p_ses_subj = mod_ses_subj.pvalues["z_spk:contrast"]
        
        # Leave-One-Session-Out (LOSO)
        unique_sessions = df["session"].unique()
        loso_betas = []
        for s in unique_sessions:
            sub_stk = stacked[stacked["session"] != s]
            m_s = smf.ols("z_lfp ~ z_spk * contrast", data=sub_stk).fit()
            b3_s = m_s.params["z_spk:contrast"]
            loso_betas.append(b3_s)
            loso_records.append({
                "band": band, "left_out_session": s, "beta3": b3_s
            })
        loso_betas = np.array(loso_betas)
        same_sign_fraction = float(np.mean(np.sign(loso_betas) == np.sign(beta3)))
        
        # Leave-One-Subject-Out (LOSubj)
        unique_subjects = df["subject"].unique()
        losubj_betas = {}
        for subj in unique_subjects:
            sub_stk = stacked[stacked["subject"] != subj]
            m_subj = smf.ols("z_lfp ~ z_spk * contrast", data=sub_stk).fit()
            b3_subj = m_subj.params["z_spk:contrast"]
            losubj_betas[subj] = b3_subj
            losubj_records.append({
                "band": band, "left_out_subject": subj, "beta3": b3_subj
            })
            
        # Subject-stratified correlations
        for subj in unique_subjects:
            sub_df = df[df["subject"] == subj]
            if len(sub_df) >= 3:
                r_ob_s, p_ob_s = pearsonr(sub_df["spk_ob_effect_hz_mean"], sub_df[f"{band}_ob_harmonized_db"])
                r_os_s, p_os_s = pearsonr(sub_df["spk_os_effect_hz_mean"], sub_df[f"{band}_os_db"])
                rho_ob_s, prho_ob_s = spearmanr(sub_df["spk_ob_effect_hz_mean"], sub_df[f"{band}_ob_harmonized_db"])
                rho_os_s, prho_os_s = spearmanr(sub_df["spk_os_effect_hz_mean"], sub_df[f"{band}_os_db"])
                subj_strat_records.append({
                    "band": band, "subject": subj, "n": len(sub_df),
                    "r_ob": r_ob_s, "p_r_ob": p_ob_s,
                    "rho_ob": rho_ob_s, "p_rho_ob": prho_ob_s,
                    "r_os": r_os_s, "p_r_os": p_os_s,
                    "rho_os": rho_os_s, "p_rho_os": prho_os_s,
                })
        
        # Session-cluster bootstrap (B=2000)
        rng = np.random.default_rng(42)
        n_boot = 2000
        boot_delta_r = []
        boot_delta_rho = []
        boot_beta3 = []
        
        ses_list = list(unique_sessions)
        ses_to_idx = {s: np.where(df["session"] == s)[0] for s in ses_list}
        
        for _ in range(n_boot):
            boot_ses = rng.choice(ses_list, size=len(ses_list), replace=True)
            boot_idx = np.concatenate([ses_to_idx[s] for s in boot_ses])
            b_df = df.iloc[boot_idx]
            
            # Correlations on bootstrap sample
            b_r_ob, _ = pearsonr(b_df["spk_ob_effect_hz_mean"], b_df[f"{band}_ob_harmonized_db"])
            b_r_os, _ = pearsonr(b_df["spk_os_effect_hz_mean"], b_df[f"{band}_os_db"])
            b_rho_ob, _ = spearmanr(b_df["spk_ob_effect_hz_mean"], b_df[f"{band}_ob_harmonized_db"])
            b_rho_os, _ = spearmanr(b_df["spk_os_effect_hz_mean"], b_df[f"{band}_os_db"])
            
            boot_delta_r.append(b_r_os - b_r_ob)
            boot_delta_rho.append(b_rho_os - b_rho_ob)
            
            # Standardize within sample
            b_spk_ob_z = (b_df["spk_ob_effect_hz_mean"] - b_df["spk_ob_effect_hz_mean"].mean()) / b_df["spk_ob_effect_hz_mean"].std()
            b_spk_os_z = (b_df["spk_os_effect_hz_mean"] - b_df["spk_os_effect_hz_mean"].mean()) / b_df["spk_os_effect_hz_mean"].std()
            b_lfp_ob_z = (b_df[f"{band}_ob_harmonized_db"] - b_df[f"{band}_ob_harmonized_db"].mean()) / b_df[f"{band}_ob_harmonized_db"].std()
            b_lfp_os_z = (b_df[f"{band}_os_db"] - b_df[f"{band}_os_db"].mean()) / b_df[f"{band}_os_db"].std()
            
            b_stk = pd.DataFrame({
                "contrast": [0]*len(b_df) + [1]*len(b_df),
                "z_spk": np.concatenate([b_spk_ob_z, b_spk_os_z]),
                "z_lfp": np.concatenate([b_lfp_ob_z, b_lfp_os_z]),
            })
            b_mod = smf.ols("z_lfp ~ z_spk * contrast", data=b_stk).fit()
            boot_beta3.append(b_mod.params["z_spk:contrast"])
            
        boot_delta_r = np.array(boot_delta_r)
        boot_delta_rho = np.array(boot_delta_rho)
        boot_beta3 = np.array(boot_beta3)
        
        ci_delta_r = [float(np.percentile(boot_delta_r, 2.5)), float(np.percentile(boot_delta_r, 97.5))]
        ci_delta_rho = [float(np.percentile(boot_delta_rho, 2.5)), float(np.percentile(boot_delta_rho, 97.5))]
        ci_beta3 = [float(np.percentile(boot_beta3, 2.5)), float(np.percentile(boot_beta3, 97.5))]
        
        # Store primary summary row
        results_primary.append({
            "band": band,
            "r_ob": r_ob, "p_r_ob": p_r_ob,
            "rho_ob": rho_ob, "p_rho_ob": p_rho_ob,
            "r_os": r_os, "p_r_os": p_r_os,
            "rho_os": rho_os, "p_rho_os": p_rho_os,
            "delta_r": r_os - r_ob,
            "ci_delta_r_lower": ci_delta_r[0], "ci_delta_r_upper": ci_delta_r[1],
            "delta_rho": rho_os - rho_ob,
            "ci_delta_rho_lower": ci_delta_rho[0], "ci_delta_rho_upper": ci_delta_rho[1],
            "beta3": beta3,
            "se_cell": se_cell, "p_cell": p_cell,
            "se_ses": se_ses, "p_ses": p_ses,
            "se_ses_subj": se_ses_subj, "p_ses_subj": p_ses_subj,
            "ci_beta3_boot_lower": ci_beta3[0], "ci_beta3_boot_upper": ci_beta3[1],
            "loso_median": float(np.median(loso_betas)),
            "loso_min": float(np.min(loso_betas)),
            "loso_max": float(np.max(loso_betas)),
            "loso_fraction_same_sign": same_sign_fraction,
            "losubj_C31o": losubj_betas.get("C31o", np.nan),
            "losubj_V182o": losubj_betas.get("V182o", np.nan),
            "losubj_V198o": losubj_betas.get("V198o", np.nan),
        })

    res_df = pd.DataFrame(results_primary)
    # Apply FDR correction across 5 bands
    res_df["q_cell"] = fdr_bh(res_df["p_cell"].values)
    res_df["q_ses"] = fdr_bh(res_df["p_ses"].values)
    res_df["q_ses_subj"] = fdr_bh(res_df["p_ses_subj"].values)
    
    # Save CSVs
    res_df.to_csv(OUT_DIR / "f06_robustness_summary.csv", index=False)
    pd.DataFrame(loso_records).to_csv(OUT_DIR / "f06_loso_records.csv", index=False)
    pd.DataFrame(losubj_records).to_csv(OUT_DIR / "f06_losubj_records.csv", index=False)
    pd.DataFrame(subj_strat_records).to_csv(OUT_DIR / "f06_subject_stratified.csv", index=False)
    
    # Write JSON receipt
    receipt = {
        "dataset_summary": {
            "n_matched_cells": n_cells,
            "n_sessions": n_sessions,
            "n_subjects": n_subjects,
            "cells_per_session": cells_per_session,
            "cells_per_subject": cells_per_subject,
            "cells_per_area": cells_per_area,
        },
        "robustness_summary": res_df.to_dict(orient="records"),
    }
    with open(OUT_DIR / "f06_robustness_receipt.json", "w") as f:
        json.dump(receipt, f, indent=2)
        
    print("\n=== Robustness Summary Table ===")
    cols_to_print = ["band", "r_ob", "r_os", "delta_r", "beta3", "p_cell", "q_cell", "p_ses", "q_ses", "p_ses_subj", "q_ses_subj", "loso_fraction_same_sign"]
    print(res_df[cols_to_print].to_string(index=False))

if __name__ == "__main__":
    main()
