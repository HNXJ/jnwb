# 02. Paths, Addressing, Metadata & Ontology

Data roots, streaming reads, anatomical addressing (channel $\to$ area, depth $\to$ depth class), unit quality audits and the query ontology.

---

## 1. Path Management & Drive Remap Isolation (`jnwb/paths.py`)

`jnwb.paths` resolves data roots for batch jobs from environment variables, so no absolute path
is written into code. It does not look inside a `.nwb` file: per-file discovery (acquisitions,
interval tables, event codes) is `jnwb.inspect` and the
[addressing tutorial](tutorials/02_addressing_and_metadata.md).

### Key API Functions

```python
import jnwb

# Print the status of all registered data roots and their resolution state
jnwb.paths.describe()

# Where the INSTALLED jnwb package lives. This is jnwb's own root, never yours --
# anchor to your own file (Path(__file__).resolve().parent.parent) for your project.
jnwb_package_root = jnwb.paths.PACKAGE_ROOT

# Outputs and artifacts resolve against the process working directory, so they
# follow the consuming project rather than the install location.
outputs = jnwb.paths.outputs_dir()
artifacts = jnwb.paths.artifacts_dir()

# Resolve an external data root (raises FileNotFoundError naming the env var to set)
nwb_dir = jnwb.paths.nwb_dir()
```

### Environment Variable Mapping

| Path Key | Environment Variable | Default Fallback | Purpose |
|----------|----------------------|------------------|---------|
| `nwb_dir` | `JNWB_NWB_DIR` | `None` (must be set) | Directory containing primary `.nwb` session files |
| `analysis_dir` | `JNWB_ANALYSIS_DIR` | `None` (must be set) | Analysis root volume |
| `outputs` | `JNWB_OUTPUTS_DIR` | `<cwd>/outputs` | Processed tables, analysis summaries |
| `artifacts` | `JNWB_ARTIFACTS_DIR` | `<cwd>/artifacts` | Evidence logs, metadata sidecars |

Each variable still reads a legacy `OMISSION_*` alias of the same suffix, with a
`DeprecationWarning`.

---

## 2. Memory-Bounded Array Streaming (`jnwb.io`, `stream_npz_array`)

`np.load` decompresses a whole `.npz` array into RAM. `jnwb.stream_npz_array` reads a slice of it, from `ZIP_DEFLATED` and `ZIP_STORED` archives alike. Peak memory is strictly proportional to the requested output slice plus bounded streaming/selection overhead. A stored entry is seeked past what the slice skips; a compressed one is read forward up to the slice's last element, so its time grows with the slice's position:

```python
import jnwb
from pathlib import Path

npz_path = Path("session_data.npz")

# Stream only the desired channels and time slice without allocating the full array
# e.g., channels 10:20 across time steps 1000:5000:
sliced_data = jnwb.stream_npz_array(
    npz_path,
    key="lfp_matrix",
    slice_tuple=(slice(10, 20), slice(1000, 5000)),
)

# Preserves exact dtype, shape, and C / Fortran memory order
print(sliced_data.shape, sliced_data.dtype)
```

Also accessible as `jnwb.io.stream_npz_array`.


## 3. Spatial & Laminar Addressing (`jnwb/addressing.py`)

`jnwb.addressing` translates raw hardware channel indices and microelectrode tip coordinates into anatomical area assignments and a geometric depth class.

### Peak Channel to Area Mapping (`map_peak_channel_to_area`)

```python
import jnwb

# Look up anatomical area for a unit based on its peak channel and electrodes table
area_name = jnwb.map_peak_channel_to_area(peak_channel_id=0, electrodes_df=electrodes_df)
```

### Geometric Depth Class (`classify_layer_from_depth`)

Thresholds probe electrode depth ($z$-coordinate) into a geometric depth class, with explicit unit safety. The class is a cut on depth, not a cortical layer; the electrophysiological laminar identity is `jnwb.label_layers`.

```python
# 'Superficial' for <= 1000 um, 'Deep' for > 1000 um, with explicit depth units
depth_class = jnwb.classify_layer_from_depth(peak_channel_id=0, electrodes_df=electrodes_df, depth_unit="um")
# Returns: 'Superficial', 'Deep', or 'Unknown' (unknown/incompatible units return 'Unknown')
```

### Enriching Units DataFrame (`enrich_units_dataframe`)

Attaches standardized `unit_id`, `area`, and `depth_class` columns directly to units tables:

```python
enriched_units = jnwb.enrich_units_dataframe(units_df, electrodes_df)
```

`layer` is a deprecated copy of `depth_class`, removed in the next release. The call emits `FutureWarning` whenever it writes `layer`; pandas cannot warn when a column is read, so the warning fires even if `layer` is never used. `jnwb.get_all_units_metadata` emits both columns the same way, with one warning per call, and `jnwb.unit_census_report` with `group_by=None` groups by `depth_class`.

### Probe Geometry Extraction (`probe_geometry`, `ProbeGeometry`)

Extracts contact spacing, linear ordering, orientation, and layout properties from NWB electrode tables or 3D coordinate arrays with explicit units:

```python
# Extract contact geometry with explicit units (default: 'um')
geom = jnwb.probe_geometry(electrodes_df, units="um", pitch_tolerance=0.1)

# Inspect geometry properties
print(f"Contacts: {geom.contact_positions.shape}")  # (n_channels, 3) in um
print(f"Nominal pitch: {geom.nominal_pitch:.1f} um")
print(f"Is linear: {geom.is_linear}, Is uniform: {geom.is_uniform}")
print(f"Linear ordering: {geom.linear_order}")
print(f"Shaft orientation unit vector: {geom.orientation}")
```

For multi-probe files, pass `probe_name=<name>` explicitly. Fails loudly on duplicate coordinates, NaNs, ambiguous multiple probes, or unsupported length units.

### Laminar Phase Profiling & Delay Estimation (`jnwb.zflip`, `ZFlipResult`)

Estimates cortical depth phase gradients, the per-contact delay, and an apparent velocity across ordered laminar contacts:

```python
# lfp_matrix: (n_channels, n_samples) ordered along probe shaft
z_res = jnwb.zflip(
    lfp_matrix,
    fs=1000.0,
    orientation="superficial_to_deep",   # row 0 is the most superficial contact
    freq_range=(15.0, 35.0),
    pitch_um=geom.nominal_pitch,
    n_surrogates=50,
)
print("Direction:", z_res.directionality)
print("Delay gradient (s/contact):", z_res.tau_per_channel_s)
print("Apparent velocity (m/s):", z_res.apparent_velocity_m_s)
```

**What these three numbers license.** `tau_per_channel_s` is a delay per contact in
seconds, fitted to the phase gradient across depth; `apparent_velocity_m_s` is that
gradient expressed as a speed in meters per second, using `pitch_um` for the spacing.
It is an *apparent* phase velocity, not a conduction velocity: a phase gradient of this
shape is produced by axonal conduction, but also by two sources with a fixed phase offset,
by a traveling wave in the local field, and by volume conduction from a single distant
generator. `directionality` is a direction in *depth*, not a direction of causal influence.
It comes from the sign of the gradient along the rows and the `orientation` you state, which has
no default: an electrode table can list contacts from either end, and the LFP cannot say which.
Pass `"deep_to_superficial"` when row 0 is the deepest contact. Reporting any of the
three as a conduction speed or as evidence that one layer drives another is the
association-to-causality step that [Architecture &
Philosophy](01_architecture_and_philosophy.md#c-causal-directional-verbs) rules out.

![Spatial and Laminar Addressing](assets/figures/fig01_addressing_laminar.png#only-light)
![Spatial and Laminar Addressing](assets/figures/fig01_addressing_laminar.dark.png#only-dark)

On a synthetic electrodes table, panel A of that figure is `jnwb.map_peak_channel_to_area`
partitioning 24 contacts of one probe
across V1, V2 and V3; panel B is `jnwb.classify_layer_from_depth` on the same contacts, with the
boundary it cuts at drawn. Both are spatial assignments and neither carries a causal direction.

---

## 4. Unit Metadata, Quality Classification & Census Audits (`jnwb/metadata.py`)

### Multi-Session Metadata Extraction & Classification

```python
import jnwb

nwb_files = ["sub-01_ses-01.nwb", "sub-01_ses-02.nwb"]

# Extract all units across multiple sessions into a unified pandas DataFrame
units_df = jnwb.get_all_units_metadata(nwb_files, filter_quality=False)

# Classify unit quality tiers (attaches quality_class: 'Good'|'Fair'|'Poor', is_valid, issue_flags)
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

# Assign explicit quality tier ('mua' | 'stable' | 'unstable') from presence and SNR.
# All three arguments are per-unit Series, not scalars, and `quality` is the integer
# sorter code (0 = MUA, 1 = single-unit candidate), not a word.
tier = jnwb.assign_quality_tier(
    quality=classified_units["quality"],
    trial_presence_fraction=classified_units["trial_presence_fraction"],
    snr=classified_units["snr"],
)
```

### Filtering Units by Criteria

```python
# Filter units by dictionary criteria (equality, range tuple, or set membership).
# Unknown keys are ignored by default; pass unknown="raise" to catch typos.
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

## 5. Query & Event Ontology (`jnwb/ontology.py`)

These objects record *what was asked, of which data, under which alignment, and what was
concluded*. They hold no data-access code: nothing here opens an NWB file. They are the
labels you attach to an analysis so that a result carries its own question, provenance and
lineage rather than living in a filename.

- `Query`: Declarative query on units, sessions, and areas. Hashable, so it works as a cache key.
- `Dataset` & `AlignedDataset`: Encapsulation of electrophysiological data tensors with explicit alignments (`Alignment`).
- `EpochCollection`: Structured trial epoch definitions.
- `Question`, `Result`, `Interpretation`, `Figure`, `Provenance`, `Lineage`: Epistemic metadata classes for tracking analytical provenance.

```python
import pandas as pd
from jnwb import (Query, Dataset, Alignment, EpochCollection, Question, Result,
                  Interpretation, Figure, Provenance, Lineage)

# 1. What subset of data? (declarative; executes nothing)
q = Query(sessions=["ses-01", "ses-02"], areas=["V1", "PFC"])

# 2. The data that query selected, and where time zero is.
ds = Dataset(query=q, sessions=["ses-01"], units=units_df)
aligned = ds.with_alignment(Alignment(name="stimulus_onset",
                                      reference_event="stimulus_onset"))

# 3. The trials that survived filtering, still traceable to their source.
epochs = EpochCollection(aligned_dataset=aligned, condition="AAAB", phase=2,
                         correct_only=True, epochs_df=trials_df)
print(len(epochs), "epochs")

# 4. The question, the measured answer, and how it was produced.
question = Question(hypothesis="V1 responds to the deviant", signals=["spike_times"],
                    contrast="AAAB vs AAXB", inference_unit="unit")
result = Result(question=question,
                statistics={"p": 0.004, "n_units": 37},
                provenance=Provenance(software_version=jnwb.__version__,
                                      backend="numpy", random_seed=7),
                lineage=Lineage(source_type="EpochCollection", source_id="ses-01",
                                operation="compute_psth"))

# 5. The argument built on that evidence, and the figure that shows it.
interp = Interpretation(claim="deviant response present", confidence="moderate",
                        limitations=["single subject"])
fig = Figure(result=result, interpretation=interp, title="Fig 1")
```

**`Dataset` as a dict key.** `Dataset.__hash__` uses `query` and `sessions`, so datasets
over the same sessions collide; `==` compares every field, using `DataFrame.equals` for
`units`. Equality is therefore finer than the hash, which is what a dict requires.

**`to_dict()` and JSON.** Every object above except `Dataset` and `AlignedDataset` has
`to_dict()`, returning a plain nested `dict`. It converts nothing, so
`json.dumps(result.to_dict())` raises `TypeError` when `statistics` holds NumPy values,
which is the normal case in this package. Pass a hook:

```python
json.dumps(result.to_dict(), default=lambda o: o.tolist())
```

**Immutability.** All of these except `Figure` are `frozen` dataclasses. `frozen` prevents
rebinding an attribute, not mutation of the object it points at -- `ds.sessions.append(...)`
succeeds. Treat the contained lists, dicts and frames as read-only.

**Deprecated.** `create_aligned_dataset`, `create_result` and `create_figure` forward to the
constructor of the same name and add nothing. They were never exported in `__all__`; they
now warn, and will be removed. Call the dataclass, or `Dataset.with_alignment`, directly.
