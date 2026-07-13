---
name: jnwb-visualization
description: |
  Plotting and visual QC using jnwb. Covers OmissionSession plotting shortcuts,
  the jnwb.visual_qc module, summary_report, the jnwb.viz sub-module,
  and the 16 tasks in the visualization gallery.
  Use this skill for any task that produces figures, exports SVGs/HTMLs,
  or runs a visual quality-check pass on data.
---

# jnwb-visualization: Plots and Visual QC

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `visual_qc.py`, `__init__.py` (viz sub-module), `viz.py`, `functions.py` (summary_report)

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import visual_qc as qc
from jnwb import viz
```

## Footgun: verifying SVG output on this Windows machine

`cairosvg` fails at runtime here (`OSError: no library called "cairo-2"` — no native
`libcairo-2.dll`). `reportlab.graphics.renderPM` (PNG output) also fails
(`ModuleNotFoundError: No module named '_rl_renderPM'`). Working path to actually inspect a
generated SVG before claiming a figure is done:

```python
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF
drawing = svg2rlg("path/to/figure.svg")
renderPDF.drawToFile(drawing, "path/to/figure_preview.pdf")
```

Then use the `Read` tool on the PDF (it renders pages visually) to inspect the real output.
`mcp__Claude_Browser__navigate` to a `file://` SVG path and a local `http.server` + browser
preview have both failed in this environment — don't retry those; go straight to the
svglib→PDF→Read path. "Exported without visual inspection" does not satisfy the project's
figure-verification checklist below.

## Output Directory Conventions

All visualization gallery outputs are written to task-specific subdirectories under:
```
outputs/visualization_gallery/
```
Style parameters: Background color `white`, no top/right spines, DPI `200`, `bbox_inches='tight'`.

---

## The 16 Canonical Visualization Tasks

The following 16 visualization tasks constitute the standard gallery. Use these templates to reproduce or generate plots:

### Task 1: Single Unit Raster Suite
Generates a 3-panel single-unit plot containing a Spike Raster, PSTH (with baseline), and Autocorrelogram.
```python
session = oa.read('path/to/session.nwb')
res = session.raster_suite(unit_id=2.0)
fig = res["figure"]
fig.savefig('outputs/visualization_gallery/task_01_raster/raster_suite.png')
```

### Task 2: Raw LFP Traces (Probe B / 1)
Plots raw LFP time-series for channels 44, 47, and 50 of Probe B.
```python
import pynwb
with pynwb.NWBHDF5IO('session.nwb', 'r', load_namespaces=True) as io:
    nwb = io.read()
    lfp_obj = nwb.acquisition["probe_1_lfp"]
    rate = getattr(lfp_obj, "rate", 1000.0) or 1000.0
    lfp_data = lfp_obj.data[:10000, [44, 47, 50]]
# Plot t_ms vs lfp_data using matplotlib
```

### Task 3: Raw MUAe Traces (Probe A / 0)
Plots raw Multi-Unit Activity envelope (MUAe) for channels 1 and 127 of Probe A.
```python
with pynwb.NWBHDF5IO('session.nwb', 'r', load_namespaces=True) as io:
    nwb = io.read()
    mobj = nwb.acquisition["probe_0_muae"]
    mrate = getattr(mobj, "rate", 1000.0) or 1000.0
    muae_data = mobj.data[:10000, [1, 127]]
# Fill between 0 and muae_data using matplotlib
```

### Task 4: Single Channel TFR Image
Generates a 2D Log-Frequency spectrogram image for channel 22, Probe A (PFC) in condition AAAB.
```python
tfr = session.tfr_from_preprocessed(area="PFC", condition="AAAB")
ch_data = tfr[22, :, :, 0] # frequency x time
# Compute dB relative to pre-stim baseline, then ax.pcolormesh()
```

### Task 5: TFR Band Traces
Averages and plots power across channels 20–80 for the 7 canonical frequency bands (delta, theta, alpha, beta, low_gamma, high_gamma, broadband).
```python
tfr = session.tfr_from_preprocessed(area="PFC", condition="AAAB")
tfr_sub = tfr[20:80, :, :, :] # channels, freqs, time, trials
# Loop through BAND_RANGES, slice freqs, average over channels, freqs, trials
```

### Task 6: Unit Quality Distribution
Plots distributions of firing rates, SNR, waveform durations, and quality categories across all units.
```python
fig = qc.plot_unit_quality_distribution(session._units_df)
fig.savefig('outputs/visualization_gallery/task_06_quality_distribution/unit_quality_distribution.png')
```

### Task 7: Noise vs. Signal Tradeoff Scatter
Plots a multi-metric scatter matrix showing relationships between SNR, Firing Rate, and Waveform Duration.
```python
fig = qc.plot_noise_vs_signal(session._units_df)
fig.savefig('outputs/visualization_gallery/task_07_noise_vs_signal/noise_vs_signal.png')
```

### Task 8: Pie Charts of Unit Quality
Generates summary pie charts displaying unit stability categories grouped by recording area.
```python
res_pie = session.pie_charts(criteria=None, by_area=True)
for area_name, fig in res_pie["figures"].items():
    fig.savefig(f'outputs/visualization_gallery/task_08_pie_charts/pie_{area_name}.png')
```

### Task 9: Time-Frequency Spectrogram (TFR)
Plots a trial-averaged and baseline-subtracted Log-Frequency TFR for PFC in AAXB condition.
```python
res = session.plot_tfr(area="PFC", condition="AAXB", phase=3)
res["figure"].savefig('outputs/visualization_gallery/task_09_plot_tfr/tfr_PFC_AAXB_phase3.png')
```

### Task 10: Trial-Averaged Spectrogram Plot
Plots a dB-normalized trial-averaged TFR heatmap for the MT area in AAXB condition.
```python
res = session.trial_averaged_plot(area="MT", phase=2, condition="AAXB")
res["figure"].savefig('outputs/visualization_gallery/task_10_trial_averaged/trial_averaged_MT_AAXB.png')
```

### Task 11: Channel-Averaged Power Spectrum
Plots the 1D Power Spectral Density (PSD) line plot for MT averaged across all channels and trials.
```python
res = session.channel_averaged_plot(area="MT", phase=2, condition="AAXB")
res["figure"].savefig('outputs/visualization_gallery/task_11_channel_averaged/channel_averaged_MT.png')
```

### Task 12: Spectrolaminar Motif
Performs layer-wise spectral analysis for V4, saving both a JSON summary and a heatmap PNG comparing superficial vs. deep layers.
```python
res = session.spectrolaminar_motif(area="V4", condition="AAAB")
# res["layer_data"] contains {"superficial": array, "deep": array}
```

### Task 13: LFP TFR Trace Suite
Generates the publication-grade 2-row aligned spectrogram trace suite for an area and layer.
- **Standards**:
  - Time window: extended up to `1920` ms to reveal `p3` slot traces.
  - Pool/combine Control (`control_p2`/`control_p3`) and Omission (`omission_p2`/`omission_p3`) trial distributions to improve SEM.
  - Perform dual statistical tests (t-test + Wilcoxon signed-rank vs 0) and correct using Bonferroni ($\alpha = 0.01 / N_{\text{bins}}$).
  - Smooth traces using a Gaussian filter (`sigma=2.0`). For insignificant bands ($p \ge 0.05$ on both tests), force mean to flat `0` while maintaining the SEM shaded region.
  - Significance indicators: solid horizontal bars at the top of each axis (Blue for significant increase, Red for significant decrease).
  - Grid Layout: `5x2` grid representing V1, V3a, MST, and PFC (Control left, Omission right) for Rows 0-3, and Row 4 containing superimposed 1D broadband power traces with a boxed legend.
```python
res = session.lfp_tfr_trace_suite_omission(area="V1", layer="deep")
res["figure"].savefig('outputs/visualization_gallery/task_13_trace_suite/lfp_tfr_trace_suite_V1.png')
```


### Task 14: LFP Inter-Area Correlation Heatmap
Computes and plots a 22x22 correlation matrix of LFP band power averages across all area-layers for the Alpha band.
```python
res = session.lfp_tfr_trace_correlation(band_name="Alpha")
res["figure"].savefig('outputs/visualization_gallery/task_14_correlation/lfp_correlation_alpha.png')
```

### Task 15: Condition-Family Raster Grid
Generates a multi-panel grid of spike rasters for a set of high-FR units grouped by condition family A.
```python
figs = viz.raster_grid_by_family(session, unit_ids=[1.0, 2.0], family="A")
for idx, fig in enumerate(figs):
    fig.savefig(f'outputs/visualization_gallery/task_15_raster_grid/raster_grid_A_page{idx+1}.png')
```

### Task 16: Polar Radar Band-Power & Granger Network
Plots (Left) a polar radar map representing relative band powers across V1, V4, MT, MST, and PFC, and (Right) a directional lag network heatmap representing leads and lags.
```python
# Script located at: scripts/visualization_pipeline.py (Task 16 block)
```
