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
- `jnwb.get_all_units_metadata(nwb_file)`: Extract comprehensive unit table metadata across probes.
- `jnwb.classify_unit_quality(unit_row)`: Assign unit quality classification based on SNR and isolation metrics.
- `jnwb.electrode_inventory(nwb_file)`: Summarize electrode probe channels and coordinate tables.
- `jnwb.compress_fp32(arr, bits=16)`: Lossy/lossless float compression for large electrophysiology matrices.

## 3. Invariants & Safeguards
1. **Addressing Robustness**: `map_peak_channel_to_area` checks multiple standard column names (`location`, `area`, `group_name`) and handles multi-area strings without throwing KeyError.
2. **Channel Coordinate Normalization**: Probe depths must be referenced consistently; check electrode DataFrame coordinates (`z`) before computing layer boundaries.
3. **Lossless vs Lossy Compression**: `compress_fp32` requires explicit bit-precision validation to avoid truncating low-amplitude neural oscillations.

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
