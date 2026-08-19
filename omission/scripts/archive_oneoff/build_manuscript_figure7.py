"""
build_manuscript_figure7.py — Manuscript Figure 7 Generator (Spike-LFP PPC Pipeline)
Loads single-unit spike times for stable-plus units, corresponding LFP channels,
performs Hilbert phase-extraction, computes Phase-Locking Index (PLI) or PPC,
and plots polar distributions.
Note: Figure 7 is TBD by domain experts; this script serves as the runnable pipeline skeleton.
"""

from __future__ import annotations
import os
import sys
import datetime
from pathlib import Path
import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import hilbert, butter, filtfilt

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.spiking import phase_locking_index

OUT_DIR = REPO_ROOT / "outputs/publication_figures"
SESSION_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"

def butter_bandpass(lowcut, highcut, fs, order=4):
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def butter_bandpass_filter(data, lowcut, highcut, fs, order=4):
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = filtfilt(b, a, data)
    return y

def main():
    if not Path(SESSION_PATH).exists():
        print(f"Session NWB file not found at {SESSION_PATH}")
        return
        
    print("Loading NWB session...")
    sess = oa.read(SESSION_PATH)
    
    # 1. Select representative S+, S-, and O+ units
    # (Exemplars resolved from previous audits)
    units_to_show = {
        "O+ (Unit 51)": 51,
        "S+ (Unit 89)": 88,  # row index
        "S- (Unit 6)": 181,  # row index
    }
    
    # 2. Load raw LFP data (e.g. Theta band 4-8Hz, or Beta band 15-30Hz)
    # Using probe_0 (Probe A) channels as example
    print("Loading LFP signals using h5py fallback...")
    fs = 1000.0  # sampling rate
    with h5py.File(SESSION_PATH, "r") as f:
        # direct access to avoid build blockage
        lfp_dataset = f["acquisition/probe_0_lfp/data"]
        lfp_ts = f["acquisition/probe_0_lfp/timestamps"][:]
        # Load first channel as example
        lfp_sig = lfp_dataset[:, 0]
        
    print("Applying Beta bandpass filter (15-30 Hz) and Hilbert transform...")
    lfp_filtered = butter_bandpass_filter(lfp_sig, 15.0, 30.0, fs, order=4)
    # Compute analytical signal to get phase
    analytic_signal = hilbert(lfp_filtered)
    lfp_phases = np.angle(analytic_signal)  # in range [-pi, pi]
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Plotting polar histograms of spike-LFP phase locking
    fig = plt.figure(figsize=(12, 4))
    
    matplotlib.rcParams["font.sans-serif"] = "Arial"
    matplotlib.rcParams["font.family"] = "sans-serif"
    
    for idx, (label, row_idx) in enumerate(units_to_show.items()):
        ax = fig.add_subplot(1, 3, idx + 1, polar=True)
        
        # Retrieve spike times for this unit
        spike_times = sess.get_spike_times(row_idx)
        if spike_times is not None and len(spike_times) > 0:
            # Map spike times to LFP phase timestamps
            # (Finding closest LFP index for each spike time)
            spike_indices = np.searchsorted(lfp_ts, spike_times)
            spike_indices = np.clip(spike_indices, 0, len(lfp_phases) - 1)
            spike_phases = lfp_phases[spike_indices]
            
            # Compute PLI
            pli_res = phase_locking_index(spike_times, lfp_phases, lfp_ts)
            pli_val = pli_res.get("pli", 0.0)
            pref_phase = pli_res.get("preferred_phase", 0.0)
            
            # Plot polar histogram
            counts, theta = np.histogram(spike_phases, bins=24, range=(-np.pi, np.pi))
            widths = 2 * np.pi / 24
            bars = ax.bar(theta[:-1] + widths/2, counts, width=widths, bottom=0.0, color="#1D9E75", alpha=0.6, edgecolor="black")
            
            # Draw line in the direction of preferred phase
            ax.annotate("", xy=(pref_phase, max(counts)), xytext=(0, 0),
                        arrowprops=dict(arrowstyle="->", color="red", linewidth=2.0))
                        
            ax.set_title(f"{label}\nPLI = {pli_val:.3f}", fontsize=10, fontweight="bold", pad=15)
        else:
            ax.text(0.5, 0.5, "No Spikes", ha="center", va="center")
            
    plt.tight_layout()
    
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")
    out_svg = OUT_DIR / f"figure7_spike_lfp_coupling_{dt_suffix}.svg"
    fig.savefig(out_svg, bbox_inches="tight", dpi=200)
    print(f"Saved Figure 7 to {out_svg}")
    
    fig.savefig(OUT_DIR / "figure7_spike_lfp_coupling.png", bbox_inches="tight", dpi=200)
    fig.savefig(OUT_DIR / "figure7_spike_lfp_coupling.svg", bbox_inches="tight")

if __name__ == "__main__":
    main()
