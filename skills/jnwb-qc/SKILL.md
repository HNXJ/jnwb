---
name: jnwb-qc
description: Quality control of unit and electrode tables and of results -- table audits, unit-quality plots for inspection, and the record of what ran, on what inputs, with which parameters.
---

# `jnwb-qc` — Table Audits, Unit-Quality Plots & Result Records

## 1. Trigger
Checking a session's unit and electrode tables before analysis, drawing unit-quality plots to
inspect a sorting, or recording and checking what produced a result: the jnwb that ran, its
parameters and seed, and the inputs the result came from. Reading the tables routes to
`jnwb-nwb-data`; publication figures route to `jnwb-figures`.

## 2. Routing

### Table audits

- `jnwb.audit_units(units_df, *, quality_threshold=1.0, snr_threshold=1.0, stable_labels=("good",))` and `jnwb.audit_electrodes(elec_df, units_df=None)`: Spike-time coverage and quality summaries, and electrode configuration with unit-to-electrode mapping coverage. Run both before trusting a session's tables. `good_count` uses the cut-offs, or `stable_labels` when quality is text, matched case-insensitively with whitespace kept and narrower here than in `enrich_units_dataframe`; a one-value standard deviation is NaN, which `json.dumps` writes as non-strict JSON; a NaN or infinite cut-off, or a column it reads that occurs twice, raises `ValueError`.

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
5. **Outcomes**: compose and execute when the tables, or a result's inputs and parameters, are
   at hand; request the provenance and lineage a `Result` refuses to be built without; report
   failure for a version claim that does not match execution; decline a verdict on correctness
   drawn from a record or an audit count.

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
- Plots: `tests/test_visual_qc.py`. Each plot is rendered at its final size and inspected.

## 6. Documentation
- [`docs/02_paths_addressing_metadata.md`](../../docs/02_paths_addressing_metadata.md)
- [`docs/09_decoding_and_visual_qc.md`](../../docs/09_decoding_and_visual_qc.md)
- [`docs/architecture.md`](../../docs/architecture.md)
- [`docs/api.md`](../../docs/api.md)
