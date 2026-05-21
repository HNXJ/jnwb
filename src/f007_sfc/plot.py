import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os
from src.analysis.io.logger import log

def plot_circular_sfc(results: dict, output_dir: str):
    """
    Plots Figure f007 Circular SFC Phase Distributions.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    GOLD = "#CFB87C"
    PURPLE = "#9400D3"
    
    for area, data in results.items():
        if 'bands' not in data: continue
        
        stats = data.get('stats', {'stars': '', 'p': 1.0, 'tier': 'Null'})
        print(f"[action] Plotting Circular SFC for {area}")
        
        # Create 2x2 grid for bands
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'polar'}, {'type': 'polar'}],
                   [{'type': 'polar'}, {'type': 'polar'}]],
            subplot_titles=['Theta (4-8Hz)', 'Alpha (8-12Hz)', 'Beta (13-30Hz)', 'Gamma (30-80Hz)']
        )
        
        band_names = ['Theta', 'Alpha', 'Beta', 'Gamma']
        coords = [(1,1), (1,2), (2,1), (2,2)]
        
        for name, (r, c) in zip(band_names, coords):
            if name not in data['bands']: continue
            band_data = data['bands'][name]
            
            # Histogram bins
            bins = np.linspace(-np.pi, np.pi, 24)
            
            # S+ Distribution
            counts_s, _ = np.histogram(band_data['s_phases'], bins=bins, density=True)
            fig.add_trace(go.Barpolar(
                r=counts_s,
                theta=np.rad2deg(bins[:-1]),
                name=f"S+ {name}",
                marker_color=GOLD,
                marker_line_color="white",
                marker_line_width=0.5,
                opacity=0.7,
                showlegend=(r==1 and c==1)
            ), row=r, col=c)
            
            # O+ Distribution
            counts_o, _ = np.histogram(band_data['o_phases'], bins=bins, density=True)
            fig.add_trace(go.Barpolar(
                r=counts_o,
                theta=np.rad2deg(bins[:-1]),
                name=f"O+ {name}",
                marker_color=PURPLE,
                marker_line_color="white",
                marker_line_width=0.5,
                opacity=0.7,
                showlegend=(r==1 and c==1)
            ), row=r, col=c)

        fig.update_layout(
            title=f"Figure f007: {area} Phase-Locking (SFC) {stats['stars']}",
            template="plotly_white",
            paper_bgcolor="#FFFFFF",
            font_color="#000000",
            height=900,
            width=900,
            showlegend=True
        )
        
        # Update all polar axes
        fig.update_polars(
            bgcolor="#FFFFFF",
            angularaxis=dict(gridcolor="lightgray", linecolor="black", tickfont_size=10),
            radialaxis=dict(gridcolor="lightgray", linecolor="black", showticklabels=False)
        )

        filename = f"f007_circular_sfc_{area}.html"
        fig.write_html(os.path.join(output_dir, filename))
        log.progress(f"Saved {filename}")

if __name__ == "__main__":
    pass
