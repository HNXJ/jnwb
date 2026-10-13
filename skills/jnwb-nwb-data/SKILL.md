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
