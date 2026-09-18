---
name: jnwb-nwb-data
description: NWB inspection, event/onset extraction, path addressing, anatomical mapping,
  electrode/unit QC, metadata census, and compression.
---

# `jnwb-nwb-data` — NWB Data, Addressing & Metadata

## 1. Trigger
Activate when inspecting NWB files, extracting event onsets, resolving paths, mapping
electrode channels to areas/layers, auditing unit quality, or compressing arrays.

## 2. Task-to-Primitive Routing Matrix

### Per-file discovery and events (canonical Python route)

- `jnwb.inspect(path_or_nwb)` → structured `dict` listing acquisitions, electrodes, units,
  and **all** interval tables with column samples. Does **not** select a default event table.
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
`acquisition_channel(name=<container>)` raises `AmbiguousAcquisitionError`. Name the series.
A name that exists in both `/acquisition` and a processing module is refused the same way.

**Array orientation:** `inspect` reports `layout` per 2-D series, decided by the series' own
electrode region rather than by which side is longer. `acquisition_channel` honours it, so
`channel=k` is the same channel whether the file is time-by-channel or channel-by-time. When the
electrode count matches neither dimension or both, `layout` is `"ambiguous"` and
`acquisition_channel` raises `AmbiguousLayoutError`.

### Repository path roots (not per-file inspection)

- `jnwb.paths.describe()`: report configured data roots and resolution state for a **project**
  checkout — not a substitute for `jnwb.inspect(path_or_nwb)`.

### Addressing, metadata, compression

- `jnwb.map_peak_channel_to_area(peak_channel_id, electrodes_df)`
- `jnwb.classify_layer_from_depth(peak_channel_id, electrodes_df)`
- `jnwb.enrich_units_dataframe(units_df, electrodes_df)`
- `jnwb.probe_geometry(electrodes_table, *, probe_name=None, units="um", nominal_pitch=None, pitch_tolerance=0.1, strict_linear=False)`
- `jnwb.get_all_units_metadata(nwb_paths, filter_quality=False)`
- `jnwb.classify_unit_quality(units_df, thresholds=None)`
- `jnwb.electrode_inventory(nwb_paths)`
- `jnwb.compress_fp32(src, dst=None, *, drop_convolved=False, verify=True)`

MCP tools (`inspect_nwb`, `get_event_codes_and_timings`) wrap the public API for agent hosts;
use the public functions above in normal Python workflows.

## 3. Invariants & Safeguards
1. **Discovery before selection:** call `inspect` to see interval table names and code columns;
   pass `table=` explicitly when more than one task-like table exists.
2. **Addressing robustness:** `map_peak_channel_to_area` checks `location`, then `area`, and
   returns `None` when neither exists. It does **not** fall back to `group_name`, which is the
   probe/shank label: an electrode table with no anatomical column used to return `'probeA'` as
   the brain area of channel 0, a fabricated label indistinguishable from a real one (05-18).
3. **NWB compression contract:** `compress_fp32` converts on-disk electrical series to fp32;
   verify with `verify=True` before deleting sources.

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
