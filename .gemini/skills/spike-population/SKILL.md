---
name: spike-population
---
# spike-population

## 1. Problem
This skill encompasses the legacy instructions for spike-population.
Legacy Purpose/Info:
# spike-population

## Purpose
Population-level spiking dynamics: unit extraction, firing rate traces, Fano factor trajectories, and validated V1-PFC unit assignments.

## Input
| Name | Type | Description |
|------|------|-------------|
| session_id | str | Canonical date |
| areas | list[str] | Target cortical areas |

## Output
| Name | Type | Description |
|------|------|-------------|
| fr_traces | ndarray(units, T) | Population-averaged firing rates |
| unit_map | dict | Validated area assignments |

## Mandatory Rules
- Import from `src/analysis/spiking/*`, NOT legacy `codes/functions/spiking/`
- Output arrays must follow hierarchical area order (V1→PFC)

## Example
```python
from src.analysis.spiking.utils import extract_unit_traces
traces = extract_unit_traces(session_id="230629")
print(f"""[result] Trace shape: {traces.shape}""")
```

## Files
- [src/analysis/spiking/*](file:///omission/src/analysis/spiking/) — Core algorithms

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
