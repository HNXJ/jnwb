# Repairing NWB files

A file that opens is not a file that is correct. This page covers defects in multi-probe
spike-sorted NWB files that a read does not show, how to detect each, and what to check before
and after a repair.

## Ragged index offset

A ragged column such as `spike_times` or `waveform_mean` is a flat data array plus
`<column>_index`, whose entry `i` is the exclusive end offset of row `i`; row 0 starts at 0
(HDMF `VectorIndex`). A correct index is therefore non-negative, non-decreasing, ends at the
first-axis length of the data, and has a dtype that holds that length. An empty index over empty
data is a valid empty table.

The defect this page repairs comes from a writer that appends each probe after the first with
the index offset by the first element of the existing index instead of its last (the running
total). The flat data are complete and in row order; only the index is wrong, so rows of later
probes slice into earlier probes' data.

| Check | Flag on each column's check (`report.columns`) |
|---|---|
| Non-decreasing | `monotonic` |
| First element at least 0 | `nonnegative` |
| Last element equals `len(data)` (`len(data) == 0` for an empty index) | `ends_at_data_len` |
| `len(data)` representable in the index dtype | `length_fits` |
| Index equals the defect's formula and the corrected index ends at `len(data)` | `offset_bug == "detected"` |

```python
import jnwb

# Rows where each probe begins; from a per-probe counter column c that restarts at 0,
# use np.flatnonzero(c == 0). Here: probes of 40 and 55 units, then the rest.
report = jnwb.check_ragged_indices("session.nwb", probe_starts=[0, 40, 95])
for c in report.columns:
    print(c.column, c.offset_bug, c.monotonic, c.ends_at_data_len, c.length_fits)
```

`check_ragged_indices` opens the file read-only and writes nothing. Without `probe_starts` or
`probe_column` the defect test reports `"not_tested"`. A file that fails both the defect test and
the correct-index test is `"inconsistent"` and is damaged in some other way.

`repair_ragged_index` is a dry run by default. It refuses unless the old index is exactly the
defect's formula and the corrected index fits the dtype, and it raises
`RaggedIndexRepairRefused` otherwise; [Errors](errors.md#repairing-a-ragged-index-raggedindexrepairrefused)
lists every message. To write, name a destination:

```python
r = jnwb.repair_ragged_index("session.nwb", "spike_times", probe_starts=[0, 40, 95],
                             dry_run=False, output_path="session_repaired.nwb")
```

The input is copied, only `<column>_index` of the copy is rewritten (same dtype and shape), and
the copy is re-read and checked before it is moved into place, so `r.written` is True only for a
verified file. `in_place=True` with a `backup_path` replaces the input instead, by the same
verified copy and an atomic `os.replace`; the backup holds the old index. A new `output_path` is
claimed exclusively just before the move, so a file that appears there meanwhile is refused. A
dry run writes nothing and ignores `backup_path`. A failure at any step
leaves the input byte-identical. The refusal is the useful behavior: a file that is wrong in a
different way stays unchanged and reported.

**Also check:** a ragged column whose data and `_index` exist but whose name is missing from the
table's `colnames` attribute is hidden by pynwb (`units["spike_times"]` raises `KeyError`).
`RaggedIndexReport.unlisted_ragged_columns` lists them; the check does not fix the attribute.

**Index dtype overflow.** An `int32` index holds offsets to 2,147,483,647. A long recording with
dense spiking, or a waveform table with one row per channel per unit, can exceed it, and a writer
that wraps silently produces a decreasing index. `length_fits` and `monotonic` catch both; the
fix is rewriting the file with a wider integer type, not editing the index.

## Waveform block ownership

A unit's `waveform_mean` block is sliced from the flat data by `waveform_mean_index`,
and nothing ties the sliced block to the unit: a file whose blocks are stored out of
unit order reads another unit's block through pynwb with no warning.
`check_waveform_blocks` compares each sliced block's row amplitudes against the unit's
stored `amplitude`:

```python
import jnwb

report = jnwb.check_waveform_blocks("session.nwb", rtol=1e-6)
print(report.n_owned, report.n_unowned, report.n_unknown)
```

A unit is `owned` when some row's peak-to-peak matches within tolerance:

| Verdict | Meaning |
|---|---|
| `owned` | some row's peak-to-peak matches within tolerance |
| `unowned` | the block is complete and no row matches |
| `unknown` | the block is empty, or the amplitude is missing, NaN or infinite |

`rtol` is required because no tolerance suits every writer. `peak_channel_id` travels
with each verdict for the caller's own join against the electrodes table; the check never
uses it, since a block row is not a channel id. The check repairs and reassigns nothing:
a match is evidence, not proof, and `report.ok` holds only when every unit is owned.

## Units schema across sessions

Pooling units from several files needs the same columns, dtypes and index layout. Before
pooling, compare the column set and the `<column>_index` dtype of every file with
`check_ragged_indices(...).columns` and `jnwb.inspect`. A column that is ragged in one file and
plain in another, or an index stored as `int32` in one and `int64` in another, is a schema
difference that a per-file read does not show.

## Continuous data dtype

`float64` takes twice the bytes of `float32`. `jnwb.compress_fp32(src, select=[...])` casts
exactly the named datasets and verifies the result. A cast is irreversible and changes
`data_dtype` in `jnwb.inspect`; record it with the file.

## Validate the result

One call runs the whole stack and says whether the file is ready for DANDI:

```python
import jnwb

report = jnwb.validate_nwb("session.nwb")
print(report.summary())
report.ok            # no layer that ran failed
report.complete      # no layer skipped (a missing optional dependency skips its layer)
report.dandi_ready   # read, both pynwb schema layers and the dandi layer ran and passed
```

`pip install jnwb[validate]` adds the two optional layers' dependencies. The layers, in order:

| Layer | What it checks | Fails when |
|---|---|---|
| `read` | the file opens through `jnwb.read_nwb` | it cannot be read |
| `pynwb_schema` | `pynwb.validate` against the namespaces cached in the file | any schema error |
| `pynwb_core` | `pynwb.validate` against the core namespace of the installed pynwb, the newest schema that release knows | any schema error |
| `integrity` | ragged `<column>_index` arrays of `units` (`check_ragged_indices`) and electrode regions outside the electrodes table | `check_ragged_indices` reports a column not `ok`, or a region leaves the table |
| `nwbinspector` | NWB Inspector best-practice checks | a CRITICAL or ERROR finding; best-practice findings are counted as warnings |
| `dandi` | `dandi validate` through its Python API | an ERROR or CRITICAL result; `DANDI.NO_DANDISET_FOUND` is ignored by default |

A skipped layer is never a pass: `dandi_ready` is False unless the `dandi` layer ran.

## Keep repaired outputs frozen

After a repair, mark the file read-only and record a manifest: path, size, SHA-256, the check
report, the tool versions and the original file. A later job then verifies by hash instead of
re-deriving, and a changed hash is evidence that someone wrote to a frozen file. A fix verified
on one scratch file does not repair the files already produced, so list which existing outputs
still carry the defect before calling the problem closed.
