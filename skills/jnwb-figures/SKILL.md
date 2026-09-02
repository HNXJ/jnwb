---
name: jnwb-figures
description: Publication-grade vector graphics, raster PSTH plotting, tight auto-axis
  scaling, and visual QC suites.
---

# `jnwb-figures` — Visual QC & Publication Vector Graphics

## 1. Trigger
Activate this skill when generating publication figures, raster plots, PSTH visualizations, visual quality control suites, or vector graphics exports (SVG/PDF).

## 2. Task-to-Primitive Routing Matrix
- `jnwb.setup_vector_graphics(font_family="Arial", font_size=8)`: Initialize publication rcParams for clean vector text (editable fonts in Illustrator/Inkscape).
- `jnwb.apply_tight_auto_axis(ax, x_margin=0.02, y_margin=0.05)`: Auto-scale axes with controlled padding and remove unneeded spines.
- `jnwb.save_figure_suite(fig, base_path, formats=("svg", "png", "pdf"), dpi=300)`: Export figure across vector and raster formats with matching dimensions.
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Compute binned arrays for rendering spike rasters and PSTHs.
- `jnwb.visual_qc(data, ...)`: Rapid multi-channel visual screening for artifact and saturation checks.
- `jnwb.resample_onsets(onsets, min_interval_s)`: Filter closely spaced event onsets to prevent visual overplotting.

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
ax.plot(np.linspace(0, 10, 100), np.sin(np.linspace(0, 10, 100)))
jnwb.apply_tight_auto_axis(ax)
```

## 5. Verification
- Verify exported SVGs contain `<text>` elements rather than converted path geometries.
- Verify `save_figure_suite` writes valid files for all requested formats.

## 6. Canonical Documentation Links
- [`docs/10_extending_jnwb_and_verification.md`](../../docs/10_extending_jnwb_and_verification.md)
