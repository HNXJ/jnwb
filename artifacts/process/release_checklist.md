# Release checklist, 0.2.17

A tracking artifact. It is not an authoritative release score until Hamm approves its scoring contract;
the release itself is decided by `AGENTS.md` §11 and `scripts/release_gate.py`, which this file does not
replace. Scope source: `artifacts/process/release_plan.json`; item text: `artifacts/todo_stack.md`.

**Done = 100/100**: every scope row closed and every required gate passing at the tip of `dev`. Update a
row in the commit that closes its item (minor update); rewrite the whole checklist after the release
(major update).

Current: **2/100** (2026-11-18, the commit that lands 17-103; see the update log). Gates 0 of 6 complete. Progress 2 of 60.

## Required gates (40): all-or-nothing, each complete only when every requirement passes

The release needs all six. A gate earns its 5 or 10 points only when complete; a part-pass earns nothing.

| # | Gate | Pts | Requirements (all) | State |
|---|---|---|---|---|
| A1 | The open stack holds no row | 10 | `artifacts/open_stack.md` empty; `tests/test_release_requires_an_empty_open_stack.py` | incomplete: six rows |
| A2 | Suite and CI green at the tip | 10 | `jnwb_suite.sh` 0 failed at the tip SHA; every `CI/CD` run at that SHA completed and succeeded | incomplete: suite green at `9479505e`, CI success at `b442e2b1` (runs 44403457956, 44403468332); neither at the final tip |
| A3 | Documentation low-verbosity and consistently formed | 5 | `harness_gate.py` 22 of 22; `docs_build.py` strict passes; docs-form tests pass; AGENTS.md §11 verbosity review | incomplete: harness gate 22 of 22 at `9479505e` is one requirement; docs build and review not run |
| A4 | Code low-complexity | 5 | no function above 40 by the item 17-79 measure | incomplete: 13 above 40 at `93fd20e1` |
| A5 | `scripts/release_gate.py` STEP 0 passes | 5 | `python scripts/release_gate.py` | incomplete: not run |
| A6 | Independent closure pass finds no new blocker | 5 | a `reviewer` run on the tip; each advertised scientific claim checked against the deferred rows; report under `artifacts/evidence/` | incomplete: not run |

## Weighted progress (60): provisional weights

Equal weights of 10 per row are a placeholder: the release plan states no weights. A row earns its points
in proportion to its closed items. An item counts as closed only when its todo heading and its id in the
plan's `items` list are gone, its change is merged on `dev` with the suite green, and an independent
reviewer accepted it. An item in flight earns nothing.

| # | Plan scope row | Pts | Items | Closed | Earned |
|---|---|---|---|---|---|
| S1 | The largest functions split below a stated complexity | 10 | 17-79 | 0 of 1 | 0 |
| S2 | One home per helper in jnwb, scripts and tests; dead code and unused constants removed | 10 | 17-94, 17-95, 17-96, 17-142 | 0 of 4 | 0 |
| S3 | Tests named by subject, not by the event that produced them | 10 | 17-97, 17-98 | 0 of 2 | 0 |
| S4 | Docs and examples thinned; one home per invariant | 10 | 17-99, 17-100, 17-101, 17-102, ~~17-103~~ | 1 of 5 | 2 |
| S5 | Code and prose matched to the style standards; the fact graph build made faster | 10 | 17-104, 17-127, 17-128, 17-129 | 0 of 4 | 0 |
| S6 | Validations on external ground truth | 10 | 17-144, roadmap 15-11, 12-21, 16-12 | 0 of 4 | 0 |

Closed items are struck through in the Items column. In flight: 17-95 (cells and the first git runner
landed; sites remain, item open), 17-147 (parts landed, item open).

## Mapping audit, 2026-11-18

Each todo item sits in one row. The release plan lists items without naming a row, so the row of each
item is an inference from the item's text and is open to correction.

| Finding | Evidence | Needs |
|---|---|---|
| Six rows are the six `scope` lines of the plan, in order | `release_plan.json`, version 0.2.17 | none |
| 17-147, 17-150 (scripts and tests that cannot fail) and 17-151 (public docs) fit no scope line | the plan's scope text names no such work | ruling: add scope lines, or fold into S3 and S4 |
| 17-151 is in `artifacts/todo_stack.md` marked `deferred-0.2.17` but not in the plan's `items` list | plan `items` has 22 ids, none is 17-151 | ruling: add it to the plan or re-mark it |
| 15-11, 12-21 and 16-12 are roadmap rows, not todo items | `artifacts/roadmap.md` lines 22 to 24 | none; counted as S6 items |
| 17-144 closes only when its three source commits exist | open row `17-144-src` | Hamm / jaxfne-orchestrator |
| S6 depends on inputs the plan lists as needs: the Bastos lab simulation code and a broadband jaxfne field | `release_plan.json` `needs` | Hamm |
| No item sits in two rows | each id appears once above | none |

Until the two rulings, 17-147, 17-150 and 17-151 earn no progress points and must still be closed for the
cycle (their `Release` mark), so a 60 in progress does not by itself mean the scope is done.

## Proposed AGENTS.md routing (not applied; AGENTS.md is Hamm's)

One row in the §2 project-state table: `| release checklist | artifacts/process/release_checklist.md | Agents update it as an item closes |`. No policy text moves into AGENTS.md.

## Update log

| Date | SHA | Change |
|---|---|---|
| 2026-11-18 | `b442e2b1` | Created. Provisional score 5/100 (acceptance 5 for the harness gate alone; scope 0). Superseded by the next row; kept as history. |
| 2026-11-18 | `b442e2b1` | Rescored 0/100. Gates are all-or-nothing, so A3 earns 0 while the docs build and review are open. Weights labelled provisional; mapping audited; conflicts listed. |
| 2026-11-18 | the commit that lands 17-103 | 17-103 closed (reviewer ACCEPT on 3a1a26c2; full suite on the landing SHA, see its push). S4 1 of 5; score 2/100. 17-95 stays open with a reduced bullet. |
