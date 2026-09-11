# fact stack

Human-authorized durable facts. No pending actions (see `artifacts/todo_stack.md`).
No transient state: SHAs, test counts, release status, or environment specifics.

Agents may read, use, test, and challenge these facts. They must not add, modify, or
delete entries without Hamm's explicit authorization. If repository evidence contradicts
a fact, stop treating it as reliable, surface the conflict, and request review — do not
silently rewrite the fact or the evidence.

## jnwb ownership boundary

**Scope:** `jnwb/` library surface, public API, and generic NWB electrophysiology operations.

jnwb is dataset-agnostic. Experiment-specific condition codes, session labels, area
vocabularies, hypotheses, and corpus conventions belong in downstream project code, not
in `jnwb/`, `docs/`, `skills/`, or `tests/`.

## Release publication ordering

**Scope:** production PyPI publication for tagged releases.

Production PyPI upload runs only after a non-prerelease GitHub Release is published for
the tag. A tag push alone validates build artifacts; it does not publish to production PyPI.

## Scientific choices stay downstream

**Scope:** analysis design decisions that depend on a specific study or dataset.

Project-specific scientific choices — which comparisons to run, which areas or conditions
define a cohort, what constitutes a response — remain in the consuming project's
repository. jnwb supplies composable operations; it does not encode one study's design.
