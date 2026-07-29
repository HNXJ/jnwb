---
name: labyrinth-protocol
description: |
  Adaptive Context Management Protocol (ACMP): 3-level architecture (State, Actions, Regulation),
  Self-Improving Knowledge Graph Optimizer (Knowledge -> Prediction -> Observation -> Error -> Evolution),
  Six Measured Quantities (Coverage C_struct/C_ver, Mismatch Vector, Complexity Fano/Depth, Information, Predictive Accuracy, Cost),
  Objective Function J, Schema v3, Workflow Profiles, Three Immutable Rules, 7 fundamental actions (Evolve, Plan, Progress, Review, Prune, Adapt, Seal),
  artifacts/.lab/ directory convention, lab_compile graph compiler, and SQLite SHA-256 hash-chain multi-agent protocol.
---

# Labyrinth Protocol (ACMP & Knowledge Graph Optimizer)

## Overview

**Labyrinth** is an **Adaptive Context Management Protocol (ACMP)** and a **self-improving knowledge graph optimizer** (Mission v10/v11). It forms, stabilizes, and optimizes a project's ontological graph — its concepts, decisions, claims, backlog, and structural relationships.

It drives context optimization through the continuous loop:
$$\text{Knowledge} \longrightarrow \text{Prediction} \longrightarrow \text{Observation} \longrightarrow \text{Error} \longrightarrow \text{Evolution} \longrightarrow \text{Knowledge}$$

This skill is the canonical specification governing multi-agent workflow orchestration for this repository.

---

## Storage & Directory Convention

- **Dot-prefixed Tooling State**: All local repository graph nodes live under **`artifacts/.lab/`** (e.g. `artifacts/.lab/labyrinth-<repo>.json`), distinguishing internal tooling state from project source code.
- **Schema Versioning**: Nodes carry `schema_version` (currently **v3**). `detect_schema_drift()` tracks schema health across versions (v1 base, v2 `issues`/`plan`, v3 `verification`).
- **Hash-Chain Ledger Integrity**: Multi-agent shared SQLite databases (`labyrinth.db`) use SHA-256 hash chaining (`sha256(prev_hash + canonical_json(content))`) across `messages`, `kv_store`, and `claim_links`.
- **Graph Compiler (`lab_compile.py`)**: Standalone tool `clients/lab_compile.py` parses `artifacts/.lab/` into in-memory structures (`load_lab`), Mermaid diagrams, structured JSON, or interactive single-file HTML graphs (`--format html`).

---

## The Ontology Stack & Six Measured Quantities

```
Environment          the repo/world being modeled; not owned by Labyrinth
      ↓
Predictive State     what the graph expects to observe (named)
      ↓
Observed State       claims, graph, evidence, context (Level 1 State)
      ↓
Prediction Error     the comparison of Observed vs. Predictive State
      ↓
Actions              Evolve · Plan · Progress · Review · Prune (Level 2)
      ↓
Regulation           Adapt · Seal (Level 3)
```

Graph health is quantified across **six terms**:

1. **Coverage**: Adversarial pair — $C_{struct} = \text{nodes / artifacts}$ and $C_{ver} = \sum w_i \cdot \text{verified}_i / \sum w_i$ (driven by `sources_resolve` + `reproducible`).
2. **Mismatch Vector**: Omission, Redundancy, Disconnection, Staleness, Contradiction (`None` if detector missing, NEVER `0`).
3. **Complexity**: Null-model normalized Fano factor degree irregularity (`var/mean`, reference 1.0) and Depth (`diameter / (ln n / ln ⟨k⟩)`, reference 1.0).
4. **Information**: Preserved via Rule 1 (Conservation).
5. **Predictive Accuracy**: Named, unbuilt (blocked on Predictive State).
6. **Cost**: Named, unbuilt (tracks runtime/tokens/memory).

**Objective Function $J$**: A single scalar over normalized quantities (lower is better).

---

## Information Dynamics & Graph Convergence Objective

Labyrinth unifies context evolution around three signs of prediction error:
* **Positive Surprise (Novelty)**: Surfacing new context ➔ branch / **Evolve** (exploration).
* **Zero Surprise (Repetition)**: Redundant context ➔ merge / compress / **Prune** / promote.
* **Negative Surprise (Omission)**: Missing context ➔ generate / fill structural gaps.
* **Graph Convergence Objective**: Drive the graph toward low degree variance and low graph diameter (exempting legitimate hub nodes like `mission`/root/verb nodes).

---

## Three Immutable Rules

1. **Conservation**: Reduction (compress, supersede, prune) is valid ONLY if prior state remains recoverable from history or checkpoint (hash-chained in SQLite, git-history backed in `.lab/`). Compact the live graph, never erase historical record.
2. **Reflexivity of Amendment**: A rule change must clear the bar the rule itself demands. Two-tier floor:
   - *Doctrine/Vision Tier* (`CLAUDE.md`, `AGENTS.md`, global memory): ALWAYS requires explicit human approval — no agent-confirmation substitute, ever.
   - *Skill/Memory-File Tier*: Requires independent multi-agent confirmation before the human gate.
3. **No Goal Without a Falsifier**: Every plan or project-level goal must state what "closed" (falsifier condition) means before it can Seal or Prune. Enforced strictly in `save(kind="goal", val={"text":..., "falsifier":...})`. (`mission` is exempt by being `kind="decision"`).

---

## The 3-Level System Model

Labyrinth organizes project context, workflow actions, and self-modification into three levels:

```
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 1: STATE (Things that exist)                                    │
│   • Claims, Graph, Evidence, Context                                  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 2: ACTIONS (Things agents deliberately perform)                 │
│   • Evolve, Plan, Progress, Review, Prune                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ LEVEL 3: REGULATION (Things governing the action system itself)        │
│   • Adapt, Seal                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Level 1: State

* **Graph Nodes**: Represent context items (claims, concepts, backlog items, documentation, source modules) with schema v3 (`id`, `kind`, `title`, `generated`, `status`, `notes`, `issues`, `plan`, `verification`).
* **Edges & Relations**: Explicit connections carrying reasoning and confidence (`supports`, `contradicts`, `derives_from`, `questions`, `refines`). Confidence updates on **causal pressure**.
* **Claim Kinds**: `hypothesis`, `evidence`, `goal` (requires falsifier), `plan`, `reflection`, `question`, `note`, `decision`, `checkpoint`.
* **Evidentiary Standing**: `unconfirmed` ➔ `provisional` ➔ `confirmed` (`CONFIRMATION_THRESHOLD = 2`), `contested`, `superseded`.

---

## Level 2: Fundamental Actions

### 1. Evolve (`Proceed-with-Evolve`)
- **What**: Generate new context from existing context (crossover, mutation, synthesis, abstraction, hypothesis formation, analogy, decomposition). (Exploration half of learning loop).

### 2. Plan (`Proceed-with-Plan`)
- **What**: Commit to intention, design, or structure from raw or evolved material. Break goals down into concrete, actionable steps. Incorporates exploratory inputs (Brainstorm retired as a peer node).

### 3. Progress (`Proceed-with-Progress`)
- **What**: Execute and record real work, backed strictly by empirical evidence (*No receipt, no claim*).

### 4. Review (`Proceed-with-Review`)
- **What**: Evaluates **epistemic status** ("is this true?"). Independently evaluates and scores node/edge state against real repo outputs.

### 5. Prune (`Proceed-with-Prune`)
- **What**: Evaluates **structural utility** ("is this still necessary?"). Shrinks working set in a provably terminating loop: **Balance** (structural check) ➔ **Compact** (collapsing redundant clusters into a canonical node + cross-refs based on similarity **and** coverage).

---

## Level 3: Regulation Actions

### 6. Adapt (`Proceed-with-Adapt`)
- **What**: Modify the process itself, including the action list, rules, skills, or `AGENTS.md`. (Exploitation half of learning loop). Propose-only for `CLAUDE.md`/`AGENTS.md`/memory.

### 7. Seal (`Proceed-with-Seal`)
- **What**: Checkpoint a stable, clean, restorable state before session handoffs or major milestones.

---

## Standalone Quickstart & Graph Compiler

To map any repository to the Labyrinth graph format without running an external server:

```powershell
python C:\Users\nejath\.gemini\antigravity\scratch\labyrinth\clients\repo_mapper.py --target C:\path\to\your\repo
```

To compile and inspect `artifacts/.lab/` graphs into Mermaid diagrams, structured JSON, or interactive HTML graph views:

```powershell
python C:\Users\nejath\.gemini\antigravity\scratch\labyrinth\clients\lab_compile.py --target C:\path\to\your\repo --format html
```
