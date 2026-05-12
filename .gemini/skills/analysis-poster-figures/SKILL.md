---
name: analysis-poster-figures
---
# analysis-poster-figures

## 1. Problem
This skill encompasses the legacy instructions for analysis-poster-figures.
Legacy Purpose/Info:
# analysis-poster-figures

## Purpose
Conference poster plotting functions (SFN, Cosyne). Multi-panel layouts, condition color coding, shaded omission windows, SEM overlays.

## Input
| Name | Type | Description |
|------|------|-------------|
| traces | dict | Mean/SEM arrays keyed by `(area, condition, band)` |
| timing | dict | Event onset/offset indices for shaded rectangles |
| palette | dict | `{gold: '#CFB87C', violet: '#8F00FF', pink: '#FF1493'}` |

## Output
| Name | Type | Description |
|------|------|-------------|
| figure | go.Figure | Multi-panel Plotly figure |
| html_path | str | Saved interactive HTML |

## Example
```python
from src.figures.poster_figures import plot_band_power_hierarchy
fig = plot_band_power_hierarchy(traces=data, band='Beta', areas=['V1','PFC'], conditions=['RRRR','RXRR'])
fig.write_html("outputs/posters/beta_hierarchy.html")
print(f"""[result] Poster figure exported""")
```

## Files
- [poster_figures.py](file:///omission/src/figures/poster_figures.py) — Implementation

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
