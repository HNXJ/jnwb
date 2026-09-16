# Errors and What to Pass Instead

Every refusal in this list is deliberate. jnwb will not guess which acquisition, which
interval table or which column you meant, because a wrong guess produces a number rather
than an error, and a number is much harder to notice. Each message names the thing that
was ambiguous or missing **and** the values that were available, so the fix is always to
pass one of them.

The messages below are the real ones, taken from a file written with plain pynwb.

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

Raised by `acquisition_channel` and `resolve_acquisition` when `name` is omitted and the
file holds more than one continuous series. **Pass `name=` one of the names in the
message.**

It is also raised for two narrower kinds of ambiguity:

> Container 'LFP' wraps 2 electrical series: ['lfp_alpha', 'lfp_beta']. Pass name=&lt;series&gt; explicitly.

An `LFP` container holding several series has no single rate, shape or path. **Pass
`name=` the series itself**, not the container.

> 'shared' names both /acquisition/shared and ['ecephys/shared'].

The same name exists in `/acquisition` and in a processing module, and they are different
data. **Pass the qualified processing name** (`"ecephys/shared"`) to mean the latter.

### `AcquisitionNotFoundError`

> Series 'nope' not found. Available: ['probe_0_lfp', 'probe_1_lfp']

The name does not exist. **Pass one of the names in `Available`.** The same class is
raised when a series exists but has no readable data array, and when it has no constant
sampling rate — a series with explicit `timestamps` rather than a `rate` cannot be
epoched by sample index.

### `ChannelIndexError`

> Channel index 99 out of range for series 'only' with 4 channels (layout time_by_channel, decided by electrode_count)

The channel index is outside the series. The message states the true channel count, which
axis holds channels and how that was decided — `electrode_count` means it was read from
the series' electrode region, `shape` means it was guessed from which dimension is longer
because the series carries no electrode information. **Pass `channel=` below the stated
count.**

### `AmbiguousLayoutError`

> Cannot tell which axis of series 'square' holds channels: shape (4, 4) against 4 electrodes, so neither dimension matches or both do. Guessing would return a slice across channels as a channel's time course.

The channel axis cannot be determined: the electrode count matches neither dimension, or
the array is square so it matches both. There is no argument that resolves this one,
because the file does not contain the answer. `inspect` reports `layout: "ambiguous"` for
the same series. **Read the array yourself** and transpose it according to what you know
about how it was recorded; jnwb will not pick an axis, because a wrong pick returns one
instant sampled across channels dressed as a channel's time course.

### `UnitNotFoundError`

> Unit index 7 out of range for 1 units

Raised by `unit_spike_times` for an out-of-range row, for a file with no units table, and
for a units table with no `spike_times` column. **Pass `unit_index=` below the stated
count**, or check `jnwb.inspect(path)["units"]`.

## Reading events: `NWBEventError`

`jnwb.NWBEventError` is the base class for event and onset extraction errors.

### `AmbiguousIntervalTableError`

> Several interval tables and none named 'trials': ['blocks', 'stimuli']. Pass table=&lt;name&gt; explicitly.

Raised by `events`, `event_onsets` and `resolve_interval_table` when `table` is omitted,
several interval tables exist and none is called `trials`. **Pass `table=` one of the
names in the message.** Note that a file with a `trials` table *and* five others does not
raise: `trials` wins. Pass `table=` anyway when you mean one of the others.

### `IntervalTableNotFoundError`

> Interval table 'nope' not found. Available: ['trials']

**Pass one of the names in `Available`.**

### `ColumnNotFoundError`

> Code column 'nope' not found. Columns: ['start_time', 'stop_time']

The interval table exists and the requested `code_column` does not. **Pass `code_column=`
one of the listed columns.** `codes` is a jnwb default, not an NWB requirement — a file
from another lab usually calls that column `stimulus`, `condition` or `trial_type`.

Omitting `code_column` on a table with no `codes` column is *not* an error: the onsets are
returned with a warning that no codes were found, because the onsets are what you need
next. Naming a column that does not exist is an error, because you asked for something
specific.

### `InvalidOnsetValueError`

> Missing onset in column 'start_time' at table row 0

> Non-finite onset at index 0: np.float64(nan)

A selected row has a missing or non-finite onset. All three entry points agree: `events`,
`event_onsets` and `epoch_continuous` refuse it rather than carry `NaN` into an index
computation. **Drop or repair the offending row**; the message names it.

## Reading the file at all: `MissingRequiredNWBFieldError`

> NWB file is missing required field 'session_description'; jnwb does not synthesize required metadata

Raised while reading, when a field the NWB specification requires is absent from the file
on disk. There is no argument to pass: the file is incomplete. **Repair the file** — the
exception carries the missing field name as `exc.field_name`. jnwb will not invent a value
for a field the specification requires, because a synthesized `session_description`
propagates into every figure caption and table that reads it.

## Warnings, not errors

Two conditions warn rather than raise, because in both cases the caller gets something
usable and the risk is that it is silently wrong.

- **No `codes` column** (`events`, `event_onsets`): the onsets are returned without codes.
- **Most epochs entirely outside the data** (`epoch_continuous`, under
  `boundary_policy="nan"`): the returned array is the right shape and entirely `NaN`,
  which is what onsets in milliseconds look like when read as seconds. The warning names
  both spans. See [Common mistakes §11](common_mistakes.md).

Turn either into an error while developing:

```python
import warnings
warnings.simplefilter("error", UserWarning)
```
