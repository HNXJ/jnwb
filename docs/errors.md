# Errors and What to Pass Instead

Every refusal in this list is deliberate. jnwb will not guess which acquisition, which
interval table or which column you meant, because a wrong guess produces a number rather
than an error, and a number is much harder to notice. Each message names the thing that
was ambiguous or missing **and** the values that were available, so the fix is always to
pass one of them.

The messages below are the real ones, taken from a file written with plain pynwb.

## What to pass

| Error | Raised by | The fix |
|---|---|---|
| `AmbiguousAcquisitionError` | `acquisition_channel`, `resolve_acquisition` | `name=` one of the series in the message |
| `AcquisitionNotFoundError` | `acquisition_channel`, `resolve_acquisition` | `name=` one of the names under `Available` |
| `ChannelIndexError` | `acquisition_channel` | `channel=` below the stated count |
| `AmbiguousLayoutError` | `acquisition_channel` | Nothing. Read and transpose the array yourself |
| `UnitNotFoundError` | `unit_spike_times` | `unit_index=` below the stated count |
| `AmbiguousIntervalTableError` | `events`, `event_onsets`, `resolve_interval_table` | `table=` one of the names in the message |
| `IntervalTableNotFoundError` | `events`, `event_onsets`, `resolve_interval_table` | `table=` one of the names under `Available` |
| `ColumnNotFoundError` | `events`, `event_onsets` | `code_column=` one of the listed columns |
| `InvalidOnsetValueError` | `events`, `event_onsets`, `epoch_continuous` | Drop or repair the row the message names |
| `MissingRequiredNWBFieldError` | any read | Nothing. Repair the file |

`NWBInspectError` and `NWBEventError` are the two base classes; they are never raised
directly. The rest of this page is why each refusal exists, which the table cannot carry.

## Finding the name to pass

Two resolvers answer "what would jnwb pick, and is that unambiguous?" without reading any
data. They take the same arguments as the functions that use them, and they raise the same
errors, so they are the cheapest way to find out what a file will do.

```python
jnwb.resolve_acquisition(path_or_nwb, name=None)     # -> the continuous series name
jnwb.resolve_interval_table(path_or_nwb, table=None) # -> the interval table name
```

`resolve_acquisition` searches `/acquisition` and every processing module. With `name`
omitted it returns the sole continuous series when exactly one exists, and otherwise
raises. `resolve_interval_table` prefers a table called `trials`, falls back to the sole
table, and otherwise raises.

[`inspect`](api.md) lists everything both of them can see:

```python
info = jnwb.inspect("recording.nwb")
[a["name"] for a in info["acquisitions"]]
[t["name"] for t in info["interval_tables"]]
[c["name"] for c in info["interval_tables"][0]["columns"]]
```

## Addressing an NWB file: `NWBInspectError`

`jnwb.NWBInspectError` is the base class for every error raised while addressing a file's
contents. Catch it to catch the family:

```python
try:
    data, fs = jnwb.acquisition_channel(path, channel=0)
except jnwb.NWBInspectError as exc:
    print(exc)          # every message below names what to pass next
```

### `AmbiguousAcquisitionError`

> Several continuous series present: ['probe_0_lfp', 'probe_1_lfp']. Pass name=&lt;series&gt; explicitly.

Two narrower kinds of ambiguity raise the same class:

> Container 'LFP' wraps 2 electrical series: ['lfp_alpha', 'lfp_beta']. Pass name=&lt;series&gt; explicitly.

An `LFP` container holding several series has no single rate, shape or path, so name the
series itself rather than the container.

> 'shared' names both /acquisition/shared and ['ecephys/shared'].

The same name exists in `/acquisition` and in a processing module, and they are different
data. The qualified processing name (`"ecephys/shared"`) means the latter.

### `AcquisitionNotFoundError`

> Series 'nope' not found. Available: ['probe_0_lfp', 'probe_1_lfp']

The same class is raised when a series exists but has no readable data array, and when it
has no constant sampling rate — a series with explicit `timestamps` rather than a `rate`
cannot be epoched by sample index.

### `ChannelIndexError`

> Channel index 99 out of range for series 'only' with 4 channels (layout time_by_channel, decided by electrode_count)

The message states which axis holds channels and how that was decided:
`electrode_count` means it was read from the series' electrode region, `shape` means it
was guessed from which dimension is longer, because the series carries no electrode
information.

### `AmbiguousLayoutError`

> Cannot tell which axis of series 'square' holds channels: shape (4, 4) against 4 electrodes, so neither dimension matches or both do. Guessing would return a slice across channels as a channel's time course.

There is no argument that resolves this one, because the file does not contain the answer.
`inspect` reports `layout: "ambiguous"` for the same series. Transpose the array according
to what you know about how it was recorded; jnwb will not pick an axis, because a wrong
pick returns one instant sampled across channels dressed as a channel's time course.

### `UnitNotFoundError`

> Unit index 7 out of range for 1 units

Raised for an out-of-range row, for a file with no units table, and for a units table with
no `spike_times` column. `jnwb.inspect(path)["units"]` shows which of the three it is.

## Reading events: `NWBEventError`

`jnwb.NWBEventError` is the base class for event and onset extraction errors.

### `AmbiguousIntervalTableError`

> Several interval tables and none named 'trials': ['blocks', 'stimuli']. Pass table=&lt;name&gt; explicitly.

A file with a `trials` table *and* five others does not raise: `trials` wins. Pass
`table=` anyway when you mean one of the others.

### `IntervalTableNotFoundError`

> Interval table 'nope' not found. Available: ['trials']

### `ColumnNotFoundError`

> Code column 'nope' not found. Columns: ['start_time', 'stop_time']

`codes` is a jnwb default, not an NWB requirement — a file from another lab usually calls
that column `stimulus`, `condition` or `trial_type`.

Omitting `code_column` on a table with no `codes` column is *not* an error: the onsets are
returned with a warning that no codes were found, because the onsets are what you need
next. Naming a column that does not exist is an error, because you asked for something
specific.

### `InvalidOnsetValueError`

> Missing onset in column 'start_time' at table row 0

> Non-finite onset at index 0: np.float64(nan)

All three entry points agree: `events`, `event_onsets` and `epoch_continuous` refuse a
missing or non-finite onset rather than carry `NaN` into an index computation.

## Reading the file at all: `MissingRequiredNWBFieldError`

> NWB file is missing required field 'session_description'; jnwb does not synthesize required metadata

Raised while reading, when a field the NWB specification requires is absent from the file
on disk. The exception carries the missing field name as `exc.field_name`. jnwb will not
invent a value for a field the specification requires, because a synthesized
`session_description` propagates into every figure caption and table that reads it.

## Warnings, not errors

Two conditions warn rather than raise, because in both cases the caller gets something
usable and the risk is that it is silently wrong.

| Condition | Raised by | What you get |
|---|---|---|
| No `codes` column | `events`, `event_onsets` | The onsets, without codes |
| Most epochs entirely outside the data, under `boundary_policy="nan"` | `epoch_continuous` | An array of the right shape and entirely `NaN`, which is what onsets in milliseconds look like when read as seconds. The warning names both spans. See [Common mistakes §11](common_mistakes.md) |

Turn either into an error while developing:

```python
import warnings
warnings.simplefilter("error", UserWarning)
```
