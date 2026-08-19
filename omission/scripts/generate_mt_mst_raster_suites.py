#!/usr/bin/env python3
"""
Generate 4x4 PNG Raster Suite Figures for Top MT/MST S+ and S- Neurons.

Outputs:
  - outputs/raster_suites/mt_mst_splus/
  - outputs/raster_suites/mt_mst_sminus/
"""

from __future__ import annotations

import pathlib
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter1d

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa
from omission.jnwb_ext.unit_classification import precompute_condition_onsets
from omission.jnwb_ext.viz import get_sequence_onset_onsets, resample_onsets
from jnwb import paths as _P

# Directories
OUT_SPLUS_DIR = REPO_ROOT / "outputs" / "raster_suites" / "mt_mst_splus"
OUT_SMINUS_DIR = REPO_ROOT / "outputs" / "raster_suites" / "mt_mst_sminus"
OUT_SPLUS_DIR.mkdir(parents=True, exist_ok=True)
OUT_SMINUS_DIR.mkdir(parents=True, exist_ok=True)

# Constants
CONDS = ["RRRR", "RXRR", "RRXR", "RRRX"]
COND_COLORS = {
    "RRRR": "#333333",
    "RXRR": "#d62728",
    "RRXR": "#2ca02c",
    "RRRX": "#1f77b4",
}
EPOCH_ONSETS_MS = {
    "p1": 0.0,
    "d1": 531.0,
    "p2": 1031.0,
    "d2": 1562.0,
    "p3": 2062.0,
    "d3": 2593.0,
    "p4": 3093.0,
    "d4": 3624.0,
}
WIN = (-500.0, 4124.0)
BIN_SIZE = 20.0  # ms


def compute_psth(spikes: np.ndarray, onsets: np.ndarray, win: tuple[float, float], sigma: float = 2.0):
    if len(onsets) == 0:
        bins = np.arange(win[0], win[1] + BIN_SIZE, BIN_SIZE)
        centers = 0.5 * (bins[:-1] + bins[1:])
        return centers, np.zeros_like(centers), np.zeros_like(centers)

    bins = np.arange(win[0], win[1] + BIN_SIZE, BIN_SIZE)
    centers = 0.5 * (bins[:-1] + bins[1:])
    counts = np.zeros((len(onsets), len(centers)))

    st = np.sort(spikes)
    for i, onset in enumerate(onsets):
        t_start = (onset + win[0] / 1000.0)
        t_end = (onset + win[1] / 1000.0)
        idx_start = np.searchsorted(st, t_start, side="left")
        idx_end = np.searchsorted(st, t_end, side="right")
        rel_spikes = (st[idx_start:idx_end] - onset) * 1000.0

        c, _ = np.histogram(rel_spikes, bins=bins)
        counts[i] = c / (BIN_SIZE / 1000.0)  # Hz

    mean = np.mean(counts, axis=0)
    sem = np.std(counts, axis=0) / np.sqrt(len(onsets)) if len(onsets) > 1 else np.zeros_like(mean)

    if sigma > 0:
        mean = gaussian_filter1d(mean, sigma=sigma)
        sem = gaussian_filter1d(sem, sigma=sigma)

    return centers, mean, sem


def render_mt_mst_raster_suite(
    session,
    session_stem: str,
    unit_row_idx: int,
    rank_idx: int,
    cell_type: str,
    r_val: float,
    p_val: float,
    out_dir: pathlib.Path,
    target_n_trials: int = 100,
):
    units_df = session.get_units()
    unit_row = units_df.iloc[unit_row_idx]
    unit_id = unit_row.get("unit_id", unit_row_idx)
    area = unit_row.get("area", "MT/MST")
    quality = unit_row.get("quality", "stable")

    spikes = session.get_spike_times(unit_row_idx)

    # Gather condition sequence onset epochs (P1 onset, phase=2)
    raw_onsets_dict = precompute_condition_onsets(session, correct_only=True)
    plot_onsets_dict = {}
    for cond in CONDS:
        raw_onsets = raw_onsets_dict.get(cond, np.array([]))
        plot_onsets_dict[cond] = resample_onsets(raw_onsets, target_n=target_n_trials, random_state=42)

    fig, axes = plt.subplots(5, 1, figsize=(10, 9), sharex=True, gridspec_kw={"height_ratios": [1, 1, 1, 1, 1.8]}, dpi=300)
    fig.patch.set_facecolor("#ffffff")

    title_str = (
        f"MT/MST {cell_type} Rank #{rank_idx:02d} — Area: {area} | Session: {session_stem}\n"
        f"Unit Row: {unit_row_idx} (ID: {unit_id}) | Tag: {quality} | r_{cell_type}: {r_val:.3f} (p={p_val:.2e})"
    )
    fig.suptitle(title_str, fontsize=11, fontweight="bold", y=0.97)

    # Plot 4 raster rows (all exactly target_n_trials rows)
    for row_idx, cond in enumerate(CONDS):
        ax = axes[row_idx]
        ax.set_facecolor("#ffffff")
        onsets = plot_onsets_dict[cond]
        n_trials = len(onsets)

        # Draw shaded epoch backgrounds
        ax.axvspan(EPOCH_ONSETS_MS["p1"], EPOCH_ONSETS_MS["d1"], color="#fff2cc", alpha=0.5, zorder=0)  # P1
        ax.axvspan(EPOCH_ONSETS_MS["p2"], EPOCH_ONSETS_MS["d2"], color="#fce5cd", alpha=0.5, zorder=0)  # P2
        ax.axvspan(EPOCH_ONSETS_MS["p3"], EPOCH_ONSETS_MS["d3"], color="#d9ead3", alpha=0.5, zorder=0)  # P3
        ax.axvspan(EPOCH_ONSETS_MS["p4"], EPOCH_ONSETS_MS["d4"], color="#d9d2e9", alpha=0.5, zorder=0)  # P4

        # Red dashed line for omission slot
        if cond == "RXRR":
            ax.axvline(EPOCH_ONSETS_MS["p2"], color="red", ls="--", lw=1.5, zorder=4)
            ax.text(EPOCH_ONSETS_MS["p2"] - 20, target_n_trials * 0.85, "Omit", color="red", fontsize=8, fontweight="bold", ha="right")
        elif cond == "RRXR":
            ax.axvline(EPOCH_ONSETS_MS["p3"], color="red", ls="--", lw=1.5, zorder=4)
            ax.text(EPOCH_ONSETS_MS["p3"] - 20, target_n_trials * 0.85, "Omit", color="red", fontsize=8, fontweight="bold", ha="right")
        elif cond == "RRRX":
            ax.axvline(EPOCH_ONSETS_MS["p4"], color="red", ls="--", lw=1.5, zorder=4)
            ax.text(EPOCH_ONSETS_MS["p4"] - 20, target_n_trials * 0.85, "Omit", color="red", fontsize=8, fontweight="bold", ha="right")

        # Raster spikes
        st = np.sort(spikes)
        for trial_i, onset in enumerate(onsets):
            t_start = (onset + WIN[0] / 1000.0)
            t_end = (onset + WIN[1] / 1000.0)
            idx_start = np.searchsorted(st, t_start, side="left")
            idx_end = np.searchsorted(st, t_end, side="right")
            rel_spikes = (st[idx_start:idx_end] - onset) * 1000.0

            ax.vlines(rel_spikes, trial_i, trial_i + 0.85, color="black", lw=0.6, zorder=3)

        ax.set_ylabel(f"{cond}\n(N={target_n_trials})", fontsize=8, fontweight="bold", color=COND_COLORS[cond])
        ax.set_ylim(0, target_n_trials)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    # Plot PSTH (linear scale)
    ax_psth = axes[4]
    ax_psth.set_facecolor("#ffffff")
    ax_psth.axvspan(EPOCH_ONSETS_MS["p1"], EPOCH_ONSETS_MS["d1"], color="#fff2cc", alpha=0.5, zorder=0)
    ax_psth.axvspan(EPOCH_ONSETS_MS["p2"], EPOCH_ONSETS_MS["d2"], color="#fce5cd", alpha=0.5, zorder=0)
    ax_psth.axvspan(EPOCH_ONSETS_MS["p3"], EPOCH_ONSETS_MS["d3"], color="#d9ead3", alpha=0.5, zorder=0)
    ax_psth.axvspan(EPOCH_ONSETS_MS["p4"], EPOCH_ONSETS_MS["d4"], color="#d9d2e9", alpha=0.5, zorder=0)

    for slot in ("p1", "p2", "p3", "p4"):
        ax_psth.axvline(EPOCH_ONSETS_MS[slot], color="gray", ls="--", lw=0.7, zorder=4)

    max_rate = 5.0
    for cond in CONDS:
        onsets = raw_onsets_dict.get(cond, np.array([]))
        centers, mean, sem = compute_psth(spikes, onsets, WIN)
        c = COND_COLORS[cond]

        ax_psth.plot(centers, mean, color=c, lw=1.5, zorder=3, label=cond)
        ax_psth.fill_between(centers, np.maximum(mean - sem, 0), mean + sem, color=c, alpha=0.20, linewidth=0, zorder=2)
        if len(mean) > 0:
            max_rate = max(max_rate, float(np.max(mean + sem)))

    ax_psth.set_ylim(bottom=0.0, top=max_rate * 1.15)
    ax_psth.set_xlim(WIN)

    ticks = [-500.0, 0.0, 531.0, 1031.0, 1562.0, 2062.0, 2593.0, 3093.0, 3624.0, 4124.0]
    labels = ["-500ms - fx", "0ms - p1", "531ms - d1", "1031ms - p2", "1562ms - d2",
              "2062ms - p3", "2593ms - d3", "3093ms - p4", "3624ms - d4", "4124ms - end"]

    ax_psth.set_xticks(ticks)
    ax_psth.set_xticklabels(labels, rotation=45, fontsize=7, ha="right")
    ax_psth.set_ylabel("Rate (Hz)", fontsize=8, fontweight="bold")
    ax_psth.legend(fontsize=7, loc="upper right", frameon=True, facecolor="white", edgecolor="none")

    for s in ("top", "right"):
        ax_psth.spines[s].set_visible(False)

    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])

    fn = f"mt_mst_{cell_type.lower()}_rank{rank_idx:02d}_{session_stem}_row{unit_row_idx}_{area}_r{r_val:.3f}.png"
    out_path = out_dir / fn
    fig.savefig(out_path, dpi=300, facecolor="#ffffff", edgecolor="none")
    plt.close(fig)

    print(f"Saved MT/MST raster suite PNG: {fn}")
    return out_path


def main():
    nwb_dir = pathlib.Path(_P.nwb_dir())
    csv_path = REPO_ROOT / "outputs" / "classification" / "mt_mst_top_s_plus_s_minus_units.csv"
    df = pd.read_csv(csv_path)

    # Top 5 S+
    df_splus = df[df["cell_type"] == "S+"].sort_values(by="r_Splus", ascending=False).head(5)
    # Top 5 S-
    df_sminus = df[df["cell_type"] == "S-"].sort_values(by="r_Sminus", ascending=False).head(5)

    # Render S+ suites
    session_cache = {}
    for rank_idx, (idx, r) in enumerate(df_splus.iterrows(), 1):
        stem = r["session_prefix"]
        if stem not in session_cache:
            nwb_path = nwb_dir / f"{stem}.nwb"
            if not nwb_path.exists():
                nwb_path = nwb_dir / f"{stem}_rec.nwb"
            session_cache[stem] = oa.read(nwb_path)

        render_mt_mst_raster_suite(
            session=session_cache[stem],
            session_stem=stem,
            unit_row_idx=int(r["unit_row_idx"]),
            rank_idx=rank_idx,
            cell_type="S+",
            r_val=float(r["r_Splus"]),
            p_val=float(r["p_Splus"]),
            out_dir=OUT_SPLUS_DIR,
        )

    # Render S- suites
    for rank_idx, (idx, r) in enumerate(df_sminus.iterrows(), 1):
        stem = r["session_prefix"]
        if stem not in session_cache:
            nwb_path = nwb_dir / f"{stem}.nwb"
            if not nwb_path.exists():
                nwb_path = nwb_dir / f"{stem}_rec.nwb"
            session_cache[stem] = oa.read(nwb_path)

        render_mt_mst_raster_suite(
            session=session_cache[stem],
            session_stem=stem,
            unit_row_idx=int(r["unit_row_idx"]),
            rank_idx=rank_idx,
            cell_type="S-",
            r_val=float(r["r_Sminus"]),
            p_val=float(r["p_Sminus"]),
            out_dir=OUT_SMINUS_DIR,
        )

    print("\nAll MT/MST S+ and S- raster suites generated cleanly.")


if __name__ == "__main__":
    main()
