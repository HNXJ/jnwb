---
name: coding-neuro-omission-bhv-parser
---
# coding-neuro-omission-bhv-parser

## 1. Problem
This skill encompasses the legacy instructions for coding-neuro-omission-bhv-parser.
Legacy Purpose/Info:
# coding-neuro-omission-bhv-parser

## Purpose
Parses MonkeyLogic 2.2 `.bhv2.mat` files to extract event timing, stimulus identity (A/B/R), omission flags, and trial-error filtering.

## Input
| Name | Type | Description |
|------|------|-------------|
| bhv_path | str | Path to `.bhv2.mat` file |
| event_schema | dict | Code→state mapping (e.g. `{100: 'TrialStart', 101: 'P1Onset'}`) |

## Output
| Name | Type | Description |
|------|------|-------------|
| trial_dicts | list[dict] | `{trial_id, start_time, end_time, stimulus_id, is_omission}` |
| event_timecourse | list[tuple] | `(event_code, absolute_time)` per trial |

## Example
```python
import scipy.io as sio
mat = sio.loadmat('session.bhv2.mat', squeeze_me=True)
trials = mat['ML2']['TrialData']
for t in trials:
    if t['TrialError'] == 0:
        print(f"""[result] Trial {t['Trial']}: Stim={t['TaskObject']['Attribute'][0]}""")
```

## Files
- [bhv_parser.py](file:///omission/src/extract/bhv_parser.py) — Core logic

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
