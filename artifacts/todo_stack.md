
# 0.1.8

- CI full-test environment lacks documentation dependencies required by `test_mkdocs_strict_build`. Repair CI install command to `pip install -e ".[test,docs]"`, verify test suite dependencies, add deterministic workflow-policy test preventing recurrence, and re-verify full suite, gates, docs, release gate, and remote CI.

# Before 1.0

- Replace example-based estimator coverage with analytic/property-based tests.
- PSTH SEM policy for `N=1` trials (zero vs NaN) if statistical contract tightened.
- Processing-module discovery generalization beyond LFP if corpus requires it.

# Unversioned

- File omission-side expert-feedback items in the omission repository.
