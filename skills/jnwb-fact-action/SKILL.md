---
name: jnwb-fact-action
description: Execution-control kernel for jnwb. Enforces the F -> R -> A -> V -> S cycle and epistemic constraints.
---

# jnwb-fact-action — Execution-Control Kernel

## 1. Trigger
Activate this skill for any substantial, multi-step, or consequential repository work in `jnwb`: implementing or repairing features, investigating reported defects, executing todo stack items, modifying APIs, refactoring, or performing release verification.

Simple, single-domain reference lookups may route directly to domain skills. All multi-step work must route through `jnwb-fact-action`.

## 2. Mandatory Authority Loading Order
Before inspecting or altering code, an agent MUST load authorities in strict sequence:
1. `AGENTS.md` (repository invariants, operational rules, workflow grammar)
2. `artifacts/fact_stack.md` (human-authorized durable facts)
3. `artifacts/todo_stack.md` (unresolved executable work)
4. Relevant domain skill (e.g. `jnwb-nwb-data`, `jnwb-lfp-spectral`, `jnwb-statistics`)
5. Current repository evidence (re-read targets, execute probes, inspect live tree)

## 3. Core Epistemic Invariants
- **High freedom in hypothesis generation; zero freedom in project-fact completion.**
- Domain priors and background expectations produce probes and hypotheses, NEVER project facts.
- Unknown project facts remain unknown until established by live empirical receipts.
- `fact_stack.md` is strictly human-authorized. Agents may read, test, and challenge facts using evidence, but MUST NOT autonomously add, edit, or delete facts. If evidence contradicts a fact, stop and surface the conflict to Hamm.
- **Verification Independence**: For material scientific, API, packaging, or harness work:
  $$\text{actor} \ne \text{sole verifier}$$
  The actor implementing a change cannot be the sole party verifying its validity. An independent verification step or verifier role must inspect the diff and empirical tests.
- **Evidence Reconciliation**: Conflicting conclusions between delegated roles or evaluations are resolved strictly through empirical receipts and discriminating tests, never through voting or consensus.

## 4. Execution Cycle: F -> R -> A -> V -> S

The execution loop formalizes $W = P(RG)^N S$:

### F — Frame
- Load authorities in the mandatory sequence (1–5).
- Identify the exact todo item from `artifacts/todo_stack.md`.
- Reconstruct the estimand, units, coordinate frames, boundaries, and acceptance criteria.
- Select the relevant domain skill (`role` $\perp$ `domain`).

### R — Review & Reproduce
- Inspect live code and tests before making any changes.
- Formulate discriminating probes for competing hypotheses.
- Reproduce the baseline state or failure mode mechanically on disk. Collect the pre-change receipt.

### A — Action (Smallest Justified)
- Design and apply the smallest justified, reversible change that advances the acceptance criteria.
- Preserve unrelated code and verified invariants.
- No drive-by edits, cosmetic refactoring, or unauthorized API expansions.

### V — Verification (Independent)
- Execute targeted regression and adversarial tests.
- Re-derive key numerical quantities from data rather than summaries.
- Ensure independent verification: inspect the exact diff and assert that all invariants hold.

### S — Seal & Reconcile
- Reconcile the todo stack: delete completed items from `artifacts/todo_stack.md`.
- Keep documentation, skills, and gates synchronized.
- Run `python scripts/harness_gate.py` and `python -m pytest tests/ -q`.
- Commit validated checkpoints on `dev`, push to `origin/dev`, and verify clean status.

## 5. Delegation Protocol (Role ⊥ Domain)
When delegating sub-tasks to separate subagents or roles, decouple the role from the domain skill. Every delegated packet must follow the standard contract:

```text
ROLE: authority | critic | actor | verifier | docs-harness
DOMAIN SKILL: <canonical domain skill, e.g. jnwb-nwb-data>
GOAL: <precise outcome>
TODO ITEM: <item from todo_stack.md>
AUTHORITIES: <receipts / files>
RELEVANT FACTS: <from fact_stack.md>
OBSERVED BASELINE: <reproduced behavior before change>
INVARIANTS: <preserved properties>
ALLOWED SCOPE: <exact files permitted to change>
ACCEPTANCE: <concrete passing criteria>
STOP CONDITIONS: <when to stop and surface>
```

Every delegated result must return:

```text
RESULT: PASS | DEFECT | BLOCKED
CLAIMS:
  - statement: <claim>
    class: observed | derived | inferred | assumed | unknown
    evidence: <command + output receipt>
SMALLEST ACTION: <justified action taken or proposed>
VERIFICATION: <independent verification commands and receipts>
UNRESOLVED: <open material issues or conflicts>
```

## 6. Verification
```bash
python scripts/harness_gate.py
python -m pytest tests/test_skills_validation.py -q
```
