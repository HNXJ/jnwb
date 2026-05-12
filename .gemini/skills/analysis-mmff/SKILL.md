---
name: analysis-mmff
---
# analysis-mmff

## 1. Problem
This skill encompasses the legacy instructions for analysis-mmff.
Legacy Purpose/Info:
# analysis-mmff

## Purpose
Mean-Matched Fano Factor (MMFF) computation and visualization. Controls for firing-rate confounds in variability analysis. Absorbs `science-neuro-omission-variability-quenching`.

## Input
| Name | Type | Description |
|------|------|-------------|
| spike_data | ndarray(trials, units, T) | Binned spike counts |
| nwb_path | str | For unit-to-area mapping |
| win_size | int | Sliding window (default: 150ms) |
| step | int | Step size (default: 5ms) |
| sigma | float | Gaussian smoothing (default: 5.0) |

## Output
| Name | Type | Description |
|------|------|-------------|
| mmff_traces | dict | `{area: {condition: ndarray(T,)}}` time-resolved MMFF |
| html_figure | str | Interactive Plotly HTML with SEM shading |

## Key Formula
- **Fano Factor**: `FF = σ² / μ` (FF<1 = regular, FF>1 = bursty)
- **Mean-Matching**: Equalizes FR distributions across time bins via subsampling before computing FF
- **Quenching**: Stimulus/surprise collapses high-variance spontaneous state

## Example
```python
from src.analysis.mmff_pipeline import compute_mmff, plot_mmff
mmff_data = compute_mmff(spike_path='spikes.npy', nwb_path='session.nwb', win_size=150, step=5)
fig = plot_mmff(mmff_data, area='V1')
fig.write_html('outputs/v1_mmff.html')
print(f"""[result] MMFF computed for {len(mmff_data)} areas""")
```

## Files
- [omission_hierarchy_utils.py](file:///omission/codes/functions/omission_hierarchy_utils.py) — Core functions
- [compute_mean_matched_fano.py](file:///omission/codes/scripts/compute_mean_matched_fano.py) — Orchestrator

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
