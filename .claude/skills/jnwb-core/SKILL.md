---
name: jnwb-core
description: |
  Load, explore, and manage Omission NWB sessions using the jnwb API.
  Covers oa.read(), oa.batch_read(), OmissionSession data access methods,
  behavioral condition/phase mappings, and the unit quality tier system.
  Also covers jnwb.paths (repo and data root resolution, OMISSION_NWB_DIR /
  OMISSION_TFR_DIR), the ontology/factories objects, and the MCP server.
  Use this skill for any task that starts with opening an NWB file,
  querying basic session metadata, or resolving where data lives on disk.
---

# jnwb-core: Session I/O and Data Access

Module root: `jnwb/` (repo root: `oa.paths.REPO_ROOT`)  
Primary files: `session.py`, `__init__.py`

## Import

```python
import jnwb as oa
```

## Paths — resolve, never hardcode (`jnwb.paths`)

Absolute `D:/...` literals used to be scattered through `session.py`, `viz.py`, `report.py` and
the scripts. A drive remap broke all of them at once, silently, because they were default
arguments that resolve to a nonexistent path rather than raise. Everything now goes through
`jnwb.paths`.

```python
oa.paths.describe()        # every root + whether it currently resolves -- run this first
oa.paths.REPO_ROOT         # from the package's own location; always correct
oa.paths.nwb_dir()         # $OMISSION_NWB_DIR,      fallback D:/nwb/omission  (read-only input)
oa.paths.analysis_dir()    # $OMISSION_ANALYSIS_DIR, fallback D:/analysis      (all derived data)
oa.paths.tfr_dir()         # $OMISSION_TFR_DIR,      fallback <analysis>/tfr_arrays
oa.paths.meta_dir()        # $OMISSION_META_DIR,     fallback <analysis>/metadata
oa.paths.conndb_dir()      # $OMISSION_CONNDB_DIR,   fallback <analysis>/connectivity_databases
oa.paths.outputs_dir("classification")     # repo-relative
oa.paths.artifacts_dir("data")             # repo-relative
oa.paths.layer_masks_path()                # canonical vFLIP layer masks
oa.paths.require(p, "NWB directory", "OMISSION_NWB_DIR")   # exists-or-raise, with the fix
```

Two classes of root, and they fail differently:

- **Repo-internal** (`REPO_ROOT`, `outputs_dir`, `artifacts_dir`, `layer_masks_path`) — derived
  from `__file__`. Not configurable, cannot drift.
- **External data** (`nwb_dir`, `analysis_dir`, and the `tfr_dir` / `meta_dir` / `conndb_dir`
  subtrees under it) — on a separate volume that moves. If `describe()` reports
  `exists: false`, set the env var. Do not edit source, and do not write a new absolute
  literal into a script.

**Two volumes, one rule:** NWBs are read-only inputs under `D:/nwb/omission`; every derived
artifact — arrays, matrices, supplements, post-process output — goes under `D:/analysis`,
never into the repo. `D:/nwb/mglo/` is a **different experiment** (subject `V182m`, `_ks2`
suffix); never glob across `D:/nwb` or you will pull mglo sessions into an omission analysis.

## Load a Session

```python
session = oa.read(oa.paths.nwb_dir() / 'sub-C31o_ses-230823_rec.nwb')
# Optional context (default already set to omission_glo_passive):
session = oa.read(path, context='omission_glo_passive')
```

## Batch Load (all sessions)

```python
sessions = oa.batch_read(oa.paths.nwb_dir(), pattern='*.nwb')
```

Session count drifts as data lands — verify the current count via
`artifacts/data/session_readiness.csv` or `nwb_catalog.json` rather than
hardcoding a number; "13 sessions" is a known-stale legacy figure (see
`.agents/AGENTS.md`; 21 NWB files as of the 2026-07-26 receipt).

## Data Access Methods (OmissionSession)

```python
session.info()           # Summary dict: n_units, areas, etc.
session.summary()        # Print formatted summary

# Units
units_df = session.get_units(quality='stable_plus', area='V1')
units_df = session.get_units(quality='stable', firing_rate_range=(1, 200))

# Channels / electrodes
elec_df  = session.get_electrodes(area='V4')

# Epochs / trials
epochs   = session.get_epochs(phase=3, condition='AAXB', correct_only=True)

# Channel maps
lfp_map  = session.lfp_channel_areas()          # channel → area/layer
unit_map = session.channel_unit_mapping()        # unit_id → channel_id, area, layer
```

## Behavioral Condition Codes

| Name  | Condition Numbers | Meaning                           |
|-------|-------------------|-----------------------------------|
| AAAB  | 1, 2              | All A's, B deviant at p4          |
| AXAB  | 3                 | Omission at p2                    |
| AAXB  | 4                 | Omission at p3 (canonical omit)   |
| AAAX  | 5                 | Omission at p4                    |
| BBBA  | 6, 7              | All B's, A deviant at p4          |
| BXBA  | 8                 | B omission at p2                  |
| BBXA  | 9                 | B omission at p3                  |
| BBBX  | 10                | B omission at p4                  |
| RRRR  | 11–26             | Random sequences                  |
| RXRR  | 27–34             | Omission at p2                    |
| RRXR  | 35, 37, 39, 41    | Omission at p3 (odd slots only)   |
| RRRX  | 36, 38, 40, 42–50 | Omission at p4                    |

**V182o exception** (`CONDITION_MAP_V182O` in `jnwb/session.py`): RRXR = 35–42, RRRX = 43–50
(contiguous ranges, no odd/even split). Always resolve from the map dict, not from memory —
the default map's odd-slot RRXR split is a real quirk that has silently mislabeled sessions.

## Phase Numbers

| phase argument | stimulus_number | Slot     |
|----------------|-----------------|----------|
| `1`            | 1               | Fixation |
| `2`            | 2               | p1       |
| `3`            | 3               | p2       |
| `4`            | 4               | p3       |
| `5`            | 5               | p4       |

## Unit Quality Tiers

| Quality       | Definition                                                    |
|---------------|---------------------------------------------------------------|
| `stable_plus` | is_stable=True, FR > 1 Hz, SNR > 0.8, 100 % trial presence   |
| `stable`      | is_stable=True but not stable_plus                            |
| `mua`         | Multi-unit activity                                           |
| `unstable`    | Poor quality / unstable recordings                            |

Grand database: 6,040 units total.  
Stable-plus gate: 661 units.  
Stable-only metrics table: 3,071 units (`stable_units_calculated_metrics.csv`).

## Key Source CSV Paths

```
outputs/publication_figures/data_tables/grand_database_6040_units.csv
outputs/publication_figures/data_tables/stable_units_calculated_metrics.csv
```

## NWB File Locations

```
<nwb_dir>/sub-C31o_ses-*.nwb   (subject C31o, multiple dates)
<nwb_dir>/sub-V198o_ses-*.nwb  (subject V198o, multiple dates)
```

## Critical footgun: unit identity is a DataFrame row position, not `unit_id`

`session.get_spike_times(unit_id)` (and equivalent internal lookups) index by **raw DataFrame
row position** (`units_df.index`), **not** the `unit_id` column. `unit_id` is a per-probe-local
kilosort id — it can have gaps and is not globally unique across probes/sessions. Passing a
`unit_id` column value where a row-position index is expected silently fetches the wrong unit's
spikes (confirmed real bug, found in `jnwb/trajectory.py::build_time_resolved_matrix` and in a
`grand_unit_table_shuffle_sso.csv` consumer script — both were using the `unit_id` column).
Before writing any new code that fetches spikes for a given unit, confirm which identifier you
are actually holding.

## Footgun: bytes-encoded h5py numeric columns

On some sessions (confirmed: `sub-C31o_ses-230816`, `sub-C31o_ses-230901`), raw intervals-table
columns read directly via h5py come back as **byte strings** (`b'2.0'`, `b'nan'`), not floats.
`float(b'2.0')` works but naive numeric comparisons on the raw bytes silently produce wrong trial
counts (370 vs the real 246 for one condition, until fixed). This only bites code that reads
`stimulus_number`/`correct`/`task_condition_number`/`start_time` etc. directly via h5py instead
of through `session.get_epochs(...)` — prefer the session API; if you must read raw, coerce with
an explicit bytes-aware numeric parser and sanity-check trial counts against a known session.

## Standard NWB Content Atlas

Omission NWB session files contain the following physiological signals:

1. **Local Field Potentials (LFP)**:
   * *Location*: `nwb.acquisition['probe_X_lfp']` (where `X` is `0` or `1` representing probe indices).
   * *Usage*: Low-frequency local neural populations (delta, theta, alpha, beta, gamma).
2. **Multi-Unit Activity envelope (MUAe)**:
   * *Location*: `nwb.acquisition['probe_X_muae']` (precalculated multi-unit envelopes).
   * *Usage*: Population-level high-frequency envelope signals.
3. **Single Units (Spikes)**:
   * *Location*: `nwb.units` (unit spike times, sorting waveforms, metrics).
   * *Usage*: Firing rates, autocorrelograms, single-unit tuning.
4. **Spiking Signal Types**:
   * *Unconvolved Spikes*: Raw discrete event spike times retrieved via `session.get_units()` or `nwb.units['spike_times']`.
   * *Convolved Spikes / PSTH*: Continuous rate representations computed by smoothing discrete spikes with a temporal kernel (e.g. Gaussian window or binning via `UnitAnalyzer.psth`).

## direct h5py fallback access (head-free & speedups)
On older sessions (such as `V182o` and visual sessions containing PyNWB Device schema anomalies), attempting a standard PyNWB object build can cause build blockages. Use direct `h5py` reads to load LFP matrices and behavioral arrays without using full PyNWB schemas. **LFP group layout differs by subject** — verify per file, do not assume:

- C31o: `acquisition/probe_0_lfp/` contains `data`, `electrodes`, `timestamps` directly (so the path is `.../probe_0_lfp/data`).
- V182o: `acquisition/probe_0_lfp/` contains a nested `probe_0_lfp_data/` group holding `data`/`timestamps` (path `.../probe_0_lfp/probe_0_lfp_data/data`).
- Pupil is `acquisition/pupil_1_tracking/` (data at `.../pupil_1_tracking/data` or `.../pupil_1_tracking/pupil_1_diameter_data`) — there is **no** `pupil_diameter` group in either subject.
- Probe indices are 0–2 (some sessions 0–3); the `electrical_series` intermediate group does not exist in these files.

```python
import h5py
import numpy as np

# direct read template (V182o layout shown; adjust per the rules above)
with h5py.File(oa.paths.nwb_dir() / "sub-V182o_ses-260706.nwb", "r") as f:
    # 1. Direct LFP extraction (avoiding device metadata build blocks)
    # V182o: nested group; C31o would be f["acquisition/probe_0_lfp/data"]
    lfp_data = f["acquisition/probe_0_lfp/probe_0_lfp_data/data"][:] # channels x samples
    lfp_timestamps = f["acquisition/probe_0_lfp/probe_0_lfp_data/timestamps"][:]

    # 2. Pupil diameter behavioral tracking
    pupil_data = f["acquisition/pupil_1_tracking/data"][:]
    pupil_timestamps = f["acquisition/pupil_1_tracking/timestamps"][:]
```

## Footgun: dual-area probes must be resolved by channel position

A probe labeled `"Y, Z"` or `"Y/Z"` means channels **1–64 = Y, 65–128 = Z**; bare `"V3"` alone
expands to `(V3d, V3a)`; dual `"V3, V1"` keeps V3 as the first half (no V3d/V3a expansion).
Never resolve area by taking `location.split(',')[0]` — that bug shipped once and silently
mislabeled 1,965 of 6,655 rows in the grand unit table. Canonical helper:
`jnwb.addressing.map_peak_channel_to_area` (via `jnwb.sequence_layout.parse_probe_areas` /
`channel_slice_for_area`). See `.agents/AGENTS.md` footgun #3.


## Structured objects: `jnwb.ontology` and `jnwb.factories`

When an analysis needs to carry its own provenance rather than return a bare dict, build it out
of the ontology objects instead of tuples. `factories` wires them to a live `OmissionSession`.

```python
from jnwb.factories import (
    dataset_from_session, aligned_dataset_from_dataset, epochs_from_aligned_dataset,
    result_from_psth_analysis, result_from_tfr_analysis, result_from_decoding_analysis,
    figure_from_result,
)
ds      = dataset_from_session(session, query)
aligned = aligned_dataset_from_dataset(ds, alignment)
epochs  = epochs_from_aligned_dataset(aligned, session, condition="AAXB", phase=2)
result  = result_from_psth_analysis(question, epochs, session, unit_ids)
fig     = figure_from_result(result, interpretation, title="...")
```

Object types (`jnwb.ontology`, all exported at `oa.` top level): `Query`, `Dataset`,
`AlignedDataset`, `Alignment`, `EpochCollection`, `Question`, `Result`, `Interpretation`,
`Figure`, `Provenance`, `Lineage`. `Provenance`/`Lineage` are what make a `Result` traceable to
its data source, parameters, and code — use them rather than reconstructing provenance later.

## MCP server (`jnwb.mcp_server`)

stdio MCP server exposing four tools to an LLM client:

```python
from jnwb.mcp_server import (
    inspect_nwb,                    # session metadata, areas, channels
    get_event_codes_and_timings,    # event model for a session
    prepare_signal_reference,       # trial-aligned LFP / MUAe
    add_tool,                       # append a new tool; needs ALLOW_DYNAMIC_TOOLS=1
)
```

The function is `inspect_nwb`, not `inspect_nwb_file` — older docs had the wrong name.
`add_tool` is gated behind the `ALLOW_DYNAMIC_TOOLS` environment variable and is off by default.
Pinned to `mcp<2.0`: MCP 2.0 removed `mcp.server.fastmcp`, which `mcp_server/server.py` imports.
