# Integration of 17-152 and closure of 17-143 (2026-11-16)

CI/CD was re-enabled alone (Hamm 2026-11-16); `dashboard` and `CI` stay `disabled_manually`.
Every push went through `scripts/jnwb_push.sh`. `main` stayed at `0aa220ba`.

| Step | `dev` SHA | CI/CD run | Event | Conclusion |
|---|---|---|---|---|
| Dispatch at the old tip, target `none` | `fabe3c021f26a0b8d8d9b5fe0ceb33cdc26986b0` | 43962681789 | workflow_dispatch | success |
| Push the gate repair (17-152), no override | `4dfb398d3cfc19c1844b02d60bca2d01be7948b4` | 43971841378 | push | success |
| Push the row closures, artifacts-only route | `152b36b53e997fda62675a76f3f50568eb6467a8` | 43982730024 | push | failure |
| Push the fix, `JNWB_PUSH_OVER_RED=1` (Hamm approved this push) | `fef42bf6aa2f58b930ab4a0c1dba1589865dc612` | 43990836160 | push | success |

In each successful run every test leg and the build job concluded success and every publish job
was skipped.

Exact-SHA check before the 17-152 push: `ci_gate.py hnxj/jnwb dev --tip <fabe3c02>` printed
`pass fabe3c02: 1 completed run(s) succeeded`; asked about `4dfb398d` before its run existed it
printed `refuse: no run at the branch tip 4dfb398d; no run is listed` (exit 1).

## The red run

`152b36b5` deleted todo 17-143 and left it in the 0.2.17 items of
`artifacts/process/release_plan.json`. `scripts/build_dashboard.py` raised "0.2.17 names 17-143,
which no stack contains"; `tests/test_build_dashboard.py` gave 10 failed and 27 errors on every
leg, and nothing else failed. Cause of the miss: the closure was checked with the harness gate
and the 14 test files that name the stacks, not the full suite, and the search for the item id
skipped `.json` files. `fef42bf6` removes the item from the plan; on it the file gives 84 passed
and the full local suite 10901 passed, 82 skipped, 38 xfailed.

## 17-152 evidence

`17-152/` holds the red runs (new tests on `fabe3c02`, review tests on `f967d2ee`, `total_count`
cases on `00f1d022`), the suite wrapper outputs, the final suite log and harness gate at `4dfb398d`.

## The record on `dev` (Hamm 2026-11-16: merge the complete record, then delete the branch)

Branch `_temp_dev_qual_20261116` (tip `5d6e05f994ff1035118fab922f8b30689382d962`) was merged as
`5fcb1428`; `51c7ef48d3e0f9a874ff22f802a567bdb8979add` then set `env_pip_freeze.txt` to LF, because
its mixed line endings failed gate 16 and three tests on the merge (lines unchanged). Pushed
through the wrapper with no override. CI/CD run 44004557410 (push) at `51c7ef48` concluded success:
every test leg and the build job, every publish job skipped. The 56 files of this folder are the
whole record; nothing outside it changed between `fef42bf6` and `51c7ef48`. The branch was deleted
on the remote after that run; `_temp_17-152_ci_gate_tip` and the fix checkpoint
`_temp_fix_release_plan_17-143` were deleted when they merged. The commit that adds this section
is tested by its own CI run, which this file cannot name.
