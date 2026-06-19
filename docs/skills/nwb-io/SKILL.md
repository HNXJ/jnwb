---
name: nwb-io
description: >
  Canonical NWB data-access layer for the Omission project. Covers NWBHDF5IO
  open/close discipline, trial-onset extraction by condition code, spike-time
  retrieval, LFP channel lookup, and area/probe/layer address resolution.
---

# Skill: nwb-io — NWB I/O and Address Layer

## Purpose
Provide a small agent (or a step inside a larger agent) with everything needed
to **open an NWB file safely, resolve addresses, and extract raw data vectors**
without touching higher-level analysis code.

---

## 1. Environment and Imports

```python
# --- Always use explicit close handling ---
from pynwb import NWBHDF5IO
import numpy as np
import pandas as pd
from pathlib import Path
from src.analysis.io.nwb_address import (
    CANONICAL_CONDITIONS, CONDITION_NUMBER_MAP, NUMBER_TO_CONDITION,
    SEQUENCE_TIMING_MS,
)
from src.analysis.io.loader import DataLoader          # NPY array access
```

> **Doctrine**: Never open an NWB file without a context manager (`with`).
> Never mutate an NWB file (`mode='r'` always).

---

## 2. Opening an NWB File

```python
NWB_DIR = "D:/analysis/nwb"    # canonical mount point; never hardcode absolute paths in code

def get_nwb_map(nwb_dir: str = NWB_DIR) -> dict[str, str]:
    """Return {session_id: path} for all NWB files in nwb_dir."""
    import glob, os
    m = {}
    for f in glob.glob(f"{nwb_dir}/*.nwb"):
        bn = os.path.basename(f)
        sid = bn.split("ses-")[1].split("_")[0] if "ses-" in bn else bn.split("_")[0]
        m[sid] = f
    return m

# Usage
nwb_map = get_nwb_map()   # → {"230629": "D:/analysis/nwb/sub-V198o_ses-230629_rec.nwb", ...}

with NWBHDF5IO(nwb_map["230629"], "r", load_namespaces=True) as io:
    nwb = io.read()
    # all reads happen inside the with-block
```

---

## 3. Trial Onset Extraction by Condition

Condition codes live in `nwb.intervals['omission_glo_passive']`.

```python
def get_onsets(intervals_df: pd.DataFrame, condition: str) -> np.ndarray:
    """Return p1-onset timestamps (sec) for a named condition string."""
    codes = CONDITION_NUMBER_MAP[condition]
    correct   = pd.to_numeric(intervals_df['correct'],               errors='coerce') == 1.0
    stim_num  = pd.to_numeric(intervals_df['stimulus_number'],       errors='coerce') == 2.0
    cond_num  = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce').isin(codes)
    return intervals_df.loc[correct & stim_num & cond_num, 'start_time'].values

# Example
with NWBHDF5IO(nwb_map["230629"], "r", load_namespaces=True) as io:
    nwb = io.read()
    intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
    aaab_onsets = get_onsets(intervals_df, "AAAB")   # shape (N_trials,)
```

**All 12 conditions** → use `CANONICAL_CONDITIONS` from `nwb_address.py`.

---

## 4. Spike Time Retrieval

Spike times per unit are in `nwb.units.to_dataframe()['spike_times']`.

```python
with NWBHDF5IO(nwb_map["230629"], "r", load_namespaces=True) as io:
    nwb = io.read()
    units_df = nwb.units.to_dataframe()
    unit_id  = 23
    spike_times = units_df.loc[unit_id, 'spike_times']   # 1-D np.ndarray (seconds)
```

> **Never** index units with integer ranges — always use `loc[uid]` with the
> explicit unit_id from the metadata CSV.

---

## 5. LFP / Electrode Retrieval

```python
with NWBHDF5IO(nwb_map["230629"], "r", load_namespaces=True) as io:
    nwb = io.read()
    # Find all available LFP acquisition keys
    lfp_keys = [k for k in nwb.acquisition if 'lfp' in k.lower()]
    # Load one LFP series (shape: time × channels)
    lfp_series = nwb.acquisition[lfp_keys[0]]
    lfp_data   = lfp_series.data[:]      # full array: (T, N_channels)
    fs         = float(lfp_series.rate)  # sampling rate, usually 1000.0 Hz
    electrodes  = lfp_series.electrodes.to_dataframe()   # area, probe, group, etc.
```

---

## 6. Channel → Area/Probe Mapping

```python
# After loading electrodes df from an NWB file:
# electrodes.columns: ['location', 'group_name', 'group', 'imp', 'filtering', ...]
# 'location' usually holds the area string (e.g. "V1", "PFC").
# probe_id = peak_channel_id // 128  (implicit rule — validated in SPSAM pipeline)

from src.analysis.io.loader import DataLoader
dl = DataLoader()
area = dl.normalize_area("DP (V4)")   # → "V4"
```

---

## 7. Stable-Plus Population Filter

Always gate analysis on Stable-Plus units before any computation.

```python
import pandas as pd
metadata = pd.read_csv("outputs/spsam/grand_unit_metadata.csv")
stable   = metadata[metadata["is_stable"]].copy()
# Columns of interest: session_id, unit_id, area, layer, snr, firing_rate, group, is_stable
```

**Stable-Plus criteria**:
| Criterion | Threshold |
|-----------|-----------|
| `firing_rate` | ≥ 1.0 Hz |
| `snr` | > 0.8 |
| `presence_ratio` | ≥ 0.98 |
| `is_stable` | `True` |

---

## 8. Sequence Timing Reference

From `src.analysis.lfp.lfp_constants.SEQUENCE_TIMING_MS` (all ms from p1 onset = 0):

| Epoch | Start ms | End ms | Role |
|-------|----------|--------|------|
| p1 | 0 | 531 | First stimulus |
| d1 | 531 | 1031 | Inter-stimulus delay |
| p2 | 1031 | 1562 | Second stimulus / omission slot 2 |
| d2 | 1562 | 2062 | Inter-stimulus delay |
| p3 | 2062 | 2593 | Third stimulus / omission slot 3 |
| d3 | 2593 | 3093 | Inter-stimulus delay |
| p4 | 3093 | 3624 | Fourth stimulus / omission slot 4 |
| fx | -500 | 0 | Baseline / fixation window |

---

## 9. Critical Validation Rules

From `src.analysis.task_semantics`:
- **Code 101** = p1 stimulus onset (`stimulus_number == 2`) — **use this as alignment anchor**
- **Code 100** = fixation cue — **NEVER use as p1 anchor**
- AAXB = condition_number 4 (omission at p3)
- AXAB = condition_number 3 (omission at p2)
- AAAX = condition_number 5 (omission at p4)

---

## 10. Key Files

| File | Role |
|------|------|
| [nwb_address.py](file:///D:/workspace/omission/src/analysis/io/nwb_address.py) | Condition maps, address utilities |
| [loader.py](file:///D:/workspace/omission/src/analysis/io/loader.py) | NPY DataLoader |
| [task_semantics.py](file:///D:/workspace/omission/src/analysis/task_semantics.py) | Event-code validation |
| [lfp_constants.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_constants.py) | Timing, bands, areas |
| [contracts/constants.py](file:///D:/workspace/omission/src/analysis/contracts/constants.py) | Event code constants |
