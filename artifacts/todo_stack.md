# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by
dependency and risk (correctness and harness first).

Completeness means no known material defect under the declared jnwb goals — including the
smallest missing generic primitives justified by evidence, not breadth of method or a large
new subsystem. **100/100** is awarded only after a second independent zero-based audit finds
no known material defect; an empty stack alone is insufficient.

# 0.1.7

## Optional follow-up (non-blocking)

- Generalize subject IDs in `compression.py` / `addressing.py` receipts
  (`artifacts/source_neutrality_scan_0.1.7.md` inventory).
- `docs/04_spectral_analysis_and_tfr.md` and `docs/index.md`: add `normalize=False` or
  `baseline=` to `band_power` examples for consistency with the new contract.

# Before 1.0

- **Replace example-based estimator coverage** with analytic, property-based or composition
  tests. The suite is broad and adversarial already; this is the remaining estimator-coverage
  gap.

# Unversioned

- File the omission-side issue for items 1, 2, 5 and 6 of the expert feedback register
  (jnwb issue #4) in the omission repository.
- Four more notebooks under `examples/notebooks/` (WP3 planned five, one exists).
  `tests/test_notebooks.py` picks up a new one with no test change.
