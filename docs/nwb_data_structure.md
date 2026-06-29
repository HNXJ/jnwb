# NWB Data Structure & Optimization Guide

This document outlines the organization, extraction strategies, and performance guardrails for handling Omission NWB datasets.

---

## NWB File Organization

Omission sessions are structured in the Neurodata Without Borders (NWB) standard format:
- `/acquisition`: Contains raw neural signals, including LFP (`probe_X_lfp`) and Multi-Unit Activity envelope (`probe_X_muae`).
- `/intervals`: Contains behavioral event timings (`omission_glo_passive`).
- `/units`: Contains spike times, clusters, brain areas, and recording quality metrics.
- `/electrodes`: Contains channel IDs, locations (areas), and coordinates (z-depth).

---

## Session-Probe-Area Mapping
Probes are assigned letters (A, B, C) corresponding to physical linear microelectrode arrays:
- **Probe A (index 0)**: Typically targeted at PFC/FEF.
- **Probe B (index 1)**: Typically targeted at early visual areas (V1, V2, V3, V4).
- **Probe C (index 2)**: Targeted at additional higher visual areas (MT, MST, TEO).

Standard area acronyms stored in the `location` column:
- Visual: `V1`, `V2`, `V3d`, `V3a`, `V4`, `MT`, `MST`, `TEO`, `FST`
- Frontal/Executive: `FEF`, `PFC`

---

## PyNWB Performance Guardrails

To ensure fast analysis execution on large neurophysiological datasets, adhere to the following optimization guidelines:

### 1. Lazy I/O (Do Not Load Eagerly)
Avoid reading full datasets into memory unless required. Rely on lazy-slicing dataset handles:
```python
# GOOD: Lazy slicing only the required channels/samples
lfp_data = lfp_obj.data[start_idx:end_idx, channel_indices]

# BAD: Loading the entire LFP array eagerly
lfp_data = np.asarray(lfp_obj.data)
```

### 2. Cache Metadata Tables
Avoid repeated `to_dataframe()` calls or NWB parses inside loops. Precompute and cache mapping structures once:
```python
# Cache unit-to-area mappings once at session load
self._units_df = enrich_units_dataframe(raw_units, self._electrodes_df)
```

### 3. Minimize Reopening
Do not call `NWBHDF5IO.read()` repeatedly within area or condition loops. Read the session once at the entry point of your pipeline.
