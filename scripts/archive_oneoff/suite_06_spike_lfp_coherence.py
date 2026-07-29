"""
suite_06_spike_lfp_coherence.py — Spike-LFP Phase Locking Index (PLI) relationship
Loops through all valid sessions, dynamically loads the correct probe LFP data,
matches selected S+, S-, O+ unit spikes, and generates polar phase histograms.
Usage:
  python scripts/suite_06_spike_lfp_coherence.py
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
import datetime
import numpy as np
import pandas as pd
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import hilbert
from scipy.stats import rayleigh

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import jnwb as oa

READY_CSV = Path("artifacts/data/session_readiness.csv")
GRAND_TABLE_CSV = Path("outputs/classification/grand_unit_table_shuffle_sso.csv")

def main():
    if not READY_CSV.exists() or not GRAND_TABLE_CSV.exists():
        print("Required CSV files do not exist.")
        return
        
    readiness = pd.read_csv(READY_CSV)
    grand = pd.read_csv(GRAND_TABLE_CSV)
    
    active_sessions = readiness[readiness["nwb_ok"].astype(bool) & readiness["sidecar_ok"].astype(bool)]
    print(f"Looping over {len(active_sessions)} valid sessions...")
    
    out_dir = REPO_ROOT / "outputs/publication_figures/suite_spk_lfp"
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")

    # Mapping of probes: probeA -> probe_0_lfp, probeB -> probe_1_lfp, probeC -> probe_2_lfp
    probe_lfp_keys = {
        "probeA": "acquisition/probe_0_lfp/data",
        "probeB": "acquisition/probe_1_lfp/data",
        "probeC": "acquisition/probe_2_lfp/data"
    }

    for _, row in active_sessions.iterrows():
        stem = row["stem"]
        path = row["nwb_path"]
        prefix = row["session_prefix"]
        
        sub = grand[grand["nwb_stem"] == stem]
        if len(sub) == 0:
            continue
            
        s_plus_candidates = sub[sub["is_s_plus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        s_minus_candidates = sub[sub["is_s_minus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        o_plus_candidates = sub[sub["is_o_plus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        
        if len(s_plus_candidates) == 0 or len(s_minus_candidates) == 0 or len(o_plus_candidates) == 0:
            s_plus_candidates = sub[sub["display_class"] == "S+"].sort_values("firing_rate", ascending=False)
            s_minus_candidates = sub[sub["display_class"] == "S-"].sort_values("firing_rate", ascending=False)
            o_plus_candidates = sub[sub["display_class"] == "O+"].sort_values("firing_rate", ascending=False)
            
        if len(s_plus_candidates) == 0 or len(s_minus_candidates) == 0 or len(o_plus_candidates) == 0:
            print(f"Skipping {prefix}: missing candidates for S+ ({len(s_plus_candidates)}), S- ({len(s_minus_candidates)}), or O+ ({len(o_plus_candidates)})")
            continue
            
        units = {
            "S+": int(s_plus_candidates.iloc[0]["unit_id"]),
            "S-": int(s_minus_candidates.iloc[0]["unit_id"]),
            "O+": int(o_plus_candidates.iloc[0]["unit_id"])
        }
        
        print(f"Processing {prefix} with units S+={units['S+']}, S-={units['S-']}, O+={units['O+']}")
        
        try:
            sess = oa.read(path)
            units_df = sess.get_units()
        except Exception as e:
            print(f"Failed to load NWB {path}: {e}")
            continue

        fig, axes = plt.subplots(1, 3, figsize=(18, 6), subplot_kw=dict(projection='polar'))
        
        try:
            with h5py.File(path, "r") as f:
                el = sess.get_electrodes()
                
                # Check actual available datasets in acquisition group
                available_keys = list(f['acquisition'].keys())
                
                for col_idx, (cls, uid) in enumerate(units.items()):
                    peak_id = int(float(units_df.loc[uid, "peak_channel_id"]))
                    probe = el.loc[peak_id, "probe"]
                    lfp_key = probe_lfp_keys.get(probe)
                    
                    if not lfp_key or lfp_key.split('/')[1] not in available_keys:
                        # Fallback: take first available lfp dataset
                        fall_k = [k for k in available_keys if 'lfp' in k.lower()]
                        if fall_k:
                            lfp_key = f"acquisition/{fall_k[0]}/data"
                        else:
                            print(f"No LFP dataset available for unit {uid}")
                            continue
                            
                    lfp_data = f[lfp_key]
                    n_samples, n_ch = lfp_data.shape
                    
                    local_ch_idx = peak_id % n_ch
                    
                    fs = 1000.0
                    max_t = 100.0
                    max_samples = int(max_t * fs)
                    
                    trace = lfp_data[:max_samples, local_ch_idx].astype(float)
                    analytic_signal = hilbert(trace)
                    phases = np.angle(analytic_signal)
                    
                    spike_times = sess.get_spike_times(uid)
                    spike_times = spike_times[spike_times < max_t]
                    
                    spk_samples = (spike_times * fs).astype(int)
                    spk_samples = spk_samples[spk_samples < max_samples]
                    spk_phases = phases[spk_samples]
                    
                    r_val = np.abs(np.mean(np.exp(1j * spk_phases)))
                    p_val = rayleigh.sf(r_val * np.sqrt(len(spk_phases)))
                    
                    ax = axes[col_idx]
                    ax.hist(spk_phases, bins=24, color="#185FA5", alpha=0.7, edgecolor="black")
                    ax.set_title(f"{cls} Phase Lock (Unit {uid})\nMRV={r_val:.3f}, p={p_val:.2e}", fontsize=11, fontweight="bold", pad=15)
                    
            fig.suptitle(f"Suite 06: Spike-LFP Phase Locking (PLI) Curves — {prefix}", fontsize=14, fontweight="bold", y=1.02)
            plt.tight_layout()
            
            svg_path = out_dir / f"{prefix}_suite_06_spike_lfp_coherence_{dt_suffix}.svg"
            fig.savefig(svg_path, bbox_inches="tight")
            plt.close(fig)
            print(f"Saved {svg_path}")
            
            # Legacy default symlink mapping
            if prefix == "sub-C31o_ses-230823":
                legacy_path = out_dir / f"suite_06_spike_lfp_coherence_{dt_suffix}.svg"
                fig.savefig(legacy_path, bbox_inches="tight")
                
        except Exception as e:
            print(f"Error processing LFP dataset for {prefix}: {e}")

if __name__ == "__main__":
    main()
