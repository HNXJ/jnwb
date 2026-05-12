---
name: analysis-omission-suite
---
# analysis-omission-suite

## 1. Problem
This skill encompasses the legacy instructions for analysis-omission-suite.
Legacy Purpose/Info:
# analysis-omission-suite

## Purpose
Central router for the `src/f0xx_*` figure generation pipeline. Maps analytical modules to output figures in `outputs/oglo-8figs/`.

## Input
| Name | Type | Description |
|------|------|-------------|
| target_module | str | `f0xx` analysis directory name (e.g. `f038_layer_granger`) |
| data_source | DataLoader | Via `src/analysis/io/loader.py` |

## Output
| Name | Type | Description |
|------|------|-------------|
| html_figures | list[str] | Interactive HTML files in `outputs/oglo-8figs/f0xx/` |
| csv_results | list[str] | Raw data exports |

## Example
```python
import subprocess
subprocess.run(["python", "src/f038_layer_granger/script.py"])
print(f"""[result] Check outputs/oglo-8figs/f038/""")
```

## Files
- [run_pipeline.py](file:///omission/src/scripts/run_pipeline.py) — Master executor
- [src/f0xx_*/script.py] — Per-figure entrypoints

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
