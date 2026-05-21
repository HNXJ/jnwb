# beta — restored from git history (commit 90c743d^, deleted 2026-05-05)
import plotly.graph_objects as go
from src.analysis.visualization.plotting import OmissionPlotter
import numpy as np

def plot_recurrence_dynamics(results: dict, output_dir: str):
    """
    Plots Figure 30: Recurrence Dynamics (Spectral Radius).
    """
    plotter = OmissionPlotter(
        title="Figure 30: Recurrence Stability Radius",
        subtitle="Spectral Radius of Linear Transition Matrix | Omission Window | Memory Index"
    )
    plotter.set_axes("Area", "Hierarchy", "Spectral Radius (ρ)", "Stability Index")

    areas = list(results.keys())
    means = [results[area]['radius_mean'] for area in areas]
    stds = [results[area]['radius_std'] for area in areas]

    plotter.add_trace(
        go.Bar(x=areas, y=means, marker_color="#FF5E00", error_y=dict(type='data', array=stds, visible=True)),
        name="Recurrence Radius"
    )

    plotter.add_yline(1.0, "Stability Boundary", color="red", dash="dot")
    plotter.save(output_dir, "fig30_recurrence_radius")
