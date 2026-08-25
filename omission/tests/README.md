# `tests/` — this project's pytest suite

**Purpose:** verification for `../jnwb_ext/` and `../scripts/` behavior, plus a few
doctrine-enforcement tests (frozen-boundary and retraction-guard tests) that fail loudly if a
past mistake recurs.

**Owns:** all `test_*.py` under this directory.

**Run it, don't trust a pass count written in prose** — counts in `README.md`/`PROJECT_STATE.md`
are a snapshot, not a guarantee; re-run before citing.

```bash
pytest omission/tests -q
```

**Notable enforcement tests:** `test_no_retracted_census_in_live_code.py` and
`test_labyrinth_validator.py` guard against a specific retracted 421/8597 (4.90%) synthetic
census figure re-entering live code — see `../context/09_conflicts_and_flagged_discrepancies.md`.
`test_quarantine_enforcement.py` guards the `historical/confounded/` and
`notebooks/historical/` quarantines. `tests/test_jnwb_frozen_boundary.py` (repo root `tests/`,
not here) guards the `jnwb/` layering direction.
