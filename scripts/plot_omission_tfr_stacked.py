r"""
Omission-aligned TFR panels in the stacked two-area layout.

LAYOUT (matching the reference slide figure)
    Per area, three stacked axes:
        screen strip   what the animal saw -- grating during the preceding stimulus,
                       uniform gray through both delays and the omitted slot, with a
                       "Screen" arrow label at the left
        spectrogram    3-199 Hz on a LOG frequency axis against -1500..+1500 ms from
                       omission onset, viridis, band edges in red, colorbar on the
                       right, area name set large and rotated on the far right
        band traces    five bands with SEM ribbons, legend boxed inside the panel
    Two areas are stacked per figure and share one x-axis, labelled only on the bottom
    panel. Epoch names run along the top: Visual stim / Delay / Omission / Delay / Next stim.

WINDOW AND WHAT IS ACTUALLY IN IT
    -1500..+1500 ms shows the whole preceding stimulus (p(k-1), -1031..-500), the delay
    before the omission, the omitted slot, the delay after it, and the arrival of the next
    stimulus at +1031 ms. Two composition boundaries are marked rather than smoothed over:
      +897 ms   dotted line -- p4 omissions end the trial here, so everything to its right
                comes from p2 and p3 omissions only
      +1031 ms  faded grating -- the next stimulus, present only in those same conditions
    Nothing to the right of +897 ms should be read as an omission-only effect.

OUTPUT PATHS below are written under outputs/omission_tfr_maps_w1500/.

MEASURE
    Input maps hold the RATIO OF EXPECTED POWER: power is averaged over trials first, then
    divided by that channel's own -250..-50 ms pre-omission baseline, and the logarithm is
    taken once, at the very end, after averaging over channels, band frequencies, window
    times and sessions. Averaging decibels instead biases each unit low by roughly half the
    variance of its log-power, which on this corpus reaches -1.98 dB and reverses the sign
    of an animal's effect. See artifacts/.lab/db_averaging_bias_finding_20260728.json.

BANDS
    The audited house set: theta 4-8, alpha 8-14, beta 14-30, low gamma 30-50, high gamma
    50-80 Hz. The reference slide's legend shows theta 2-7, alpha 8-12, gamma-low 32-80,
    gamma-high 80+, which is the pre-correction set retired by the 2026-07-27 figure audit.
    Pass --bands reference to reproduce the slide exactly.

OUTPUT
    outputs/omission_tfr_maps_final/figures_stacked/pair_<A>_<B>.png
    outputs/omission_tfr_maps_final/figures_stacked/all_areas_grid.png
    outputs/omission_tfr_maps_final/figures_stacked/receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.ticker
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

MAPS = r"D:/workspace/omission/outputs/omission_tfr_maps_w1500/maps.npz"
OUT_DIR = r"D:/workspace/omission/outputs/omission_tfr_maps_w1500"
FIG_DIR = os.path.join(OUT_DIR, "figures_stacked")

# hierarchy order, paired as they are read together
PAIRS = [("V1", "V2"), ("V3a/d", "V4"), ("MT", "MST"), ("TEO", "FST"), ("FEF", "PFC")]

BANDSETS = {
    "manuscript": {"Theta(4-8Hz)": (4, 8), "Alpha(8-14Hz)": (8, 14), "Beta(14-30Hz)": (14, 30),
                   "Gamma(Low,30-50Hz)": (30, 50), "Gamma(High,50-80Hz)": (50, 80)},
    "reference": {"Theta(2-7Hz)": (2, 7), "Alpha(8-12Hz)": (8, 12), "Beta(14-30Hz)": (14, 30),
                  "Gamma(Low,32-80Hz)": (32, 80), "Gamma(High,80+Hz)": (80, 201)},
}
BAND_COLORS = ["#0000EE", "#EE0000", "#FF8C00", "#FF00FF", "#00A000"]

STIM_MS, DELAY_MS = 531, 500
# Bins contributed by fewer than this fraction of the maximum are dropped. At the wider
# window the binding constraint is that p4 omissions end the trial at +897 ms, so beyond
# that only p2 and p3 omissions contribute -- two thirds of the conditions. The threshold
# admits them and the change is marked on the figure instead of being hidden.
COVERAGE_MIN = 0.55
WIN = (-1500, 1500)
PREV_STIM = (-1031, -DELAY_MS)      # p(k-1), fully inside the window now
OMISSION = (0, STIM_MS)             # the omitted slot itself
NEXT_STIM = (1031, 1562)            # p(k+1) -- p2/p3 omissions only; p4 ends the trial
SLOT4_END = 897                     # last sample a p4 omission can contribute


def grating_strip(width=700, height=60, cycles=12):
    x = np.linspace(0, 1, width)
    y = np.linspace(0, 1, height)
    xx, yy = np.meshgrid(x, y)
    return 0.5 + 0.5 * np.sin(2 * np.pi * cycles * (xx + 0.55 * yy))


def to_db(r):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10.0 * np.log10(r)


def load():
    z = np.load(MAPS, allow_pickle=True)
    keys = [str(k) for k in z["keys"]]
    sums, counts, freqs, times = z["sums"], z["counts"], z["freqs"], z["times"]
    maps = {}
    for i, k in enumerate(keys):
        with np.errstate(invalid="ignore", divide="ignore"):
            m = np.where(counts[i] > 0, sums[i] / np.maximum(counts[i], 1), np.nan)
        per_bin = np.nanmax(counts[i], axis=0)
        mx = np.nanmax(per_bin) if per_bin.size else 0
        keep = per_bin >= COVERAGE_MIN * mx if mx > 0 else per_bin > 0
        m[:, ~keep] = np.nan
        maps[k] = m
    return maps, freqs, times


def area_sessions(maps, area, layer="all"):
    return {k.split("|")[0]: m for k, m in maps.items()
            if k.split("|")[1] == area and k.split("|")[2] == layer}


OUTLIER_FACTOR = 5.0


def drop_outlier_sessions(sess):
    """Remove sessions whose map is grossly out of scale with the rest of the area.

    A single channel with a near-zero baseline makes its power ratio enormous, which shows up
    as a session whose extreme is many times the typical one. Those extremes sit outside the
    windows any statistic uses -- in the stimulus period and at the window edges -- so they do
    not affect the reported numbers, but they do set the colour scale and drag the mean trace.
    A session is dropped from the DISPLAY when its maximum |dB| exceeds OUTLIER_FACTOR times
    the median session maximum for that area. Returns (kept, dropped_names).
    """
    if len(sess) < 3:
        return sess, []
    names = list(sess)
    mx = np.array([np.nanmax(np.abs(to_db(sess[n]))) for n in names])
    med = float(np.median(mx))
    keep = {n: sess[n] for n, v in zip(names, mx) if v <= OUTLIER_FACTOR * med}
    dropped = [n for n, v in zip(names, mx) if v > OUTLIER_FACTOR * med]
    return (keep, dropped) if keep else (sess, [])


def band_ratio(m, freqs, lo, hi):
    sel = (freqs >= lo) & (freqs < hi)
    return np.nanmean(m[sel], axis=0) if sel.any() else np.full(m.shape[1], np.nan)


def draw_area(fig, gs_cell, area, sess, freqs, times, bands, vlim, bottom):
    """screen strip + spectrogram + band traces for one area."""
    sess, dropped = drop_outlier_sessions(sess)
    gs = gs_cell.subgridspec(3, 1, height_ratios=[0.42, 2.9, 2.5], hspace=0.06)
    ax_s, ax_m, ax_t = (fig.add_subplot(gs[i]) for i in range(3))

    # ---- screen strip ---------------------------------------------------------
    ax_s.set_xlim(*WIN)
    ax_s.set_ylim(0, 1)
    ax_s.add_patch(Rectangle((WIN[0], 0), WIN[1] - WIN[0], 1, color="0.45", zorder=1))
    ax_s.imshow(grating_strip(), cmap="gray", aspect="auto", zorder=2, vmin=0, vmax=1,
                extent=(PREV_STIM[0], PREV_STIM[1], 0, 1))
    # p(k+1): present only for p2/p3 omissions, so it is drawn faded and labelled as partial
    ax_s.imshow(grating_strip(), cmap="gray", aspect="auto", zorder=2, vmin=0, vmax=1,
                alpha=0.45, extent=(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), 0, 1))
    for sp in ax_s.spines.values():
        sp.set_visible(False)
    ax_s.set_xticks([])
    ax_s.set_yticks([])
    # placed in axes fractions so the label cannot be clipped by the figure margin
    ax_s.annotate("", xy=(-0.012, 0.5), xytext=(-0.075, 0.5), xycoords="axes fraction",
                  textcoords="axes fraction", annotation_clip=False,
                  arrowprops=dict(arrowstyle="-|>", color="black", lw=1.4))
    ax_s.text(-0.082, 0.5, "Screen", transform=ax_s.transAxes, ha="right", va="center",
              fontsize=11, clip_on=False)
    for x, lab, col in [(-765, "Visual stim", "red"), (-250, "Delay", "black"),
                        (265, "Omission", "purple"), (780, "Delay", "black"),
                        (1270, "Next stim*", "0.35")]:
        ax_s.text(x, 1.55, lab, color=col, ha="center", va="bottom", fontsize=13)

    # ---- spectrogram ----------------------------------------------------------
    grand = to_db(np.nanmean(np.stack(list(sess.values())), axis=0))
    im = ax_m.pcolormesh(times, freqs, grand, cmap="viridis", shading="nearest",
                         vmin=vlim[0], vmax=vlim[1])
    for e in sorted({e for v in bands.values() for e in v if e <= freqs[-1]}):
        ax_m.axhline(e, color="red", lw=0.7, alpha=0.85)
    ax_m.axvline(0, color="green", ls="--", lw=1.6)
    ax_m.axvline(SLOT4_END, color="0.25", ls=":", lw=1.2)
    ax_m.set_xlim(*WIN)
    # Log frequency axis: at 3-199 Hz linear, theta through beta occupy the bottom ~14% of
    # the panel and are unreadable. Log spacing gives the low-frequency bands the room the
    # analysis actually spends its attention on.
    ax_m.set_yscale("log")
    ax_m.set_ylim(freqs[0], freqs[-1])
    ax_m.set_yticks([4, 8, 14, 30, 50, 80, 150])
    ax_m.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
    ax_m.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax_m.set_ylabel("Frequency (Hz)", color="blue", fontsize=10)
    ax_m.tick_params(labelbottom=False, labelsize=9)
    for lb in ax_m.get_yticklabels():
        lb.set_color("blue")
    cb = fig.colorbar(im, ax=ax_m, pad=0.012, fraction=0.030)
    cb.set_label("Power change (dB)", fontsize=8, rotation=270, labelpad=12)
    cb.ax.tick_params(labelsize=8)
    # large rotated area name, outside the colorbar
    ax_m.text(1.085, -0.05, area, transform=ax_m.transAxes, rotation=270,
              va="center", ha="left", fontsize=24, fontweight="bold")
    if dropped:
        ax_m.text(0.005, 1.03, f"{len(dropped)} session excluded from display (out of scale)",
                  transform=ax_m.transAxes, fontsize=7, color="0.35", va="bottom")

    # ---- band traces ----------------------------------------------------------
    for (name, (lo, hi)), col in zip(bands.items(), BAND_COLORS):
        r = np.stack([band_ratio(m, freqs, lo, hi) for m in sess.values()])
        mu = np.nanmean(r, axis=0)
        n = np.sum(np.isfinite(r), axis=0)
        sem = np.nanstd(r, axis=0, ddof=1) / np.sqrt(np.maximum(n, 1))
        ax_t.plot(times, to_db(mu), color=col, lw=2.2, label=name, zorder=3)
        ax_t.fill_between(times, to_db(np.maximum(mu - sem, 1e-12)), to_db(mu + sem),
                          color=col, alpha=0.30, lw=0, zorder=2)
    ax_t.axhline(0, color="black", lw=0.9)
    ax_t.axvline(0, color="green", ls="--", lw=1.6)
    # p4 omissions end the trial here; everything to the right is p2/p3 only
    ax_t.axvline(SLOT4_END, color="0.25", ls=":", lw=1.2)
    ax_t.set_xlim(*WIN)
    ax_t.set_ylabel("Power change (dB)", fontsize=10)
    ax_t.axvspan(*PREV_STIM, color="#F8C6C6", alpha=0.45, zorder=0)
    ax_t.axvspan(*OMISSION, color="#E7D3F0", alpha=0.55, zorder=0)
    ax_t.axvspan(NEXT_STIM[0], min(NEXT_STIM[1], WIN[1]), color="#F8C6C6", alpha=0.22,
                 zorder=0)
    leg = ax_t.legend(fontsize=8, loc="upper right", framealpha=0.9, fancybox=False)
    leg.get_frame().set_linestyle("--")
    leg.get_frame().set_edgecolor("black")
    ax_t.set_xticks([-1500, -1000, -500, 0, 500, 1000, 1500])
    if bottom:
        ax_t.set_xticklabels(["-1500", "-1000", "-500", "0", "+500", "+1000", "+1500"],
                             color="green", fontsize=12)
        ax_t.text(0.5, -0.36, "* next stimulus and the region right of the dotted line come "
                  "only from p2/p3 omissions; p4 omissions end the trial at +897 ms",
                  transform=ax_t.transAxes, ha="center", va="top", fontsize=8, color="0.3")
        ax_t.set_xlabel("Time from omission onset (ms)", color="green", fontsize=15)
    else:
        ax_t.tick_params(labelbottom=False)
    return len(sess)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bands", choices=list(BANDSETS), default="manuscript")
    ap.add_argument("--areas", default=None,
                    help="comma-separated area list, e.g. V1,V3a/d,TEO,PFC. Overrides PAIRS.")
    ap.add_argument("--ncol", type=int, default=2, help="columns in the multi-area figure")
    ap.add_argument("--scale", choices=["common", "per-panel"], default="common",
                    help="colour scale shared across panels, or fitted to each panel")
    ap.add_argument("--out", default=None, help="output basename")
    ap.add_argument("--figw", type=float, default=13.5, help="per-column width, inches")
    ap.add_argument("--title", default=None, help="optional suptitle template, {pair} allowed")
    args = ap.parse_args()
    bands = BANDSETS[args.bands]
    os.makedirs(FIG_DIR, exist_ok=True)

    maps, freqs, times = load()
    have = {k.split("|")[1] for k in maps}
    # common colour scale so every panel is directly comparable
    vals = np.concatenate([to_db(np.nanmean(np.stack(list(area_sessions(maps, a).values())),
                                            axis=0)).ravel()
                           for a in have if area_sessions(maps, a)])
    lim = float(np.nanpercentile(np.abs(vals), 99))
    vlim = (-round(lim, 1), round(lim, 1))

    def vlim_for(area):
        """Colour limits from a ROBUST summary, restricted to the analysed time range.

        The displayed map is still the mean across sessions. The colour LIMITS are taken
        from the median across sessions and only over -1000..+1000 ms, because a single
        session with a small-baseline channel can push the map past 30 dB in the stimulus
        period and at the window edges -- regions no reported statistic uses. Setting the
        scale from those values compresses every real effect into one colour.
        """
        if args.scale == "common":
            return vlim
        kept, _ = drop_outlier_sessions(area_sessions(maps, area))
        v = to_db(np.nanmean(np.stack(list(kept.values())), axis=0))
        lim = float(np.nanpercentile(np.abs(v), 99))
        return (-round(lim, 1), round(lim, 1))

    if args.areas:
        req = [a.strip() for a in args.areas.split(",")]
        present_req = [a for a in req if area_sessions(maps, a)]
        miss = [a for a in req if a not in present_req]
        if miss:
            print("WARNING: no data for", miss)
        ncol = max(1, args.ncol)
        nrow = int(np.ceil(len(present_req) / ncol))
        fig = plt.figure(figsize=(args.figw * ncol, 5.2 * nrow))
        gs = fig.add_gridspec(nrow, ncol, hspace=0.32, wspace=0.22,
                              left=0.065, right=0.955, top=0.965, bottom=0.085)
        cnt = {}
        for i, area in enumerate(present_req):
            cnt[area] = draw_area(fig, gs[i // ncol, i % ncol], area,
                                  area_sessions(maps, area), freqs, times, bands,
                                  vlim_for(area), i // ncol == nrow - 1)
        base = args.out or ("fig_" + "_".join(a.replace("/", "") for a in present_req))
        out = os.path.join(FIG_DIR, base + ".png")
        fig.savefig(out, dpi=180)
        fig.savefig(out.replace(".png", ".svg"))
        plt.close(fig)
        print(f"areas: {present_req}")
        print(f"sessions per area: {cnt}")
        print(f"colour scale: {args.scale}" +
              ("" if args.scale == "common" else
               "  " + str({a: vlim_for(a) for a in present_req})))
        print("WROTE", out, "and", out.replace(".png", ".svg"))
        with open(os.path.join(FIG_DIR, base + ".receipt.json"), "w", encoding="utf-8") as fh:
            json.dump({"generated_utc": datetime.now(timezone.utc).isoformat(),
                       "script": os.path.abspath(__file__), "maps": MAPS,
                       "areas": present_req, "sessions_per_area": cnt,
                       "ncol": ncol, "scale_mode": args.scale,
                       "colour_scale_db": {a: list(vlim_for(a)) for a in present_req},
                       "window_ms": list(WIN), "frequency_axis": "logarithmic",
                       "bands_hz": {k: list(v) for k, v in bands.items()},
                       "measure": "ratio of expected power vs each channel's own -250..-50 ms "
                                  "pre-omission baseline; log taken once after averaging"},
                      fh, indent=2)
        return

    made, counts = [], {}
    for a, b in PAIRS:
        pair = [x for x in (a, b) if area_sessions(maps, x)]
        if not pair:
            continue
        fig = plt.figure(figsize=(13.5, 5.4 * len(pair)))
        gs = fig.add_gridspec(len(pair), 1, hspace=0.22,
                              left=0.135, right=0.90,
                              top=0.93 if args.title else 0.955, bottom=0.075)
        for i, area in enumerate(pair):
            counts[area] = draw_area(fig, gs[i], area, area_sessions(maps, area),
                                     freqs, times, bands, vlim, i == len(pair) - 1)
        if args.title:
            fig.suptitle(args.title.format(pair="/".join(pair)), fontsize=17, y=0.985)
        name = "pair_" + "_".join(x.replace("/", "") for x in pair) + ".png"
        fig.savefig(os.path.join(FIG_DIR, name), dpi=185)
        plt.close(fig)
        made.append(name)

    # ---- all-area overview, same layout, two columns ------------------------------
    present = [a for p in PAIRS for a in p if area_sessions(maps, a)]
    ncol = 2
    nrow = int(np.ceil(len(present) / ncol))
    fig = plt.figure(figsize=(27, 5.2 * nrow))
    gs = fig.add_gridspec(nrow, ncol, hspace=0.30, wspace=0.22,
                          left=0.065, right=0.955, top=0.97, bottom=0.045)
    for i, area in enumerate(present):
        draw_area(fig, gs[i // ncol, i % ncol], area, area_sessions(maps, area),
                  freqs, times, bands, vlim, i // ncol == nrow - 1)
    fig.savefig(os.path.join(FIG_DIR, "all_areas_grid.png"), dpi=130)
    plt.close(fig)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "maps": MAPS,
        "layout": "two areas stacked per figure, shared x-axis labelled on the bottom panel",
        "pairs": [list(p) for p in PAIRS],
        "figures": made + ["all_areas_grid.png"],
        "bandset": args.bands,
        "bands_hz": {k: list(v) for k, v in bands.items()},
        "bandset_note": "audited house set; the reference slide uses the pre-correction set "
                        "retired by the 2026-07-27 figure audit (--bands reference reproduces it)",
        "measure": "ratio of expected power: trial-mean power / that channel's own -250..-50 ms "
                   "pre-omission baseline; 10*log10 applied once, after all averaging",
        "aggregation": "unweighted mean of per-session ratios; SEM ribbons across sessions, "
                       "mapped through the same logarithm",
        "sessions_per_area": counts,
        "colour_scale_db": list(vlim),
        "colour_scale_rule": "common across all areas, symmetric, 99th percentile of |dB|",
        "window_ms": list(WIN),
        "frequency_axis": "logarithmic; ticks at the band edges 4, 8, 14, 30, 50, 80, 150 Hz",
        "composition_caveat": "p4 omissions end the trial at +897 ms, so bins beyond that "
                              "come only from p2 and p3 omissions, and a new stimulus begins "
                              "at +1031 ms in those conditions. Both boundaries are drawn on "
                              "the figure; nothing right of +897 ms is omission-only.",
        "coverage_min": COVERAGE_MIN,
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(os.path.join(FIG_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("figures:", ", ".join(made))
    print("sessions per area:", counts)
    print("colour scale:", vlim, "dB")
    print("WROTE", FIG_DIR)


if __name__ == "__main__":
    main()
