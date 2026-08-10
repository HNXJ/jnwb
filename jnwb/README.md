# jnwb: Object-Oriented Grammar for NWB Analysis

Clean, object-oriented interface for omission experiment analysis. Fast shortcuts for all common analysis types.

## Quick Start

```python
import jnwb as oa

# Load a session
session = oa.read('sub-C31o_ses-230823_rec.nwb')

# Explore
print(session)
units = session.find_single_units(quality='stable_plus', area='V1')

# Analyze
session.trial_averaged_plot(area='V1', condition='AAXB')
session.raster_suite(unit_id=42)
```

## Core Classes

### OmissionSession

Main interface for all analysis. Returned by `oa.read()`.

**Constructor:**
```python
session = oa.read(nwb_path, context='omission_glo_passive')
```

**Data Access Methods:**
- `get_units(quality, area, firing_rate_range)` — Get filtered units
- `get_electrodes(area)` — Get channels
- `get_epochs(phase, condition, correct_only)` — Get behavioral data
- `info()` — Get session summary
- `summary()` — Print formatted summary

**Analysis Methods:**

*Plotting:*
- `trial_averaged_plot(area, phase, condition)` — Trial-averaged spectrogram
- `channel_averaged_plot(area, phase, condition)` — Channel-averaged power
- `plot_tfr(area, condition, phase)` — Time-frequency plot

*Single-Unit Analysis:*
- `find_single_units(quality, area, firing_rate_range)` — Find units by criteria
- `channel_unit_mapping()` — Map channels to units
- `lfp_channel_areas()` — Map LFP channels to areas
- `raster_suite(unit_id, condition, phase)` — Raster + PSTH + autocorrelogram

*Population Analysis:*
- `spectrolaminar_motif(area, condition)` — Layer-wise spectral analysis
- `pie_charts(criteria, by_area, by_layer)` — Population distributions

*Spectral Methods:*
- `tfr_from_preprocessed(area, band, condition)` — Load preprocessed TFR
- `plot_tfr(area, condition, phase)` — Plot TFR

## Functions

### read()
Load NWB file as OmissionSession.
```python
session = oa.read('path/to/file.nwb', context='omission_glo_passive')
```

### batch_read()
Load multiple NWB files from directory.
```python
sessions = oa.batch_read('D:/analysis/nwb', pattern='*.nwb')
for session in sessions:
    units = session.find_single_units(quality='stable_plus')
```

## Usage Examples

### Finding Units
```python
# All stable+ units in V1
v1_stable = session.find_single_units(quality='stable_plus', area='V1')

# High firing rate units (>20 Hz)
high_fr = session.find_single_units(firing_rate_range=(20, 200))

# Low-firing MUA
mua = session.find_single_units(quality='mua', firing_rate_range=(0.1, 5))
```

### Channel Mapping
```python
# Which channels are in which area?
lfp_map = session.lfp_channel_areas()
v1_channels = lfp_map[lfp_map['area'] == 'V1']

# Which unit was recorded on which channel?
unit_map = session.channel_unit_mapping()
unit_map[unit_map['unit_id'] == 42]
```

### Plotting
```python
# Trial-averaged V1 response to AAXB condition (p2 omission)
session.trial_averaged_plot(area='V1', phase=3, condition='AAXB')

# Raster + PSTH for single unit
session.raster_suite(unit_id=42, condition='AAXB', phase=3)

# Layer-specific spectral analysis
session.spectrolaminar_motif(area='MT', condition='omission')
```

### Population Statistics
```python
# Pie charts: how many stable+ units by area?
result = session.pie_charts(criteria={'is_stable_plus': True}, by_area=True)

# How many high-firing units in each layer?
result = session.pie_charts(
    criteria={'firing_rate': (20, 200)},
    by_layer=True
)
```

### Batch Analysis
```python
# Load all 13 sessions
sessions = oa.batch_read('D:/analysis/nwb')

# Across all sessions: find all stable+ units
all_units = []
for sess in sessions:
    units = sess.find_single_units(quality='stable_plus')
    all_units.append(units)

# Analyze by area
for sess in sessions:
    print(f"{sess}: {len(sess.get_units(quality='stable_plus'))} stable+ units")
```

## Design Philosophy

1. **Clean Grammar**: `session.<method>(<args>)` for every analysis type
2. **Fast Shortcuts**: Common analyses in 1-2 lines of code
3. **Sensible Defaults**: Works out-of-box for typical use cases
4. **Chainable**: Methods return objects ready for further analysis
5. **Extensible**: Subclass `OmissionSession` for custom methods

## Behavioral Condition Mapping

| Name  | Condition Numbers | Meaning |
|-------|-------------------|---------|
| AAAB  | 1, 2              | All A's, final B |
| AXAB  | 3                 | A, omit, A, B |
| AAXB  | 4                 | A, A, omit, B (p2 omission) |
| AAAX  | 5                 | A, A, A, omit (p4 omission) |
| BBBA  | 6, 7              | All B's, final A |
| BXBA  | 8                 | B, omit, B, A |
| BBXA  | 9                 | B, B, omit, A (p3 omission) |
| BBBX  | 10                | B, B, B, omit (p4 omission) |
| RRRR  | 11-26             | Random sequence |
| RXRR  | 27-34             | Random with omission |
| RRXR  | 35, 37, 39, 41    | Random with omission |
| RRRX  | 36, 38, 40, 42-50 | Random with omission |

## Phase Identifiers

| Phase | stimulus_number | Meaning |
|-------|-----------------|---------|
| Fixation | 1 | Fixation cue appearance |
| p1 | 2 | First stimulus (global anchor) |
| p2 | 3 | Second stimulus / omission slot |
| p3 | 4 | Third stimulus / omission slot |
| p4 | 5 | Fourth stimulus / omission slot |

## Unit Quality Levels

| Quality | Definition |
|---------|-----------|
| stable_plus | Stable units with firing_rate > 1 Hz, SNR > 0.8, 100% presence |
| stable | Stable units (is_stable=True) but not stable_plus |
| mua | Multi-unit activity (lower SNR/consistency) |
| unstable | Poor quality or unstable recordings |

## File Structure

```
jnwb/
├── __init__.py          # Main API exports (read, batch_read, OmissionSession)
├── session.py           # OmissionSession class with all analysis methods
└── README.md            # This file
```

## Implementation Status

✓ **Core Data Access**
- Unit loading and filtering
- Electrode/channel access
- Behavioral epoch extraction

✓ **Analysis Stubs**
- All analysis methods defined with docstrings
- Proper type hints and documentation
- TODO comments indicate implementation needed

⏳ **Full Implementation**
- TFR loading and plotting
- Raster suite (raster + PSTH + autocorr)
- Pie chart generation
- Spectrolaminar analysis
- Trial/channel averaging

## Extending the Class

To add custom analysis methods:

```python
from jnwb import OmissionSession

class MyAnalysis(OmissionSession):
    def custom_analysis(self, param1, param2):
        """Custom analysis description."""
        units = self.get_units()
        # Your analysis code here
        return results
```

## See Also

- **Spectral Relations Pipeline** (spectral_relations_pipeline.py) — Multi-modal network analysis
- **NWB-IO Skill** (.claude/skills/jnwb-core/SKILL.md) — Lower-level NWB utilities
- **Spiking Skill** (.claude/skills/jnwb-spiking/SKILL.md) — Spike-related methods

---

**Author**: Claude Code  
**Date**: 2025-06-24  
**Version**: 1.0.0  
**Status**: Core API ready, implementation in progress

---

## MCP Server Setup

The `jnwb` package includes a built-in Model Context Protocol (MCP) server for integration with Claude and other MCP-compatible agents/clients.

### Tools Provided
1. `inspect_nwb` — Inspect NWB file structure, metadata, groups, datasets, and neurodata_types.
2. `get_event_codes_and_timings` — Extract all event/trial codes and timestamps with auto-discovery.
3. `prepare_signal_reference` — Prepare a lazy metadata reference for large signal/ephys datasets without loading data arrays into memory.

### Setup and Dependencies

The MCP server depends on:
* `mcp` (Model Context Protocol Python SDK)
* `h5py` (HDF5 file system backend)
* `pynwb` (NWB standard library)
* `pandas` (Data processing)
* `numpy` (Numerical backend)

To install the required dependencies:
```bash
pip install mcp h5py pynwb pandas numpy
```

### Running the Server
The MCP server communicates over standard input/output (stdio). Run it directly using Python:
```bash
python -m jnwb.mcp_server
```

To configure it in Claude Desktop, add the following to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "jnwb-mcp-server": {
      "command": "python",
      "args": ["-m", "jnwb.mcp_server"]
    }
  }
}
```
