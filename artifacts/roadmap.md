# Roadmap

Work deferred past the cycles the todo stack holds, one row per item. An item moves into the
todo stack, with its full text, when its cycle opens; it is never in both files.

A row is `| id | theme | defect | waits | deferred-X.Y.Z |`: the item id, a short theme, the
defect in one line, the reason it waits (AGENTS.md section 11), and the cycle it is deferred to,
later than the declared version. `scripts/release_gate.py` STEP 0a refuses any row that breaks
this form, and `scripts/fact_gate.py` counts each row's id as a live item. Rows are grouped by theme;
within a theme they run in the order listed, dependencies first. A theme ending in `(validation)`
marks a validation, which the dashboard lists as not started.

The full text of each item carried here from the todo stack is in
`artifacts/archive/0.2.10/todo_stack_0.2.10.md`, the stack as it stood when this file opened.

## Laminar validation

Ground truth for vflip2, xflip's null and the curation path.

| ID | Theme | Defect | Waits | Release |
|---|---|---|---|---|
| 15-11 | `vflip2` recovers a planted vFLIP2 crossover on Andre Bastos's simulation code (validation) | The generator half landed in 1dbcedbf (`artifacts/evidence/0.2.13/vflip2_recovery.md`: recovery 29 of 100, matched null 24 of 100); the same table has not run on his code, under the contract in `artifacts/evidence/0.2.13/vflip2_generator_design.md`; full text: `git log -S '### 15-11' -- artifacts/todo_stack.md`. | His simulation code; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-19). | deferred-0.2.15 |
| 16-12 | Dashboard real-data cards for `isi_cv` (9,056 units), WaveMAP and the omission results (validation) | The dashboard ships with the four committed GLO entries; the others need a receipt computed without calling jnwb: the omission and WaveMAP receipts record jnwb calls (`jnwb_version`, `jnwb_wavemap_commit`), and the `isi_cv` receipt file (branch `claude/site-overview-326890`, commit 9b52c5e7) no longer exists | Independent recomputations with committed receipts; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23). | deferred-0.2.15 |
| 12-21 | jnwb recovers a planted delay and a planted direction from a jaxfne field (validation) | The spectrum half landed (`tests/test_jaxfne_ground_truth.py`: `compute_psd` recovers the planted 10.0 Hz of jaxfne's protocol_c planar field, commit 21c99f96); a single-frequency field has no phase-slope delay and no direction, so delay (`phase_slope_index`) and direction (`granger`) wait for a broadband jaxfne field | A broadband jaxfne field with a stated delay or coupling; nothing shipped changes. Moved to 0.2.15 (ruled 2026-10-23: the spectrum test closes the item for 0.2.14). | deferred-0.2.15 |

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
