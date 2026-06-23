#!/usr/bin/env python3
"""
scripts/run_tfr_parametric_anova.py
===================================
Performs multi-way parametric ANOVA on omission-aligned LFP TFR band power
to examine significance of Area, Layer, Band, and their interaction effects.
"""

import os
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.formula.api import ols
from pathlib import Path
import re

# Constants
TFR_DIR = Path("D:/workspace/data/tfr_arrays")
OUTPUT_DIR = Path("D:/workspace/omission/outputs/omission_aligned_tfr")
LAYER_MASKS_PATH = Path("D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json")
CANONICAL_AREAS = ['V1', 'V2', 'V3d', 'V3a', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

FREQS_HZ = np.arange(3, 201, 2)
N_TIME_BINS = 500
TIMES_MS = -1000.0 + np.arange(N_TIME_BINS) * 10.0

BANDS = {
    "Theta": (3.0, 7.0),
    "Alpha": (8.0, 12.0),
    "Beta-1": (12.0, 20.0),
    "Beta-2": (20.0, 30.0),
    "Gamma-1": (32.0, 50.0),
    "Gamma-2": (50.0, 90.0),
    "Gamma-3": (90.0, 200.0)
}

SLOT_CONDITIONS = {
    2: ["AXAB", "BXBA", "RXRR"],
    3: ["AAXB", "BBXA", "RRXR"],
    4: ["AAAX", "BBBX", "RRRX"]
}

def discover_tfr_files(area: str) -> list[dict]:
    tokens = [area]
    if area == "V4":
        tokens.append("DP")
    files = []
    file_pattern = re.compile(rf"^(.+)-([ABC])-([A-Za-z0-9]+)-([A-Z0-9]+)\.npy$")
    for path in TFR_DIR.glob("*.npy"):
        m = file_pattern.match(path.name)
        if not m:
            continue
        session, probe, file_area, cond = m.groups()
        if file_area not in tokens:
            continue
        slot = None
        for s_idx, conds in SLOT_CONDITIONS.items():
            if cond in conds:
                slot = s_idx
                break
        if slot is None:
            continue
        files.append({
            "path": path, "session": session, "probe": probe,
            "area": file_area, "condition": cond, "slot": slot
        })
    return files

def get_onset_idx_and_slices(slot: int) -> tuple[int, int, int]:
    if slot == 2:
        onset_ms = 1031.0
    elif slot == 3:
        onset_ms = 2062.0
    else:
        onset_ms = 3093.0
    onset_idx = int(round((onset_ms - (-1000.0)) / 10.0))
    start_idx = onset_idx - 156
    end_idx = onset_idx + 104
    return onset_idx, start_idx, end_idx

def load_and_align_trials(file_info: dict, mask: np.ndarray) -> np.ndarray:
    power = np.load(file_info["path"], mmap_mode="r")
    layer_power = np.mean(power[:, mask, :, :], axis=1)
    baseline_mask = (TIMES_MS >= -500.0) & (TIMES_MS <= 0.0)
    baseline = np.mean(layer_power[..., baseline_mask], axis=-1, keepdims=True)
    safe_power = np.maximum(layer_power, 1e-12)
    safe_baseline = np.maximum(baseline, 1e-12)
    layer_power_db = 10.0 * np.log10(safe_power / safe_baseline)
    layer_power_db = np.nan_to_num(layer_power_db, nan=0.0)
    
    onset_idx, start_idx, end_idx = get_onset_idx_and_slices(file_info["slot"])
    aligned = np.full((power.shape[0], len(FREQS_HZ), 260), np.nan, dtype=np.float32)
    src_start = max(0, start_idx)
    src_end = min(N_TIME_BINS, end_idx)
    dest_start = src_start - start_idx
    dest_end = dest_start + (src_end - src_start)
    aligned[:, :, dest_start:dest_end] = layer_power_db[:, :, src_start:src_end]
    return aligned

def run_anova():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(LAYER_MASKS_PATH, "r") as f:
        layer_masks_cache = json.load(f)
    by_key_masks = layer_masks_cache.get("by_key", {})
    
    # We will build a list of all trial-level records
    records = []
    
    relative_time = np.arange(-156, 104) * 10.0
    t_mask_om = (relative_time >= 0.0) & (relative_time <= 500.0)
    
    for area in CANONICAL_AREAS:
        print(f"Loading trials for ANOVA: {area}...")
        files = discover_tfr_files(area)
        if not files:
            continue
            
        for layer_name in ["superficial_putative", "deep_putative"]:
            layer_key = "superficial" if "superficial" in layer_name else "deep"
            
            # Group aligned trials by slot
            slot_trials = {2: [], 3: []}
            
            for file_info in files:
                if file_info["slot"] not in [2, 3]:
                    continue
                mask_key = f"{file_info['session']}|{file_info['probe']}"
                if mask_key not in by_key_masks:
                    continue
                mask_info = by_key_masks[mask_key]
                if mask_info["orientation"] in ["unresolved", "invalid_range", "error"]:
                    continue
                mask = np.array(mask_info["superficial_mask"] if layer_key == "superficial" else mask_info["deep_mask"])
                if not np.any(mask):
                    continue
                try:
                    aligned = load_and_align_trials(file_info, mask)
                    slot_trials[file_info["slot"]].append(aligned)
                except Exception as e:
                    if not isinstance(e, FileNotFoundError):
                        print(f"Error: {e}")
                        
            # Subsample and pool trials
            slot_data = {}
            for slot in [2, 3]:
                if slot_trials[slot]:
                    slot_data[slot] = np.concatenate(slot_trials[slot], axis=0)
                else:
                    slot_data[slot] = np.empty((0, len(FREQS_HZ), 260))
            
            n_trials_per_slot = {s: d.shape[0] for s, d in slot_data.items()}
            if min(n_trials_per_slot.values()) == 0:
                continue
                
            N = min(n_trials_per_slot.values())
            rng = np.random.default_rng(42)
            subsampled_data = {}
            for slot, data in slot_data.items():
                idx = rng.choice(data.shape[0], size=N, replace=False)
                subsampled_data[slot] = data[idx]
                
            pooled_trials = np.concatenate([subsampled_data[s] for s in [2, 3]], axis=0)
            
            # Now compute average omission window power for each trial and band
            for band_name, (fmin, fmax) in BANDS.items():
                freq_mask = (FREQS_HZ >= fmin) & (FREQS_HZ <= fmax)
                # Average across frequencies for each trial, shape: (3*N, times)
                trial_band_power = np.nanmean(pooled_trials[:, freq_mask, :], axis=1)
                # Mean during omission window: (3*N,)
                omission_power = np.nanmean(trial_band_power[:, t_mask_om], axis=1)
                
                # Append to records
                for p_val in omission_power:
                    if np.isfinite(p_val):
                        records.append({
                            "Power": float(p_val),
                            "Area": area,
                            "Layer": layer_key,
                            "Band": band_name
                        })
                        
    df = pd.DataFrame(records)
    print(f"Total trials loaded for ANOVA: {len(df)}")
    
    # Fit OLS model with main effects + 2-way interactions
    print("Fitting ANOVA model...")
    formula = 'Power ~ C(Area) + C(Layer) + C(Band) + C(Area):C(Layer) + C(Area):C(Band) + C(Layer):C(Band)'
    model = ols(formula, data=df).fit()
    anova_table = sm.stats.anova_lm(model, typ=2)
    
    print("\nParametric ANOVA Results:")
    print(anova_table)
    
    # Save ANOVA table
    anova_table.to_csv(OUTPUT_DIR / "tfr_parametric_anova.csv")
    
    # Generate Markdown summary
    md = []
    md.append("# TFR Omission Response Parametric ANOVA")
    md.append(f"\nModel fitted: `Power ~ Area + Layer + Band + Area:Layer + Area:Band + Layer:Band` on $N = {len(df)}$ trial-level data points.")
    md.append("\n### ANOVA Summary Table")
    md.append("| Term | Sum of Squares | Degrees of Freedom | F-statistic | p-value | Significant? |")
    md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    
    for term, row in anova_table.iterrows():
        p_val = row["PR(>F)"]
        sig_str = "**YES**" if p_val < 0.05 else "No"
        p_str = f"{p_val:.2e}" if p_val > 0 else "0.00"
        md.append(f"| {term} | {row['sum_sq']:.2f} | {row['df']:.0f} | {row['F']:.2f} | {p_str} | {sig_str} |")
        
    with open(OUTPUT_DIR / "tfr_parametric_anova.md", "w") as f:
        f.write("\n".join(md))
    print("Exported ANOVA Markdown report.")

if __name__ == "__main__":
    run_anova()
