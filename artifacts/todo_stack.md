# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by
dependency and risk (correctness and harness first).

Completeness means no known material defect under the declared jnwb goals — including the
smallest missing generic primitives justified by evidence, not breadth of method or a large
new subsystem. **100/100** is awarded only after a second independent zero-based audit finds
no known material defect; an empty stack alone is insufficient.

# 0.1.7

## Documentation consistency gates (0.1.7 deliverable)

- Optional: move residual implementation receipts in `compression.py` / `onset_fitting.py` to an
  internal note (`artifacts/source_neutrality_scan_0.1.7.md` inventories them).

## Second-audit placeholder (do not delete until 0.1.7 seal)

- Fresh zero-based audit from **current** repository state; partitions do **not** use this
  stack as checklist: (1) scientific/numerical semantics, (2) API/code/doc consistency,
  (3) README/docs/nav usability, (4) tests/gates/failure behavior, (5) packaging/install/release,
  (6) boundary/provenance/no-trace, (7) architecture/maintenance, **(8) harness/skills
  authority (`AGENTS.md`, `CLAUDE.md`, skills, gates, workflows)**. Reconcile against live
  code; material findings re-enter 0.1.7; 100/100 only when second audit has no known
  material defect.

# Before 1.0

- **Replace example-based estimator coverage** with analytic, property-based or composition
  tests. The suite is broad and adversarial already; this is the remaining estimator-coverage
  gap.

# Unversioned

- File the omission-side issue for items 1, 2, 5 and 6 of the expert feedback register
  (jnwb issue #4) in the omission repository.
- Four more notebooks under `examples/notebooks/` (WP3 planned five, one exists).
  `tests/test_notebooks.py` picks up a new one with no test change.
