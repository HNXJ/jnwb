# 09. Visual QC & Publication-Ready Vector Graphics

This document details automated visual quality control (QC) pipelines and publication-grade vector graphic formatting in `jnwb`.

---

## 1. Automated Electrophysiology Visual QC (`jnwb/visual_qc.py`)

`jnwb.visual_qc` generates standardized diagnostic multi-panel figures for inspecting spike sorting fidelity, waveform stability, and noise distributions across multi-channel recording sessions.

### Unit Waveform Pagination & Inspection

```python
import jnwb.visual_qc as vqc

# Paginate and plot raw waveforms (mean ± 1 std dev) for all units in a session
fig = vqc.plot_unit_waveforms(
    waveforms_dict,      # Dict[unit_id -> (n_spikes, n_samples)]
    units_table=units_df,
    units_per_page=16,
    sampling_rate=30000.0
)
```

### Quality Distributions & Noise Diagnostics

```python
# Multi-panel distribution of Unit SNR, Firing Rates, and Isolation Distance
fig_dist = vqc.plot_unit_quality_distribution(units_df, group_by="area")

# 2x2 Noise vs. Signal Diagnostic Panel
fig_noise = vqc.plot_noise_vs_signal(lfp_segments, spike_trains)
```

---

## 2. Vector Graphics & Publication Formatting Standards (`jnwb/viz.py`)

### The Editable Vector Text Standard (`setup_vector_graphics`)
Standard matplotlib SVG and PDF exports frequently convert text into paths or non-editable glyphs. `jnwb.viz.setup_vector_graphics` configures matplotlib rcParams for full text editability in vector editors (Adobe Illustrator, Inkscape, Affinity Designer):

```python
import jnwb.viz as viz

# Call once at the start of a script or notebook
viz.setup_vector_graphics()
# Sets:
# - svg.fonttype = 'none' (preserves text as true SVG text elements)
# - pdf.fonttype = 42     (TrueType font embedding)
# - ps.fonttype = 42
# - font.sans-serif = ['Arial', 'Helvetica', 'DejaVu Sans']
```

### Tight Auto-Axis Bounding (`apply_tight_auto_axis`)
Eliminates dead margin whitespace while respecting physical domain constraints:

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.plot(times_ms, firing_rate_hz)

# Set tight limits around active data span, with 5% margin, preserving non-negative rate floor
viz.apply_tight_auto_axis(ax, x=times_ms, y=firing_rate_hz, margin_pct=0.05, y_min_zero=True)
```

### Multi-Format Figure Suite Saving (`save_figure_suite`)
Saves figures atomically across multiple formats (SVG for layout, PDF for vector review, PNG for slide presentations) at 300+ DPI:

```python
viz.save_figure_suite(
    fig,
    base_path="outputs/figures/fig01_overview",
    formats=["svg", "png", "pdf"],
    dpi=300
)
# Automatically writes:
# - outputs/figures/fig01_overview.svg
# - outputs/figures/fig01_overview.png
# - outputs/figures/fig01_overview.pdf
```
