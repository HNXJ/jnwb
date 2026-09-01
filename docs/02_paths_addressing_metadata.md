# 02. Paths, Addressing, Metadata & Ontology

This document provides a comprehensive guide to data path resolution, anatomical addressing (channel $\to$ area, depth $\to$ layer), unit quality auditing, and query ontology in `jnwb`.

---

## 1. Path Management & Drive Remap Isolation (`jnwb/paths.py`)

Electrophysiology datasets frequently span multiple storage volumes, local SSDs, network mounts, or external RAID arrays. `jnwb.paths` eliminates hardcoded absolute paths by managing dynamic root resolution via environment variables while guaranteeing stable repo-internal paths.

### Key API Functions

```python
import jnwb.paths

# Print the status of all registered data roots and their resolution state
jnwb.paths.describe()

# Access standard repository-internal directories (always guaranteed to resolve)
repo_root = jnwb.paths.REPO_ROOT
outputs = jnwb.paths.outputs_dir()
artifacts = jnwb.paths.artifacts_dir()

# Resolve a project-level data root
nwb_dir = jnwb.paths.get_path("nwb_dir")
```

### Environment Variable Mapping
Paths are configured via environment variables rather than source code edits:

| Path Key | Environment Variable | Default Fallback | Purpose |
|----------|----------------------|------------------|---------|
| `nwb_dir` | `JNWB_NWB_DIR` | `D:/Analysis/data/nwb` | Directory containing primary `.nwb` session files |
| `raw_dir` | `JNWB_RAW_DIR` | `D:/Analysis/data/raw` | Raw acquisition streams (OpenEphys / SpikeGLX) |
| `outputs` | `JNWB_OUTPUTS_DIR` | `<repo_root>/outputs` | Processed tables, analysis summaries |
| `artifacts` | `JNWB_ARTIFACTS_DIR` | `<repo_root>/artifacts`| Evidence logs, metadata sidecars |

---

## 2. Spatial & Laminar Addressing (`jnwb/addressing.py`)

`jnwb.addressing` translates raw hardware channel indices and microelectrode tip coordinates into anatomically meaningful area and laminar (cortical layer) assignments.

### Channel-to-Area Mapping
Resolves probe channels to brain structures based on electrode group metadata stored in NWB files or external channel map tables.

```python
import jnwb.addressing as addr

# Look up anatomical area for a specific electrode channel
area_name = addr.channel_to_area(electrode_table, channel_id=32)
```

### Depth-to-Layer (Laminar) Resolution
Translates cortical probe depth ($\mu\text{m}$) into laminar boundaries:
- **Supragranular (L2/3)**: Superficial cortical layers.
- **Granular (L4)**: Main thalamocortical input layer.
- **Infragranular (L5/6)**: Deep output layers.

```python
# Resolve laminar classification from probe tip depth and area boundaries
layer = addr.depth_to_layer(depth_um=450.0, area="V1", boundary_table=area_boundaries)
```

---

## 3. Unit Metadata, Quality Classification & Census Audits (`jnwb/metadata.py`)

`jnwb.metadata` provides tools for extracting spike-sorting metadata across large cohorts of NWB files, categorizing unit isolation quality, computing Signal-to-Noise Ratios (SNR), and producing census reports.

### Multi-Session Metadata Extraction & Classification

```python
import jnwb

nwb_files = ["sub-01_ses-01.nwb", "sub-01_ses-02.nwb"]

# Extract all units across multiple sessions into a unified pandas DataFrame
units_df = jnwb.get_all_units_metadata(nwb_files)

# Classify unit quality tiers (e.g. stable_plus, single_unit, multi_unit, noise)
classified_units = jnwb.classify_unit_quality(units_df)

# Generate a census summary grouped by brain area
census = jnwb.unit_census_report(classified_units, group_by=["area"])
print(census)
```

### SNR and Unit Auditing

```python
# Compute SNR statistics across units
snr_stats = jnwb.get_snr_analysis(classified_units)
# -> {'pass_rate': 0.84, 'snr_mean': 4.25, 'snr_median': 3.90}

# Perform comprehensive unit audit
audit = jnwb.audit_units(classified_units)
# Analyzes firing rate distributions, presence fraction, ISI violations, and waveform SNR
```

### Filtering Units by Criteria

```python
# Filter units by joint quality and physiological thresholds
good_v1_units = jnwb.filter_by_criteria(
    classified_units,
    criteria={
        "area": "V1",
        "firing_rate": (0.5, 60.0),
        "snr": (2.5, None),
        "trial_presence_fraction": (0.8, 1.0),
    }
)
```

---

## 4. Query & Event Ontology (`jnwb/ontology.py`)

`jnwb.ontology` defines object-oriented queries and event descriptors to standardize session filtering, stimulus referencing, and trial segmentation across datasets.

### Defining Queries & Session Descriptors

```python
from jnwb.ontology import SessionFilter, EventReference

# Define an event reference anchor (e.g. stimulus presentation or omission slot)
stim_anchor = EventReference(name="stimulus_onset", reference_event="p1_onset", phase_number=1)

# Structured session filter
session_query = SessionFilter(
    query="area == 'V1' and quality == 'stable_plus'",
    sessions=["ses-01", "ses-02"]
)
```

---

## 5. Summary of Key Data Structures

| Class / Function | Input | Output | Primary Use Case |
|------------------|-------|--------|------------------|
| `paths.describe()` | None | Dict / stdout | Diagnostic overview of data root resolution |
| `paths.get_path()` | `key: str` | `Path` | Dynamic retrieval of external storage paths |
| `get_all_units_metadata()` | `List[Path]` | `pd.DataFrame` | Multi-session metadata compilation |
| `classify_unit_quality()` | `pd.DataFrame` | `pd.DataFrame` | Attaches quality tiers and issue flags |
| `unit_census_report()` | `pd.DataFrame` | `pd.DataFrame` | Unit breakdown by area and quality |
| `audit_units()` | `pd.DataFrame` | `Dict[str, Any]` | Detailed spike sorting quality verification |
