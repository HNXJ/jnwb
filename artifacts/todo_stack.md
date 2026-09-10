# TODO stack

Remaining work only, grouped by the version that carries it. A finished item is deleted —
git, `CHANGELOG.md` and the receipts hold the history. Ordered within each version by the
path a post-0.1.6 completeness audit recommended.

Completeness means no known material defect under the declared jnwb goals — including the
smallest missing generic primitives justified by evidence, not breadth of method or a large
new subsystem.

# 0.1.7

## Release / packaging workflow (policy: GitHub Release before PyPI)

0.1.6 evidence: tag push published PyPI successfully; a later GitHub Release re-ran CI and
`publish-pypi` failed with `400 File already exists` for `jnwb-0.1.6-py3-none-any.whl`. PyPI
artifact was unaffected; the red run is duplicate-publish noise, not a bad release.

**Canonical order from 0.1.7 onward:** fast-forward `main` → push tag `vX.Y.Z` → create and
publish **GitHub Release** for that tag → **then** PyPI upload. PyPI must never publish before
the GitHub Release exists.

- `CONTRIBUTING.md` § Releasing steps 4–5 → currently says tag push publishes PyPI and omits
  GitHub Release as a required step → rewrite to: (1) push tag after CI green on `dev`;
  (2) `gh release create vX.Y.Z` with `CHANGELOG` notes; (3) PyPI publish is triggered only
  by the GitHub Release `published` event, not by the tag push alone → maintainer checklist
  matches workflow.
- `.github/workflows/workflow.yml` `publish-pypi` job `if:` → currently fires on **both**
  `push` to `refs/tags/v*` and `release: published`, causing double publish and false-red CI
  when both happen → restrict `publish-pypi` to `github.event_name == 'release' &&
  github.event.action == 'published' && !github.event.release.prerelease` only; tag push runs
  test + build/validate only (no `upload.pypi.org`). Topology review (2026-09-10): `release:
  published` does not re-emit a release event, so no publish↔release cycle; a release run
  still `needs: build` in the same workflow invocation (rebuilds wheel at release time).
- `.github/workflows/workflow.yml` `publish-pypi` step → optional **safety net only**:
  `skip-existing: true` on `pypa/gh-action-pypi-publish@release/v1` (hyphenated input per
  upstream README; not `skip_existing`). Primary invariant remains release-before-publish;
  duplicate upload must not be a normal successful path — if `skip-existing` masks a workflow
  ordering bug, the mechanical test below must still fail. Use only to avoid HTTP 400 noise
  on accidental re-publish of an already-valid artifact.
- `tests/` workflow policy test (new) → parse `.github/workflows/workflow.yml` and assert
  `publish-pypi` `if:` has no `push` + `refs/tags/v*` branch for non-`rc` production
  releases; assert `release` + `published` is required; fixture proves a tag-only workflow
  graph would fail the test → `python -m pytest tests/ -k workflow_release -q`.
- `AGENTS.md` / `docs/11_extending_and_development.md` release prose (if any) → align with
  GitHub-Release-before-PyPI order and with updated `CONTRIBUTING.md` → no doc still claims
  tag push alone publishes.

## Executable documentation defects

- `docs/quickstart.md` workflow table rows → nonexistent modules `jnwb.artifacts`, `jnwb.directed`, `jnwb.stats`; `compute_psd` listed under `jnwb.tfr`; `raster_psth` / `fit_exponential_onset` listed under `jnwb.spiking` → replace with real module paths (`artifact_repair`, `connectivity`, `statistics`, `spectral`, `viz`, `onset_fitting`) or top-level exports → `mkdocs build --strict`; manual import checks for each listed module.
- `docs/quickstart.md` §3 PSI example → `freq_range=` invalid; `psi.score` / `psi.p_value` invalid on `DirectedResult` → use `bands=(8.0, 30.0)` and `psi.x_to_y`, `psi.p_x_to_y` → execute §3 snippet in fresh interpreter.
- `docs/quickstart.md` §6 jRSA example → `n_permutations=` does not set permutation count; `jrsa_res.p_value` invalid → use `permutations=100` and `jrsa_res.p` → execute §6 snippet; assert `parameters['permutations']==100`.
- `examples/quickstart_jnwb.py:74` `panel_band_power` → positional `band_power(boost, FS, CANONICAL_BANDS[b], ...)` maps band tuple to `sampling_rate` → `band_power(boost, fs=FS, freq_range=jnwb.CANONICAL_BANDS[b], baseline=base)` → `python examples/quickstart_jnwb.py` exits 0 and writes figure.
- `docs/07_statistical_inference_and_nulls.md` §4 `build_permutation_plan` example → wrong signature (`n_samples`, `scheme`, `rng`) → match `build_permutation_plan(labels, groups, *, n_permutations, seed)` → add/extend `tests/test_docs_smoke.py` or doctest execution for this block.
- `docs/07_statistical_inference_and_nulls.md` §5 `detect_trial_cycles` / `assign_subblock_quartiles` examples → wrong args (`trial_times`, `cycle_length_s`, `n_quartiles`) → `detect_trial_cycles(epochs_df, gap_factor=10.0)`, `assign_subblock_quartiles(epochs_df, n_quantiles=4)` → execute corrected snippets against synthetic `epochs_df`.
- `docs/08_directed_connectivity_and_information.md` §2 Granger print block → `result.statistic`, `result.pvalue`, `result.net_direction` invalid → `x_to_y`, `p_x_to_y`, `net` → execute snippet.
- `docs/08_directed_connectivity_and_information.md` §3 PSI print → `psi_res.statistic` invalid → `psi_res.x_to_y` or `psi_res.net` → execute snippet.
- `docs/08_directed_connectivity_and_information.md` §4 transfer entropy example → documents `estimator="kraskov"`; runtime accepts `quantile|uniform|discrete|symbolic` only → remove `kraskov`; list actual estimators → `transfer_entropy(..., estimator="symbolic")` executes.
- `docs/08_directed_connectivity_and_information.md` §6 network pipeline → `directed_connectivity(data_matrix, method=...)` as all-pairs matrix builder and `directed_network(conn_matrix, alpha=...)` with `.adjacency` invalid → document `directed_network(signals, method=..., fdr=...)` returning `dict` with `"matrix"`; fix topology key names → execute corrected §6; `tests/test_docs_smoke.py` extension for `directed_network` + `network_topology`.
- `docs/08_directed_connectivity_and_information.md` §6 `network_topology` print → keys `in_degree`/`out_degree` invalid → `in_degrees`/`out_degrees` per `jnwb.connectivity.network_topology` → execute snippet.
- `docs/04_spectral_analysis_and_tfr.md` §5 `compress_fp32` bullet → describes in-memory array compression; API is NWB path I/O (`src`, `dst`, …) → rewrite to file-path workflow → cross-check against `jnwb.compression.compress_fp32` docstring.
- `docs/common_mistakes.md` §7 PSI trap comment → illustrative z-scores (`z ~ 1.5`, `z > 50`) disagree with library docstring measured values (`z=3` sinusoid, `z=64` broadband) → replace with receipt-backed numbers from `jnwb.connectivity.phase_slope_index` docstring or a runnable probe → cite same source in prose and docstring.

## API reference (`docs/api.md`) accuracy

- `docs/api.md` `jnwb.assert_mergeable` row → description truncated to `**` after signature → restore full one-line description from docstring → visual review + api generator regen if applicable.
- `docs/api.md` `jnwb.repair_band_artifacts` → missing `sided='upper'` parameter in generated signature → regenerate with `sided` → `inspect.signature(jnwb.repair_band_artifacts)` matches api row.
- `docs/api.md` `jnwb.cluster_permutation_test` → missing `n_jobs: int = 1` in generated signature → regenerate → `inspect.signature` matches api row.
- `docs/api.md` signature generation → audit truncated/mismatched function rows (`compress_fp32`, `get_all_units_metadata`, `fit_exponential_onset`, trajectory helpers, …) → extend generator or gate to compare `inspect.signature` for every `__all__` callable → new harness/doc gate: zero signature mismatches on required parameters.

## Skills parity

- `skills/jnwb-connectivity/SKILL.md` routing matrix → `directed_connectivity(signals, fs, method=...)` and `directed_network(adj_matrix, ...)` disagree with runtime (`directed_connectivity` is pairwise X,Y; `directed_network` takes `signals` matrix) → align with `jnwb.connectivity` → `tests/test_skills_validation.py` PASS after update.

## User-facing semantics / failure behavior

- `jnwb/metadata.py` `filter_by_criteria` → unknown criterion keys silently ignored (typo expands selection) → add `unknown: Literal["ignore","raise"]="ignore"`; document silent-ignore hazard, default, and `unknown="raise"` in docstring + `docs/02_paths_addressing_metadata.md` + `docs/api.md` → new test: `unknown="raise"` on misspelled key raises; default unchanged; existing `tests/test_metadata.py:118` retained.
- `jnwb/metadata.py:91` batch unit extraction `except Exception: continue` → silently drops sessions on any failure → narrow exception types or accumulate/report failures → test with corrupt NWB path asserts surfaced error.
- `jnwb/metadata.py:338` electrode inventory batch loop → same silent-drop pattern → same correction/verification as above.
- `jnwb/jrsa.py:1314` Granger AIC lag selection `except Exception: best_lag = lag` → masks statsmodels/API drift → catch specific failures; warn or NaN → unit test with malformed result object.

## Project provenance / agent traces (generic package boundary)

- `jnwb/trajectory.py:8`, `tests/test_trajectory.py:4` → `Author: Antigravity` agent trace in library/tests → remove author line → `rg -n Antigravity jnwb/ tests/` empty.
- `tests/test_permutation.py:3` → cites `artifacts/.lab/agent-harness-audit-20260810.json` → replace with git/CHANGELOG reference or delete → `rg agent-harness tests/` empty.
- `jnwb/decoding.py` module docstring → names `OmissionSession`, `decode_omission_presence`, `omission.jnwb_ext.*` → generic “project decoders live downstream” wording → `rg OmissionSession jnwb/` comments only.
- `jnwb/viz.py` module docstring → `OmissionSession`, `raster_suite_omission` inventory → generic viz scope only → doc review.
- `jnwb/trajectory.py:111` Args → `session: OmissionSession object` → generic session contract (units table + spike accessor) → `rg OmissionSession jnwb/` empty in docstrings.
- `jnwb/statistics.py:886` `confirmatory_compare` example → study tokens `omission`, `FEF`, `O+` → generic condition comparison string → doc review.
- `jnwb/compression.py:6` example path `D:/nwb/omission/...` → neutral `D:/nwb/sub-X_ses-Y.nwb` → `rg nwb/omission jnwb/` empty.
- `jnwb/ontology.py:126-132` `Alignment` examples `omission_relative`, `omission_slot` → generic alignment names → doc review.
- `jnwb/artifact_repair.py` module docstring → omission corpus receipts, subject IDs, downstream figure paths, skill references → method description + overridable defaults only → `rg "V198o|fig_v1_omission|omission corpus" jnwb/` empty.
- `jnwb/spectral.py:39-40` → claims `omission.jnwb_ext.connectivity` re-exports `CANONICAL_BANDS` → delete cross-repo claim → doc review.
- `jnwb/statistics.py:374` `coef_rows` docstring → `fit_omission_band_power_glmm.py` script name → generic wording → `rg fit_omission jnwb/` empty.
- **Bulk promotion provenance** (~40 `PROMOTED 2026-08-23` / `99%-jnwb-sufficiency` strings across 17 `jnwb/` modules + 9 test headers) → delete promotion blocks; keep scientific contract → `rg "PROMOTED 2026|99%-jnwb-sufficiency|promoted 2026-08-23" jnwb/ tests/` empty.
- **Residual `omission` token scan** (~75 occurrences in `jnwb/` source per 2026-09-10 count; todo_stack previously cited 83 across 17 modules) → after targeted rewrites above, run non-blocking source-neutrality audit script; Gate 12 PASS is not sufficient evidence of neutrality → report residue count; target user-facing docstrings/comments in `jnwb/` at zero study-specific tokens.

## MCP documentation

- `docs/10_extending_jnwb_and_verification.md` §3 appendix → lists nonexistent tools `read_nwb_metadata`, `query_units_by_area`, `compute_quick_psth` → document actual tools `inspect_nwb`, `prepare_signal_reference`, `get_event_codes_and_timings`, `add_tool` (optional `ALLOW_DYNAMIC_TOOLS`) → cross-check `jnwb/mcp_server/__init__.py`.

## Architecture / user docs gaps

- No `docs/` mention of lazy public exports introduced in 0.1.6 (`jnwb._lazy_exports`, deferred scipy/sklearn/matplotlib/pynwb) → add concise note in `docs/01_architecture_and_philosophy.md` and/or `docs/install.md` (what loads at `import jnwb` vs first symbol access) → matches `tests/test_import_lazy.py` behavior.
- `CONTRIBUTING.md:31` and `AGENTS.md` §6 → “Around 610 tests” stale (616 passed, 15 skipped, ~4 min on 2026-09-10 planning baseline) → update both to current count band and runtime receipt → re-count after next test additions.

## Test / delegation boundary

- `tests/` omission delegation via `pytest.importorskip("omission…")` (14 call sites across 8 modules) → move to `omission/tests/` when that tree is present in the workspace; **blocked while `omission/` is absent** — if still blocked at stack drain, stop for Hamm's decision rather than delete the tests → `rg 'importorskip\("omission' tests/` empty after move; `test_jnwb_frozen_boundary.py` still passes without omission on `sys.path`.

## Capability primitives (pre-1.0 completeness; smallest generic delta only)

Before implementing each item: inventory whether the capability already exists under another
name in active `jnwb/` (`channel_correlation_matrix`, `bad_channels_from_correlation`,
`directed_network`, `cross_area_coherence`, etc.). Reduce to the missing delta. Surface
consequential algorithm/definition choices to Hamm rather than guessing.

- **`vflip2` public primitive** — `jnwb.__all__` / `docs/api.md` → `vflip2` absent from
  active public API; no matches in current `jnwb/` (implementation/history only in
  parked/archive code per prior state) → inspect archived implementation and provenance
  before copying; establish exact generic numerical operation (inputs, outputs, axes, units,
  edge behavior, electrophysiological meaning); verify jnwb ownership (not project-specific);
  if justified, implement or reimplement the smallest clean generic primitive under identical
  semantics — do not blindly resurrect archive code → public export + `docs/api.md` +
  `docs/references.md` citation if published method + analytic/synthetic tests that
  distinguish correct from plausible-but-wrong behavior + `python scripts/release_gate.py`
  smoke resolves symbol; if ownership or semantics cannot be established independently,
  stop and surface to Hamm without export.

- **Generic LFP channel QC measurements** — `jnwb/artifact_detection.py` (correlation-based
  bad-channel flagging only), `jnwb/artifact_repair.py` (trial repair, not per-channel QC
  metrics) → no reusable per-channel LFP QC measurement suite with explicit time axis/rate,
  units, NaN/Inf behavior, and failure semantics → review existing artifact/QC/spectral
  capabilities first; define smallest missing measurement primitives only where justified
  (candidates: missing/invalid samples, amplitude/variance outliers, saturation/clipping,
  line-noise contamination, spectral abnormalities, flat/dead channels — each only if
  evidence supports and scope is generic); return measurements/flags, not study-specific
  exclusion policy; separate detection from exclude/repair/interpret decisions → synthetic
  tests per metric/flag; no manuscript thresholds encoded as universal defaults; outputs
  compose with existing LFP/NWB addressing (`electrode_inventory`, `map_peak_channel_to_area`,
  etc.).

- **LFP channel relation, locality, and clustering primitives** — active `jnwb/` has
  pairwise directed estimators (`granger`, `phase_slope_index`, `directed_network`, …) but
  no small composable primitives for data-driven channel grouping from features + optional
  coordinates → specify generic inputs/outputs (signals/features, optional electrode
  coordinates/metadata, relation/distance representation, clustering method, `rng`, returned
  labels/scores); keep four layers separate: (1) channel feature/relation estimation, (2)
  locality/spatial distance, (3) clustering, (4) downstream interpretation; reuse existing
  connectivity/coupling estimators where mathematically appropriate — no duplicate estimators;
  do not silently combine spatial proximity and functional relation (any combined metric must
  expose components and weighting); clustering exposes method, parameters, randomness, and
  degenerate-case failure; cluster labels are not anatomical or causal claims → synthetic
  systems with known locality/relation structure recover expected grouping; permutation/label
  invariance and seed-determinism tested where applicable; API preserves
  `relation/locality ≠ cluster ≠ biological network`; remain a small primitive set, not a
  network-analysis subsystem.

## Documentation consistency gates (0.1.7 deliverable)

- Add deterministic gate(s) beyond current Gate 5/10: (a) executable-doc probe for `docs/quickstart.md` code blocks; (b) `inspect.signature` parity for all `__all__` callables in `docs/api.md`; (c) internal `.md` link resolver for `docs/`; (d) optional non-blocking `jnwb/` source-neutrality scan (comments+docstrings) reporting count without failing CI → each gate has a failing fixture test proving it catches a known defect → `python scripts/harness_gate.py` extended; adversarial tests in `tests/test_harness_adversarial_gates.py`.

## Second-audit placeholder (do not delete until 0.1.7 seal)

- After stack empty: run partitioned independent second audit (scientific semantics, API/doc, README/nav, tests/gates, packaging/install, boundary/provenance, architecture debt). Any confirmed material finding re-enters this section before 0.1.7 is declared closed.

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
