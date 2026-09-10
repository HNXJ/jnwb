# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by the
path a 2026-09-10 deep review of the published 0.1.5 sdist recommended (91/100, no defect
requiring withdrawal).

New analysis methods are not a priority until 0.1.6 and 0.1.7 are closed. Completeness
means small sufficient primitives, explicit semantics, strong composition, and no hidden
study choices — not breadth of method.

# 0.1.7

- **Remove project provenance from generic source.** 83 occurrences of `omission` across
  17 modules; densest `statistics.py` 12, `__init__.py` 12, `metadata.py` 9,
  `spectral.py` 7, `artifact_repair.py` 7. Semantics-preserving: no numerical change.
- Delete promotion provenance ("promoted 2026-08-23 from `omission.jnwb_ext.spectral`") —
  git holds it, and the module path it names is unresolvable from here.
- Delete claims about another repository's contents: `jnwb/spectral.py:40` asserts what
  `omission.jnwb_ext.connectivity` re-exports, which jnwb cannot verify and which goes
  stale silently.
- Rewrite the intrusive cases so no downstream knowledge is needed:
  `jnwb/artifact_repair.py` (defaults "tuned on the omission corpus", historical receipts,
  downstream figure paths), `jnwb/statistics.py:888` (`"FR during omission > FR during
  stimulus in FEF O+ units"` as the worked example), `jnwb/trajectory.py:65` and
  `jnwb/decoding.py:12` (both explain themselves through `OmissionSession`'s API). Where a
  corpus genuinely sets a default, say so without requiring the reader to know it.
- Measure the residue with a **non-blocking** source-neutrality audit. Gate 12 skips
  comments and docstrings by design and must stay that way — so `Gate 12 PASS` is not the
  claim "project-neutral", and must not be reported as it.
- **Audit the 31 `except Exception` sites** in `jnwb/` (`spectral.py` 7, `jrsa.py` 5,
  `analyzers.py` 3, then `metadata.py`, `mcp_server/nwb_tools.py`, `addressing.py`,
  `_backend.py` at 2). Classify each: required boundary, narrowable, or dangerous. A broad
  catch is correct at optional-backend, controlled-fallback and file-parsing boundaries,
  and dangerous when it turns a defect into a plausible result — how the
  `cross_area_coherence` bug survived. Every fallback preserves estimator identity or
  reports that it could not.
- **Add a strict path to `filter_by_criteria`** (`jnwb/metadata.py`). An unknown criterion
  is ignored, so `{"aera": "V1"}` returns the table unfiltered: a misspelled selection
  silently yields a *larger* dataset. Add `unknown="raise"`, keep `"ignore"` as the default
  for compatibility. `tests/test_metadata.py:118` pins the current behaviour as
  intentional; flipping the default needs a declared breaking release.

# Before 1.0

- **Audit `jnwb.__all__`,** 111 symbols. Per symbol: a primitive a user should call
  directly, or an implementation component exported because it was convenient? Do not
  shrink the number for its own sake — each export is compatibility, docs, namespace and
  import cost carried indefinitely.
- **Replace example-based estimator coverage** with analytic, property-based or
  composition tests. The suite is broad and adversarial already
  (`tests/test_harness_adversarial_gates.py` tests the gates themselves); this is the
  remaining gap.

# Unversioned

- File the omission-side issue for items 1, 2, 5 and 6 of the expert feedback register
  (jnwb issue #4) in the omission repository. Items 3 and 4 were checked against 0.1.5;
  3 became the HSIC fix.
- Four more notebooks under `examples/notebooks/` (WP3 planned five, one exists).
  `tests/test_notebooks.py` picks up a new one with no test change.
