#!/usr/bin/env python3
"""
Compute omission firing likelihood, P1-D1 comparisons, and O++ conjunction classification across all single units and MUA in the Omission corpus.

Target Window:
  -250 ms to +750 ms relative to omission onset (1000 ms duration window):
  - Position 2 omission (p2-d2): [781, 1781] ms in AXAB, BXBA, RXRR
  - Position 3 omission (p3-d3): [1812, 2812] ms in AAXB, BBXA, RRXR
  - Position 4 omission (p4-d4): [2843, 3843] ms in RRRX, BBBX, AAAX

Matching Control Window:
  Same [-250, +750] ms slot windows in intact control sequences (AAAB, BBBA, RRRR).

P1-D1 Initial Stimulus Presentation Window:
  [0, 1031] ms relative to sequence P1 onset (P1 presentation + D1 delay).

Pre-stimulus Baseline Window:
  [-500, 0] ms relative to sequence P1 onset.

O++ Conjunction Criteria:
  1. Omission Rate > Matching Control Rate (p_val < 0.05)
  2. Omission Rate > P1-D1 Stimulus Presentation Rate (p_val_p1d1 < 0.05 & diff_vs_p1d1 > 0)

Output Files:
  1. outputs/classification/omission_likelihood_grand_units.csv (Full 8,597 units table)
  2. outputs/classification/omission_oplusplus_grand_units.csv (Filtered O++ candidate table)
"""

from __future__ import annotations

import os
import sys
import time
import pathlib
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.unit_classification import precompute_condition_onsets, _rate_in_window
from jnwb import paths as _P

NWB_DIR = pathlib.Path(os.environ.get("OMISSION_NWB_DIR", _P.nwb_dir()))
OUTPUT_CSV = REPO_ROOT / "outputs" / "classification" / "omission_likelihood_grand_units.csv"
OUTPUT_OPLUSPLUS_CSV = REPO_ROOT / "outputs" / "classification" / "omission_oplusplus_grand_units.csv"
OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)

GRAND_UNITS_PATH = REPO_ROOT / "outputs" / "classification" / "omission_grand_units.csv"
GRAND_UNITS_DF = pd.read_csv(GRAND_UNITS_PATH) if GRAND_UNITS_PATH.exists() else None

# Helper map for omission_class lookup
CLASS_MAP = {}
if GRAND_UNITS_DF is not None:
    for _, r in GRAND_UNITS_DF.iterrows():
        stem = str(r['session']).replace('_rec', '')
        u_row = int(r['unit_row'])
        CLASS_MAP[(stem, u_row)] = r.get('omission_class', 'ns')

def tag_waveform(duration_ms: float) -> str:
    if np.isnan(duration_ms) or duration_ms <= 0:
        return "unknown"
    if duration_ms <= 0.35:
        return "fast"
    elif duration_ms <= 0.50:
        return "moderate"
    else:
        return "slow"

def tag_quality(quality_val: float, presence_ratio: float) -> str:
    is_single = (quality_val == 1.0)
    pr = presence_ratio if not np.isnan(presence_ratio) else 0.95
    is_stable = (pr >= 0.90)
    
    if is_single and is_stable:
        return "single-stable"
    elif is_single and not is_stable:
        return "single-unstable"
    elif not is_single and is_stable:
        return "mua-stable"
    else:
        return "mua-unstable"

def main():
    start_time_all = time.time()
    nwb_files = sorted(list(NWB_DIR.glob("*.nwb")))
    print(f"Found {len(nwb_files)} NWB files in {NWB_DIR}.")
    
    all_results = []
    
    for f_idx, nwb_path in enumerate(nwb_files, start=1):
        stem = nwb_path.stem.replace("_rec", "")
        t0 = time.time()
        print(f"[{f_idx}/{len(nwb_files)}] Processing {stem}...")
        
        try:
            session = oa.read(nwb_path)
            onsets = precompute_condition_onsets(session)
        except Exception as e:
            print(f"  ERROR reading session {stem}: {e}")
            continue
        
        # Omission trial onsets by position
        p2_omit_onsets = np.concatenate([onsets.get(c, []) for c in ("AXAB", "BXBA", "RXRR")])
        p3_omit_onsets = np.concatenate([onsets.get(c, []) for c in ("AAXB", "BBXA", "RRXR")])
        p4_omit_onsets = np.concatenate([onsets.get(c, []) for c in ("RRRX", "BBBX", "AAAX")])
        all_omit_onsets = np.concatenate([p2_omit_onsets, p3_omit_onsets, p4_omit_onsets])
        
        # Control intact onsets
        control_onsets = np.concatenate([onsets.get(c, []) for c in ("AAAB", "BBBA", "RRRR")])
        
        units_df = session.get_units()
        n_units = len(units_df)
        
        for unit_row in range(n_units):
            spikes = session.get_spike_times(unit_row)
            if spikes is None or len(spikes) == 0:
                continue
            spikes = np.sort(spikes)
            
            # Baseline rates (-500 to 0 ms relative to P1 onset)
            base_rates = [_rate_in_window(spikes, t, (-500.0, 0.0)) for t in control_onsets]
            mean_baseline = float(np.mean(base_rates)) if len(base_rates) > 0 else 0.0
            
            # P1-D1 Initial Stimulus Presentation rates (0 to 1031 ms)
            p1_d1_rates = [_rate_in_window(spikes, t, (0.0, 1031.0)) for t in all_omit_onsets]
            mean_p1_d1 = float(np.mean(p1_d1_rates)) if len(p1_d1_rates) > 0 else 0.0
            
            # Position-specific omission rates (-250 to +750 ms relative to slot onset)
            p2_omit_rates = [_rate_in_window(spikes, t, (781.0, 1781.0)) for t in p2_omit_onsets]
            p3_omit_rates = [_rate_in_window(spikes, t, (1812.0, 2812.0)) for t in p3_omit_onsets]
            p4_omit_rates = [_rate_in_window(spikes, t, (2843.0, 3843.0)) for t in p4_omit_onsets]
            
            p2_mean = float(np.mean(p2_omit_rates)) if len(p2_omit_rates) > 0 else 0.0
            p3_mean = float(np.mean(p3_omit_rates)) if len(p3_omit_rates) > 0 else 0.0
            p4_mean = float(np.mean(p4_omit_rates)) if len(p4_omit_rates) > 0 else 0.0
            
            all_omit_rates = p2_omit_rates + p3_omit_rates + p4_omit_rates
            mean_omit = float(np.mean(all_omit_rates)) if len(all_omit_rates) > 0 else 0.0
            
            # Control rates matching windows
            ctrl_p2_rates = [_rate_in_window(spikes, t, (781.0, 1781.0)) for t in control_onsets]
            ctrl_p3_rates = [_rate_in_window(spikes, t, (1812.0, 2812.0)) for t in control_onsets]
            ctrl_p4_rates = [_rate_in_window(spikes, t, (2843.0, 3843.0)) for t in control_onsets]
            all_ctrl_rates = ctrl_p2_rates + ctrl_p3_rates + ctrl_p4_rates
            mean_ctrl = float(np.mean(all_ctrl_rates)) if len(all_ctrl_rates) > 0 else 0.0
            
            diff_hz = mean_omit - mean_ctrl
            ratio = (mean_omit + 0.1) / (mean_ctrl + 0.1)
            
            diff_p1_d1_hz = mean_omit - mean_p1_d1
            ratio_p1_d1 = (mean_omit + 0.1) / (mean_p1_d1 + 0.1)
            
            # Standardized z-score
            std_pooled = float(np.std(all_ctrl_rates)) if len(all_ctrl_rates) > 1 else 1.0
            if std_pooled == 0:
                std_pooled = 1.0
            z_score = diff_hz / std_pooled
            
            # Mann-Whitney U test vs matching control
            if len(all_omit_rates) > 0 and len(all_ctrl_rates) > 0:
                try:
                    stat, pval = mannwhitneyu(all_omit_rates, all_ctrl_rates, alternative="greater")
                except Exception:
                    pval = 1.0
            else:
                pval = 1.0
                
            # Mann-Whitney U test vs P1-D1 initial presentation
            if len(all_omit_rates) > 0 and len(p1_d1_rates) > 0:
                try:
                    stat_p1d1, pval_p1d1 = mannwhitneyu(all_omit_rates, p1_d1_rates, alternative="greater")
                except Exception:
                    pval_p1d1 = 1.0
            else:
                pval_p1d1 = 1.0
                
            # O++ Conjunction Flag
            is_oplusplus = bool(
                (diff_hz > 0) and (diff_p1_d1_hz > 0) and 
                (pval < 0.05) and (pval_p1d1 < 0.05)
            )
            
            unit_info = units_df.iloc[unit_row]
            u_id = float(unit_info.get("unit_id", unit_row))
            area = str(unit_info.get("area", "unknown"))
            probe_id = str(unit_info.get("probe_id", "A"))
            peak_ch = float(unit_info.get("peak_channel_id", -1))
            local_ch = float(unit_info.get("local_channel", -1))
            quality_val = float(unit_info.get("quality", 0.0))
            wf_dur = float(unit_info.get("waveform_duration", np.nan))
            snr_val = float(unit_info.get("snr", np.nan))
            presence_ratio_val = float(unit_info.get("presence_ratio", np.nan))
            
            wf_type = tag_waveform(wf_dur)
            q_tag = tag_quality(quality_val, presence_ratio_val)
            om_cls = CLASS_MAP.get((stem, unit_row), "ns")
            if is_oplusplus:
                om_cls = "O++"
            
            # Raw likelihood index combining magnitude and statistical confidence
            raw_score = diff_hz * (-np.log10(max(pval, 1e-300)))
            oplusplus_score = diff_p1_d1_hz * (-np.log10(max(pval_p1d1, 1e-300))) if is_oplusplus else 0.0
            
            all_results.append({
                "session": stem,
                "unit_row": unit_row,
                "unit_id": u_id,
                "probe_id": probe_id,
                "area": area,
                "peak_channel_id": peak_ch,
                "local_channel": local_ch,
                "quality": quality_val,
                "quality_tag": q_tag,
                "waveform_duration_ms": wf_dur,
                "waveform_type": wf_type,
                "snr": snr_val,
                "presence_ratio": presence_ratio_val,
                "baseline_rate_hz": mean_baseline,
                "p1_d1_rate_hz": mean_p1_d1,
                "control_rate_hz": mean_ctrl,
                "p2_omission_rate_hz": p2_mean,
                "p3_omission_rate_hz": p3_mean,
                "p4_omission_rate_hz": p4_mean,
                "omission_rate_hz": mean_omit,
                "omission_diff_hz": diff_hz,
                "omission_ratio": ratio,
                "omission_vs_p1_d1_diff_hz": diff_p1_d1_hz,
                "omission_vs_p1_d1_ratio": ratio_p1_d1,
                "omission_vs_p1_d1_pval": pval_p1d1,
                "is_oplusplus_conjunction": is_oplusplus,
                "omission_zscore": z_score,
                "p_value": pval,
                "raw_likelihood_score": raw_score,
                "oplusplus_score": oplusplus_score,
                "omission_class": om_cls,
            })
            
        print(f"  -> Finished {stem} ({n_units} units) in {time.time() - t0:.2f} s")
        
    df_out = pd.DataFrame(all_results)
    
    # Sort by raw_likelihood_score descending
    df_out = df_out.sort_values("raw_likelihood_score", ascending=False).reset_index(drop=True)
    
    # Compute percentile rank (100% = top omission-excited unit)
    n_total = len(df_out)
    if n_total > 0:
        df_out["likelihood_pct"] = np.round(100.0 * (n_total - df_out.index) / n_total, 2)
    else:
        df_out["likelihood_pct"] = []
        
    cols_order = [
        "likelihood_pct",
        "session",
        "unit_row",
        "unit_id",
        "probe_id",
        "area",
        "peak_channel_id",
        "local_channel",
        "quality",
        "quality_tag",
        "waveform_duration_ms",
        "waveform_type",
        "snr",
        "presence_ratio",
        "baseline_rate_hz",
        "p1_d1_rate_hz",
        "control_rate_hz",
        "omission_rate_hz",
        "omission_diff_hz",
        "omission_ratio",
        "omission_vs_p1_d1_diff_hz",
        "omission_vs_p1_d1_ratio",
        "omission_vs_p1_d1_pval",
        "is_oplusplus_conjunction",
        "omission_zscore",
        "p_value",
        "p2_omission_rate_hz",
        "p3_omission_rate_hz",
        "p4_omission_rate_hz",
        "omission_class",
        "raw_likelihood_score",
        "oplusplus_score",
    ]
    df_out = df_out[cols_order]
    df_out.to_csv(OUTPUT_CSV, index=False)
    
    # Export filtered O++ grand units table (sorted by O++ score)
    df_oplusplus = df_out[df_out["is_oplusplus_conjunction"] == True].sort_values("oplusplus_score", ascending=False).reset_index(drop=True)
    n_oplusplus = len(df_oplusplus)
    if n_oplusplus > 0:
        df_oplusplus["oplusplus_rank"] = np.arange(1, n_oplusplus + 1)
    df_oplusplus.to_csv(OUTPUT_OPLUSPLUS_CSV, index=False)
    
    print(f"\n=======================================================")
    print(f"Successfully processed {n_total} units across {len(nwb_files)} sessions.")
    print(f"Full grand units table: {OUTPUT_CSV}")
    print(f"Filtered O++ conjunction units table ({n_oplusplus} units): {OUTPUT_OPLUSPLUS_CSV}")
    print(f"Total elapsed time: {time.time() - start_time_all:.2f} s")
    print(f"=======================================================\n")
    
    print("TOP 15 O++ CONJUNCTION NEURONS (Omission > Control AND Omission > P1-D1):")
    print(df_oplusplus.head(15)[["oplusplus_rank", "likelihood_pct", "session", "unit_row", "area", "quality_tag", "waveform_type", "omission_rate_hz", "p1_d1_rate_hz", "omission_vs_p1_d1_diff_hz", "omission_vs_p1_d1_pval", "omission_class"]].to_string())

if __name__ == "__main__":
    main()
