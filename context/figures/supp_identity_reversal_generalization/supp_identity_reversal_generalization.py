"""Supplement: FEF / V3a-d expected-identity reversal-generalization decodability.

Draws the signed, time-resolved population decodability trace for the ONLY two areas that pass
the p2+p3-train / p4-test cross-position generalization test for the omitted stimulus's expected
identity (scripts/decode_identity_sliding_window.py analysis="reversal_generalization",
aggregated by scripts/aggregate_identity_clusters.py). Every other area (V1-V4, MT, TEO, PFC,
MST+FST) is null on this specific test -- see
outputs/classification/identity_decoding_latency_by_area.csv.

Curve = mean out-of-fold sign(decision score) among true-label-A test trials, +1 = always
predicted A, -1 = always predicted B, 0 = chance. Shaded band = null distribution's per-bin
[5th, 95th] percentile (500 within-block permutations per cell, averaged across sessions).
Red marker = a cluster-permutation-significant bin/run (cluster mass vs the null draws' own
max-cluster-mass distribution, p<0.05); bins before t=0 are excluded from the search by
construction (a slot's identity cannot be decodable before that slot's own onset -- the same
fix applied to the omission-onset latency analysis, 2026-08-13).

This is a real-data supplement of an exploratory, single-pass, uncorrected-across-cells analysis
(27 area x analysis cells tested at nominal cluster alpha=0.05, no family-level correction) --
the caption states this and the bootstrap onset-stability numbers explicitly, because both
significant clusters here are small (1-2 bins) and only found in a minority of session
bootstrap resamples.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "context" / "figures"))

import figstyle
from scripts.aggregate_identity_clusters import load_cells, group_curve_and_null, cluster_test

MANIFEST_CSV = REPO_ROOT / "outputs/classification/identity_sliding_window/cell_manifest.csv"
FIG_DIR = Path(__file__).resolve().parent
SVG_DIR = FIG_DIR / "svg"

AREAS = ["FEF", "V3a/d"]
AREA_MERGE = {"MST": "MST+FST", "FST": "MST+FST", "V3a": "V3a/d", "V3d": "V3a/d"}
ANALYSIS = "reversal_generalization"
BIN_HALF_MS = 12.5  # decode_identity_sliding_window.BIN_MS / 2, for cluster-span shading


def main():
    import pandas as pd

    figstyle.use_house_style()
    manifest = pd.read_csv(MANIFEST_CSV)
    cells_raw = load_cells(manifest)

    merged = {}
    for (raw_area, analysis), cell_list in cells_raw.items():
        if analysis != ANALYSIS:
            continue
        area_m = AREA_MERGE.get(raw_area, raw_area)
        merged.setdefault(area_m, []).extend(cell_list)

    fig, axes = plt.subplots(1, 2, figsize=(9.5, 4.2), gridspec_kw=dict(wspace=0.35, bottom=0.16, top=0.78, left=0.09, right=0.98))

    # At p4 (the only test slot in this design), preceding_identity is the exact complement of
    # expected_identity (the Milestone 1 reversal-design invariant, enforced/checked in
    # jnwb.structured_identity_m2a). So true-label=A test trials ARE preceding=B trials, and
    # true-label=B test trials ARE preceding=A trials -- curve_A below IS the X|B trace and
    # curve_B IS the X|A trace; no separate re-decode is needed to get this split.
    for ax, area in zip(axes, AREAS):
        cell_list = merged[area]
        ctr, obs_a, null_a = group_curve_and_null(cell_list, "a")
        _, obs_b, null_b = group_curve_and_null(cell_list, "b")
        res_a = cluster_test(ctr, obs_a, null_a, sign=1)
        res_b = cluster_test(ctr, obs_b, null_b, sign=-1)

        lo_a, hi_a = np.percentile(null_a, 5, axis=0), np.percentile(null_a, 95, axis=0)
        lo_b, hi_b = np.percentile(null_b, 5, axis=0), np.percentile(null_b, 95, axis=0)
        color = figstyle.AREA_COLORS.get(area, "#333333")

        ax.axvspan(ctr.min() - 5, 0, color="#DDDDDD", alpha=0.6, zorder=0)
        ax.fill_between(ctr, lo_a, hi_a, color=color, alpha=0.15, lw=0, zorder=1)
        ax.fill_between(ctr, lo_b, hi_b, color="#888888", alpha=0.20, lw=0, zorder=1)
        ax.axhline(0, color="black", lw=0.6, zorder=2)
        ax.axvline(0, color=figstyle.ONSET_COLOR, ls="--", lw=1.2, zorder=2)
        ax.plot(ctr, obs_a, color=color, lw=1.9, zorder=3, label="X|B  (predict A, preceding=B)")
        ax.plot(ctr, obs_b, color="#666666", lw=1.5, ls="--", zorder=3, label="X|A  (predict B, preceding=A)")

        n_sig_a = n_sig_b = 0
        for c in res_a["clusters"]:
            if c["significant"]:
                n_sig_a += 1
                span0, span1 = c["start_ms"] - BIN_HALF_MS, c["end_ms"] + BIN_HALF_MS
                ax.axvspan(span0, span1, color="#D62728", alpha=0.22, zorder=1)
                ax.plot([(c["start_ms"] + c["end_ms"]) / 2], [1.02], marker="v", color="#D62728",
                        markersize=6, clip_on=False, zorder=4)
                ax.text((c["start_ms"] + c["end_ms"]) / 2, 1.10, f"p={c['p_cluster']:.3f}",
                        ha="center", va="bottom", fontsize=6.5, color="#D62728", clip_on=False)
        for c in res_b["clusters"]:
            n_sig_b += int(c["significant"])

        ax.set_ylim(-1.05, 1.25)
        ax.set_xlim(ctr.min(), ctr.max())
        ax.set_xlabel("time from omitted slot's own onset (ms)")
        ax.set_ylabel("signed decodability index\n(+1 = A, -1 = B, 0 = chance)")
        ax.set_title(f"{area}   X|B: {n_sig_a} sig. cluster{'s' if n_sig_a != 1 else ''}"
                     f"   /   X|A: {n_sig_b} sig. cluster{'s' if n_sig_b != 1 else ''}", fontsize=9)
        ax.legend(loc="lower right", fontsize=6.5, framealpha=0.9)

    fig.suptitle("Reversal-generalization decoding of the omitted stimulus's expected identity: X|A vs X|B",
                 fontsize=10.5, y=0.97)
    fig.text(0.5, 0.885,
             "train p2+p3, test p4  --  effect is entirely in X|B; X|A is null in both areas  --  "
             "uncorrected across 27 cells: FEF p_holm=1.0, q_BH=0.14; V3a/d best p_holm=1.0, q_BH=0.090",
             ha="center", va="top", fontsize=7.2, color="#444444")

    figstyle.save(fig, str(FIG_DIR), "supp_identity_reversal_generalization")
    plt.close(fig)
    print("wrote", FIG_DIR / "supp_identity_reversal_generalization.svg")


if __name__ == "__main__":
    main()
