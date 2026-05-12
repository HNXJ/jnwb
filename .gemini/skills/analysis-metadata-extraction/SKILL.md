---
name: analysis-metadata-extraction
---
# analysis-metadata-extraction

## 1. Problem
This skill encompasses the legacy instructions for analysis-metadata-extraction.
Legacy Purpose/Info:
# analysis-metadata-extraction

## Purpose
Extracts NWB trial metadata (start/stop times, conditions, events) into CSV for tabular analysis and cross-referencing with neural data.

## Input
| Name | Type | Description |
|------|------|-------------|
| nwb_path | str | Path to `.nwb` recording |
| table_name | str | `omission_glo_passive` (preferred) or `trials` (fallback) |

## Output
| Name | Type | Description |
|------|------|-------------|
| trial_csv | str | Path to `ses-<ID>_trials.csv` with all interval columns |

## Example
```python
import pynwb, pandas as pd
with pynwb.NWBHDF5IO('ses-230818.nwb', 'r') as io:
    nwb = io.read()
    df = nwb.intervals['omission_glo_passive'].to_dataframe()
    df.to_csv('metadata_audit.csv', index=False)
    print(f"""[result] Extracted {len(df)} trials""")
```

## Files
- [extract_trial_metadata.py](file:///omission/codes/scripts/extract_trial_metadata.py) — Source

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
