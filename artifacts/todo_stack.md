# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by
dependency and risk (correctness and harness first).

Completeness means no known material defect under the declared jnwb goals — including the
smallest missing generic primitives justified by evidence, not breadth of method or a large
new subsystem. **100/100** is awarded only after a second independent zero-based audit finds
no known material defect; an empty stack alone is insufficient.

Evidence: `artifacts/independent_audit_0.1.7.md` @ `2c69640`.

# 0.1.7

## Scientific/numerical semantics (independent audit)

- `StatisticalAnalysis.permutation_test` → `(1+k)/(B+1)` Monte Carlo p-value → regression test
  with fixed RNG.
- `shuffle_r2_ci` → same +1 correction → test perfect-rank floor `1/(n_shuffle+1)`.
- `compare_groups(paired=True)` → raise on length mismatch (no silent independent fallback) →
  test mismatch raises; equal lengths still paired.
- `cross_modal_comparison` → explicit axis/shape contract; reject ambiguous layouts → test
  canonical passes, permuted layout raises.
- `spike_mutual_information` → bin grid must match `bin_spikes` → test shared window/bin
  agreement.
- `granger(order="auto")` → unify IC with `select_optimal_lag` → test equality on fixed series.
- `granger_spectral` → per-band surrogate p-values, not one shared p → test band-specific
  null.
- **`jrsa(metric="granger"|"transfer_entropy")` identity** → Hamm decision: delegate to
  `connectivity`, rename metrics, or remove → discriminating test after choice.
- `band_power(normalize=True)` → require `baseline` or raise → test raises without baseline.
- `jrsa` permutation null → +1 correction; seed GPU permutation path → CPU/GPU parity test
  when CUDA available.
- `transfer_entropy(estimator="symbolic")` → `n_times` matches embedded length → test symbolic
  path metadata.

## Documentation/usability (independent audit)

- `docs/quickstart.md` ↔ `examples/quickstart_jnwb.py` panel parity (script + figure are
  authority) → adversarial fixture: panel API strings match.
- `docs/10_extending_jnwb_and_verification.md` → remove phantom test references; neutralize
  `omission/` facade example → `rg test_skill_tree_consolidation docs/` empty;
  `rg "omission" docs/` empty.
- Merge or demote `docs/10` vs `docs/11` → single extending entry point; `mkdocs build --strict`.

## Tests/gates (independent audit)

- `tests/test_jnwb_core.py` → replace bare `except Exception: pass` with explicit
  `pytest.raises` → introduced bug fails test.
- `harness_gate.py` `EPHEMERAL_ROOT_DIRS` → include `_audit_dist`, `_audit_dist2` → Gate 4
  passes with audit wheel dirs present.
- `harness_gate.py` module header → document gates 1–12 matching `run_full_preflight`.

## Boundary/provenance (independent audit)

- Tripwire #1: remove hardcoded empirical values from `jnwb/compression.py` and
  `jnwb/onset_fitting.py` user-facing docstrings → move receipts to `artifacts/` →
  `rg "2\\.8x|rho=-0\\.98" jnwb/` empty.
- Optional follow-up: generalize subject IDs in `compression.py` / `addressing.py` receipts
  (`artifacts/source_neutrality_scan_0.1.7.md` inventory).

## API consistency (independent audit — after Hamm decision on jrsa)

- **`granger` vs `granger_causality`** → Hamm decision: deprecate legacy dict API or document
  permanent dual surface → connectivity tests unchanged until decision.

## Documentation consistency gates (generator polish)

- `generate_api_md.py` → type constants as `constant`; correct module grouping for re-exports →
  regenerate `docs/api.md`; Gate 9 PASS.

# Before 1.0

- **Replace example-based estimator coverage** with analytic, property-based or composition
  tests. The suite is broad and adversarial already; this is the remaining estimator-coverage
  gap.

# Unversioned

- File the omission-side issue for items 1, 2, 5 and 6 of the expert feedback register
  (jnwb issue #4) in the omission repository.
- Four more notebooks under `examples/notebooks/` (WP3 planned five, one exists).
  `tests/test_notebooks.py` picks up a new one with no test change.
