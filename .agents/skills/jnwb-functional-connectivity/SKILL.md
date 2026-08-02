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
Primary files: `functions.py` (cross_modal_comparison, network_connectivity, tfr_correlate_areas),
`connectivity.py` (granger_causality, spike_mutual_information), `jrsa.py` (unified similarity
engine). `spectral.py` has only `band_power` -- no coherence or spike-field-coupling function
exists there or anywhere else in the package (see the Granger Causality section below).

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

## Granger Causality

```python
# jnwb.connectivity.granger_causality — real function, confirmed at jnwb/connectivity.py:365
gc = oa.granger_causality(sig1, sig2, order=5, device='cpu', ridge=0.0, criterion='aic')
# Returns F_2_to_1 / F_1_to_2 directional causality plus residual diagnostics
# (lightweight ADF + Ljung-Box) -- do not read GC as biological directionality
# when those diagnostics warn. `device` defaults to 'cpu'; GPU dispatch is not
# confirmed wired through this function specifically (a `cupy` import exists
# elsewhere in connectivity.py, not verified inside granger_causality itself)
# -- do not assume `device='cuda'` here without checking the current source.
```

**No `spectral.coherence()` or `spectral.spike_field_ppc()` exist in `jnwb/spectral.py`.**
An earlier version of this skill documented both as real functions; verified 2026-07-29 by
grepping `jnwb/spectral.py` for `def coherence`/`def spike_field_ppc` — only `band_power()`
is defined there. Confirmed with `select:` — the corpus has **no volume-conduction-safe
coupling estimator anywhere** (no imaginary coherency, no orthogonalized power envelope) and
**no bipolar/Laplacian re-referencing utility**. Both are required before any LFP-LFP or
spike-LFP coupling result can be trusted (see `context/figures/fig06_band_power_coupling/README.md`
and `fig07_lfp_spike_coupling/README.md`) and must be written from scratch, not imported.
`jnwb.jrsa` (see below) has a real `granger` and `phase_slope` metric in its dispatch table
(`_METRIC_DISPATCH` in `jrsa.py`) plus generic permutation/FDR stats machinery that a new
coupling estimator can reuse by registering as another dispatch entry, or by calling its
stats/permutation helpers directly on a custom-computed coupling value.

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
