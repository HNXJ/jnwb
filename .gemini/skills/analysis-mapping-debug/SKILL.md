---
name: analysis-mapping-debug
---
# analysis-mapping-debug

## 1. Problem
This skill encompasses the legacy instructions for analysis-mapping-debug.
Legacy Purpose/Info:
# analysis-mapping-debug

## Purpose
Traces unit-to-area assignment step-by-step through NWB electrode tables. Diagnoses mislocalization from compound labels or segment-based mapping errors.

## Input
| Name | Type | Description |
|------|------|-------------|
| nwb_path | str | Path to `.nwb` file |
| unit_idx | int | Index of the unit to trace |
| CHANNELS_PER_PROBE | int | 128 (constant) |
| AREA_MAPPING | dict | Label normalization (e.g. `{'DP': 'V4'}`) |

## Output
| Name | Type | Description |
|------|------|-------------|
| debug_trace | dict | `{unit_idx, peak_channel_id, probe_id, raw_label, assigned_area}` |

## Example
```python
import pynwb
io = pynwb.NWBHDF5IO('ses-230818.nwb', 'r')
nwb = io.read()
chan_id = int(nwb.units[42]['peak_channel_id'])
probe_id = chan_id // 128
raw_loc = nwb.electrodes[chan_id, 'location']
print(f"""[trace] Unit 42: ch={chan_id}, probe={probe_id}, raw={raw_loc}""")
```

## Files
- [debug_mapping.py](file:///omission/codes/scripts/debug_mapping.py) — Source

## 2. Solution Architecture
Executes the analytical pipeline using the standardized Omission hierarchy.
- **Input**: NWB data or Numpy arrays via DataLoader.
- **Output**: Interactive HTML/SVG figures saved to `D:/drive/outputs/oglo-8figs/`.

## 3. Skills/Tools
- Python 3.14
- canonical LFP/Spike loaders (`src/analysis/io/loader.py`)
- OmissionPlotter (`src/analysis/visualization/plotting.py`)
- **Code/DOI Reference**: Internal Codebase (src)

## 4. Version Control
- All changes must be committed.
- Comply with the GAMMA protocol (Commit-Pull-Push after every action).

## 5. Rules/Cautions
- Ensure strict adherence to the Madelane Golden Dark aesthetic.
- Folders must be named using dashes (e.g., `f0xx-keyword`), NO underscores.
- Only run on 'Stable-Plus' neuronal populations.
