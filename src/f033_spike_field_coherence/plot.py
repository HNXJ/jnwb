import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from src.analysis.visualization.plotting import OmissionPlotter
from src.analysis.io.logger import log

def plot_spike_field_coherence(results: dict, output_dir: str):
    """
    Plots grouped bar charts with error bars for Theta and Gamma1 PLV
    across areas and contexts (baseline, standard, flash, omission).
    """
    # Create subplots: 1 row, 2 cols (Theta on left, Gamma on right)
    fig = make_subplots(
        rows=1, cols=2,
        subplot_titles=("<b>Theta PLV (4-8 Hz)</b>", "<b>Gamma PLV (35-50 Hz)</b>"),
        horizontal_spacing=0.15
    )
    
    contexts = ["baseline", "standard", "flash", "omission"]
    context_colors = {
        "baseline": "#7F7F7F",  # Gray
        "standard": "#CFB87C",  # Gold
        "flash": "#D3D3D3",     # Light Gray
        "omission": "#9400D3"   # Violet
    }
    
    areas = sorted(list(results.keys()))
    
    for context in contexts:
        theta_means = []
        theta_sems = []
        gamma_means = []
        gamma_sems = []
        
        for area in areas:
            if context in results[area]:
                theta_means.append(results[area][context]["theta"]["mean"])
                theta_sems.append(results[area][context]["theta"]["sem"])
                gamma_means.append(results[area][context]["gamma1"]["mean"])
                gamma_sems.append(results[area][context]["gamma1"]["sem"])
            else:
                theta_means.append(0.0)
                theta_sems.append(0.0)
                gamma_means.append(0.0)
                gamma_sems.append(0.0)
                
        color = context_colors[context]
        
        # Add Theta trace (Col 1)
        fig.add_trace(
            go.Bar(
                x=areas, y=theta_means,
                error_y=dict(type='data', array=theta_sems, visible=True, thickness=1.5, color='#000000'),
                name=context.capitalize(),
                marker_color=color,
                legendgroup=context,
                showlegend=True
            ),
            row=1, col=1
        )
        
        # Add Gamma trace (Col 2)
        fig.add_trace(
            go.Bar(
                x=areas, y=gamma_means,
                error_y=dict(type='data', array=gamma_sems, visible=True, thickness=1.5, color='#000000'),
                name=context.capitalize(),
                marker_color=color,
                legendgroup=context,
                showlegend=False
            ),
            row=1, col=2
        )
        
    fig.update_layout(
        title=dict(
            text="<b>Figure 33: Context-Specific Spike-LFP Coupling (PLV)</b><br><sup>PLV Strength by Cortical Area across contexts (Theta vs. Gamma)</sup>",
            x=0.5, xanchor='center',
            font=dict(family="Arial", size=18, color="#000000")
        ),
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="center",
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#000000",
            borderwidth=1
        ),
        margin=dict(l=80, r=40, t=120, b=80),
        modebar_add=['toImage']
    )
    
    fig.update_yaxes(title_text="PLV Strength", row=1, col=1)
    fig.update_yaxes(title_text="PLV Strength", row=1, col=2)
    fig.update_xaxes(title_text="Cortical Area", row=1, col=1)
    fig.update_xaxes(title_text="Cortical Area", row=1, col=2)
    
    # Save using standard output flow
    import os
    os.makedirs(output_dir, exist_ok=True)
    html_file = os.path.join(output_dir, "fig33_spike_field_coherence.html")
    config = {'toImageButtonOptions': {'format': 'svg', 'filename': 'fig33_sfc', 'height': 800, 'width': 1000, 'scale': 2}}
    fig.write_html(html_file, include_plotlyjs="cdn", config=config)
    log.progress(f"Saved interactive HTML: {html_file}")
    
    # Save to canonical registry destination
    global_output_dir = "../outputs/oglo-8figs"
    os.makedirs(global_output_dir, exist_ok=True)
    global_html_file = os.path.join(global_output_dir, "fig33_spike_field_coherence.html")
    fig.write_html(global_html_file, include_plotlyjs="cdn", config=config)
    log.progress(f"Saved interactive HTML: {global_html_file}")
