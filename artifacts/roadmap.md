# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item. Rows are grouped by theme;
within a theme they run in the order listed, dependencies first.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

## Laminar validation

Ground truth for vflip2, xflip's null and the curation path.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 15-11 | `vflip2` recovers a planted vFLIP2 crossover on Andre Bastos's simulation code | The generator half landed in 1dbcedbf (`artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100); the same table has not run on his code, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`; full text: `git log -S '### 15-11' -- artifacts/todo_stack.md`. | His simulation code; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-19). | deferred-0.2.15 |
| 16-20 | A distance-aware coherence graph | `cross_area_coherence` and `network_topology` take a coherence matrix as it is, so a graph of nearby contacts or electrodes is dense from field spread alone; Nejat and Hajipour Sardouie 2021 normalize edge weights by distance and compare groups edge by edge (`docs/references.md`, Pitfalls) | raised during 0.2.14, after its scope was set (goal F3, ruled 2026-10-21) | deferred-0.2.15 |

## Fact closure

Items that hold UNHELD facts; signature types before the scans and holder fixes.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## Public API

Each needs Hamm's ruling before code.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## NWB reading edges

Reader and integrity edge cases.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## Consumers and docs

Use of jnwb from outside: a new dataset, a downstream agent, tutorial figures.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|

## Harness and gates

Gate reach before pruning; guards for the installed-wheel leg.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
