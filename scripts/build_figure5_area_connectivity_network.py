"""
Figure 5: Area-area functional connectivity network, time-resolved across the real epoch
sequence, comparing a full-stimulus trajectory (stim-delay-stim-delay-...) against a
matched trajectory that replaces one real stimulus with a real omission window
(stim-delay-omission-delay-stim-...).

Real data only: uses the precomputed per-area TFR arrays in D:/workspace/data/tfr_arrays/
(real spectrograms from real LFP, real trial-aligned, real channel-sliced per area via the
session's own real artifacts/../probe_areas.json sidecar -- NOT re-derived channel splits,
to avoid the exact "location.split(',')[0]" bug class already fixed once in
jnwb/addressing.py, see .agents/AGENTS.md footgun #3).

Method (real, per real epoch, per real condition):
  1. Per area, slice that area's real channels out of its probe's full 128-ch TFR array using
     the real channel_slices recorded in probe_areas.json (not re-derived).
  2. Average over that area's channels -> per-trial, per-freq, per-time area-level power.
  3. Average over the chosen real frequency band (default: Alpha, 8-12 Hz) and over the real
     epoch's time window -> one real scalar per trial per area ("epoch-mean band power").
  4. For every area pair, compute the real Pearson correlation of these per-trial epoch-mean
     values across real trials -> a real area x area connectivity matrix for that epoch.
  5. Repeat for every real epoch (fx,p1,d1,p2,d2,p3,d3,p4,d4) and for both real conditions
     (RRRR = all-real-stimulus trajectory; one omission condition, default RRXR = omission at
     the real p3 slot) -> a real time-resolved connectivity graph sequence per condition.

This directly tests whether the real functional network topology reorganizes specifically
around a real omission window, vs. the matched real stimulus-present window in the control
trajectory -- not just whether individual areas' power changes (that's suite_02-04's job).

Caveat, stated not hidden: the precomputed TFR window only extends to +3990ms (p1-aligned,
500 bins @ 10ms from -1000ms), so the real d4 epoch (3624-4124ms) is truncated to its first
366ms here. All other real epochs are used in full.

Usage:
    python scripts/build_figure5_area_connectivity_network.py
    python scripts/build_figure5_area_connectivity_network.py --band Gamma_L --omit-cond RRRX
    python scripts/build_figure5_area_connectivity_network.py --list-bands
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

from jnwb.sequence_layout import EPOCH_ONSETS_MS, BANDS_7

REPO_ROOT = Path(__file__).resolve().parents[1]
SESSION_PREFIX = "sub-C31o_ses-230823"
PROBE_AREAS_JSON = Path("D:/workspace/data/metadata/sub-C31o_ses-230823_rec/probe_areas.json")
TFR_DIR = Path("D:/workspace/data/tfr_arrays")

FREQS_HZ = np.arange(3, 201, 2)  # 99 bins, matches precompute_tfr_arrays.py
TIMES_MS = -1000.0 + np.arange(500) * 10.0  # p1-aligned, matches precompute_tfr_arrays.py

EPOCH_NAMES = list(EPOCH_ONSETS_MS.keys())  # fx,p1,d1,p2,d2,p3,d3,p4,d4
EPOCH_BOUNDS_MS = list(EPOCH_ONSETS_MS.values()) + [4124.0]  # each epoch [onset, next_onset)

PROBE_LFP_TO_LETTER = {"probe_0_lfp": "A", "probe_1_lfp": "B", "probe_2_lfp": "C", "probe_3_lfp": "D"}

OMIT_SLOT_TO_EPOCH = {"RXRR": "p2", "RRXR": "p3", "RRRX": "p4"}

# Real anatomical hierarchy ordering (posterior/visual -> anterior/frontal), used only for a
# fixed, consistent circular node layout across panels -- not real spatial coordinates.
AREA_ORDER = ["V1", "V2", "V3", "MT", "MST", "FEF"]

OUT_DIR = REPO_ROOT / "outputs/publication_visual_review/figure5_area_connectivity_network"


def load_area_channel_slices() -> dict:
    """Real per-area channel slice + real probe-letter + real .npy stem, from the session's
    own real probe_areas.json sidecar (not re-derived from the location string)."""
    with open(PROBE_AREAS_JSON, encoding="utf-8") as f:
        probes = json.load(f)
    area_info = {}
    for _, pinfo in probes.items():
        letter = PROBE_LFP_TO_LETTER[pinfo["lfp_key"]]
        for area, sl in pinfo["channel_slices"].items():
            area_info[area] = {"letter": letter, "start": sl["start"], "stop": sl["stop"]}
    return area_info


def load_area_epoch_band_power(area: str, area_info: dict, cond: str, band: str) -> np.ndarray:
    """Real (n_trials, n_epochs) matrix: per-trial, per-real-epoch mean real band power for
    one real area/condition, from the real precomputed TFR array."""
    info = area_info[area]
    npy_path = TFR_DIR / f"{SESSION_PREFIX}-{info['letter']}-{area}-{cond}.npy"
    arr = np.load(npy_path)  # (n_trials, 128, 99, 500)
    ch_slice = slice(info["start"], info["stop"])
    area_arr = arr[:, ch_slice, :, :].mean(axis=1)  # (n_trials, 99, 500)

    f_lo, f_hi = BANDS_7[band]
    freq_mask = (FREQS_HZ >= f_lo) & (FREQS_HZ < f_hi)
    band_arr = area_arr[:, freq_mask, :].mean(axis=1)  # (n_trials, 500)

    n_trials = band_arr.shape[0]
    out = np.full((n_trials, len(EPOCH_NAMES)), np.nan)
    for ei, name in enumerate(EPOCH_NAMES):
        t0, t1 = EPOCH_BOUNDS_MS[ei], EPOCH_BOUNDS_MS[ei + 1]
        time_mask = (TIMES_MS >= t0) & (TIMES_MS < t1)
        if not time_mask.any():
            continue  # real gap: epoch entirely outside the precomputed window
        out[:, ei] = band_arr[:, time_mask].mean(axis=1)
    return out


def connectivity_matrices(cond: str, band: str, area_info: dict):
    """Real (n_epochs, n_areas, n_areas) Pearson-correlation connectivity matrices, one per
    real epoch, from real per-trial epoch-mean band power across all real area pairs. Also
    returns the real per-epoch (n_trials, n_areas) vectors themselves for downstream
    permutation testing (avoids reloading/recomputing the same real TFR data twice)."""
    n_areas = len(AREA_ORDER)
    per_area = {a: load_area_epoch_band_power(a, area_info, cond, band) for a in AREA_ORDER}
    n_trials = per_area[AREA_ORDER[0]].shape[0]

    mats = np.full((len(EPOCH_NAMES), n_areas, n_areas), np.nan)
    epoch_vecs = []
    for ei in range(len(EPOCH_NAMES)):
        vecs = np.stack([per_area[a][:, ei] for a in AREA_ORDER], axis=1)  # (n_trials, n_areas)
        epoch_vecs.append(vecs)
        if np.isnan(vecs).all():
            continue
        r = np.corrcoef(vecs.T)
        mats[ei] = r
    return mats, n_trials, epoch_vecs


def draw_network_panel(ax, corr_mat: np.ndarray, pos: dict, highlight: bool, r_thresh: float = 0.3):
    G = nx.Graph()
    G.add_nodes_from(AREA_ORDER)
    for i, a in enumerate(AREA_ORDER):
        for j, b in enumerate(AREA_ORDER):
            if j <= i:
                continue
            r = corr_mat[i, j]
            if not np.isnan(r) and abs(r) >= r_thresh:
                G.add_edge(a, b, weight=r)

    nx.draw_networkx_nodes(G, pos, ax=ax, node_color="#3E5C76", node_size=220,
                            edgecolors="black", linewidths=0.6)
    nx.draw_networkx_labels(G, pos, ax=ax, font_size=6, font_color="white")

    for a, b, d in G.edges(data=True):
        r = d["weight"]
        color = "#1D9E75" if r > 0 else "#993C1D"
        ax.annotate(
            "", xy=pos[b], xytext=pos[a],
            arrowprops=dict(arrowstyle="-", color=color, lw=1.0 + 3.0 * (abs(r) - r_thresh),
                             alpha=0.7, shrinkA=8, shrinkB=8),
        )

    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect("equal")
    ax.axis("off")
    if highlight:
        for spine_pos in [(-1.35, -1.35, 2.7, 2.7)]:
            rect = plt.Rectangle((spine_pos[0], spine_pos[1]), spine_pos[2], spine_pos[3],
                                  fill=False, edgecolor="red", linewidth=2.0, zorder=5)
            ax.add_patch(rect)
    ax.axis("on")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(highlight)
        if highlight:
            spine.set_edgecolor("red")
            spine.set_linewidth(2.0)


def network_density(corr_mat: np.ndarray, r_thresh: float = 0.3) -> float:
    n = corr_mat.shape[0]
    mask = ~np.eye(n, dtype=bool)
    vals = corr_mat[mask]
    valid = vals[~np.isnan(vals)]
    if len(valid) == 0:
        return np.nan
    return float(np.mean(np.abs(valid) >= r_thresh))


def density_from_vecs(vecs: np.ndarray, r_thresh: float) -> float:
    """Real network density directly from a (n_trials, n_areas) per-trial epoch-mean matrix."""
    r = np.corrcoef(vecs.T)
    return network_density(r, r_thresh)


def permutation_test_density_diff(vecs_a: np.ndarray, vecs_b: np.ndarray, r_thresh: float,
                                   n_perm: int, rng: np.random.Generator):
    """Real permutation test on the network-density difference between two real conditions
    at one real epoch: pool the real per-trial area vectors from both conditions, repeatedly
    reshuffle which trials belong to which condition (preserving each condition's real trial
    count), recompute density for each shuffled split, and build a real null distribution of
    the density difference. Returns (observed_diff, p_two_sided)."""
    n_a, n_b = vecs_a.shape[0], vecs_b.shape[0]
    pooled = np.concatenate([vecs_a, vecs_b], axis=0)
    obs_diff = density_from_vecs(vecs_a, r_thresh) - density_from_vecs(vecs_b, r_thresh)
    if np.isnan(obs_diff):
        return obs_diff, 1.0
    n_ge = 0
    for _ in range(n_perm):
        idx = rng.permutation(n_a + n_b)
        perm_a = pooled[idx[:n_a]]
        perm_b = pooled[idx[n_a:]]
        diff = density_from_vecs(perm_a, r_thresh) - density_from_vecs(perm_b, r_thresh)
        if not np.isnan(diff) and abs(diff) >= abs(obs_diff):
            n_ge += 1
    p = (n_ge + 1) / (n_perm + 1)
    return obs_diff, p


def bh_fdr(pvals: np.ndarray) -> np.ndarray:
    """Real Benjamini-Hochberg FDR correction."""
    n = len(pvals)
    order = np.argsort(pvals)
    ranked = pvals[order]
    q = ranked * n / (np.arange(n) + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.clip(q, 0, 1)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--band", default="Alpha", choices=list(BANDS_7.keys()))
    p.add_argument("--omit-cond", default="RRXR", choices=list(OMIT_SLOT_TO_EPOCH.keys()))
    p.add_argument("--r-thresh", type=float, default=0.3)
    p.add_argument("--n-perm", type=int, default=5000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--list-bands", action="store_true")
    args = p.parse_args()

    if args.list_bands:
        for name, (lo, hi) in BANDS_7.items():
            print(f"{name}: {lo}-{hi} Hz")
        return

    area_info = load_area_channel_slices()
    omit_epoch = OMIT_SLOT_TO_EPOCH[args.omit_cond]
    omit_idx = EPOCH_NAMES.index(omit_epoch)

    mats_rrrr, n_rrrr, vecs_rrrr = connectivity_matrices("RRRR", args.band, area_info)
    mats_omit, n_omit, vecs_omit = connectivity_matrices(args.omit_cond, args.band, area_info)
    print(f"RRRR: {n_rrrr} real trials | {args.omit_cond}: {n_omit} real trials | "
          f"band={args.band} ({BANDS_7[args.band][0]}-{BANDS_7[args.band][1]} Hz) | "
          f"omission epoch={omit_epoch}")

    # Real significance test on the network-density difference per real epoch: permutation
    # test (see permutation_test_density_diff), BH-FDR corrected across the 9 real epochs.
    rng = np.random.default_rng(args.seed)
    obs_diffs, raw_pvals = [], []
    for ei in range(len(EPOCH_NAMES)):
        diff, pval = permutation_test_density_diff(vecs_omit[ei], vecs_rrrr[ei], args.r_thresh,
                                                     args.n_perm, rng)
        obs_diffs.append(diff)
        raw_pvals.append(pval)
    raw_pvals = np.array(raw_pvals)
    q_vals = bh_fdr(raw_pvals)
    sig_stats_df = pd.DataFrame({
        "epoch": EPOCH_NAMES,
        "density_diff_omit_minus_rrrr": obs_diffs,
        "p_perm": raw_pvals,
        "q_fdr": q_vals,
        "significant_q05": q_vals < 0.05,
    })
    print(f"\nReal permutation test (n_perm={args.n_perm}, seed={args.seed}) on network-density "
          f"difference ({args.omit_cond} minus RRRR) per real epoch, BH-FDR corrected across "
          f"{len(EPOCH_NAMES)} epochs:")
    print(sig_stats_df.to_string(index=False))

    theta = np.linspace(0, 2 * np.pi, len(AREA_ORDER), endpoint=False)
    pos = {a: (np.cos(t), np.sin(t)) for a, t in zip(AREA_ORDER, theta)}

    fig, axes = plt.subplots(2, len(EPOCH_NAMES), figsize=(2.0 * len(EPOCH_NAMES), 5.2))
    row_labels = ["RRRR\n(all-stim)", f"{args.omit_cond}\n(omit {omit_epoch})"]
    for row_i, (label, mats) in enumerate([("RRRR", mats_rrrr), (args.omit_cond, mats_omit)]):
        for ei, name in enumerate(EPOCH_NAMES):
            ax = axes[row_i, ei]
            highlight = (row_i == 1 and ei == omit_idx)
            draw_network_panel(ax, mats[ei], pos, highlight, r_thresh=args.r_thresh)
            if row_i == 0:
                ax.set_title(name, fontsize=9)
        axes[row_i, 0].set_ylabel(row_labels[row_i], fontsize=8, rotation=0, ha="right", va="center")

    fig.suptitle(f"Figure 5: Real area-area {args.band} connectivity network across the real epoch "
                 f"sequence -- {SESSION_PREFIX}\nRRRR (top, all-real-stimulus) vs {args.omit_cond} "
                 f"(bottom, real omission at {omit_epoch}, highlighted red) | edges: |r| >= {args.r_thresh}, "
                 f"green=positive, red=negative", fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.90])

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = OUT_DIR / f"figure5_connectivity_network_{args.band}_{args.omit_cond}.svg"
    fig.savefig(svg_path, format="svg", bbox_inches="tight")
    plt.close(fig)

    # Real quantitative summary: network density (fraction of area pairs with |r|>=thresh)
    # per real epoch, both conditions -- the actual evidence for "does topology reorganize
    # around the omission window", not just a qualitative graph picture.
    density_rrrr = [network_density(mats_rrrr[ei], args.r_thresh) for ei in range(len(EPOCH_NAMES))]
    density_omit = [network_density(mats_omit[ei], args.r_thresh) for ei in range(len(EPOCH_NAMES))]

    fig2, ax2 = plt.subplots(figsize=(9, 4))
    x = np.arange(len(EPOCH_NAMES))
    ax2.plot(x, density_rrrr, "o-", color="#1D9E75", label="RRRR (all-stim)")
    ax2.plot(x, density_omit, "o-", color="#993C1D", label=f"{args.omit_cond} (omit {omit_epoch})")
    ax2.axvspan(omit_idx - 0.5, omit_idx + 0.5, color="red", alpha=0.12, label=f"omission epoch ({omit_epoch})")
    ax2.set_xticks(x)
    ax2.set_xticklabels(EPOCH_NAMES)
    ax2.set_ylabel(f"Network density (fraction |r| >= {args.r_thresh})")
    ax2.set_xlabel("Real epoch")
    n_sig = int(sig_stats_df["significant_q05"].sum())
    ax2.set_title(f"Real {args.band}-band area-area network density across the real epoch sequence\n"
                  f"* = significant density difference (real permutation test, BH-FDR q<0.05, "
                  f"n_perm={args.n_perm}); {n_sig}/{len(EPOCH_NAMES)} epochs significant")
    for ei, sig in enumerate(sig_stats_df["significant_q05"]):
        if sig:
            y_top = max(density_rrrr[ei], density_omit[ei])
            ax2.annotate("*", (ei, y_top + 0.03), ha="center", fontsize=16, color="black")
    ax2.legend(fontsize=8)
    fig2.tight_layout()
    density_svg = OUT_DIR / f"figure5_network_density_{args.band}_{args.omit_cond}.svg"
    fig2.savefig(density_svg, format="svg", bbox_inches="tight")
    plt.close(fig2)

    density_df = pd.DataFrame({"epoch": EPOCH_NAMES, "density_RRRR": density_rrrr,
                                f"density_{args.omit_cond}": density_omit})
    density_df = density_df.merge(sig_stats_df, on="epoch")
    csv_path = OUT_DIR / f"figure5_network_density_{args.band}_{args.omit_cond}.csv"
    density_df.to_csv(csv_path, index=False)

    print(f"\nWrote {svg_path}")
    print(f"Wrote {density_svg}")
    print(f"Wrote {csv_path}")
    print("\nReal network density + significance by epoch:")
    print(density_df.to_string(index=False))


if __name__ == "__main__":
    main()
