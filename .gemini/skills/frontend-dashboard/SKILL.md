---
name: frontend-dashboard
---
# frontend-dashboard

## 1. Problem
This skill encompasses the legacy instructions for frontend-dashboard.
Legacy Purpose/Info:
# frontend-dashboard

## Purpose
React-based Omission Dashboard: figure hosting, iframe scaling, gallery view, and asset discovery from `outputs/`.

## Input
| Name | Type | Description |
|------|------|-------------|
| figure_dir | str | `outputs/oglo-8figs/` HTML figures + READMEs |
| port | int | Dev server port (default: 5173) |

## Output
| Name | Type | Description |
|------|------|-------------|
| live_url | str | `http://localhost:5173/` |
| ui_state | str | Interactive gallery with maximize/minimize |

## Commands
```bash
cd D:/workspace/omission/dashboard
npm run dev
```

## Files
- [App.jsx](file:///omission/dashboard/src/App.jsx) — Main dashboard logic

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
