# 02. Paths, Addressing, Metadata & Ontology

This document provides a comprehensive guide to data path resolution, anatomical addressing (channel $\to$ area, depth $\to$ layer), unit quality auditing, and query ontology in `jnwb`.

---

## 1. Path Management & Drive Remap Isolation (`jnwb/paths.py`)

Electrophysiology datasets frequently span multiple storage volumes, local SSDs, network mounts, or external RAID arrays. `jnwb.paths` eliminates hardcoded absolute paths by managing dynamic root resolution via environment variables while guaranteeing stable repo-internal paths.

### Key API Functions

```python
import jnwb

# Print the status of all registered data roots and their resolution state
jnwb.paths.describe()

# Access standard repository-internal directories (always guaranteed to resolve)
repo_root = jnwb.paths.REPO_ROOT
outputs = jnwb.paths.outputs_dir()
artifacts = jnwb.paths.artifacts_dir()

# Resolve a registered data root
nwb_dir = jnwb.paths.get_path("nwb_dir")
```

### Environment Variable Mapping
Paths are configured via environment variables rather than source code edits:

| Path Key | Environment Variable | Default Fallback | Purpose |
|----------|----------------------|------------------|---------|
| `nwb_dir` | `JNWB_NWB_DIR` / `OMISSION_NWB_DIR` | `None` (must be set) | Directory containing primary `.nwb` session files |
| `analysis_dir` | `JNWB_ANALYSIS_DIR` / `OMISSION_ANALYSIS_DIR` | `None` (must be set) | Analysis root volume |
| `outputs` | `JNWB_OUTPUTS_DIR` | `<repo_root>/outputs` | Processed tables, analysis summaries |
| `artifacts` | `JNWB_ARTIFACTS_DIR` | `<repo_root>/artifacts`| Evidence logs, metadata sidecars |

---

## 2. Spatial & Laminar Addressing (`jnwb/addressing.py`)

`jnwb.addressing` translates raw hardware channel indices and microelectrode tip coordinates into anatomically meaningful area and laminar (cortical layer) assignments.

### Peak Channel to Area Mapping (`map_peak_channel_to_area`)

```python
import jnwb

# Look up anatomical area for a unit based on its peak channel and electrodes table
area_name = jnwb.map_peak_channel_to_area(peak_channel_id=0, electrodes_df=electrodes_df)
```

### Depth-to-Layer (Laminar) Resolution (`classify_layer_from_depth`)

Translates probe electrode depth ($z$-coordinate in $\mu\text{m}$) into cortical layer classification:

```python
# Classifies layer based on electrode z depth ('Superficial' for <= 1000 um, 'Deep' for > 1000 um)
layer = jnwb.classify_layer_from_depth(peak_channel_id=0, electrodes_df=electrodes_df)
# Returns: 'Superficial', 'Deep', or 'Unknown'
```

### Enriching Units DataFrame (`enrich_units_dataframe`)

Attaches standardized `unit_id`, `area`, and `layer` columns directly to units tables:

```python
enriched_units = jnwb.enrich_units_dataframe(units_df, electrodes_df)
```

---

## 3. Unit Metadata, Quality Classification & Census Audits (`jnwb/metadata.py`)

`jnwb.metadata` provides tools for extracting spike-sorting metadata across cohorts of NWB files, categorizing unit isolation quality, computing Signal-to-Noise Ratios (SNR), and producing census reports.

### Multi-Session Metadata Extraction & Classification

```python
import jnwb

nwb_files = ["sub-01_ses-01.nwb", "sub-01_ses-02.nwb"]

# Extract all units across multiple sessions into a unified pandas DataFrame
units_df = jnwb.get_all_units_metadata(nwb_files, filter_quality=False)

# Classify unit quality tiers (attaches quality_class: 'Good'|'MUA'|'Noise', is_valid, issue_flags)
classified_units = jnwb.classify_unit_quality(units_df)

# Generate a census summary grouped by brain area
census = jnwb.unit_census_report(classified_units, group_by=["area"])
print(census)
```

### SNR Analysis, Quality Tiers & Inventory

```python
# Compute SNR statistics across units
snr_stats = jnwb.get_snr_analysis(classified_units, snr_threshold=1.0)
# -> {'pass_rate': 0.84, 'snr_mean': 4.25, 'snr_median': 3.90}

# Perform comprehensive unit audit
unit_audit = jnwb.audit_units(classified_units)

# Audit electrode tables and area coverage
elec_audit = jnwb.audit_electrodes(electrodes_df, units_df)

# Generate multi-session electrode inventory
inventory = jnwb.electrode_inventory(nwb_files)

# Assign explicit quality tier based on presence fraction and SNR
tier = jnwb.assign_quality_tier(
    quality="good",
    trial_presence_fraction=0.95,
    snr=4.5
)
```

### Filtering Units by Criteria

```python
# Filter units by dictionary criteria (equality, range tuple, or set membership)
good_v1_units = jnwb.filter_by_criteria(
    classified_units,
    criteria={
        "area": "V1",
        "firing_rate": (0.5, 60.0),
        "snr": (2.5, 100.0),
        "trial_presence_fraction": (0.8, 1.0),
    }
)
```

---

## 4. Query & Event Ontology (`jnwb/ontology.py`)

`jnwb.ontology` defines object-oriented queries, datasets, and provenance descriptors:

- `Query`: Declarative query on units, sessions, and areas.
- `Dataset` & `AlignedDataset`: Encapsulation of electrophysiological data tensors with explicit alignments (`Alignment`).
- `EpochCollection`: Structured trial epoch definitions.
- `Question`, `Result`, `Interpretation`, `Figure`, `Provenance`, `Lineage`: Epistemic metadata classes for tracking analytical provenance.

```python
from jnwb import Query, Dataset, EpochCollection

# Construct declarative dataset query
q = Query(sessions=["ses-01", "ses-02"], areas=["V1", "PFC"])
```
