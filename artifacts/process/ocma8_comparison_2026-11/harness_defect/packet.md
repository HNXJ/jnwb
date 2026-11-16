Owner: the harness keeper (`jynx-claude-keeper`). Reporter: the OCMA-8 pilot orchestrator (Claude session
30cef652, host vwin-pc / ASBL-BASTOSI9). Authorised by Hamm 2026-11-16: delivery and tracking only. The reporter
changed nothing in the harness, in `~/.claude/settings.json` or in any hook, and built no workaround.
Delivered here because the jchat hub (127.0.0.1:8780), the relay (127.0.0.1:8770) and the tailnet hub gave no
HTTP answer (curl code 000 on each, last at 2026-11-16T16:03Z; no listener on either local port).

## Defect

On vwin-pc the mandatory shell guard `block_python_stdin.py` does not refuse the interpreter-on-stdin and
`-c` forms. In one session, 19 shell commands holding `python -c ...` or `python - ...` ran with no refusal:
13 from the orchestrator and 6 from its subagents, 2026-11-15T13:32Z to 2026-11-16T15:12Z. Two of the 19 start
the command (standalone); 17 sit inside a compound command (after `;`, `&&`, `|`, inside `$(...)`, after an
environment assignment). Two orchestrator commands with a bare `python -` hit the 120 s tool timeout.

## Evidence (all read-only; files beside this packet in the pilot record, see "Where")

| Observation | Status | Source |
|---|---|---|
| 19 commands ran, none refused (`is_error` false, normal output) | observed | `runs_orchestrator.txt`, `runs_subagents.txt` (`find_stdin_runs.py` over the session transcript and its 77 subagent transcripts) |
| The installed hook's own `PATTERN` matches 19 of the 19, matches 8 of 8 forbidden control forms (standalone and compound) and 0 of 5 permitted controls | observed; the hook was not run, only its two pattern assignments were compiled | `pattern_check.txt`, `pattern_check.py` |
| `~/.claude/settings.json` (mtime 2026-11-15T12:15 local) wires `PreToolUse` `Bash\|PowerShell` to `git_guard.py` and `run_guard.py` only; `block_python_stdin.py` is absent. jarness `harness/README.md:27` lists all three and calls this hook mandatory (line 45) | observed | `wired_hooks.txt` (`list_hooks.py` prints script names only) |
| `~/.claude/friction.jsonl`: every `block_python_stdin` rule last fired on or before 2026-11-15T01:12:10Z (`python_c`: 2,513 rows, last then); `git_guard` and `run_guard` rows continue through 2026-11-16 | observed | `friction_summary.txt` (`friction_scan.py`, no command text) |
| The installed `~/.claude/hooks/block_python_stdin.py` (mtime 2026-11-15T09:59 local, sha256 1de870626f37a3a4...) differs from the copy in the `D:/repos/jarness` worktree at `main` d21047c (first difference at line 145) | observed; which is newer is unknown | `cmp` |
| Cause: the hook is not invoked at all since about 2026-11-15, because its wiring is missing from the user settings; the pattern itself handles compound forms | inferred from the four rows above, not proven; when and how the wiring was lost is unknown; a plugin or managed-settings route for the hook was not checked |  |

Earlier statement corrected: the pilot record said the guard blocks the standalone form and misses the
compound form. The transcript shows the standalone form also ran (2026-11-15T13:32:51Z and one subagent
command). The other mandatory hooks of that README row were not checked beyond the list in `wired_hooks.txt`.

## Required of the repair (Hamm 2026-11-16)

1. Address the underlying guard bypass, including the forbidden interpreter forms embedded in compound shell
   commands. If the cause is the wiring (inferred above), the repair covers how a mandatory hook can drop out
   of the settings unnoticed (installer, self-check or session start), not only this machine's file.
2. Regression tests, red first: each test is shown failing before the repair. Forbidden forms refused both
   standalone and inside compound commands (`;`, `&&`, `||`, `|`, `$(...)`, after an environment assignment,
   with `</dev/null`, with a heredoc). A test that the wired settings invoke the hook, not only that the
   pattern matches.
3. Negative controls: permitted commands still pass (`python script.py -c x`, `python -m pytest -c x`,
   `python path/file.py - <in.txt`, plain `git` and `ls` commands).
4. Report acknowledgement, implementation and verification as separate events on this issue. The reporter
   verifies nothing by trying the forbidden forms; verification is the keeper's, with a reviewer other than
   the writer.

Not asked: any change to the pilot, to its frozen T2 instrument, or to this reporter's session.

## Why it matters to the pilot

The pilot's worker packets forbid these forms and rely on the guard to enforce it. Six subagent commands,
one of them from the freeze reviewer, ran them anyway. Pilot execution stays withheld by Hamm; this defect is
one of its open operational gates.

## Where

Pilot record: `HNXJ/jnwb`, branch `_temp_ocma8_pilot`,
`artifacts/process/ocma8_comparison_2026-11/harness_defect/` (this packet, the four scripts, their outputs).
Tracking of delivery, acknowledgement, implementation and verification: `TRACKING.md` in the same folder.
