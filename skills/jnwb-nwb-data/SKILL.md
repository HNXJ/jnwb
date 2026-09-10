---
name: jnwb-nwb-data
description: NWB inspection, path addressing, anatomical mapping, electrode/unit QC,
  metadata census, and compression.
---

# `jnwb-nwb-data` — NWB Data, Addressing & Metadata

## 1. Trigger
Activate this skill when inspecting NWB files, resolving paths, mapping electrode channels to brain areas/layers, auditing unit quality tiers, or compressing arrays.

## 2. Task-to-Primitive Routing Matrix
- `jnwb.paths.describe()`: Inspect repository data paths and NWB file discovery.
- `jnwb.map_peak_channel_to_area(peak_channel_id, electrodes_df)`: Map channel index to brain area string.
- `jnwb.classify_layer_from_depth(peak_channel_id, electrodes_df)`: Classify cortical depth into layer tiers ('Deep' vs 'Superficial').
- `jnwb.enrich_units_dataframe(units_df, electrodes_df)`: Standardize units DataFrame with unit_id, area, and layer annotations.
- `jnwb.get_all_units_metadata(nwb_paths, filter_quality=False)`: Extract comprehensive unit table metadata across sessions.
- `jnwb.classify_unit_quality(units_df, thresholds=None)`: Add quality tier columns to a units DataFrame.
- `jnwb.electrode_inventory(nwb_paths)`: Summarize electrode probe channels and coordinate tables.
- `jnwb.compress_fp32(src, dst=None, *, drop_convolved=False, verify=True)`: NWB file fp32 compression (path I/O, not in-memory arrays).

## 3. Invariants & Safeguards
1. **Addressing Robustness**: `map_peak_channel_to_area` checks multiple standard column names (`location`, `area`, `group_name`) and handles multi-area strings without throwing KeyError.
2. **Channel Coordinate Normalization**: Probe depths must be referenced consistently; check electrode DataFrame coordinates (`z`) before computing layer boundaries.
3. **NWB compression contract**: `compress_fp32` converts on-disk NWB electrical series to fp32; verify round-trip with `verify=True` before deleting sources.

## 4. Minimal Workflow
```python
import jnwb
import pandas as pd

elec_df = pd.DataFrame({'location': ['V1'], 'z': [1200.0]}, index=[10])
area = jnwb.map_peak_channel_to_area(10, elec_df)
layer = jnwb.classify_layer_from_depth(10, elec_df)
assert area == 'V1' and layer == 'Deep'
```

## 5. Verification
- Validate addressing against synthetic and real electrode DataFrames.
- Ensure compression roundtrip matches declared tolerances.

## 6. Canonical Documentation Links
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
