---
name: jnwb-visualization
description: |
  Plotting and visual QC using jnwb. Covers OmissionSession plotting shortcuts,
  the jnwb.visual_qc module, summary_report, and the jnwb.viz sub-module.
  Use this skill for any task that produces figures, exports SVGs/HTMLs,
  or runs a visual quality-check pass on data.
---

# jnwb-visualization: Plots and Visual QC

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `visual_qc.py`, `__init__.py` (viz sub-module), `functions.py` (summary_report)

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import visual_qc, viz
from jnwb import summary_report, noise_vs_signal
```

## OmissionSession Plotting Methods

```python
session = oa.read('path/to/file.nwb')

# Time-frequency spectrogram
session.plot_tfr(area='V1', condition='AAXB', phase=3)
session.trial_averaged_plot(area='V1', phase=3, condition='AAXB')
session.channel_averaged_plot(area='V4', phase=3, condition='AAXB')

# Spectrolaminar motif (layer-wise spectral)
session.spectrolaminar_motif(area='MT', condition='omission')

# Raster suite: raster + PSTH + autocorrelogram
session.raster_suite(unit_id=42, condition='AAXB', phase=3)

# Population pie charts
session.pie_charts(criteria={'is_stable_plus': True}, by_area=True)
```

## jnwb.visual_qc Module

```python
# Waveform gallery (all units on a session/channel)
visual_qc.waveform_gallery(session, area='V1', output_path='output/waveforms.png')

# Channel noise / artifact inspection
visual_qc.channel_noise_report(session, output_path='output/noise.html')

# Unit stability trace (firing rate across trial blocks)
visual_qc.stability_trace(session, unit_id=42, output_path='output/stability.png')

# Summary dashboard
visual_qc.session_dashboard(session, output_dir='output/')
```

## jnwb.viz Sub-Module

The `viz` sub-module provides publication-grade Plotly and Matplotlib wrappers.

```python
# TFR heatmap (Plotly interactive)
fig = viz.tfr_heatmap(tfr_array, times, freqs, title='V1 – AAXB – gamma')
fig.write_html('output/tfr.html')
fig.write_image('output/tfr.svg')

# Band-power trace
fig = viz.band_power_trace(band_power_array, times, label='alpha', area='V1')

# Raster
fig = viz.raster(spike_raster, trial_onsets, window_ms=(-500, 2000))

# PSTH trace
fig = viz.psth_trace(psth_array, sem_array, bin_centers)
```

## Canonical Functions

```python
# Summary report (generates file + returns dict)
report = summary_report(session, output_dir='output/')
# Returns: {'file': 'output/summary.html', 'n_units': 368,
#           'n_stable_plus': 45, 'firing_rate_mean': 5.2, ...}

# Signal-to-noise ratio analysis for a unit
snr = noise_vs_signal(session, unit_id=42)
# Returns: {'snr_db': 8.5, 'is_good_unit': True, 'waveform_peak': ..., 'waveform_trough': ...}
```

## Output Directories

```
d:/workspace/omission/outputs/
├── publication_figures/       ← final publication figures (SVG/PDF)
├── publication_visual_review/ ← review drafts and exploratory figures
└── scratch/                   ← one-off exploration plots
```

## Pie Chart Figure Source

Reproducible generator:
```
d:/workspace/omission/scripts/remake_pie_charts_summary.py
```

Outputs written to `outputs/publication_visual_review/`:
- `pie_charts_summary_revised.svg`
- `pie_charts_summary_revised.csv`
- `pie_charts_summary_revised.md`
