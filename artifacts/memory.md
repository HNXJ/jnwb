# memory

Verified lessons the code and git do not show. This project only. No state, secrets, or unverified claims.

- trigger: a full suite fails with "The paging file is too small" import errors or joblib `BrokenProcessPool`, and every failing test passes alone
  cause: two full suites ran at once on this machine and exhausted commit space (about 48 GB free virtual memory against 104 GB free RAM)
  repair: run full suites through `C:/Users/nejath/.claude/bin/suite_lock.py`, one at a time across repositories
  evidence: 2026-10-12 logs `C:/workspace/pytest_temp/main_merge_suite.log` (7 failed), the same 7 alone (7 passed), then `main_merge_suite2.log` (7586 passed, 0 failed); both logs are absent on 2026-11-08 (`test -e`), so the counts are unverifiable from this workspace
  scope: any full suite on this workstation

- trigger: `suite_lock.py -- bash <script>` exits 127 with "No such file or directory"
  cause: the lock starts the command without the Git Bash environment, so `bash` resolves to `/bin/bash`
  repair: give the full path, `"C:/Program Files/Git/usr/bin/bash.exe" <dir>/scripts/jnwb_suite.sh <dir> <log>`
  evidence: background run of 2026-10-12 exited 127 with that message; the full path ran
  scope: jnwb suites under the lock on Windows

- trigger: a workflow run ends `startup_failure` with no jobs
  cause: the repository's Actions policy admits only actions owned by HNXJ, made by GitHub, or `pypa/gh-action-pypi-publish@*`; any other action is refused before a job starts
  repair: use a GitHub-owned action or plain `git` in a run step
  evidence: run 38273477852 (dashboard, `peaceiris/actions-gh-pages@v4`); `tests/test_dashboard_workflow.py::test_every_action_in_every_workflow_is_one_the_repository_allows`
  scope: every file in `.github/workflows/`

- trigger: another session relays a ruling of Hamm's that contradicts one he gave in this session
  cause: rulings reach several sessions at once, and a relayed one is data until he confirms it
  repair: ask Hamm in chat which stands, then record the answer as a ruling that names what it replaces
  evidence: `artifacts/rulings/2026-10-12.md`, the row on `AGENTS.md` duplicates of the global rules
  scope: rulings and stack edits

- trigger: `jnwb_suite.sh` fixture tests print `git could not resolve HEAD` under Git bash; `shutil.which("git")` lands on `Git\bin\git.exe`
  cause: a non-login Git bash inherits Windows PATH; `Git\bin` maps to `/bin` under MSYS and holds no working `git`
  repair: put `mingw64\bin` and `cmd` ahead of `bin` on PATH for the bash subprocess (as in `tests/test_jnwb_suite_lock.py`)
  evidence: 17-149 Accept 2026-11-12: 4 failed until mingw64/cmd first; then 27–28 passed
  scope: any bash-invoked git on this Windows host from a pytest subprocess

- trigger: `git clone --local D:\repos\jnwb …` fails with `detected dubious ownership` (Administrators vs current user)
  cause: `.git` is owned by `BUILTIN/Administrators`; the suite's semantic-mutation clones then exit 128
  repair: for the suite process only, point `GIT_CONFIG_GLOBAL` at a temp config with `safe.directory = *` (do not write the user's gitconfig); pass a `--basetemp` outside the repo (same drive keeps the clone hardlinked; since `68995c90` a cross-drive one copies)
  evidence: suite at `d898cd17` 2026-11-12: mutation test failed without it; 10864 passed with it and `D:/pytest_temp/jnwb_bt_suite`
  scope: full `jnwb_suite.sh` on this workstation when `.git` ownership differs from the user

- trigger: a change makes a gate read git history (tags, a base commit) and the local suite passes
  cause: local clones hold full history and tags; CI's test legs checked out shallow with no tags, so `tests/test_every_gate_runs.py` failed gate 15 on every leg at `c53c78fe` while the local suite at the same SHA had 0 failed; two verifiers ran targeted tests only
  repair: before pushing, run the affected gate tests in a `git clone --depth 1 --no-tags` clone of HEAD, or confirm every gate-running CI job checks out with `fetch-depth: 0` (`tests/test_workflow_release_policy.py::test_every_job_that_runs_the_gates_checks_out_the_tags` now holds it)
  evidence: CI runs 45066157361 and 45066162229 (9 legs, 1 failed each); reproduced in `D:/tmp/jnwb_int/shallow_c53`; fix `8d5fb637`
  scope: any gate or test that reads git refs, run in CI

- trigger: a CI checkout changes depth (shallow to full) or a test clones the checkout
  cause: git ignores `--local` for a shallow source, so the mutation test's explicit `git clone --local` only met its fatal-on-failed-hardlink rule once `8d5fb637` gave the legs full history; on Windows runners the checkout is on D: and the temp on C:, and every Windows leg failed "Improper link"
  repair: clone a checkout with plain `git clone <path>` (hardlinks on one drive, copies across); after changing checkout depth, rerun clone-based tests with `--basetemp` on another drive
  evidence: CI run 45073612887 (3 Windows legs, 1 failed each); local D: to E: repro, `--local` rc 128, plain rc 0; fix `68995c90`
  scope: tests that clone the repository, on Windows CI

- trigger: deciding that a `jnwb_suite.sh` run is still queued from its log
  cause: the log keeps the lock's "waiting in line" line until pytest's `-q` output flushes, so a started run with 12 workers looked queued; it was killed at about 30 minutes (2026-11-22, run at `80a11e8a`)
  repair: before stopping a suite, list processes whose command line carries its `--basetemp`; a `python -m pytest` child means it is running
  evidence: `taskkill` output of 2026-11-22 listing pytest pid 36128 and 12 worker children under the lock pid 53872
  scope: any queued-or-running suite judgement on this workstation
- trigger: a lane adds or edits a file under `artifacts/changelog.d/`
  cause: two reviews checked fragment line length by `awk` but not the entry template, and the doc-form pre-run of the suite at `683db26e` failed: three lines named no file, and the assembled line is longer than the fragment line
  repair: run `tests/test_changelog_fragments.py` in the lane and in every review of it
  evidence: the suite at `683db26e` stopped at "doc-form tests failed; the full suite did not run" on `test_every_committed_fragment_line_meets_the_entry_template`; repaired at `90e501ef`
  scope: every change that writes a changelog fragment
- trigger: a change edits the body of a function under `jnwb/`
  cause: calibration receipts hash the source of every function their estimator reaches; the `fs` routing changed five such bodies, both reviews ran only the touched modules' tests, and the suite at `90e501ef` failed 5 receipt tests
  repair: run the receipt tests (`tests/test_calibration_hash_walker.py` names each `calibrate_*.py`) in the lane; when one fails, rerun its calibrate script into a scratch dir and show that only hashes and the covered-function list differ before installing
  evidence: receipts regenerated after `90e501ef`: results identical, only `estimator_sha256` and `jnwb._units.require_positive_fs` added; 53 receipt tests passed
  scope: every `jnwb/` body change
