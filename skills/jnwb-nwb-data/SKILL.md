---
name: jnwb-nwb-data
description: NWB inspection, event/onset extraction, path addressing, anatomical mapping,
  electrode/unit QC, metadata census, and compression.
---

# `jnwb-nwb-data` — NWB Data, Addressing & Metadata

## 1. Trigger
Activate when inspecting NWB files, extracting event onsets, resolving paths, mapping
electrode channels to areas/layers, auditing unit quality, or compressing arrays.

## 2. Task-to-Operation Routing Matrix

### Per-file discovery and events (canonical Python route)

- `jnwb.inspect(path_or_nwb)` → structured `dict` listing acquisitions, electrodes, units,
  and **all** interval tables with column samples. Selects no event table on the caller's behalf.
- `jnwb.events(path_or_nwb, table=None, code_column="codes", onset_column="start_time")` →
  `EventTable` with all rows from one interval table. Onsets in **seconds**.
- `jnwb.event_onsets(path_or_nwb, table=None, codes=None, code_column="codes",
  onset_column="start_time")` → `numpy.ndarray` of onset times (seconds), table row order.
- `jnwb.resolve_interval_table(path_or_nwb, table=None)` → table name using `trials` → sole table →
  `AmbiguousIntervalTableError` when several tables and `table` omitted.
- `jnwb.unit_spike_times(path_or_nwb, unit_index=0)` → spike times in seconds for one units row.
- `jnwb.acquisition_channel(path_or_nwb, name=None, channel=0)` → `(data, rate_hz)` for one
  continuous channel (direct `ElectricalSeries` or `LFP` wrapper in acquisitions or processing modules,
  calibrated by `conversion` and `offset`).
- `jnwb.read_nwb(path, allow_missing=None)`: Reads an NWB file through jnwb's repairs and closes
  it, so read data arrays through `nwb_read_io`. A file missing `session_description` raises
  `MissingRequiredNWBFieldError`; `allow_missing=("session_description",)` opens it with the field
  `""`, and `nwbfile.jnwb_waived_requirements` is `("session_description",)` only when the waiver
  was used.
- `jnwb.nwb_read_io(path, mode="r", allow_missing=None)`: Context manager yielding the open
  `NWBHDF5IO`; call `io.read()` and read data inside the block. Same `allow_missing` and waiver
  record as `read_nwb`.
- `jnwb.epoch_continuous(data, onsets, *, win_s, fs)` → `(epochs, time_axis_s)` extracting fixed-window
  epochs from continuous signals aligned to event onsets.

**Event code semantics:** codes are opaque interval-table labels (default column `codes`). jnwb
does not interpret scientific meaning. When `codes=None`, no code filtering is performed and
`code_column` is not required to exist. String and numeric codes compare without cross-type
coercion (`"1"` ≠ `1`). Empty code selection returns an empty array; missing table/column raises
specific errors.

**Table ambiguity:** several interval tables + omitted `table` → `AmbiguousIntervalTableError`.
Several continuous series + omitted `name` in `acquisition_channel` → `AmbiguousAcquisitionError`.

**One schema:** `inspect(path)` and `inspect(nwb_object)` return the same dict for the same
file, including `data_path`, `layout` and `series` on every continuous entry. Every key in
`jnwb.nwb_inspect.CONTINUOUS_KEYS` is always present, `None` when unknown.

**Several series in one container:** an `LFP` wrapping more than one `ElectricalSeries` reports
`series: [names]` with `rate_hz`/`data_path`/`data_shape`/`layout` `None`, and
`acquisition_channel(name=<container>)` raises `AmbiguousAcquisitionError`. Name the series,
bare (`name="series"`) or qualified (`name="container/series"`); a bare name held by two
containers is refused. A name that exists in both `/acquisition` and a processing module is
refused the same way. A series stored with `timestamps` and no constant `rate` is refused
rather than given a rate: read its timestamps and derive the rate against an independent clock.

**Array orientation:** `inspect` reports `layout` per 2-D series, decided by the series' own
electrode region rather than by which side is longer. `acquisition_channel` honors it, so
`channel=k` is the same channel whether the file is time-by-channel or channel-by-time. When the
electrode count matches neither dimension or both, `layout` is `"ambiguous"` and
`acquisition_channel` raises `AmbiguousLayoutError`.

### Repository path roots (not per-file inspection)

- `jnwb.paths.describe()`: report configured data roots and resolution state for a **project**
  checkout — not a substitute for `jnwb.inspect(path_or_nwb)`.

### Addressing, metadata, compression

- `jnwb.map_peak_channel_to_area(peak_channel_id, electrodes_df)`
- `jnwb.classify_layer_from_depth(peak_channel_id, electrodes_df)`
- `jnwb.enrich_units_dataframe(units_df, electrodes_df)`: Writes the geometric depth class ('Deep' / 'Superficial' / 'Unknown') to `depth_class`. `layer` is a deprecated copy, removed in 0.2.7, and writing it emits `FutureWarning`; read `depth_class`. `get_all_units_metadata` emits both the same way.
- `jnwb.probe_geometry(electrodes_table, *, probe_name=None, units="um", nominal_pitch=None, pitch_tolerance=0.1, strict_linear=False)`
- `jnwb.get_all_units_metadata(nwb_paths, filter_quality=False)`
- `jnwb.classify_unit_quality(units_df, thresholds=None)`
- `jnwb.electrode_inventory(nwb_paths)`
- `jnwb.compress_fp32(src, dst=None, *, drop_convolved=False, verify=True, select=None)`: `select=` lists the dataset paths to cast to float32. `select=None` falls back to the anchored LFP/MUAE preset and emits `FutureWarning`; `select=` becomes required in 0.2.7. Naming `spike_train` or `convolved_spike_train`, a missing path, a group, or a dataset whose dtype is not floating (integer and boolean included) raises before anything is written.

MCP tools (`inspect_nwb`, `get_event_codes_and_timings`) wrap the public API for agent hosts;
use the public functions above in normal Python workflows.

- `jnwb.as_trials(X, time_axis=-1, name="X", allow_ragged=True)`: Normalizes any supported container to a `(n_trials, n_times)` float array. Use it before any operation that documents that shape, rather than reshaping by hand.
- `jnwb.resolve_acquisition(path_or_nwb, name=None)`: Resolves an acquisition or processing series by name; raises `AcquisitionNotFoundError` when the name is absent and `AmbiguousAcquisitionError` rather than picking one when it is ambiguous.
- `jnwb.stream_npz_array(file_path, key, slice_tuple=(slice(None, None, None),))`: Memory-bounded slice out of an NPZ archive, compressed or not, without materializing the array.
- `jnwb.audit_units(units_df)` and `jnwb.audit_electrodes(elec_df, units_df=None)`: Spike-time coverage and quality summaries, and electrode configuration with unit-to-electrode mapping coverage. Run both before trusting a session's tables.
- `jnwb.unit_census_report(units_df, group_by=None)`: Census of units; `group_by=None` groups by session, area and `depth_class`, and warns when the frame has only the deprecated `layer`.
- `jnwb.assign_quality_tier(quality, trial_presence_fraction, snr, presence_threshold=0.98, snr_threshold=0.5)`: Tiers a unit `'mua'` / `'stable'` / `'unstable'` from quality code, trial presence and SNR. State the thresholds wherever the tier is reported; they are a choice, not a property of the unit.
- `jnwb.get_snr_analysis(units_df, snr_threshold=1.0, detail=False)`: SNR distribution and quality breakdown across a units table.
- `jnwb.filter_by_criteria(df, criteria, *, unknown="ignore")`: Applies a criteria dict to any table. `unknown="ignore"` silently drops a criterion naming a column that is not there -- pass `unknown="raise"` when a typo must not widen the selection.
- `jnwb.detect_trial_cycles(epochs_df, gap_factor=10.0)` and `jnwb.assign_subblock_quartiles(epochs_df, n_quantiles=4)`: Recording-structure labels -- cycle boundaries from a gap threshold, and temporal quantile buckets by `start_time` order. Both are grouping variables for `permute_labels` and `cluster_permutation_test`, not results.

## 3. Invariants & Safeguards
1. **Discovery before selection:** call `inspect` to see interval table names and code columns;
   pass `table=` explicitly when more than one task-like table exists.
2. **Addressing robustness:** `map_peak_channel_to_area` reads only anatomical columns and
   returns `None` when the table has none. It does **not** fall back to `group_name`, which is the
   probe/shank label: an electrode table with no anatomical column used to return `'probeA'` as
   the brain area of channel 0, a fabricated label indistinguishable from a real one (05-18).
3. **NWB compression contract:** `compress_fp32` casts exactly the datasets named in `select=`
   to fp32, irreversibly; name them rather than relying on the preset. Verify with
   `verify=True` before deleting sources.

## 4. Minimal Workflow
```python
import jnwb

info = jnwb.inspect("session.nwb")
table = "test_synth_task"  # from info["interval_tables"]
onsets = jnwb.event_onsets("session.nwb", table=table, codes=["test-synth-1"])
spikes = jnwb.unit_spike_times("session.nwb", unit_index=0)
lfp, fs_hz = jnwb.acquisition_channel("session.nwb", name="probe_0_lfp", channel=0)
```

## 5. Verification
- Tutorials under `examples/tutorials/` execute in CI (`tests/test_tutorials.py`).
- Event/onset acceptance matrix: `tests/test_nwb_events.py`.

## 6. Canonical Documentation Links
- [Tutorial: NWB Basics](../../docs/tutorials/01_nwb_basics.md)
- [Tutorial: Addressing and metadata](../../docs/tutorials/02_addressing_and_metadata.md)
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
