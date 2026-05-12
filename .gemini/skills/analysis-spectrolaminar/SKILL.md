---
name: analysis-spectrolaminar
---
# analysis-spectrolaminar

## 1. Problem
This skill encompasses the legacy instructions for analysis-spectrolaminar.
Legacy Purpose/Info:
# analysis-spectrolaminar

## Purpose
Spectrolaminar profiling: computes depth-resolved Alpha/Beta vs Gamma power from linear-probe LFP and identifies the L4 crossover channel for laminar assignment.

## Input
| Name | Type | Description |
|------|------|-------------|
| lfp_data | ndarray(C, T) | Raw LFP (n_channels × n_timepoints) |
| fs | float | Sampling frequency (default: 1000 Hz) |
| bands | implicit | Alpha/Beta: 8-30 Hz, Gamma: 35-80 Hz |

## Output
| Name | Type | Description |
|------|------|-------------|
| alpha_beta_profile | ndarray(C,) | Normalized low-freq power per channel |
| gamma_profile | ndarray(C,) | Normalized high-freq power per channel |
| l4_channel | int | Channel index where Gamma > Alpha/Beta (crossover) |

## Example
```python
from codes.functions.vflip2_mapping import compute_spectrolaminar_profiles, find_crossover
profiles = compute_spectrolaminar_profiles(lfp_data, fs=1000.0)
l4 = find_crossover(profiles)
print(f"""[result] L4 crossover at channel {l4}""")
```

## Files
- [vflip2_mapping.py](file:///omission/codes/functions/vflip2_mapping.py) — Core

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
