"""
generate_strict_rasters.py
==========================
Generates standardized 12-condition group SVG rasters for:
  1. All genuine (strict) omission neurons (N=36)
  2. All genuine stimulus-positive neurons (N=50, balanced across areas)

Outputs are saved in a new folder: outputs/strict_omission_rasters/
"""

import os
import glob
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.ndimage as ndimage
from pynwb import NWBHDF5IO
from scipy.stats import mannwhitneyu
from src.analysis.io.logger import log

NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/strict_omission_rasters"
METADATA_CSV = "outputs/spsam/grand_unit_metadata.csv"

# Clear and create the new folder
shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

FAMILIES = {
    "A": {
        "ctrl": "AAAB",
        "conds": ["AAAB", "AXAB", "AAXB", "AAAX"],
        "codes": {
            "AAAB": [1, 2],
            "AXAB": [3],
            "AAXB": [4],
            "AAAX": [5],
        },
        "colors": {
            "AAAB": "#1565C0",
            "AXAB": "#4CAF50",
            "AAXB": "#FF9800",
            "AAAX": "#E53935",
        },
        "slots": {
            2: {"cond": "AXAB", "window": (1031, 1531), "codes": [3], "ctrl_codes": [1, 2]},
            3: {"cond": "AAXB", "window": (2062, 2562), "codes": [4], "ctrl_codes": [1, 2]},
            4: {"cond": "AAAX", "window": (3093, 3593), "codes": [5], "ctrl_codes": [1, 2]}
        }
    },
    "B": {
        "ctrl": "BBBA",
        "conds": ["BBBA", "BXBA", "BBXA", "BBBX"],
        "codes": {
            "BBBA": [6, 7],
            "BXBA": [8],
            "BBXA": [9],
            "BBBX": [10],
        },
        "colors": {
            "BBBA": "#00ACC1",
            "BXBA": "#8E24AA",
            "BBXA": "#FFB300",
            "BBBX": "#D81B60",
        },
        "slots": {
            2: {"cond": "BXBA", "window": (1031, 1531), "codes": [8], "ctrl_codes": [6, 7]},
            3: {"cond": "BBXA", "window": (2062, 2562), "codes": [9], "ctrl_codes": [6, 7]},
            4: {"cond": "BBBX", "window": (3093, 3593), "codes": [10], "ctrl_codes": [6, 7]}
        }
    },
    "R": {
        "ctrl": "RRRR",
        "conds": ["RRRR", "RXRR", "RRXR", "RRRX"],
        "codes": {
            "RRRR": list(range(11, 27)),
            "RXRR": list(range(27, 35)),
            "RRXR": [35, 37, 39, 41],
            "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
        },
        "colors": {
            "RRRR": "#E5D429",
            "RXRR": "#0E9F58",
            "RRXR": "#3E9BE5",
            "RRRX": "#D9541F",
        },
        "slots": {
            2: {"cond": "RXRR", "window": (1031, 1531), "codes": [27, 28, 29, 30, 31, 32, 33, 34], "ctrl_codes": list(range(11, 27))},
            3: {"cond": "RRXR", "window": (2062, 2562), "codes": [35, 37, 39, 41], "ctrl_codes": list(range(11, 27))},
            4: {"cond": "RRRX", "window": (3093, 3593), "codes": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50], "ctrl_codes": list(range(11, 27))}
        }
    }
}

SLOT_COLORS = [
    (0, 500, "#FCF9E3"),
    (1031, 1531, "#F6EEF9"),
    (2062, 2562, "#E9F5FC"),
    (3093, 3593, "#FDF2E9"),
]

def get_onsets(intervals_df, allowed_codes):
    correct_val = pd.to_numeric(intervals_df['correct'], errors='coerce')
    stim_num_val = pd.to_numeric(intervals_df['stimulus_number'], errors='coerce')
    cond_num_val = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce')
    matched = (correct_val == 1.0) & (stim_num_val == 2.0) & (cond_num_val.isin(allowed_codes))
    return intervals_df.loc[matched, 'start_time'].values

def get_nwb_file_map():
    m = {}
    for f in glob.glob(f"{NWB_DIR}/*.nwb"):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m

def main():
    if not os.path.exists(METADATA_CSV):
        print("Metadata file not found. Please run the SpSAM pipeline first.")
        return
        
    df = pd.read_csv(METADATA_CSV)
    stable = df[df["is_stable"]].copy()
    
    nwb_map = get_nwb_file_map()
    time_bins = np.arange(-1000, 4001)
    
    log.action("Auditing units for strict omission selectivity...")
    strict_omission_records = []
    
    for sess_id, group in stable.groupby("session_id"):
        sess_id_str = str(sess_id)
        if sess_id_str not in nwb_map:
            continue
        nwb_path = nwb_map[sess_id_str]
        
        with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
            nwb = io.read()
            intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
            units_df = nwb.units.to_dataframe()
            
            for _, u_row in group.iterrows():
                uid = int(u_row["unit_id"])
                row = units_df.loc[uid]
                spike_times = row['spike_times']
                
                unit_results = []
                for fam_name, fam_cfg in FAMILIES.items():
                    for slot, slot_cfg in fam_cfg["slots"].items():
                        om_ons = get_onsets(intervals_df, slot_cfg["codes"])
                        ctrl_ons = get_onsets(intervals_df, slot_cfg["ctrl_codes"])
                        
                        if len(om_ons) < 5 or len(ctrl_ons) < 5:
                            continue
                            
                        w_start, w_end = slot_cfg["window"]
                        om_rates = []
                        for ons in om_ons:
                            t0 = ons + w_start / 1000.0
                            t1 = ons + w_end / 1000.0
                            spk = len(spike_times[(spike_times >= t0) & (spike_times <= t1)])
                            om_rates.append(spk / ((w_end - w_start) / 1000.0))
                            
                        ctrl_rates = []
                        for ons in ctrl_ons:
                            t0 = ons + w_start / 1000.0
                            t1 = ons + w_end / 1000.0
                            spk = len(spike_times[(spike_times >= t0) & (spike_times <= t1)])
                            ctrl_rates.append(spk / ((w_end - w_start) / 1000.0))
                            
                        om_mean = np.mean(om_rates)
                        ctrl_mean = np.mean(ctrl_rates)
                        diff = om_mean - ctrl_mean
                        
                        try:
                            stat, p_val = mannwhitneyu(om_rates, ctrl_rates, alternative='greater')
                        except Exception:
                            p_val = 1.0
                            
                        unit_results.append({
                            "family": fam_name,
                            "slot": slot,
                            "diff": diff,
                            "p_val": p_val
                        })
                
                if unit_results:
                    best_res = max(unit_results, key=lambda x: x["diff"])
                    if best_res["diff"] >= 4.0 and best_res["p_val"] < 0.01:
                        strict_omission_records.append({
                            "session_id": int(sess_id_str),
                            "unit_id": uid
                        })
                        
    strict_omission_df = pd.DataFrame(strict_omission_records)
    log.action(f"Strict omission selectivity audit completed: found {len(strict_omission_df)} units passing strict criteria.")
    
    # 1. Select strictly audited omission units
    if len(strict_omission_df) > 0:
        om_units = stable.merge(strict_omission_df, on=["session_id", "unit_id"])
    else:
        om_units = pd.DataFrame(columns=stable.columns)
    om_units["target_group"] = "omission"
    
    # 2. Select top 50 stable stimulus positive units (balanced across areas)
    sp_df = stable[stable["group"] == "stimulus_positive"].copy()
    areas_sp = sorted(list(sp_df["area"].unique()))
    sp_by_area = {area: sp_df[sp_df["area"] == area].sort_values("snr", ascending=False).to_dict("records") for area in areas_sp}
    
    sp_list = []
    while len(sp_list) < 50 and any(len(lst) > 0 for lst in sp_by_area.values()):
        for area in areas_sp:
            if len(sp_list) >= 50:
                break
            if sp_by_area[area]:
                sp_list.append(sp_by_area[area].pop(0))
    sp_units = pd.DataFrame(sp_list) if sp_list else pd.DataFrame(columns=stable.columns)
    sp_units["target_group"] = "stim_positive"
    
    # Combine selected units
    targets = pd.concat([om_units, sp_units], ignore_index=True)
    targets["session_id"] = targets["session_id"].astype(str)
    targets["unit_id"] = targets["unit_id"].astype(int)
    
    log.action(f"Total units selected for plotting: {len(targets)}")
    log.action(f"Strict omission neurons: {len(om_units)}")
    log.action(f"S+ neurons: {len(sp_units)}")
    
    # Group targets by session for NWB access efficiency
    sessions = targets.groupby("session_id")
    
    for sess_id, group in sessions:
        if sess_id not in nwb_map:
            print(f"NWB file for session {sess_id} not found.")
            continue
            
        nwb_path = nwb_map[sess_id]
        log.action(f"Opening NWB session {sess_id} at {nwb_path}")
        
        with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
            nwb = io.read()
            intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
            units_df = nwb.units.to_dataframe()
            
            for _, unit_row in group.iterrows():
                uid = int(unit_row["unit_id"])
                area = unit_row["area"]
                t_grp = unit_row["target_group"]
                
                row = units_df.loc[uid]
                spike_times = row['spike_times']
                wf_mean = row.get("waveform_mean", None)
                
                # Generate A, B, and R families
                for fam_name, fam_cfg in FAMILIES.items():
                    conds_to_plot = fam_cfg["conds"]
                    codes_cfg = fam_cfg["codes"]
                    colors_cfg = fam_cfg["colors"]
                    
                    onsets = {cond: get_onsets(intervals_df, codes_cfg[cond]) for cond in conds_to_plot}
                    
                    sdfs = {}
                    sems = {}
                    rasters = {}
                    
                    for cond, ons in onsets.items():
                        if len(ons) == 0:
                            continue
                        
                        # Limit to exactly 40 trials
                        ons_sliced = ons[:40]
                        spike_matrix = np.zeros((len(ons_sliced), len(time_bins)))
                        aligned_spikes = []
                        
                        for trial_idx, t_onset in enumerate(ons_sliced):
                            t_start = t_onset - 1.0
                            t_end = t_onset + 4.0
                            trial_spk = spike_times[(spike_times >= t_start) & (spike_times <= t_end)]
                            aligned_ms = (trial_spk - t_onset) * 1000.0
                            aligned_spikes.append(aligned_ms)
                            
                            hist, _ = np.histogram(aligned_ms, bins=np.arange(-1000.5, 4001.5))
                            spike_matrix[trial_idx, :] = hist
                            
                        rasters[cond] = aligned_spikes
                        
                        mean_rate = np.mean(spike_matrix, axis=0) * 1000.0
                        std_rate = np.std(spike_matrix, axis=0) * 1000.0
                        sem_rate = std_rate / np.sqrt(len(ons_sliced))
                        
                        sdfs[cond] = ndimage.gaussian_filter1d(mean_rate, sigma=40.0)
                        sems[cond] = ndimage.gaussian_filter1d(sem_rate, sigma=40.0)
                        
                    # Create 2-column Matplotlib layout
                    fig = plt.figure(figsize=(13, 14), facecolor="white")
                    gs = fig.add_gridspec(5, 2, width_ratios=[3, 1], height_ratios=[1, 1, 1, 1, 3.5])
                    
                    axes_raster = [fig.add_subplot(gs[i, 0]) for i in range(4)]
                    ax_psth = fig.add_subplot(gs[4, 0])
                    ax_text = fig.add_subplot(gs[0:4, 1])
                    ax_text.axis('off')
                    ax_wf = fig.add_subplot(gs[4, 1])
                    
                    # 1. Plot Rasters
                    for ax_idx, cond in enumerate(conds_to_plot):
                        ax = axes_raster[ax_idx]
                        for start, end, color in SLOT_COLORS:
                            ax.axvspan(start, end, color=color, alpha=0.8, zorder=0)
                        for marker in [0, 1031, 2062, 3093]:
                            ax.axvline(marker, color="#C0C0C0", linestyle="--", linewidth=1.0, zorder=1)
                        
                        if cond in rasters:
                            for trial_idx, trial_spikes in enumerate(rasters[cond]):
                                ax.vlines(trial_spikes, trial_idx - 0.4, trial_idx + 0.4, colors="black", linewidth=0.5)
                        
                        ax.set_ylim(-1, 40)
                        ax.set_title(f"{cond} Raster (N={len(rasters.get(cond, []))} trials)", fontsize=11, pad=3)
                        ax.set_ylabel("Trials", fontsize=9)
                        ax.set_xlim(-1000, 4000)
                        ax.spines['top'].set_visible(False)
                        ax.spines['right'].set_visible(False)
                        ax.tick_params(labelbottom=False)
                        
                    # 2. Plot PSTH
                    for start, end, color in SLOT_COLORS:
                        ax_psth.axvspan(start, end, color=color, alpha=0.8, zorder=0)
                    for marker in [0, 1031, 2062, 3093]:
                        ax_psth.axvline(marker, color="#C0C0C0", linestyle="--", linewidth=1.0, zorder=1)
                        
                    for cond in conds_to_plot:
                        if cond in sdfs:
                            ax_psth.plot(time_bins, sdfs[cond], color=colors_cfg[cond], label=cond, linewidth=1.5, zorder=3)
                            if cond in sems:
                                ax_psth.fill_between(time_bins, sdfs[cond] - sems[cond], sdfs[cond] + sems[cond], 
                                                     color=colors_cfg[cond], alpha=0.15, zorder=2)
                                
                    ax_psth.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), ncol=4, frameon=False, fontsize=10)
                    ax_psth.set_xlabel("Time from p1 onset (ms)", fontsize=10)
                    ax_psth.set_ylabel("FR (Hz)", fontsize=10)
                    ax_psth.set_xlim(-1000, 4000)
                    ax_psth.spines['top'].set_visible(False)
                    ax_psth.spines['right'].set_visible(False)
                    
                    # 3. Waveform Plot
                    if wf_mean is not None:
                        wf_color = "#9400D3" if t_grp == "omission" else "#CFB87C"
                        ax_wf.plot(wf_mean, color=wf_color, linewidth=2.0)
                        ax_wf.set_title("Mean Waveform", fontsize=10, fontweight="bold", pad=5)
                        ax_wf.set_xlabel("Samples", fontsize=8)
                        ax_wf.set_ylabel("Amplitude (µV)", fontsize=8)
                        ax_wf.spines['top'].set_visible(False)
                        ax_wf.spines['right'].set_visible(False)
                    else:
                        ax_wf.text(0.5, 0.5, "No Waveform\nData", ha="center", va="center", fontsize=10)
                        ax_wf.axis('off')
                        
                    # 4. Metadata details text box
                    layer_val = unit_row.get("layer", "unresolved")
                    snr_val = unit_row.get("snr", 0.0)
                    fr_val = unit_row.get("firing_rate", 0.0)
                    wf_cls = unit_row.get("waveform_class", "unknown")
                    wf_dur = unit_row.get("waveform_duration", 0.0)
                    
                    info_text = (
                        f"**Unit metadata:**\n"
                        f"• NWB Unit ID: {uid}\n"
                        f"• Session: {sess_id}\n"
                        f"• Area: {area}\n"
                        f"• Layer: {layer_val}\n"
                        f"• Type: {t_grp.replace('_', ' ').capitalize()}\n"
                        f"• SNR: {snr_val:.2f}\n"
                        f"• Mean FR: {fr_val:.2f} Hz\n"
                        f"• Waveform: {wf_cls}\n"
                        f"• Duration: {wf_dur:.1f} ms"
                    )
                    info_text_clean = info_text.replace("**", "").replace("• ", "  ")
                    ax_text.text(0.05, 0.9, info_text_clean, fontsize=9.5, verticalalignment='top',
                                 bbox=dict(boxstyle="round,pad=0.6", facecolor="#FDFDFD", edgecolor="#E0E0E0", alpha=0.95))
                    
                    # Figure title and layout adjustments
                    grp_title = t_grp.replace('_', ' ').capitalize()
                    plt.suptitle(f"{grp_title} Neuron | Session {sess_id} | Area {area} | Unit {uid} | {fam_name}-Family", 
                                 fontsize=13, fontweight='bold', y=0.98)
                    
                    plt.tight_layout()
                    
                    # Naming format: stim_positive_PFC_ses230830_unit134_A_family.svg
                    save_name = f"{t_grp}_{area.replace(', ', '_')}_ses{sess_id}_unit{uid}_{fam_name}_family.svg"
                    plt.savefig(f"{OUTPUT_DIR}/{save_name}", format="svg", facecolor='white')
                    plt.close()
                    
    print("\nDone generating strict rasters in outputs/strict_omission_rasters/.")

if __name__ == "__main__":
    main()
