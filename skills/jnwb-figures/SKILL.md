---
name: jnwb-figures
description: Matplotlib publication figures, vector export, tight auto-axis scaling, and
  equal raster trial counts.
---

# `jnwb-figures` — Matplotlib Figures & Vector Export

## 1. Trigger
Matplotlib publication figures, equal raster trial counts, or vector export (SVG/PDF). PSTH arrays route to `jnwb-spiking`; multi-panel Plotly figures route to `jnwb-landmark-viz`; unit-quality plots route to `jnwb-qc`.

## 2. Routing
- `jnwb.setup_vector_graphics()`: Sets publication rcParams for editable vector text (`svg.fonttype = 'none'`).
- `jnwb.apply_tight_auto_axis(ax, x_span=(-500, 4124), y_margin=0.12)`: Sets the x-limits to `x_span` exactly, whatever the data spans, so pass your own span; the signature's `(-500, 4124)` is one fixed window. Fits the y-limits to the plotted lines with `y_margin` padding; the lower limit is floored at 0 only when no plotted value is negative, so signed traces keep their negative values in view.
- `jnwb.save_figure_suite(figures, output_dir, basename, dpi=300, formats=["png", "pdf"])`: Exports a **list** of figures, one `<basename>_page<N>.<fmt>` per figure per format. `figures` is iterated, so a single figure must be passed as `[fig]`; passing the figure itself raises `TypeError: 'Figure' object is not iterable`.
- `jnwb.resample_onsets(onsets, target_n=100, rng=42)`: Resamples onsets to exactly `target_n`, for an equal raster trial count across units. With at least `target_n` onsets it draws without replacement; with fewer it draws **with** replacement, so onsets repeat.

## 3. Invariants & Safeguards
1. **Vector text**: never convert text to outlines or rasterize labels on export; `setup_vector_graphics` keeps text editable.
2. **Color**: colorblind-safe palettes with one condition-to-color mapping across panels.
3. **No synthetic visuals**: figures must render from results a script computed from data. Synthetic scaffolding data displays an explicit placeholder banner.

## 4. Minimal Workflow
```python
# Input: deterministic array.
import jnwb
import matplotlib.pyplot as plt
import numpy as np

jnwb.setup_vector_graphics()
fig, ax = plt.subplots(figsize=(3.5, 2.5))
t_ms = np.linspace(-200.0, 800.0, 100)
ax.plot(t_ms, 20.0 + 10.0 * np.exp(-((t_ms - 150.0) / 80.0) ** 2))  # a rate in Hz
jnwb.apply_tight_auto_axis(ax, x_span=(-200.0, 800.0))
```

## 5. Verification
- An SVG saved after `setup_vector_graphics` holds its text as `<text>` elements, not paths.
- `save_figure_suite` writes valid files for every requested format.
- Each figure is rendered at its final size and inspected: no clipped or overlapping text, and every axis and colorbar names its unit.

## 6. Documentation
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
