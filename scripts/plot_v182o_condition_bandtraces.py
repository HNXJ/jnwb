r"""
Supplement: V182o only -- five-band power traces in PFC, FEF, MT, TEO, V4, across RXRR (p2
omitted), RRXR (p3 omitted), RRRR (no omission), p1-aligned.

WHY THIS EXISTS
    User request, 2026-07-31: "visualize the TFR traces of five bands for V182o PFC, FEF, MT,
    TEO, V4, during RXRR and RRXR and RRRR, just as supplement." Every other condition-TFR
    figure in this repo (fig04, fig05) pools sessions ACROSS subjects; this filters the same
    extraction to ONE subject's own sessions, so the trace only reflects V182o.

REUSE, NOT REDERIVATION
    Estimator, baseline, band definitions, and the band-trace drawing routine itself
    (draw_condition_bandtrace) come directly from fig04_v1_pfc_condition_tfr.py -- this script
    only filters area_cond_sessions() to session_prefix.startswith("sub-V182o_") before calling
    it. Nothing about the dB computation is reimplemented.

DATA COVERAGE CAVEAT -- READ BEFORE CITING
    V182o has an UNEVEN number of TFR-ready sessions per area (session_readiness.csv, 4 of 10
    V182o sessions are suite_tfr_ready): PFC=2, FEF=4, MT=1, TEO=4, V4=2. MT's trace is a
    SINGLE SESSION, not a session-averaged statistic -- no SEM ribbon is drawn for it, and it
    is labelled "n=1 session" directly on the panel rather than presented on equal footing with
    the other four areas. RRXR (p3 omission) has fewer trials per session than RXRR (p2) in
    every area checked (~28-30 vs ~59-61 in PFC/FEF) -- expect a noisier RRXR trace even where
    the session count matches RXRR.

OUTPUT
    context/figures/supplements/figS_v182o_condition_bandtraces.png / .svg / .receipt.json
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

FIG04_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "context", "figures", "fig04_v1_pfc_condition_tfr")
sys.path.insert(0, os.path.abspath(FIG04_DIR))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                                "context", "figures"))
import fig04_v1_pfc_condition_tfr as fig04  # noqa: E402
from figstyle import mark_full_trial_axis  # noqa: E402

SUBJECT = "V182o"
AREAS = ["PFC", "FEF", "MT", "TEO", "V4"]
CONDITIONS = ["RXRR", "RRXR", "RRRR"]
COND_LABEL = {"RXRR": "RXRR (p2 omitted)", "RRXR": "RRXR (p3 omitted)", "RRRR": "RRRR (no omission)"}
COND_OMIT_SLOT = {"RXRR": 2, "RRXR": 3, "RRRR": None}
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                       "context", "figures", "supplements")


def subject_area_cond_sessions(maps, area, cond):
    """Same key scheme as fig04.area_cond_sessions(), filtered to this subject's own
    sessions only -- session_prefix looks like 'sub-V182o_ses-260629'."""
    return {k: v for k, v in fig04.area_cond_sessions(maps, area, cond).items()
            if k.startswith(f"sub-{SUBJECT}_")}


ZOOM_WIN = (300, 2400)   # zoomed on the omission window -- covers p2 omission (1031ms) and
                         # p3 omission (2062ms) with padding, tighter than the full -500..2593


def smooth_axis_lines(ax, win=5):
    """Quick post-hoc moving-average smoothing (50ms at 10ms bins) applied to the already-
    drawn band-trace lines -- user, 2026-07-31: 'smooth them.' SEM ribbons are left as drawn."""
    k = np.ones(win) / win
    for ln in ax.get_lines():
        y = ln.get_ydata()
        if len(y) >= win:
            ln.set_ydata(np.convolve(y, k, mode="same"))


def draw_single_session_bandtrace(ax, area, cond, sess, freqs, times, bands):
    """MT has exactly one V182o session -- no SEM is computable. Draw the same five band
    lines with no ribbon, and say so on the panel rather than implying a session average."""
    for (name, (lo, hi)), col in zip(bands.items(), fig04.BAND_COLORS):
        m = next(iter(sess.values()))
        r = fig04.band_ratio(m, freqs, lo, hi)
        ax.plot(times, fig04.to_db(r), color=col, lw=1.6, label=name, zorder=3)
    ax.axhline(0, color="black", lw=0.8)
    mark_full_trial_axis(ax, fig04.CONDITION_WIN, omit_slot=COND_OMIT_SLOT[cond])
    ax.set_title(f"{area}, {COND_LABEL[cond]}  (n=1 session, no SEM)", fontsize=9, color="0.25")
    ax.tick_params(labelsize=7)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    maps, freqs, times = fig04.load_condition_maps()
    bands = fig04.BANDSETS["manuscript"]

    fig, axes = plt.subplots(len(AREAS), len(CONDITIONS),
                             figsize=(4.6 * len(CONDITIONS), 2.6 * len(AREAS)))
    counts = {}
    for ri, area in enumerate(AREAS):
        for ci, cond in enumerate(CONDITIONS):
            ax = axes[ri, ci]
            sess = subject_area_cond_sessions(maps, area, cond)
            counts[f"{area}_{cond}"] = len(sess)
            if not sess:
                ax.text(0.5, 0.5, "no V182o data", ha="center", va="center",
                        transform=ax.transAxes, fontsize=9, color="0.5")
                ax.set_xticks([])
                ax.set_yticks([])
                continue
            if len(sess) == 1:
                draw_single_session_bandtrace(ax, area, cond, sess, freqs, times, bands)
            else:
                fig04.draw_condition_bandtrace(ax, area, cond, sess, freqs, times, bands, "")
                ax.set_title(f"{area}, {COND_LABEL[cond]}  (n={len(sess)} sessions)", fontsize=9)
            smooth_axis_lines(ax)
            ax.set_xlim(*ZOOM_WIN)
            if ci == 0:
                ax.set_ylabel("Power change (dB)", fontsize=8)
            if ri == len(AREAS) - 1:
                ax.set_xlabel("Time from p1 onset (ms)", fontsize=8)

    handles, labs = None, None
    for ax in axes.ravel():
        h, l = ax.get_legend_handles_labels()
        if h:
            handles, labs = h, l
            break
    if handles:
        fig.legend(handles, labs, fontsize=8, ncol=5, loc="upper center",
                  bbox_to_anchor=(0.5, 1.015), frameon=False)
    fig.suptitle(f"Subject {SUBJECT} only -- five-band power traces, p1-d1-p2-d2-p3, "
                f"baseline = middle of d1", fontsize=12, fontweight="bold", y=1.035)

    out = os.path.join(OUT_DIR, "figS_v182o_condition_bandtraces")
    fig.savefig(out + ".png", dpi=170, bbox_inches="tight")
    fig.savefig(out + ".svg", bbox_inches="tight")
    plt.close(fig)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "subject": SUBJECT, "areas": AREAS, "conditions": CONDITIONS,
        "maps": fig04.CONDITION_MAPS,
        "sessions_per_area_condition": counts,
        "measure": "ratio of expected power vs each channel's own middle-of-d1 baseline; "
                  "10*log10 applied once, after all averaging -- identical estimator to fig04",
        "single_session_areas": [k for k, v in counts.items() if v == 1],
        "zero_session_areas": [k for k, v in counts.items() if v == 0],
        "bands_hz": {k: list(v) for k, v in bands.items()},
        "window_ms_re_p1": list(fig04.CONDITION_WIN),
        "caveat": "MT has only 1 TFR-ready V182o session (of 4 total ready sessions covering "
                 "the other areas unevenly: PFC=2, FEF=4, TEO=4, V4=2) -- panels with n=1 "
                 "carry no SEM and are labelled as a single session, not a session average.",
        "env": {"python": platform.python_version(), "numpy": np.__version__,
                "matplotlib": matplotlib.__version__},
    }
    with open(out + ".receipt.json", "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print("sessions per area/condition:", counts)
    print("WROTE", out + ".png", out + ".svg", out + ".receipt.json")


if __name__ == "__main__":
    main()
