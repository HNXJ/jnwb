---
name: analysis-nwb-read-guardrails
---
# analysis-nwb-read-guardrails

## 1. Problem
This skill encompasses the legacy instructions for analysis-nwb-read-guardrails.
Legacy Purpose/Info:
# analysis-nwb-read-guardrails

## Purpose
Enforces lazy-loading, memory safety, and canonical NWB access patterns. Absorbs `coding-neuro-omission-nwb-pipeline` I/O contracts.

## Mandatory Rules
1. Import from `src.core.data_loader`, NOT legacy `src/utils/nwb_io.py`
2. Always use `mmap_mode='r'` for `.npy` files
3. Temporal alignment anchored to Code 101.0 (p1 onset)
4. Probe-local: `probe_id = peak_channel_id // 128`
5. Close NWB handles explicitly after use

## Input
| Name | Type | Description |
|------|------|-------------|
| session_id | str | Canonical date (e.g. `230629`) |
| modality | str | `LFP`, `Spikes`, or `Pupil` |
| condition | str | Trial condition code |

## Output
| Name | Type | Description |
|------|------|-------------|
| tensor | ndarray | `(trials, channels/units, samples)` aligned and lazy-loaded |

## Example
```python
from src.core.data_loader import DataLoader
loader = DataLoader(mmap=True)
v1_lfp = loader.get_signal(mode="lfp", condition="AXAB", area="V1")
print(f"""[result] Loaded V1 LFP: {v1_lfp.shape}""")
```

## Files
- [data_loader.py](file:///omission/src/core/data_loader.py) — Canonical loader

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
