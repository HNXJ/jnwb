---
name: jnwb-qc
description: Quality control of unit and electrode tables and of results -- unit-quality measures and classes, WaveMAP waveform clustering, table audits, unit-quality plots for inspection, and the record of what ran, on what inputs, with which parameters.
---

# `jnwb-qc` — Table Audits, Unit-Quality Plots & Result Records

## 1. Trigger
Measuring or classifying unit quality, checking a session's unit and electrode tables before
analysis, drawing unit-quality plots to inspect a sorting, or recording and checking what produced a result: the jnwb that ran, its
parameters and seed, and the inputs the result came from. Reading the tables routes to
`jnwb-nwb-data`; publication figures route to `jnwb-figures`.

## 2. Routing

The "Table audits" routing rows live in [`references/table_audits.md`](references/table_audits.md).

The "Unit-quality measures" routing rows live in [`references/unit_quality_measures.md`](references/unit_quality_measures.md).

The "Waveform clustering (WaveMAP)" routing rows live in [`references/waveform_clustering.md`](references/waveform_clustering.md).

The "Unit-quality classes and tiers" routing rows live in [`references/unit_quality_classes_and_tiers.md`](references/unit_quality_classes_and_tiers.md).

The "Unit-quality plots" routing rows live in [`references/unit_quality_plots.md`](references/unit_quality_plots.md).

The "Result records" routing rows live in [`references/result_records.md`](references/result_records.md).

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
   as not estimable, never as a plausible number. The one exception is `classify_unit_quality`: a unit with a measured `quality` or `snr` failure is `'Poor'` even when another metric is undefined. State every cut-off with the class or flag
   it produced.
6. **A waveform cluster is not a cell type**: a WaveMAP cluster groups units by mean-waveform
   shape on one dataset, at one resolution and seed. Resample the units (`wavemap_resolution_sweep`; a
   new `rng` alone leaves the graph unchanged below 4096 units) and report how well the labels
   agree before naming a cluster; decline to call a cluster a cell
   type, or to equate clusters across datasets recorded or filtered differently, from shape
   alone.
7. **Outcomes**: compose and execute when the tables, or a result's inputs and parameters, are
   at hand; request the provenance and lineage a `Result` refuses to be built without; report
   failure for a version claim that does not match execution; decline a verdict on correctness
   drawn from a record or an audit count. For unit quality: execute the measures on the
   waveforms, spike times and cut-offs at hand; request the waveforms, `fs` or geometry a
   measure lacks; report a measure or class the input cannot support as not estimable;
   decline "this unit is a single neuron" from quality measures alone. For WaveMAP: execute
   on aligned, normalized waveforms with a stated resolution; request `fs`, or a resolution
   when none was chosen; decline a cell-type label from a cluster alone.

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
- [`docs/unit_quality_example.md`](../../docs/unit_quality_example.md), run from `examples/notebooks/unit_quality.ipynb`
- [`docs/architecture.md`](../../docs/architecture.md)
- [`docs/api.md`](../../docs/api.md)
