# Your Own NWB File

Start here if the file came from somewhere else and you do not yet know what is in it.

The other tutorials write a synthetic recording and check it against values they already
know, which makes them good tests and poor first reads: copy one against your own file and
it fails inside the tutorial, on an identifier that was never yours. This one reads the
layout off [`jnwb.inspect`](../02_paths_addressing_metadata.md) and adapts to what it finds.

```bash
python examples/tutorials/00_your_own_file.py /path/to/recording.nwb
```

With no argument it writes a small stand-in with plain `pynwb` first, so the script runs
anywhere. The stand-in names its code column `stimulus` rather than `codes`, because that is
the situation the discovery step exists for.

## Four things the script does not assume

**Which interval table.** `jnwb` resolves `trials`, then a sole table, then refuses. On a
file with five interval tables the refusal names them all and asks for one:

```
jnwb will not guess between these tables: Several interval tables and none named 'trials':
['photodiode_1_detected_changes', 'reward_1_detected', 'test_synth_flash', 'test_synth_rf',
'test_synth_task']. Pass table=<name> explicitly.
```

Pass the table as the second argument. Choosing the first table in the list instead would
have aligned everything to detected photodiode changes and reported a PSTH of 0.00 Hz
without complaining.

**Which column holds the codes.** `codes` is a jnwb default, not an NWB requirement. The
script prefers it when present and otherwise takes the first non-structural column that has
sample values, then passes that name explicitly. Naming a column that does not exist raises
`ColumnNotFoundError` listing the columns that do.

**That spikes or a continuous channel exist at all.** Both alignment steps are guarded by
what `inspect` reported, because a file may carry neither.

**Where the continuous data lives, or that it has a sampling rate.** `inspect` returns two
lists, `acquisitions` and `processing_continuous`, and an `LFP` container usually lives in
the second. The script reads both. It also handles the values that can legitimately be
absent: `rate_hz` is `None` for a series stored with `timestamps` instead of a constant
rate, and `data_shape`, `layout` and `rate_hz` are all `None` for a container wrapping
several series that do not share one. Each case prints what is unknown and why that series
was not epoched, rather than a bare `None` or a traceback:

```
Acquisition lfp: shape [2000, 8], no constant rate (irregularly sampled), time_by_channel
lfp: no constant sampling rate, so not epoched here. Read its timestamps and resample if
you need a spectrum.
Layout discovered; no continuous series could be aligned, and the lines above say why for
each one.
```

The closing line reports what happened rather than what was hoped for. A script that says
"aligned" after aligning nothing is how a blank figure gets believed.

## Source

The page below is included from the tutorial script; edit the script, not this block.

```python
--8<-- "examples/tutorials/00_your_own_file.py"
```
