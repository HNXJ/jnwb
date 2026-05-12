---
name: analysis-lfp-pipeline
---
# analysis-lfp-pipeline

## 1. Problem
This skill encompasses the legacy instructions for analysis-lfp-pipeline.
Legacy Purpose/Info:
# analysis-lfp-pipeline

## Purpose
End-to-end LFP analysis: NPY/NWB loading, TFR computation, SFC/PPC, cross-area connectivity, and Kaleido-Free Plotly output. Absorbs `lfp-core`.

## Input
| Name | Type | Description |
|------|------|-------------|
| raw_data | ndarray / path | Memory-mapped `.npy` arrays or NWB files |
| area | str | Target brain area (V1, PFC, etc.) |
| condition | str | Trial condition code (e.g. `AXAB`) |
| freq_range | tuple | Analysis band (default: 2-100 Hz) |
| baseline_win | tuple | Normalization window in ms (default: -1000 to 0) |

## Output
| Name | Type | Description |
|------|------|-------------|
| tfr_db | ndarray(F, T) | dB-normalized power heatmap |
| sfc_spectrum | ndarray(F,) | Pairwise Phase Consistency values |
| html_figure | str | Path to saved interactive HTML plot |

## Key Formulas
- **dB normalization**: `10 * log10(P / P_baseline)`
- **Band definitions**: Delta (1-4Hz), Beta (13-30Hz), Gamma (40-80Hz)
- **Channel selection**: Best channel per area by SNR

## Example
```python
from src.core.data_loader import DataLoader
from src.analysis.lfp_pipeline import LFPAnalyzer

loader = DataLoader()
lfp = loader.get_signal(mode="lfp", area="V1", session="230630")
analyzer = LFPAnalyzer(sampling_rate=1000)
tfr_db = analyzer.compute_tfr(lfp, baseline_win=(-1.0, 0.0))
analyzer.plot_tfr(tfr_db, save_path="outputs/fig5_v1_tfr.html")
print(f"""[result] TFR shape: {tfr_db.shape}""")
```

## Files
- [loader.py](file:///omission/src/analysis/io/loader.py) — Data access
- [lfp_pipeline.py](file:///omission/src/analysis/lfp/lfp_pipeline.py) — Core implementation
- [OmissionPlotter](file:///omission/src/analysis/visualization/plotting.py) — Visualization

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
