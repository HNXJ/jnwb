---
name: analysis-neuro-omission-unit-classification
---
# analysis-neuro-omission-unit-classification

## 1. Problem
This skill encompasses the legacy instructions for analysis-neuro-omission-unit-classification.
Legacy Purpose/Info:
# analysis-neuro-omission-unit-classification

## Purpose
Categorizes neurons into functional types (S+, O+, S-, O-) based on epoch-specific firing rate ratios. Implements Top-10 indexing for high-fidelity population analysis.

## Input
| Name | Type | Description |
|------|------|-------------|
| spike_matrix | ndarray(trials, units, T) | Binned spike counts |
| epochs | dict | `{fx: (-500,0), p1: (0,531), d1: (531,1031), p2: (1031,1562)}` |

## Output
| Name | Type | Description |
|------|------|-------------|
| unit_labels | dict[str, str] | Unit ID → functional category (S+/O+/S-/O-) |
| top10_indices | dict[str, list] | `{area: {S+: [...], O+: [...]}}` |

## Key Formulas
- **S+ Score**: `Mean(p1) / (Mean(fx) + ε)` — stimulus responsiveness
- **O+ Score**: `Mean(p2) / (Mean(d1) + ε)` — omission responsiveness
- Classification: S+ if Score_S > threshold AND Score_S > Score_O, vice versa

## Example
```python
from src.analysis.spiking.putative_classification import get_top_units
top_o_pfc = get_top_units(spk_matrix, area='PFC', type='O+', top_n=10)
print(f"""[result] Top 10 PFC O+ indices: {top_o_pfc}""")
```

## Files
- [putative_classification.py](file:///omission/src/analysis/spiking/putative_classification.py) — Core logic

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
