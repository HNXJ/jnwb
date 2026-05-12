---
name: analysis-granger-convergence-debug
---
# analysis-granger-convergence-debug

## 1. Problem
This skill encompasses the legacy instructions for analysis-granger-convergence-debug.
Legacy Purpose/Info:
# analysis-granger-convergence-debug

## Purpose
Diagnoses Granger causality model stability by sweeping AR orders, checking NaN counts, and comparing directional causality. Absorbs `analysis-granger-result-extraction` (band-specific GC extraction) and `analysis-nitime-inspection` (output shape debugging).

## Input
| Name | Type | Description |
|------|------|-------------|
| lfp_data | ndarray(C, T) | Multi-channel LFP for V1 and PFC |
| model_orders | list[int] | AR orders to sweep (e.g. `[5, 10, 20, 50]`) |
| fs | float | Sampling rate (default: 1000 Hz) |
| bands | dict | Frequency band definitions (e.g. `{'beta': (13,30), 'gamma': (35,80)}`) |

## Output
| Name | Type | Description |
|------|------|-------------|
| convergence_report | dict | Per-order: NaN count, F-stats, optimal lag |
| band_causality | dict | Per-band mean GC in each direction (FF/FB) |
| dominant_direction | str | `"FF"` or `"FB"` per band |

## Example
```python
import numpy as np
from statsmodels.tsa.stattools import grangercausalitytests

v1 = np.load('v1_lfp.npy').mean(axis=(0,1))
pfc = np.load('pfc_lfp.npy').mean(axis=(0,1))
v1 = (v1 - v1.mean()) / v1.std()
pfc = (pfc - pfc.mean()) / pfc.std()

data = np.stack([pfc, v1], axis=1)  # tgt=col0, src=col1
for order in [5, 10, 20]:
    res = grangercausalitytests(data, maxlag=order, verbose=False)
    best_p = min(res[lag][0]['ssr_ftest'][1] for lag in range(1, order+1))
    print(f"""[result] order={order}: best_p={best_p:.6f}""")
```

## Files
- [debug_granger_convergence.py](file:///omission/codes/scripts/debug_granger_convergence.py) — Source
- [math-neuro-omission-connectivity-metrics](file:///omission/.gemini/skills/math-neuro-omission-connectivity-metrics/SKILL.md) — Theory

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
