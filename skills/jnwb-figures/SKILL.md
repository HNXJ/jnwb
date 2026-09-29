---
name: jnwb-figures
description: Publication-grade vector graphics, raster PSTH plotting, tight auto-axis
  scaling, and visual QC suites.
---

# `jnwb-figures` — Visual QC & Vector Graphics (Matplotlib)

## 1. Trigger
Matplotlib publication figures, raster and PSTH plots, visual QC suites, or vector export (SVG/PDF). Multi-panel Plotly figures route to `jnwb-landmark-viz`.

## 2. Routing
- `jnwb.setup_vector_graphics()`: Sets publication rcParams for editable vector text (`svg.fonttype = 'none'`).
- `jnwb.apply_tight_auto_axis(ax, x_span=(-500, 4124), y_margin=0.12)`: Sets the x-limits to `x_span` exactly, whatever the data spans, so pass your own span; the signature's `(-500, 4124)` is one fixed window. Fits the y-limits to the plotted lines with `y_margin` padding and floors the lower limit at 0, so it suits non-negative traces such as rates: negative values fall out of view.
- `jnwb.save_figure_suite(figures, output_dir, basename, dpi=300, formats=["png", "pdf"])`: Exports a **list** of figures, one `<basename>_page<N>.<fmt>` per figure per format. `figures` is iterated, so a single figure must be passed as `[fig]`; passing the figure itself raises `TypeError: 'Figure' object is not iterable`.
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Binned arrays for rendering spike rasters and PSTHs.
- `jnwb.resample_onsets(onsets, target_n=100, rng=42)`: Resamples onsets to exactly `target_n`, for an equal raster trial count across units. With at least `target_n` onsets it draws without replacement; with fewer it draws **with** replacement, so onsets repeat.
- `jnwb.visual_qc`: Submodule of unit-quality plots -- waveforms, quality distributions, noise against signal, and quality compared across sessions (import `jnwb.visual_qc`).

## 3. Invariants & Safeguards
1. **Vector text**: never convert text to outlines or rasterize labels on export; `setup_vector_graphics` keeps text editable.
2. **Color**: colorblind-safe palettes with one condition-to-color mapping across panels.
3. **No synthetic visuals**: figures must render from results a script computed from data. Synthetic scaffolding data displays an explicit placeholder banner.

## 4. Minimal Workflow
```python
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
- Exported SVGs contain `<text>` elements rather than converted path geometries.
- `save_figure_suite` writes valid files for every requested format.

## 6. Documentation
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
