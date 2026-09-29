# fact stack — typed draft for approval

Draft of `artifacts/fact_stack.md` in the form ruled on 2026-09-29 (quiz Q1 to Q19,
`artifacts/rulings/2026-09-29.md`). Approved by Hamm on 2026-09-29; everything from
"# fact stack" to the clause map landed as that file, which is now the one the fact gate
reads. The clause map is the evidence that no meaning changed, and did not land.

---

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
| B3 | public parameters that set a scientific choice | such a parameter is keyword-only and required, or defaulted with a cited reason; the domain is the choice-name lexicon plus the exceptions table | `todo:10-10` | fact stack; reduced to its residual Q6, Q7 2026-09-29 |

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
| I1 | numeric public operations | each declares input signal class, output estimand, unit, and frame or index base, and composition edges type-check | `todo:10-10` | fact stack; Q11 2026-09-29 |
| I2 | public operations | a unit change, or a wrapper or default that changes the estimand, is a named parameter or fails | `todo:10-10` | fact stack; Q11 2026-09-29 |
| I3 | a `jnwb` function boundary | units, coordinate frames, sample rates, and 0- vs 1-indexing do not change silently; an intentional break is stated at the change site | `todo:10-10` | `AGENTS.md` §4.4; moved 2026-09-29 (Q3) |

## Science

IDs follow the numbering of the invariants they came from; 3 and 4 moved to B1 and I3.

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| S1 | every output | no empirical value appears that no script computed from data; a hardcoded value is a visual constant or sits in output marked synthetic | `todo:09-04` | `AGENTS.md` §4.1; Q13 2026-09-29 |
| S2 | decibel outputs | raw power is averaged, divided by baseline, and `10*log10` is taken once, last | `todo:09-04` | `AGENTS.md` §4.2; Q13 2026-09-29 |
| S5 | randomness consumers | anything consuming randomness takes an `rng` parameter, and nothing calls `np.random.seed()` | `todo:09-04` | `AGENTS.md` §4.5; Q13 2026-09-29 |
| S6 | `device` and `n_jobs` | device and worker count never change a number | `gate:21`, `test:tests/test_execution_switch.py`, `test:tests/test_parallel.py` | `AGENTS.md` §4.6; Q13 2026-09-29 |
| S7 | docs generators, examples, skills | a caller uses the library function instead of retyping its rule | `todo:09-04` | `AGENTS.md` §4.7; Q13 2026-09-29 |
| S8 | text naming an estimand | the text uses no vocabulary of a higher class of `claim classes` than the estimand declares | `todo:09-04` | `AGENTS.md` §4.8; Q12 2026-09-29 |
| S9 | data inputs | missing data fails loudly | `todo:09-04` | `AGENTS.md` §4.1; moved 2026-09-29 (Q3) |
| S10 | label permutation | a permutation null names its exchangeability scheme | `todo:09-04` | `AGENTS.md` §4.5; moved 2026-09-29 (Q3) |
| S11 | randomness consumers | a result reports the `rng` it used | `todo:09-04` | `AGENTS.md` §4.5; moved 2026-09-29 (Q3) |
| S12 | GPU results | a result computed on GPU records that it was | `todo:09-04` | `AGENTS.md` §4.6; moved 2026-09-29 (Q3) |
| S13 | delay and velocity claims | a physical latency or conduction velocity is claimed only under a verified linear unwrapped phase-frequency relation and predeclared identifiability criteria, and is reported unavailable otherwise | `todo:09-04` | `AGENTS.md` §4.8; moved 2026-09-29 (Q3) |
| S14 | every text | no vocabulary of `immunity vocabulary` is used of volume conduction or reference contamination; the claim is reduced sensitivity to zero-phase-lag coupling | `todo:09-04` | `AGENTS.md` §4.8; Q12 2026-09-29 |

## Skills

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| K1 | shipped domain skills | they partition the routed operations, each owning at least `k` exclusively, the router outside the partition | `todo:09-04` | 2026-09-22; Q14 2026-09-29 |
| K2 | routing rows | every routing target starts at an export of `jnwb.__all__` and resolves on the package; the targets read are the calls in a routing bullet's head and the names in a skill table's `jnwb.` column | `computed:routes` | 2026-09-22; Q15 2026-09-29 |
| K3 | every skill | a task ends in one of four outcomes: compose and execute, request missing information, report non-identifiability or failure, decline unsupported inference | `test:tests/test_skill_decline_behaviour.py::test_every_skill_outcome_is_tested_or_excused` | 2026-09-22 |
| K4 | `skills/` | no skill defines a manifest or receipt contract where `inspect`, `Result`, `Provenance` or `Lineage` carries the responsibility; those are extended instead | `todo:09-04` | 2026-09-22 |
| K5 | new skills | a skill is created only for a coherent public capability surface with enough routing complexity, that no existing skill handles more simply; skill count is not an objective, and a skill whose principal behaviour would be declining, or ad-hoc implementation, is not created | `todo:09-04` | 2026-09-22 |

## Release

| ID | Domain | Predicate | Held by | Ruled |
|---|---|---|---|---|
| R1 | production PyPI | publication requires a published, non-prerelease GitHub Release of a tag | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy` | 2026-09-22 (R-3) |
| R2 | after production publication | the release installed from PyPI has the tag run's wheel sha256, passes `pip check` and the installed smoke test | `todo:12-07` | 2026-09-22 (R-3); Q16 2026-09-29 |
| R3 | tag push | a tag push alone validates the build artifacts and publishes nothing to production PyPI | `test:tests/test_workflow_release_policy.py::TestWorkflowReleasePolicy::test_tag_push_alone_cannot_reach_production_pypi` | 2026-09-22 (R-3) |
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

## B3 exceptions

A defaulted scientific-choice parameter whose default is reviewed and kept. Agent-editable with
evidence and a critic's sign-off.

| Operation | Parameter | Default | Reason | Evidence |
|---|---|---|---|---|

---

## Clause map (does not land)

Every clause of `artifacts/fact_stack.md` at `9ec27c01` and of `AGENTS.md` §4, and the row that
carries it. "Plan" marks a clause Q14 moved to the todo stack; "ruled" marks where a quiz answer,
not this draft, changed the clause's form.

| Source | Clause | Row |
|---|---|---|
| fact: ownership boundary | jnwb is dataset-agnostic | B1, B2 |
| fact: ownership boundary | condition codes, session labels, area vocabularies, hypotheses and corpus conventions belong downstream, not in `jnwb/`, `docs/`, `skills/` or `tests/` | B2 |
| fact: scientific choices | which comparisons, cohorts and response definitions stay in the consuming project; jnwb does not encode one study's design | B3 (ruled Q6, Q7: reduced to its residual) |
| fact: scientific choices | jnwb supplies primitives | D1 |
| fact: composable operations | jnwb exposes composable operations and ships no fixed scientific pipeline or study-specific workflow graph | D1 (ruled Q8: defined by delegation) |
| fact: composable operations | downstream projects compose calls and own sequencing choices that affect interpretation | D1 ("names every sequenced choice as a parameter") |
| fact: estimator identity | signal class, estimator, units and frame are never silently substituted across a boundary | I1, I2 |
| fact: estimator identity | a wrapper or default that would change the estimand names the choice or fails | I2 |
| fact: skill creation | a skill is created only when a coherent surface exists, has routing complexity, and no existing skill handles it more simply | K5 |
| fact: skill creation | skill count is not an objective; a declining or ad-hoc-implementation skill is not created | K5 |
| fact: skill creation | the planned set of twelve, `jnwb-landmark-viz` included, plus `jnwb-paradigm` and `jnwb-qc` | plan (Q14): 09-04's K1 bullet moves the list to the todo stack |
| fact: skill creation | `jnwb-data-engineering` and `jnwb-compute` are gated on their APIs and are not required endpoints | plan (Q14), with the list above |
| fact: skill creation | skills route to existing public objects | K2 |
| fact: skill creation | no parallel manifest or receipt contract where `inspect`, `Result`, `Provenance` or `Lineage` carry it; those are extended | K4 |
| fact: skill creation | every skill ends a task in one of four outcomes | K3 |
| fact: NWB mutation | the core may own validate, write or create, copy or transform, convert, repair, normalize, upgrade, verify | D2 and `mutation categories` (ruled Q9: closed-world allowlist) |
| fact: NWB mutation | it may repair a representation when the intended one is identifiable | D4 |
| fact: NWB mutation | it detects ambiguous scientific meaning and never resolves it | D5 |
| fact: NWB mutation | it does not infer undocumented condition meanings, guess anatomy or units, invent trial semantics, or choose among plausible mappings | D6, D7, D8, D9 (ruled Q9: never-clauses are rows of their own) |
| fact: NWB mutation | the core may own cache identity, fingerprints, manifests, provenance, persistence, validation and invalidation, resume | D3 and `cache categories` |
| fact: NWB mutation | it does not decide what to cache on scientific grounds | D10 |
| fact: NWB mutation | execution controls are public only once they change no number | D11 |
| fact: NWB mutation | in this order: numerical identity, public execution abstraction, performance evidence, skill routing; API, docs and tests precede or land with the skill | D12 and `lifecycle` (ruled Q10: one chain; ruled 2026-09-29: performance evidence is not a state, and the computational order is recorded under release condition 2) |
| fact: Python versions | interpreters declared in `pyproject.toml`, enforced by Gate 8; Gate 8 holds classifiers, matrix and `.readthedocs.yaml` | R6 |
| fact: Python versions | CI runs the full suite on each declared interpreter on Ubuntu and Windows | R7 |
| fact: Python versions | plus the suite against the built wheel | R8 |
| fact: Python versions | local-machine constraints do not override package metadata | R6 |
| fact: publication order | validate on `main`, tag | R5 |
| fact: publication order | GitHub Release (non-prerelease), then production PyPI | R1 |
| fact: publication order | a tag push alone validates build artifacts and does not publish to production PyPI | R3 |
| fact: publication order | TestPyPI first, verified in a clean environment | R4 |
| fact: publication order | after publication, the same check runs from PyPI | R2 (ruled Q16: a CI job) |
| `AGENTS.md` §4.1 | no empirical value that no script computed from data; hardcoded values are visual constants or marked synthetic | S1 |
| `AGENTS.md` §4.1 | missing data fails loudly | S9 |
| `AGENTS.md` §4.2 | take the logarithm last: average raw power, divide by baseline, `10*log10` once | S2 |
| `AGENTS.md` §4.2 | use `aggregate_to_db` | not a fact: an instruction, kept in `AGENTS.md` as §4.7 is (ruled 2026-09-29 for §4.7) |
| `AGENTS.md` §4.3 | `jnwb/` imports nothing from a project folder; identical with a project installed or absent | B1 |
| `AGENTS.md` §4.3 | condition codes, session labels, area vocabularies and findings stay out of `jnwb/`, `docs/`, `skills/`, `tests/`; Gate 6's scan surface | B2 (the partial scan is why B2 names `gate:6` beside `todo:12-07`) |
| `AGENTS.md` §4.3 | a corpus convention is the project's to normalise; a request to encode one is a reason to stop | B2 |
| `AGENTS.md` §4.4 | units, frames, sample rates and indexing do not change silently; breaks stated at the change site | I3 |
| `AGENTS.md` §4.5 | label permutation requires a named exchangeability scheme | S10 |
| `AGENTS.md` §4.5 | randomness takes an `rng`; never `np.random.seed()` | S5 |
| `AGENTS.md` §4.5 | reports what it used | S11 |
| `AGENTS.md` §4.6 | device and worker count never change a number | S6 |
| `AGENTS.md` §4.6 | a GPU result records that it was | S12 |
| `AGENTS.md` §4.7 | call the library function instead of retyping its rule | S7 |
| `AGENTS.md` §4.7 | if the function's shape blocks reuse, widen the shape | not a fact: stays a rule in `AGENTS.md` (ruled 2026-09-29) |
| `AGENTS.md` §4.8 | magnitude, direction, delay and inference are distinct claims; no direction from unsigned magnitude | S8 and `claim classes` |
| `AGENTS.md` §4.8 | latency or velocity only under a verified linear unwrapped relation and predeclared criteria; unavailable otherwise | S13 |
| `AGENTS.md` §4.8 | never "immunity" or "complete suppression"; describe as reduced sensitivity to zero-phase-lag coupling | S14 and `immunity vocabulary` |

The study-vocabulary and dB-lexicon constants take their values in 12-07 and 09-04 (ruled
2026-09-29); the `identity tests` constant is accepted as drafted.
