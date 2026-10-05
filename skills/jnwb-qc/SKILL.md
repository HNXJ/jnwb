---
name: jnwb-qc
description: Quality control of unit and electrode tables and of results -- unit-quality measures and classes, table audits, unit-quality plots for inspection, and the record of what ran, on what inputs, with which parameters.
---

# `jnwb-qc` — Table Audits, Unit-Quality Plots & Result Records

## 1. Trigger
Measuring or classifying unit quality, checking a session's unit and electrode tables before
analysis, drawing unit-quality plots to inspect a sorting, or recording and checking what produced a result: the jnwb that ran, its
parameters and seed, and the inputs the result came from. Reading the tables routes to
`jnwb-nwb-data`; publication figures route to `jnwb-figures`.

## 2. Routing

### Table audits

- `jnwb.audit_units(units_df, *, quality_threshold=1.0, snr_threshold=1.0, stable_labels=("good",))` and `jnwb.audit_electrodes(elec_df, units_df=None)`: Spike-time coverage and quality summaries, and electrode configuration with unit-to-electrode mapping coverage. Run both before trusting a session's tables. `good_count` uses the cut-offs, or `stable_labels` when quality is text, matched case-insensitively with whitespace kept and narrower here than in `enrich_units_dataframe`; a one-value standard deviation is NaN, which `json.dumps` writes as non-strict JSON; a NaN or infinite cut-off, or a column it reads that occurs twice, raises `ValueError`.

### Unit-quality measures

Each measure reads one unit and keeps or rejects none; `docs/06_spikes_psth_and_onset_dynamics.md` section 5 defines them.

- `jnwb.waveform_features(waveform, fs)`: Peak channel, amplitude, trough-to-peak duration in ms, peak-trough ratio and polarity of a mean waveform `(n_channels, n_samples)`. `fs` in Hz is required: request it when the file does not give it.
- `jnwb.waveform_snr(spike_waveforms)`: SNR of one unit on one channel from its `(n_spikes, n_samples)` waveforms; NaN for one spike or identical spikes.
- `jnwb.waveform_flatness(waveform, *, threshold)` and `jnwb.spatial_derivative_sharpness(waveform, channel_positions, *, threshold)`: Flat and sharp flags against a `threshold` the caller gives; neither has a default or a published value, so state it with every flag. The sharpness needs two or more channels and their positions: request the geometry when the waveform has one channel or no positions.
- `jnwb.presence_ratio(spike_times, blocks)`: Fraction of the caller's `[start, stop)` blocks, in seconds, that hold a spike.
- `jnwb.isi_cv(spike_times)`: Coefficient of variation of the intervals; NaN under three spikes.
- `jnwb.refractory_contamination(spike_times, *, duration_s, refractory_ms, censored_ms)`: Contaminating fraction after Hill et al. (2011). The duration and both periods are required: request them. `contamination` is NaN, with a `reason`, for an empty train, a zero duration or an equation with no real root.

### Unit-quality classes and tiers

- `jnwb.classify_unit_quality(units_df, thresholds=None)`: Flags each unit whose metric is below its threshold; `quality_class` is `'Good'`, `'Fair'`, `'Poor'` (a `quality` or `snr` failure) or `'Unknown'` (a metric missing, not a number, or absent from the frame), and `is_valid` is True only with no flag. `thresholds=None` uses `{'quality': 1.0, 'snr': 1.0, 'firing_rate': 0.1}`, a convention with no cited source, and so marks every unit of a frame without `firing_rate` `'Unknown'`. Empty `thresholds`, a NaN or infinite threshold, or a threshold column that occurs twice raises `ValueError`.
- `jnwb.enrich_units_dataframe(units_df, electrodes_df, *, stable_threshold=1.0, stable_labels=("good", "sua", "single", "stable", "clean"))`: Writes the geometric depth class ('Deep' / 'Superficial' / 'Unknown') to `depth_class`; no `layer` column is written, so read `depth_class`. `get_all_units_metadata` emits it the same way. `is_stable` (pandas `"boolean"` dtype) is `quality >= stable_threshold` for numeric quality and membership in `stable_labels` for text labels (the signature's values are a convention with no cited source; a bare-string `stable_labels` raises `TypeError`; an empty one, a NaN or infinite `stable_threshold`, or a column it reads that occurs twice raises `ValueError`), `<NA>` for a unit with no usable or an infinite `quality`, and absent when no unit has one; `filter_quality=True` excludes `<NA>` units.
- `jnwb.assign_quality_tier(quality, trial_presence_fraction, snr, presence_threshold=0.98, snr_threshold=0.5, *, stable_threshold=1.0, stable_labels=("good", "sua", "single", "stable", "clean"))`: Tiers a unit `'mua'` / `'stable'` / `'unstable'` / `'unknown'` from quality, trial presence and SNR, reading quality by the `is_stable` rule of `enrich_units_dataframe`. A candidate (quality at or above `stable_threshold`, or a label in `stable_labels`) is `'stable'` only when presence and SNR both strictly exceed their thresholds, and `'unstable'` otherwise, including a missing presence or SNR. A non-candidate is `'mua'` only when declared so, as code 0 or the label `'mua'`; any other value (missing, infinite, -1, 0.5, `'noise'`, `'unsorted'`, a boolean, a date or a duration) is `'unknown'`. Presence and SNR are Series aligned to `quality` by unit label in any order, extra labels ignored, except when `quality` has the index `0..n-1`, which pandas gives a filter followed by `reset_index`, `head()` and `iloc[:k]` alike; those labels may be positions rather than unit labels, so aligning could pair the wrong units, and it raises: pass presence and SNR selected the same way as `quality`. They may also be arrays of its length read by position; a label of `quality` missing from them, a repeated label, a scalar, or a masked array with a masked entry raises `ValueError`, as does a NaN or infinite cut-off or an empty `stable_labels`. State the thresholds wherever the tier is reported; they are a choice, not a property of the unit.
- `jnwb.get_snr_analysis(units_df, snr_threshold=1.0, detail=False)`: SNR distribution and quality breakdown across a units table.

### Unit-quality plots

- `jnwb.visual_qc`: Submodule of unit-quality plots -- waveforms, quality distributions, noise against signal, and quality compared across sessions (import `jnwb.visual_qc`).

### Result records

- `jnwb.Result(question, statistics, provenance, lineage)`: An immutable analysis output that
  carries its question, provenance and lineage; it cannot be built without all four.
  `to_dict()` returns a plain nested `dict` and converts no value, so `json.dumps` of NumPy
  statistics needs a hook such as `lambda o: o.tolist()`.
- `jnwb.Provenance(software_version, backend, timestamp, random_seed, git_commit, parameters, environment)`:
  What ran. `jnwb_version` and `jnwb_path` are read from the executing package and cannot be
  passed; `software_version` is the caller's claim, and `version_claim_matches_execution` says
  whether the two agree.
- `jnwb.Lineage(source_type, source_id, parents, operation)`: Where an output came from: its
  source, the identifiers of its parents and the operation that made it.

## 3. Invariants & Safeguards
1. **An audit counts; it does not certify**: the audits count and summarize columns under the
   cut-offs the caller passes. State the cut-offs wherever a count is reported.
2. **An absent column is unaudited**: a summary returned as `{}` means the column was not in
   the table. Report it as not audited, never as no problem found.
3. **What ran is observed, not claimed**: report `jnwb_version` and `jnwb_path` as the
   implementation that ran. A record whose `version_claim_matches_execution` is False names a
   version that did not run, and that is reported as a failure, not corrected by hand.
4. **A record does not judge its contents**: provenance and lineage say where a number came
   from, not that it is correct. No field or method of `Result`, `Provenance` or `Lineage`
   holds a verdict, and a request to call a result correct, or a table valid, from its record
   or an audit count is declined.
5. **Sorter labels are an input, never ground truth**: a sorter's label or quality column is a
   value to screen against. No measure here, and no agreement with a label, shows that a unit
   is a single neuron, and a request to call a unit a single neuron from quality measures alone
   is declined. A measure or class that the input cannot support (NaN, `'Unknown'`) is reported
   as not estimable, never as a plausible number. State every cut-off with the class or flag
   it produced.
6. **Outcomes**: compose and execute when the tables, or a result's inputs and parameters, are
   at hand; request the provenance and lineage a `Result` refuses to be built without; report
   failure for a version claim that does not match execution; decline a verdict on correctness
   drawn from a record or an audit count. For unit quality: execute the measures on the
   waveforms, spike times and cut-offs at hand; request the waveforms, `fs` or geometry a
   measure lacks; report a measure or class the input cannot support as not estimable;
   decline "this unit is a single neuron" from quality measures alone.

## 4. Minimal Workflow
```python
# Input: deterministic array.
import jnwb
import numpy as np
import pandas as pd

units = pd.DataFrame({
    "unit_id": [0, 1, 2],
    "spike_times": [np.array([0.1, 0.5]), np.array([]), np.array([0.2])],
    "quality": [1.0, 0.5, 2.0],
    "snr": [3.0, 0.8, 1.5],
})
cutoffs = {"quality_threshold": 1.0, "snr_threshold": 1.0}  # state them with every count
audit = jnwb.audit_units(units, **cutoffs)
question = jnwb.Question(hypothesis="units pass the stated cut-offs", signals=["spike_times"],
                         contrast="none", inference_unit="unit")
record = jnwb.Result(
    question=question,
    statistics={"good_count": audit["quality_distribution"]["good_count"]},
    provenance=jnwb.Provenance(software_version=jnwb.__version__, backend="numpy",
                               parameters=cutoffs),
    lineage=jnwb.Lineage(source_type="units_table", source_id="example", operation="audit_units"),
)
assert record.provenance.version_claim_matches_execution
```

## 5. Verification
- Audit counts and refusals: `tests/test_metadata.py`.
- Record fields and the observed version: `tests/test_ontology.py`.
- Unit-quality measures: `tests/test_unit_quality.py`; classes, tiers and SNR: `tests/test_metadata.py`.
- Plots: `tests/test_visual_qc.py`. Each plot is rendered at its final size and inspected.

## 6. Documentation
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
- [`docs/06_spikes_psth_and_onset_dynamics.md`](../../docs/06_spikes_psth_and_onset_dynamics.md)
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
- [`docs/architecture.md`](../../docs/architecture.md)
- [`docs/api.md`](../../docs/api.md)
