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
Figures are built from `plotly.graph_objects` and `plotly.subplots.make_subplots`. Dense rasters and continuous LFPs use `go.Scattergl`. Every `save_and_seal` call writes SVG with editable `<text>` (through `kaleido`), one PNG at `png_dpi` dots per inch and interactive HTML, and returns a dict mapping `svg`, `png`, `html` and `argument` to the written paths. The HTML loads plotly.js from a CDN, so it needs a network connection to render.

### Layout
Panels occupy disjoint paper-domain rectangles. The canvas methods `add_panel_tags` and `get_colorbar_config` place panel tags and colorbars at pixel offsets from each panel's domain; their `offset_x_px` arguments, and `offset_y_px` for tags, set the offsets. Section 5 says how to check the result.

## 3. Invariants & Safeguards
- **Confidence intervals**: every summary curve carries a confidence envelope (e.g. 95% bootstrap CI, SEM), drawn with `fill='tonexty'` and a translucent `rgba(...)` fill.
- **Error bars**: categorical points and prevalences use `error_y` with exact Clopper-Pearson binomial intervals.
- **Units**: every axis declares its unit (`Time (ms)`, `Depth (μm)`, `Frequency (Hz)`, `Firing Rate (spikes/s)`, `Power Modulation (ΔdB)`). The laminar panels take a required `depth_unit` (`'mm'`, `'um'` or `'relative'`) and label the depth axis from it; the unit is never read off the data range. `plot_csd` and `plot_sorted_heatmap` take a required `value_unit` (for example `"A/m³"`, `"V/m²"`, `"spikes/s"`) that labels the colorbar, and `plot_hierarchy_regression` a required `y_label`. `plot_spectrolaminar_map` draws fractions in [0, 1] and raises on any other value; `jnwb.relative_power` returns a ratio to baseline, which is not that input.
- **Anatomical markers**: a crossover depth computed from the recording (for example with `jnwb.vflip`) is drawn as a dashed horizontal reference line with annotation. No depth is drawn unless the caller passes one; it is a property of each recording, not a constant.
- **Baseline references**: dotted zero references ($y = 0$) for $\Delta\text{dB}$ and $\Delta z$. Draw a decoder's chance line at the measured baseline the `jnwb-population` skill names (`majority_baseline`, or the `majority_baseline_accuracy` that `nested_cv_linear_svm` returns), not at $1/K$; pass it as `chance_level` instead of relying on the two-class $1/K$ line.
- **Significance**: Benjamini-Hochberg FDR indicators ($q_{\text{BH}} \le 0.05$) and cluster-based permutation test bars.

## 4. Minimal Workflow

```python
# Input: deterministic array.
import numpy as np
import jnwb.vis as jviz

# 0. Stand-in profiles for 32 contacts; replace them with the ones computed from your recording
channel_depths_mm = np.linspace(0.0, 3.1, 32)
gamma_profile = np.linspace(0.2, 0.8, 32)
alphabeta_profile = gamma_profile[::-1]
gamma_ci = np.column_stack([gamma_profile - 0.05, gamma_profile + 0.05])
alphabeta_ci = np.column_stack([alphabeta_profile - 0.05, alphabeta_profile + 0.05])
rel_power_matrix = np.outer(np.linspace(1.0, 0.5, 150), gamma_profile)  # fractions in [0, 1]
crossover_depth = channel_depths_mm[np.argmin(np.abs(gamma_profile - alphabeta_profile))]

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
    rel_power=rel_power_matrix,      # [150 freqs x 32 channels], fractions in [0, 1]
    freqs=np.arange(1, 151),
    depths=channel_depths_mm,
    crossover_depth=crossover_depth,  # computed from this recording, in mm
    cmap="Magma",
    depth_unit="mm",                  # required: 'mm', 'um' or 'relative'; never inferred
)

# 3. Panel B: Opposing Laminar Gradients with Bootstrap CI
jviz.laminar.plot_opposing_gradients(
    canvas=canvas,
    row=0, col=1,
    gamma_power=gamma_profile,
    alphabeta_power=alphabeta_profile,
    depths=channel_depths_mm,
    crossover_depth=crossover_depth,  # computed from this recording, in mm
    ci_gamma=gamma_ci,              # [32 x 2]
    ci_alphabeta=alphabeta_ci,      # [32 x 2]
    depth_unit="mm",
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
- The SVG `save_and_seal` writes through kaleido holds its text as `<text>` elements, not paths.
- `save_and_seal` writes `.svg`, `.png` and `.html` plus `_argument.json`.
- Open the written PNG at the width it will be shown (the canvas `layout` width) and inspect every panel: no panel tag, title, tick label, colorbar or legend overlaps another element or a neighboring panel, and no text is clipped at the figure edge. No test measures this, so the PNG is the evidence.
- Every summary curve has a confidence interval.

## 6. Documentation
- [`docs/vis.md`](../../docs/vis.md)
