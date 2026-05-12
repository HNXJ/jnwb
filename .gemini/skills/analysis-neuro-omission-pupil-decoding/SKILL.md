---
name: analysis-neuro-omission-pupil-decoding
---
# analysis-neuro-omission-pupil-decoding

## 1. Problem
This skill encompasses the legacy instructions for analysis-neuro-omission-pupil-decoding.
Legacy Purpose/Info:
# analysis-neuro-omission-pupil-decoding

## Purpose
Decodes stimulus identity and omission surprise from pupillometry. Maps pupil diameter shifts to arousal and cognitive load via SVM classification.

## Input
| Name | Type | Description |
|------|------|-------------|
| pupil_raw | ndarray(trials, T) | Raw pupil diameter |
| blink_mask | ndarray(trials, T) | Boolean blink timestamps |
| trial_labels | ndarray(trials,) | Condition/identity labels |
| cv_folds | int | Cross-validation folds (default: 5) |

## Output
| Name | Type | Description |
|------|------|-------------|
| accuracy_trace | ndarray(T,) | Time-resolved classification performance |
| surprise_metric | float | Peak dilation amplitude in omission window |

## Example
```python
from src.f021_pupil_decoding.analysis import decode_pupil_identity
accuracy = decode_pupil_identity(pupil_data, labels, cv=5)
print(f"""[result] Max decoding accuracy: {max(accuracy):.2%}""")
```

## Files
- [script.py](file:///omission/src/f021_pupil_decoding/script.py) — Core implementation

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
