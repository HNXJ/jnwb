# Release checklist, 0.2.17

100/100 means the cycle is done: every scope row closed, every acceptance condition of `AGENTS.md` §11
holding at the tip of `dev`. Score = scope points + acceptance points. A row earns its points in proportion
to its closed items; an acceptance line earns all or nothing. Update a row in the commit that closes its
item (minor update); rewrite the whole checklist after the release (major update). Scope source:
`artifacts/process/release_plan.json`, item text: `artifacts/todo_stack.md`.

Scored 2026-11-18 at `b442e2b1`: **5/100** (acceptance 5; scope 0 of 60, no item closed).

## Scope (60)

Closed items leave the todo stack and the plan's `items` list, so "closed" is read from both.

| # | Row | Pts | Items | Closed | Earned |
|---|---|---|---|---|---|
| S1 | The largest functions split below a stated complexity | 10 | 17-79 | 0 of 1 | 0 |
| S2 | One home per helper; dead code and unused constants removed | 10 | 17-94, 17-95, 17-96, 17-142 | 0 of 4 | 0 |
| S3 | Tests and scripts that can fail, named by subject, free of process vocabulary | 10 | 17-97, 17-98, 17-147, 17-150 | 0 of 4 | 0 |
| S4 | Docs and examples thinned; one home per invariant; pointers resolve | 10 | 17-99, 17-100, 17-101, 17-102, 17-103, 17-151 | 0 of 6 | 0 |
| S5 | Code and prose matched to the style standards; the fact graph build faster | 10 | 17-104, 17-127, 17-128, 17-129 | 0 of 4 | 0 |
| S6 | Validations on external ground truth | 10 | 17-144, 15-11, 12-21, 16-12 | 0 of 4 | 0 |

In flight at the score: 17-103 (committed in a lane, not merged), 17-95 (running), 17-147 (guard and
registry work pushed; scripts-2, the tolerance test and the guard gaps remain).

## Acceptance (40)

| # | Condition | Pts | Check | Now |
|---|---|---|---|---|
| A1 | The open stack holds no row | 10 | `artifacts/open_stack.md`, `tests/test_release_requires_an_empty_open_stack.py` | 0 (six rows) |
| A2 | Full suite 0 failed at the tip of `dev`, and CI green at that SHA | 10 | `bash scripts/jnwb_suite.sh`, `gh run list` | 0 (suite green at `9479505e`; CI success at `b442e2b1`, runs 44403457956 and 44403468332; both are tips of an unfinished cycle) |
| A3 | Documentation low-verbosity and consistently formed | 5 | `python scripts/harness_gate.py` 22 of 22, `python scripts/docs_build.py` strict | 5 (harness gate passed at `9479505e`; docs build not run) |
| A4 | Code low-complexity: no function above 40 | 5 | cyclomatic scan of `jnwb/` (item 17-79) | 0 (13 above 40 at `93fd20e1`) |
| A5 | `scripts/release_gate.py` passes its STEP 0 checks | 5 | `python scripts/release_gate.py` | 0 (not run) |
| A6 | An independent closure pass finds no new blocker, and each advertised claim is checked against the deferred rows | 5 | a `reviewer` run on the tip, report in `artifacts/evidence/` | 0 (not run) |

A3 is scored 5 on the harness gate alone; the strict docs build, once run, can lower it.

## Update log

| Date | SHA | Change |
|---|---|---|
| 2026-11-18 | `b442e2b1` | Created. Score 5/100. |
