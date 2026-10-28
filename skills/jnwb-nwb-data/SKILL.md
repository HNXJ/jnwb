---
name: jnwb-nwb-data
description: NWB inspection, event/onset extraction, path addressing, anatomical mapping,
  metadata census, and compression.
---

# `jnwb-nwb-data` — NWB Data, Addressing & Metadata

## 1. Trigger
Inspecting NWB files, extracting event onsets, resolving paths, mapping electrode channels to
areas/layers, or compressing arrays.

## 2. Routing

The "Per-file discovery and events" routing rows live in [`references/per_file_discovery_and_events.md`](references/per_file_discovery_and_events.md).

The "Repository path roots" routing rows live in [`references/repository_path_roots.md`](references/repository_path_roots.md).

The "Addressing and metadata" routing rows live in [`references/addressing_and_metadata.md`](references/addressing_and_metadata.md).

The "Compression and storage" routing rows live in [`references/compression_and_storage.md`](references/compression_and_storage.md).

- Timestamps labelled seconds that hold acquisition ticks go to `jnwb.derive_tick_clock(tick_segments, spike_times)`, which returns a `jnwb.TickClock`; `seconds(ticks)` maps the ticks to session seconds. The tick segments and the spike times must each cover the whole recording, and the caller checks the offset, which is placed at the first spike.
- A stream that may have been held from a lower rate goes to `jnwb.effective_rate(data, rate)`, which returns a `jnwb.EffectiveRate` (`repeat_fraction`, `repeat_runs`, `power_above_quarter`, `held`); `held` is the repeat fraction against a fixed 0.25, and the power share is evidence only.
- Gaze onsets of departure from a baseline go to `jnwb.gaze_departure_onsets(gaze, rate, trial_starts, *, baseline_window_s, reference_trials, envelope_percentile=99.5, hold_s=0.025, walkback_fraction=0.5)`: one onset in seconds per trial, NaN for a trial with no departure; `baseline_window_s` is `(start_s, stop_s)` relative to each trial start.
- The rising and falling edge of a `TimeSeries` nearest each event go to `jnwb.edges_near_events(path_or_nwb, series_path, events, *, threshold, window_s)`: a DataFrame with one row per event; `window_s` is `(before_s, after_s)`; the caller names the series and the threshold.
- `jnwb.write_nwb(nwbfile, *, dst, overwrite=False, verify=True)`: Writes a caller-built `NWBFile` to `dst` and returns a `MutationReport`. The object is schema-validated before anything is written; a failure raises `NWBMutationError` and leaves nothing behind. An existing `dst` raises `FileExistsError` unless `overwrite=True`; a required field left empty raises `MissingRequiredNWBFieldError`. With `verify=True` the written file is re-read by `verify_nwb`; a failed check raises `NWBVerificationError` and leaves the file in place.
- `jnwb.transform_nwb(src, *, dst, keep=None, drop=None, cast=None, compression=None, overwrite=False, verify=True)`: Copies `src` to `dst` with declared changes and returns a `MutationReport`. `keep` or `drop` (not both) names paths; `cast` maps float datasets to a floating dtype; `compression` is `{"filter": "gzip", ...}` or `None`. A drop that would leave a dangling reference, a cast of an index dataset, of an integer or boolean dataset to a non-floating or narrower type, or an existing `dst` without `overwrite=True` raises and writes nothing.
- `jnwb.repair_nwb(src, *, dst, repairs, overwrite=False, verify=True)`: Writes the read path's in-memory repairs (`squeeze_scalar_attributes`, `units_colnames`, `vector_index_types`, `waveform_index_dtype`) to a copy and returns a `MutationReport`. A repair whose precondition does not hold, or that would change nothing, raises `UnidentifiableRepairError` and writes nothing.
- `jnwb.verify_nwb(dst, *, against=None, report=None, n_check=200000)`: Re-reads one written NWB file and returns a `MutationReport` whose `checks` hold one row per check. Always parses the file through pynwb, runs schema validation, and resolves every link and object reference. With `against` and the writer's `report`, each dataset the report's applied records do not name is byte-identical over `n_check` rows (scalars whole, references dereferenced to their targets), `file_create_date` ignored; the attributes of every dataset, group and the root are compared, `object_id` ignored, and a group an applied record names is exempt; any other difference is reported unexplained. An applied record named `cast` declares its paths as dtype casts of the source. `against` without `report` raises `ValueError`.

## 3. Invariants & Safeguards
1. **Discovery before selection:** call `inspect` to see interval table names and code columns;
   pass `table=` explicitly when more than one task-like table exists.
2. **Addressing:** `map_peak_channel_to_area` reads only anatomical columns and returns `None`
   when the table has none. It does **not** fall back to `group_name`, the probe/shank label,
   which would report a label such as `'probeA'` as the brain area, indistinguishable from a
   real one.
3. **Compression:** `compress_fp32` casts exactly the datasets named in `select=` to fp32,
   irreversibly; name only floating-point arrays, and verify with `verify=True`
   before deleting sources.

## 4. Minimal Workflow
```python
# Input: calibration fixture.
import jnwb

# session.nwb here is a small synthetic file of known contents; pass your own path.
info = jnwb.inspect("session.nwb")
table = "test_synth_task"  # from info["interval_tables"]
onsets = jnwb.event_onsets("session.nwb", table=table, codes=["test-synth-1"])
spikes = jnwb.unit_spike_times("session.nwb", unit_index=0)
lfp, fs_hz = jnwb.acquisition_channel("session.nwb", name="probe_0_lfp", channel=0)
```

## 5. Verification
- Tutorials under `examples/tutorials/` execute in CI (`tests/test_tutorials.py`).
- `examples/quickstart_jnwb.py` is the smoke script and `examples/notebooks/01_spectral_and_inference.ipynb` the executed notebook (`tests/test_notebooks.py`).
- Event/onset acceptance matrix: `tests/test_nwb_events.py`.

## 6. Documentation
- [Tutorial: NWB Basics](../../docs/tutorials/01_nwb_basics.md)
- [Tutorial: Addressing and metadata](../../docs/tutorials/02_addressing_and_metadata.md)
- [`docs/reading_nwb.md`](../../docs/reading_nwb.md)
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
