---
name: analysis-neuro-omission-oculomotor-suite
---
# analysis-neuro-omission-oculomotor-suite

## 1. Problem
This skill encompasses the legacy instructions for analysis-neuro-omission-oculomotor-suite.
Legacy Purpose/Info:
# analysis-neuro-omission-oculomotor-suite

## Purpose
Detects saccades/microsaccades, validates fixation stability, and generates pupillometric correlates of attention during visual omissions.

## Input
| Name | Type | Description |
|------|------|-------------|
| eye_data | ndarray(2, T) | Raw XY in DVA from `.bhv2.mat` |
| fs | float | 1000 Hz |
| screen_dist | float | 57 cm |
| vel_thresh | float | 30 DVA/s for saccade detection |

## Output
| Name | Type | Description |
|------|------|-------------|
| saccade_events | list[dict] | `{time, amplitude, velocity, direction}` |
| microsaccades | list[dict] | Subset with amplitude < 1.5° |
| pupil_trace | ndarray(T,) | Normalized pupillometry |

## Example
```python
from src.analysis.oculomotor import detect_saccades
eye_x, eye_y = get_calibrated_eye_data(session_id)
saccades = detect_saccades(eye_x, eye_y, fs=1000, thresh=30)
microsaccades = [s for s in saccades if s.amplitude < 1.5]
print(f"""[result] {len(microsaccades)} microsaccades""")
```

## Files
- [EyeDataMapper.py](file:///omission/src/analysis/io/eye_mapper.py) — NWB-BHV correlator

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
