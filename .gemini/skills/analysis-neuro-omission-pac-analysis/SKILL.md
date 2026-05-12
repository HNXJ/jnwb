---
name: analysis-neuro-omission-pac-analysis
---
# analysis-neuro-omission-pac-analysis

## 1. Problem
This skill encompasses the legacy instructions for analysis-neuro-omission-pac-analysis.
Legacy Purpose/Info:
# analysis-neuro-omission-pac-analysis

## Purpose
Computes Phase-Amplitude Coupling (PAC) via the Tort Modulation Index (MI). Quantifies how low-frequency phase (Theta) modulates high-frequency amplitude (Gamma).

## Input
| Name | Type | Description |
|------|------|-------------|
| lfp_trace | ndarray(T,) | Raw or broadband LFP |
| f_phase | tuple | Low-freq band (e.g. `(4, 8)` Hz) |
| f_amp | tuple | High-freq band (e.g. `(40, 80)` Hz) |
| n_bins | int | Phase bins (default: 18) |

## Output
| Name | Type | Description |
|------|------|-------------|
| mi_value | float | Modulation Index (KL-divergence from uniform) |
| comodulogram | ndarray(F_phase, F_amp) | MI heatmap over frequency pairs |

## Example
```python
from src.f019_pac_analysis.analysis import calculate_modulation_index
mi = calculate_modulation_index(lfp_trace, f_phase=(4,8), f_amp=(40,80), n_bins=18)
print(f"""[result] MI = {mi:.6f}""")
```

## Files
- [script.py](file:///omission/src/f019_pac_analysis/script.py) — Core implementation

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
