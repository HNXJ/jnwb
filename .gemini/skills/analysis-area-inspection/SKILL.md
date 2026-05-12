---
name: analysis-area-inspection
---
# analysis-area-inspection

## 1. Problem
This skill encompasses the legacy instructions for analysis-area-inspection.
Legacy Purpose/Info:
# analysis-area-inspection

## Purpose
QC utility: inspects unique brain area labels in processed unit CSVs to catch nomenclature inconsistencies before batch analysis.

## Input
| Name | Type | Description |
|------|------|-------------|
| csv_path | str | Path to `checkpoints/omission_units_layered.csv` with an `area` column |

## Output
| Name | Type | Description |
|------|------|-------------|
| unique_areas | list[str] | All distinct area labels found |
| flagged_rows | DataFrame | Rows with compound labels (e.g. `V3/V4`) for manual audit |

## Example
```python
import pandas as pd
df = pd.read_csv('checkpoints/omission_units_layered.csv')
print(f"""[result] Unique areas: {df['area'].unique()}""")
print(f"""[flag] V3/V4 entries: {len(df[df['area'] == 'V3/V4'])}""")
```

## Files
- [omission_units_layered.csv](file:///omission/checkpoints/omission_units_layered.csv) — Primary data source

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
