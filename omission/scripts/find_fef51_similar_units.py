#!/usr/bin/env python3
"""
Find units across the corpus with highest correlation to the smoothed PSTH profile of FEF Unit 51
(sub-C31o_ses-230823_rec, unit_row 51).

Reference Unit:
  Session: sub-C31o_ses-230823
  Unit Row: 51 (ID: 52.0)
  Area: FEF

Method:
  1. Compute smoothed 4-condition concatenated PSTH profile for FEF Unit 51 (-500 to 4124 ms, 20ms bins, Gaussian sigma=40ms).
  2. For each unit in the corpus, compute its smoothed 4-condition PSTH profile.
  3. Calculate Pearson correlation r between each unit's profile and FEF Unit 51's profile.
  4. Rank units by Pearson r and export top candidates to CSV.
  5. Generate 4x4 raster suite PNG figures for top matches.
"""

from __future__ import annotations

import os
import sys
import pathlib
import time
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.ndimage import gaussian_filter1d
from scipy.stats import pearsonr

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

import omission as oa
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS
from omission.jnwb_ext.unit_classification import precompute_condition_onsets
from figstyle import FULL_TRIAL_WIN, full_trial_ticks, mark_full_trial_axis
from jnwb import paths as _P

OUTPUT_CSV = REPO_ROOT / "outputs" / "classification" / "omission_fef51_similar_units.csv"
OUTPUT_PNG_DIR = REPO_ROOT / "outputs" / "raster_suites" / "fef51_similar"
OUTPUT_PNG_DIR.mkdir(parents=True, exist_ok=True)

CONDS = ["RRRR", "RXRR", "RRXR", "RRRX"]
OMIT_SLOT = {"RRRR": None, "RXRR": 2, "RRXR": 3, "RRRX": 4}
COND_COLORS = {"RRRR": "#000000", "RXRR": "#DC2626", "RRXR": "#16A34A", "RRRX": "#2563EB"}
PSTH_BIN_MS = 20.0
GAUSS_SIGMA_BINS = 2.0  # 40ms smoothing
WIN = FULL_TRIAL_WIN

def compute_concatenated_psth(session, unit_row, onsets_dict):
    spikes = session.get_spike_times(unit_row)
    if spikes is None or len(spikes) == 0:
        edges = np.arange(WIN[0], WIN[1] + PSTH_BIN_MS, PSTH_BIN_MS)
        return np.zeros((len(edges) - 1) * len(CONDS))
        
    spikes = np.sort(spikes)
    edges = np.arange(WIN[0], WIN[1] + PSTH_BIN_MS, PSTH_BIN_MS)
    
    psth_list = []
    for cond in CONDS:
        onsets = onsets_dict.get(cond, np.array([]))
        if onsets.size == 0:
            psth_list.append(np.zeros(len(edges) - 1))
            continue
            
        t_starts = onsets + WIN[0] / 1000.0
        t_ends = onsets + WIN[1] / 1000.0
        
        idx_start = np.searchsorted(spikes, t_starts)
        idx_end = np.searchsorted(spikes, t_ends)
        
        rel_spikes_list = []
        for i in range(onsets.size):
            if idx_end[i] > idx_start[i]:
                rel_spikes_list.append((spikes[idx_start[i]:idx_end[i]] - onsets[i]) * 1000.0)
                
        if len(rel_spikes_list) > 0:
            all_rel = np.concatenate(rel_spikes_list)
            counts, _ = np.histogram(all_rel, bins=edges)
            rate = counts / (onsets.size * (PSTH_BIN_MS / 1000.0))
        else:
            rate = np.zeros(len(edges) - 1)
            
        smoothed = gaussian_filter1d(rate, sigma=GAUSS_SIGMA_BINS)
        psth_list.append(smoothed)
        
    return np.concatenate(psth_list)

def main():
    t0 = time.time()
    nwb_dir = pathlib.Path(_P.nwb_dir())
    nwb_files = sorted(list(nwb_dir.glob("*.nwb")))
    
    # 1. Compute reference profile for FEF Unit 51 (sub-C31o_ses-230823)
    ref_stem = "sub-C31o_ses-230823"
    ref_nwb_path = nwb_dir / f"{ref_stem}_rec.nwb"
    if not ref_nwb_path.exists():
        ref_nwb_path = nwb_dir / f"{ref_stem}.nwb"
        
    print(f"Loading reference session: {ref_nwb_path.name}...")
    ref_session = oa.read(ref_nwb_path)
    ref_onsets = precompute_condition_onsets(ref_session)
    ref_profile = compute_concatenated_psth(ref_session, 51, ref_onsets)
    print(f"Reference FEF Unit 51 profile computed (length: {len(ref_profile)}).")
    
    # 2. Iterate across all sessions and units
    results = []
    
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        session = oa.read(nwb_path)
        onsets_dict = precompute_condition_onsets(session)
        units_df = session.get_units()
        n_units = len(units_df)
        
        print(f"[{f_idx}/{len(nwb_files)}] Scanning {stem} ({n_units} units)...")
        
        for u_idx in range(n_units):
            # Skip reference unit itself from being ranked #1 duplicate
            is_ref = (stem == ref_stem and u_idx == 51)
            
            u_profile = compute_concatenated_psth(session, u_idx, onsets_dict)
            
            # Compute Pearson correlation with reference
            if np.std(u_profile) == 0 or np.std(ref_profile) == 0:
                r_val, p_val = 0.0, 1.0
            else:
                r_val, p_val = pearsonr(u_profile, ref_profile)
                
            unit_id = units_df.iloc[u_idx].get("unit_id", u_idx)
            area = units_df.iloc[u_idx].get("area", "unknown")
            quality = units_df.iloc[u_idx].get("quality", "unknown")
            snr = units_df.iloc[u_idx].get("snr", np.nan)
            
            results.append({
                "session": stem,
                "unit_row": u_idx,
                "unit_id": unit_id,
                "area": area,
                "quality": quality,
                "snr": snr,
                "fef51_corr_r": float(r_val),
                "fef51_corr_pval": float(p_val),
                "is_reference_unit": is_ref,
                "mean_rate_hz": float(u_profile.mean())
            })
            
    df_res = pd.DataFrame(results)
    # Sort by correlation r descending
    df_res = df_res.sort_values(by="fef51_corr_r", ascending=False).reset_index(drop=True)
    
    # Save full CSV
    df_res.to_csv(OUTPUT_CSV, index=False)
    print(f"\nSaved correlation results to {OUTPUT_CSV}.")
    print(f"Total time elapsed: {time.time() - t0:.2f} s")
    
    print("\nTOP 15 UNITS MOST CORRELATED TO FEF UNIT 51:")
    print(df_res.head(15)[["session", "unit_row", "area", "quality", "fef51_corr_r", "fef51_corr_pval", "mean_rate_hz"]])
    
    # 3. Render 4x4 raster suite PNGs for top matches
    from generate_oplusplus_raster_suites import render_unit_raster_suite
    top_matches = df_res[df_res["is_reference_unit"] == False].head(10).reset_index(drop=True)
    for idx, row in top_matches.iterrows():
        rank = idx + 1
        stem = str(row["session"]).replace("_rec", "")
        u_row = int(row["unit_row"])
        area = str(row["area"])
        r_val = float(row["fef51_corr_r"])
        
        filename = f"fef51_similar_rank{rank:02d}_{stem}_row{u_row}_{area}_r{r_val:.3f}.png"
        out_path = OUTPUT_PNG_DIR / filename
        render_unit_raster_suite(rank, row, out_path)
        
    print(f"\nGenerated top FEF Unit 51 similar PNG raster suites in {OUTPUT_PNG_DIR}.")

if __name__ == "__main__":
    main()
