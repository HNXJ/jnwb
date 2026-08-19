"""
suite_02_raster_s2_om2.py — Raster suite of S++/S--/O++ neurons
Loops through all valid NWB sessions dynamically, selects double-response exemplars,
and outputs panel SVGs per session prefix.
Usage:
  python scripts/suite_02_raster_s2_om2.py
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
import datetime
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.gridspec as gridspec
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from scipy.stats import friedmanchisquare

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
import omission as oa
from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS

READY_CSV = Path("artifacts/data/session_readiness.csv")
GRAND_TABLE_CSV = Path("outputs/classification/grand_unit_table_shuffle_sso.csv")
CONDITIONS = ["RRRR", "RXRR", "RRXR", "RRRX"]
WINDOW_MS = (-500.0, 4124.0)
N_TRIALS_SHOWN = 40

CLASS_COLORS = {"S++": "#1D9E75", "S--": "#993C1D", "O++": "#185FA5"}
EPOCH_SHADE_COLORS = {"p1": "#fcee21", "p2": "#93278f", "p3": "#019147", "p4": "#000bd4"}
EPOCH_SHADE_ALPHA = 0.15

EPOCH_LABELS = list(EPOCH_ONSETS_MS.keys()) + ["end"]
EPOCH_TIMES_MS = list(EPOCH_ONSETS_MS.values()) + [WINDOW_MS[1]]

def causal_exponential_smoothing(spike_times_rel: list[float], n_trials: int, window_ms: tuple[float, float], tau_ms: float = 30.0, bin_ms: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    t_start, t_stop = window_ms
    bins = np.arange(t_start, t_stop + bin_ms, bin_ms)
    counts, edges = np.histogram(spike_times_rel, bins=bins)
    bin_centers = (edges[:-1] + edges[1:]) / 2
    raw_rate = counts / (n_trials * (bin_ms / 1000.0))
    t_filter = np.arange(0, 5 * tau_ms, bin_ms)
    h = np.exp(-t_filter / tau_ms)
    h /= h.sum()
    padded_rate = np.concatenate([np.zeros(len(h) - 1), raw_rate])
    smoothed = np.convolve(padded_rate, h, mode="valid")
    return bin_centers, smoothed

def main():
    if not READY_CSV.exists() or not GRAND_TABLE_CSV.exists():
        print("Required CSV files do not exist.")
        return
        
    readiness = pd.read_csv(READY_CSV)
    grand = pd.read_csv(GRAND_TABLE_CSV)
    
    active_sessions = readiness[readiness["nwb_ok"].astype(bool) & readiness["sidecar_ok"].astype(bool)]
    print(f"Looping over {len(active_sessions)} valid sessions...")
    
    out_dir = REPO_ROOT / "outputs/publication_figures/suite_raster"
    out_dir.mkdir(parents=True, exist_ok=True)
    dt_suffix = datetime.datetime.now().strftime("%y%m%d")

    for _, row in active_sessions.iterrows():
        stem = row["stem"]
        path = row["nwb_path"]
        prefix = row["session_prefix"]
        
        sub = grand[grand["nwb_stem"] == stem]
        if len(sub) == 0:
            continue
            
        # Select S++, S--, O++ units based on classification categories
        s_plus_candidates = sub[sub["is_s_plus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        s_minus_candidates = sub[sub["is_s_minus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        o_plus_candidates = sub[sub["is_o_plus"] & (sub["firing_rate"] > 1.0)].sort_values("firing_rate", ascending=False)
        
        if len(s_plus_candidates) == 0 or len(s_minus_candidates) == 0 or len(o_plus_candidates) == 0:
            s_plus_candidates = sub[sub["display_class"] == "S+"].sort_values("firing_rate", ascending=False)
            s_minus_candidates = sub[sub["display_class"] == "S-"].sort_values("firing_rate", ascending=False)
            o_plus_candidates = sub[sub["display_class"] == "O+"].sort_values("firing_rate", ascending=False)
            
        if len(s_plus_candidates) == 0 or len(s_minus_candidates) == 0 or len(o_plus_candidates) == 0:
            print(f"Skipping {prefix}: missing candidates for S++ ({len(s_plus_candidates)}), S-- ({len(s_minus_candidates)}), or O++ ({len(o_plus_candidates)})")
            continue
            
        # Sort or map to second best or distinct unit to represent S++, S--, O++
        s_plus_uid = int(s_plus_candidates.iloc[min(1, len(s_plus_candidates)-1)]["unit_id"])
        s_minus_uid = int(s_minus_candidates.iloc[min(1, len(s_minus_candidates)-1)]["unit_id"])
        o_plus_uid = int(o_plus_candidates.iloc[min(1, len(o_plus_candidates)-1)]["unit_id"])
        
        units = {"S++": s_plus_uid, "S--": s_minus_uid, "O++": o_plus_uid}
        
        # Select highly stable, high-firing exemplars for the visual showcase session
        if prefix == "sub-C31o_ses-230823":
            # KS ID 208 is S++ (firing rate ~25Hz), KS ID 238 is S-- (firing rate ~19Hz), KS ID 49 is O++ (~15Hz)
            units = {
                "S++": 208,
                "S--": 238,
                "O++": 49
            }
            
        print(f"Processing {prefix} with units S++={units['S++']}, S--={units['S--']}, O++={units['O++']}")
        
        try:
            sess = oa.read(path)
        except Exception as e:
            print(f"Failed to load NWB {path}: {e}")
            continue
            
        onsets_by_cond = {}
        for cond in CONDITIONS:
            epochs = sess.get_epochs(phase=2, condition=cond, correct_only=True)
            onsets_by_cond[cond] = epochs["start_time"].values

        fig = plt.figure(figsize=(14, 16))
        outer_gs = gridspec.GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.25)
        
        for row_idx, cond in enumerate(CONDITIONS):
            onsets = onsets_by_cond[cond]
            for col_idx, (cls, uid) in enumerate(units.items()):
                inner_gs = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer_gs[row_idx, col_idx], height_ratios=[3, 1], hspace=0.08)
                ax_raster = fig.add_subplot(inner_gs[0])
                ax_psth = fig.add_subplot(inner_gs[1], sharex=ax_raster)
                
                spike_times = sess.get_spike_times(uid)
                win_s = (WINDOW_MS[0] / 1000.0, WINDOW_MS[1] / 1000.0)
                
                for label, t_start in EPOCH_ONSETS_MS.items():
                    if label in EPOCH_SHADE_COLORS:
                        idx = EPOCH_LABELS.index(label)
                        t_stop = EPOCH_TIMES_MS[idx + 1]
                        ax_raster.axvspan(t_start, t_stop, color=EPOCH_SHADE_COLORS[label], alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
                        ax_psth.axvspan(t_start, t_stop, color=EPOCH_SHADE_COLORS[label], alpha=EPOCH_SHADE_ALPHA, zorder=0, linewidth=0)
                
                all_spike_times_rel = []
                trial_idx = 0
                p1_rates = []
                p2_rates = []
                p3_rates = []
                
                for onset in onsets[:N_TRIALS_SHOWN]:
                    lo, hi = onset + win_s[0], onset + win_s[1]
                    mask = (spike_times >= lo) & (spike_times < hi)
                    rel_ms = (spike_times[mask] - onset) * 1000.0
                    all_spike_times_rel.extend(rel_ms)
                    ax_raster.vlines(rel_ms, trial_idx + 0.05, trial_idx + 0.95, color="black", linewidth=0.6, zorder=2)
                    trial_idx += 1
                    
                    p1_spk = np.sum((rel_ms >= 0.0) & (rel_ms < 531.0))
                    p2_spk = np.sum((rel_ms >= 1031.0) & (rel_ms < 1562.0))
                    p3_spk = np.sum((rel_ms >= 2062.0) & (rel_ms < 2593.0))
                    p1_rates.append(p1_spk)
                    p2_rates.append(p2_spk)
                    p3_rates.append(p3_spk)
                    
                if len(onsets) > 0 and len(all_spike_times_rel) > 0:
                    bin_centers, afr = causal_exponential_smoothing(all_spike_times_rel, len(onsets[:N_TRIALS_SHOWN]), WINDOW_MS, tau_ms=30.0)
                    ax_psth.plot(bin_centers, afr, color=CLASS_COLORS[cls], linewidth=1.2, zorder=3)
                    ax_psth.fill_between(bin_centers, 0, afr, color=CLASS_COLORS[cls], alpha=0.15, zorder=2)
                    
                    try:
                        stat, p_val = friedmanchisquare(p1_rates, p2_rates, p3_rates)
                        ax_psth.text(0.05, 0.8, f"Fr-p={p_val:.4f}", transform=ax_psth.transAxes, fontsize=8, color="#333333")
                    except ValueError:
                        pass

                ax_raster.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
                ax_raster.set_ylim(0, N_TRIALS_SHOWN)
                ax_raster.invert_yaxis()
                ax_raster.xaxis.set_tick_params(labelbottom=False)
                ax_raster.yaxis.set_major_locator(MaxNLocator(integer=True, nbins=4))
                ax_raster.grid(True, which="both", axis="x", linestyle=":", linewidth=0.5, alpha=0.5)

                ax_psth.set_xlim(WINDOW_MS[0], WINDOW_MS[1])
                ax_psth.set_ylim(0, 50)
                ax_psth.yaxis.set_major_locator(MaxNLocator(nbins=3))
                ax_psth.grid(True, which="both", axis="x", linestyle=":", linewidth=0.5, alpha=0.5)
                
                if row_idx == 0:
                    ax_raster.set_title(f"{cls} Neuron (Unit {uid})", fontsize=11, fontweight="bold", color=CLASS_COLORS[cls])
                if col_idx == 0:
                    ax_raster.set_ylabel(f"{cond}\nTrials", fontsize=9, fontweight="bold")
                    ax_psth.set_ylabel("Hz", fontsize=8)
                if row_idx == 3:
                    ax_psth.set_xlabel("Time from trial onset (ms)", fontsize=9)

        svg_path = out_dir / f"{prefix}_suite_02_raster_s2_om2_{dt_suffix}.svg"
        fig.suptitle(f"Suite 02: S++ / S-- / O++ Raster & PSTH Grid — {prefix}", fontsize=14, fontweight="bold", y=0.96)
        fig.savefig(svg_path, bbox_inches="tight")
        plt.close(fig)
        print(f"Saved {svg_path}")

if __name__ == "__main__":
    main()
