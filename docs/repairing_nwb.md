# Repairing NWB files

A file that opens is not a file that is correct. This page covers defects in multi-probe
spike-sorted NWB files that a read does not show, how to detect each, and what to check before
and after a repair.

## Ragged index offset

A ragged column such as `spike_times` or `waveform_mean` is a flat data array plus
`<column>_index`, whose entry `i` is the exclusive end offset of row `i`; row 0 starts at 0
(HDMF `VectorIndex`). A correct index is non-negative, non-decreasing, ends at the
first-axis length of the data, and its dtype holds that length. An empty index over empty
data is a valid empty table.

The defect comes from a writer that appends each probe after the first, offsetting
its index by the first element of the existing index, not its last (the running
total). The flat data are complete; only the index is wrong, so rows of later
probes slice into earlier probes' data.

![Index and data spans by row, correct and defective](assets/figures/fig35_ragged_index_defect.png#only-light)
![Index and data spans by row, correct and defective](assets/figures/fig35_ragged_index_defect.dark.png#only-dark)

Synthetic: nine made-up units on three probes, read by `jnwb.check_ragged_indices`. Each later probe's first row reads nothing.

| Check | Flag in `report.columns` |
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
the correct-index test is `"inconsistent"`, damaged in some other way.

`repair_ragged_index` is a dry run by default. It refuses unless the old index is exactly the
defect's formula and the corrected index fits the dtype, raising
`RaggedIndexRepairRefused`; [Errors](errors.md#repairing-a-ragged-index-raggedindexrepairrefused)
lists every message. To write, name a destination:

```python
r = jnwb.repair_ragged_index("session.nwb", "spike_times", probe_starts=[0, 40, 95],
                             dry_run=False, output_path="session_repaired.nwb")
```

The input is copied, only `<column>_index` of the copy is rewritten (same dtype and shape), and
the copy is re-read and checked before it moves into place, so `r.written` is True only for a
verified file. `in_place=True` with a `backup_path` replaces the input instead, by the same
verified copy and an atomic `os.replace`; the backup holds the old index. A new `output_path` is
claimed exclusively just before the move; a file that appears there meanwhile is refused. A
dry run writes nothing and ignores `backup_path`. A failure at any step
leaves the input byte-identical, so a file wrong in another way stays unchanged and reported.

**Also check:** a ragged column whose data and `_index` exist but whose name is missing from the
table's `colnames` attribute is hidden by pynwb (`units["spike_times"]` raises `KeyError`).
`RaggedIndexReport.unlisted_ragged_columns` lists them; it does not fix the attribute.

**Index dtype overflow.** An `int32` index holds offsets to 2,147,483,647. A long recording with
dense spiking, or a waveform table with one row per channel per unit, can exceed it, and a writer
that wraps silently produces a decreasing index. `length_fits` and `monotonic` catch both; the
fix is rewriting the file with a wider integer type, not editing the index.

## Waveform block ownership

A unit's `waveform_mean` block is sliced by `waveform_mean_index`, or, with no index, is
`waveform_mean[unit]`, shape `(units, samples, channels)`. Nothing ties the block to the
unit: blocks stored out of unit order read as another unit's through pynwb, silently. `check_waveform_blocks` compares each block's row amplitudes against the
unit's stored `amplitude`:

```python
import jnwb

report = jnwb.check_waveform_blocks("session.nwb", rtol=1e-6)
print(report.n_owned, report.n_unowned, report.n_unknown)
```

| Verdict | Meaning |
|---|---|
| `owned` | some row's peak-to-peak matches within tolerance |
| `unowned` | the block is complete and no row matches |
| `unknown` | the block is empty (dense: has no samples), or the amplitude is missing, NaN or infinite |

`rtol` is required because no tolerance suits every writer. `peak_channel_id` travels
with each verdict for the caller's join against the electrodes table; the check never
uses it. The check repairs and reassigns nothing:
a match is evidence, not proof, and `report.ok` holds only when every unit is owned.

When the median ratio of amplitude to largest block peak-to-peak, over units with a nonzero
amplitude and a finite, nonflat block, is 1000 or more, or 1/1000 or less, the check raises
`ValueError` for a unit mismatch (microvolts against volts, say) and judges no unit.

## Units schema across sessions

Pooling units from several files needs the same columns, dtypes and index layout.
Compare each file's column set and `<column>_index` dtype with
`check_ragged_indices(...).columns` and `jnwb.inspect`. A column that is ragged in one file and
plain in another, or an index stored as `int32` in one and `int64` in another, is a schema
difference a per-file read does not show.

## Continuous data dtype

`float64` takes twice the bytes of `float32`. `jnwb.compress_fp32(src, select=[...])` casts
exactly the named datasets and verifies the result. A cast is irreversible and changes
`data_dtype` in `jnwb.inspect`; record it with the file.

## Validate the result

One call runs every layer and says whether the file is ready for DANDI:

```python
import jnwb

report = jnwb.validate_nwb("session.nwb")
print(report.summary())
report.ok            # no layer that ran failed
report.complete      # no layer skipped (a missing optional dependency skips its layer)
report.dandi_ready   # read, both pynwb schema layers and the dandi layer ran and passed
```

`pip install jnwb[validate]` adds the optional layers' dependencies. The layers, in order:

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
report, tool versions and the original file. A later job verifies by hash instead of
re-deriving, and a changed hash is evidence that someone wrote to a frozen file. A fix verified
on one scratch file does not repair files already produced, so list which existing outputs
still carry the defect before calling the problem closed.
