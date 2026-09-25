# Plotly Figures (`jnwb.vis`)

`jnwb.vis` draws multi-panel figures in Plotly and exports each one as SVG, PNG and
interactive HTML, sealed with a JSON sidecar that states what the figure licenses. It
plots arrays you supply; the two exceptions are named in the panel table.

## Install

```bash
pip install "jnwb[vis]"
```

The extra adds `plotly` and `kaleido`; kaleido writes the SVG and PNG. Without it, `import jnwb`
and every other export work, and two things raise `ImportError` naming `pip install jnwb[vis]`:

| Call | Why |
|---|---|
| `jnwb.vis` or `from jnwb import vis` | the module needs Plotly |
| `from jnwb import *` | `vis` is in `jnwb.__all__`, and a star import resolves every name |

## One canvas from supplied arrays

```python
import numpy as np
from jnwb import vis

rng = np.random.default_rng(0)
time_ms = np.arange(-200.0, 500.0, 10.0)
rates = rng.normal(size=(40, time_ms.size))          # units x time, synthetic
order = np.argsort(np.argmax(rates[:, time_ms >= 0], axis=1))

canvas = vis.PlotlyPublicationCanvas(layout="1col", height_mm=70.0, rows=1, cols=1, tags=[["A"]])
vis.plot_sorted_heatmap(canvas, 0, 0, rates, time_ms, sort_idx=order,
                        title="Synthetic units sorted by peak time", colorbar_title="Rate (z)")

argument = vis.EpistemicArgumentObject(
    QUESTION="Does the heatmap render units sorted by peak time?",
    DATA="Synthetic normal draws, 40 units x 70 bins, seed 0",
    ESTIMAND="None: a rendering example",
    INFERENCE_UNIT="None",
    RESULT="A sorted heatmap",
    LICENSED_CLAIM="The canvas renders a supplied matrix",
    BARRED_CLAIM="Any claim about neural data",
    SOURCE_ARTIFACTS=["generated in this script, seed 0"],
)
paths = canvas.save_and_seal("figures", "sorted_heatmap", argument)
# paths: {'argument', 'html', 'svg', 'png'} -> Path
```

Panels are addressed by `(row, col)` from 0. Widths follow the presets `'1col'` (89 mm),
`'1.5col'` (136 mm) and `'2col'` (183 mm), or `width_mm`. Every field of the sidecar must be
non-empty, and `SOURCE_ARTIFACTS` must name at least one source, so a figure cannot be sealed
without saying what it rests on.

## Panels

Each function draws into one `(row, col)` of a canvas.

| Function | Draws |
|---|---|
| `plot_sorted_heatmap` | units x time rates, in a supplied order |
| `plot_multi_condition_raster_psth` | rasters and PSTHs per condition from spike and onset times; computes the PSTH and a mean ± 1.96 SEM ribbon across trials, not a bootstrap interval |
| `plot_spectrolaminar_map` | relative power over depth and frequency |
| `plot_opposing_gradients` | gamma against alpha/beta power over depth, with supplied CIs |
| `plot_csd` | current source density over depth and time, with layer boundaries |
| `plot_spectral_modulation_matrix` | area x band modulation, with FDR-corrected markers |
| `plot_granger_spectra` | directed Granger spectra, with a shuffle-null ribbon |
| `plot_hierarchy_regression` | values over hierarchy rank with supplied error bars and null; computes a least-squares line |
| `plot_decoding_timecourse` | cross-validated decoding over time, with a CI ribbon |
| `plot_rsm_heatmap` | a representational similarity or dissimilarity matrix |

Every other interval, null and correction is an input: compute it with the jnwb operation
that estimates it and pass the result in. Signatures are on [Public API](api.md).
