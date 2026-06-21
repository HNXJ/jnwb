---
name: tfr-visualization-spectrogram-2d
description: >
  Generating 2D time-frequency power spectrograms (heatmaps) using Plotly and Matplotlib.
---

# Skill: tfr-visualization-spectrogram-2d — 2D Heatmaps

## Purpose
Instructions for building 2D time-frequency power heatmaps (spectrograms) with dB-baseline normalization.

---

## 1. Parameters & Colorscale
- **Z-Axis**: Baseline-normalized power in dB: $10 \log_{10}(P / P_{\text{baseline}})$.
- **Baseline Window**: [-500, 0] ms relative to trial start.
- **Colorscale**: Custom diverging or sequential colorscale (e.g. 'RdBu_r' or customized gold-to-violet gradients).

---

## 2. Axis Definitions
- **X-axis**: Time relative to p1 onset (-1000 to 4000 ms).
- **Y-axis**: Frequencies (2 to 150 Hz log-spaced).

---

## 3. Code Example
```python
import plotly.graph_objects as go
import numpy as np

def generate_spectrogram_2d(times, freqs, z_data):
    fig = go.Figure(data=go.Heatmap(
        x=times,
        y=freqs,
        z=z_data,
        colorscale='RdBu_r',
        zmin=-3, zmax=3
    ))
    fig.update_layout(
        xaxis_title="Time (ms)",
        yaxis_title="Frequency (Hz)",
        yaxis_type="log",
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF"
    )
    return fig
```
