"""
plot_coherence_results.py
==========================
Generates interactive HTML dashboard of cross-area LFP-to-LFP coherence results.
Output: outputs/coherence/coherence_dashboard.html
"""

import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

OUTPUT_DIR = "outputs/coherence"
RESULTS_CSV = f"{OUTPUT_DIR}/coherence_results.csv"
OUT_HTML   = f"{OUTPUT_DIR}/coherence_dashboard.html"

# Aesthetic variables
BG  = "#FFFFFF"
GRID = "#EBEBEB"
TXT = "#1a1a1a"
FONT = "Inter, Arial, sans-serif"

# Colors
EPOCH_COLOR = {
    "baseline": "#9E9E9E",  # Grey
    "stimulus": "#CFB87C",  # Gold (Target)
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
    if not os.path.exists(RESULTS_CSV):
        print("Error: Results CSV not found.")
        return
        
    df = pd.read_csv(RESULTS_CSV)
    
    # Compute averages across sessions
    avg_df = df.groupby(["area1", "area2", "epoch"])[[f"{b}_coherence" for b in ["theta", "alpha", "beta", "gamma"]]].mean().reset_index()
    avg_df["pair"] = avg_df["area1"] + "-" + avg_df["area2"]
    
    pairs = sorted(avg_df["pair"].unique())
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            "<b>Fig A: Theta-Band Coherence per Area Pair</b>",
            "<b>Fig B: Gamma-Band Coherence per Area Pair</b>",
            "<b>Fig C: Coherence Profile - V1-V2</b>",
            "<b>Fig D: Coherence Profile - MT-V4</b>"
        ],
        vertical_spacing=0.15,
        horizontal_spacing=0.12
    )
    
    # ------------------------------------------------------------------
    # Fig A: Theta-Band Coherence per Area Pair
    # ------------------------------------------------------------------
    for epoch in ["baseline", "stimulus", "omission"]:
        sub = avg_df[avg_df["epoch"] == epoch]
        fig.add_trace(
            go.Bar(
                x=sub["pair"],
                y=sub["theta_coherence"],
                name=f"Theta: {epoch.capitalize()}",
                marker_color=EPOCH_COLOR[epoch],
                legendgroup="epoch",
                showlegend=True
            ),
            row=1, col=1
        )
        
    # ------------------------------------------------------------------
    # Fig B: Gamma-Band Coherence per Area Pair
    # ------------------------------------------------------------------
    for epoch in ["baseline", "stimulus", "omission"]:
        sub = avg_df[avg_df["epoch"] == epoch]
        fig.add_trace(
            go.Bar(
                x=sub["pair"],
                y=sub["gamma_coherence"],
                name=f"Gamma: {epoch.capitalize()}",
                marker_color=EPOCH_COLOR[epoch],
                legendgroup="epoch",
                showlegend=False
            ),
            row=1, col=2
        )
        
    # ------------------------------------------------------------------
    # Fig C: Coherence Profile - V1-V2
    # ------------------------------------------------------------------
    bands = ["theta", "alpha", "beta", "gamma"]
    band_labels = ["Theta", "Alpha", "Beta", "Gamma"]
    
    for epoch in ["baseline", "stimulus", "omission"]:
        sub = avg_df[(avg_df["pair"] == "V1-V2") & (avg_df["epoch"] == epoch)]
        if len(sub) > 0:
            row = sub.iloc[0]
            vals = [row[f"{b}_coherence"] for b in bands]
            fig.add_trace(
                go.Scatter(
                    x=band_labels,
                    y=vals,
                    mode="lines+markers",
                    name=f"V1-V2: {epoch.capitalize()}",
                    line=dict(color=EPOCH_COLOR[epoch], width=3),
                    marker=dict(size=8),
                    legendgroup="epoch",
                    showlegend=False
                ),
                row=2, col=1
            )
            
    # ------------------------------------------------------------------
    # Fig D: Coherence Profile - MT-V4
    # ------------------------------------------------------------------
    for epoch in ["baseline", "stimulus", "omission"]:
        sub = avg_df[(avg_df["pair"] == "MT-V4") & (avg_df["epoch"] == epoch)]
        if len(sub) > 0:
            row = sub.iloc[0]
            vals = [row[f"{b}_coherence"] for b in bands]
            fig.add_trace(
                go.Scatter(
                    x=band_labels,
                    y=vals,
                    mode="lines+markers",
                    name=f"MT-V4: {epoch.capitalize()}",
                    line=dict(color=EPOCH_COLOR[epoch], width=3),
                    marker=dict(size=8),
                    legendgroup="epoch",
                    showlegend=False
                ),
                row=2, col=2
            )

    # Styling axes
    fig.update_xaxes(axis_style(title="Area Pair"), row=1, col=1)
    fig.update_yaxes(axis_style(title="Theta Coherence"), row=1, col=1)
    
    fig.update_xaxes(axis_style(title="Area Pair"), row=1, col=2)
    fig.update_yaxes(axis_style(title="Gamma Coherence"), row=1, col=2)
    
    fig.update_xaxes(axis_style(title="Frequency Band"), row=2, col=1)
    fig.update_yaxes(axis_style(title="Coherence"), row=2, col=1)
    
    fig.update_xaxes(axis_style(title="Frequency Band"), row=2, col=2)
    fig.update_yaxes(axis_style(title="Coherence"), row=2, col=2)

    # Master Layout
    fig.update_layout(
        **layout_base(),
        title=dict(
            text="<b>CROSS-AREA LFP-TO-LFP COHERENCE DASHBOARD (Responsive Channels)</b>",
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
    print(f"Coherence dashboard written to {OUT_HTML}")

if __name__ == "__main__":
    main()
