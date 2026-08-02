#!/usr/bin/env python3
"""
Generate 4x4 raster suite PNG figures for top O++ conjunction neurons (omission > control AND omission > P1-D1).

Output Directory:
  outputs/raster_suites/oplusplus/
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
from jnwb.sequence_layout import EPOCH_ONSETS_MS, FULL_SEQUENCE_END_MS
from jnwb.unit_classification import precompute_condition_onsets
from figstyle import FULL_TRIAL_WIN, full_trial_ticks, mark_full_trial_axis

OUTPUT_DIR = REPO_ROOT / "outputs" / "raster_suites" / "oplusplus"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OPLUSPLUS_CSV = REPO_ROOT / "outputs" / "classification" / "omission_oplusplus_grand_units.csv"

CONDS = ["RRRR", "RXRR", "RRXR", "RRRX"]
OMIT_SLOT = {"RRRR": None, "RXRR": 2, "RRXR": 3, "RRRX": 4}
COND_COLORS = {"RRRR": "#000000", "RXRR": "#DC2626", "RRXR": "#16A34A", "RRRX": "#2563EB"}
PSTH_BIN_MS = 20.0
RASTER_TRIALS = 40
WIN = FULL_TRIAL_WIN

def compute_psth(st, onsets, win_ms, bin_ms=PSTH_BIN_MS):
    edges = np.arange(win_ms[0], win_ms[1] + bin_ms, bin_ms)
    centers = edges[:-1] + bin_ms / 2.0
    if onsets.size == 0:
        return centers, np.zeros_like(centers), np.zeros_like(centers)
    counts = np.zeros((onsets.size, edges.size - 1))
    for i, t0 in enumerate(onsets):
        s = (st[(st >= t0 + win_ms[0] / 1000.0) & (st < t0 + win_ms[1] / 1000.0)] - t0) * 1000.0
        counts[i], _ = np.histogram(s, bins=edges)
    rate = counts / (bin_ms / 1000.0)
    mean = rate.mean(axis=0)
    sem = rate.std(axis=0, ddof=1) / np.sqrt(rate.shape[0]) if rate.shape[0] > 1 else np.zeros_like(mean)
    return centers, mean, sem

def render_unit_raster_suite(rank_idx, row, save_path):
    stem = str(row["session"]).replace("_rec", "")
    unit_row = int(row["unit_row"])
    
    nwb_path = pathlib.Path(r"D:\analysis\nwb") / f"{stem}_rec.nwb"
    if not nwb_path.exists():
        nwb_path = pathlib.Path(r"D:\analysis\nwb") / f"{stem}.nwb"
    
    session = oa.read(nwb_path)
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
        
    pct = row.get("likelihood_pct", 100.0)
    area = row.get("area", "unknown")
    u_id = row.get("unit_id", unit_row)
    q_tag = row.get("quality_tag", "single-stable")
    wf_type = row.get("waveform_type", "slow")
    omit_hz = row.get("omission_rate_hz", 0.0)
    p1d1_hz = row.get("p1_d1_rate_hz", 0.0)
    diff_p1d1 = row.get("omission_vs_p1_d1_diff_hz", 0.0)
    pval_p1d1 = row.get("omission_vs_p1_d1_pval", 1.0)
    
    title_str = (
        f"O++ Conjunction Rank #{rank_idx} ({pct:.2f}% Corpus Rank) — Area: {area} | Session: {stem}\n"
        f"Unit Row: {unit_row} (ID: {u_id}) | Tag: {q_tag} [{wf_type}] | "
        f"Omission: {omit_hz:.2f} Hz vs P1-D1: {p1d1_hz:.2f} Hz (Δ: +{diff_p1d1:.2f} Hz, p={pval_p1d1:.2e})"
    )
    fig.suptitle(title_str, fontsize=10, fontweight="bold", y=0.98)
    
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(save_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved O++ raster suite PNG: {save_path.name}")

def main():
    if not OPLUSPLUS_CSV.exists():
        print(f"Error: {OPLUSPLUS_CSV} not found.")
        return
        
    df = pd.read_csv(OPLUSPLUS_CSV)
    print(f"Loaded {len(df)} O++ conjunction units.")
    
    top_candidates = df.head(10)
    for idx, row in top_candidates.iterrows():
        rank = idx + 1
        stem = str(row["session"]).replace("_rec", "")
        u_row = int(row["unit_row"])
        area = str(row["area"])
        
        filename = f"oplusplus_rank{rank:02d}_{stem}_row{u_row}_{area}.png"
        out_path = OUTPUT_DIR / filename
        render_unit_raster_suite(rank, row, out_path)
        
    print(f"\nAll top 10 O++ raster suites generated in {OUTPUT_DIR}.")

if __name__ == "__main__":
    main()
