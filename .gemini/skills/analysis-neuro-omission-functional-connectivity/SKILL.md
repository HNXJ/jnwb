---
name: analysis-neuro-omission-functional-connectivity
---
# analysis-neuro-omission-functional-connectivity

## 1. Problem
This skill encompasses the legacy instructions for analysis-neuro-omission-functional-connectivity.
Legacy Purpose/Info:
# analysis-neuro-omission-functional-connectivity

## Purpose
Quantifies inter-area synchronization via Power Envelope Correlations ("Spectral Harmony") and bias-free Pairwise Phase Consistency (PPC).

## Input
| Name | Type | Description |
|------|------|-------------|
| power_envelopes | ndarray(11, T) | Time-resolved band power per area |
| spike_phases | ndarray(N_spikes,) | LFP phases at spike times |
| regional_mask | dict | Grouping of electrodes into 11 areas |

## Output
| Name | Type | Description |
|------|------|-------------|
| harmony_matrix | ndarray(11, 11) | Pearson correlation of power envelopes |
| ppc_spectrum | ndarray(F,) | Phase consistency across 1-100 Hz |

## Key Formula
- **PPC**: `(Σ cos(θ_i - θ_j)) / C(N,2)` — bias-free alternative to PLV

## Example
```python
import numpy as np
envelopes = np.random.rand(11, 1000)
harmony = np.corrcoef(envelopes)
assert np.allclose(np.diag(harmony), 1.0)
print(f"""[result] Harmony matrix shape: {harmony.shape}""")
```

## Files
- [lfp_connectivity.py](file:///omission/src/analysis/lfp/lfp_connectivity.py) — Core implementation

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
