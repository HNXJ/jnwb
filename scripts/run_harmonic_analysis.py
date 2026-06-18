"""
run_harmonic_analysis.py
========================
Orchestrates LFP-to-LFP and Spiking-to-LFP harmonic analysis on high SNR channels
across all 13 NWB sessions.

Saves results to: outputs/harmonic/
"""

import os
import glob
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from src.analysis.io.logger import log
from src.analysis.spsam.spsam_pipeline import map_group_to_lfp_key, build_channel_area_map
from src.analysis.harmonic.harmonic import (
    detect_high_snr_channels,
    get_bandpass_phase,
    get_bandpass_amplitude,
    compute_nm_phase_coupling,
    compute_spk_lfp_plv
)
from src.analysis.lfp.stats import compute_modulation_index

NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/harmonic"
METADATA_CSV = "outputs/spsam/grand_unit_metadata.csv"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Define harmonic frequency ranges
FS = 1000.0
FUNDAMENTAL_BAND = (4, 8)  # Theta
HARMONIC_BANDS = {
    "h2": (8, 16),    # Beta1 (1:2)
    "h3": (16, 24),   # Beta2 (1:3)
    "h4": (24, 32),   # Gamma1 (1:4)
    "h5": (32, 40),   # Gamma2 (1:5)
}

# Contexts to analyze
CONTEXT_WINDOWS = {
    "baseline": (-0.5, 0.0),  # Pre-onset (relative to p1)
    "standard": (0.0, 0.5),   # Post-onset (relative to standard stim)
    "omission": (0.0, 0.5),   # Post-onset (relative to omission)
}

def get_nwb_file_map():
    m = {}
    for f in glob.glob(f"{NWB_DIR}/*.nwb"):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        try:
            m[int(sid)] = f
        except ValueError:
            pass
    return m

def main():
    if not os.path.exists(METADATA_CSV):
        log.error(f"Metadata file {METADATA_CSV} not found. Run SpSAM pipeline first.")
        return

    log.action("Filtering high SNR channels...")
    high_snr_df = detect_high_snr_channels(METADATA_CSV, snr_threshold=1.5)
    high_snr_df.to_csv(f"{OUTPUT_DIR}/high_snr_channels.csv", index=False)
    log.action(f"Found {len(high_snr_df)} high SNR channels (SNR >= 1.5) across sessions.")

    nwb_map = get_nwb_file_map()
    
    lfp_lfp_results = []
    spk_lfp_results = []
    
    # Process session-by-session
    sessions = high_snr_df["session_id"].unique()
    for ses in sorted(sessions):
        if ses not in nwb_map:
            log.warning(f"NWB file for session {ses} not found in {NWB_DIR}.")
            continue
            
        nwb_path = nwb_map[ses]
        log.action(f"Processing session {ses} from {nwb_path}")
        
        # Load NWB
        with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
            nwb = io.read()
            
            # 1. Build channel area map
            elec_df = nwb.electrodes.to_dataframe()
            channel_area_map = build_channel_area_map(elec_df)
            
            # Cache all unit spikes for fast access
            units_df = nwb.units.to_dataframe()
            unit_spikes_cache = {}
            for u_idx, row in units_df.iterrows():
                unit_spikes_cache[u_idx] = np.array(row["spike_times"], dtype=float)
            
            # Find high SNR channels in this session
            ses_channels = high_snr_df[high_snr_df["session_id"] == ses].copy()
            
            # Pre-load LFP caches for probes holding high SNR channels
            probe_names = elec_df["group_name"].unique()
            lfp_caches = {}
            for p_name in probe_names:
                lfp_key, probe_idx = map_group_to_lfp_key(p_name)
                if lfp_key in nwb.acquisition:
                    try:
                        lfp_caches[probe_idx] = nwb.acquisition[lfp_key].data[:]
                    except Exception as e:
                        log.warning(f"Session {ses}: Failed to load LFP for probe {p_name}: {e}")
                        
            # Get event timings
            if "omission_glo_passive" not in nwb.intervals:
                continue
            int_df = nwb.intervals["omission_glo_passive"].to_dataframe()
            for col in ("correct", "is_omission", "stimulus_number"):
                int_df[col] = pd.to_numeric(int_df[col], errors="coerce")
                
            correct_mask = int_df["correct"] == 1.0
            
            p1_onsets = int_df[correct_mask & (int_df["stimulus_number"] == 2.0)]["start_time"].values
            std_onsets = int_df[
                correct_mask &
                int_df["stimulus_number"].isin([2.0, 3.0, 4.0, 5.0]) &
                (int_df["is_omission"] != 1.0)
            ]["start_time"].values
            om_onsets = int_df[
                correct_mask &
                int_df["stimulus_number"].isin([3.0, 4.0, 5.0]) &
                (int_df["is_omission"] == 1.0)
            ]["start_time"].values
            
            # Context event times
            contexts = {
                "baseline": p1_onsets,
                "standard": std_onsets,
                "omission": om_onsets,
            }
            
            # Process each high SNR channel
            for _, ch_row in ses_channels.iterrows():
                global_ch = int(ch_row["peak_channel_global"])
                if global_ch not in channel_area_map:
                    continue
                info = channel_area_map[global_ch]
                probe_id = info["probe_id"]
                local_ch = info["local_idx"]
                area = info["area"]
                
                if probe_id not in lfp_caches or local_ch < 0:
                    continue
                    
                lfp_full = lfp_caches[probe_id]
                if local_ch >= lfp_full.shape[1]:
                    continue
                    
                lfp_channel = lfp_full[:, local_ch].astype(float)
                
                # Retrieve units recorded on this peak channel
                session_units = pd.read_csv(METADATA_CSV)
                ses_units_ch = session_units[
                    (session_units["session_id"] == ses) &
                    (session_units["peak_channel_global"] == global_ch) &
                    (session_units["is_stable"])
                ]
                
                # Run context-specific analyses
                for ctx_name, onsets in contexts.items():
                    if len(onsets) == 0:
                        continue
                        
                    # Extract continuous LFP and spike timestamps
                    lfp_trials = []
                    win_start, win_end = CONTEXT_WINDOWS[ctx_name]
                    
                    # Gather LFP segments and unit spikes
                    unit_spikes_list = {u_row["unit_id"]: [] for _, u_row in ses_units_ch.iterrows()}
                    units_data = {u_row["unit_id"]: u_row for _, u_row in ses_units_ch.iterrows()}
                    
                    # Store relative timestamps for spikes
                    for trial_idx, t in enumerate(onsets[:80]):  # Limit to first 80 trials for memory efficiency
                        start_time = t + win_start
                        end_time = t + win_end
                        
                        start_idx = int(round(start_time * FS))
                        end_idx = int(round(end_time * FS))
                        
                        if start_idx < 0 or end_idx > len(lfp_channel):
                            continue
                            
                        lfp_seg = lfp_channel[start_idx:end_idx]
                        if len(lfp_seg) != 500:
                            continue
                        lfp_trials.append(lfp_seg)
                        
                        # Add spikes within this window
                        for u_id in unit_spikes_list:
                            spikes = unit_spikes_cache[u_id]
                            # Find spikes in [start_time, end_time] and convert to relative trial time [0, 0.5]
                            spk_win = spikes[(spikes >= start_time) & (spikes < end_time)] - start_time
                            # Store global spike times for PLV matching LFP timestamps
                            unit_spikes_list[u_id].extend(spk_win + (trial_idx * 0.5))
                            
                    if not lfp_trials:
                        continue
                        
                    # LFP trials to flat 1D array
                    lfp_flat = np.concatenate(lfp_trials)
                    lfp_timestamps = np.arange(len(lfp_flat)) / FS
                    
                    # 1. LFP-to-LFP Harmonic Analysis
                    # Extract Theta phase and Gamma amplitude for PAC
                    theta_phase = get_bandpass_phase(lfp_flat, FS, FUNDAMENTAL_BAND[0], FUNDAMENTAL_BAND[1])
                    gamma_amp = get_bandpass_amplitude(lfp_flat, FS, 30.0, 80.0)
                    pac_mi = compute_modulation_index(theta_phase, gamma_amp)
                    
                    # Extract phase coupling values for harmonics (n:m phase coupling)
                    coupling_vals = {}
                    for h_name, h_band in HARMONIC_BANDS.items():
                        # Determine n:m ratio. e.g. Theta is 4-8Hz (center 6Hz), h2 is 8-16Hz (center 12Hz) -> 1:2 coupling (n=2, m=1)
                        h_phase = get_bandpass_phase(lfp_flat, FS, h_band[0], h_band[1])
                        # If theta = f, h2 = 2f, PLV_2_1 is < e^(i(2 * phi_theta - 1 * phi_h2)) >
                        n_factor = int(h_name[1])  # e.g., 'h2' -> 2
                        coupling_vals[h_name] = compute_nm_phase_coupling(theta_phase, h_phase, n=n_factor, m=1)
                        
                    lfp_lfp_results.append({
                        "session_id": ses,
                        "channel_global": global_ch,
                        "area": area,
                        "context": ctx_name,
                        "pac_mi": pac_mi,
                        **{f"{h}_plv": coupling_vals[h] for h in HARMONIC_BANDS}
                    })
                    
                    # 2. Spiking-to-LFP Harmonic Analysis
                    for u_id, spk_list in unit_spikes_list.items():
                        spk_arr = np.array(spk_list)
                        u_meta = units_data[u_id]
                        
                        spk_plv_vals = {}
                        # Theta (Fundamental) PLV
                        spk_plv_vals["theta"] = compute_spk_lfp_plv(spk_arr, theta_phase, lfp_timestamps)
                        
                        # Harmonics PLVs
                        for h_name, h_band in HARMONIC_BANDS.items():
                            h_phase = get_bandpass_phase(lfp_flat, FS, h_band[0], h_band[1])
                            spk_plv_vals[h_name] = compute_spk_lfp_plv(spk_arr, h_phase, lfp_timestamps)
                            
                        spk_lfp_results.append({
                            "session_id": ses,
                            "channel_global": global_ch,
                            "unit_id": u_id,
                            "area": area,
                            "context": ctx_name,
                            "group": u_meta["group"],
                            "wf_class": u_meta["waveform_class"],
                            "theta_plv": spk_plv_vals["theta"],
                            **{f"{h}_plv": spk_plv_vals[h] for h in HARMONIC_BANDS}
                        })
                        
    # Save results
    df_lfp_lfp = pd.DataFrame(lfp_lfp_results)
    df_lfp_lfp.to_csv(f"{OUTPUT_DIR}/lfp_lfp_harmonic.csv", index=False)
    
    df_spk_lfp = pd.DataFrame(spk_lfp_results)
    df_spk_lfp.to_csv(f"{OUTPUT_DIR}/spk_lfp_harmonic.csv", index=False)
    
    log.action("Harmonic analysis successfully completed across all sessions!")

if __name__ == "__main__":
    main()
