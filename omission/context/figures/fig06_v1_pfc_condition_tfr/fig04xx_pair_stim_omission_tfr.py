r"""
Figure 4xx (new supplement, 2026-08-06): TFR spectrograms for V1/V2, MT/MST, and FEF/PFC,
separately for a "stim" context group and an "omission" context group, each pooling trials
across the three condition families (R, A, B) at the shared p2 slot position -- confirmed
design 2026-08-06.

CONTEXT GROUPS
    stim     : RRRR + AAAB + BBBA pooled -- all three are fully real at every slot; no omission
               anywhere in this group.
    omission : RXRR + AXAB + BXBA pooled -- all three omit exactly at p2; the omitted-slot
               timing is identical across all three block-type families.
    Both groups already share the SAME p1-relative time base (p2 sits at the same trial-relative
    position, 1031-1562 ms, in every condition of both groups) -- no slot-realignment trick is
    needed, only pooling trials across the three block-type families at each shared slot. This
    is a narrower, simpler case than the full R/A/B/slot-position realignment scheme in
    ../PLAN_sliding_window_connectivity.md, which pools p2/p3/p4-omission slots onto a common
    LOCAL clock; that broader scheme remains a separate, not-yet-done follow-up.

DATA SOURCE
    outputs/condition_tfr_maps_p1d1p2d2p3/maps.npz (scripts/extract_condition_tfr_maps.py),
    which already covers all 7 needed conditions (RXRR, RRRR, AXAB, AAAB, BXBA, BBBA, plus RRXR
    unused here) for all 10 areas, keyed session|area|layer|cond, storing per-session RATIO sums
    and trial/channel counts (layer='all' pools channels within area) -- no new NWB extraction
    needed for this figure.

MEASURE
    Per session, per area, per context group: sum the ratio-space `sums`/`counts` across the
    three conditions in that group (still ratio space -- valid, since ratio sums from
    independent condition subsets add directly), THEN take 10*log10 once to get that session's
    own dB map. Grand average across sessions is the MEAN of these per-session dB maps (not a
    further ratio-space pool) -- session is the unit of inference here, consistent with the
    GLMM/hit-rate convention this project has used for every other cross-session average this
    week (fig05/06/07), not the single-pipeline-run convention in
    fig04_v1_pfc_condition_tfr.py's own docstring (which pools sessions in ratio space) --
    that difference is a real, disclosed choice, not an oversight.

OUTPUT
    svg/fig04xx_pair_<A>_<B>.svg/.png -- one figure per area pair, 2 areas (rows) x 2 context
        groups (columns) of spectrogram heatmaps
    svg/fig04xx_receipt.json
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

HERE = os.path.dirname(os.path.abspath(__file__))
FIGDIR = os.path.dirname(HERE)
sys.path.insert(0, FIGDIR)
from figstyle import mark_full_trial_axis  # noqa: E402
from svgassemble import assemble  # noqa: E402
from jnwb.spectral import to_db  # noqa: E402

REPO = os.path.dirname(os.path.dirname(FIGDIR))
MAPS_NPZ = os.path.join(REPO, "outputs", "condition_tfr_maps_p1d1p2d2p3", "maps.npz")
SVG_DIR = os.path.join(HERE, "svg")

CONTEXT_GROUPS = {"stim": ["RRRR", "AAAB", "BBBA"], "omission": ["RXRR", "AXAB", "BXBA"]}
PAIRS = [("V1", "V2"), ("MT", "MST"), ("FEF", "PFC")]
WIN_MS = (0, 2593)      # p1-d1-p2-d2-p3 only, per request -- fx dropped from this view


def load():
    d = np.load(MAPS_NPZ, allow_pickle=True)
    keys = d["keys"]
    idx = {}
    for i, k in enumerate(keys):
        parts = k.split("|")
        if len(parts) != 4 or parts[2] != "all":
            continue
        session, area, _layer, cond = parts
        idx[(session, area, cond)] = i
    return d, idx


def session_group_db(d, idx, session, area, conds, times, i0, i1):
    """Sum ratio-space ``sums``/``counts`` across ``conds`` for one session, one area, then
    log once. Returns (freq, time) dB array, or None if this session/area has none of the
    conditions in this group."""
    s_acc, c_acc = None, None
    for cond in conds:
        key = (session, area, cond)
        if key not in idx:
            continue
        i = idx[key]
        s, c = d["sums"][i][:, i0:i1], d["counts"][i][:, i0:i1]
        s_acc = s if s_acc is None else s_acc + s
        c_acc = c if c_acc is None else c_acc + c
    if s_acc is None:
        return None
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.divide(s_acc, c_acc, out=np.full_like(s_acc, np.nan), where=c_acc > 0)
        return to_db(ratio)


def area_group_grand_mean(d, idx, area, conds, times, i0, i1):
    sessions = sorted({k[0] for k in idx if k[1] == area})
    maps_ = []
    for sess in sessions:
        m = session_group_db(d, idx, sess, area, conds, times, i0, i1)
        if m is not None and np.isfinite(m).any():
            maps_.append(m)
    if not maps_:
        return None, 0
    return np.nanmean(np.stack(maps_), axis=0), len(maps_)


def draw_pair_figure(d, idx, freqs, times, i0, i1, area_a, area_b, out_stem):
    fig, axes = plt.subplots(2, 2, figsize=(9.5, 6.4), sharex=True, sharey=True)
    win_times = times[i0:i1]
    vmax_all = 0.0
    grids = {}
    for area in (area_a, area_b):
        for cg, conds in CONTEXT_GROUPS.items():
            m, n_sess = area_group_grand_mean(d, idx, area, conds, times, i0, i1)
            grids[(area, cg)] = (m, n_sess)
            if m is not None:
                vmax_all = max(vmax_all, np.nanmax(np.abs(m)))
    im0 = None
    for ri, area in enumerate((area_a, area_b)):
        for ci, cg in enumerate(CONTEXT_GROUPS):
            ax = axes[ri, ci]
            m, n_sess = grids[(area, cg)]
            if m is None:
                ax.text(0.5, 0.5, "no data", ha="center", va="center", transform=ax.transAxes)
                continue
            im = ax.pcolormesh(win_times, freqs, m, cmap="viridis", vmin=-vmax_all,
                               vmax=vmax_all, shading="auto")
            im0 = im0 or im
            ax.set_yscale("log")
            ax.set_ylim(freqs.min(), freqs.max())
            mark_full_trial_axis(ax, win=WIN_MS, omit_slot=2 if cg == "omission" else None)
            if ri == 0:
                ax.set_title(f"{cg}\n(n={n_sess} sessions)", fontsize=9)
            if ci == 0:
                ax.set_ylabel(f"{area}\nfreq (Hz)", fontsize=9)
    if im0 is not None:
        cb = fig.colorbar(im0, ax=axes, shrink=0.8, pad=0.02)
        cb.set_label("dB vs middle-of-d1 baseline", rotation=270, labelpad=14, fontsize=8)
    fig.suptitle(f"{area_a} / {area_b} -- stim vs omission context (RRRR+AAAB+BBBA vs "
                f"RXRR+AXAB+BXBA)", fontsize=10, fontweight="bold")
    out = os.path.join(SVG_DIR, out_stem)
    fig.savefig(out + ".png", dpi=190, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)
    return out + ".svg", {f"{a}|{cg}": n for a in (area_a, area_b)
                          for cg, (_, n) in [(cg, grids[(a, cg)]) for cg in CONTEXT_GROUPS]}


def main():
    os.makedirs(SVG_DIR, exist_ok=True)
    d, idx = load()
    times = d["times"]
    freqs = d["freqs"]
    i0 = int(np.searchsorted(times, WIN_MS[0]))
    i1 = int(np.searchsorted(times, WIN_MS[1]))

    svgs = []
    n_sessions_report = {}
    for area_a, area_b in PAIRS:
        stem = "fig04xx_pair_" + f"{area_a}_{area_b}".replace("/", "")
        svg, n_report = draw_pair_figure(d, idx, freqs, times, i0, i1, area_a, area_b, stem)
        svgs.append(svg)
        n_sessions_report[f"{area_a}_{area_b}"] = n_report
        print(f"drew {stem}: {n_report}")

    out, w, h = assemble(svgs, os.path.join(HERE, "fig04xx_pair_stim_omission_tfr.svg"),
                         ncol=1, width=9.5 * 72)
    print(f"assembled -> {out}  {w:.1f} x {h:.1f} pt")

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "source": MAPS_NPZ,
        "context_groups": CONTEXT_GROUPS,
        "pairs": PAIRS, "window_ms_re_p1": list(WIN_MS),
        "measure": "session-level dB (ratio summed across the group's 3 conditions in ratio "
                  "space, then log once); grand mean = mean of per-session dB maps, session "
                  "as the unit of inference",
        "n_sessions_by_pair_and_group": n_sessions_report,
    }
    with open(os.path.join(SVG_DIR, "fig04xx_receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"WROTE {SVG_DIR}/fig04xx_receipt.json")


if __name__ == "__main__":
    main()
