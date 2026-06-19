---
name: tfr
description: >
  Multitaper Time-Frequency Representation (TFR) computation and visualization
  for LFP signals in the Omission project. Covers frequency-dependent n_cycles
  policy, dB baseline normalization, and interactive Plotly heatmap export.
---

# Skill: tfr — Multitaper Time-Frequency Representation

## Purpose
Produce publication-quality TFR heatmaps using the canonical multitaper engine
in `src/analysis/lfp/lfp_tfr.py`. This skill covers data preparation, parameter
selection, normalization, and visualization, with working code examples.

---

## 1. Core Engine

The canonical TFR engine uses **MNE's multitaper** (`tfr_array_multitaper`) with
frequency-dependent `n_cycles` for stable time-frequency resolution.

```python
from src.analysis.lfp.lfp_tfr import (
    compute_tfr,
    n_cycles_for_freqs,
    default_band_time_support_ms,
)
from src.analysis.lfp.lfp_constants import FS_LFP, BANDS
import numpy as np
import mne
from mne.time_frequency import tfr_array_multitaper
```

---

## 2. Full TFR Computation

```python
def run_tfr(epochs, fs=1000.0, freqs=None, bands=BANDS):
    """
    Compute baseline-normalized TFR.

    epochs : (n_trials, n_channels, n_times) in µV
    fs     : sampling rate in Hz
    freqs  : frequency array; defaults to 2–150 Hz log-spaced
    Returns:
        tfr_db : (n_channels, n_freqs, n_times) dB-normalized power
        freqs  : (n_freqs,) Hz
        times  : (n_times,) seconds
    """
    if freqs is None:
        freqs = np.logspace(np.log10(2), np.log10(150), 60)

    n_cycles = n_cycles_for_freqs(freqs, bands=bands)

    # MNE expects (n_epochs, n_channels, n_times)
    power = tfr_array_multitaper(
        epochs,                    # (epochs, channels, times)
        sfreq=fs,
        freqs=freqs,
        n_cycles=n_cycles,
        output='power',
        verbose=False,
    )  # (n_epochs, n_channels, n_freqs, n_times)

    # Average across trials
    power_avg = np.mean(power, axis=0)  # (channels, freqs, times)

    # dB normalize using pre-stimulus baseline (-1000 to 0 ms)
    n_pre = int(1.0 * fs)   # samples for 1000 ms pre-stimulus
    baseline = np.mean(power_avg[:, :, :n_pre], axis=2, keepdims=True)
    tfr_db = 10.0 * np.log10(power_avg / (baseline + 1e-30))

    n_times = epochs.shape[-1]
    pre_ms  = 1000                                          # hard-coded 1000ms pre
    times   = (np.arange(n_times) - n_pre) / fs            # seconds

    return tfr_db, freqs, times
```

---

## 3. n_cycles Policy (Critical)

The `n_cycles` per frequency determines the trade-off between time and frequency
resolution. The project uses a **band-dependent effective time support**:

| Band | Effective Support |
|------|------------------|
| Theta (3–7 Hz) | **1200 ms** (need ~3–9 cycles for stability) |
| Alpha, Beta (8–30 Hz) | **200 ms** |
| Gamma (32–200 Hz) | **150 ms** |

Formula: `n_cycles(f) = (support_ms / 1000) × f`

```python
# Example: get n_cycles for a given frequency array
freqs    = np.arange(3, 100, 1)  # Hz
n_cycles = n_cycles_for_freqs(freqs, bands=BANDS)
# n_cycles is clipped to [2.0, 20.0] automatically
```

---

## 4. Canonical Timing Overlays

Apply vertical reference lines at these events (from `SEQUENCE_TIMING_MS`):

| Event | ms from p1 | Purpose |
|-------|-----------|---------|
| p1 | 0 | Stimulus onset reference |
| p2 | 1031 | Slot 2 stimulus/omission |
| p3 | 2062 | Slot 3 stimulus/omission |
| p4 | 3093 | Slot 4 stimulus/omission |

---

## 5. Plotly TFR Heatmap (Canonical Output)

```python
import plotly.graph_objects as go
from src.analysis.lfp.lfp_constants import GOLD, VIOLET, WHITE

def plot_tfr_heatmap(tfr_db, freqs, times_ms, title, save_path):
    """
    tfr_db   : (n_freqs, n_times)   — one channel, dB normalized
    freqs    : (n_freqs,)  in Hz
    times_ms : (n_times,)  in ms from p1
    """
    fig = go.Figure(data=go.Heatmap(
        z=tfr_db,
        x=times_ms,
        y=freqs,
        colorscale='RdBu_r',
        zmid=0,
        colorbar=dict(title="dB", thickness=15),
    ))

    # Vertical event markers
    for label, t_ms in [("p1", 0), ("p2", 1031), ("p3", 2062), ("p4", 3093)]:
        fig.add_vline(x=t_ms, line_dash="dash",
                      line_color=GOLD if label == "p1" else VIOLET,
                      annotation_text=label, annotation_position="top")

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", x=0.5, font=dict(size=18)),
        xaxis_title="Time from p1 onset (ms)",
        yaxis_title="Frequency (Hz)",
        yaxis=dict(type='log'),
        paper_bgcolor=WHITE,
        plot_bgcolor=WHITE,
    )
    fig.write_html(save_path)
    print(f"[result] TFR saved to {save_path}")
    return fig
```

---

## 6. Best-Channel Selection

Use the channel with the **highest SNR** from the stable Stable-Plus population
for any given area. From the metadata CSV:

```python
import pandas as pd
metadata = pd.read_csv("outputs/spsam/grand_unit_metadata.csv")
area_best = (
    metadata[metadata["is_stable"] & (metadata["area"] == "V1")]
    .sort_values("snr", ascending=False)
    .iloc[0]
)
best_channel = int(area_best["peak_channel_global"])
session_id   = str(area_best["session_id"])
```

---

## 7. Output Spec

| Field | Value |
|-------|-------|
| File format | Interactive **HTML** (Plotly) |
| dB range | Symmetric ±3 to ±6 dB typical |
| Colormap | `RdBu_r` (red = increase, blue = decrease) |
| Background | `#FFFFFF` (pure white) |
| Gold color `#CFB87C` | Sink / stimulus signal markers |
| Violet color `#9400D3` | Source / omission markers |

---

## 8. Key Files

| File | Role |
|------|------|
| [lfp_tfr.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_tfr.py) | Multitaper TFR engine (canonical) |
| [lfp_constants.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_constants.py) | Bands, timing, palette |
| [lfp_preproc.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_preproc.py) | Pre-processing (filter before TFR) |
| [f005_tfr/](file:///D:/workspace/omission/src/f005_tfr/) | Figure 5 TFR module |
| [visualization/lfp_plotting.py](file:///D:/workspace/omission/src/analysis/visualization/lfp_plotting.py) | LFP-specific plot utilities |
