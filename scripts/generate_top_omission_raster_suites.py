#!/usr/bin/env python3
"""
Generate 4x4 raster suite figures for top omission-excited neurons from omission_likelihood_grand_units.csv.

Each raster suite figure displays:
  - 4 condition rows: RRRR (intact control), RXRR (slot 2 omission), RRXR (slot 3 omission), RRRX (slot 4 omission)
  - Full sequence time axis (-500 to +4124 ms) with p1-p4 presentation epoch background shading and "Omit" red dashed markers
  - Bottom panel: PSTH mean firing rate traces (Hz, 20 ms bins ± SEM) overlaying all 4 conditions
  - Metadata header: Session, Unit Row, Unit ID, Area, Quality Tag, Waveform Type, Omission Rate, Likelihood Rank

Output Directory:
  outputs/raster_suites/
"""

from __future__ import annotations

import os
import sys
import pathlib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

import jnwb as oa
from jnwb.sequence_layout import EPOCH_ONSETS_MS, FULL_SEQUENCE_END_MS, EPOCH_ORDER
from jnwb.unit_classification import precompute_condition_onsets
from jnwb.viz import raster_psth as _raster_psth
from figstyle import FULL_TRIAL_WIN, full_trial_ticks, mark_full_trial_axis
from jnwb import paths as _P

OUTPUT_DIR = REPO_ROOT / "outputs" / "raster_suites"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GRAND_CSV = REPO_ROOT / "outputs" / "classification" / "omission_likelihood_grand_units.csv"

CONDS = ["RRRR", "RXRR", "RRXR", "RRRX"]
OMIT_SLOT = {"RRRR": None, "RXRR": 2, "RRXR": 3, "RRRX": 4}
COND_COLORS = {"RRRR": "#000000", "RXRR": "#DC2626", "RRXR": "#16A34A", "RRRX": "#2563EB"}
PSTH_BIN_MS = 20.0
RASTER_TRIALS = 40
WIN = FULL_TRIAL_WIN  # (-500, 4124)

def compute_psth(st, onsets, win_ms, bin_ms=PSTH_BIN_MS):
    """Thin wrapper over jnwb.viz.raster_psth preserving this file's PSTH_BIN_MS=20.0 default
    (jnwb.viz.raster_psth's own default is 10.0 -- explicit here so the swap is not a silent
    behavior change)."""
    return _raster_psth(st, onsets, win_ms, bin_ms=bin_ms)

def render_unit_raster_suite(session_stem, unit_row, unit_info, save_path):
    session = oa.read(_P.resolve_nwb_path(session_stem))
    onsets_dict = precompute_condition_onsets(session)
    spikes = session.get_spike_times(unit_row)
    if spikes is None:
        spikes = np.array([])
    else:
        spikes = np.sort(spikes)
        
    fig, axes = plt.subplots(
        len(CONDS) + 1, 1, figsize=(7.5, 6.8),
        gridspec_kw={"hspace": 0.18, "height_ratios": [1, 1, 1, 1, 1.1]},
        facecolor="white"
    )
    
    ticks, labels = full_trial_ticks()
    
    # 4 Condition Rasters
    for ri, cond in enumerate(CONDS):
        ax = axes[ri]
        ax.set_facecolor("white")
        slot = OMIT_SLOT[cond]
        mark_full_trial_axis(ax, WIN, omit_slot=slot)
        
        onsets = onsets_dict.get(cond, np.array([]))
        if onsets.size == RASTER_TRIALS:
            show = onsets
        elif onsets.size > RASTER_TRIALS:
            show = onsets[np.linspace(0, onsets.size - 1, RASTER_TRIALS).astype(int)]
        else:
            show = onsets
            
        for i, t0 in enumerate(show):
            s = (spikes[(spikes >= t0 + WIN[0] / 1000.0) & (spikes < t0 + WIN[1] / 1000.0)] - t0) * 1000.0
            ax.plot(s, np.full(s.size, i), "|", color="black", ms=3.0, mew=0.7, zorder=3)
            
        ax.set_ylim(-0.5, RASTER_TRIALS + 0.5)
        ax.set_ylabel(cond, fontsize=9, fontweight="bold", color=COND_COLORS[cond])
        ax.set_xticks(ticks)
        ax.tick_params(axis="x", top=False, labeltop=False, bottom=False, labelbottom=False)
        ax.tick_params(axis="y", labelsize=7)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
            
    # PSTH Bottom Panel
    ax_psth = axes[-1]
    ax_psth.set_facecolor("white")
    mark_full_trial_axis(ax_psth, WIN, omit_slot=None)
    for slot in ("p1", "p2", "p3", "p4"):
        ax_psth.axvline(EPOCH_ONSETS_MS[slot], color="gray", ls="--", lw=0.7, zorder=4)
        
    for cond in CONDS:
        onsets = onsets_dict.get(cond, np.array([]))
        centers, mean, sem = compute_psth(spikes, onsets, WIN)
        c = COND_COLORS[cond]
        ax_psth.plot(centers, mean, color=c, lw=1.5, zorder=3, label=cond)
        ax_psth.fill_between(centers, mean - sem, mean + sem, color=c, alpha=0.20, linewidth=0, zorder=2)
        
    ax_psth.set_xlim(WIN)
    ax_psth.set_xticks(ticks)
    ax_psth.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
    ax_psth.set_ylabel("Rate (Hz)", fontsize=8, fontweight="bold")
    ax_psth.legend(fontsize=7, loc="upper right", frameon=True, facecolor="white", edgecolor="none")
    for s in ("top", "right"):
        ax_psth.spines[s].set_visible(False)
        
    # Title & Metadata
    pct = unit_info.get("likelihood_pct", 100.0)
    area = unit_info.get("area", "unknown")
    u_id = unit_info.get("unit_id", unit_row)
    q_tag = unit_info.get("quality_tag", "single-stable")
    wf_type = unit_info.get("waveform_type", "slow")
    diff_hz = unit_info.get("omission_diff_hz", 0.0)
    ratio = unit_info.get("omission_ratio", 1.0)
    
    title_str = (
        f"Unit Rank #{unit_info.name + 1} ({pct:.2f}% Likelihood) — Area: {area} | Session: {session_stem}\n"
        f"Unit Row: {unit_row} (ID: {u_id}) | Tag: {q_tag} [{wf_type}] | "
        f"Omission Δ: +{diff_hz:.2f} Hz ({ratio:.2f}x control)"
    )
    fig.suptitle(title_str, fontsize=10, fontweight="bold", y=0.98)
    
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved raster suite PNG: {save_path.name}")

def main():
    if not GRAND_CSV.exists():
        print(f"Error: {GRAND_CSV} not found.")
        return
        
    df = pd.read_csv(GRAND_CSV)
    print(f"Loaded {len(df)} units from grand likelihood table.")
    
    # Process top 10 candidates
    top_candidates = df.head(10)
    
    for idx, row in top_candidates.iterrows():
        rank = idx + 1
        stem = str(row["session"]).replace("_rec", "")
        u_row = int(row["unit_row"])
        area = str(row["area"])
        
        filename = f"top{rank:02d}_rank{row['likelihood_pct']:.1f}_{stem}_row{u_row}_{area}.png"
        out_path = OUTPUT_DIR / filename
        render_unit_raster_suite(stem, u_row, row, out_path)
        
    print(f"\nAll top 10 raster suites generated in {OUTPUT_DIR}.")

if __name__ == "__main__":
    main()
