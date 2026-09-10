# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by
dependency and risk (correctness and harness first).

Completeness means no known material defect under the declared jnwb goals — including the
smallest missing generic primitives justified by evidence, not breadth of method or a large
new subsystem. **100/100** is awarded only after a second independent zero-based audit finds
no known material defect; an empty stack alone is insufficient.

# 0.1.7

## User-facing semantics / failure behavior

## Public API and active-module classification (required for 0.1.7 100/100)

- **Audit `jnwb.__all__` (111 symbols) and every active non-private module** (`bilinear.py`,
  `nam.py`, `gpu_pca.py`, `nwb_io.py`, `_lazy_exports.py`, …) → per symbol/module classify
  `{public primitive, intentional module-internal, optional/experimental, dead/parked}`; do
  not export because code exists → align `__all__`, docs, tests, naming (`_` prefix where
  compatibility permits); moved from pre-1.0 because 100/100 requires resolved surface →
  written disposition table; `docs/api.md` and `python scripts/harness_gate.py` Gate 5/10
  agree with runtime exports.

## Skills parity (all eight skills)

Existing `tests/test_skills_validation.py` proves `hasattr` only — insufficient.

- `skills/jnwb-connectivity/SKILL.md` → `directed_connectivity(signals, …)` and
  `directed_network(adj_matrix, …)` wrong; runtime is pairwise `X,Y` and
  `directed_network(signals, …)` → align routing matrix with `jnwb.connectivity`.
- `skills/jnwb-nwb-data/SKILL.md` → `compress_fp32(arr, bits=16)` false; runtime is NWB path
  I/O `compress_fp32(src, dst=None, *, …)`; bit-precision safeguard not current API → align
  with `jnwb.compression.compress_fp32`.
- `skills/jnwb-figures/SKILL.md` → `setup_vector_graphics(font_family=…)` (no args at
  runtime); `apply_tight_auto_axis(x_margin=…)` vs `x_span`; `resample_onsets(onsets,
  min_interval_s)` vs `target_n`/`random_state` → align every routing row with
  `inspect.signature` and semantics.
- `skills/jnwb-population/SKILL.md` → `assign_outer_folds(groups, n_folds)` false; runtime
  requires trial DataFrame + `analysis_cols`/`group_col` → align CV grouping contract.
- **All eight skills** (`jnwb`, `jnwb-nwb-data`, `jnwb-spiking`, `jnwb-lfp-spectral`,
  `jnwb-statistics`, `jnwb-population`, `jnwb-connectivity`, `jnwb-figures`) → audit every
  routing row against `inspect.signature` and semantics, not symbol existence only →
  strengthen `tests/test_skills_validation.py` with signature probes or executable
  representative calls per routing entry where practical → full skill suite passes.

## Executable documentation defects

- `docs/quickstart.md` workflow table → wrong modules (`jnwb.artifacts`, `jnwb.directed`,
  `jnwb.stats`, misplaced `compute_psd`, `raster_psth`/`fit_exponential_onset`) → real module
  paths or top-level exports → `mkdocs build --strict`; import checks.
- `docs/quickstart.md` §3 PSI → `freq_range=`, `psi.score`/`psi.p_value` invalid →
  `bands=`, `psi.x_to_y`, `psi.p_x_to_y` → execute snippet.
- `docs/quickstart.md` §6 jRSA → `n_permutations=` ignored; `jrsa_res.p_value` invalid →
  `permutations=`, `jrsa_res.p` → execute snippet; `parameters['permutations']==100`.
- `examples/quickstart_jnwb.py:74` `band_power` positional args → `fs=`/`freq_range=` →
  `python examples/quickstart_jnwb.py` exits 0.
- `docs/07_statistical_inference_and_nulls.md` §4–5 → wrong
  `build_permutation_plan`/`detect_trial_cycles`/`assign_subblock_quartiles` signatures →
  match runtime → extend `tests/test_docs_smoke.py`.
- `docs/08_directed_connectivity_and_information.md` §2–§6 → wrong `DirectedResult` fields,
  `kraskov` estimator, `directed_network` pipeline, topology key names → match runtime →
  execute corrected blocks; extend `tests/test_docs_smoke.py`.
- `docs/04_spectral_analysis_and_tfr.md` §5 `compress_fp32` → in-memory description false →
  NWB path I/O per `jnwb.compression.compress_fp32`.
- `docs/common_mistakes.md` §7 PSI z-scores → replace with receipt-backed values from
  `phase_slope_index` docstring or probe.

## Documentation corpus (MkDocs + excluded/stale sources)

- `docs/README.md` → excluded from `mkdocs.yml`; stale; duplicates nav; contains `omission/`
  worked example → delete if redundant or generate/keep consistent with MkDocs nav; no orphan
  stale index → strict build + link check if retained.
- `docs/01_architecture_and_philosophy.md` module map → `compression` described as in-memory
  TFR quantizer; active `compress_fp32` is NWB file conversion (same class of error as
  `docs/04` item) → correct module contract; audit absolute/prescriptive claims (`zero
  assumptions`, hierarchical-model prescriptions, causal-language rules) as
  `{package contract, supported guidance, convention, unsupported overstatement}` → only
  package-contract claims remain unconditional.
- Lazy-import note → `docs/01` and/or `docs/install.md` document 0.1.6 deferred exports →
  matches `tests/test_import_lazy.py`.
- `README.md` explicit closure → execute both Quickstart blocks; verify capability-table
  symbols and placement; install extras vs `pyproject.toml`; Python support vs metadata/CI;
  links; never hardcode public-API count; dataset-independence sentence true only after
  provenance cleanup → new `tests/test_readme_smoke.py` or extend doc smoke probes.

## API reference (`docs/api.md`) — runtime-generated truth

Known defects: truncated `assert_mergeable`; `repair_band_artifacts` missing `sided`;
`cluster_permutation_test` missing `n_jobs`; other truncated rows.

- Implement **API doc generator** from `jnwb.__all__` + `inspect.signature` + runtime
  docstrings → committed `docs/api.md` is diff of generator output; harness gate compares
  generated vs committed and fails on any mismatch → adversarial fixtures: missing param,
  changed default, truncated description, missing/extra symbol → Gate 5/10 use generator as
  sole source of truth (not Markdown signature parsing).

## Project provenance / source neutrality (generic package boundary)

- Targeted docstring fixes: `decoding.py`, `viz.py`, `trajectory.py:111`, `statistics.py:886`
  and `:374`, `compression.py:6`, `ontology.py` Alignment examples, `artifact_repair.py`,
  `spectral.py:39-40`, `jnwb/__init__.py` promotion comments (first file users inspect).
- **Bulk promotion provenance purge** (~40 `PROMOTED 2026-08-23` / `99%-jnwb-sufficiency`
  strings across 17 `jnwb/` modules + 9 test headers) → delete promotion blocks; keep
  scientific contract → `rg "PROMOTED 2026|99%-jnwb-sufficiency|promoted 2026-08-23" jnwb/
  tests/` empty.
- **Non-blocking source-neutrality scan** (comments + docstrings in `jnwb/`) → report
  residue count; Gate 6 PASS is not sufficient evidence of neutrality; target user-facing
  docstrings at zero study-specific tokens.

## MCP documentation

- `docs/10_extending_jnwb_and_verification.md` §3 → lists nonexistent MCP tools → document
  `inspect_nwb`, `prepare_signal_reference`, `get_event_codes_and_timings`, `add_tool` per
  `jnwb/mcp_server/__init__.py`.

## Test / delegation boundary (standalone jnwb)

- `tests/` `pytest.importorskip("omission…")` (14 call sites, 8 modules) → classify each as
  downstream delegation; **remove from jnwb suite** once downstream ownership recorded in
  handoff/issue (do not require absent `omission/` tree for jnwb completeness); retain only
  jnwb-owned boundary tests (`test_jnwb_frozen_boundary.py`, no-downstream-import proofs) →
  `rg 'importorskip\("omission' tests/` empty; full `pytest tests/` passes without omission
  installed.

## Capability hypotheses (review-first; implementation not forced)

Before each item: inventory existing `jnwb/` capabilities. **A justified conclusion that the
capability does not belong in jnwb is a valid completion outcome.** Absence of a method is not
itself a defect.

- **`vflip2`** — absent from active `jnwb/`; archive/parked code only → inspect provenance;
  establish semantics and ownership; implement smallest generic primitive only if justified;
  else record "not in jnwb" with evidence → no export without discriminating tests + docs.
- **LFP channel QC measurements** — partial overlap (`channel_correlation_matrix`,
  `bad_channels_from_correlation`) → define smallest missing measurement primitives only if
  justified; measurements/flags not study exclusion policy → synthetic tests; no universal
  manuscript thresholds.
- **Channel relation / locality / clustering** — small composable primitives only; four layers
  separate; no silent spatial+functional merge; clustering algorithm choice surfaces to Hamm
  if scientifically consequential; `relation/locality ≠ cluster ≠ biological network` →
  synthetic grouping tests or documented "not in jnwb" outcome.

## Documentation consistency gates (0.1.7 deliverable)

- Executable-doc probes: `docs/quickstart.md`, `README.md` quickstart blocks.
- Runtime-generated `docs/api.md` diff gate (above).
- Internal `.md` link resolver for MkDocs corpus (+ `docs/README.md` policy).
- Non-blocking `jnwb/` comment/docstring neutrality report (above).
- Skills signature probes (above).
- Each gate has adversarial fixture proving it catches a known defect →
  `tests/test_harness_adversarial_gates.py` extended.

## Second-audit placeholder (do not delete until 0.1.7 seal)

- Fresh zero-based audit from **current** repository state; partitions do **not** use this
  stack as checklist: (1) scientific/numerical semantics, (2) API/code/doc consistency,
  (3) README/docs/nav usability, (4) tests/gates/failure behavior, (5) packaging/install/release,
  (6) boundary/provenance/no-trace, (7) architecture/maintenance, **(8) harness/skills
  authority (`AGENTS.md`, `CLAUDE.md`, skills, gates, workflows)**. Reconcile against live
  code; material findings re-enter 0.1.7; 100/100 only when second audit has no known
  material defect.

## Housekeeping (docs counts)

- `CONTRIBUTING.md:31` and `AGENTS.md` §6 → update test-count band and runtime receipt
  (616 passed, 15 skipped, ~4 min planning baseline) → re-count after test additions.

# Before 1.0

- **Replace example-based estimator coverage** with analytic, property-based or composition
  tests. The suite is broad and adversarial already; this is the remaining estimator-coverage
  gap.

# Unversioned

- File the omission-side issue for items 1, 2, 5 and 6 of the expert feedback register
  (jnwb issue #4) in the omission repository.
- Four more notebooks under `examples/notebooks/` (WP3 planned five, one exists).
  `tests/test_notebooks.py` picks up a new one with no test change.
