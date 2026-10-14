### Per-file discovery and events

- `jnwb.inspect(path_or_nwb)` → structured `dict` listing acquisitions, electrodes, units,
  and **all** interval tables with column samples. Selects no event table on the caller's behalf.
- `jnwb.event_onsets(path_or_nwb, table=None, codes=None, code_column="codes",
  onset_column="start_time")` → `numpy.ndarray` of onset times (seconds), table row order.
- `jnwb.unit_spike_times(path_or_nwb, unit_index=0)` → spike times in seconds for one units row.
- `jnwb.acquisition_channel(path_or_nwb, name=None, channel=0)` → `(data, rate_hz)` for one
  continuous channel (direct `ElectricalSeries` or `LFP` wrapper in acquisitions or processing modules,
  or a series wrapped in `FilteredEphys` or a behavior container: `EyeTracking`, `PupilTracking`,
  `BehavioralTimeSeries`, `Position`, `CompassDirection`: in acquisitions; calibrated by
  `conversion`, the channel's `channel_conversion` factor and `offset`).
- `jnwb.resolve_acquisition(path_or_nwb, name=None)`: Resolves an acquisition or processing series by name; raises `AcquisitionNotFoundError` when the name is absent and `AmbiguousAcquisitionError` rather than picking one when it is ambiguous.
- `jnwb.read_nwb(path, allow_missing=None)`: Reads an NWB file through jnwb's repairs and closes
  it, so read data arrays through `nwb_read_io`. A file missing `session_description` raises
  `MissingRequiredNWBFieldError`; `allow_missing=("session_description",)` opens it with the field
  `""`, and `nwbfile.jnwb_waived_requirements` is `("session_description",)` only when the waiver
  was used.
- `jnwb.nwb_read_io(path, mode="r", allow_missing=None)`: Context manager yielding the open
  `NWBHDF5IO`; call `io.read()` and read data inside the block. Same `allow_missing` and waiver
  record as `read_nwb`. Read-only: any other `mode` raises `ValueError`; write with
  `pynwb.NWBHDF5IO`.
- `jnwb.as_trials(X, time_axis=-1, name="X", allow_ragged=True)`: Normalizes any supported container to a `(n_trials, n_times)` float array. Use it before any operation that documents that shape, rather than reshaping by hand.

- `jnwb.check_ragged_indices(path, *, table="units", probe_starts=None, probe_column=None)`: Read-only integrity check of every `<column>_index` of one table, returning a `RaggedIndexReport` with one `RaggedIndexCheck` per column: `monotonic`, `nonnegative`, `ends_at_data_len`, `length_fits`, and `offset_bug` (the multi-probe offset defect). The defect test needs `probe_starts` or `probe_column`; without one `offset_bug` is `"not_tested"`. Writes nothing.
- `jnwb.repair_ragged_index(path, column, *, table="units", probe_starts=None, probe_column=None, dry_run=True, output_path=None, in_place=False, backup_path=None)`: Corrects one index only when `check_ragged_indices` reports `"detected"`; otherwise raises `RaggedIndexRepairRefused`. Dry run unless `dry_run=False`, which needs `output_path` (a new file) or `in_place=True` with `backup_path`. The index is written to a copy, re-read and checked before an atomic replace; a failure leaves the input byte-identical. See [Repairing NWB files](../../../docs/repairing_nwb.md).
- `jnwb.check_waveform_blocks(path, *, table="units", rtol, atol=0.0)`: Read-only check that each unit's `waveform_mean` block is the unit's, ragged (sliced by `waveform_mean_index`) or dense (`waveform_mean[unit]` of shape `(units, samples, channels)`): `owned` when some row's peak-to-peak matches the stored `amplitude` within tolerance, `unowned` when no row of a complete block matches, `unknown` for an empty block or a missing, NaN or infinite amplitude. `rtol` is required because no tolerance suits every writer. Repairs and reassigns nothing. A stored `amplitude` in another unit than the blocks raises `ValueError` naming a unit mismatch when the median ratio of amplitude to largest block peak-to-peak is 1000 or more, or 1/1000 or less. See [Repairing NWB files](../../../docs/repairing_nwb.md).
- `jnwb.validate_nwb(path, *, layers=None, dandi_ignore=("DANDI.NO_DANDISET_FOUND",), max_messages=50)`: Validates one NWB file in six layers (`read`, `pynwb_schema`, `pynwb_core`, `integrity`, `nwbinspector`, `dandi`) and returns an `NWBValidationReport` whose `layers` hold one row per layer. `ok` is no failed layer, `complete` is no skipped layer, `dandi_ready` is True only when the `dandi` layer ran and passed. A layer whose optional dependency is missing (`pip install jnwb[validate]`) is skipped, never passed. Writes nothing. See [Repairing NWB files](../../../docs/repairing_nwb.md).

Choosing an interval table, event rows, epochs around events, recording structure and what a
condition code means are routed by `jnwb-paradigm`.

MCP tools `inspect_nwb` and `get_event_codes_and_timings` wrap `inspect` and `events` for agent
hosts, and `prepare_signal_reference` describes one dataset without loading it and names the
`acquisition_channel` call that reads it; Python workflows call the functions directly.

| Topic | Contract |
|---|---|
| Event codes | Codes are opaque interval-table labels (default column `codes`); jnwb does not interpret their meaning. With `codes=None` nothing is filtered and the column `codes` may be absent (`events` then warns and records `code_column=None`); a `code_column` named explicitly must exist, with or without `codes`, or `ColumnNotFoundError` is raised. String and numeric codes compare without cross-type coercion (`"1"` ≠ `1`). An empty code selection returns an empty array; a missing table or column raises a specific error. |
| Ambiguity | Several interval tables and no `table` → `AmbiguousIntervalTableError`. Several continuous series and no `name` in `acquisition_channel` → `AmbiguousAcquisitionError`. |
| One schema | `inspect(path)` and `inspect(nwb_object)` return the same dict for the same file. Every continuous entry always carries `name`, `path`, `neurodata_type`, `packaging`, `series`, `data_path`, `data_shape`, `data_dtype`, `layout`, `rate_hz` and `starting_time` (seconds, and None for a series stored with timestamps), `None` when unknown. |
| Aligning events to a series | Event times in the interval tables are session times, and sample 0 of an `acquisition_channel` array is at the series' `starting_time`. Subtract it from the onsets before epoching: `epoch_continuous(data, onsets - entry["starting_time"], win_s=..., fs=rate_hz)`. `acquisition_channel` warns when `starting_time` is not 0. |
| Several series in one container | An `LFP` wrapping more than one `ElectricalSeries` reports `series: [names]` with `rate_hz`/`data_path`/`data_shape`/`layout` `None`, and `acquisition_channel(name=<container>)` raises `AmbiguousAcquisitionError`. Name the series, bare (`name="series"`) or qualified (`name="container/series"`); a bare name held by two containers is refused, as is a name in both `/acquisition` and a processing module. A series stored with `timestamps` and no constant `rate` is refused rather than given a rate: read its timestamps and derive the rate against an independent clock. |
| Array orientation | `inspect` reports `layout` per 2-D series, decided by the series' own electrode region rather than by which side is longer. `acquisition_channel` honors it, so `channel=k` is the same channel whether the file is time-by-channel or channel-by-time. When the electrode count matches neither dimension or both, `layout` is `"ambiguous"` and `acquisition_channel` raises `AmbiguousLayoutError`. |
