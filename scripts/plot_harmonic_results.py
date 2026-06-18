"""
plot_harmonic_results.py
========================
Generates interactive visualizations of the LFP-to-LFP and Spiking-to-LFP
harmonic analysis results.

Output: outputs/harmonic/harmonic_dashboard.html
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

OUTPUT_DIR = "outputs/harmonic"
IN_LFP_LFP = f"{OUTPUT_DIR}/lfp_lfp_harmonic.csv"
IN_SPK_LFP = f"{OUTPUT_DIR}/spk_lfp_harmonic.csv"
OUT_HTML   = f"{OUTPUT_DIR}/harmonic_dashboard.html"

# Aesthetic variables
BG  = "#FFFFFF"
GRID = "#EBEBEB"
TXT = "#1a1a1a"
FONT = "Inter, Arial, sans-serif"

# Colors
CTX_COLOR = {
    "baseline": "#9E9E9E",
    "standard": "#CFB87C",  # Gold (Target/Sinks)
    "omission": "#9400D3"   # Violet (Source/Omission)
}

def layout_base():
    return dict(paper_bgcolor=BG, plot_bgcolor=BG,
                font=dict(family=FONT, color=TXT, size=11),
                margin=dict(t=80, b=50, l=55, r=20))

def axis_style(**kw):
    return dict(showgrid=True, gridcolor=GRID, gridwidth=1,
                zeroline=False, tickfont=dict(size=9), **kw)

def main():
    if not os.path.exists(IN_LFP_LFP) or not os.path.exists(IN_SPK_LFP):
        print("Error: Input files not found.")
        return
        
    df_lfp = pd.read_csv(IN_LFP_LFP)
    df_spk = pd.read_csv(IN_SPK_LFP)
    
    # Check if we have data to plot
    if len(df_lfp) == 0:
        print("Error: LFP-LFP harmonic data is empty.")
        return

    # Create multi-panel dashboard
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "<b>Fig A: LFP-to-LFP Phase-Amplitude Coupling (PAC)</b>",
            "<b>Fig B: LFP-to-LFP n:m Harmonic Phase Synchronization</b>",
            "<b>Fig C: Spike-to-LFP Coupling (PLV) per Area</b>",
            "<b>Fig D: Spike-LFP Harmonic Coupling Spectrum</b>"
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.12
    )

    # ------------------------------------------------------------------
    # Fig A: LFP-to-LFP PAC (Theta-Gamma PAC Modulation Index)
    # ------------------------------------------------------------------
    # Group by area and context
    pac_mean = df_lfp.groupby(["area", "context"])["pac_mi"].mean().unstack()
    areas = pac_mean.index.tolist()
    
    for ctx in ["baseline", "standard", "omission"]:
        if ctx in pac_mean.columns:
            fig.add_trace(
                go.Bar(
                    x=areas,
                    y=pac_mean[ctx],
                    name=f"PAC: {ctx.capitalize()}",
                    marker_color=CTX_COLOR[ctx],
                    legendgroup="context",
                    showlegend=True
                ),
                row=1, col=1
            )
            
    # ------------------------------------------------------------------
    # Fig B: LFP-to-LFP n:m Phase-Phase Synchronization
    # ------------------------------------------------------------------
    # Plot line spectrum across harmonics (h2, h3, h4, h5) per context (averaged over channels)
    harmonics = ["h2", "h3", "h4", "h5"]
    harmonic_labels = ["h2 (1:2)", "h3 (1:3)", "h4 (1:4)", "h5 (1:5)"]
    
    for ctx in ["baseline", "standard", "omission"]:
        ctx_df = df_lfp[df_lfp["context"] == ctx]
        if len(ctx_df) > 0:
            means = [ctx_df[f"{h}_plv"].mean() for h in harmonics]
            sems = [ctx_df[f"{h}_plv"].sem() for h in harmonics]
            
            fig.add_trace(
                go.Scatter(
                    x=harmonic_labels,
                    y=means,
                    mode="lines+markers",
                    name=f"n:m Sync: {ctx.capitalize()}",
                    line=dict(color=CTX_COLOR[ctx], width=3),
                    marker=dict(size=8),
                    error_y=dict(type="data", array=sems, visible=True),
                    legendgroup="context",
                    showlegend=False
                ),
                row=1, col=2
            )
            
    # ------------------------------------------------------------------
    # Fig C: Spiking-to-LFP Coupling (PLV) per Area (Theta PLV)
    # ------------------------------------------------------------------
    spk_mean = df_spk.groupby(["area", "context"])["theta_plv"].mean().unstack()
    spk_areas = spk_mean.index.tolist()
    
    for ctx in ["baseline", "standard", "omission"]:
        if ctx in spk_mean.columns:
            fig.add_trace(
                go.Bar(
                    x=spk_areas,
                    y=spk_mean[ctx],
                    name=f"Spk-LFP: {ctx.capitalize()}",
                    marker_color=CTX_COLOR[ctx],
                    legendgroup="context",
                    showlegend=False
                ),
                row=2, col=1
            )
            
    # ------------------------------------------------------------------
    # Fig D: Spike-LFP Harmonic Coupling Spectrum
    # ------------------------------------------------------------------
    # Plot PLV across theta + harmonics (h2, h3, h4, h5)
    bands = ["theta", "h2", "h3", "h4", "h5"]
    band_labels = ["Theta (Fund)", "h2 (1:2)", "h3 (1:3)", "h4 (1:4)", "h5 (1:5)"]
    
    for ctx in ["baseline", "standard", "omission"]:
        ctx_df = df_spk[df_spk["context"] == ctx]
        if len(ctx_df) > 0:
            means = [ctx_df[f"{b}_plv"].mean() for b in bands]
            sems = [ctx_df[f"{b}_plv"].sem() for b in bands]
            
            fig.add_trace(
                go.Scatter(
                    x=band_labels,
                    y=means,
                    mode="lines+markers",
                    name=f"Spk Spectrum: {ctx.capitalize()}",
                    line=dict(color=CTX_COLOR[ctx], width=3, dash="dash"),
                    marker=dict(size=8, symbol="diamond"),
                    error_y=dict(type="data", array=sems, visible=True),
                    legendgroup="context",
                    showlegend=False
                ),
                row=2, col=2
            )

    # Styling axes
    fig.update_xaxes(axis_style(title="Brain Area"), row=1, col=1)
    fig.update_yaxes(axis_style(title="Tort MI (PAC)"), row=1, col=1)
    
    fig.update_xaxes(axis_style(title="Harmonic Frequency"), row=1, col=2)
    fig.update_yaxes(axis_style(title="n:m Phase PLV"), row=1, col=2)
    
    fig.update_xaxes(axis_style(title="Brain Area"), row=2, col=1)
    fig.update_yaxes(axis_style(title="Theta Spike-LFP PLV"), row=2, col=1)
    
    fig.update_xaxes(axis_style(title="Harmonic Band"), row=2, col=2)
    fig.update_yaxes(axis_style(title="Spike-LFP PLV"), row=2, col=2)

    # Master Layout
    fig.update_layout(
        **layout_base(),
        title=dict(
            text="<b>HARMONIC INTERACTION DASHBOARD (High SNR Channels)</b>",
            font=dict(size=16, color=TXT, family=FONT)
        ),
        barmode="group",
        height=850,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1.0
        )
    )

    fig.write_html(OUT_HTML, include_plotlyjs="cdn")
    print(f"Harmonic dashboard written to {OUT_HTML}")

if __name__ == "__main__":
    main()
