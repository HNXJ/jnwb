### Addressing and metadata

- `jnwb.map_peak_channel_to_area(peak_channel_id, electrodes_df)`
- `jnwb.classify_layer_from_depth(peak_channel_id, electrodes_df)`
- `jnwb.probe_geometry(electrodes_table, *, probe_name=None, units="um", nominal_pitch=None, pitch_tolerance=0.1, strict_linear=False)`
- `jnwb.get_all_units_metadata(nwb_paths, filter_quality=False, allow_missing=None)`: also takes an open `NWBFile` (used as is, never closed here); `allow_missing=("session_description",)` opens files that lack it, and the waivers used are recorded in the frame's `attrs["jnwb_waived_requirements"]` keyed by input name.
- `jnwb.electrode_inventory(nwb_paths)`
- `jnwb.unit_census_report(units_df, group_by=None)`: Census of units; `group_by=None` groups by `session_id`, `area` and `depth_class`, does not read a `layer` column, and emits `UserWarning` when the frame has `layer` but no `depth_class` (which `enrich_units_dataframe` supplies). It aggregates `firing_rate`, `waveform_duration` and `snr` and counts `unit_id` (or `cluster_id`), so it takes a frame as `get_all_units_metadata` builds it; a frame without those columns raises `KeyError`.
- `jnwb.filter_by_criteria(df, criteria, *, unknown="ignore")`: Applies a criteria dict to any table. `unknown="ignore"` silently drops a criterion naming a column that is not there. Pass `unknown="raise"` when a typo must not widen the selection.

Auditing a session's unit and electrode tables, and unit quality (measures, classes, tiers, SNR), are routed by `jnwb-qc`.
