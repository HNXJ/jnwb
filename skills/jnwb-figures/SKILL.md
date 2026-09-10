---
name: jnwb-figures
description: Publication-grade vector graphics, raster PSTH plotting, tight auto-axis
  scaling, and visual QC suites.
---

# `jnwb-figures` — Visual QC & Publication Vector Graphics

## 1. Trigger
Activate this skill when generating publication figures, raster plots, PSTH visualizations, visual quality control suites, or vector graphics exports (SVG/PDF).

## 2. Task-to-Primitive Routing Matrix
- `jnwb.setup_vector_graphics()`: Initialize publication rcParams for editable vector text (`svg.fonttype = 'none'`).
- `jnwb.apply_tight_auto_axis(ax, x_span=(-500, 4124), y_margin=0.12)`: Auto-scale axes with controlled padding.
- `jnwb.save_figure_suite(figures, output_dir, basename, dpi=300, formats=("png", "pdf"))`: Export one or more figures with consistent naming.
- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Compute binned arrays for rendering spike rasters and PSTHs.
- `jnwb.visual_qc`: Submodule for rapid multi-channel visual screening (import `jnwb.visual_qc`).
- `jnwb.resample_onsets(onsets, target_n=100, random_state=42)`: Subsample onsets to a target count for plotting.

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
