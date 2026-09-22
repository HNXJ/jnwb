---
name: jnwb-landmark-viz
description: Publication-grade non-human primate electrophysiology visualization engine (pure Plotly) generating Nature/Neuron-standard multi-panel figures, laminar spectrolaminar/CSD maps, multi-condition rasters, hierarchy regressions, triple default exports (SVG/PNG/HTML), and epistemic argument sidecars.
---

# `jnwb-landmark-viz` — Publication-Grade Electrophysiology Visualization Engine (Plotly)

## 1. Trigger
Activate this skill when:
- Generating multi-panel publication figures for electrophysiology, single units, LFPs, CSD, or population decoding.
- Plotting 2D spectrolaminar power maps (radical-sign $\sqrt{\cdot}$ motif), opposing laminar gradients, or current source density profiles.
- Rendering multi-condition spike rasters, trial-aligned PSTHs with confidence intervals, or sorted population heatmaps.
- Performing anatomical hierarchy regressions, area-by-area forest plots, or multi-area time cascades.
- Exporting triple-format publication bundles (`.svg` vector text, `.png` 300/600 DPI, `.html` interactive WebGL) with machine-readable epistemic sidecars (`_argument.json`).

## 2. Core Architecture & Standards

### 2.1 Pure Plotly Engine
All figures are constructed using `plotly.graph_objects` (`go.Figure`, `go.Scatter`, `go.Scattergl`, `go.Heatmap`, `go.Contour`) and `plotly.subplots.make_subplots`.
- **Interactive Web / HTML**: Full zoom, pan, hover inspection (unit ID, latency, $p$-value, firing rate), and trace toggles.
- **Hardware-Accelerated WebGL**: High-density spike rasters and continuous LFPs use `go.Scattergl` for lag-free rendering of $>100{,}000$ points.
- **Publication Vector Export**: Exports crisp vector SVG with editable `<text>` tags (via `kaleido`), 300/600 DPI PNG, and self-contained interactive HTML by default.

### 2.2 Collision-Free Relative Coordinate Engine
Subplots and elements use strict non-overlapping relative domain coordinates:
- Subplot panels occupy disjoint normalized domain rectangles: $[x_0, x_1] \times [y_0, y_1] \subset [0, 1]^2$.
- Panel tags (`A`, `B`, `C`, ...) are anchored to paper coordinates $(x_0 - 0.035, y_1 + 0.015)$ with `xanchor='right'`, `yanchor='bottom'`.
- Colorbars are explicitly placed with `x = x_1 + 0.02`, `y = (y_0 + y_1)/2`, `len = (y_1 - y_0) * 0.85`, preventing collisions with neighboring panels.

### 2.3 Statistical Rigor & Scientific Standards
- **Mandatory Confidence Intervals**: Every summary curve must feature a confidence envelope (e.g. 95% bootstrap CI, SEM) using Plotly's `fill='tonexty'` with translucent fills (`rgba(...)`).
- **Explicit Error Bars**: Categorical points and prevalences use `error_y` with exact Clopper-Pearson binomial intervals.
- **Physical Scales & Units**: Explicit unit declarations on every axis (`Time (ms)`, `Depth (μm)`, `Frequency (Hz)`, `Firing Rate (spikes/s)`, `Power Modulation (ΔdB)`).
- **Anatomical Markers**: Canonical Layer 4 crossover depth ($d = 0.405$) displayed as a dashed horizontal reference line with annotation.
- **Baseline References**: Dotted zero references ($y = 0$) for $\Delta\text{dB}$ and $\Delta z$; chance line ($y = 0.5$) for binary decoders.
- **Significance Thresholding**: Benjamini-Hochberg FDR indicators ($q_{\text{BH}} \le 0.05$) and non-parametric cluster-based permutation test bars.

## 3. Minimal Workflow Example

```python
import numpy as np
import jnwb.viz as jviz

# 1. Initialize canvas (2-column Nature width: 183 mm)
canvas = jviz.PlotlyPublicationCanvas(
    layout="2col",
    height_mm=140,
    rows=1,
    cols=2,
    col_width_ratios=[1.2, 1.0],
    tags=["A", "B"]
)

# 2. Panel A: 2D Spectrolaminar Map (Mendoza-Halliday 2024 motif)
jviz.laminar.plot_spectrolaminar_map(
    canvas=canvas,
    row=0, col=0,
    rel_power=rel_power_matrix,      # [150 freqs x 32 channels]
    freqs=np.arange(1, 151),
    depths=channel_depths_mm,
    crossover_depth=0.405,
    cmap="Magma"
)

# 3. Panel B: Opposing Laminar Gradients with Bootstrap CI
jviz.laminar.plot_opposing_gradients(
    canvas=canvas,
    row=0, col=1,
    gamma_power=gamma_profile,
    alphabeta_power=alphabeta_profile,
    depths=channel_depths_mm,
    crossover_depth=0.405,
    ci_gamma=gamma_ci,              # [32 x 2]
    ci_alphabeta=alphabeta_ci       # [32 x 2]
)

# 4. Triple Default Export & Epistemic Sidecar Seal
canvas.save_and_seal(
    output_dir="outputs/figures",
    basename="fig_spectrolaminar",
    argument_object={
        "QUESTION": "Is the spectrolaminar radical-sign motif preserved?",
        "DATA": "Macaque E2 corpus (V4 and PFC linear arrays)",
        "ESTIMAND": "Relative power P_rel(f, d) and L4 crossover depth",
        "INFERENCE UNIT": "Sessions (n=22)",
        "RESULT": "Gamma and alpha/beta intersect at d=0.405",
        "LICENSED CLAIM": "Spectrolaminar motif is ubiquitous across sampled areas",
        "BARRED CLAIM": "Omission reverses laminar spectral directionality",
        "SOURCE ARTIFACTS": ["spectrolaminar_arrays.h5"]
    }
)
# Automatically writes:
# - outputs/figures/fig_spectrolaminar.svg
# - outputs/figures/fig_spectrolaminar.png
# - outputs/figures/fig_spectrolaminar.html
# - outputs/figures/fig_spectrolaminar_argument.json
```

## 4. Verification
- Verify exported SVGs contain `<text>` elements rather than converted path geometries.
- Verify `save_and_seal` generates all three files (`.svg`, `.png`, `.html`) plus `_argument.json`.
- Verify no visual overlaps between panel titles, axis tick labels, and colorbars.
- Verify confidence intervals accompany all summary curves.
