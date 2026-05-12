---
name: design-neuro-omission-advanced-plotting
---
# design-neuro-omission-advanced-plotting

## 1. Problem
This skill encompasses the legacy instructions for design-neuro-omission-advanced-plotting.
Legacy Purpose/Info:
# design-neuro-omission-advanced-plotting

## Purpose
Publication-quality Plotly visualization spec: Kaleido-Free HTML export, Madelane Golden Dark theme, modebar SVG download, multi-panel layouts.

## Mandatory Rules
1. Export via `fig.write_html(include_plotlyjs='cdn')` — never `write_image`
2. Enable SVG download: `fig.update_layout(modebar_add=['toImage'])`
3. Color: Gold `#CFB87C` (S+/FF/Gamma), Purple `#9400D3` (O+/FB/Beta)
4. Background: White `#FFFFFF`, Grids: `#D3D3D3`, Axes: `#000000`
5. Bicubic smoothing on heatmaps: `zsmooth='best'`

## Input
| Name | Type | Description |
|------|------|-------------|
| data_tensor | ndarray | Processed data (TFR, connectivity, traces) |
| labels | dict | Axis labels, trace names |
| layout_config | dict | Title, axis limits, colorbar |

## Output
| Name | Type | Description |
|------|------|-------------|
| html_path | str | Standalone `.html` with embedded Plotly |

## Example
```python
import plotly.graph_objects as go
fig = go.Figure()
fig.add_trace(go.Scatter(x=time, y=gamma, name="S+ Gamma", line=dict(color="#CFB87C")))
fig.add_trace(go.Scatter(x=time, y=beta, name="O+ Beta", line=dict(color="#9400D3")))
fig.update_layout(modebar_add=['toImage'])
fig.write_html("output/figure.html", include_plotlyjs='cdn')
```

## Files
- [plotting.py](file:///omission/src/analysis/visualization/plotting.py) — OmissionPlotter

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
