---
name: jnwb-core
description: |
  Load, explore, and manage Omission NWB sessions using the jnwb API.
  Covers oa.read(), oa.batch_read(), OmissionSession data access methods,
  behavioral condition/phase mappings, and the unit quality tier system.
  Use this skill for any task that starts with opening an NWB file or
  querying basic session metadata.
---

# jnwb-core: Session I/O and Data Access

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `session.py`, `__init__.py`

## Import

```python
import sys
sys.path.insert(0, 'd:/workspace/omission')
import jnwb as oa
```

## Load a Session

```python
session = oa.read('D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb')
# Optional context (default already set to omission_glo_passive):
session = oa.read(path, context='omission_glo_passive')
```

## Batch Load (all sessions)

```python
sessions = oa.batch_read('D:/analysis/nwb', pattern='*.nwb')
```

Session count drifts as data lands — verify the current count via
`artifacts/data/session_readiness.csv` or `nwb_catalog.json` rather than
hardcoding a number; "13 sessions" is a known-stale legacy figure (see
`.agents/AGENTS.md`, 17 NWB files as of the 2026-07-09 receipt).

## Data Access Methods (OmissionSession)

```python
session.info()           # Summary dict: n_units, areas, etc.
session.summary()        # Print formatted summary

# Units
units_df = session.get_units(quality='stable_plus', area='V1')
units_df = session.get_units(quality='stable', firing_rate_range=(1, 200))

# Channels / electrodes
elec_df  = session.get_electrodes(area='V4')

# Epochs / trials
epochs   = session.get_epochs(phase=3, condition='AAXB', correct_only=True)

# Channel maps
lfp_map  = session.lfp_channel_areas()          # channel → area/layer
unit_map = session.channel_unit_mapping()        # unit_id → channel_id, area, layer
```

## Behavioral Condition Codes

| Name  | Condition Numbers | Meaning                           |
|-------|-------------------|-----------------------------------|
| AAAB  | 1, 2              | All A's, B deviant at p4          |
| AXAB  | 3                 | Omission at p2                    |
| AAXB  | 4                 | Omission at p3 (canonical omit)   |
| AAAX  | 5                 | Omission at p4                    |
| BBBA  | 6, 7              | All B's, A deviant at p4          |
| BXBA  | 8                 | B omission at p2                  |
| BBXA  | 9                 | B omission at p3                  |
| BBBX  | 10                | B omission at p4                  |
| RRRR  | 11–26             | Random sequences                  |
| RXRR/RRXR/RRRX | 27–50 | Random + omission variants   |

## Phase Numbers

| phase argument | stimulus_number | Slot     |
|----------------|-----------------|----------|
| `1`            | 1               | Fixation |
| `2`            | 2               | p1       |
| `3`            | 3               | p2       |
| `4`            | 4               | p3       |
| `5`            | 5               | p4       |

## Unit Quality Tiers

| Quality       | Definition                                                    |
|---------------|---------------------------------------------------------------|
| `stable_plus` | is_stable=True, FR > 1 Hz, SNR > 0.8, 100 % trial presence   |
| `stable`      | is_stable=True but not stable_plus                            |
| `mua`         | Multi-unit activity                                           |
| `unstable`    | Poor quality / unstable recordings                            |

Grand database: 6,040 units total.  
Stable-plus gate: 661 units.  
Stable-only metrics table: 3,071 units (`stable_units_calculated_metrics.csv`).

## Key Source CSV Paths

```
d:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv
d:/workspace/omission/outputs/publication_figures/stable_units_calculated_metrics.csv
```

## NWB File Locations

```
D:/analysis/nwb/sub-C31o_ses-*.nwb   (subject C31o, multiple dates)
D:/analysis/nwb/sub-V198o_ses-*.nwb  (subject V198o, multiple dates)
```

## Critical footgun: unit identity is a DataFrame row position, not `unit_id`

`session.get_spike_times(unit_id)` (and equivalent internal lookups) index by **raw DataFrame
row position** (`units_df.index`), **not** the `unit_id` column. `unit_id` is a per-probe-local
kilosort id — it can have gaps and is not globally unique across probes/sessions. Passing a
`unit_id` column value where a row-position index is expected silently fetches the wrong unit's
spikes (confirmed real bug, found in `jnwb/trajectory.py::build_time_resolved_matrix` and in a
`grand_unit_table_shuffle_sso.csv` consumer script — both were using the `unit_id` column).
Before writing any new code that fetches spikes for a given unit, confirm which identifier you
are actually holding.

## Footgun: bytes-encoded h5py numeric columns

On some sessions (confirmed: `sub-C31o_ses-230816`, `sub-C31o_ses-230901`), raw intervals-table
columns read directly via h5py come back as **byte strings** (`b'2.0'`, `b'nan'`), not floats.
`float(b'2.0')` works but naive numeric comparisons on the raw bytes silently produce wrong trial
counts (370 vs the real 246 for one condition, until fixed). This only bites code that reads
`stimulus_number`/`correct`/`task_condition_number`/`start_time` etc. directly via h5py instead
of through `session.get_epochs(...)` — prefer the session API; if you must read raw, coerce with
an explicit bytes-aware numeric parser and sanity-check trial counts against a known session.

## Standard NWB Content Atlas

Omission NWB session files contain the following physiological signals:

1. **Local Field Potentials (LFP)**:
   * *Location*: `nwb.acquisition['probe_X_lfp']` (where `X` is `0` or `1` representing probe indices).
   * *Usage*: Low-frequency local neural populations (delta, theta, alpha, beta, gamma).
2. **Multi-Unit Activity envelope (MUAe)**:
   * *Location*: `nwb.acquisition['probe_X_muae']` (precalculated multi-unit envelopes).
   * *Usage*: Population-level high-frequency envelope signals.
3. **Single Units (Spikes)**:
   * *Location*: `nwb.units` (unit spike times, sorting waveforms, metrics).
   * *Usage*: Firing rates, autocorrelograms, single-unit tuning.
4. **Spiking Signal Types**:
   * *Unconvolved Spikes*: Raw discrete event spike times retrieved via `session.get_units()` or `nwb.units['spike_times']`.
   * *Convolved Spikes / PSTH*: Continuous rate representations computed by smoothing discrete spikes with a temporal kernel (e.g. Gaussian window or binning via `UnitAnalyzer.psth`).

## direct h5py fallback access (head-free & speedups)
On older sessions (such as `V182o` and visual sessions containing PyNWB Device schema anomalies), attempting a standard PyNWB object build can cause build blockages. Use direct `h5py` reads to load LFP matrices and behavioral arrays without using full PyNWB schemas:

```python
import h5py
import numpy as np

# direct read template
with h5py.File("D:/analysis/nwb/sub-V182o_ses-260706.nwb", "r") as f:
    # 1. Direct LFP extraction (avoiding device metadata build blocks)
    # LFP data is under acquisition/probe_[idx]_lfp/electrical_series/data
    lfp_data = f["acquisition/probe_0_lfp/probe_0_lfp_data/data"][:] # channels x samples
    lfp_timestamps = f["acquisition/probe_0_lfp/probe_0_lfp_data/timestamps"][:]
    
    # 2. Pupil diameter behavioral tracking
    pupil_data = f["acquisition/pupil_diameter/data"][:]
    pupil_timestamps = f["acquisition/pupil_diameter/timestamps"][:]
```

