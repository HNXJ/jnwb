"""
run_coherence_analysis.py
==========================
Orchestrates LFP-to-LFP coherence analysis between brain areas across all sessions.
Saves results to outputs/coherence/coherence_results.csv
"""

import os
import glob
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from src.analysis.io.logger import log
from src.analysis.spsam.spsam_pipeline import map_group_to_lfp_key, build_channel_area_map
from src.analysis.coherence.coherence import get_responsive_channels, compute_spectral_coherence

NWB_DIR = "D:/analysis/nwb"
OUTPUT_DIR = "outputs/coherence"
METADATA_CSV = "outputs/spsam/grand_unit_metadata.csv"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Coherence bands
BANDS = {
    "theta": (4, 8),
    "alpha": (8, 12),
    "beta": (12, 30),
    "gamma": (30, 80),
}

FS = 1000.0

# Condition groups for slot omissions
OMISSION_CONDITIONS = {
    "p2": [3, 8] + list(range(27, 35)),
    "p3": [4, 9] + [35, 37, 39, 41],
    "p4": [5, 10] + [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
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
        print("Error: Metadata file not found. Run SpSAM first.")
        return
        
    log.action("Filtering responsive stable channels...")
    resp_ch = get_responsive_channels(METADATA_CSV)
    resp_ch.to_csv(f"{OUTPUT_DIR}/responsive_channels.csv", index=False)
    log.action(f"Found {len(resp_ch)} responsive stable channels across sessions.")
    
    nwb_map = get_nwb_file_map()
    results = []
    
    sessions = resp_ch["session_id"].unique()
    for ses in sorted(sessions):
        if ses not in nwb_map:
            continue
            
        nwb_path = nwb_map[ses]
        log.action(f"Processing session {ses} from {nwb_path}")
        
        with NWBHDF5IO(nwb_path, "r", load_namespaces=True) as io:
            nwb = io.read()
            
            # 1. Build channel area map
            elec_df = nwb.electrodes.to_dataframe()
            channel_area_map = build_channel_area_map(elec_df)
            
            # Find responsive channels in this session
            ses_ch = resp_ch[resp_ch["session_id"] == ses].copy()
            
            # Map responsive global channels to area, layer, and local indices
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
            for col in ("correct", "is_omission", "stimulus_number", "task_condition_number"):
                int_df[col] = pd.to_numeric(int_df[col], errors="coerce")
                
            correct_mask = int_df["correct"] == 1.0
            
            # Epochs mapping
            p1_onsets = int_df[correct_mask & (int_df["stimulus_number"] == 2.0)]["start_time"].values
            
            # Group channels by area
            area_channels = {}
            for _, r in ses_ch.iterrows():
                g_ch = int(r["peak_channel_global"])
                if g_ch in channel_area_map:
                    ch_info = channel_area_map[g_ch]
                    area = ch_info["area"]
                    if area not in area_channels:
                        area_channels[area] = []
                    area_channels[area].append(ch_info)
                    
            areas_in_session = sorted(area_channels.keys())
            
            # Load LFP epochs for three contexts
            epochs = ["baseline", "stimulus", "omission"]
            epoch_lfps = {e: {} for e in epochs}  # area -> channel_idx -> concatenated_signal
            
            for area in areas_in_session:
                epoch_lfps["baseline"][area] = {}
                epoch_lfps["stimulus"][area] = {}
                epoch_lfps["omission"][area] = {}
                
                for ch_info in area_channels[area]:
                    p_id = ch_info["probe_id"]
                    l_ch = ch_info["local_idx"]
                    
                    if p_id not in lfp_caches or l_ch < 0:
                        continue
                    lfp_full = lfp_caches[p_id]
                    if l_ch >= lfp_full.shape[1]:
                        continue
                        
                    lfp_ch = lfp_full[:, l_ch].astype(float)
                    
                    # 1. Baseline: -0.5 to 0.0s relative to p1
                    base_segs = []
                    for t in p1_onsets[:80]:
                        start = int(round((t - 0.5) * FS))
                        end = int(round(t * FS))
                        if 0 <= start and end <= len(lfp_ch):
                            base_segs.append(lfp_ch[start:end])
                    if base_segs:
                        epoch_lfps["baseline"][area][l_ch] = np.concatenate(base_segs)
                        
                    # 2. Stimulus: 0.0s to 0.5s relative to p1
                    stim_segs = []
                    for t in p1_onsets[:80]:
                        start = int(round(t * FS))
                        end = int(round((t + 0.5) * FS))
                        if 0 <= start and end <= len(lfp_ch):
                            stim_segs.append(lfp_ch[start:end])
                    if stim_segs:
                        epoch_lfps["stimulus"][area][l_ch] = np.concatenate(stim_segs)
                        
                    # 3. Omission: slot-specific segment relative to p1
                    omit_segs = []
                    # Filter trials by condition family for slot omissions
                    for _, trial in int_df[correct_mask & (int_df["stimulus_number"] == 2.0)].iterrows():
                        t = trial["start_time"]
                        cond = trial["task_condition_number"]
                        
                        # Slot 2 omission (p2)
                        if cond in OMISSION_CONDITIONS["p2"]:
                            start = int(round((t + 1.033) * FS))
                            end = int(round((t + 1.533) * FS))
                        # Slot 3 omission (p3)
                        elif cond in OMISSION_CONDITIONS["p3"]:
                            start = int(round((t + 2.066) * FS))
                            end = int(round((t + 2.566) * FS))
                        # Slot 4 omission (p4)
                        elif cond in OMISSION_CONDITIONS["p4"]:
                            start = int(round((t + 3.099) * FS))
                            end = int(round((t + 3.599) * FS))
                        else:
                            continue
                            
                        if 0 <= start and end <= len(lfp_ch):
                            omit_segs.append(lfp_ch[start:end])
                    if omit_segs:
                        epoch_lfps["omission"][area][l_ch] = np.concatenate(omit_segs)
                        
            # Compute coherence for all area pairs
            for i, area1 in enumerate(areas_in_session):
                for j, area2 in enumerate(areas_in_session):
                    if i >= j:  # symmetric, compute once
                        continue
                        
                    for epoch in epochs:
                        # Find valid channels
                        ch1_dict = epoch_lfps[epoch][area1]
                        ch2_dict = epoch_lfps[epoch][area2]
                        
                        if not ch1_dict or not ch2_dict:
                            continue
                            
                        # Average coherence across channel pairs
                        pair_coherences = {b: [] for b in BANDS}
                        
                        for ch1_idx, sig1 in ch1_dict.items():
                            for ch2_idx, sig2 in ch2_dict.items():
                                min_len = min(len(sig1), len(sig2))
                                if min_len < 256:
                                    continue
                                    
                                f, cxy = compute_spectral_coherence(sig1[:min_len], sig2[:min_len], fs=FS)
                                
                                # Extract band averages
                                for b_name, b_range in BANDS.items():
                                    mask = (f >= b_range[0]) & (f <= b_range[1])
                                    if np.any(mask):
                                        pair_coherences[b_name].append(np.mean(cxy[mask]))
                                        
                        # Record mean coherence per band
                        if any(pair_coherences.values()):
                            results.append({
                                "session_id": ses,
                                "area1": area1,
                                "area2": area2,
                                "epoch": epoch,
                                **{f"{b}_coherence": np.mean(pair_coherences[b]) if pair_coherences[b] else np.nan for b in BANDS}
                            })
                            
    df_res = pd.DataFrame(results)
    df_res.to_csv(f"{OUTPUT_DIR}/coherence_results.csv", index=False)
    log.action("LFP-to-LFP coherence analysis successfully completed across all sessions!")

if __name__ == "__main__":
    main()
