# fact stack

Human-authorized durable facts. No pending actions (`artifacts/todo_stack.md` holds those) and no
transient state: SHAs, test counts, release status, benchmark snapshots or open defects. The five
state slots and who edits each are `AGENTS.md` §2.

Agents may read, use, test and challenge these facts. They must not add, modify or delete an entry
without Hamm's explicit authorization. If repository evidence contradicts a fact, stop treating it
as reliable, surface the conflict and request review; never silently rewrite the fact or the
evidence. Current evidence can show that a fact no longer applies; it does not authorize an agent to
rewrite it.

| Fact | Scope | Statement |
|---|---|---|
| jnwb ownership boundary | `jnwb/` library surface, public API, generic NWB electrophysiology operations | jnwb is dataset-agnostic. Experiment-specific condition codes, session labels, area vocabularies, hypotheses and corpus conventions belong in downstream project code, not in `jnwb/`, `docs/`, `skills/` or `tests/`. |
| Scientific choices stay downstream | analysis design decisions that depend on a study or dataset | Which comparisons to run, which areas or conditions define a cohort, and what constitutes a response remain in the consuming project's repository. jnwb supplies primitives; it does not encode one study's design. |
| Composable operations, not a pipeline | library design and public API shape | jnwb exposes composable operations (inspect, extract, align, analyze primitives). It ships no fixed scientific pipeline or study-specific workflow graph. Downstream projects compose calls and own sequencing choices that affect interpretation. |
| Estimator and signal identity | analysis functions and their documented estimands | A function's signal class (spikes vs LFP), estimator, units and coordinate frame are never silently substituted across a `jnwb` boundary. If a wrapper or default would change the estimand, the API names the choice explicitly or fails. |
| Skill creation is capability-gated | `skills/`; ruled 2026-09-22 | A skill is created only when a coherent public capability surface exists, has enough routing complexity to benefit from specialization, and cannot be handled more simply by an existing skill. Skill count is not an objective. A skill whose principal behaviour would be declining, or ad-hoc implementation of what no public API provides, is not created. The planned set is twelve: the ten of 0.2.6, `jnwb-landmark-viz` included (ruled 2026-09-22, P-180), plus `jnwb-paradigm` (experiment and timing semantics) and `jnwb-qc` (independent scientific and output QC). `jnwb-data-engineering` and `jnwb-compute` are gated on their public APIs, and neither is a required endpoint: if the router can route a capability cleanly, no skill is manufactured for it. Skills route to existing public objects: no parallel manifest or receipt contract is defined where `inspect`, `Result`, `Provenance` or `Lineage` already carry the responsibility; those are extended instead. Every skill ends a task in one of four outcomes: compose and execute, request missing information, report non-identifiability or failure, decline unsupported inference. |
| NWB mutation and execution infrastructure belong in the core | `jnwb/` public API; ruled 2026-09-22 | The core may own generic structural operations on NWB: validate, write or create, copy or transform, convert a generic format to NWB, repair structurally invalid NWB, normalize explicitly declared units or layouts, upgrade supported representations, and verify written output. It may repair a representation when the intended representation is identifiable. It detects ambiguous scientific meaning and never resolves it: it does not infer undocumented condition meanings, guess anatomical identity or units, invent trial semantics, or choose among plausible mappings. The core may own content-addressed execution infrastructure: cache identity, input and parameter fingerprints, checkpoint manifests, dependency and version provenance, safe artifact persistence, cache validation and invalidation, and resume. It does not decide what to cache on scientific grounds. Execution controls (device, precision, worker and resource policy) are public only once they change no number, in this order: numerical identity, public execution abstraction, performance evidence, skill routing. API, documentation and tests for each family precede or land atomically with its skill. |
| Supported Python versions | compatibility and CI policy | Supported interpreters are declared in `pyproject.toml` and enforced by harness Gate 8. CI runs the full suite on every interpreter `pyproject.toml` declares, on Ubuntu and Windows, plus the suite against the built wheel; Gate 8 holds the classifiers, the CI matrix and `.readthedocs.yaml` to that set (ruled 2026-09-22, 06-92). Local-machine Python constraints do not override package metadata. |
| Release publication ordering | production PyPI publication for tagged releases | Validate on `main`, tag, GitHub Release (non-prerelease), production PyPI. A tag push alone validates build artifacts and does not publish to production PyPI. Before production publication the candidate is published to TestPyPI and verified from there in a clean environment; after it, the same check runs from PyPI (ruled 2026-09-22, R-3). |

## Changes from `artifacts/fact_stack.md` at `fe14858d`

| Old | New | Why |
|---|---|---|
| "Stack roles" section defining `fact_stack` and `todo_stack`, and that finished items are deleted from the todo stack | one sentence pointing to `AGENTS.md` §2, which tables all five slots and their edit rules | two homes for the same rule; the "finished items are deleted" rule is `AGENTS.md` §2's |
| "Current evidence can falsify whether a fact still applies; it does not authorize an agent to rewrite a fact without Hamm" (under Stack roles) | moved into the authorization paragraph, same words in substance | it is part of the authorization rule, not of the stack roles |
| Eight `##` sections, each a `**Scope:**` line and a paragraph | one table: fact, scope, statement | comparable facts in a table (`AGENTS.md` §11 condition 1) |
| "jnwb ownership boundary" and "Scientific choices stay downstream" as distant sections | adjacent rows, texts unchanged | they state two sides of one boundary; a reader sees both together. Not merged, because each has its own scope |
| "must not be silently substituted", "must name the choice explicitly or fail" | "are never silently substituted", "names the choice explicitly or fails" | wording only |
| Release order written with arrows | the same four steps as a comma list | wording only |

No fact, scope, date, ruling reference or authorization rule is added, removed or weakened. The file
keeps the strings `tests/test_harness_adversarial_gates.py` asserts ("Human-authorized durable
facts", "Hamm"), names no literal release label (`tests/test_standing_rules_name_no_cycle.py`), and
cites only paths that resolve (`tests/test_pointer_documents_resolve.py`).

## A conflict to surface, not a change

"The planned set is twelve: the ten of 0.2.6". `skills/` holds nine directories and
`CANONICAL_SKILLS` in `tests/test_skills_validation.py` lists nine; the tenth reading is
`artifacts/skills/jnwb-fact-action`, which does not ship. 07-30 adds a second repository-only
skill, `jnwb-review`. Whether repository-only skills count toward the twelve is `decisions.md` D13.
The text above is kept as ruled.
