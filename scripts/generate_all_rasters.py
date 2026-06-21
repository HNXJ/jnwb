#!/usr/bin/env python
"""
generate_all_rasters.py
=======================
Creates standardized SVG raster figures for:
  * All stable omission neurons
  * Top 50 stimulus‑positive neurons (balanced across areas)
  * Top 50 stimulus‑negative neurons (balanced across areas)
Each figure follows the Madelane Golden Dark aesthetic, includes three family
traces (A, B, R), exactly 40 trials per condition, and embeds unit metadata
and waveform information.

Outputs are saved under `outputs/omission_rasters/` with the naming pattern:
`{group}_{area}_ses{session}_unit{unit}_{family}_family.svg`
where `group` is one of `omission`, `stim_positive`, `stim_negative`.
"""

import os
import glob
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.ndimage as ndimage
from pynwb import NWBHDF5IO
from src.analysis.io.logger import log

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/omission_rasters"
METADATA_CSV = "outputs/spsam/grand_unit_metadata.csv"

# ---------------------------------------------------------------------------
# Helper utilities (mirrored from generate_strict_rasters.py)
# ---------------------------------------------------------------------------
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
            4: {"cond": "AAAX", "window": (3093, 3593), "codes": [5], "ctrl_codes": [1, 2]},
        },
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
            4: {"cond": "BBBX", "window": (3093, 3593), "codes": [10], "ctrl_codes": [6, 7]},
        },
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
            2: {"cond": "RXRR", "window": (1031, 1531), "codes": list(range(27, 35)), "ctrl_codes": list(range(11, 27))},
            3: {"cond": "RRXR", "window": (2062, 2562), "codes": [35, 37, 39, 41], "ctrl_codes": list(range(11, 27))},
            4: {"cond": "RRRX", "window": (3093, 3593), "codes": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50], "ctrl_codes": list(range(11, 27))},
        },
    },
}

SLOT_COLORS = [
    (0, 500, "#FCF9E3"),
    (1031, 1531, "#F6EEF9"),
    (2062, 2562, "#E9F5FC"),
    (3093, 3593, "#FDF2E9"),
]

time_bins = np.arange(-1000, 4001)

def get_onsets(intervals_df, allowed_codes):
    correct = pd.to_numeric(intervals_df["correct"], errors="coerce") == 1.0
    stim = pd.to_numeric(intervals_df["stimulus_number"], errors="coerce") == 2.0
    cond = pd.to_numeric(intervals_df["task_condition_number"], errors="coerce").isin(allowed_codes)
    return intervals_df.loc[correct & stim & cond, "start_time"].values

def get_nwb_file_map():
    m = {}
    for f in glob.glob(f"{NWB_DIR}/*.nwb"):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m

def main():
    if not os.path.exists(METADATA_CSV):
        log.error("Metadata CSV not found – run the SpSAM pipeline first.")
        return
    df = pd.read_csv(METADATA_CSV)
    stable = df[df["is_stable"]].copy()

    # Strict omission neurons (pre‑computed list)
    strict_path = "outputs/strict_omission_units.csv"
    if os.path.exists(strict_path):
        strict_df = pd.read_csv(strict_path)
        omission_units = stable.merge(strict_df, on=["session_id", "unit_id"], how="inner")
    else:
        omission_units = pd.DataFrame(columns=stable.columns)
    omission_units["target_group"] = "omission"

    # Top 50 stimulus‑positive (balanced across areas)
    sp_df = stable[stable["group"] == "stimulus_positive"].copy()
    sp_selected = []
    for area in sorted(sp_df["area"].unique()):
        area_df = sp_df[sp_df["area"] == area].sort_values("snr", ascending=False)
        sp_selected.extend(area_df.head(50).to_dict("records"))
    sp_units = pd.DataFrame(sp_selected)
    sp_units["target_group"] = "stim_positive"

    # Top 50 stimulus‑negative (balanced across areas)
    sn_df = stable[stable["group"] == "stimulus_negative"].copy()
    sn_selected = []
    for area in sorted(sn_df["area"].unique()):
        area_df = sn_df[sn_df["area"] == area].sort_values("snr", ascending=False)
        sn_selected.extend(area_df.head(50).to_dict("records"))
    sn_units = pd.DataFrame(sn_selected)
    sn_units["target_group"] = "stim_negative"

    targets = pd.concat([omission_units, sp_units, sn_units], ignore_index=True)
    targets["session_id"] = targets["session_id"].astype(str)
    targets["unit_id"] = targets["unit_id"].astype(int)
    log.action(f"Units to plot: {len(targets)} (omission={len(omission_units)}, +={len(sp_units)}, -={len(sn_units)})")

    shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    nwb_map = get_nwb_file_map()
    for sess_id, group in targets.groupby("session_id"):
        if sess_id not in nwb_map:
            log.warn(f"NWB missing for session {sess_id}; skipping.")
            continue
        nwb_path = nwb_map[sess_id]
        log.action(f"Processing session {sess_id}")
        with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
            nwb = io.read()
            intervals_df = nwb.intervals["omission_glo_passive"].to_dataframe()
            units_df = nwb.units.to_dataframe()
            for _, unit_row in group.iterrows():
                uid = int(unit_row["unit_id"])
                area = unit_row["area"]
                grp = unit_row["target_group"]
                row = units_df.loc[uid]
                spike_times = row["spike_times"]
                wf_mean = row.get("waveform_mean")
                for fam_name, fam_cfg in FAMILIES.items():
                    conds = fam_cfg["conds"]
                    codes = fam_cfg["codes"]
                    colors = fam_cfg["colors"]
                    onsets = {c: get_onsets(intervals_df, codes[c]) for c in conds}
                    rasters = {}
                    sdfs = {}
                    sems = {}
                    for cond, ons in onsets.items():
                        if len(ons) == 0:
                            continue
                        ons = ons[:40]
                        spike_mat = np.zeros((len(ons), len(time_bins)))
                        aligned_spikes = []
                        for ti, t_on in enumerate(ons):
                            win_start = t_on - 1.0
                            win_end = t_on + 4.0
                            trial_sp = spike_times[(spike_times >= win_start) & (spike_times <= win_end)]
                            aligned_ms = (trial_sp - t_on) * 1000.0
                            aligned_spikes.append(aligned_ms)
                            hist, _ = np.histogram(aligned_ms, bins=np.arange(-1000.5, 4001.5))
                            spike_mat[ti, :] = hist
                        rasters[cond] = aligned_spikes
                        mean_rate = np.mean(spike_mat, axis=0) * 1000.0
                        std_rate = np.std(spike_mat, axis=0) * 1000.0
                        sem_rate = std_rate / np.sqrt(len(ons))
                        sdfs[cond] = ndimage.gaussian_filter1d(mean_rate, sigma=40.0)
                        sems[cond] = ndimage.gaussian_filter1d(sem_rate, sigma=40.0)
                    # Plot
                    fig = plt.figure(figsize=(13, 14), facecolor="white")
                    gs = fig.add_gridspec(5, 2, width_ratios=[3, 1], height_ratios=[1, 1, 1, 1, 3.5])
                    axes_raster = [fig.add_subplot(gs[i, 0]) for i in range(4)]
                    ax_psth = fig.add_subplot(gs[4, 0])
                    ax_text = fig.add_subplot(gs[0:4, 1])
                    ax_text.axis("off")
                    ax_wf = fig.add_subplot(gs[4, 1])
                    for ax_idx, cond in enumerate(conds):
                        ax = axes_raster[ax_idx]
                        for start, end, col in SLOT_COLORS:
                            ax.axvspan(start, end, color=col, alpha=0.8, zorder=0)
                        for marker in [0, 1031, 2062, 3093]:
                            ax.axvline(marker, color="#C0C0C0", linestyle="--", linewidth=1.0, zorder=1)
                        if cond in rasters:
                            for tr_idx, tr_sp in enumerate(rasters[cond]):
                                ax.vlines(tr_sp, tr_idx - 0.4, tr_idx + 0.4, colors="black", linewidth=0.5)
                        ax.set_ylim(-1, 40)
                        ax.set_title(f"{cond} Raster (N={len(rasters.get(cond, []))})", fontsize=11)
                        ax.set_ylabel("Trials", fontsize=9)
                        ax.set_xlim(-1000, 4000)
                        ax.spines["top"].set_visible(False)
                        ax.spines["right"].set_visible(False)
                        ax.tick_params(labelbottom=False)
                    # PSTH
                    for start, end, col in SLOT_COLORS:
                        ax_psth.axvspan(start, end, color=col, alpha=0.8, zorder=0)
                    for marker in [0, 1031, 2062, 3093]:
                        ax_psth.axvline(marker, color="#C0C0C0", linestyle="--", linewidth=1.0, zorder=1)
                    for cond in conds:
                        if cond in sdfs:
                            ax_psth.plot(time_bins, sdfs[cond], color=colors[cond], label=cond, linewidth=1.5)
                            if cond in sems:
                                ax_psth.fill_between(time_bins, sdfs[cond] - sems[cond], sdfs[cond] + sems[cond], color=colors[cond], alpha=0.15)
                    ax_psth.legend(loc="upper center", bbox_to_anchor=(0.5, 1.08), ncol=4, frameon=False, fontsize=10)
                    ax_psth.set_xlabel("Time from p1 onset (ms)", fontsize=10)
                    ax_psth.set_ylabel("FR (Hz)", fontsize=10)
                    ax_psth.set_xlim(-1000, 4000)
                    ax_psth.spines["top"].set_visible(False)
                    ax_psth.spines["right"].set_visible(False)
                    # Waveform
                    if wf_mean is not None:
                        wf_col = "#9400D3" if grp == "omission" else "#CFB87C"
                        ax_wf.plot(wf_mean, color=wf_col, linewidth=2.0)
                        ax_wf.set_title("Mean Waveform", fontsize=10, fontweight="bold")
                        ax_wf.set_xlabel("Samples", fontsize=8)
                        ax_wf.set_ylabel("Amplitude (µV)", fontsize=8)
                        ax_wf.spines["top"].set_visible(False)
                        ax_wf.spines["right"].set_visible(False)
                    else:
                        ax_wf.text(0.5, 0.5, "No Waveform\nData", ha="center", va="center", fontsize=10)
                        ax_wf.axis("off")
                    # Metadata box
                    layer = unit_row.get("layer", "unresolved")
                    snr = unit_row.get("snr", 0.0)
                    fr = unit_row.get("firing_rate", 0.0)
                    wf_cls = unit_row.get("waveform_class", "unknown")
                    wf_dur = unit_row.get("waveform_duration", 0.0)
                    info = (
                        f"Unit ID: {uid}\n"
                        f"Session: {sess_id}\n"
                        f"Area: {area}\n"
                        f"Layer: {layer}\n"
                        f"Group: {grp.replace('_', ' ').title()}\n"
                        f"SNR: {snr:.2f}\n"
                        f"Mean FR: {fr:.2f} Hz\n"
                        f"Waveform: {wf_cls}\n"
                        f"Duration: {wf_dur:.1f} ms"
                    )
                    ax_text.text(0.05, 0.9, info, fontsize=9.5, verticalalignment="top",
                                  bbox=dict(boxstyle="round,pad=0.6", facecolor="#FDFDFD", edgecolor="#E0E0E0", alpha=0.95))
                    # Title & save
                    title = f"{grp.replace('_', ' ').title()} | {area} | Session {sess_id} | Unit {uid} | {fam_name}-Family"
                    plt.suptitle(title, fontsize=13, fontweight='bold', y=0.98)
                    plt.tight_layout()
                    filename = f"{grp}_{area.replace(', ', '_')}_ses{sess_id}_unit{uid}_{fam_name}_family.svg"
                    plt.savefig(os.path.join(OUTPUT_DIR, filename), format="svg", facecolor="white")
                    plt.close()
    log.action("Raster generation completed.")

if __name__ == "__main__":
    main()
