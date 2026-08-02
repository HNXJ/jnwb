---
name: jnwb-tfr
description: |
  Time-Frequency Representation (TFR) analysis using jnwb. Covers TFRAnalyzer
  object methods and the five canonical TFR functions: tfr_trial_average,
  tfr_compare_conditions, tfr_correlate_areas, tfr_spectrolaminar,
  tfr_permutation_test. Also covers the jnwb.spectral module for band-power
  extraction and LFP spectrolaminar mapping. Use this for any LFP / TFR analysis.
---

# jnwb-tfr: Time-Frequency Representation Analysis

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `analyzers.py` (TFRAnalyzer), `functions.py` (tfr_*), `spectral.py`

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import TFRAnalyzer
from jnwb import (
    tfr_trial_average, tfr_compare_conditions,
    tfr_correlate_areas, tfr_spectrolaminar, tfr_permutation_test,
    lfp_channel_areas,
)
from jnwb import spectral
```

## TFRAnalyzer Object

```python
# Extract frequency band (canonical frequency band table)
theta      = TFRAnalyzer.extract_band(tfr_data, band='theta')      # 4–8 Hz
alpha      = TFRAnalyzer.extract_band(tfr_data, band='alpha')      # 8–14 Hz
beta       = TFRAnalyzer.extract_band(tfr_data, band='beta')       # 14–30 Hz
low_gamma  = TFRAnalyzer.extract_band(tfr_data, band='low_gamma')  # 30–50 Hz
high_gamma = TFRAnalyzer.extract_band(tfr_data, band='high_gamma') # 50–80 Hz

## Laminar Frequency Asymmetry & PARAFAC Tensor Components (Bastos 2012 / Chao 2018)

- **Superficial L2/3 Compartment**: Dominated by high-frequency $\gamma$-band power (30–120 Hz), broadcasting bottom-up prediction errors ($PE1$ local, $PE2$ global).
- **Deep L5/6 Compartment**: Dominated by lower-frequency $\alpha/\beta$-band power (8–30 Hz), conveying top-down predictions and prediction updates ($PE3$).
- **PARAFAC 3D Factorization**: Factorizes 3D tensors (Channels $\times$ Time-Frequency $\times$ Conditions) into $PE1$ ($\gamma_{\text{early}}$), $PE2$ ($\gamma_{\text{late}}$), and $PE3$ ($\alpha/\beta_{\text{decrease}}$).

# Trial-average (returns {'mean', 'std', 'sem', 'n_trials'})
avg = TFRAnalyzer.trial_average(tfr_data)

# Compare two conditions (vectorized t-test across all channels x freqs x time bins)
comparison = TFRAnalyzer.compare_conditions(tfr_stim, tfr_omit)
# Returns: {'n_tests', 'n_significant', 'fraction_significant', 'mean_diff',
#           'p_values' (array), 't_statistics' (array), 'summary'}

# Spectrolaminar: layer-wise power
layer_stats = TFRAnalyzer.by_layer(tfr_data, layer_bounds={'superficial': (0, 5), 'deep': (6, 15)})

# Inter-area TFR correlation (returns Pearson r + Spearman rho + FDR-corrected p-values)
corr = TFRAnalyzer.correlate_areas(tfr1, tfr2, band='alpha')
```

## Canonical Functions (session-level)

```python
session = oa.read('path/to/file.nwb')

# 1. Trial-averaged TFR
avg = tfr_trial_average(session, area='V1', condition='AAXB', phase=3, band='alpha')

# 2. Compare conditions (parametric + non-parametric + FDR automatically)
stats = tfr_compare_conditions(session, area='V4',
                                condition1='AAAB', condition2='AAXB', band='beta')

# 3. Inter-area correlation
corr = tfr_correlate_areas(session, area1='V1', area2='V4', band='alpha', condition='AAXB')

# 4. Spectrolaminar (layer-wise)
layers = tfr_spectrolaminar(session, area='MT', condition='omission')
# Returns: {'superficial': {...power stats...}, 'deep': {...power stats...},
#           'comparison': {...stats, FDR...}}

# 5. Permutation test
perm = tfr_permutation_test(session, area='V1',
                             condition1='AAAB', condition2='AAXB',
                             n_permutations=5000)

# LFP channel → area mapping
lfp_map = lfp_channel_areas(session, area='V1')
```

## OmissionSession Shortcuts

```python
session.plot_tfr(area='V1', condition='AAXB', phase=3)
session.trial_averaged_plot(area='V1', phase=3, condition='AAXB')
session.channel_averaged_plot(area='V4', phase=3, condition='AAXB')
session.spectrolaminar_motif(area='MT', condition='omission')
session.tfr_from_preprocessed(area='V1', band='alpha', condition='AAXB')
```

## jnwb.spectral Module

All spectral functions support GPU-acceleration via CuPy by specifying `device='cuda'` (which falls back cleanly to CPU if CUDA is unavailable):

```python
# GPU-Accelerated Band-power extraction
bp = spectral.band_power(lfp_signal, sfreq=1000.0, band='gamma', device='cuda')

# GPU-Accelerated Coherence
coh = spectral.coherence(sig1, sig2, sfreq=1000.0, fmin=30, fmax=80, device='cuda')

# Spike-field coupling (PPC)
ppc = spectral.spike_field_ppc(spike_times, lfp_signal, sfreq=1000.0, band='beta')

# Spectrolaminar vFLIP2 mapping
flip = spectral.vflip2(lfp_array, channel_depths, sfreq=1000.0)
```

## Frequency Band Definitions

Canonical bands — settled by the 2026-07-27 audit; do not re-drift. Every fitted coefficient
in `outputs/lfp_band_census_v2/` uses this set; alpha 8–12 / theta 3–8 / low gamma 30–60 /
high gamma 60–120 are pre-correction legacy values.

| Band       | Range (Hz) |
|------------|------------|
| delta      | 1–4        |
| theta      | 4–8        |
| alpha      | 8–14       |
| beta       | 14–30      |
| low_gamma  | 30–50      |
| high_gamma | 50–80      |
| broadband  | 1–150      |

## TFR Array Locations and Naming Convention

All TFR arrays are in `D:/workspace/data/tfr_arrays/`.  
Naming: `{session_prefix}-{probe_letter}-{area}-{condition}.npy`

Confirmed live examples (sub-C31o_ses-230823):
```
sub-C31o_ses-230823-A-FEF-RRRR.npy   (probe A = FEF for this session)
sub-C31o_ses-230823-B-MST-RXRR.npy   (probe B has MST and MT for this session)
sub-C31o_ses-230823-C-V1-AAAB.npy    (probe C has V1, V2, V3 for this session)
```

Probe → area assignment is **NOT fixed across sessions** — always resolve from  
`session_readiness.csv` / `nwb_catalog.json` or read the TFR directory listing per session.

**Conditions available** (12 per probe/area combination):
- Standard sequences: `AAAB`, `AXAB`, `AAXB`, `AAAX`, `BBBA`, `BXBA`, `BBXA`, `BBBX`
- R-family: `RRRR` (random, no omission), `RXRR` (omit p2), `RRXR` (omit p3), `RRRX` (omit p4)

**Array shape**: `(n_trials, n_channels, n_freqs, n_times)` — verified on disk 2026-08-02
(e.g. `sub-C31o_ses-230630-A-PFC-AAAB.npy` is `(44, 128, 99, 500)`). Confirm with `.shape`
before slicing; `TFRArray` orientation is trials-first, not channels-first.

**Session readiness** (2026-07-26 receipt; verify live — corpus grows):
- 21 NWB files total; TFR array corpus: **23 sessions / 1,236 npy files** on disk as of
  2026-08-02 (C31o 8, V182o 10, V198o 5) — this grew from the 17-session/948-file corpus that
  older text and `context/docs/CONTEXT.md` may still cite.
- Always gate on `artifacts/data/session_readiness.csv` before loading a TFR array.

Use only **Stable-Plus** channels (channels with at least one stable-plus unit) for LFP analysis.

## LFP memory preservation & lazy loading
Loading raw LFP datasets from NWB can exhaust available system memory (RAM) due to high sampling frequencies (usually 30 kHz downsampled to 1000 Hz in preprocessed files). 

### Guidelines for Memory Safety:
1. **Head-free Downsampling**: Ensure raw LFP electrical series data is downsampled to `1000 Hz` immediately upon direct loading.
2. **Channel-by-channel loading (lazy load)**: Avoid using ` data[:]` which loads all channels and trials into RAM. Instead, load only the channels corresponding to the targeted brain area/layer of interest. **There is no `electrical_series` group in these files** — the real layouts are `acquisition/probe_*_lfp/data` (C31o) and `acquisition/probe_*_lfp/probe_*_lfp_data/data` (V182o), see `jnwb-core`:
   ```python
   # Load only channels 0 to 10 of LFP dataset
   with h5py.File("path_to_nwb.nwb", "r") as f:
       lfp_ds = f["acquisition/probe_0_lfp/data"]  # or probe_0_lfp_data/data for V182o
       # Slicing keeps the load in RAM minimal
       lfp_channel_slice = lfp_ds[:, 0:10] # samples x 10 channels
   ```
3. **Decouple TFR arrays**: For multi-channel computations, utilize precomputed `.npy` arrays located in `D:/workspace/data/tfr_arrays/` rather than re-computing TFRs from raw signals on the fly.

