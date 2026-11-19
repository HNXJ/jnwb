# Handoff: main-jnwb, 0.2.17 readiness, 2026-11-18

Written for the agent that takes this over. Facts are from the repository at `9ad92d4b` (local `dev`,
two commits ahead of `origin/dev` `e3af332f`) and from this session's receipts; each is marked observed
unless it says inferred or unknown. The checklist, `artifacts/process/release_checklist.md`, holds the
score and its method.

## Result

Release readiness for 0.2.17: **2/100 verified** at `9ad92d4b` (suite 11021 passed, 0 failed; CI/CD success on
both runs; `origin/dev` = that SHA; provisional weights, not an authoritative score). No scope row is closed; no required gate is complete. Next release is far (observed:
19 todo items open, 6 open rows, `dev` still declares 0.2.16, last tag `v0.2.16`).

## Why the score is low

| Cause | Evidence |
|---|---|
| The cycle only just started | 22 plan items, 1 closed (17-103); 17-95 and 17-147 partly landed |
| The open stack must be empty at release | 6 rows, 4 need Hamm (`OCMA-5`, `17-144-src`, `17-152-over`, `17-147-gate15`) |
| Large unstarted work | 17-79 (five functions above 40; 13 above 40 at `93fd20e1`), 17-94, 17-104, 17-97, 17-98, 17-100 |
| External inputs missing | the three isi_cv commits (not on any host clone or bundle, per main-vwin); the Bastos simulation code; a broadband jaxfne field |
| Plan and todo disagree | 17-151 is in the todo stack, not in `release_plan.json` `items`; 17-147, 17-150 and 17-151 fit no plan scope line |

## Work done this session (all on `dev`, CI green at `e3af332f`)

17-147 part: `push_guard.py` rewritten as a linear scanner after five independent reviews (quoted and
absolute `git`, `GIT_DIR` env, `cd`/`pushd`, subshell and substitution scoping, quoted subcommand), with
192 tests in `test_push_guard.py` and `test_jnwb_push.py`; audit rows scripts-5 to -8 and tests-2, -4 (six of seven), -5, -6, -9; registry regenerated.
17-103 closed (not yet counted until the suite passes). 17-95 part: `stack_parse.cells`, `gates.boundary.git`.
Checklist, stack rows and this note are the artifacts of the session.

## Next, in order

1. Confirm the suite on `9ad92d4b` (queued behind other agents' suites on the machine lock); push `dev`
   through `scripts/jnwb_push.sh` only at 0 failed, then verify the remote SHA.
2. Take the eligible items: 17-79 (largest, needs calibration receipts unchanged), 17-97, 17-98, 17-100,
   17-104; finish 17-95's remaining sites. Each: failing-first test, independent `reviewer`, full suite.
3. Hamm rulings needed (one at a time): gate 15 (`17-147-gate15`), `17-152-over` policy, `OCMA-5` card specs,
   the plan/todo mismatch for 17-151 and the three unmapped items, the checklist's weights and AGENTS.md routing.

## Feedback

- Review loops are expensive on text-matching code: the push guard took six review rounds; each found a real
  hole or hang. A tokenizer over the shell grammar, or a deny-by-default allowlist of pushes, would end the
  class. The residual gaps are listed in row `17-147-guard`.
- A worker's targeted tests missed two whole-suite guards: a new test module without the wheel-leg
  `sys.path` guard (failed at `77e9682a`), and a code-hash registry made stale by a one-line edit (failed at
  `01f3cf16`).
  The agent and review definitions now name both checks (`artifacts/agents/jnwb-developer.md`,
  `artifacts/skills/jnwb-review/SKILL.md`).
- A reviewer misread its own probe output (column order) and called pre-existing misses regressions. The
  verifier definition now requires the baseline verdict beside the new one in one row.
- Machine contention: the suite lock serialised jnwb behind other agents for about 1 h per run; one run hung
  at about 99% for 1.5 h (row `17-147-hang`; cause unknown, not diagnosed). Capture the stuck test before
  killing a stalled run (`faulthandler_timeout`, `-v`).
- Do not create or remove a branch or worktree while a suite runs: gate 20 reads them and fails
  `test_every_gate_runs` (one run lost at `9ad92d4b`).
- `jnwb_push.sh` needs a local branch named `dev`; a gate-20 failure on an artifacts-only push is cleared by
  `python scripts/reconstruct_state.py` (the file is generated, never committed).
- Figure image comparison is not possible on this host (no Liberation Sans); fig26's stream equivalence rests
  on a seeded draw-sequence check.

## Do not

Push `main`, tag, publish, merge or close PR #44, change goal or fact stacks, decide the rows above, install
jnwb into the shared Python (0.2.11 stays; reinstalling downgrades pandas), or recreate the missing isi_cv
commits.
