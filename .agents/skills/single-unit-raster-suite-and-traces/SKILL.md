---
name: single-unit-raster-suite-and-traces
description: >
  Generating 40-trial raster plots with family-matched SDF/PSTH traces and waveform inserts.
---

# Skill: single-unit-raster-suite-and-traces — Raster Suites & SDF Traces

## Purpose
Code primitives and layout formatting for rendering 40-trial raster suites with spike density function (SDF) traces and waveform insets.

---

## 1. Figure Layout
- Left column (4 panels): 40-trial rasters for each task condition.
- Bottom panel: Combined SDF/PSTH traces colored by condition (Gold/Violet scheme).
- Right-column panel 1: Unit metadata card (ID, Area, SNR, FR, etc.).
- Right-column panel 2: Mean spike waveform trace.

---

## 2. Waveform & Time Parameters
- **Time range**: [-1000, 4000] ms relative to trial start.
- **SDF Smoothing**: Gaussian kernel filter with $\sigma = 40$ ms.
- **Waveform color**: `#9400D3` (Violet) for omission units, `#CFB87C` (Gold) for stimulus units.

---

## 3. SDF Construction
```python
import scipy.ndimage as ndimage
import numpy as np

def compute_sdf(spike_times, onsets, time_bins=np.arange(-1000, 4001), sigma=40.0):
    spike_mat = np.zeros((len(onsets), len(time_bins)))
    for ti, t_on in enumerate(onsets[:40]):
        trial_sp = spike_times[(spike_times >= t_on - 1.0) & (spike_times <= t_on + 4.0)]
        aligned_ms = (trial_sp - t_on) * 1000.0
        hist, _ = np.histogram(aligned_ms, bins=np.arange(-1000.5, 4001.5))
        spike_mat[ti, :] = hist
    mean_rate = np.mean(spike_mat, axis=0) * 1000.0
    return ndimage.gaussian_filter1d(mean_rate, sigma=sigma)
```
