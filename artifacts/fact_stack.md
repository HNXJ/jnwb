# fact stack

Human-authorized durable facts. No pending actions (see `artifacts/todo_stack.md`).
No transient state: SHAs, test counts, release status, benchmark snapshots, or open defects.

Agents may read, use, test, and challenge these facts. They must not add, modify, or
delete entries without Hamm's explicit authorization. If repository evidence contradicts
a fact, stop treating it as reliable, surface the conflict, and request review — do not
silently rewrite the fact or the evidence.

## Stack roles

**`fact_stack`** — stable, human-authorized facts (this file).

**`todo_stack`** — mutable, unresolved executable work (`artifacts/todo_stack.md`). Finished
items are deleted from the todo stack, not archived here.

Current evidence can falsify whether a fact still applies; it does not authorize an agent to
rewrite a fact without Hamm.

## jnwb ownership boundary

**Scope:** `jnwb/` library surface, public API, and generic NWB electrophysiology operations.

jnwb is dataset-agnostic. Experiment-specific condition codes, session labels, area
vocabularies, hypotheses, and corpus conventions belong in downstream project code, not
in `jnwb/`, `docs/`, `skills/`, or `tests/`.

## Composable operations, not a pipeline

**Scope:** library design and public API shape.

jnwb exposes composable operations (inspect, extract, align, analyze primitives). It does
not ship one fixed scientific pipeline or study-specific workflow graph. Downstream projects
compose calls and own sequencing choices that affect interpretation.

## Estimator and signal identity

**Scope:** analysis functions and their documented estimands.

A function's signal class (spikes vs LFP), estimator, units, and coordinate frame must not
be silently substituted across a `jnwb` boundary. If a wrapper or default would change the
estimand, the API must name the choice explicitly or fail.

## Scientific choices stay downstream

**Scope:** analysis design decisions that depend on a specific study or dataset.

Project-specific scientific choices — which comparisons to run, which areas or conditions
define a cohort, what constitutes a response — remain in the consuming project's
repository. jnwb supplies primitives; it does not encode one study's design.

## Skill creation is capability-gated

**Scope:** `skills/`. Ruled 2026-09-22.

A skill is created only when a coherent public capability surface exists, has enough routing
complexity to benefit from specialization, and cannot be handled more simply by an existing
skill. Skill count is not an objective. A skill whose principal behaviour would be declining,
or ad-hoc implementation of what no public API provides, is not created.

The planned set is twelve: the ten of 0.2.6, `jnwb-landmark-viz` included (ruled 2026-09-22,
P-180), plus `jnwb-paradigm` (experiment and timing semantics) and `jnwb-qc` (independent
scientific and output QC). `jnwb-data-engineering` and
`jnwb-compute` are gated on their public APIs, and neither is a required endpoint: if the
router can route a capability cleanly, no skill is manufactured for it.

Skills route to existing public objects. No parallel manifest or receipt contract is defined
where `inspect`, `Result`, `Provenance` or `Lineage` already carry the responsibility; those
are extended instead. Every skill ends a task in one of four outcomes: compose and execute,
request missing information, report non-identifiability or failure, decline unsupported
inference.

## NWB mutation and execution infrastructure belong in the core

**Scope:** `jnwb/` public API. Ruled 2026-09-22.

The core may own generic structural operations on NWB: validate, write or create, copy or
transform, convert a generic format to NWB, repair structurally invalid NWB, normalize
explicitly declared units or layouts, upgrade supported representations, and verify written
output. It may repair a representation when the intended representation is identifiable. It
detects ambiguous scientific meaning and never resolves it: it does not infer undocumented
condition meanings, guess anatomical identity or units, invent trial semantics, or choose
among plausible mappings.

The core may own content-addressed execution infrastructure: cache identity, input and
parameter fingerprints, checkpoint manifests, dependency and version provenance, safe
artifact persistence, cache validation and invalidation, and resume. It does not decide what
to cache on scientific grounds.

Execution controls (device, precision, worker and resource policy) are public only once they
change no number. Order: numerical identity, then public execution abstraction, then
performance evidence, then skill routing.

API, documentation and tests for each family precede or land atomically with its skill.

## Supported Python versions

**Scope:** compatibility and CI policy.

Supported interpreters are declared in `pyproject.toml` and enforced by harness Gate 8.
CI runs the full suite on every interpreter `pyproject.toml` declares, on Ubuntu and Windows,
plus the suite against the built wheel; Gate 8 holds the classifiers, the CI matrix and
`.readthedocs.yaml` to that set (ruled 2026-09-22, 06-92). Local-machine Python constraints
do not override package metadata.

## Release publication ordering

**Scope:** production PyPI publication for tagged releases.

Release order: validate on `main` → tag → GitHub Release (non-prerelease) → production PyPI.
A tag push alone validates build artifacts; it does not publish to production PyPI.
Before production publication, the candidate is published to TestPyPI and verified from there in a
clean environment; after it, the same check runs from PyPI (ruled 2026-09-22, R-3).
