# Telemetry patch: applied, verified, failed one check, restored (2026-11-15)

Hamm 2026-11-15, option 1: add `SubagentStop` and `SubagentStart` (`subagent_log.py`) to `~/.claude/settings.json`
on vwin-pc with a dated backup; verify with a real subagent run; restore the backup if verification fails.
Scripts: `settings_patch_apply.py` (check, apply), `settings_hooks_proposed.diff`. No settings file is committed.

| Check | Result |
|---|---|
| Baseline equals the proposal's | pass: only `PreToolUse`, its 3 hooks; 3817 B; sha256 `44651d9d…61a4c3`; JSON round trip byte-equal |
| Backup | `~/.claude/backups/settings-json-before-subagent-log-20261115.json`, byte-equal to the original |
| Patch | 2 events added; every other key and hook equal on re-read; all hook script paths exist before and after |
| Existing hooks still run | pass: `git_guard.py` blocked a probe (`git branch zz_guard_probe`) after the patch |
| Real run, first dispatch (`worker`, agent `ade9393b0f61a8ab8`) | pass: 1 start row, 1 stop row, `run_id` `.1`, session `30cef652…`, model `claude-haiku-5-5`, `s` 10 (harness 10.4 s), `tools` 2 (harness 2), verdict `STOPPED` as reported |
| Resume of the same agent | start row `.2` with `parent_run_id` `.1`: pass. Stop rows: **2 rows with `run_id` `.2`** (17:45:42Z verdict null, 17:45:46Z verdict `PASS`): **fail, duplicate** |
| Negative control | agents that ran before the patch have 0 rows; the session has exactly these 3 stop rows |

## The defect (in `subagent_log.py`, not in the wiring)

- The harness fired `SubagentStop` twice in the resumed run: once when the agent ended a turn without its
  hand-back (payload holds `last_assistant_message`), once after the hand-back. `record()` appends a row at each
  firing, so one run has two rows; the log's readers count every row as a run.
- Second observation: `measure()` reads the whole transcript, so a `.2` row's `s`, tokens and tools are the
  agent's totals since its first start (`s` 31 against 6.9 s for the resumed run; `cache_read` 116,490 includes
  run `.1`). Summing rows per agent double-counts; the last row per agent is the agent's total.
- No payload field was missing; no value was invented.

## Second attempt, after the hook repair: passed (2026-11-15T18:17:15Z)

Hamm 2026-11-15: install only the repaired `subagent_log.py`, test concurrent writes first, roll back both files
on any failure.

| Step | Result |
|---|---|
| Concurrency before install (`telemetry_stress.py`, 8 processes x 40 runs, each stopped twice) | jarness 6733daf: 45 to 47 of 320 rows lost, 12 to 23 unparsable lines, `PermissionError`, 3 of 3 trials; serial control clean |
| Repair | jarness 9496736 (OS file lock around each hook event) and 79045ef (in-place rewrite when a reader refuses the swap), each from a red test; suite 784 passed, 20 skipped, 0 failed at 79045ef; three `reviewer` ACCEPTs, two with their own probes (0 missing, 0 duplicated with reader loops); on jarness `dev` 7a232a1 |
| Hook install | backup `~/.claude/backups/subagent_log-before-lock-20261115.py` (sha256 `0eca020c…c7c5d0`); installed file sha256 `a53b3132…7905a3`, equal to the reviewed file at 79045ef |
| Settings | backup `~/.claude/backups/settings-json-before-subagent-log-20261115b.json` (sha256 of the original); the same two entries; JSON valid; other keys equal |
| Existing hooks | `git_guard.py` blocked a probe branch after the patch |
| Real runs (`telemetry_verify.py`) | two fresh `worker` runs in parallel and a resume of one: 3 stop rows, 3 start rows, ids `.1`, `.2` (parent `.1`), `.1`; one row per run id; session, model, seconds (6, 19, 10 against the harness's 6.0, 4.4 for the resume, 9.9), tools and verdicts as reported; the 4,600 earlier stop rows and 620 start rows byte-identical |
| Duplicate stops against the installed file | `telemetry_stress.py` on a temp log: 320 of 320, 0 duplicated, 0 missing, 3 of 3 trials. Whether the harness fired twice in the real resume is unknown: the row is single either way |
| Independent check | a `worker` (Haiku 5.5) reran the verification on frozen copies of the logs and compared the hashes: PASS |

Limits: a `.2` row holds the agent's totals since its first start (`s` 19 covers both runs), unchanged by design;
the harness's `subagent_tokens` (29,189 for run `.1`) differs from the row's fresh input plus output (29,524) by
1.1%, its definition unknown; the installed hook now differs from the jarness install receipt (f7cdfb2), which
`selfcheck.py` will report until a `main` that holds the fix is installed; macOS not run.

## State after the first attempt

`settings.json` restored from the backup at 2026-11-15T17:47:06Z; sha256 equals the original. The three stop rows
and two start rows written during the test remain in the logs: they are real records. Prerequisite 1 of
`PREREG.md` is not passed. Repair belongs in jarness (the source of `subagent_log.py`, with a red test: two stop
payloads for one started run give one row), then install, then this verification again.
