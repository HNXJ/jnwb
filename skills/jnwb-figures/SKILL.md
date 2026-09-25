---
name: jnwb-figures
description: Publication-grade vector graphics, raster PSTH plotting, tight auto-axis
  scaling, and visual QC suites.
---

# `jnwb-figures` — Visual QC & Publication Vector Graphics

## 1. Trigger
Activate this skill when generating publication figures, raster plots, PSTH visualizations, visual quality control suites, or vector graphics exports (SVG/PDF).

## 2. Task-to-Operation Routing Matrix
- `jnwb.setup_vector_graphics()`: Initialize publication rcParams for editable vector text (`svg.fonttype = 'none'`).
- `jnwb.apply_tight_auto_axis(ax, x_span=(-500, 4124), y_margin=0.12)`: Sets the x-limits to `x_span` exactly, whatever the data spans, so pass your own span; the signature's `(-500, 4124)` is one fixed window. Fits the y-limits to the plotted lines with `y_margin` padding and floors the lower limit at 0, so it suits non-negative traces such as rates: negative values fall out of view.
- `jnwb.save_figure_suite(figures, output_dir, basename, dpi=300, formats=["png", "pdf"])`: Export a **list** of figures with consistent naming, one `<basename>_page<N>.<fmt>` per figure per format. `figures` is iterated, so a single figure must be passed as `[fig]`; passing the figure itself raises `TypeError: 'Figure' object is not iterable`.
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Compute binned arrays for rendering spike rasters and PSTHs.
- `jnwb.visual_qc`: Submodule of unit-quality plots -- waveforms, quality distributions, noise against signal, and quality compared across sessions (import `jnwb.visual_qc`).
- `jnwb.resample_onsets(onsets, target_n=100, rng=42)`: Resamples onsets to exactly `target_n`, for an equal raster trial count across units. With at least `target_n` onsets it draws without replacement; with fewer it draws **with** replacement, so onsets repeat.

## 3. Invariants & Safeguards
1. **Vector Text Integrity**: Never convert text to outlines or rasterize labels during figure export; `setup_vector_graphics` sets `svg.fonttype = 'none'` so text remains editable.
2. **Deterministic Color Standards**: Use colorblind-safe palettes with consistent condition mapping across panels.
3. **No Synthetic Visuals**: Figures must render directly from empirical receipts. Synthetic data for scaffolding must display an explicit placeholder banner.

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
- Verify exported SVGs contain `<text>` elements rather than converted path geometries.
- Verify `save_figure_suite` writes valid files for all requested formats.

## 6. Canonical Documentation Links
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
