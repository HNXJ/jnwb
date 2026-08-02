---
name: jnwb-metadata
description: |
  Unit metadata extraction, quality classification, SNR analysis, and session
  diagnostics using jnwb. Covers the jnwb.metadata module (get_all_units_metadata,
  classify_unit_quality, unit_census_report, get_snr_analysis, electrode_inventory)
  and the jnwb.diagnostics module (audit_session, compare_sessions).
  Use this skill when you need the grand unit table, quality flags, or
  session-level audit reports.
---

# jnwb-metadata: Unit Metadata and Diagnostics

Module root: `d:/workspace/omission/jnwb/`  
Primary files: `metadata.py`, `diagnostics.py`

## Import

```python
import sys; sys.path.insert(0, 'd:/workspace/omission')
from jnwb import (
    get_all_units_metadata,
    classify_unit_quality,
    unit_census_report,
    get_snr_analysis,
    electrode_inventory,
    audit_session,
    compare_sessions,
    print_audit_report,
)
```

## metadata Module

### get_all_units_metadata

```python
# Full unit table for one or more sessions (by paths)
units_df = get_all_units_metadata('D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb')
# DataFrame columns include: unit_id, area, layer, firing_rate, snr,
#   waveform_duration, presence_ratio, is_stable, stable_plus, quality
```

### classify_unit_quality

```python
# Re-apply quality tier logic to a units DataFrame
units_df = classify_unit_quality(units_df)
# Adds/updates: quality_class ('Good' | 'Fair' | 'Poor') and is_valid (bool)
```

Quality rules:
- `Good`: Passes all thresholds (quality, SNR, firing rate)
- `Fair`: Fails minor thresholds
- `Poor`: Fails critical thresholds (quality < 1.0 or SNR < 1.0)

### unit_census_report

```python
# Return population breakdown
report_df = unit_census_report(units_df, group_by=['session_id', 'area'])
# Returns summary DataFrame with counts and statistics
```

### get_snr_analysis

```python
snr_stats = get_snr_analysis(units_df)
# Returns dict with SNR statistics and pass rates
```

### electrode_inventory

```python
elec_df = electrode_inventory('D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb')
# DataFrame of electrode metadata and unit assignments
```

## diagnostics Module

### audit_session

```python
audit = audit_session('D:/analysis/nwb/sub-C31o_ses-230630_rec.nwb')
# Returns dict: {'nwb_file': ..., 'passed': True, 'warnings': [], 'errors': [], ...}
```

### compare_sessions

```python
# Compare multiple sessions by paths
comparison_df = compare_sessions(['file1.nwb', 'file2.nwb'])
# Returns DataFrame with audit metrics comparing sessions
```

### print_audit_report

```python
print_audit_report(audit, verbose=True)   # Formatted console output of audit dict
```

## Grand Database CSVs

```python
import pandas as pd

grand = pd.read_csv(
    'd:/workspace/omission/outputs/publication_figures/data_tables/grand_database_6040_units.csv'
)
# Columns: unit_id, session, area, layer, firing_rate, snr, waveform_duration_us,
#          presence_ratio, is_stable, is_stable_plus, quality, response_class, ...

stable = pd.read_csv(
    'd:/workspace/omission/outputs/publication_figures/data_tables/stable_units_calculated_metrics.csv'
)
# Columns: unit_id, firing_rate_tier, fano_factor, burst_index, waveform_duration_bin, ...
```

## Key Numbers

| Metric               | Value  |
|----------------------|--------|
| Total units          | 6,040  |
| Stable               | 3,071  |
| Stable-plus          | 661    |
| Sessions             | verify via `artifacts/data/session_readiness.csv` / `nwb_catalog.json` — do not hardcode; "13" is a known-stale legacy figure (21 NWB files as of the 2026-07-26 receipt, see `.agents/AGENTS.md`) |
| Subjects             | 3 (C31o, V182o, V198o) |

## Bytes-Aware String Decoding
On specific sessions (e.g. `sub-C31o_ses-230816` and `230901`), direct h5py string dataset reads come back as **bytes objects** (like `b'2.0'`, `b'nan'`, or `b'stable_plus'`), which fail standard string equality matching and trial sorting checks.
Always coerce and decode byte-encoded attribute columns to standard UTF-8 strings before querying:

```python
# Safe decode utility for dataset attributes and columns
def decode_bytes(val):
    if isinstance(val, bytes):
        return val.decode("utf-8")
    return val

# Example check loop
for col in ["stimulus_number", "correct", "task_condition_number"]:
    val = dataset[idx]
    cleaned_val = decode_bytes(val)
    # Perform numeric/string checks safely on cleaned_val
```

