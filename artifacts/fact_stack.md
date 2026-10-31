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
| B2 | `jnwb/`, `docs/`, `skills/`, `tests/` | no experiment-specific condition code, session label, area vocabulary, hypothesis, finding or corpus convention appears; a corpus convention (two spellings of one area) is normalised by the project | `gate:6` | fact stack; Q5 2026-09-29 |
| B3 | public parameters that set a scientific choice | such a parameter is required, or defaulted with a cited reason; the domain is the choice-name lexicon plus the exceptions table | `computed:choice_defaults` | fact stack; reduced to its residual Q6, Q7 2026-09-29; "keyword-only" dropped, Hamm 2026-10-25 |

## Design

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| D1 | public callables | a public callable delegates to at most one public analysis operation: each `return f(...)` tail call names one target, and every Analyzer method is checked by its delegation edges | `computed:delegation`, `test:tests/test_fact_gate.py::TestDelegationStaysSingular` | fact stack; Q8 2026-09-29 |
| D2 | public operations with NWB side effects | each carries exactly one category of `mutation categories`, read from its Declaration's category field; the domain is every public callable reaching a file write, transform or repair sink, sinks included | `computed:nwb_side_effects`, `test:tests/test_fact_gate.py::TestNwbSideEffectsCarryOneCategory` | 2026-09-22; Q9 2026-09-29 |
| D3 | public operations with caching side effects | each carries exactly one category of `cache categories`, read from its Declaration's category field; the domain is every public callable reaching the cache-write sink, sinks included | `computed:cache_side_effects`, `test:tests/test_fact_gate.py::TestCacheSideEffectsCarryOneCategory` | 2026-09-22; Q9 2026-09-29 |
| D4 | NWB repair | a representation is repaired only when the intended representation is identifiable | `test:tests/test_nwb_write.py::test_repair_vector_index_refuses_valid_foreign_target` | 2026-09-22 |
| D5 | NWB operations | ambiguous scientific meaning is detected and reported, never resolved: `AmbiguousMappingError` is defined, exported and documented reserved, and a repeated acquisition name or an omitted table that settles nothing raises | `computed:reserved_errors`, `test:tests/test_inspect_one_schema.py::TestANameInTwoPlaces::test_resolve_acquisition_refuses_the_same_collision`, `test:tests/test_nwb_events.py::TestCanonicalFixture::test_ambiguous_omitted_table` | 2026-09-22 |
| D6 | NWB operations | no undocumented condition meaning is inferred: the only defaulted readings are the `documented guesses` rows, each pinned by a test; a codes column the caller named must exist | `computed:documented_guesses`, `test:tests/test_nwb_events.py::TestAnAbsentCodeColumnIsNotSilent::test_a_column_the_caller_named_must_exist`, `test:tests/test_nwb_events.py::TestEdgeConstructs::test_table_without_codes_column` | 2026-09-22 |
| D7 | NWB operations | no anatomical identity and no unit is guessed: `UndeclaredUnitError` is defined, exported and documented reserved, and an electrode count that settles nothing raises | `computed:reserved_errors`, `test:tests/test_acquisition_layout.py::TestWhatTheElectrodeCountCannotSettle` | 2026-09-22 |
| D8 | NWB operations | no trial semantics are invented: `trials` wins only when present and ambiguity raises; the layout answer comes from the electrode count or the documented shape guess | `computed:documented_guesses`, `test:tests/test_nwb_events.py::TestCanonicalFixture::test_ambiguous_omitted_table`, `test:tests/test_nwb_events.py::TestEdgeConstructs::test_trials_table_preferred`, `test:tests/test_acquisition_layout.py::TestTheResolverItself::test_without_an_electrode_count_the_shape_guess_is_all_there_is` | 2026-09-22 |
| D9 | NWB operations | no choice is made among plausible mappings: `AmbiguousMappingError` is defined, exported and documented reserved, and a repeated acquisition name is refused | `computed:reserved_errors`, `test:tests/test_inspect_one_schema.py::TestANameInTwoPlaces::test_resolve_acquisition_refuses_the_same_collision` | 2026-09-22 |
| D10 | execution infrastructure | the core does not decide what to cache on scientific grounds: no call in `jnwb/` reaches the cache-write or cache-key function | `computed:cache_decisions`, `test:tests/test_fact_gate.py::TestCacheDecisionsStayOutOfTheCore` | 2026-09-22 |
| D11 | public execution controls (device, precision, worker, resource) | a control is public only once it changes no number | `gate:21`, `test:tests/test_parallel.py` | 2026-09-22 |
| D12 | `jnwb.__all__` | each export's states follow `lifecycle`: a state holds only when every earlier one holds; `identity-verified` applies where the export takes an execution switch | `computed:lifecycle` | 2026-09-22; Q10 2026-09-29 |

## Identity

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| I1 | public operations with a parameter that takes spikes or LFP by name | each declares input signal class, estimator, output estimand, unit, and frame or index base; no call from one to another, directly or through private helpers, reaches an operation of a wider input class | `computed:signature_types` | fact stack; Q11 2026-09-29; narrowed to what the scan checks 2026-10-24 |
| I4 | numeric public operations outside I1's domain, return-only spike or LFP operations included | each declares input signal class, estimator, output estimand, unit, and frame or index base; none of the five is silently substituted across a `jnwb` boundary, and composition edges type-check | `computed:signal_class` | split from I1 2026-10-24 |
| I2 | public operations | a unit change, or a wrapper or default that changes the estimand, is a named parameter or fails | `computed:unit_conversions`, `computed:wrapper_defaults` | fact stack; Q11 2026-09-29 |
| I3 | a call between `jnwb` functions | a value whose name carries a unit or base suffix reaches a parameter with the same suffix, or is converted on the way; an intentional break is stated at the change site | `computed:boundary_units` | `AGENTS.md` §4.4; moved 2026-09-29 (Q3); narrowed to named units, frames, rates and unsuffixed bases to roadmap 17-08, Hamm 2026-10-25 |

## Science

IDs follow the numbering of the invariants they came from; 3 and 4 moved to B1 and I3.

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| S1 | every output | no empirical value appears that no script computed from data; a hardcoded value is a visual constant or sits in output marked synthetic | `computed:figure_owner_calls`, `test:tests/test_figure_form.py` | `AGENTS.md` §4.1; Q13 2026-09-29 |
| S2 | decibel outputs | raw power is averaged, divided by baseline, and `10*log10` is taken once, last | `computed:db_averages` | `AGENTS.md` §4.2; Q13 2026-09-29 |
| S5 | randomness consumers | anything consuming randomness takes an `rng` parameter, and nothing calls `np.random.seed()` | `computed:global_seeds`, `computed:rng_parameters` | `AGENTS.md` §4.5; Q13 2026-09-29 |
| S6 | `device` and `n_jobs` | device and worker count never change a number | `gate:21`, `test:tests/test_execution_switch.py`, `test:tests/test_parallel.py` | `AGENTS.md` §4.6; Q13 2026-09-29 |
| S7 | docs generators, examples, skills | a caller uses the library function instead of retyping its rule | `computed:owned_rules` | `AGENTS.md` §4.7; Q13 2026-09-29 |
| S8 | a figure label or a returned unit naming a magnitude or direction estimand | it uses no vocabulary of a higher class of `claim classes` than the estimand declares | `computed:claim_class_labels` | `AGENTS.md` §4.8; Q12 2026-09-29; narrowed to labels and units, Hamm 2026-10-25 |
| S9 | exception handlers on data inputs | missing data fails loudly: no handler swallows it | `computed:silent_handlers` | `AGENTS.md` §4.1; moved 2026-09-29 (Q3); scope named, non-finite inputs to roadmap 17-24, Hamm 2026-10-25 |
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
| K5 | new skills | a skill is created only for a coherent public capability surface with enough routing complexity, that no existing skill handles more simply; skill count is not an objective, and a skill whose principal behaviour would be declining, or ad-hoc implementation, is not created | `computed:planned_skills` | 2026-09-22 |

## Release

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| R1 | production PyPI | publication requires a final-version `v*` tag push whose TestPyPI upload, install verification and release-body check passed in the same run; the GitHub Release is created after it | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_publish_pypi_runs_only_on_a_v_tag_push`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_testpypi_needs_build_and_pypi_needs_the_verification`, `test:tests/test_workflow_release_policy.py::TestTheTagPushCreatesTheRelease::test_the_release_follows_the_pypi_upload_in_the_tag_push_run`, `test:tests/test_workflow_release_policy.py::TestTheTagPushCreatesTheRelease::test_the_notes_are_checked_before_anything_reaches_pypi` | 2026-09-22 (R-3) |
| R2 | after production publication | the release installed from PyPI has the tag run's wheel sha256, passes `pip check` and the installed smoke test | `test:tests/test_workflow_release_policy.py::TestTheUploadToPyPIIsVerifiedAfterIt::test_the_release_installed_from_pypi_has_the_build_wheel_and_passes_pip_check_and_smoke` | 2026-09-22 (R-3); Q16 2026-09-29 |
| R3 | tag push | a tag push publishes to production PyPI only for a final version, after its TestPyPI upload and verification in the same run | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_prerelease_cannot_reach_production_pypi`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_the_final_release_rule_agrees_with_pep_440`, `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_the_kind_step_run_in_bash_says_final_only_for_a_final_tag` | 2026-09-22 (R-3) |
| R4 | before production publication | the candidate is published to TestPyPI and verified from there in a clean environment | `test:tests/test_workflow_release_policy.py::TestTestPyPIBeforePyPI` | 2026-09-22 (R-3) |
| R5 | release order | a release is validated on `main` before it is tagged | `test:tests/test_workflow_release_policy.py::TestATagPushReusesTheMainRunOfItsCommit::test_only_a_passed_main_run_of_this_commit_qualifies` | 2026-09-22 (R-3) |
| R6 | supported interpreters | they are the set `pyproject.toml` declares, and the classifiers, the CI matrix and `.readthedocs.yaml` agree with that set; a local-machine constraint does not override it | `gate:8` | 2026-09-22 (06-92) |
| R7 | CI test matrix | the full suite runs on every declared interpreter on both Ubuntu and Windows | `test:tests/test_workflow_release_policy.py::TestEveryDeclaredInterpreterRunsOnBothSystems::test_the_matrix_runs_every_declared_leg_but_the_named_exception` | 2026-09-22 (06-92) |
| R8 | CI build job | the suite runs against the built wheel, installed outside the checkout | `test:tests/test_the_suite_can_qualify_an_installed_copy.py::test_ci_runs_the_suite_against_the_installed_wheel` | 2026-09-22 (06-92) |

## Constants

The values the predicates read. A gate reads them from here and holds no copy.

| Constant | Values | Ruled |
|---|---|---|
| `lifecycle` | `implemented`, `identity-verified`, `documented`, `tested`, `routed` | Q10 2026-09-29 |
| `identity tests` | `device=tests/test_execution_switch.py`, `backend=tests/test_execution_switch.py`, `n_jobs=tests/test_parallel.py` | 2026-09-29 |
| `mutation categories` | `validate`, `write or create`, `copy or transform`, `convert to NWB`, `structural repair`, `normalize declared units or layouts`, `upgrade representation`, `verify written output` | 2026-09-22; Q9 2026-09-29 |
| `cache categories` | `cache identity`, `input and parameter fingerprints`, `checkpoint manifests`, `dependency and version provenance`, `safe artifact persistence`, `cache validation and invalidation`, `resume` | 2026-09-22; Q9 2026-09-29 |
| `documented guesses` | `table default units: jnwb.nwb_integrity.check_ragged_indices`, `table default units: jnwb.nwb_integrity.repair_ragged_index`, `table default units: jnwb.nwb_integrity.check_waveform_blocks`, `code_column default codes: jnwb.nwb_events.events`, `code_column default codes: jnwb.nwb_events.event_onsets`, `trials preferred over epochs`, `layout from electrode count, shape guess otherwise` | 2026-10-28 |
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
| `jnwb.spiking.fano_factor` | `window_s` | `_REQUIRED` | a sentinel, not a value: omitted, the call raises `TypeError`; one positional window is accepted under a `FutureWarning` naming the keyword, until the keyword is the only form | ruling 2026-10-28 (`artifacts/rulings/2026-10-28.md`, 17-06); `tests/test_api_consistency.py::TestAWindowPassedPositionally` |
| `jnwb.spiking.network_burst_index` | `window_s` | `_REQUIRED` | as above | as above |
| `jnwb.spiking.spike_count_correlation` | `window_s` | `_REQUIRED` | as above | as above |
| `jnwb.statistics._firing.fires_in_window` | `window_ms` | `_REQUIRED` | as above | as above |
| `jnwb.statistics._firing.fire_indicator` | `window_ms` | `_REQUIRED` | as above | as above |
| `jnwb.statistics._firing.rate_in_window` | `window_ms` | `_REQUIRED` | as above | as above |
