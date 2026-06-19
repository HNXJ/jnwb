import numpy as np
import plotly.graph_objects as go
from src.analysis.visualization.plotting import OmissionPlotter
from src.analysis.io.logger import log

def plot_spike_phase_locking(results: dict, output_dir: str):
    """
    Plots Spike-Field Phase Locking Value (PLV) spectrum comparing Narrow vs Wide
    units across Omission, Standard, and Baseline contexts.
    """
    plotter = OmissionPlotter(
        title="Figure 31: Spike-Field Phase Locking (PLV) Spectrum",
        x_label="Frequency",
        y_label="PLV Strength",
        subtitle="Narrow (Violet) vs Wide (Gold) coupling strength to local LFP across contexts.",
        x_unit="Hz",
        y_unit="PLV"
    )
    
    # Context styling map: solid for omission, dash for standard, dot for baseline
    context_styles = {
        "omission": {"dash": "solid", "width": 3},
        "standard": {"dash": "dash", "width": 2},
        "baseline": {"dash": "dot", "width": 2},
        "flash": {"dash": "dashdot", "width": 1.5}
    }
    
    # Class coloring map: violet for narrow, gold for wide
    class_colors = {
        "narrow": "#9400D3",
        "wide": "#CFB87C"
    }

    for context, wfs in results.items():
        if context not in context_styles:
            continue
        style = context_styles[context]
        
        for wf, data in wfs.items():
            freqs = data["freqs"]
            mean = data["plv_mean"]
            sem = data["plv_sem"]
            count = data["count"]
            color = class_colors[wf]
            
            trace_name = f"{context.capitalize()} - {wf.capitalize()} (N={count})"
            
            # Convert hex to rgba for shaded error band
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            fill_color = f"rgba({r}, {g}, {b}, 0.1)"
            
            # Upper bound scatter
            plotter.fig.add_trace(go.Scatter(
                x=freqs, y=mean + sem,
                mode='lines',
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip',
                legendgroup=trace_name
            ))
            
            # Lower bound + shaded fill
            plotter.fig.add_trace(go.Scatter(
                x=freqs, y=mean - sem,
                mode='lines',
                line=dict(width=0),
                fill='tonexty',
                fillcolor=fill_color,
                showlegend=False,
                hoverinfo='skip',
                legendgroup=trace_name
            ))
            
            # Mean trace
            plotter.fig.add_trace(go.Scatter(
                x=freqs, y=mean,
                mode='lines+markers',
                line=dict(color=color, width=style["width"], dash=style["dash"]),
                marker=dict(color=color, size=6),
                name=trace_name,
                legendgroup=trace_name
            ))
            
    plotter.fig.update_xaxes(
        type="log",
        tickvals=[6, 10, 16, 25, 42, 72, 120],
        ticktext=["Theta\n(6Hz)", "Alpha\n(10Hz)", "Beta1\n(16Hz)", "Beta2\n(25Hz)", "Gamma1\n(42Hz)", "Gamma2\n(72Hz)", "Gamma3\n(120Hz)"]
    )
    
    # Save both inside the module and the global oglo-8figs directory
    plotter.save(output_dir, "fig31_spike_phase_locking")
    
    # Save to the canonical registry destination as well
    global_output_dir = "../outputs/oglo-8figs"
    plotter.save(global_output_dir, "fig31_spike_phase_locking")
