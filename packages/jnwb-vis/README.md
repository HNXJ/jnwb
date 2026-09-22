# `jnwb-vis`: Publication-Grade Electrophysiology Visualization Engine (Plotly)

A lightweight, high-performance, pure-Plotly visualization engine designed for non-human primate (NHP) electrophysiology, laminar recordings, and systems neuroscience.

## Highlights
- **Pure Plotly Engine**: Dual-use interactive HTML exploration + publication-identical vector SVG (pure `<text>` elements) and 300/600 DPI PNG export.
- **Hardware-Accelerated WebGL**: Seamlessly renders $>100{,}000$ spikes and continuous LFPs via `go.Scattergl`.
- **Collision-Free Relative Domain Mathematics**: Eliminates overlapping panel tags, titles, axis labels, and colorbars.
- **Landmark Motifs**:
  - 2D Spectrolaminar maps (Mendoza-Halliday 2024 radical-sign $\sqrt{\cdot}$ motif)
  - Opposing gamma vs. alpha/beta laminar gradients with bootstrap CI envelopes
  - CSD profiles with zero-crossing contour lines
  - Multi-condition spike rasters & trial-aligned PSTHs with bootstrap ribbons
  - Hierarchy latency/prevalence regressions with permutation null ribbons
  - Spectral modulation matrices with FDR significance indicators ($q_{\text{BH}} \le 0.05$)
  - Cross-validated decoding time courses with cluster-based significance bars
- **Epistemic Reproducibility**: Automatically serializes an 8-field machine-readable argument object sidecar (`_argument.json`) with every figure.

## Quickstart

```python
import numpy as np
import jnwb.vis as vis

# 1. Initialize 2-column Nature canvas (183 mm wide)
canvas = vis.PlotlyPublicationCanvas(layout="2col", height_mm=140, rows=1, cols=2, tags=["A", "B"])

# 2. Panel A: Spectrolaminar map
vis.plot_spectrolaminar_map(
    canvas=canvas,
    row=0, col=0,
    rel_power=rel_power_matrix,
    freqs=np.arange(1, 151),
    depths=depths_mm,
    crossover_depth=0.405,
)

# 3. Panel B: Opposing laminar gradients with bootstrap CIs
vis.plot_opposing_gradients(
    canvas=canvas,
    row=0, col=1,
    gamma_power=gamma_profile,
    alphabeta_power=alphabeta_profile,
    depths=depths_mm,
    crossover_depth=0.405,
    ci_gamma=gamma_ci,
    ci_alphabeta=alphabeta_ci,
)

# 4. Triple default export + epistemic sidecar seal
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
        "SOURCE ARTIFACTS": ["spectrolaminar_arrays.h5"],
    }
)
```
