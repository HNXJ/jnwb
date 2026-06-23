import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.ndimage as ndimage
from pynwb import NWBHDF5IO

NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "../outputs/top_raster_suites"
os.makedirs(OUTPUT_DIR, exist_ok=True)
METADATA_CSV = "../outputs/publication_figures/grand_database_6040_units.csv"

FAMILIES = {
    "A": {
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
        }
    },
    "B": {
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
        }
    },
    "R": {
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

# Load stable units and pick top S+ / S- per area
df = pd.read_csv(METADATA_CSV)
stable = df[(df["is_stable"]) & (df["area"] != "unresolved")].copy()

sp_units = []
for area in stable["area"].unique():
    area_sp = stable[(stable["area"] == area) & (stable["sig_s_plus"] == True)]
    if len(area_sp) > 0:
        sp_units.append(area_sp.sort_values("stim_response_diff", ascending=False).iloc[0])
sp_df = pd.DataFrame(sp_units)
sp_df["target_group"] = "stim_positive"

sn_units = []
for area in stable["area"].unique():
    area_sn = stable[(stable["area"] == area) & (stable["sig_s_minus"] == True)]
    if len(area_sn) > 0:
        sn_units.append(area_sn.sort_values("stim_response_diff", ascending=True).iloc[0])
sn_df = pd.DataFrame(sn_units)
sn_df["target_group"] = "stim_negative"

targets = pd.concat([sp_df, sn_df], ignore_index=True)
targets["session_id"] = targets["session_id"].astype(str)
targets["unit_id"] = targets["unit_id"].astype(int)

print(f"Selected {len(targets)} top neurons across areas.")

# Find the minimum number of trials contained by all selected units/conditions
nwb_map = get_nwb_file_map()
min_trials = 9999

for sess_id, group in targets.groupby("session_id"):
    if sess_id not in nwb_map:
        continue
    with NWBHDF5IO(nwb_map[sess_id], 'r', load_namespaces=True) as io:
        nwb = io.read()
        intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
        
        for fam_name, fam_cfg in FAMILIES.items():
            for cond in fam_cfg["conds"]:
                ons = get_onsets(intervals_df, fam_cfg["codes"][cond])
                if len(ons) > 0:
                    min_trials = min(min_trials, len(ons))

print(f"Global minimum number of trials contained by all: {min_trials}")

# Generate and save plots
time_bins = np.arange(-1000, 4001)

for sess_id, group in targets.groupby("session_id"):
    if sess_id not in nwb_map:
        continue
    nwb_path = nwb_map[sess_id]
    
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
                    # Truncate to min_trials
                    ons_trunc = ons[:min_trials]
                    
                    spike_matrix = np.zeros((len(ons_trunc), len(time_bins)))
                    aligned_spikes = []
                    
                    for trial_idx, t_onset in enumerate(ons_trunc):
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
                    sem_rate = std_rate / np.sqrt(len(ons_trunc))
                    
                    sdfs[cond] = ndimage.gaussian_filter1d(mean_rate, sigma=40.0)
                    sems[cond] = ndimage.gaussian_filter1d(sem_rate, sigma=40.0)
                
                # Matplotlib Plotting
                fig, axes = plt.subplots(5, 1, figsize=(10, 14), sharex=True, 
                                         gridspec_kw={'height_ratios': [1, 1, 1, 1, 3.5]})
                
                for ax_idx, cond in enumerate(conds_to_plot):
                    ax = axes[ax_idx]
                    for start, end, color in SLOT_COLORS:
                        ax.axvspan(start, end, color=color, alpha=0.8, zorder=0)
                    for marker in [0, 1031, 2062, 3093]:
                        ax.axvline(marker, color="#C0C0C0", linestyle="--", linewidth=1.0, zorder=1)
                    
                    if cond in rasters:
                        for trial_idx, trial_spikes in enumerate(rasters[cond]):
                            ax.vlines(trial_spikes, trial_idx - 0.4, trial_idx + 0.4, colors="black", linewidth=0.5)
                        ax.set_ylim(-1, min_trials)
                    
                    ax.set_title(f"{cond} Raster (N={min_trials} trials)", fontsize=11, pad=3)
                    ax.set_ylabel("Trials", fontsize=9)
                    ax.set_xlim(-1000, 4000)
                    ax.spines['top'].set_visible(False)
                    ax.spines['right'].set_visible(False)
                
                ax_psth = axes[4]
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
                
                ax_psth.legend(loc="upper center", bbox_to_anchor=(0.5, 1.05), ncol=4, frameon=False)
                ax_psth.set_xlabel("Time from p1 onset (ms)")
                ax_psth.set_ylabel("FR (Hz)")
                ax_psth.spines['top'].set_visible(False)
                ax_psth.spines['right'].set_visible(False)
                
                plt.suptitle(f"{t_grp.replace('_', ' ').capitalize()} Neuron | Session {sess_id} | Area {area} | Unit {uid} | Family {fam_name}", fontsize=14, fontweight='bold', y=0.98)
                plt.tight_layout()
                
                base_filename = f"{t_grp}_{area.replace(', ', '_')}_ses{sess_id}_unit{uid}_{fam_name}_family"
                
                # 1. Save SVG
                svg_path = os.path.join(OUTPUT_DIR, f"{base_filename}.svg")
                plt.savefig(svg_path, format="svg", dpi=150, facecolor='white')
                
                # 2. Save HTML wrapper
                html_path = os.path.join(OUTPUT_DIR, f"{base_filename}.html")
                html_content = f'''
                <html>
                <head><title>{base_filename}</title></head>
                <body style="background-color:#FFFFFF; text-align:center;">
                    <h2>{base_filename}</h2>
                    <object type="image/svg+xml" data="{base_filename}.svg" style="width:100%; max-width:900px;"></object>
                </body>
                </html>
                '''
                with open(html_path, "w") as h_file:
                    h_file.write(html_content)
                    
                plt.close()
                
print("Done generating SVG and HTML plots.")
