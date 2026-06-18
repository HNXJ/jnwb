"""
spsam_dashboard.py
==================
Generates a comprehensive SpSAM results dashboard:

  Fig 1  – PLV heatmap: Area × Band per Context (4 panels)
  Fig 2  – Omission delta: PLV(omission) - PLV(baseline) per Area × Band
  Fig 3  – Per-context band profiles by Area (line plots)
  Fig 4  – Per-Layer PLV profiles across bands (Superficial / Middle / Deep)
  Fig 5  – Area × Layer heatmap for each frequency band
  Fig 6  – Group comparison (omission / stim+ / stim-) per band
  Fig 7  – Waveform class (Narrow vs Wide) per area and context
  Fig 8  – Unit-count and stability overview table

All figures use STABLE units only (is_stable == True).
Output: outputs/spsam/spsam_dashboard.html
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.io as pio

# ── Config ───────────────────────────────────────────────────────────────────
OUTPUT_DIR = "outputs/spsam"
OUT_HTML   = f"{OUTPUT_DIR}/spsam_dashboard.html"

BANDS      = ["theta", "alpha", "beta1", "beta2", "gamma1", "gamma2", "gamma3"]
BAND_COLS  = [f"{b}_plv" for b in BANDS]
BAND_LABELS= ["θ (4–8)", "α (8–12)", "β1 (12–20)", "β2 (20–30)",
              "γ1 (30–50)", "γ2 (50–80)", "γ3 (80–120)"]
CONTEXTS   = ["baseline", "standard", "flash", "omission"]
CTX_LABEL  = {"baseline": "Baseline", "standard": "Standard",
              "flash": "Flash", "omission": "Omission"}
CTX_COLOR  = {"baseline": "#9E9E9E", "standard": "#1565C0",
              "flash": "#F57C00", "omission": "#9400D3"}

HIER_ORDER = ["V1","V2","V3","V3a","V3d","V4","MT","MST","FST","TEO","FEF","PFC"]
LAYER_ORDER= ["Superficial (L2/3)", "Middle (L4)", "Deep (L5/L6)", "unresolved"]
LAYER_LABEL= {"Superficial (L2/3)": "Superficial (L2/3)",
              "Middle (L4)": "Middle (L4)",
              "Deep (L5/L6)": "Deep (L5/L6)",
              "unresolved": "Unresolved"}
LAYER_COLOR= {"Superficial (L2/3)": "#E53935",
              "Middle (L4)": "#7B1FA2",
              "Deep (L5/L6)": "#1565C0",
              "unresolved": "#9E9E9E"}

GROUP_COLOR= {"omission": "#9400D3", "stimulus_positive": "#CFB87C",
              "stimulus_negative": "#26A69A"}
WF_COLOR   = {"narrow": "#9400D3", "wide": "#CFB87C"}

BG  = "#FFFFFF"
GRID= "#EBEBEB"
TXT = "#1a1a1a"
FONT= "Inter, Arial, sans-serif"

def layout_base():
    return dict(paper_bgcolor=BG, plot_bgcolor=BG,
                font=dict(family=FONT, color=TXT, size=11),
                margin=dict(t=80, b=50, l=55, r=20))

def axis_style(**kw):
    return dict(showgrid=True, gridcolor=GRID, gridwidth=1,
                zeroline=False, tickfont=dict(size=9), **kw)


# ── Load data ────────────────────────────────────────────────────────────────
def load():
    uc = pd.read_csv(f"{OUTPUT_DIR}/grand_unit_lfp_coupling.csv")
    um = pd.read_csv(f"{OUTPUT_DIR}/grand_unit_metadata.csv")
    stable_uc = uc[uc["is_stable"]].copy()
    stable_um = um[um["is_stable"]].copy()
    # Ensure area ordering
    stable_uc["area"] = pd.Categorical(stable_uc["area"], categories=HIER_ORDER, ordered=True)
    stable_uc = stable_uc.sort_values("area")
    return stable_uc, stable_um


# ── Fig 1: PLV heatmap Area × Band per Context ───────────────────────────────
def fig_heatmap_area_band(df):
    """4-panel heatmap: rows=area (V1→PFC), cols=band, one panel per context."""
    fig = make_subplots(
        rows=1, cols=4,
        subplot_titles=[CTX_LABEL[c] for c in CONTEXTS],
        horizontal_spacing=0.04,
        shared_yaxes=True,
    )
    areas = [a for a in HIER_ORDER if a in df["area"].unique()]
    vmin, vmax = 0.10, 0.25

    for ci, ctx in enumerate(CONTEXTS):
        sub = df[df["context"] == ctx]
        z = []
        for area in areas:
            row_vals = []
            a_df = sub[sub["area"] == area]
            for bc in BAND_COLS:
                row_vals.append(a_df[bc].mean() if len(a_df) else np.nan)
            z.append(row_vals)
        z = np.array(z)

        hm = go.Heatmap(
            z=z, x=BAND_LABELS, y=areas,
            colorscale=[
                [0.0, "#E3F2FD"], [0.3, "#64B5F6"],
                [0.6, "#1976D2"], [0.85, "#9400D3"],
                [1.0, "#4A0080"],
            ],
            zmin=vmin, zmax=vmax,
            colorbar=dict(
                title=dict(text="PLV", font=dict(size=10)),
                thickness=12, len=0.7, x=1.01, y=0.5,
                tickfont=dict(size=9),
            ) if ci == 3 else dict(showticklabels=False, thickness=0),
            showscale=(ci == 3),
            hovertemplate="Area: %{y}<br>Band: %{x}<br>PLV: %{z:.3f}<extra></extra>",
        )
        fig.add_trace(hm, row=1, col=ci+1)

    fig.update_layout(
        title=dict(text="<b>Fig 1 — Spike-LFP Coupling (PLV) by Area × Band × Context</b>"
                        "<br><sup>Stable units only · Colour scale: PLV 0.10–0.25 · Hierarchy: V1 (bottom) → PFC (top)</sup>",
                   font=dict(size=13), x=0.5),
        height=460, width=1350,
        **layout_base(),
    )
    for i in range(1, 5):
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=8), row=1, col=i)
    return fig


# ── Fig 2: Omission delta (omission − baseline) ──────────────────────────────
def fig_omission_delta(df):
    areas = [a for a in HIER_ORDER if a in df["area"].unique()]
    baseline = df[df["context"]=="baseline"].groupby("area", observed=True)[BAND_COLS].mean()
    omission = df[df["context"]=="omission"].groupby("area", observed=True)[BAND_COLS].mean()
    delta = (omission - baseline).reindex(areas)

    fig = make_subplots(rows=1, cols=1)
    fig.add_trace(go.Heatmap(
        z=delta.values, x=BAND_LABELS, y=list(delta.index),
        colorscale=[
            [0.0, "#B71C1C"], [0.35, "#EF5350"],
            [0.5, "#F5F5F5"],
            [0.65, "#7E57C2"], [1.0, "#4A0080"],
        ],
        zmid=0,
        colorbar=dict(title=dict(text="ΔPLV", font=dict(size=10)), thickness=14, tickfont=dict(size=9)),
        hovertemplate="Area: %{y}<br>Band: %{x}<br>ΔPLV: %{z:.4f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text="<b>Fig 2 — Omission Delta: PLV(Omission) − PLV(Baseline)</b>"
                        "<br><sup>Stable units · Red = suppressed at omission · Purple = enhanced at omission</sup>",
                   font=dict(size=13), x=0.5),
        height=400, width=800,
        xaxis=axis_style(title="Frequency Band"),
        yaxis=axis_style(title="Area (V1→PFC hierarchy)"),
        **layout_base(),
    )
    return fig


# ── Fig 3: Band profiles by Area across contexts ─────────────────────────────
def fig_band_profiles_by_area(df):
    areas = [a for a in HIER_ORDER if a in df["area"].unique()]
    n_areas = len(areas)
    ncols = 4
    nrows = int(np.ceil(n_areas / ncols))

    fig = make_subplots(
        rows=nrows, cols=ncols,
        subplot_titles=areas,
        shared_xaxes=True, shared_yaxes=False,
        vertical_spacing=0.10, horizontal_spacing=0.06,
    )
    x_pos = list(range(len(BAND_LABELS)))

    for ai, area in enumerate(areas):
        r = ai // ncols + 1
        c = ai %  ncols + 1
        a_df = df[df["area"] == area]
        for ctx in CONTEXTS:
            ctx_df = a_df[a_df["context"] == ctx]
            if len(ctx_df) == 0:
                continue
            means = [ctx_df[bc].mean() for bc in BAND_COLS]
            sems  = [ctx_df[bc].sem()  for bc in BAND_COLS]
            fig.add_trace(go.Scatter(
                x=BAND_LABELS, y=means,
                error_y=dict(type="data", array=sems, visible=True, thickness=1.2, width=3),
                mode="lines+markers",
                line=dict(color=CTX_COLOR[ctx], width=1.8),
                marker=dict(size=5),
                name=CTX_LABEL[ctx],
                showlegend=(ai == 0),
                legendgroup=ctx,
                hovertemplate=f"{area}/{CTX_LABEL[ctx]}<br>%{{x}}: %{{y:.3f}}<extra></extra>",
            ), row=r, col=c)

        n_units = a_df["unit_id"].nunique()
        fig.update_xaxes(tickangle=-40, tickfont=dict(size=7), row=r, col=c)
        fig.update_yaxes(title_text="PLV" if c==1 else "",
                         tickfont=dict(size=8), showgrid=True, gridcolor=GRID, row=r, col=c)

    fig.update_layout(
        title=dict(text="<b>Fig 3 — PLV Spectral Profiles by Area × Context</b>"
                        "<br><sup>Stable units · Mean ± SEM · Hierarchy: V1 → PFC</sup>",
                   font=dict(size=13), x=0.5),
        height=420 * nrows, width=1350,
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0.5, xanchor="center",
                    font=dict(size=10), bgcolor="rgba(255,255,255,0.9)"),
        **{**layout_base(), "margin": dict(t=100, b=60, l=60, r=20)},

    )
    return fig


# ── Fig 4: Per-layer band profiles ───────────────────────────────────────────
def fig_layer_profiles(df):
    layers = [l for l in LAYER_ORDER if l in df["layer"].unique()]
    fig = go.Figure()
    for ctx in CONTEXTS:
        ctx_df = df[df["context"] == ctx]
        for lyr in layers:
            l_df = ctx_df[ctx_df["layer"] == lyr]
            if len(l_df) < 5:
                continue
            means = [l_df[bc].mean() for bc in BAND_COLS]
            sems  = [l_df[bc].sem()  for bc in BAND_COLS]
            lbl = LAYER_LABEL[lyr]
            fig.add_trace(go.Scatter(
                x=BAND_LABELS, y=means,
                error_y=dict(type="data", array=sems, visible=True, thickness=1, width=3),
                mode="lines+markers",
                line=dict(color=LAYER_COLOR[lyr], width=2,
                          dash={"baseline":"dot","standard":"solid",
                                "flash":"dash","omission":"longdash"}[ctx]),
                marker=dict(size=5, symbol={"baseline":"circle","standard":"square",
                                             "flash":"diamond","omission":"star"}[ctx]),
                name=f"{lbl} / {CTX_LABEL[ctx]}",
                hovertemplate=f"{lbl}/{CTX_LABEL[ctx]}: %{{x}} = %{{y:.3f}}<extra></extra>",
            ))

    fig.update_layout(
        title=dict(text="<b>Fig 4 — PLV Spectral Profiles by Layer × Context</b>"
                        "<br><sup>Stable units · Line style = Context · Color = Layer</sup>",
                   font=dict(size=13), x=0.5),
        xaxis=axis_style(title="Frequency Band", tickangle=-30),
        yaxis=axis_style(title="PLV", range=[0.10, 0.26]),
        legend=dict(font=dict(size=9), bgcolor="rgba(255,255,255,0.92)",
                    bordercolor=GRID, borderwidth=1),
        height=500, width=1000,
        **layout_base(),
    )
    return fig


# ── Fig 5: Area × Layer heatmap per band ─────────────────────────────────────
def fig_area_layer_heatmap(df):
    n_bands = len(BANDS)
    fig = make_subplots(
        rows=2, cols=4,
        subplot_titles=BAND_LABELS,
        horizontal_spacing=0.05, vertical_spacing=0.18,
    )
    areas  = [a for a in HIER_ORDER if a in df["area"].unique()]
    layers = [l for l in LAYER_ORDER if l in df["layer"].unique() and l != "unresolved"]

    omission_df = df[df["context"] == "omission"]
    vmin, vmax = 0.10, 0.22

    for bi, (band, bc) in enumerate(zip(BANDS, BAND_COLS)):
        r = bi // 4 + 1
        c = bi %  4 + 1
        z = []
        for area in areas:
            row_vals = []
            for lyr in layers:
                sub = omission_df[(omission_df["area"]==area) & (omission_df["layer"]==lyr)]
                row_vals.append(sub[bc].mean() if len(sub) >= 3 else np.nan)
            z.append(row_vals)
        fig.add_trace(go.Heatmap(
            z=np.array(z), x=[LAYER_LABEL[l].split(" ")[0] for l in layers], y=areas,
            colorscale=[[0,"#E3F2FD"],[0.4,"#64B5F6"],[0.7,"#1976D2"],[1,"#9400D3"]],
            zmin=vmin, zmax=vmax,
            colorbar=dict(title=dict(text="PLV", font=dict(size=9)),
                          thickness=10, len=0.4, x=1.01,
                          tickfont=dict(size=8)) if (bi == n_bands-1) else None,
            showscale=(bi == n_bands-1),
            hovertemplate="Area: %{y}<br>Layer: %{x}<br>PLV: %{z:.3f}<extra></extra>",
        ), row=r, col=c)
        fig.update_xaxes(tickfont=dict(size=8), row=r, col=c)
        fig.update_yaxes(tickfont=dict(size=8), row=r, col=c)

    fig.update_layout(
        title=dict(text="<b>Fig 5 — Area × Layer PLV Heatmap by Band (Omission Context)</b>"
                        "<br><sup>Stable units · Grey cells = fewer than 3 units</sup>",
                   font=dict(size=13), x=0.5),
        height=560, width=1350,
        **{**layout_base(), "margin": dict(t=90, b=50, l=65, r=60)},

    )
    return fig


# ── Fig 6: Group comparison per band ─────────────────────────────────────────
def fig_group_comparison(df):
    groups = [g for g in ["omission","stimulus_positive","stimulus_negative"]
              if g in df["group"].dropna().unique()]
    fig = make_subplots(
        rows=1, cols=4,
        subplot_titles=[CTX_LABEL[c] for c in CONTEXTS],
        shared_yaxes=True, horizontal_spacing=0.04,
    )
    for ci, ctx in enumerate(CONTEXTS):
        ctx_df = df[df["context"] == ctx]
        for grp in groups:
            g_df = ctx_df[ctx_df["group"] == grp]
            if len(g_df) == 0:
                continue
            means = [g_df[bc].mean() for bc in BAND_COLS]
            sems  = [g_df[bc].sem()  for bc in BAND_COLS]
            nice  = {"omission":"Omission neurons","stimulus_positive":"Stim+",
                     "stimulus_negative":"Stim−"}[grp]
            fig.add_trace(go.Scatter(
                x=BAND_LABELS, y=means,
                error_y=dict(type="data", array=sems, visible=True, thickness=1.2, width=3),
                mode="lines+markers",
                line=dict(color=GROUP_COLOR[grp], width=2.2),
                marker=dict(size=6),
                name=nice, showlegend=(ci == 0), legendgroup=grp,
                hovertemplate=f"{nice}/{CTX_LABEL[ctx]}: %{{x}} = %{{y:.3f}}<extra></extra>",
            ), row=1, col=ci+1)
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=8), row=1, col=ci+1)
        fig.update_yaxes(title_text="PLV" if ci==0 else "",
                         showgrid=True, gridcolor=GRID, tickfont=dict(size=9), row=1, col=ci+1)

    fig.update_layout(
        title=dict(text="<b>Fig 6 — PLV by Neuron Group × Context</b>"
                        "<br><sup>Stable units · Violet=Omission neurons, Gold=Stim+, Teal=Stim−</sup>",
                   font=dict(size=13), x=0.5),
        height=420, width=1350,
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", font=dict(size=10)),
        **layout_base(),
    )
    return fig


# ── Fig 7: Waveform class (Narrow vs Wide) ────────────────────────────────────
def fig_waveform_class(df):
    areas = [a for a in HIER_ORDER if a in df["area"].unique()]
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=["Baseline", "Standard", "Flash", "Omission"],
        shared_yaxes=True, shared_xaxes=True,
        horizontal_spacing=0.04, vertical_spacing=0.14,
    )
    for ci, ctx in enumerate(CONTEXTS):
        r = ci // 2 + 1
        c = ci %  2 + 1
        ctx_df = df[df["context"] == ctx]
        for wf in ["narrow", "wide"]:
            wf_df = ctx_df[ctx_df["wf_class"] == wf]
            means = [wf_df[bc].mean() for bc in BAND_COLS]
            sems  = [wf_df[bc].sem()  for bc in BAND_COLS]
            fig.add_trace(go.Scatter(
                x=BAND_LABELS, y=means,
                error_y=dict(type="data", array=sems, visible=True, thickness=1.2, width=3),
                mode="lines+markers",
                line=dict(color=WF_COLOR[wf], width=2.2),
                marker=dict(size=5),
                name=wf.capitalize(), showlegend=(ci == 0), legendgroup=wf,
                hovertemplate=f"{wf}/{ctx}: %{{x}} = %{{y:.3f}}<extra></extra>",
            ), row=r, col=c)
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=8), row=r, col=c)
        fig.update_yaxes(title_text="PLV" if c==1 else "",
                         showgrid=True, gridcolor=GRID, tickfont=dict(size=9), row=r, col=c)

    fig.update_layout(
        title=dict(text="<b>Fig 7 — PLV by Waveform Class (Narrow vs Wide) × Context</b>"
                        "<br><sup>Stable units · Violet = Narrow (putative interneurons) · Gold = Wide (putative pyramidal)</sup>",
                   font=dict(size=13), x=0.5),
        height=560, width=900,
        legend=dict(orientation="h", y=1.06, x=0.5, xanchor="center", font=dict(size=10)),
        **layout_base(),
    )
    return fig


# ── Fig 8: Omission-specific coupling by area (bar chart) ────────────────────
def fig_omission_coupling_bar(df):
    """Theta and gamma PLV during omission vs baseline per area — the key dissociation."""
    areas = [a for a in HIER_ORDER if a in df["area"].unique()]
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=["Theta (4–8 Hz)", "Gamma1 (30–50 Hz)"],
        shared_yaxes=False, horizontal_spacing=0.08,
    )
    for bi, (bc, band_label) in enumerate([("theta_plv","Theta"), ("gamma1_plv","Gamma1")]):
        col = bi + 1
        for ctx in ["baseline", "omission"]:
            ctx_df = df[df["context"] == ctx]
            means, sems, xs = [], [], []
            for area in areas:
                a_df = ctx_df[ctx_df["area"] == area]
                if len(a_df) < 3:
                    continue
                xs.append(area)
                means.append(a_df[bc].mean())
                sems.append(a_df[bc].sem())
            fig.add_trace(go.Bar(
                x=xs, y=means,
                error_y=dict(type="data", array=sems, visible=True, thickness=1.5, width=4),
                name=CTX_LABEL[ctx],
                marker_color=CTX_COLOR[ctx],
                opacity=0.85,
                showlegend=(bi == 0), legendgroup=ctx,
                hovertemplate=f"{CTX_LABEL[ctx]}: %{{x}} %{{y:.3f}}<extra></extra>",
            ), row=1, col=col)
        fig.update_xaxes(tickangle=-35, tickfont=dict(size=9), row=1, col=col)
        fig.update_yaxes(title_text="PLV" if col==1 else "",
                         showgrid=True, gridcolor=GRID, tickfont=dict(size=9), row=1, col=col)

    fig.update_layout(
        title=dict(text="<b>Fig 8 — Theta & Gamma1 PLV: Omission vs Baseline by Area</b>"
                        "<br><sup>Stable units · Grey=Baseline · Purple=Omission</sup>",
                   font=dict(size=13), x=0.5),
        height=440, width=1100,
        barmode="group",
        legend=dict(orientation="h", y=1.08, x=0.5, xanchor="center", font=dict(size=10)),
        **layout_base(),
    )
    return fig


# ── Assemble HTML dashboard ───────────────────────────────────────────────────
def assemble_html(figs, labels):
    """Write all figures into a single scrollable HTML page."""
    config = {"displayModeBar": True, "responsive": True,
              "toImageButtonOptions": {"format": "svg", "scale": 2}}

    nav_links = "\n".join(
        f'<a href="#fig{i+1}" style="margin:0 10px;color:#9400D3;text-decoration:none;font-weight:600">'
        f'Fig {i+1}: {lbl}</a>'
        for i, lbl in enumerate(labels)
    )

    fig_html = ""
    for i, (fig, lbl) in enumerate(zip(figs, labels)):
        html = pio.to_html(fig, full_html=False, config=config, include_plotlyjs=(i==0))
        fig_html += (
            f'<div id="fig{i+1}" style="margin:40px 0 10px 0;padding-top:60px">'
            f'<hr style="border:1px solid #EBEBEB;margin-bottom:20px">'
            f'{html}'
            f'</div>\n'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>SpSAM Results Dashboard</title>
<style>
  body {{ font-family: Inter, Arial, sans-serif; background: #FAFAFA; color: #1a1a1a; margin: 0; padding: 0; }}
  #nav {{ position: sticky; top: 0; background: rgba(255,255,255,0.97);
           border-bottom: 2px solid #9400D3; padding: 12px 24px; z-index: 999;
           display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }}
  #nav h2 {{ margin: 0 20px 0 0; font-size: 15px; color: #9400D3; white-space: nowrap; }}
  #main {{ max-width: 1400px; margin: 0 auto; padding: 20px 24px 80px; }}
  h3 {{ color: #4A0080; }}
</style>
</head>
<body>
<div id="nav">
  <h2>SpSAM Dashboard</h2>
  {nav_links}
</div>
<div id="main">
  <h3 style="margin-top:20px">SpSAM Spike-LFP Coupling Results — Stable Units Only</h3>
  <p style="color:#555;font-size:13px">
    N=627 stable units across 13 sessions · 7 frequency bands · 4 contexts ·
    Stable = C1 (≥5 spikes/trial) ∧ C2 (FR≥1Hz) ∧ C3 (PR≥0.98 OR SNR>0.75)
  </p>
  {fig_html}
</div>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print("Loading data...")
    stable_uc, stable_um = load()
    print(f"  Stable coupling rows: {len(stable_uc)}")
    print(f"  Stable units: {stable_uc['unit_id'].nunique()}")

    print("Building figures...")
    figs = [
        fig_heatmap_area_band(stable_uc),       # Fig 1
        fig_omission_delta(stable_uc),           # Fig 2
        fig_band_profiles_by_area(stable_uc),    # Fig 3
        fig_layer_profiles(stable_uc),           # Fig 4
        fig_area_layer_heatmap(stable_uc),       # Fig 5
        fig_group_comparison(stable_uc),         # Fig 6
        fig_waveform_class(stable_uc),           # Fig 7
        fig_omission_coupling_bar(stable_uc),    # Fig 8
    ]
    labels = [
        "Area × Band Heatmap",
        "Omission Delta",
        "Band Profiles by Area",
        "Layer Profiles",
        "Area × Layer Heatmap",
        "Group Comparison",
        "Waveform Class",
        "Theta & Gamma Bars",
    ]

    print("Assembling HTML dashboard...")
    html = assemble_html(figs, labels)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard saved -> {OUT_HTML}")


if __name__ == "__main__":
    main()
