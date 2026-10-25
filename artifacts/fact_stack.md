# fact stack

Human-authorized durable facts. No pending actions (`artifacts/todo_stack.md` holds those) and no
transient state: SHAs, test counts, release status, benchmark snapshots or open defects. The five
state slots and who edits each are `AGENTS.md` §2.

Agents may read, use, test and challenge these facts. They must not add, modify or delete an entry
without Hamm's explicit authorization. If repository evidence contradicts a fact, stop treating it
as reliable, surface the conflict and request review; never silently rewrite the fact or the
evidence. Current evidence can show that a fact no longer applies; it does not authorize an agent to
rewrite it. The B3 exceptions table is the one agent-editable part: a row lands with its evidence
and a critic's sign-off.

## Row form

One atomic claim per row. `Held by` names what establishes the claim, as backticked holders:

| Holder | Resolves to |
|---|---|
| `gate:N` | harness gate N of `scripts/harness_gate.py` |
| `test:tests/<file>.py` or `test:tests/<file>.py::<name>` | a test module, or one test in it (`Class::name` inside a class) |
| `computed:<name>` | a predicate `scripts/fact_gate.py` evaluates on the generated fact graph |
| `todo:<item>` | the live todo item that will hold the claim |

`scripts/fact_gate.py` reports each row:

| Status | When |
|---|---|
| HELD | no `todo:` holder, every holder resolves, and every `computed:` predicate is true |
| UNHELD | a `todo:` holder names a live item; any other holder listed beside it covers part of the domain |
| VIOLATED | a `computed:` predicate is false, a holder does not resolve, a `todo:` names no live item, or the row names no holder |

VIOLATED fails the gate; UNHELD is listed with its item. A `gate:` or `test:` holder is resolved,
not re-run: its verdict is the harness's or the suite's, which run it themselves.

## Boundary

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| B1 | `jnwb/` import graph | `jnwb/` imports nothing from a project folder, and behaves identically whether a project package is installed or absent | `gate:1`, `test:tests/test_jnwb_frozen_boundary.py` | `AGENTS.md` §4.3; moved 2026-09-29 (Q3) |
| B2 | `jnwb/`, `docs/`, `skills/`, `tests/` | no experiment-specific condition code, session label, area vocabulary, hypothesis, finding or corpus convention appears; a corpus convention (two spellings of one area) is normalised by the project | `gate:6`, `todo:12-07` | fact stack; Q5 2026-09-29 |
| B3 | public parameters that set a scientific choice | such a parameter is required, or defaulted with a cited reason; the domain is the choice-name lexicon plus the exceptions table | `computed:choice_defaults` | fact stack; reduced to its residual Q6, Q7 2026-09-29; "keyword-only" dropped, Hamm 2026-10-25 |

## Design

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| D1 | public callables | a public callable delegates to at most one public analysis operation, or names every sequenced choice as a parameter; each Analyzer method is checked by its delegation edges | `todo:11-03` | fact stack; Q8 2026-09-29 |
| D2 | public operations with NWB side effects | each carries exactly one category of `mutation categories` | `todo:11-03` | 2026-09-22; Q9 2026-09-29 |
| D3 | public operations with caching side effects | each carries exactly one category of `cache categories` | `todo:11-03` | 2026-09-22; Q9 2026-09-29 |
| D4 | NWB repair | a representation is repaired only when the intended representation is identifiable | `todo:11-03` | 2026-09-22 |
| D5 | NWB operations | ambiguous scientific meaning is detected and reported, never resolved | `todo:11-03` | 2026-09-22 |
| D6 | NWB operations | no undocumented condition meaning is inferred | `todo:11-03` | 2026-09-22 |
| D7 | NWB operations | no anatomical identity and no unit is guessed | `todo:11-03` | 2026-09-22 |
| D8 | NWB operations | no trial semantics are invented | `todo:11-03` | 2026-09-22 |
| D9 | NWB operations | no choice is made among plausible mappings | `todo:11-03` | 2026-09-22 |
| D10 | execution infrastructure | the core does not decide what to cache on scientific grounds | `todo:11-03` | 2026-09-22 |
| D11 | public execution controls (device, precision, worker, resource) | a control is public only once it changes no number | `todo:11-03` | 2026-09-22 |
| D12 | `jnwb.__all__` | each export's states follow `lifecycle`: a state holds only when every earlier one holds; `identity-verified` applies where the export takes an execution switch | `computed:lifecycle` | 2026-09-22; Q10 2026-09-29 |

## Identity

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| I1 | public operations with a parameter that takes spikes or LFP by name | each declares input signal class, estimator, output estimand, unit, and frame or index base; no call from one to another, directly or through private helpers, reaches an operation of a wider input class | `computed:signature_types` | fact stack; Q11 2026-09-29; narrowed to what the scan checks 2026-10-24 |
| I4 | numeric public operations outside I1's domain, return-only spike or LFP operations included | each declares input signal class, estimator, output estimand, unit, and frame or index base; none of the five is silently substituted across a `jnwb` boundary, and composition edges type-check | `todo:17-03` | split from I1 2026-10-24 |
| I2 | public operations | a unit change, or a wrapper or default that changes the estimand, is a named parameter or fails | `computed:unit_conversions`, `computed:wrapper_defaults` | fact stack; Q11 2026-09-29 |
| I3 | a `jnwb` function boundary | units, coordinate frames, sample rates, and 0- vs 1-indexing do not change silently; an intentional break is stated at the change site | `todo:16-10` | `AGENTS.md` §4.4; moved 2026-09-29 (Q3) |

## Science

IDs follow the numbering of the invariants they came from; 3 and 4 moved to B1 and I3.

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| S1 | every output | no empirical value appears that no script computed from data; a hardcoded value is a visual constant or sits in output marked synthetic | `todo:11-07` | `AGENTS.md` §4.1; Q13 2026-09-29 |
| S2 | decibel outputs | raw power is averaged, divided by baseline, and `10*log10` is taken once, last | `todo:11-07` | `AGENTS.md` §4.2; Q13 2026-09-29 |
| S5 | randomness consumers | anything consuming randomness takes an `rng` parameter, and nothing calls `np.random.seed()` | `todo:11-07` | `AGENTS.md` §4.5; Q13 2026-09-29 |
| S6 | `device` and `n_jobs` | device and worker count never change a number | `gate:21`, `test:tests/test_execution_switch.py`, `test:tests/test_parallel.py` | `AGENTS.md` §4.6; Q13 2026-09-29 |
| S7 | docs generators, examples, skills | a caller uses the library function instead of retyping its rule | `todo:12-11` | `AGENTS.md` §4.7; Q13 2026-09-29 |
| S8 | a figure label or a returned unit naming a magnitude or direction estimand | it uses no vocabulary of a higher class of `claim classes` than the estimand declares | `computed:claim_class_labels` | `AGENTS.md` §4.8; Q12 2026-09-29; narrowed to labels and units, Hamm 2026-10-25 |
| S9 | data inputs | missing data fails loudly | `computed:silent_handlers` | `AGENTS.md` §4.1; moved 2026-09-29 (Q3) |
| S10 | label permutation | a permutation null names its exchangeability scheme | `computed:permutation_schemes` | `AGENTS.md` §4.5; moved 2026-09-29 (Q3) |
| S11 | randomness consumers | a result reports the `rng` it used | `computed:rng_reports` | `AGENTS.md` §4.5; moved 2026-09-29 (Q3) |
| S12 | GPU results | a result computed on GPU records that it was | `test:tests/test_execution_switch.py::TestTheResultRecordsTheDevice::test_every_export_with_a_cuda_path_records_its_device`, `test:tests/test_execution_switch.py::TestCudaAgreesWithTheCpu::test_within_tolerance_and_recorded` | `AGENTS.md` §4.6; moved 2026-09-29 (Q3) |
| S13 | delay and velocity claims | a physical latency or conduction velocity is claimed only under a verified linear unwrapped phase-frequency relation and predeclared identifiability criteria, and is reported unavailable otherwise | `todo:12-21` | `AGENTS.md` §4.8; moved 2026-09-29 (Q3) |
| S14 | every text | no vocabulary of `immunity vocabulary` is used of volume conduction or reference contamination; the claim is reduced sensitivity to zero-phase-lag coupling | `computed:immunity_vocabulary` | `AGENTS.md` §4.8; Q12 2026-09-29 |
| S15 | routed exports | every routed export that implements a published method cites it; the predicate passes when each routed export without a citation is on the recorded exclusion list, and it does not check that methods cite | `computed:routed_citations` | 2026-10-22 |

## Skills

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| K1 | shipped domain skills | they partition the routed operations, each owning at least `k` exclusively, the router outside the partition | `computed:partition` | 2026-09-22; Q14 2026-09-29 |
| K2 | routing rows | every routing target starts at an export of `jnwb.__all__` and resolves on the package; the targets read are the calls in a routing bullet's head and the names in a skill table's `jnwb.` column | `computed:routes` | 2026-09-22; Q15 2026-09-29 |
| K3 | every skill | a task ends in one of four outcomes: compose and execute, request missing information, report non-identifiability or failure, decline unsupported inference | `test:tests/test_skill_decline_behaviour.py::test_every_skill_outcome_is_tested_or_excused` | 2026-09-22 |
| K4 | `skills/` | no skill defines a manifest or receipt contract where `inspect`, `Result`, `Provenance` or `Lineage` carries the responsibility; those are extended instead | `computed:skill_contracts` | 2026-09-22 |
| K5 | new skills | a skill is created only for a coherent public capability surface with enough routing complexity, that no existing skill handles more simply; skill count is not an objective, and a skill whose principal behaviour would be declining, or ad-hoc implementation, is not created | `todo:11-09` | 2026-09-22 |

## Release

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| R1 | production PyPI | publication requires a final-version `v*` tag push whose TestPyPI upload, install verification and release-body check passed in the same run; the GitHub Release is created after it | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_publish_pypi_runs_only_on_a_v_tag_push`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_testpypi_needs_build_and_pypi_needs_the_verification`, `test:tests/test_workflow_release_policy.py::TestTheTagPushCreatesTheRelease::test_the_release_follows_the_pypi_upload_in_the_tag_push_run`, `test:tests/test_workflow_release_policy.py::TestTheTagPushCreatesTheRelease::test_the_notes_are_checked_before_anything_reaches_pypi` | 2026-09-22 (R-3) |
| R2 | after production publication | the release installed from PyPI has the tag run's wheel sha256, passes `pip check` and the installed smoke test | `todo:12-07` | 2026-09-22 (R-3); Q16 2026-09-29 |
| R3 | tag push | a tag push publishes to production PyPI only for a final version, after its TestPyPI upload and verification in the same run | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_prerelease_cannot_reach_production_pypi`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_the_final_release_rule_agrees_with_pep_440`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_the_kind_step_run_in_bash_says_final_only_for_a_final_tag` | 2026-09-22 (R-3) |
| R4 | before production publication | the candidate is published to TestPyPI and verified from there in a clean environment | `test:tests/test_workflow_release_policy.py::TestTestPyPIBeforePyPI` | 2026-09-22 (R-3) |
| R5 | release order | a release is validated on `main` before it is tagged | `todo:12-07` | 2026-09-22 (R-3) |
| R6 | supported interpreters | they are the set `pyproject.toml` declares, and the classifiers, the CI matrix and `.readthedocs.yaml` agree with that set; a local-machine constraint does not override it | `gate:8` | 2026-09-22 (06-92) |
| R7 | CI test matrix | the full suite runs on every declared interpreter on both Ubuntu and Windows | `todo:12-07` | 2026-09-22 (06-92) |
| R8 | CI build job | the suite runs against the built wheel, installed outside the checkout | `test:tests/test_the_suite_can_qualify_an_installed_copy.py::test_ci_runs_the_suite_against_the_installed_wheel` | 2026-09-22 (06-92) |

## Constants

The values the predicates read. A gate reads them from here and holds no copy.

| Constant | Values | Ruled |
|---|---|---|
| `lifecycle` | `implemented`, `identity-verified`, `documented`, `tested`, `routed` | Q10 2026-09-29 |
| `identity tests` | `device=tests/test_execution_switch.py`, `backend=tests/test_execution_switch.py`, `n_jobs=tests/test_parallel.py` | 2026-09-29 |
| `mutation categories` | `validate`, `write or create`, `copy or transform`, `convert to NWB`, `structural repair`, `normalize declared units or layouts`, `upgrade representation`, `verify written output` | 2026-09-22; Q9 2026-09-29 |
| `cache categories` | `cache identity`, `input and parameter fingerprints`, `checkpoint manifests`, `dependency and version provenance`, `safe artifact persistence`, `cache validation and invalidation`, `resume` | 2026-09-22; Q9 2026-09-29 |
| `claim classes` | `magnitude`, `lag asymmetry`, `delay`, `inference` | Q12 2026-09-29 |
| `immunity vocabulary` | `immunity`, `immune`, `complete suppression` | `AGENTS.md` §4.8; Q12 2026-09-29 |
| `k` | `3` | Q14 2026-09-29 |
| `dB log forms` | `log10`, `10*log10`, `20*log10`, `*_db` (a call to a function whose name ends in _db) | S2 dB lexicon 2026-10-10; transcribed 2026-10-11 at Hamm's ruling |
| `B3 choice names` | `window`, `window_ms`, `window_s`, `time_window`, `time_window_s`, `time_window_ms` (a `window` whose default is a string names a taper, not a time span, and is outside the lexicon) | Hamm 2026-10-24 (11-06: time windows only; `time_window_ms` added) |
| `dB averaging forms` | `mean`, `nanmean`, `average`, `sum / count` (a sum divided by a count); a median of dB values is not flagged | S2 dB lexicon 2026-10-10; transcribed 2026-10-11 at Hamm's ruling |

## B3 exceptions

A defaulted scientific-choice parameter whose default is reviewed and kept. Agent-editable with
evidence and a critic's sign-off.

| Operation | Parameter | Default | Reason | Evidence |
|---|---|---|---|---|
| `jnwb.connectivity._trials.bin_spikes` | `window_s` | `None` | marks an omitted argument of the `window_s`/`window` pair; with neither, the call raises, so the window is required | `resolve_unit_alias` with no `default`; `tests/test_skill_decline_behaviour.py` ("requires window_s") |
| `jnwb.connectivity._trials.bin_spikes` | `window` | `None` | the alias of `window_s`; as above | as above |
| `jnwb.connectivity._information.spike_mutual_information` | `time_window_s` | `None` | marks an omitted argument of the `time_window_s`/`time_window` pair; with neither, the call raises, so the window is required | `_spike_mi` calls `resolve_unit_alias` with no `default`; `tests/test_skill_decline_behaviour.py` ("requires time_window_s") |
| `jnwb.connectivity._information.spike_mutual_information` | `time_window` | `None` | the alias of `time_window_s`; as above | as above |
| `jnwb.connectivity._information.binary_occupancy_mutual_information` | `time_window_s` | `None` | as for `spike_mutual_information`, whose body `_spike_mi` it shares; the call raises after its own `DeprecationWarning` | `tests/test_window_default_deprecation.py` (the deprecated MI aliases) |
| `jnwb.connectivity._information.binary_occupancy_mutual_information` | `time_window` | `None` | as above | as above |
| `jnwb.connectivity._information.spike_count_mutual_information` | `time_window_s` | `None` | as for `spike_mutual_information`, whose body `_spike_mi` it shares; the call raises after its own `DeprecationWarning` | `tests/test_window_default_deprecation.py` (the deprecated MI aliases) |
| `jnwb.connectivity._information.spike_count_mutual_information` | `time_window` | `None` | as above | as above |
| `jnwb.jrsa.jrsa` | `window` | `None` | no window: the whole aligned axis; `window` counts samples, not time, and the input sets the span | `jnwb/jrsa/_stages.py`, `_make_windows` returns the inputs unchanged for `None` |
| `jnwb.laminar._xflip.xflip` | `window` | `None` | no window: every probe row; `window` names rows, not time | `xflip` reads rows only when `window is not None` |
| `jnwb.laminar._zflip.zflip` | `window` | `None` | no window: every probe row; `window` names rows, not time | `zflip` reads rows only when `window` is given |
| `jnwb.analyzers.UnitAnalyzer.psth` | `window_ms` | `None` | deprecated: left out, (-1000, 2000) with a `FutureWarning`; required in 0.2.15 | Hamm 2026-10-24; `tests/test_window_default_deprecation.py`; roadmap row 17-04 |
| `jnwb.analyzers.UnitAnalyzer.raster` | `window_ms` | `None` | as above | as above |
| `jnwb.trajectory.build_time_resolved_matrix` | `time_window_ms` | `None` | as above | as above |
| `jnwb.trajectory.compute_population_trajectory` | `time_window_ms` | `None` | as above | as above |
