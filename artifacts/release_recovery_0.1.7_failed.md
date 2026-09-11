# Failed 0.1.7 release — preserved evidence

**Candidate SHA:** `803d6b88fa9c8db441ce173b282160639af556be`  
**Date:** 2026-09-11  
**Outcome:** GitHub Release published; PyPI **not** published (CI blocked build/publish).

## Promotion performed

| Step | Result |
|---|---|
| `main` fast-forward to `803d6b8` | Done |
| Tag `v0.1.7` pushed | Done |
| GitHub Release `v0.1.7` published | Done |
| PyPI `jnwb==0.1.7` | **Absent** (latest remained `0.1.6`) |

## CI failure receipt

**Workflow run:** https://github.com/HNXJ/jnwb/actions/runs/34606490580  
**Event:** `release` on tag `v0.1.7`  
**Head SHA:** `803d6b8`  
**Conclusion:** `failure` (all 4 test matrix jobs failed; build/publish skipped)

### Failure class 1 — statsmodels API compatibility

```
TypeError: grangercausalitytests() got an unexpected keyword argument 'verbose'
```

**Site:** `jnwb/jrsa.py:1321` in `_granger`  
**Tests:** `tests/test_independent_audit_semantics.py::TestJrsaMetricIdentity::test_granger_ssr_ftest_returns_f_statistic`  
**Platforms:** Ubuntu + Windows, Python 3.12 and 3.14

### Failure class 2 — `docs/api.md` generator drift

```
API_MD_DRIFT: docs/api.md does not match scripts/generate_api_md.py output
```

**Gates:** harness Gate 9, `tests/test_harness_adversarial_gates.py::TestDocumentationDriftGates::test_clean_tree_passes_both_gates`  
**Platforms:** All CI matrix jobs (clean `pip install ".[test]"` environments)

## Root-cause diagnosis (reproduced locally)

### Failure class 1 — statsmodels `verbose` removed in 0.15.0

- `pyproject.toml` allows `statsmodels>=0.13.0` with no upper bound.
- CI clean installs resolve **statsmodels 0.15.0**, which drops the `verbose` parameter from
  `grangercausalitytests`.
- Local dev at statsmodels 0.14.6 still accepts `verbose=False`; the defect was invisible
  to pre-tag verification on that resolver pin.

### Failure class 2 — `docs/api.md` non-deterministic across Python versions

- `scripts/generate_api_md.py` used `str(inspect.signature(...))` directly.
- Python **3.12** renders evaluated annotations as `Optional[List[str]]`.
- Python **3.14** renders the same annotations as `List[str] | None`.
- `docs/api.md` was generated on 3.14; CI matrix floor (3.12) failed Gate 9 drift checks.

**Fix direction:** statsmodels signature guard for `verbose`; canonical annotation renderer
in the API generator; regression gates + release_gate floor cross-check.

## Recovery policy

Delete-and-retag `v0.1.7` (no tag movement). Fix both failure classes, add regression gates, re-validate, then re-promote.
