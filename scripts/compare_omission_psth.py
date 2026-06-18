"""
compare_omission_psth.py  (v2)
==============================
Compare peri-omission firing rate traces for stable omission neurons
in PFC/FEF (higher-order) vs V1/V2/V4/MT/V3d (lower-order).

Key addition: ISI boundary (1033 ms) marked to separate genuine
omission responses from next-event contamination.

Produces:
  outputs/spsam/psth_cache.npz                -- reusable cache (skip NWB on re-runs)
  outputs/spsam/fig_omission_area_comparison.html
"""

import glob, os, sys
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from scipy.ndimage import gaussian_filter1d
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Config ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = "outputs/spsam"
NWB_GLOB   = "D:/analysis/nwb/*.nwb"
CACHE_PATH = f"{OUTPUT_DIR}/psth_cache.npz"

PRE_S    = 0.6    # s before omission
POST_S   = 1.1    # s after omission (slightly beyond ISI for context)
BIN_S    = 0.010  # 10 ms bins
SMOOTH_SIGMA_MS = 40   # Gaussian σ in ms
ISI_MS   = 1033.0      # inter-stimulus interval (empirical)

HIGHER_ORDER = {"PFC", "FEF"}
LOWER_ORDER  = {"V1", "V2", "V4", "MT", "V3d"}

# Madelane Golden Dark palette
COL_HIGHER = "#9400D3"
COL_LOWER  = "#CFB87C"
COL_BG     = "#FFFFFF"
COL_GRID   = "#EBEBEB"
COL_TEXT   = "#1a1a1a"
COL_ISI    = "#888888"
COL_CONTAM = "#FF4444"
COL_OM_LINE = "#D32F2F"

AREA_COLORS = {
    "FEF": "#7B00C8", "PFC": "#C060F0",
    "V1":  "#C48A00", "V2":  "#CFB87C",
    "V4":  "#A07840", "MT":  "#7A5B30", "V3d": "#5A4020",
}

BINS     = np.arange(-PRE_S, POST_S + BIN_S, BIN_S)
BIN_CTRS = (BINS[:-1] + BINS[1:]) / 2
N_BINS   = len(BIN_CTRS)
T_MS     = BIN_CTRS * 1000
SIGMA_BINS = (SMOOTH_SIGMA_MS / 1000) / BIN_S


# ── NWB helpers ──────────────────────────────────────────────────────────────
def get_nwb_map():
    m = {}
    for f in sorted(glob.glob(NWB_GLOB)):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m


def get_omission_onsets(nwb):
    if "omission_glo_passive" not in nwb.intervals:
        return np.array([])
    idf = nwb.intervals["omission_glo_passive"].to_dataframe()
    for col in ("correct", "is_omission", "stimulus_number"):
        idf[col] = pd.to_numeric(idf[col], errors="coerce")
    om = idf[
        (idf["correct"] == 1.0) &
        idf["stimulus_number"].isin([3.0, 4.0, 5.0]) &
        (idf["is_omission"] == 1.0)
    ]
    return om["start_time"].values


def compute_psth(spike_times, event_times):
    """Return smoothed firing rate (Hz) array."""
    psth = np.zeros(N_BINS)
    for t0 in event_times:
        c, _ = np.histogram(spike_times - t0, bins=BINS)
        psth += c
    n = len(event_times)
    if n == 0:
        return np.zeros(N_BINS)
    return gaussian_filter1d(psth / (n * BIN_S), sigma=SIGMA_BINS)


# ── Cache layer ───────────────────────────────────────────────────────────────
def build_cache(meta, nwb_map):
    """Read all NWBs, compute PSTHs, save to .npz cache."""
    stable_om = meta[(meta["is_stable"]) & (meta["group"] == "omission")].copy()
    records = []
    for sid, grp in stable_om.groupby("session_id"):
        sid_str = str(sid)
        if sid_str not in nwb_map:
            print(f"  [{sid}] NWB missing — skip")
            continue
        print(f"  [{sid}] Loading NWB ({len(grp)} units)...")
        with NWBHDF5IO(nwb_map[sid_str], "r") as io:
            nwb = io.read()
            om_onsets = get_omission_onsets(nwb)
            if len(om_onsets) == 0:
                print(f"  [{sid}] No omission events — skip")
                continue
            nwb_u = nwb.units.to_dataframe()
            nwb_u["_cid"] = pd.to_numeric(
                nwb_u["cluster_id"], errors="coerce"
            ).astype("Int64")
        for _, row in grp.iterrows():
            match = nwb_u[nwb_u["_cid"] == int(row["unit_id"])]
            if match.empty:
                continue
            spk = np.asarray(match.iloc[0]["spike_times"])
            rate = compute_psth(spk, om_onsets)
            records.append({
                "unit_id":    int(row["unit_id"]),
                "session_id": int(sid),
                "area":       row["area"],
                "wf_class":   row["waveform_class"],
                "n_events":   len(om_onsets),
                "rate":       rate,
            })
    print(f"Collected {len(records)} unit PSTHs")
    # Save
    np.savez(
        CACHE_PATH,
        unit_ids   = np.array([r["unit_id"]    for r in records]),
        session_ids= np.array([r["session_id"] for r in records]),
        areas      = np.array([r["area"]       for r in records]),
        wf_classes = np.array([r["wf_class"]   for r in records]),
        n_events   = np.array([r["n_events"]   for r in records]),
        rates      = np.array([r["rate"]       for r in records]),   # (N, N_BINS)
        t_ms       = T_MS,
    )
    print(f"Cache saved -> {CACHE_PATH}")
    return records


def load_cache():
    data = np.load(CACHE_PATH, allow_pickle=True)
    records = []
    for i in range(len(data["unit_ids"])):
        records.append({
            "unit_id":    int(data["unit_ids"][i]),
            "session_id": int(data["session_ids"][i]),
            "area":       str(data["areas"][i]),
            "wf_class":   str(data["wf_classes"][i]),
            "n_events":   int(data["n_events"][i]),
            "rate":       data["rates"][i],
        })
    print(f"Loaded {len(records)} unit PSTHs from cache")
    return records


# ── Stats helpers ─────────────────────────────────────────────────────────────
def group_stats(recs):
    mat = np.array([r["rate"] for r in recs])
    return mat.mean(axis=0), mat.std(axis=0) / np.sqrt(len(mat)), mat


# ── Figure builder ────────────────────────────────────────────────────────────
def build_figure(records):
    higher_recs = [r for r in records if r["area"] in HIGHER_ORDER]
    lower_recs  = [r for r in records if r["area"] in LOWER_ORDER]

    h_mean, h_sem, h_mat = group_stats(higher_recs)
    l_mean, l_sem, l_mat = group_stats(lower_recs)

    area_stats = {}
    all_areas = sorted({r["area"] for r in records})
    for area in all_areas:
        arecs = [r for r in records if r["area"] == area]
        if arecs:
            area_stats[area] = (*group_stats(arecs), len(arecs))

    # Print summary
    print("\n=== Early (0–600 ms) vs Late (>1033 ms) peak analysis ===")
    for area in sorted(area_stats.keys()):
        am, ase, amat, n = area_stats[area]
        bl = am[T_MS < -100].mean()
        early_mask = (T_MS >= 0) & (T_MS <= 600)
        late_mask  = (T_MS >  ISI_MS)
        e_peak = am[early_mask].max()
        e_t    = T_MS[early_mask][am[early_mask].argmax()]
        flag   = " [NEXT-EVENT CONTAMINATION]" if am[late_mask].max() > e_peak else " [EARLY GENUINE]"
        print(f"  {area:4s} N={n:2d}  baseline={bl:.1f}  early_peak=+{e_peak-bl:.1f}Hz@{e_t:.0f}ms{flag}")

    t = T_MS

    # ── Layout: 2 rows × 3 cols ───────────────────────────────────────────
    fig = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            f"<b>Higher-Order (PFC + FEF)</b>  N={len(higher_recs)}",
            f"<b>Lower-Order (V1/V2/V4/MT/V3d)</b>  N={len(lower_recs)}",
            "<b>Overlay Comparison</b>",
            "<b>Per-Area: PFC & FEF</b>",
            "<b>Per-Area: V1 & V2</b>",
            "<b>Per-Area: V4, MT & V3d</b>",
        ],
        vertical_spacing=0.18,
        horizontal_spacing=0.07,
    )

    def add_shaded(fig, mean, sem, color, name, row, col, showleg=True, lw=2.5, dash="solid"):
        fig.add_trace(go.Scatter(
            x=np.concatenate([t, t[::-1]]),
            y=np.concatenate([mean + sem, (mean - sem)[::-1]]),
            fill="toself", fillcolor=color,
            opacity=0.15, line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ), row=row, col=col)
        fig.add_trace(go.Scatter(
            x=t, y=mean, mode="lines",
            line=dict(color=color, width=lw, dash=dash),
            name=name, showlegend=showleg,
            hovertemplate="%{y:.1f} Hz @ %{x:.0f} ms<extra>" + name + "</extra>",
        ), row=row, col=col)

    def add_individual(fig, mat, color, row, col):
        for i in range(min(len(mat), 40)):
            fig.add_trace(go.Scatter(
                x=t, y=mat[i], mode="lines",
                line=dict(color=color, width=0.7),
                opacity=0.10, showlegend=False, hoverinfo="skip",
            ), row=row, col=col)

    # Row 1: group-level panels
    add_individual(fig, h_mat, COL_HIGHER, row=1, col=1)
    add_shaded(fig, h_mean, h_sem, COL_HIGHER, "PFC+FEF", row=1, col=1)

    add_individual(fig, l_mat, COL_LOWER, row=1, col=2)
    add_shaded(fig, l_mean, l_sem, COL_LOWER, "V1/V2/V4/MT/V3d", row=1, col=2)

    add_shaded(fig, h_mean, h_sem, COL_HIGHER, "PFC+FEF",         row=1, col=3, showleg=True)
    add_shaded(fig, l_mean, l_sem, COL_LOWER,  "V1/V2/V4/MT/V3d", row=1, col=3, showleg=False)

    # Row 2: per-area panels
    area_groups = [
        (["PFC", "FEF"],     2, 1),
        (["V1",  "V2"],      2, 2),
        (["V4",  "MT","V3d"], 2, 3),
    ]
    for area_list, row, col in area_groups:
        first = True
        for area in area_list:
            if area not in area_stats:
                continue
            am, ase, amat, n = area_stats[area]
            add_shaded(fig, am, ase, AREA_COLORS[area],
                       f"{area} (N={n})", row=row, col=col, showleg=first)
            first = False

    # ── Decorators (omission onset line + ISI contamination zone) ────────
    for row in [1, 2]:
        for col in [1, 2, 3]:
            # Omission onset
            fig.add_vline(x=0, line_width=1.8, line_dash="dash",
                          line_color=COL_OM_LINE, row=row, col=col)
            # Omission-window shading (0 → ISI_MS)
            fig.add_vrect(x0=0, x1=ISI_MS, fillcolor="#FFEBEE",
                          opacity=0.25, line_width=0, row=row, col=col)
            # ISI boundary
            fig.add_vline(x=ISI_MS, line_width=1.2, line_dash="dot",
                          line_color=COL_ISI, row=row, col=col)

    # ── Axis style ────────────────────────────────────────────────────────
    axis_kw = dict(
        showgrid=True, gridcolor=COL_GRID, gridwidth=1,
        zeroline=False,
        tickfont=dict(size=10, color=COL_TEXT),
        title_font=dict(size=11, color=COL_TEXT),
    )
    for r in [1, 2]:
        for c in [1, 2, 3]:
            fig.update_xaxes(
                title_text="Time from omission onset (ms)" if r == 2 else "",
                range=[-600, POST_S * 1000],
                **axis_kw, row=r, col=c,
            )
            fig.update_yaxes(
                title_text="Firing rate (Hz)" if c == 1 else "",
                **axis_kw, row=r, col=c,
            )

    # ── Global layout ─────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                "<b>Stable Omission Neurons — Higher-Order vs Lower-Order Areas</b>"
                "<br><sup>Gaussian-smoothed PSTHs (σ=40 ms) | Dashed red = omission onset | "
                "Dotted grey = ISI boundary (1033 ms, next event) | Pink = omission window | "
                "Shading = ±SEM | Thin lines = individual units</sup>"
            ),
            font=dict(size=14, color=COL_TEXT), x=0.5, xanchor="center",
        ),
        paper_bgcolor=COL_BG, plot_bgcolor=COL_BG,
        font=dict(family="Inter, Arial, sans-serif", color=COL_TEXT),
        legend=dict(
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor=COL_GRID, borderwidth=1,
            font=dict(size=10), tracegroupgap=4,
        ),
        height=720, width=1350,
        margin=dict(t=100, b=55, l=65, r=30),
    )
    for ann in fig.layout.annotations:
        ann.font.update(size=11, color=COL_TEXT)

    out = f"{OUTPUT_DIR}/fig_omission_area_comparison.html"
    fig.write_html(out)
    print(f"\nFigure saved -> {out}")


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    meta = pd.read_csv(f"{OUTPUT_DIR}/grand_unit_metadata.csv")
    nwb_map = get_nwb_map()

    force_rebuild = "--rebuild" in sys.argv
    if os.path.exists(CACHE_PATH) and not force_rebuild:
        records = load_cache()
    else:
        print("Building PSTH cache from NWB files...")
        records = build_cache(meta, nwb_map)

    build_figure(records)


if __name__ == "__main__":
    main()
