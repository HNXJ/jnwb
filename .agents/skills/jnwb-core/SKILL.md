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

## Batch Load (all 13 sessions)

```python
sessions = oa.batch_read('D:/analysis/nwb', pattern='*.nwb')
```

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
