#!/usr/bin/env python3
"""
Pipeline: Joined P2/P3 TFR Traces with +-2SEM Error Shading.
Takes an NWB file, probe letter, and channel IDs, then loads precomputed TFR arrays.
Aligns and joins trials from P2 and P3 omission conditions to achieve higher N,
and plots 1D TFR traces for canonical frequency bands with +-2SEM shaded error margins.
"""

import os
import sys
import argparse
import pathlib
import logging
import numpy as np
import matplotlib.pyplot as plt

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Ensure project root is on the Python path
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.resolve()))
import jnwb as oa

# Canonical frequency bands matching TFRAnalyzer.BANDS
BANDS_TFR = {
    "Theta": (4.0, 8.0),
    "Alpha": (8.0, 15.0),
    "Beta": (15.0, 30.0),
    "Low Gamma": (30.0, 60.0),
    "High Gamma": (60.0, 120.0)
}

# Standard colors for frequency bands
BAND_COLORS = {
    "Theta": "#9400D3",
    "Alpha": "#4B0082",
    "Beta": "#0000FF",
    "Low Gamma": "#CFB87C",
    "High Gamma": "#D55E00"
}

# Conditions
P2_OMIT_CONDS = ['AXAB', 'BXBA', 'RXRR']
P2_CTRL_CONDS = ['AAAB', 'BBBA', 'RRRR']
P3_OMIT_CONDS = ['AAXB', 'BBXA', 'RRXR']
P3_CTRL_CONDS = ['AAAB', 'BBBA', 'RRRR']

# Standard TFR axis definitions
FREQS_HZ = np.arange(3, 201, 2)  # 3 to 199 Hz step 2
TIMES_MS = -1000.0 + np.arange(500) * 10.0  # -1000 to 3990 ms

def parse_args():
    parser = argparse.ArgumentParser(description="Joined P2/P3 TFR Trace Pipeline")
    parser.add_argument(
        "--nwb",
        type=str,
        default="D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb",
        help="Path to NWB session file"
    )
    parser.add_argument(
        "--probe",
        type=str,
        default="A",
        help="Probe letter (A, B, C, ...)"
    )
    parser.add_argument(
        "--area",
        type=str,
        default="FEF",
        help="Target brain area (e.g., FEF, V1, V4)"
    )
    parser.add_argument(
        "--channels",
        type=str,
        default=None,
        help="Comma-separated channel indices (e.g. 40,41,42). If omitted, auto-resolves area channels."
    )
    parser.add_argument(
        "--tfr-dir",
        type=str,
        default="D:/workspace/data/tfr_arrays",
        help="Directory containing precomputed .npy TFR arrays"
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="D:/workspace/omission/outputs/figures",
        help="Output folder for figures"
    )
    return parser.parse_args()

def load_and_average_channels(file_path, channels):
    """Load TFR array and average over selected channels."""
    if not os.path.exists(file_path):
        return None
    
    # Load array. Shape is (trials, channels, freqs, times)
    try:
        power = np.load(file_path, mmap_mode="r")
    except Exception as e:
        log.error(f"Error loading {file_path}: {e}")
        return None

    # Resolve local channel indices (0-127)
    local_channels = [c % 128 for c in channels]
    
    # Average power across selected channels
    # power: (trials, channels, freqs, times)
    channel_power = power[:, local_channels, :, :]
    averaged_power = np.mean(channel_power, axis=1)  # shape: (trials, freqs, times)
    return averaged_power

def align_trials(power_array, align_shift_ms):
    """Align trial time axis to omission onset.
    Aligns to relative window: -1500 ms to +1000 ms relative to omission onset (0 ms).
    """
    # Shift of onset index: times starts at -1000 ms, step is 10 ms.
    onset_idx = int(round((align_shift_ms - (-1000.0)) / 10.0))
    
    # We want window [-1500, 1000] ms -> [-150 bins, +100 bins] relative to onset
    start_idx = onset_idx - 150
    end_idx = onset_idx + 100
    
    n_trials, n_freqs, n_times = power_array.shape
    aligned = np.full((n_trials, n_freqs, 250), np.nan, dtype=np.float32)
    
    src_start = max(0, start_idx)
    src_end = min(n_times, end_idx)
    dest_start = src_start - start_idx
    dest_end = dest_start + (src_end - src_start)
    
    aligned[:, :, dest_start:dest_end] = power_array[:, :, src_start:src_end]
    return aligned

def db_normalize_trials(aligned_power):
    """dB normalize each trial relative to its pre-omission delay epoch (-500 to 0 ms).
    aligned_power shape: (trials, freqs, 250) representing -1500 to 1000 ms in 10 ms bins.
    """
    # -500 to 0 ms relative to omission corresponds to aligned bins 100 to 150
    # Let's define the mask precisely:
    # Bins are -150 to 100 relative to 0ms (index 150)
    # So -500ms is index 100, 0ms is index 150.
    baseline_mask = slice(100, 150)
    
    baseline = np.mean(aligned_power[:, :, baseline_mask], axis=2, keepdims=True)
    
    # dB normalization
    power_db = 10.0 * np.log10(np.maximum(aligned_power, 1e-12) / np.maximum(baseline, 1e-12))
    power_db = np.nan_to_num(power_db, nan=0.0)
    return power_db

def main():
    args = parse_args()
    nwb_path = pathlib.Path(args.nwb)
    
    if not nwb_path.is_file():
        log.error(f"NWB file not found: {nwb_path}")
        sys.exit(1)
        
    log.info(f"Opening NWB session: {nwb_path}")
    session = oa.read(str(nwb_path), context='omission_glo_passive')
    
    # Resolve prefix from NWB filename
    parts = nwb_path.stem.split('_')
    if len(parts) >= 2:
        prefix = f"{parts[0]}_{parts[1]}"
    else:
        prefix = nwb_path.stem
        
    log.info(f"Resolved TFR file prefix: {prefix}")
    
    # Resolve channels mapping to target area & probe if not specified
    if args.channels is not None:
        channels = [int(c.strip()) for c in args.channels.split(',')]
        log.info(f"Using user-specified channels: {channels}")
    else:
        log.info("No channels specified. Auto-resolving area channels...")
        df = session.lfp_channel_areas()
        # Filter by area name
        area_df = df[df['area'].str.upper().str.contains(args.area.upper())]
        
        # Probe channel boundaries
        probe_ranges = {'A': (0, 127), 'B': (128, 255), 'C': (256, 383), 'D': (384, 511)}
        start_ch, end_ch = probe_ranges.get(args.probe.upper(), (0, 127))
        probe_df = area_df[(area_df['channel_id'] >= start_ch) & (area_df['channel_id'] <= end_ch)]
        
        channels = probe_df['channel_id'].values.tolist()
        if not channels:
            log.warning(f"No channels found mapping to area {args.area} on probe {args.probe}!")
            # Fallback: use all channels for the probe range
            channels = list(range(start_ch, end_ch + 1))
            log.info(f"Fallback to all probe channels: {channels[:5]}...{channels[-1]}")
        else:
            log.info(f"Auto-resolved {len(channels)} channels for area {args.area}: {channels[:5]}...{channels[-1]}")

    # Load and align trials for omission conditions
    tfr_dir = pathlib.Path(args.tfr_dir)
    
    omission_trials = []
    control_trials = []
    
    # P2 Omission (AXAB, BXBA, RXRR) aligned to 1031 ms
    for cond in P2_OMIT_CONDS:
        file_name = f"{prefix}-{args.probe}-{args.area}-{cond}.npy"
        file_path = tfr_dir / file_name
        power_array = load_and_average_channels(file_path, channels)
        if power_array is not None:
            aligned = align_trials(power_array, 1031.0)
            omission_trials.append(aligned)
            log.info(f"Loaded P2 Omission {cond} ({power_array.shape[0]} trials)")
            
    # P2 Control (AAAB, BBBA, RRRR) aligned to 1031 ms
    for cond in P2_CTRL_CONDS:
        file_name = f"{prefix}-{args.probe}-{args.area}-{cond}.npy"
        file_path = tfr_dir / file_name
        power_array = load_and_average_channels(file_path, channels)
        if power_array is not None:
            aligned = align_trials(power_array, 1031.0)
            control_trials.append(aligned)
            log.info(f"Loaded P2 Control {cond} ({power_array.shape[0]} trials)")

    # P3 Omission (AAXB, BBXA, RRXR) aligned to 2062 ms
    for cond in P3_OMIT_CONDS:
        file_name = f"{prefix}-{args.probe}-{args.area}-{cond}.npy"
        file_path = tfr_dir / file_name
        power_array = load_and_average_channels(file_path, channels)
        if power_array is not None:
            aligned = align_trials(power_array, 2062.0)
            omission_trials.append(aligned)
            log.info(f"Loaded P3 Omission {cond} ({power_array.shape[0]} trials)")
            
    # P3 Control (AAAB, BBBA, RRRR) aligned to 2062 ms
    for cond in P3_CTRL_CONDS:
        file_name = f"{prefix}-{args.probe}-{args.area}-{cond}.npy"
        file_path = tfr_dir / file_name
        power_array = load_and_average_channels(file_path, channels)
        if power_array is not None:
            # Shift by 2062 ms since control p3 matches slot 3 onset
            aligned = align_trials(power_array, 2062.0)
            control_trials.append(aligned)
            log.info(f"Loaded P3 Control {cond} ({power_array.shape[0]} trials)")

    if not omission_trials or not control_trials:
        log.error("Failed to load required TFR condition arrays. Exiting.")
        sys.exit(1)
        
    # Concatenate all trials along axis 0
    all_omission = np.concatenate(omission_trials, axis=0)
    all_control = np.concatenate(control_trials, axis=0)
    
    n_omit_trials = all_omission.shape[0]
    n_ctrl_trials = all_control.shape[0]
    log.info(f"Total pooled trials: Omission N = {n_omit_trials}, Control N = {n_ctrl_trials}")
    
    # dB normalize each trial individually
    all_omission_db = db_normalize_trials(all_omission)
    all_control_db = db_normalize_trials(all_control)
    
    # Compute trace mean and SEM for each frequency band
    aligned_times_ms = np.arange(-150, 100) * 10.0  # -1500 to 990 ms
    
    fig, axes = plt.subplots(len(BANDS_TFR), 1, figsize=(10, 12), sharex=True, facecolor="white")
    
    for idx, (band_name, (fmin, fmax)) in enumerate(BANDS_TFR.items()):
        ax = axes[idx]
        ax.set_facecolor("white")
        
        freq_mask = (FREQS_HZ >= fmin) & (FREQS_HZ <= fmax)
        color = BAND_COLORS[band_name]
        
        # 1. Omission Trace: average over frequencies, then mean & SEM over trials
        omit_band_power = np.nanmean(all_omission_db[:, freq_mask, :], axis=1)  # (trials, times)
        omit_mean = np.nanmean(omit_band_power, axis=0)
        omit_sem = np.nanstd(omit_band_power, axis=0, ddof=1) / np.sqrt(n_omit_trials)
        
        # 2. Control Trace: average over frequencies, then mean & SEM over trials
        ctrl_band_power = np.nanmean(all_control_db[:, freq_mask, :], axis=1)  # (trials, times)
        ctrl_mean = np.nanmean(ctrl_band_power, axis=0)
        ctrl_sem = np.nanstd(ctrl_band_power, axis=0, ddof=1) / np.sqrt(n_ctrl_trials)
        
        # Plot curves
        ax.plot(aligned_times_ms, omit_mean, color=color, linewidth=2.0, label=f"Omission (N={n_omit_trials})")
        # +-2SEM Shading/Patches
        ax.fill_between(aligned_times_ms, omit_mean - 2 * omit_sem, omit_mean + 2 * omit_sem, color=color, alpha=0.2)
        
        ax.plot(aligned_times_ms, ctrl_mean, color="#808080", linewidth=1.5, linestyle="--", label=f"Control (N={n_ctrl_trials})")
        ax.fill_between(aligned_times_ms, ctrl_mean - 2 * ctrl_sem, ctrl_mean + 2 * ctrl_sem, color="#808080", alpha=0.1)
        
        # Reference markers
        ax.axvline(0, color="purple", linestyle="--", linewidth=1.0)
        ax.axhline(0, color="black", linestyle=":", linewidth=0.7)
        
        ax.set_ylabel(f"{band_name}\nPower (dB)", fontsize=9)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        
        if idx == 0:
            ax.set_title(f"Pooled Omission TFR Traces with +-2SEM Shading\nArea {args.area}, Probe {args.probe}", fontsize=12, fontweight="bold")
            
        if idx == len(BANDS_TFR) - 1:
            ax.set_xlabel("Time from Omission Onset (ms)", fontsize=10)
            
        ax.legend(loc="upper right", fontsize=8, frameon=True, facecolor="white", edgecolor="#D3D3D3")
        
    plt.tight_layout()
    
    # Save output files
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    base_name = f"tfr_traces_{args.area}_probe{args.probe}_joined_p2p3"
    png_path = out_dir / f"{base_name}.png"
    pdf_path = out_dir / f"{base_name}.pdf"
    
    plt.savefig(png_path, dpi=300, bbox_inches="tight")
    plt.savefig(pdf_path, format="pdf", bbox_inches="tight")
    plt.close()
    
    log.info(f"Successfully saved joined TFR traces to {png_path} and {pdf_path}")

if __name__ == "__main__":
    main()
