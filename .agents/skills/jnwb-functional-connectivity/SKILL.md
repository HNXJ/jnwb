---
name: jnwb-functional-connectivity
description: |
  Functional connectivity and network analysis using jnwb. Covers cross-modal
  comparison (LFP vs. spike networks), mutual information between spike trains,
  TFR-to-TFR MI, spike-to-TFR MI, and network_connectivity canonical function.
  Use this skill for any inter-area or inter-unit correlation / MI / lead-lag analysis.
---

# jnwb-functional-connectivity: Networks and Mutual Information

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `functions.py` (cross_modal_comparison, network_connectivity), `spectral.py` (coherence, spike_field_ppc)

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import (
    cross_modal_comparison,
    network_connectivity,
    tfr_correlate_areas,
    jrsa,
    JRSAResult,
)
from jnwb import spectral
```

## Unified Relationship Analysis Core (JRSA)

For all multi-dimensional similarity, connection, and relationship analysis, use `oa.jrsa`. It handles dimension alignment, resampling (downsampling, linear/cubic interpolation, DTW), GPU-acceleration, and dispatches to 14 metrics (including classic Kriegeskorte RSA, linear CKA, Granger Causality, and Transfer Entropy).

```python
# Unified analysis on multi-dimensional matrices (e.g. Area-Layer-Band spectro-laminar tensors)
result = oa.jrsa(
    x1, x2,
    metric="rsa",          # or "cka", "granger", "transfer_entropy", "phase_slope", "cosine" etc.
    adim="time",           # axis name or index to align
    lag=0,                 # lag alignment in samples
    stats=True,            # compute statistics
    permutations=1000,     # statistical permutation count
    bootstrap=1000,        # bootstrap iterations for confidence intervals
    device="auto"          # cupy/torch/jax/numpy backend
)

# Accessing JRSAResult fields
print(f"Stat: {result.value:.3f}, p-val: {result.p:.4f}")

# Quick reporting methods
result.summary()          # prints human-readable snapshot
result.plot()             # displays correlation matrices / 1D line curves
result.save("result.json") # supports json, npz, or csv outputs
```

## Cross-Modal Comparison (LFP vs Spikes)

```python
# Compare LFP TFR array vs spike rate array with lag analysis
result = cross_modal_comparison(tfr_array, spike_array,
                                 lag_range_ms=(-500, 500))
# Returns: {'correlation': 0.42, 'lag_ms': -50,
#           'lfp_leads_spikes': True,
#           'parametric': {...}, 'non_parametric': {...}, 'fdr_pval_parametric': ...}
```

## Network Connectivity from Correlation Matrix

```python
session = oa.read('path/to/file.nwb')

# Build correlation matrix from multi-unit firing rates, then:
net = network_connectivity(session, correlation_matrix, threshold=0.3)
# Returns: {'n_nodes': 7, 'n_edges': 12, 'density': 0.57,
#           'mean_degree': 3.4, 'clustering_coefficient': 0.61}
```

## Inter-Area TFR Correlation

```python
corr = tfr_correlate_areas(session, area1='V1', area2='V4',
                            band='alpha', condition='AAXB')
# Full dual-stats return (Pearson + Spearman + FDR)
```

## Spectral Coherence & Granger Causality

All connectivity functions support GPU-acceleration via PyTorch and CuPy by specifying `device='cuda'` (which falls back cleanly to CPU if CUDA is unavailable):

```python
# GPU-Accelerated Granger Causality (CuPy)
gc = oa.granger_causality(sig1, sig2, order='auto', device='cuda')

# GPU-Accelerated Coherence (CuPy)
coh = spectral.coherence(sig1, sig2, sfreq=1000.0, fmin=30, fmax=80, device='cuda')

# Spike-field coupling (PPC)
ppc = spectral.spike_field_ppc(spike_times, lfp_signal, sfreq=1000.0, band='beta')
```

## Mutual Information (Spike-to-Spike)

For Shannon MI between spike trains, use the canonical `spike_mutual_information` function (exported at package root):

```python
mi = oa.spike_mutual_information(
    spike_times1,
    spike_times2,
    time_window=(0.0, 3.0),   # (start, end) time window in seconds
    bin_size_ms=10.0           # bin size in milliseconds
)
# Returns Mutual Information in bits.
```

## Key Analysis Patterns

### Spike-to-TFR MI

```python
# 1. Load session
session = oa.read('path/to/file.nwb')

# 2. Get spike train for a unit
units = session.get_units(quality='stable_plus', area='V1')
spike_times = units.loc[unit_id, 'spike_times']

# 3. Load TFR band power
bp = spectral.band_power(lfp_signal, sfreq=1000.0, band='gamma')

# 4. Cross-modal MI
result = cross_modal_comparison(bp, spike_times, lag_range_ms=(-200, 200))
```

### TFR-to-TFR MI

```python
bp_v1 = spectral.band_power(lfp_v1, sfreq=1000.0, band='gamma')
bp_v4 = spectral.band_power(lfp_v4, sfreq=1000.0, band='gamma')
result = cross_modal_comparison(bp_v1, bp_v4, lag_range_ms=(-200, 200))
```

## Output Storage

MI / connectivity outputs → `d:/workspace/omission/outputs/`  
Network figures → `d:/workspace/omission/outputs/publication_visual_review/`
