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
| `MissingRequiredNWBFieldError` | any read | Repair the file, or waive the field with `read_nwb(path, allow_missing=(exc.field_name,))` |

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
info = jnwb.inspect("session.nwb")
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

| Basis | How the channel axis was found |
|---|---|
| `electrode_count` | read from the series' electrode region |
| `schema` | the series is a type with no electrode region, such as a plain `TimeSeries`, so it is read time-first as the NWB schema lays it out |
| `shape` | guessed from which dimension is longer, because the series has no electrode region and its type does not settle the axis |

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

Omitting `code_column` on a table with no `codes` column is *not* an error, because the
onsets are what you need next: `events` returns them with a warning that names the columns,
and `event_onsets` without `codes=` returns them without one. Naming a column that does not
exist is an error, because you asked for something specific.

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

To open the file anyway, name the field you accept losing. Today `session_description` is the
only field jnwb refuses on, and naming any other raises `ValueError`:

```python
try:
    nwbfile = jnwb.read_nwb("session.nwb")
except jnwb.MissingRequiredNWBFieldError as exc:
    nwbfile = jnwb.read_nwb("session.nwb", allow_missing=(exc.field_name,))

nwbfile.session_description        # "" -- pynwb cannot build the object without the field
nwbfile.jnwb_waived_requirements   # ("session_description",)
```

`jnwb_waived_requirements` records the waivers the read used, not the ones it was offered. A
file that has the field reads `()` under the same `allow_missing`, so passing the waiver across a
whole corpus still tells each waived file apart from one that recorded an empty description.

`read_nwb` closes the file before it returns, so its object holds metadata and no readable data
arrays. To read data from a waived file, read inside `nwb_read_io`, which takes the same
`allow_missing` and sets the same attribute:

```python
with jnwb.nwb_read_io("session.nwb", allow_missing=("session_description",)) as io:
    nwbfile = io.read()
    spike_times = nwbfile.units["spike_times"][0]
```

The functions that take a path (`inspect`, `events`, `unit_spike_times`, ...) never waive.

### What a read returns for each state of `session_description`

"Default" is `read_nwb(path)`; "waived" is `read_nwb(path, allow_missing=("session_description",))`.
"Flag" is `jnwb_waived_requirements` on the returned object.

| On disk | Default | Waived |
|---|---|---|
| Absent | Raises `MissingRequiredNWBFieldError` | `""`, flag `("session_description",)` |
| Explicit null: null dataspace, zero-length array or null reference | Raises an HDMF or h5py error | Raises the same error |
| Empty string | `""`, flag `()` | `""`, flag `()` |
| One-element string array | The element, flag `()`, no warning | The same |
| Any other malformed value, such as an integer or a two-element array | Raises HDMF's `ConstructError` | Raises the same error |
| Present and valid | The value, flag `()` | The same |
| Soft or external link to a valid description | The linked value, flag `()` | The same |
| Dangling soft link | Raises `MissingRequiredNWBFieldError`, with `BrokenLinkWarning` | `""`, flag `("session_description",)`, with `BrokenLinkWarning` |
| External link to a missing file | Raises `MissingRequiredNWBFieldError`, with `BrokenLinkWarning` | `""`, flag `("session_description",)`, with `BrokenLinkWarning` |
| Fixed-length string of NUL bytes | `""`, flag `()` | The same |

Four rows collapse information the file holds, and the returned object cannot recover it:

- **Damage reads as absence.** A dangling soft link and a broken external link return exactly
  what an absent field returns. HDMF drops the link and emits `BrokenLinkWarning` during the
  read; the returned object carries no trace of it. Record warnings at read time if damage and
  incompleteness must be told apart.
- **NUL bytes read as empty.** A fixed-length string loses its trailing NUL bytes when read, so
  a field holding only NULs is indistinguishable from an empty one.
- **A one-element array reads as its element.** pynwb flattens it on every read, with or without
  jnwb, and it is indistinguishable from a scalar holding the same string.

## Warnings, not errors

Three conditions warn rather than raise, because in each case the caller gets something
usable and the risk is that it is silently wrong.

| Condition | Raised by | What you get |
|---|---|---|
| A length-1 array attribute was collapsed to its scalar: `SqueezedAttributeWarning` | any read | The repaired value. The warning names the attributes, once per read, so a record written from the read can say the file needed repairing |
| No `codes` column | `events` | The onsets, without codes. `event_onsets` returns them without the warning |
| Most epochs entirely outside the data, under `boundary_policy="nan"` | `epoch_continuous` | An array of the right shape and entirely `NaN`, which is what onsets in milliseconds look like when read as seconds. The warning names both spans. See [Common mistakes §11](common_mistakes.md) |

Turn all three into errors while developing:

```python
import warnings
warnings.simplefilter("error", UserWarning)
```
