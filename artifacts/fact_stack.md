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

## Supported Python versions

**Scope:** compatibility and CI policy.

Supported interpreters are declared in `pyproject.toml` and enforced by harness Gate 8.
CI tests the declared floor and newest supported version. Local-machine Python constraints
do not override package metadata.

## Release publication ordering

**Scope:** production PyPI publication for tagged releases.

Release order: validate on `main` → tag → GitHub Release (non-prerelease) → production PyPI.
A tag push alone validates build artifacts; it does not publish to production PyPI.
