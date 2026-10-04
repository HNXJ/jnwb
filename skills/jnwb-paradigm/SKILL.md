---
name: jnwb-paradigm
description: Experiment structure from NWB interval tables -- event rows and onsets, epochs aligned to events, recording cycles, and condition meaning taken from documented metadata.
---

# `jnwb-paradigm` — Experiment Structure, Timing & Conditions

## 1. Trigger
Choosing an interval table, reading event codes and onsets, cutting epochs around events,
grouping trials by recording structure, or deciding what a condition code means.

## 2. Routing

### Event rows

- `jnwb.resolve_interval_table(path_or_nwb, table=None)` → table name using `trials` → sole table →
  `AmbiguousIntervalTableError` when several tables and `table` omitted.
- `jnwb.events(path_or_nwb, table=None, code_column="codes", onset_column="start_time")` →
  `EventTable` with all rows from one interval table. Onsets in **seconds**.
- `jnwb.EventTable(table, path, code_column, onset_column, time_unit, codes, onsets, stop_times)`:
  The record `events` builds; construct one by hand only to test code that reads it. `codes`
  holds the column's stored values in row order, and no field carries a name for any of them.

### Epochs

- `jnwb.epoch_continuous(data, onsets, *, win_s, fs)` → `(epochs, time_axis_s)` extracting fixed-window
  epochs from continuous signals aligned to event onsets.
- `jnwb.EpochCollection(aligned_dataset, condition, phase, correct_only, epochs_df)`: An immutable
  set of trials filtered from an `AlignedDataset`, keeping each trial's identity. `condition` is
  the label the caller's documented mapping gives; jnwb assigns none.

### Recording structure

- `jnwb.detect_trial_cycles(epochs_df, gap_factor=10.0)` and `jnwb.assign_subblock_quartiles(epochs_df, n_quantiles=4)`: Recording-structure labels -- cycle boundaries from a gap threshold, and temporal quantile buckets by `start_time` order. Both are grouping variables for `permute_labels` and `cluster_permutation_test`, not results.

## 3. Invariants & Safeguards
1. **Condition meaning, strongest evidence first**: (a) metadata the file carries: the code
   column's `description`, a lookup table stored with the session, the protocol text; (b) a
   mapping the caller supplies with its source; (c) structural inference last: row order,
   cycles, code frequencies. Structure groups trials; it does not name them. jnwb reads codes
   as opaque values at every step.
2. **An undocumented code is reported, never named**: a code that neither the file nor the
   caller documents is reported as its stored value, with its count and onsets. Its value,
   frequency or position in the session is no evidence for a name.
3. **One clock**: onsets are session seconds. Subtract the series' `starting_time` before
   epoching, as `jnwb-nwb-data` states under "Aligning events to a series". When most epochs
   are all-NaN with a warning, the onsets are on another clock, and that is reported as a
   failure, not analyzed.
4. **Outcomes**: compose and execute when the table, code column and series are known;
   request `table=` or `code_column=` when a call refuses and names the tables or columns that exist;
   report failure for all-NaN epochs; decline to name an undocumented code.

## 4. Minimal Workflow
```python
# Input: calibration fixture.
import jnwb
import pandas as pd

# session.nwb here is a small synthetic file of known contents; pass your own path.
name = jnwb.resolve_interval_table("session.nwb", table="test_synth_task")
rows = jnwb.events("session.nwb", table=name)
# rows.codes are stored values: name one only where the file or your protocol documents it.
signal, rate_hz = jnwb.acquisition_channel("session.nwb", name="probe_0_lfp", channel=0)
epochs, time_axis_s = jnwb.epoch_continuous(signal, rows.onsets, win_s=(-0.1, 0.2), fs=rate_hz)
cycles = jnwb.detect_trial_cycles(pd.DataFrame({"start_time": rows.onsets}))
```

## 5. Verification
- Event acceptance matrix: `tests/test_nwb_events.py`.
- Each epoch's sample at `time_axis_s == 0` comes from the sample nearest its onset; check it on
  a signal whose value is its own time.

## 6. Documentation
- [Common mistakes: assuming a schema the file does not have](../../docs/common_mistakes.md)
- [Tutorial: NWB Basics](../../docs/tutorials/01_nwb_basics.md)
- [`docs/errors.md`](../../docs/errors.md)
- [`docs/07_statistical_inference_and_nulls.md`](../../docs/07_statistical_inference_and_nulls.md)
