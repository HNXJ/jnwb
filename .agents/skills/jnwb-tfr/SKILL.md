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
# Extract frequency band (using the canonical 7-band table)
alpha = TFRAnalyzer.extract_band(tfr_data, band='alpha')       # 8–15 Hz
beta  = TFRAnalyzer.extract_band(tfr_data, band='beta')        # 15–30 Hz
low_gamma = TFRAnalyzer.extract_band(tfr_data, band='low_gamma') # 30–60 Hz
high_gamma = TFRAnalyzer.extract_band(tfr_data, band='high_gamma') # 60–120 Hz

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

| Band       | Range (Hz) |
|------------|------------|
| delta      | 1–4        |
| theta      | 4–8        |
| alpha      | 8–15        |
| beta       | 15–30       |
| low_gamma  | 30–60       |
| high_gamma | 60–120      |
| broadband  | 1–150      |

## TFR Array Locations

```
D:/workspace/data/tfr_arrays/
  sub-C31o_ses-230823-C-FEF-AXAB.npy
  sub-C31o_ses-230823-C-FEF-AAXB.npy
  ... (naming: sub-{subj}_ses-{date}-{probe}-{area}-{condition}.npy)
```

## Stable-Plus LFP Channels: Selection Rule

Use only **Stable-Plus** channels (channels with at least one stable-plus unit) for LFP analysis.
