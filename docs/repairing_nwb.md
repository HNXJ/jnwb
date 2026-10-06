# Repairing NWB files

A file that opens is not a file that is correct. This page covers the defects found while repairing
a batch of multi-probe spike-sorted NWB files, how to detect each, and what to check before and
after a repair. Statements are labeled **observed** (seen in the files repaired), **derived**
(follows from the NWB layout) or **inferred** (a reading of the observations that was not
confirmed against the writer's source for every file).

## Ragged index offset

A ragged column such as `spike_times` or `waveform_mean` is a flat data array plus
`<column>_index`, whose entry `i` is the exclusive end offset of row `i`. **Derived:** a correct
index is non-decreasing, ends at the first-axis length of the data, and has a dtype that holds
that length.

**Observed:** one multi-probe writer appended each probe after the first with the index offset by
the first element of the existing index instead of its last (the running total). The flat data
were complete and in row order; only the index was wrong, so rows of later probes sliced into
earlier probes' data. Two of three ragged columns were affected; the third was written correctly,
which is what exposed it.

| Check | Flag on each column's check (`report.columns`) |
|---|---|
| Non-decreasing | `monotonic` |
| Last element equals `len(data)` | `ends_at_data_len` |
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

`check_ragged_indices` writes nothing. Without `probe_starts` or `probe_column` the defect test
reports `"not_tested"`. A file that fails both the defect test and the correct-index test is
`"inconsistent"` and is damaged in some other way.

`repair_ragged_index` is a dry run unless `dry_run=False` is passed with a `backup_path`. It
refuses to write unless the old index is exactly the defect's formula, the corrected index ends at
`len(data)` and fits the dtype; it keeps dtype and shape and touches no other dataset. It returns a `RaggedIndexRepair` (old and new index, rows changed, whether it wrote) and raises
`RaggedIndexRepairRefused` otherwise. Run it on a copy, then re-run the check on the result. The refusal is the useful behavior: a file that is wrong in a different way stays unchanged and
reported.

**Also check:** a ragged column whose data and `_index` exist but whose name is missing from the
table's `colnames` attribute is hidden by pynwb (`units["spike_times"]` raises `KeyError`).
`RaggedIndexReport.unlisted_ragged_columns` lists them; the check does not fix the attribute.

**Index dtype overflow.** **Derived:** an `int32` index holds offsets to 2,147,483,647. A long
recording with dense spiking, or a waveform table with one row per channel per unit, can exceed
it, and a writer that wraps silently produces a decreasing index. `length_fits` and `monotonic`
catch both; the fix is rewriting the file with a wider integer type, not editing the index.

## Which channel a unit belongs to

Three quantities are easy to confuse.

| Quantity | What it is |
|---|---|
| `peak_channel_id` | **Observed:** a raw channel id, global across probes. Subtract the probe's first channel id to get a probe-local row |
| `waveform_mean` rows | **Observed:** one row per channel of the unit's own probe, in probe-local order |
| Sorter template peak | The channel where the sorter's template is largest |

- **Observed:** applying the probe's `channel_map` to the `waveform_mean` rows agreed with
  `peak_channel_id` worse than leaving the rows as stored. Do not reorder them.
- **Observed:** the channel where the sorter's mean waveform is largest often differs from the
  template's peak channel. **Inferred:** the mean waveform averages spikes whose noise and drift
  differ from the template fit.
- Consequence: `argmax(waveform_mean)` is not the unit's channel. Take the channel from
  `peak_channel_id` and use the waveform for shape measures. The fraction of units whose maximum
  row equals the probe-local `peak_channel_id` is a plausibility check on an index repair, never
  a per-unit label.

## Units schema across sessions

**Derived:** pooling units from several files needs the same columns, dtypes and index layout.
Before pooling, compare the column set and the `<column>_index` dtype of every file with
`check_ragged_indices(...).columns` and `jnwb.inspect`. A column that is ragged in one file and
plain in another, or an index stored as `int32` in one and `int64` in another, is a schema
difference that a per-file read does not show.

## Continuous data dtype

**Derived:** `float64` takes twice the bytes of `float32`. **Observed:** LFP and multiunit
envelopes derived from 16-bit integer recordings were stored as `float64` by one pipeline and were
moved to `float32` once the filters were confirmed to run stably in it.
`jnwb.compress_fp32(src, select=[...])` casts exactly the named datasets and verifies the result.
A cast is irreversible and changes `data_dtype` in `jnwb.inspect`; record it with the file.

## Validate the result

Run the stack in this order; each layer catches what the previous one cannot.

```bash
python -c "import pynwb; pynwb.NWBHDF5IO('session.nwb', 'r').read()"
nwbinspector session.nwb
dandi validate --ignore DANDI.NO_DANDISET_FOUND session.nwb
```

- The pynwb read proves the file opens, not that an index is right.
- `nwbinspector` reports best-practice violations; none concerns ragged-index values.
- `dandi validate` checks schema and DANDI requirements; without a Dandiset the
  `DANDI.NO_DANDISET_FOUND` finding is expected and ignored.
- `jnwb.check_ragged_indices` covers the index values the three tools above do not.

## Keep repaired outputs frozen

After a repair, mark the file read-only and record a manifest: path, size, SHA-256, the check
report, the tool versions and the backup path. A later job then verifies by hash instead of
re-deriving, and a changed hash is evidence that someone wrote to a frozen file. A fix verified
on one scratch file does not repair the files already produced, so list which existing outputs
still carry the defect before calling the problem closed.
