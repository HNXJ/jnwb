---
name: jnwb-spiking
description: |
  Single-unit spike analysis using jnwb. Covers raster plots, PSTHs,
  autocorrelograms, omission response classification, phase-locking index,
  and unit quality scoring. Uses UnitAnalyzer object and raster_plot /
  psth_analysis / autocorrelogram canonical functions. Also wraps the
  jnwb.spiking module (compute_response_metrics, classify_omission_response).
---

# jnwb-spiking: Single-Unit Spike Analysis

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `analyzers.py` (UnitAnalyzer), `functions.py` (raster_plot, psth_analysis, autocorrelogram), `spiking.py`

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
from jnwb import UnitAnalyzer
from jnwb import (
    raster_plot, psth_analysis, autocorrelogram,
    find_units, unit_quality_scores,
    compute_response_metrics, classify_omission_response, phase_locking_index,
)
```

## UnitAnalyzer Object

```python
# Raster aligned to trial onset
raster = UnitAnalyzer.raster(spike_times, trial_onsets, window_ms=(-500, 2000))
# Returns: {'raster': [[...], [...], ...], 'n_trials': 40, 'n_spikes': 980}

# PSTH with bootstrap CI
psth = UnitAnalyzer.psth(spike_times, trial_onsets, bin_size_ms=10)
# Returns: {'psth': array, 'sem': array, 'bin_centers': array, 'bootstrap_ci': {'lo': ..., 'hi': ...}}

# Autocorrelogram + refractory period test
acg = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=100)
# Returns: {'acg': array, 'refractory_period_violation': p_value, 'is_single_unit': bool}

# Quality metrics
quality = UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=400, firing_rate=15)
# Returns: {'firing_rate_hz': 15, 'refr_violations_pct': 2.1, 'is_good_single_unit': True, ...}
```

## Canonical Functions (session-level)

```python
session = oa.read('path/to/file.nwb')

# Raster via session
raster = raster_plot(session, unit_id=42, condition='AAXB', phase=3, window_ms=(-500, 2000))

# PSTH via session
psth = psth_analysis(session, unit_id=42, condition='AAXB', phase=3, bin_size_ms=10)

# Autocorrelogram via session
acg = autocorrelogram(session, unit_id=42, max_lag_ms=100)

# Find units by criteria
units_df = find_units(session, quality='stable_plus', area='V1', firing_rate_range=(1, 200))

# Unit quality scores
quality = unit_quality_scores(session, unit_id=42)
```

## OmissionSession Shortcut: raster_suite

```python
# Full suite: raster + PSTH + autocorrelogram in one call
session.raster_suite(unit_id=42, condition='AAXB', phase=3)
```

## jnwb.spiking Module Functions

```python
# Response metrics (baseline vs. evoked FR)
metrics = compute_response_metrics(spike_times, trial_onsets,
                                   baseline_window=(-0.250, -0.050),
                                   response_window=(0.0, 0.150))
# Returns: {'baseline_rate': ..., 'response_rate': ..., 'response_zscore': ...}

# Classify omission selectivity
stim_onsets = session.get_epochs(condition='AAAB')["start_time"].values
omission_onsets = session.get_epochs(condition='AAXB')["start_time"].values
omit_class = classify_omission_response(spike_times, stim_onsets, omission_onsets)
# Returns: {'sig_s': bool, 'sig_o': bool, 'stimulus_rate': ..., 'omission_rate': ...}

# Phase-locking index
pli = phase_locking_index(spike_times, lfp_phase_array, lfp_timestamps)
# Returns: {'pli': ..., 'preferred_phase': ..., 'rayleigh_pvalue': ...}
```

## Response Classification (S+ / S- / Other)

- **S+** — Significant firing rate increase during omission window
- **S-** — Significant decrease
- **Other / non-selective** — No significant change  

Grand database counts (from stable-plus units): S+ = 1,468 | S- = 986 | Other = 3,586

## Laminar Assignment (Putative Layer)

- **Superficial**: unit channel within ±10 channels of another verified superficial unit → N = 614
- **Deep**: unit channel within ±10 channels of another verified deep unit → N = 1,813
- **Unresolved**: ~25 % remain unresolved
