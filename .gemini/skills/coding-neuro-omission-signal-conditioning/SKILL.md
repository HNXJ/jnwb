---
name: coding-neuro-omission-signal-conditioning
---
# coding-neuro-omission-signal-conditioning

## 1. Problem
This skill encompasses the legacy instructions for coding-neuro-omission-signal-conditioning.
Legacy Purpose/Info:
# coding-neuro-omission-signal-conditioning

## Purpose
DSP suite: spike→PSTH smoothing, Z-scoring, band-pass filtering (Butterworth), Hilbert phase/amplitude extraction, MUAe computation.

## Input
| Name | Type | Description |
|------|------|-------------|
| raw_tensor | ndarray(trials, ch, T) | Absolute units (µV or binary spikes) |
| fs | float | Sampling rate (1000 Hz or 30 kHz) |
| baseline_win | tuple | Window for normalization (e.g. -500 to 0 ms) |

## Output
| Name | Type | Description |
|------|------|-------------|
| psth | ndarray | Gaussian-smoothed firing rates (Hz) |
| z_signal | ndarray | Z-scored relative to baseline |
| analytic | ndarray(complex) | Hilbert transform (phase + envelope) |

## Key Parameters
- Gaussian σ: 20ms (spike smoothing)
- Butterworth: zero-phase via `scipy.signal.filtfilt`
- MUAe: rectify 1-3kHz band → 200Hz LPF

## Example
```python
from scipy.ndimage import gaussian_filter1d
psth = gaussian_filter1d(spikes.astype(float), sigma=20, axis=2) * 1000
baseline_mu = psth[:,:,:500].mean(axis=(0,2), keepdims=True)
baseline_sd = psth[:,:,:500].std(axis=(0,2), keepdims=True)
z_psth = (psth - baseline_mu) / (baseline_sd + 1e-6)
print(f"""[result] Z-PSTH shape: {z_psth.shape}""")
```

## Files
- [signal_processing.py](file:///omission/src/analysis/signal_processing.py) — Implementation

## 2. Solution Architecture
Executes the analytical pipeline using the standardized Omission hierarchy.
- **Input**: NWB data or Numpy arrays via DataLoader.
- **Output**: Interactive HTML/SVG figures saved to `D:/drive/outputs/oglo-8figs/`.

## 3. Skills/Tools
- Python 3.14
- canonical LFP/Spike loaders (`src/analysis/io/loader.py`)
- OmissionPlotter (`src/analysis/visualization/plotting.py`)
- **Code/DOI Reference**: Internal Codebase (src)

## 4. Version Control
- All changes must be committed.
- Comply with the GAMMA protocol (Commit-Pull-Push after every action).

## 5. Rules/Cautions
- Ensure strict adherence to the Madelane Golden Dark aesthetic.
- Folders must be named using dashes (e.g., `f0xx-keyword`), NO underscores.
- Only run on 'Stable-Plus' neuronal populations.
