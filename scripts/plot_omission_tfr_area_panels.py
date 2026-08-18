r"""
Omission-aligned spectrogram + band-trace panels for all ten areas, plus the
area x band x putative-layer statistics that go with them.

STYLE
    Reproduces the reference panel layout: a screen strip showing what the animal saw
    (grating during the stimulus, uniform gray through both delays and the omission),
    a viridis spectrogram with band edges marked, and band-power traces with SEM shading,
    over -1000 to +1000 ms relative to omission onset. Stimulus period shaded pink,
    omission period shaded lavender, omission onset marked with a green dashed line.

BASELINE
    Every value is dB relative to THAT CHANNEL's own -250 to -50 ms pre-omission baseline
    (see extract_omission_tfr_maps.py). Nothing here is normalised by another area, another
    session or another animal, so a panel showing modulation is showing modulation of that
    area against itself.

UNIT OF INFERENCE
    Session. Area maps are the unweighted mean of per-session means, so a session
    contributing many channels does not dominate. SEM ribbons are across sessions.
    Subject identity is not shown -- but every dB value is computed within a channel within
    a session, so each effect is within-subject by construction and no contrast in this
    figure is ever taken across animals.

BAND DEFINITIONS
    Default is the manuscript's declared set (theta 4-8, alpha 8-14, beta 14-30,
    low gamma 30-50, high gamma 50-80 Hz). The reference figure's legend uses a different
    set (theta 2-7, alpha 8-12, beta 14-30, gamma-low 32-80, gamma-high 80+). Pass
    --bands reference to switch. The two are not interchangeable and the choice belongs in
    Methods, so it is explicit here rather than silent.

OUTPUT
    outputs/omission_tfr_maps/figures/area_<AREA>.png        one per area
    outputs/omission_tfr_maps/figures/all_areas_grid.png     10-area overview
    outputs/omission_tfr_maps/figures/layers_<AREA>.png      sup vs deep, where available
    outputs/omission_tfr_maps/area_band_layer_stats.csv
    outputs/omission_tfr_maps/figures/receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
from collections import defaultdict
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from scipy import stats
import jnwb as oa
from jnwb import paths as _P

MAPS = _P.REPO_ROOT / "outputs/omission_tfr_maps_ratio/maps.npz"
OUT_DIR = _P.REPO_ROOT / "outputs/omission_tfr_maps_ratio"
FIG_DIR = os.path.join(OUT_DIR, "figures")

AREA_ORDER = ["V1", "V2", "V3", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]
# Hamm 2026-07-28: the pooled V3/V3a/V3d group is labelled V3a/d, inclusively covering all
# three source tokens, so the label never implies a single measured subdivision.
AREA_DISPLAY = {"V3": "V3a/d"}

BANDSETS = {
    "manuscript": {"Theta(4-8Hz)": (4, 8), "Alpha(8-14Hz)": (8, 14), "Beta(14-30Hz)": (14, 30),
                   "Gamma(Low,30-50Hz)": (30, 50), "Gamma(High,50-80Hz)": (50, 80)},
    "reference": {"Theta(2-7Hz)": (2, 7), "Alpha(8-12Hz)": (8, 12), "Beta(14-30Hz)": (14, 30),
                  "Gamma(Low,32-80Hz)": (32, 80), "Gamma(High,80+Hz)": (80, 201)},
}
BAND_COLORS = ["#0000EE", "#EE0000", "#FF8C00", "#FF00FF", "#00A000"]

STIM_MS, DELAY_MS = 531, 500
COVERAGE_MIN = 0.80          # drop time bins sampled by fewer than this fraction of trials
PREV_STIM = (-1000, -DELAY_MS)          # previous stimulus, clipped at the window edge
OMISSION = (0, STIM_MS)
WIN = (-1000, 1000)


def grating_strip(width=600, height=60, cycles=11):
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)
    return 0.5 + 0.5 * np.sin(2 * np.pi * cycles * (xx + 0.55 * yy))


def load():
    z = np.load(MAPS, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts = z["sums"], z["counts"]
    freqs, times = z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        # Conditions with the omission in the last slot run out of source samples ~100 ms
        # before +1000 ms. Averaging the surviving subset there would draw a step that is a
        # change of sample, not a change of physiology, so those bins are dropped.
        per_bin = np.nanmax(counts[i], axis=0)
        keep = per_bin >= COVERAGE_MIN * np.nanmax(per_bin) if np.nanmax(per_bin) > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        maps[k] = m          # POWER RATIO, not dB -- see to_db()
    return maps, freqs, times


def to_db(ratio):
    """Take the logarithm once, after every average. Never average decibels."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(ratio)


def area_session_maps(maps, area, layer="all"):
    out = {}
    for k, m in maps.items():
        sp, a, l = k.split("|")
        if a == area and l == layer:
            out[sp] = m
    return out


def band_trace(m, freqs, lo, hi, db=True):
    """Mean POWER RATIO across the band, converted to dB last."""
    sel = (freqs >= lo) & (freqs < hi)
    if sel.sum() == 0:
        return np.full(m.shape[1], np.nan)
    r = np.nanmean(m[sel], axis=0)
    return to_db(r) if db else r


def draw_panel(fig, gs_row, area, sess_maps, freqs, times, bands, vlim, show_xlabel):
    """Three stacked axes: screen strip, spectrogram, band traces."""
    gsub = gs_row.subgridspec(3, 1, height_ratios=[0.5, 3.0, 2.6], hspace=0.05)
    ax_s = fig.add_subplot(gsub[0])
    ax_m = fig.add_subplot(gsub[1])
    ax_t = fig.add_subplot(gsub[2])

    # ---- screen strip ------------------------------------------------------------
    ax_s.set_xlim(*WIN)
    ax_s.set_ylim(0, 1)
    ax_s.add_patch(Rectangle((WIN[0], 0), WIN[1] - WIN[0], 1, color="0.45", zorder=1))
    ax_s.imshow(grating_strip(), cmap="gray", aspect="auto", zorder=2,
                extent=(PREV_STIM[0], PREV_STIM[1], 0, 1), vmin=0, vmax=1)
    for s in ax_s.spines.values():
        s.set_visible(False)
    ax_s.set_xticks([])
    ax_s.set_yticks([])
    ax_s.text(-750, 1.35, "Visual stim", color="red", ha="center", fontsize=11)
    ax_s.text(-250, 1.35, "Delay", color="black", ha="center", fontsize=11)
    ax_s.text(265, 1.35, "Omission", color="purple", ha="center", fontsize=11)
    ax_s.text(765, 1.35, "Delay", color="black", ha="center", fontsize=11)

    # ---- spectrogram: unweighted mean of per-session means ------------------------
    stack = np.stack(list(sess_maps.values()))
    grand = to_db(np.nanmean(stack, axis=0))          # average ratios, then log
    im = ax_m.pcolormesh(times, freqs, grand, cmap="viridis", shading="nearest",
                         vmin=vlim[0], vmax=vlim[1])
    for edge in sorted({e for lohi in bands.values() for e in lohi if e <= freqs[-1]}):
        ax_m.axhline(edge, color="red", lw=0.6, alpha=0.85)
    ax_m.axvline(0, color="green", ls="--", lw=1.5)
    ax_m.set_xlim(*WIN)
    ax_m.set_ylim(freqs[0], freqs[-1])
    ax_m.set_yticks([20, 40, 60, 80, 100, 150, 200])
    ax_m.set_ylabel("Frequency (Hz)", color="blue", fontsize=10)
    ax_m.tick_params(labelbottom=False, colors="black")
    for lbl in ax_m.get_yticklabels():
        lbl.set_color("blue")
    cb = fig.colorbar(im, ax=ax_m, pad=0.01, fraction=0.025)
    cb.set_label("Power change (dB)", fontsize=8)
    cb.ax.tick_params(labelsize=8)

    # ---- band traces, SEM across sessions -----------------------------------------
    for (name, (lo, hi)), col in zip(bands.items(), BAND_COLORS):
        # Average the RATIO across sessions, then take the logarithm once, so the trace is
        # consistent with the spectrogram above it and carries no dB-averaging bias.
        # The ribbon is the SEM of the session ratios, mapped through the same logarithm.
        r_sess = np.stack([band_trace(m, freqs, lo, hi, db=False)
                           for m in sess_maps.values()])
        r_mu = np.nanmean(r_sess, axis=0)
        r_n = np.sum(np.isfinite(r_sess), axis=0)
        r_sem = np.nanstd(r_sess, axis=0, ddof=1) / np.sqrt(np.maximum(r_n, 1))
        mu = to_db(r_mu)
        lo_db, hi_db = to_db(np.maximum(r_mu - r_sem, 1e-12)), to_db(r_mu + r_sem)
        ax_t.plot(times, mu, color=col, lw=2.0, label=name, zorder=3)
        ax_t.fill_between(times, lo_db, hi_db, color=col, alpha=0.30, lw=0, zorder=2)

    ax_t.axhline(0, color="black", lw=0.8)
    ax_t.axvline(0, color="green", ls="--", lw=1.5)
    ax_t.set_xlim(*WIN)
    ax_t.set_ylabel("Power change (dB)", fontsize=10)
    ax_t.legend(fontsize=7, ncol=1, loc="best", framealpha=0.85,
                edgecolor="black", fancybox=False)
    if show_xlabel:
        ax_t.set_xlabel("Time from omission onset (ms)", color="green", fontsize=13)
        ax_t.set_xticks([-1000, -500, 0, 500, 1000])
        ax_t.set_xticklabels(["-1000", "-500", "0", "+500", "+1000"], color="green")
    else:
        ax_t.set_xticks([-1000, -500, 0, 500, 1000])
        ax_t.tick_params(labelbottom=False)

    for ax in (ax_s, ax_m, ax_t):
        ax.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.45, zorder=0)
        ax.axvspan(*OMISSION, color="#E7D3F0", alpha=0.55, zorder=0)

    ax_t.text(1.015, 1.05, area, transform=ax_t.transAxes, rotation=270,
              va="center", ha="left", fontsize=17, fontweight="bold")
    return len(sess_maps)


def window_stats(maps, freqs, times, bands, index):
    """Session-level test of dB against 0, per area x band x layer, in two windows."""
    wins = {"omitted_slot_0_531": (0, STIM_MS), "post_531_1000": (STIM_MS, 1000),
            "full_0_1000": (0, 1000)}
    rows = []
    for area in AREA_ORDER:
        for layer in ("all", "sup", "deep", "mid"):
            sm = area_session_maps(maps, area, layer)
            if len(sm) < 3:
                continue
            nch = int(index[(index.area == area) & (index.layer == layer)]["n_channels"].sum())
            for bname, (lo, hi) in bands.items():
                for wname, (t0, t1) in wins.items():
                    tsel = (times >= t0) & (times < t1)
                    vals = np.array([to_db(np.nanmean(
                        band_trace(m, freqs, lo, hi, db=False)[tsel])) for m in sm.values()])
                    vals = vals[np.isfinite(vals)]
                    if vals.size < 3:
                        continue
                    t = stats.ttest_1samp(vals, 0.0)
                    ci = stats.t.interval(0.95, vals.size - 1, loc=vals.mean(),
                                          scale=stats.sem(vals))
                    rows.append({"area": AREA_DISPLAY.get(area, area), "layer": layer, "band": bname,
                                 "window": wname, "n_sessions": int(vals.size),
                                 "n_channels": nch, "mean_db": float(vals.mean()),
                                 "sem_db": float(stats.sem(vals)),
                                 "ci_lo": float(ci[0]), "ci_hi": float(ci[1]),
                                 "t": float(t.statistic), "p_raw": float(t.pvalue)})
    r = pd.DataFrame(rows)
    # BH across the ten areas within each (band, window, layer) -- the declared family.
    # Was a hand-rolled loop with a backwards rank divisor (np.arange(n, 0, -1) instead of
    # np.arange(1, n+1)) that silently under-corrected every q_bh value until fixed
    # 2026-08-14 -- see artifacts/.lab/bh-fdr-backwards-divisor-fix-20260814.json.
    r["q_bh"] = np.nan
    for _, g in r.groupby(["band", "window", "layer"]):
        p = g["p_raw"].values
        if len(p) == 0:
            continue
        r.loc[g.index, "q_bh"] = oa.StatisticalAnalysis.fdr_correct(p)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", choices=list(BANDSETS), default="manuscript")
    args = ap.parse_args()
    bands = BANDSETS[args.bands]

    os.makedirs(FIG_DIR, exist_ok=True)
    maps, freqs, times = load()
    index = pd.read_csv(os.path.join(OUT_DIR, "index.csv"))

    present = [a for a in AREA_ORDER if area_session_maps(maps, a)]
    # one common colour scale so areas are comparable at a glance
    allv = np.concatenate([to_db(np.nanmean(
        np.stack(list(area_session_maps(maps, a).values())), axis=0)).ravel()
        for a in present])
    lim = float(np.nanpercentile(np.abs(allv), 99))
    vlim = (-round(lim, 1), round(lim, 1))

    # ---- one figure per area ------------------------------------------------------
    counts = {}
    for area in present:
        sm = area_session_maps(maps, area)
        fig = plt.figure(figsize=(11, 5.2))
        gs = fig.add_gridspec(1, 1, left=0.08, right=0.93, top=0.90, bottom=0.11)
        counts[area] = draw_panel(fig, gs[0], AREA_DISPLAY.get(area, area), sm, freqs, times, bands, vlim, True)
        fig.suptitle(f"{AREA_DISPLAY.get(area, area)} — omission-aligned power change vs each channel's own "
                     f"pre-omission baseline ({counts[area]} sessions)", fontsize=11)
        fig.savefig(os.path.join(FIG_DIR, f"area_{area}.png"), dpi=190)
        plt.close(fig)

    # ---- 10-area grid -------------------------------------------------------------
    ncol = 2
    nrow = int(np.ceil(len(present) / ncol))
    fig = plt.figure(figsize=(21, 4.6 * nrow))
    gs = fig.add_gridspec(nrow, ncol, hspace=0.34, wspace=0.20,
                          left=0.045, right=0.955, top=0.965, bottom=0.045)
    for i, area in enumerate(present):
        draw_panel(fig, gs[i // ncol, i % ncol], AREA_DISPLAY.get(area, area),
                   area_session_maps(maps, area), freqs, times, bands, vlim,
                   i // ncol == nrow - 1)
    fig.savefig(os.path.join(FIG_DIR, "all_areas_grid.png"), dpi=150)
    plt.close(fig)

    # ---- laminar panels, where coverage allows ------------------------------------
    lam_made = []
    for area in present:
        avail = [l for l in ("sup", "deep") if len(area_session_maps(maps, area, l)) >= 3]
        if len(avail) < 2:
            continue
        fig = plt.figure(figsize=(11, 4.6 * len(avail)))
        gs = fig.add_gridspec(len(avail), 1, hspace=0.34, left=0.08, right=0.93,
                              top=0.95, bottom=0.07)
        for j, l in enumerate(avail):
            n = draw_panel(fig, gs[j], f"{AREA_DISPLAY.get(area, area)} {l}", area_session_maps(maps, area, l),
                           freqs, times, bands, vlim, j == len(avail) - 1)
        fig.suptitle(f"{area} — superficial vs deep (putative, vFLIP crossover)", fontsize=11)
        fig.savefig(os.path.join(FIG_DIR, f"layers_{area}.png"), dpi=170)
        plt.close(fig)
        lam_made.append(area)

    # ---- statistics ---------------------------------------------------------------
    st = window_stats(maps, freqs, times, bands, index)
    st.to_csv(os.path.join(OUT_DIR, "area_band_layer_stats.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "maps": str(MAPS),
        "bandset": args.bands, "bands_hz": {k: list(v) for k, v in bands.items()},
        "bandset_note": "The reference figure's legend uses a different band set; pass "
                        "--bands reference to reproduce it. The two are not interchangeable.",
        "areas_plotted": present,
        "sessions_per_area": counts,
        "colour_scale_db": list(vlim),
        "colour_scale_rule": "common across all areas, symmetric, 99th percentile of |dB|",
        "baseline": "-250 to -50 ms re: omission onset, per channel, per trial, per frequency",
        "aggregation": "unweighted mean of per-session means; SEM ribbons across sessions",
        "subject_handling": "subject identity is not displayed; every dB value is computed "
                            "within a channel within a session, so no contrast crosses animals",
        "laminar_figures": lam_made,
        "laminar_coverage_note": "vFLIP2 assigns a layer to about a third of channels and is "
                                 "still running over the session list; laminar panels and rows "
                                 "are provisional until it completes",
        "stats_rows": int(len(st)),
        "stats_multiplicity": "Benjamini-Hochberg across the ten areas within each "
                              "(band, window, layer); controls FDR, not FWER",
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "matplotlib": matplotlib.__version__, "platform": platform.platform()},
    }
    with open(os.path.join(FIG_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)

    print(f"areas plotted: {present}")
    print(f"sessions per area: {counts}")
    print(f"laminar figures: {lam_made}")
    print(f"colour scale: {vlim} dB")
    print(f"WROTE {FIG_DIR} and {OUT_DIR}/area_band_layer_stats.csv")


if __name__ == "__main__":
    main()
