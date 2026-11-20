# jnwb `dev` local qualification at fabe3c02 (2026-11-16)

Authorized by Hamm 2026-11-16 (main-vwin, Option 1): local qualification only; no CI re-enable. Hamm accepted the
result as local evidence and authorized this record's push to a `_temp_*` branch based on `fabe3c02` (2026-11-16).
Status: **local qualification, not CI verification**. Written 2026-11-16T16:40:44Z. The record adds files under this
folder only; the qualified source tree is unchanged. 17-143 stays open (Hamm 2026-11-16).

## Revision and inputs

| Item | Value |
|---|---|
| Revision | `fabe3c021f26a0b8d8d9b5fe0ceb33cdc26986b0` (`origin/dev`, fetched over HTTPS) |
| Tree | `D:/repos/_work/_temp_jnwb_qual`, a fresh `git clone https://github.com/HNXJ/jnwb.git`, branch `dev`; tracked tree clean before and after; HEAD did not move (the suite script wrote its stamp for this SHA) |
| Baseline | `9252d0cd`, the last `dev` SHA with CI runs (CI/CD and dashboard, success, 2026-11-13T16:22Z); tree `D:/repos/_work/_temp_jnwb_qual_base` (`git clone --shared` of the tree above, origin set to the HTTPS remote) |
| Host | vwin-pc, Windows 11 (10.0.26300), Git Bash MINGW64 3.4.10 |
| Interpreter | `C:/Python314/python`, Python 3.14.3; packages in `env_pip_freeze.txt` (numpy 2.4.6, scipy 1.18.0, pandas 3.0.5, pynwb 3.1.3, hdmf 4.3.1, h5py 3.16.0, pytest 9.0.2, pytest-xdist 3.8.0) |
| jnwb import | site-packages holds jnwb 0.2.11; the suite imports the clone through `pythonpath = ["."]` in `pyproject.toml` (inferred from the pytest configuration, not printed) |
| Data | no NWB volume named; tests that need absent inputs skip (82 skipped) |

## Results

| Check | Command | Result |
|---|---|---|
| Suite at `fabe3c02` | `bash scripts/jnwb_suite.sh <tree> <log> D:/pytest_temp/jnwb_qual_fabe3c02` (doc-form tests, state rebuild and check, `pytest tests/ -q -n 12` under the suite lock) | `10885 passed, 82 skipped, 38 xfailed, 1509 warnings, 36 subtests passed in 692.87s`; rc 0; 0 FAILED or ERROR lines |
| Suite at `9252d0cd`, same machine | same script | `10864 passed, 82 skipped, 38 xfailed, 1514 warnings, 36 subtests passed in 636.31s`; rc 0 |
| Harness gate at `fabe3c02` | `python scripts/harness_gate.py` after `reconstruct_state.py --check` (rc 0) | `ALL HARNESS GATES PASSED. 22 of 22 gates executed.`; rc 0 |
| CI at `9252d0cd`, for reference | Actions job logs, Windows legs | Python 3.14 and 3.13: `10849 passed, 95 skipped, 38 xfailed` |

Regressions against the baseline: none. Failures at either revision: none, so no pre-existing failure exists to
separate. The head adds 21 passing tests and `tests/test_push_guard.py` collects 32 tests at the baseline and 53 at
the head, which accounts for all 21. Local against CI at the baseline: 13 fewer skips and 2 more collected items
locally (10946 against 10944 passed plus skipped); the cause is the environment and was not itemized.

## 17-143 closing predicate

Predicate (`artifacts/todo_stack.md` at `fabe3c02`): `jnwb_push.sh <dir> --tag vX.Y.Z` pushes a `v*` tag only at
`origin/main`'s tip with a successful main CI/CD run of that SHA, else refuses; an artifacts-only push with a bare
directory in `Writes:` is refused; guard tests cover each. Ruled 2026-11-09: an artifacts-only push first runs gate 15
and `tests/test_stack_item_length.py`.

| Condition | Code | Test (in `tests/test_push_guard.py`) | State |
|---|---|---|---|
| Tag name is `vX.Y.Z` | `scripts/jnwb_push.sh:26` | `test_tag_name_must_be_vX_Y_Z` (4 cases) | met |
| Tag goes only to `origin/main`'s tip | `:28-29`, `:41-49` | `..._pushes_the_tag_at_main_tip_...`, `..._newest_main_run_is_not_at_the_tip`, `..._origin_main_moves_during_the_CI_read` | met |
| A successful main CI/CD run of that SHA, else refuse | `:35-44`, `scripts/ci_gate.py --require-name` | `..._a_main_run_at_the_tip_failed`, `..._no_successful_CI_CD_run`, `..._an_unreadable_main_answer`, `test_the_override_does_not_reach_a_tag_push` | met |
| An existing tag is never moved | `:30-32` | `test_tag_push_refuses_to_move_an_existing_tag` | met (beyond the predicate) |
| Artifacts-only push with a bare directory in `Writes:` refused | `scripts/verify_lane.py` `_bare_directory`, `push_check` | `test_artifacts_only_push_refuses_a_bare_directory_in_writes`, control `..._with_a_file_in_writes_passes` | met on the `--item` route only |
| Artifacts-only push runs gate 15 and the item-length test | `scripts/jnwb_push.sh:76-88` | `..._refuses_when_the_stack_gate_fails`, `..._refuses_when_the_item_length_test_fails` | met |
| Guard tests cover each | | 21 new tests; all 53 pass at the head | met |

Red check: the head's `tests/test_push_guard.py` on the baseline code gives `18 failed, 35 passed`
(`red_17-143_tests_on_9252d0cd.txt`). Of the 21 new tests, 18 fail there and three pass, identified by absence from
the FAILED list: the permitted control `..._with_a_file_in_writes_passes`; the guard case
`git --namespace=foo push origin dev` (a 17-147 case the old pattern already denied); and
`test_the_override_does_not_reach_a_tag_push`, which the old script satisfies by refusing `--tag` as an unknown
branch (inferred from the old script, `not on $branch`), so that test alone does not separate old code from new.

Disposition: **predicate met locally; row not closed.** Closing deletes the row on `dev`, which is a push, and the
stack's wave barrier asks for CI green on `dev` at the SHA; neither is possible under the current ruling and with
workflows disabled.

Limits of the predicate as built:

- The bare-directory refusal runs only when the caller passes `--item <id>`; a plain `jnwb_push.sh <dir> dev` does not
  read `Writes:` at all (`scripts/jnwb_push.sh:59-65`).
- The tag route was exercised on a scaffold repository with a local CI stub, never against the real origin.
- Read-only live call from the head: `python scripts/ci_gate.py hnxj/jnwb main --require-name "CI/CD"` prints
  `pass 0aa220ba: 1 completed run(s) succeeded`.

## Newly exposed

| Item | Evidence |
|---|---|
| The branch route's CI condition passes on a stale SHA | `python scripts/ci_gate.py hnxj/jnwb dev` prints `pass 9252d0cd: 2 completed run(s) succeeded` while `origin/dev` is `fabe3c02`; the branch route (`jnwb_push.sh:91`) does not compare the gate's SHA with the branch tip (the tag route does, `:41-44`). With workflows disabled every later push passes this condition without a run. |
| No CI run reads the 14 commits `9252d0cd..fabe3c02` | workflows `CI`, `CI/CD`, `dashboard` are `disabled_manually`; the three 17-143 code commits among them |
| The canonical local clone cannot fetch | `D:/repos/jnwb` is at `9252d0cd`; its SSH remote fails, `~/.ssh/id_ed25519_github_agent` is missing |

## Files here

`suite_fabe3c02.log.txt` (sha256 starts `8a2fd41c7f9adaee`), `suite_fabe3c02.wrapper.txt`, `suite_9252d0cd.log.txt`,
`suite_9252d0cd.wrapper.txt` (the two logs carry `.txt` because `*.log` is ignored), `harness_gate_fabe3c02.txt` (sha256 starts `51a1506a3288c301`),
`red_17-143_tests_on_9252d0cd.txt`, `env_pip_freeze.txt`.
