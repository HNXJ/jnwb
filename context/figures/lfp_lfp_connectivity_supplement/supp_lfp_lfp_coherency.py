r"""
LFP-LFP coupling matrices (area x area imaginary coherency) -- SUPPLEMENT to figure 5.

Demoted from main-figure status 2026-08-04: null at the group level (0/240 survive Holm-
Bonferroni in either window; see README). Figure 5 itself is now the directed Granger network
in fig05_lfp_lfp_coupling.py. This script and its outputs are retained as an honest
undirected-coupling supplement, not deleted -- the null result is itself informative.

Reads outputs/lfp_coupling_matrices/coupling.npz, built by
scripts/extract_lfp_coupling_matrices.py per the plan in this folder's README.md. Main figure:
omission-window (RXRR, p2 omitted) area x area imaginary-coherency matrices, one per band,
observed minus trial-shuffled null, session as the unit of inference. Stimulus-window matrices
(present in every condition) are supplement-only, alongside the layer-resolved (not
area-pooled) versions.

MULTIPLICITY, DONE RIGHT THIS TIME: fig04_laminar and fig05_area_by_band (inventory review,
2026-07-30) reused one family name across 4 separately-corrected files, which does not
under-count anything currently significant but is architecturally unsound. Here the full area
x area x band grid for one context is corrected together as ONE family, in one call, in one
file -- not split by band and not split by file.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import AREA_COLORS, AREA_ORDER, AREA_POOL, BANDS  # noqa: E402
from figstats import group_location, paired_location, write  # noqa: E402
from svgassemble import PT_PER_IN, assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
COUPLING_NPZ = os.path.join(REPO, "outputs", "lfp_coupling_matrices", "coupling.npz")
SVG_DIR = os.path.join(HERE, "svg")

CONTEXT_LABEL = {"stimulus": "Stimulus (p1, real in every condition)",
                 "omission": "Omission window (p2, RXRR only)"}


def load():
    d = np.load(COUPLING_NPZ, allow_pickle=True)
    keys, vals = d["keys"], d["values"]
    rows = []
    for k, v in zip(keys, vals):
        session, ctx, band, areaA, layerA, areaB, layerB = k.split("|")
        rows.append({
            "session": session, "context": ctx, "band": band,
            "areaA": AREA_POOL.get(areaA, areaA), "layerA": layerA,
            "areaB": AREA_POOL.get(areaB, areaB), "layerB": layerB,
            "obs": v[0], "null_mu": v[1], "null_sd": v[2],
            "n_shuffle": v[3], "n_trials": v[4],
        })
    import pandas as pd
    return pd.DataFrame(rows)


def session_area_pair_effect(df, context, band):
    """Pool layer-cells within an area pair (mean effect across whichever layer
    combinations exist for that area pair in that session), one row per
    (session, areaA, areaB)."""
    sub = df[(df.context == context) & (df.band == band)].copy()
    sub["effect"] = sub.obs - sub.null_mu
    # canonicalize area order so (A,B) and (B,A) don't split into two rows
    lo = np.minimum(sub.areaA, sub.areaB)
    hi = np.maximum(sub.areaA, sub.areaB)
    sub["areaA"], sub["areaB"] = lo, hi
    return sub.groupby(["session", "areaA", "areaB"], as_index=False)["effect"].mean()


def build_matrix_and_stats(df, context, areas):
    """One area x area effect matrix per band, plus one Result per (band, area-pair)
    -- all bands x all pairs for this context corrected together as ONE family."""
    n = len(areas)
    matrices = {}
    stats = []
    for band in BANDS:
        band_key = band.split(" ")[0].lower().replace("(", "").replace(")", "")
        # BANDS keys in figstyle are display strings; coupling.npz used the plain band name.
        raw_band = {"Theta": "theta", "Alpha": "alpha", "Beta": "beta",
                   "Low": "low_gamma", "High": "high_gamma"}
        key = None
        for prefix, raw in raw_band.items():
            if band.startswith(prefix):
                key = raw
        pooled = session_area_pair_effect(df, context, key)
        mat = np.full((n, n), np.nan)
        for i, a in enumerate(areas):
            for j, b in enumerate(areas):
                if i >= j:
                    continue
                lo, hi = min(a, b), max(a, b)
                cell = pooled[(pooled.areaA == lo) & (pooled.areaB == hi)]
                if cell.empty:
                    continue
                vals = cell.effect.values
                mat[i, j] = mat[j, i] = np.mean(vals)
                res = paired_location(
                    vals, np.zeros_like(vals), figure="fig05_supp", panel=context,
                    question=f"{key} {lo}-{hi} {context} coupling vs null", unit="session",
                    family=f"fig05_supp_{context}",
                    note=f"n={len(vals)} sessions with both cells present")
                stats.append(res)
        matrices[band] = mat
    return matrices, stats


def draw_context_figure(df, context, areas, out_stem, title):
    matrices, stats = build_matrix_and_stats(df, context, areas)
    n_bands = len(BANDS)
    fig, axes = plt.subplots(1, n_bands, figsize=(3.1 * n_bands, 3.4))
    vmax = max(np.nanmax(np.abs(m)) for m in matrices.values() if np.any(np.isfinite(m)))
    im0 = None
    for ax, (band, mat) in zip(axes, matrices.items()):
        im = ax.imshow(mat, cmap="RdBu_r", vmin=-vmax, vmax=vmax)
        im0 = im0 or im
        ax.set_xticks(range(len(areas))); ax.set_xticklabels(areas, rotation=90, fontsize=6)
        ax.set_yticks(range(len(areas))); ax.set_yticklabels(areas, fontsize=6)
        ax.set_title(band, fontsize=8)
    fig.suptitle(title, fontsize=11, fontweight="bold", y=1.04)
    cb = fig.colorbar(im0, ax=axes, shrink=0.75, pad=0.01)
    cb.set_label("|Im coherency| observed - shuffle null", rotation=270, labelpad=14, fontsize=8)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg", stats


def identity_stats(df, areas):
    """A/B/R stimulus-identity question (phase 2): does area-pair x band coupling during the
    position-2 omission differ by which stimulus-sequence family (A/AXAB, B/BXBA, R/RXRR) the
    trial belongs to? All three use the identical window (1.031-1.562 s); "identity_R" reuses
    the already-extracted "omission" context (RXRR) rather than re-running it, since they are
    the same condition and window -- see extract_lfp_coupling_matrices.py's CONTEXTS comment.
    3-group comparison (Kruskal-Wallis/ANOVA via group_location), unit = session, ONE joint
    family across the whole area x area x band grid -- same convention as the other families
    in this file."""
    ctx_map = {"A": "identity_A", "B": "identity_B", "R": "omission"}
    stats = []
    for band in BANDS:
        band_key = None
        for prefix, raw in {"Theta": "theta", "Alpha": "alpha", "Beta": "beta",
                           "Low": "low_gamma", "High": "high_gamma"}.items():
            if band.startswith(prefix):
                band_key = raw
        pooled = {ident: session_area_pair_effect(df, ctx, band_key)
                 for ident, ctx in ctx_map.items()}
        for i in range(len(areas)):
            for j in range(i + 1, len(areas)):
                lo, hi = areas[i], areas[j]
                groups, labels = [], []
                for ident, p in pooled.items():
                    vals = p[(p.areaA == lo) & (p.areaB == hi)].effect.values
                    if len(vals) >= 3:
                        groups.append(vals)
                        labels.append(ident)
                if len(groups) >= 2:
                    stats.append(group_location(
                        groups, labels, figure="fig05_supp", panel="identity",
                        question=f"{band_key} {lo}-{hi} coupling differs by A/B/R identity",
                        unit="session", family="fig05_supp_identity",
                        note="identity_R reuses the omission context (RXRR); same window "
                             "(1.031-1.562s) across all three identities"))
    return stats


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    df = load()
    areas = [a for a in AREA_ORDER if a in set(df.areaA) | set(df.areaB)]
    print(f"areas present: {areas}")
    print(f"sessions present: {df.session.nunique()}")
    print(f"contexts: {sorted(df.context.unique())}")

    all_stats = []
    omission_svg, stats_o = draw_context_figure(
        df, "omission", areas, "supp_coherency_omission_matrices",
        "LFP-LFP coupling, omission window (RXRR, p2 omitted)")
    all_stats += stats_o
    stim_svg, stats_s = draw_context_figure(
        df, "stimulus", areas, "supp_coherency_stimulus_matrices",
        "LFP-LFP coupling, stimulus window (p1, present in every condition)")
    all_stats += stats_s

    if {"identity_A", "identity_B"}.issubset(set(df.context.unique())):
        stats_id = identity_stats(df, areas)
        all_stats += stats_id
        print(f"identity (A/B/R) stats: {len(stats_id)} tests")

    out, w, h = assemble([omission_svg], os.path.join(HERE, "supp_lfp_lfp_coherency.svg"), ncol=1)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    write(all_stats, SVG_DIR, "supp_coherency",
         title="Figure 5 supplement -- LFP-LFP coupling matrices (undirected, imaginary coherency), observed vs shuffle null",
         preamble="Imaginary coherency (Nolte et al. 2004), zero-lag-mixing-insensitive, "
                  "Laplacian-referenced within probe, representative channel per area x "
                  "layer cell (see README for the tractability decisions this resolves). "
                  "Paired (by session) test of observed minus trial-shuffled-null "
                  "|Im coherency|, per area-pair x band. Family = the FULL area x area x "
                  "band grid for one context (contexts' families reported separately since "
                  "each asks a different question). fig05_supp_identity (phase 2, 2026-07-30) "
                  "asks whether coupling during the position-2 omission differs by A/B/R "
                  "stimulus-sequence-family identity (AXAB/BXBA/RXRR, same window) -- a "
                  "3-group test per area-pair x band, also one joint family. Unit of "
                  "inference is session throughout.")
    print(f"stats: {len(all_stats)} tests written")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": COUPLING_NPZ,
        "areas": areas, "n_sessions": int(df.session.nunique()),
        "contexts": sorted(df.context.unique().tolist()),
        "bands": list(BANDS),
    }
    import json
    with open(os.path.join(SVG_DIR, "supp_coherency_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
