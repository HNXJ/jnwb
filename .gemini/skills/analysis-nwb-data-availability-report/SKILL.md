---
name: analysis-nwb-data-availability-report
---
# analysis-nwb-data-availability-report

## 1. Problem
This skill encompasses the legacy instructions for analysis-nwb-data-availability-report.
Legacy Purpose/Info:
# analysis-nwb-data-availability-report

## Purpose
Generates a data completeness matrix across all NWB sessions. Tracks presence of spikes, LFP, eye, and reward signals. Outputs the Stable-Plus exclusion list.

## Input
| Name | Type | Description |
|------|------|-------------|
| nwb_dir | str | Path to `.nwb` files |
| modality_tags | list[str] | Sensors to check (e.g. `['LFP', 'Spikes', 'Pupil']`) |

## Output
| Name | Type | Description |
|------|------|-------------|
| report_path | str | Path to `DATA_AVAILABILITY_SUMMARY.md` |
| yield_summary | dict | Total units/trials across valid sessions |

## Example
```python
from src.audit.availability import run_availability_audit
report = run_availability_audit("D:/workspace/omission/data/nwb/")
print(f"""[result] Report saved to {report}""")
```

## Files
- [DATA_AVAILABILITY_SUMMARY.md](file:///omission/data/nwb/DATA_AVAILABILITY_SUMMARY.md) — Living document
- [availability.py](file:///omission/src/audit/availability.py) — Core audit

## 2. Solution Architecture
Executes the analytical pipeline using the standardized Omission hierarchy.
- **Input**: NWB data or Numpy arrays via DataLoader.
- **Output**: Interactive HTML/SVG figures saved to `D:/drive/outputs/oglo-8figs/`.

## Trigger / Scope
- Triggered before multi-session analysis to inventory NWB completeness.
- Scans all `.nwb` files under a configured root for SPK, LFP, MUAe, eye, and reward availability.
- Produces exclusion lists for sessions missing required modalities.

## Required Tools / Commands
- Python 3.14+
- `src/audit/availability.py` or `jnwb.list_nwb_files` + `jnwb.inspect_nwb`
- `python -m pytest -q tests/test_skill_paths.py` after skill doc edits

## Stop Conditions / Blocker Codes
- `BLOCKED_NWB_ROOT_MISSING`: no NWB directory or zero `.nwb` files found.
- `BLOCKED_NO_UNITS`: SPK requested but units table empty.
- `BLOCKED_SIGNAL_UNAVAILABLE`: LFP/MUAe series not discoverable in NWB.
- `BLOCKED_SESSION_BLACKLISTED`: session on exclusion list (e.g. clipping artifact).

## Final Report Requirements
- Write `DATA_AVAILABILITY_SUMMARY.md` or CSV inventory with per-session SPK/LFP/MUAe flags.
- Include session_id, subject, file path, and unit/channel counts where available.
- List excluded sessions with explicit reason codes.

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
