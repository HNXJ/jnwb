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
  repair: for the suite process only, point `GIT_CONFIG_GLOBAL` at a temp config with `safe.directory = *` (do not write the user's gitconfig); pass a same-drive `--basetemp`
  evidence: suite at `d898cd17` 2026-11-12: mutation test failed without it; 10864 passed with it and `D:/pytest_temp/jnwb_bt_suite`
  scope: full `jnwb_suite.sh` on this workstation when `.git` ownership differs from the user
