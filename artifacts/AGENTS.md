# AGENTS.md — Generalized Agent Reliability Policy & Operational Kernel

> **POLICY STATUS & SCOPE NOTICE**:
> This document is a **generalized, reusable work-policy reference artifact**.
> Its existence in `artifacts/` does not constitute automatically active agent configuration unless explicitly mounted or declared.
>
> **Scope Mapping**:
> - `general work rule` $\rightarrow$ `artifacts/AGENTS.md`
> - `jnwb development rule` $\rightarrow$ `docs/11_extending_and_development.md`
> - `reusable jnwb procedure` $\rightarrow$ `skills/`
> - `mechanical invariant` $\rightarrow$ `tests/` and `scripts/harness_gate.py`
> - `temporary receipt` $\rightarrow$ `artifacts/`

---

## 1. Epistemic Discipline & Authority Hierarchy

### Truth Precedence
When claims, observations, or descriptions conflict, authority resolves strictly in descending order:
1. **Direct Empirical Receipts**: The exact data artifact (CSV, JSON, HDF5, NWB) written by verified code on disk, named beside the claim.
2. **Current Repository & File State**: Live inspection of working directory and version control.
3. **Structured Project State**: Machine-readable logs, manifests, and index tables.
4. **Narrative Memory & Prose**: Conversation transcripts, doctrine descriptions, and skill documentation.

### Core Epistemic Invariants
- **Claim Taxonomy**: Every claim belongs strictly to:
  $$\text{claim} \in \{\text{observed}, \text{derived}, \text{inferred}, \text{assumed}, \text{unknown}\}$$
- **Verification Rule**: $\text{execution} \ne \text{verification}$. A process completing or exiting with status 0 does not constitute verification. Verification requires observed empirical receipts matching the exact claim scope.
- **State Invariant**: $\text{memory} \ne \text{current state} \ne \text{evidence}$. Never assert repository or file state based on memory from prior turns. Re-derive from live disk inspection.
- **State Transition Invariant**: $\text{configured} \ne \text{discovered} \ne \text{loaded} \ne \text{executed} \ne \text{verified}$.
- **Pass Criterion**: $\text{unknown} \ne \text{PASS}$. An unresolved conflict or unverified assumption is a STOP condition. PASS requires observed empirical receipts matching claim scope.
- **Autoritative Conflict**: Unresolved authoritative conflict $\rightarrow$ STOP and surface plainly.
- **Harness Threshold**: Any evaluated harness score $< 80/100$ triggers mandatory harness diagnosis and minimal durable repair before proceeding.

---

## 2. Execution Grammar: $W = P(RG)^N S$

All multi-step agent actions follow the PRGS operational loop:
- **P (Prepare)**: Orient, inspect baseline state, identify physical constraints, locate input receipts, and establish explicit acceptance criteria before mutating state.
- **R (Review)**: Evaluate candidate action, script output, or intermediate observation against evidence and protected invariants.
- **G (Progress)**: Execute the smallest discriminative action producing decisive empirical feedback.
- **S (Seal)**: Verify all acceptance criteria against direct empirical receipts, run regression tests, and record provenance before declaring completion.

---

## 3. Action & Scope Discipline

- **Smallest Justified $\Delta$**: Smallest sufficient action, context, and harness to achieve acceptance. Preserve unrelated invariants.
- **Decision Rule**:
  - Reversible + justified $\rightarrow$ act + verify.
  - Ambiguous + consequential / irreversible $\rightarrow$ ask.
- **Scope Hierarchy**:
  - Global only if universal across unrelated projects.
  - Project truth stays in project repository/workspace.
  - Multi-step procedure $\rightarrow$ skill.
  - Mechanically preventable failure $\rightarrow$ automated test/gate.
  - Tool deficiency $\rightarrow$ tool.
  - Temporary state $\rightarrow$ conversation context or artifact.
- **Root Discipline**:
  $$\boxed{\text{New root entry requires demonstrated root necessity}}$$
  Work products, intermediate data, and diagnostic receipts reside in `artifacts/`, `docs/`, `skills/`, `scripts/`, `tests/`, or package directories.

---

## 4. Harness Adaptation & Maintenance

- **Diagnosis Triggers**: $\text{friction} \mid \text{contradiction} \mid \text{drift} \mid \text{error} \mid \text{stale knowledge} \mid \text{missing capability} \rightarrow \text{diagnose cause} \rightarrow \text{inspect harness } H$.
- **Harness Score**: Performance $< 80/100 \rightarrow$ mandatory harness diagnosis.
- **Durable Repair**: Harness-preventable issue $\rightarrow$ minimal durable repair at root.
- **Recurring Corrections**: Prefer root harness repair over repeated prompting.
- **Pruning**: Unused harness elements $\rightarrow$ review for removal.
- **Target**: $\min |H|$ subject to reliable performance $\ge$ required quality.

---

## 5. Mechanical Safety Gates

1. **No Destructive Operations**: Prohibit destructive commands (`git reset --hard`, `git push --force`) and indiscriminate wildcard additions (`git add .`, `git add -A`, `git commit -a`).
2. **Pre-Commit Index Verification**: Verify the staged index before every commit:
   ```bash
   git diff --cached --name-only
   ```
   Confirm that every listed path strictly belongs to the declared task. Unstage unrelated or concurrent edits immediately.
3. **Automated Prevention**: Mechanically preventable errors must be guarded by executable gates or tests, not just docstrings.

---

## 6. Communication & Delivery

- Lead with the result.
- Be concise, skeptical, and direct.
- Surface blocking friction, contradictions, or drift immediately.
- List unresolved material issues at the conclusion of deliverables.
