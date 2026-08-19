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
Probes are assigned letters (A, B, C, and D for sessions with a 4th probe - confirmed
present in V182o sessions) corresponding to physical linear microelectrode arrays.
**The probe letter -> area assignment is NOT fixed across subjects/sessions** - it is
determined per-recording by the physical probe insertion, not a stable convention.
Confirmed by real precomputed TFR filenames across 3 sessions:
- `sub-C31o_ses-230630`: A=PFC, B=MT/V4, C=V1/V3
- `sub-C31o_ses-230823`: A=FEF, B=MST/MT, C=V1/V2/V3
- `sub-V182o_ses-260629`: A=PFC, B=FEF, C=FST/MST, D=TEO (frontal probe B here, not visual)

Always resolve area from the real `location`/`area`/`group_name` column via
`jnwb.addressing.map_peak_channel_to_area` (or the enriched `area` column from
`enrich_units_dataframe`) - never assume a probe letter implies a specific area.

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
