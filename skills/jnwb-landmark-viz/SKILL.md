---
name: jnwb-landmark-viz
description: Multi-panel Plotly publication figures through jnwb.vis, with SVG, PNG and HTML
  export and an argument sidecar. Needs the vis extra.
---

# `jnwb-landmark-viz` — Plotly Publication Figures (`jnwb.vis`)

## 1. Trigger
Multi-panel publication figures in Plotly: spectrolaminar maps, laminar gradients and CSD, multi-condition rasters and PSTHs, sorted population heatmaps, decoding timecourses, RSM heatmaps, spectral modulation and Granger spectra, and hierarchy regressions, exported as SVG, PNG and HTML with an argument sidecar (`_argument.json`). Needs the optional `vis` extra.

## 2. Routing

| Figure | `jnwb.vis` module |
|---|---|
| Canvas, panel layout, export and sidecar | `canvas` (`PlotlyPublicationCanvas`, `save_and_seal`), `sidecar` |
| Spectrolaminar map, opposing laminar gradients, CSD | `laminar` |
| Multi-condition raster/PSTH, sorted population heatmap | `spiking` |
| Decoding timecourse, RSM heatmap | `state_space` |
| Spectral modulation matrix, Granger spectra | `spectral` |
| Hierarchy regression | `hierarchy` |
| Publication theme and axis configuration | `theme` |

### Rendering and export
Figures are built from `plotly.graph_objects` and `plotly.subplots.make_subplots`. Dense rasters and continuous LFPs use `go.Scattergl`. Every `save_and_seal` call writes SVG with editable `<text>` (through `kaleido`), 300/600 DPI PNG and interactive HTML, and returns a dict mapping `svg`, `png`, `html` and `argument` to the written paths. The HTML loads plotly.js from a CDN, so it needs a network connection to render.

### Layout
Panels occupy disjoint normalized domain rectangles $[x_0, x_1] \times [y_0, y_1] \subset [0, 1]^2$. Panel tags (`A`, `B`, ...) sit at paper coordinates $(x_0 - 0.035, y_1 + 0.015)$ with `xanchor='right'`, `yanchor='bottom'`. Colorbars sit at `x = x_1 + 0.02`, `y = (y_0 + y_1)/2`, `len = (y_1 - y_0) * 0.85`, clear of neighboring panels.

## 3. Invariants & Safeguards
- **Confidence intervals**: every summary curve carries a confidence envelope (e.g. 95% bootstrap CI, SEM), drawn with `fill='tonexty'` and a translucent `rgba(...)` fill.
- **Error bars**: categorical points and prevalences use `error_y` with exact Clopper-Pearson binomial intervals.
- **Units**: every axis declares its unit (`Time (ms)`, `Depth (μm)`, `Frequency (Hz)`, `Firing Rate (spikes/s)`, `Power Modulation (ΔdB)`).
- **Anatomical markers**: a crossover depth computed from the recording (for example with `jnwb.vflip`) is drawn as a dashed horizontal reference line with annotation. No depth is drawn unless the caller passes one; it is a property of each recording, not a constant.
- **Baseline references**: dotted zero references ($y = 0$) for $\Delta\text{dB}$ and $\Delta z$. Draw a decoder's chance line at the measured baseline the `jnwb-population` skill names (`majority_baseline`, or the `majority_baseline_accuracy` that `nested_cv_linear_svm` returns), not at $1/K$; pass it as `chance_level`.
- **Significance**: Benjamini-Hochberg FDR indicators ($q_{\text{BH}} \le 0.05$) and cluster-based permutation test bars.

## 4. Minimal Workflow

```python
import numpy as np
import jnwb.vis as jviz

# 1. Initialize canvas (2-column Nature width: 183 mm)
canvas = jviz.PlotlyPublicationCanvas(
    layout="2col",
    height_mm=140,
    rows=1,
    cols=2,
    col_width_ratios=[1.2, 1.0],
    tags=[["A", "B"]]
)

# 2. Panel A: 2D Spectrolaminar Map (Mendoza-Halliday 2024 motif)
jviz.laminar.plot_spectrolaminar_map(
    canvas=canvas,
    row=0, col=0,
    rel_power=rel_power_matrix,      # [150 freqs x 32 channels]
    freqs=np.arange(1, 151),
    depths=channel_depths_mm,
    crossover_depth=crossover_depth,  # computed from this recording
    cmap="Magma"
)

# 3. Panel B: Opposing Laminar Gradients with Bootstrap CI
jviz.laminar.plot_opposing_gradients(
    canvas=canvas,
    row=0, col=1,
    gamma_power=gamma_profile,
    alphabeta_power=alphabeta_profile,
    depths=channel_depths_mm,
    crossover_depth=crossover_depth,  # computed from this recording
    ci_gamma=gamma_ci,              # [32 x 2]
    ci_alphabeta=alphabeta_ci       # [32 x 2]
)

# 4. Triple Export & Epistemic Sidecar Seal
canvas.save_and_seal(
    output_dir="outputs/figures",
    basename="fig_spectrolaminar",
    argument_object={
        "QUESTION": "<the question the figure answers>",
        "DATA": "<dataset, areas and unit or channel counts>",
        "ESTIMAND": "<the quantity plotted, e.g. relative power by depth>",
        "INFERENCE UNIT": "<what n counts, e.g. sessions>",
        "RESULT": "<the computed result, traced to the source artifact>",
        "LICENSED CLAIM": "<what the result supports>",
        "BARRED CLAIM": "<what it does not support>",
        "SOURCE ARTIFACTS": ["spectrolaminar_arrays.h5"]
    }
)
# Automatically writes:
# - outputs/figures/fig_spectrolaminar.svg
# - outputs/figures/fig_spectrolaminar.png
# - outputs/figures/fig_spectrolaminar.html
# - outputs/figures/fig_spectrolaminar_argument.json
```

## 5. Verification
- Exported SVGs contain `<text>` elements rather than converted path geometries.
- `save_and_seal` writes `.svg`, `.png` and `.html` plus `_argument.json`.
- Panel titles, axis tick labels and colorbars do not overlap.
- Every summary curve has a confidence interval.
