r"""
Figure 7 -- spike-LFP phase coupling (PPC), by area and band.

Reads outputs/spike_lfp_coupling/coupling.npz, built by scripts/extract_spike_lfp_coupling.py.
Main figure: omission-window (RXRR, p2 omitted) PPC observed-minus-shuffle-null, by area, one
panel per band, session as the unit of inference (units within a session are pooled first --
see README's "unit of inference" note, same pseudo-replication rule figure 3's stats already
apply). Stimulus-window is supplement-only.

MULTIPLICITY: same convention this session established for figure 6 -- the full area x band
grid for one context is corrected together as ONE family, in one file, not split per band or
per file the way fig04_laminar/fig05_area_by_band were (found and flagged during the 2026-07-30
inventory review).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import AREA_COLORS, AREA_ORDER, BANDS  # noqa: E402
from figstats import group_location, paired_location, write  # noqa: E402
from svgassemble import assemble  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
COUPLING_NPZ = os.path.join(REPO, "outputs", "spike_lfp_coupling", "coupling.npz")
SVG_DIR = os.path.join(HERE, "svg")

RAW_BAND = {"Theta": "theta", "Alpha": "alpha", "Beta": "beta",
           "Low": "low_gamma", "High": "high_gamma"}


def load():
    d = np.load(COUPLING_NPZ, allow_pickle=True)
    keys, vals = d["keys"], d["values"]
    rows = []
    for k, v in zip(keys, vals):
        session, ctx, band, area, layer, unit_row = k.split("|")
        rows.append({"session": session, "context": ctx, "band": band, "area": area,
                    "layer": layer, "unit_row": int(unit_row),
                    "obs": v[0], "null_mu": v[1], "null_sd": v[2],
                    "n_shuffle": v[3], "n_spikes": v[4]})
    return pd.DataFrame(rows)


def session_area_band_effect(df, context, band_key):
    """Pool units (then layers) within a session x area for one band -- unit of inference is
    session, not unit; many units in one session are not independent replicates (see figure
    3's own presence/functionality panels for the same rule applied to unit counts)."""
    sub = df[(df.context == context) & (df.band == band_key)].copy()
    sub["effect"] = sub.obs - sub.null_mu
    return sub.groupby(["session", "area"], as_index=False)["effect"].mean()


def identity_stats(df, areas):
    """A/B/R stimulus-identity question (phase 2): does area x band spike-LFP PPC during the
    position-2 omission differ by which stimulus-sequence family (A/AXAB, B/BXBA, R/RXRR) the
    trial belongs to? Same construction as fig06's identity_stats -- identity_R reuses the
    already-extracted 'omission' context (RXRR, same window) rather than re-running it."""
    ctx_map = {"A": "identity_A", "B": "identity_B", "R": "omission"}
    stats = []
    for band_disp in BANDS:
        band_key = None
        for prefix, raw in RAW_BAND.items():
            if band_disp.startswith(prefix):
                band_key = raw
        pooled = {ident: session_area_band_effect(df, ctx, band_key)
                 for ident, ctx in ctx_map.items()}
        for a in areas:
            groups, labels = [], []
            for ident, p in pooled.items():
                vals = p[p.area == a].effect.values
                if len(vals) >= 3:
                    groups.append(vals)
                    labels.append(ident)
            if len(groups) >= 2:
                stats.append(group_location(
                    groups, labels, figure="fig07", panel="identity",
                    question=f"{band_key} {a} spike-LFP PPC differs by A/B/R identity",
                    unit="session", family="fig07_identity",
                    note="identity_R reuses the omission context (RXRR); same window "
                         "(1.031-1.562s) across all three identities"))
    return stats


def build_panel_and_stats(df, context, areas):
    stats = []
    band_effects = {}
    for band_disp in BANDS:
        band_key = None
        for prefix, raw in RAW_BAND.items():
            if band_disp.startswith(prefix):
                band_key = raw
        pooled = session_area_band_effect(df, context, band_key)
        means, sems, ns = [], [], []
        for a in areas:
            vals = pooled[pooled.area == a].effect.values
            means.append(np.mean(vals) if len(vals) else np.nan)
            sems.append(np.std(vals, ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else np.nan)
            ns.append(len(vals))
            if len(vals) >= 3:
                stats.append(paired_location(
                    vals, np.zeros_like(vals), figure="fig07", panel=context,
                    question=f"{band_key} {a} {context} spike-LFP PPC vs null", unit="session",
                    family=f"fig07_{context}", note=f"n={len(vals)} sessions"))
        band_effects[band_disp] = (np.array(means), np.array(sems), np.array(ns))
    return band_effects, stats


def draw_context_figure(df, context, areas, out_stem, title):
    band_effects, stats = build_panel_and_stats(df, context, areas)
    n_bands = len(BANDS)
    fig, axes = plt.subplots(1, n_bands, figsize=(2.9 * n_bands, 3.2), sharey=True)
    x = np.arange(len(areas))
    for ax, (band, (means, sems, ns)) in zip(axes, band_effects.items()):
        colors = [AREA_COLORS.get(a, "0.5") for a in areas]
        ax.bar(x, means, yerr=sems, color=colors, edgecolor="black", linewidth=0.4, capsize=2)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(x); ax.set_xticklabels(areas, rotation=90, fontsize=6)
        ax.set_title(band, fontsize=8)
        for xi, n in zip(x, ns):
            if n:
                ax.text(xi, 0, str(n), fontsize=5, ha="center", va="bottom", color="0.3")
    axes[0].set_ylabel("PPC observed - shuffle null\n(mean +- SEM across sessions)", fontsize=8)
    fig.suptitle(title, fontsize=11, fontweight="bold", y=1.05)
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg", stats


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    df = load()
    areas = [a for a in AREA_ORDER if a in set(df.area)]
    print(f"areas present: {areas}")
    print(f"sessions present: {df.session.nunique()}")
    print(f"units present: {df.groupby(['session', 'area', 'unit_row']).ngroups}")

    all_stats = []
    omission_svg, stats_o = draw_context_figure(
        df, "omission", areas, "fig07_omission_ppc",
        "Spike-LFP phase coupling (PPC), omission window (RXRR, p2 omitted)")
    all_stats += stats_o
    stim_svg, stats_s = draw_context_figure(
        df, "stimulus", areas, "fig07_stimulus_ppc",
        "Spike-LFP phase coupling (PPC), stimulus window (p1, present in every condition)")
    all_stats += stats_s

    if {"identity_A", "identity_B"}.issubset(set(df.context.unique())):
        stats_id = identity_stats(df, areas)
        all_stats += stats_id
        print(f"identity (A/B/R) stats: {len(stats_id)} tests")

    out, w, h = assemble([omission_svg], os.path.join(HERE, "fig07.svg"), ncol=1)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    write(all_stats, SVG_DIR, "fig07",
         title="Figure 7 -- spike-LFP phase coupling (PPC), observed vs shuffle null",
         preamble="Pairwise phase consistency (Vinck et al. 2010, bias-free across spike "
                  "counts) between each SUA unit's spike times and its own area's "
                  "representative-channel LFP phase, per band. Same-electrode contamination "
                  "control: units within 2 channels of the representative LFP channel are "
                  "excluded (see extract_spike_lfp_coupling.py). Null: spike-count-matched "
                  "random-time resampling within each trial window. Paired (by session) test "
                  "of observed minus null, per area x band. Family = the full area x band "
                  "grid for one context, corrected together in one call. fig07_identity "
                  "(phase 2, 2026-07-30) asks whether PPC during the position-2 omission "
                  "differs by A/B/R stimulus-sequence-family identity (AXAB/BXBA/RXRR, same "
                  "window) -- a 3-group test per area x band, also one joint family. Unit of "
                  "inference is session throughout -- units within a session are pooled first "
                  "(many units per session are not independent replicates).")
    print(f"stats: {len(all_stats)} tests written")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "source": COUPLING_NPZ,
        "areas": areas, "n_sessions": int(df.session.nunique()),
        "contexts": sorted(df.context.unique().tolist()), "bands": list(BANDS),
    }
    with open(os.path.join(SVG_DIR, "fig07_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)


if __name__ == "__main__":
    main()
