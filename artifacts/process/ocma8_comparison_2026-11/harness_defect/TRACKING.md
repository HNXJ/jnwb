# Harness defect: the shell guard `block_python_stdin.py` is not invoked on vwin-pc

Owner of the repair: the harness keeper. The pilot delivers and tracks only (Hamm 2026-11-16). The four
events below are separate; none implies the next.

| Event | State | Evidence |
|---|---|---|
| Delivered | done 2026-11-16T16:03:36Z | jarness issue 16 (`https://github.com/HNXJ/jarness/issues/16`, private repo, label `bug`, opened through `gh` as HNXJ); body equals `packet.md` (one trailing blank line added by GitHub). jchat route unavailable: hub 127.0.0.1:8780, relay 127.0.0.1:8770 and the tailnet hub answered curl code 000 at 16:03Z |
| Acknowledged by the keeper | not yet | at 2026-11-16T16:10Z the issue's one comment is the reporter's addendum (`issue16_addendum.md`: the settings file's last write postdates the first unrefused command); a comment by HNXJ is not by itself the keeper's acknowledgement, read its text |
| Implemented | not yet | none |
| Verified (regression tests red first, standalone and compound forms, permitted controls, a reviewer other than the writer) | not yet | none |

Ownership is stated in the issue title and body; the issue has no assignee, because the keeper is an agent
profile and the repository has one GitHub account.

Evidence files: `packet.md`, `runs_orchestrator.txt` (13 commands), `runs_subagents.txt` (6 commands),
`pattern_check.txt`, `wired_hooks.txt`, `friction_summary.txt`, and the scripts that wrote them.

Until verified: the pilot's rule against `python -c`, `python -` and heredoc code is enforced by instruction
only on this machine. Keeper dispatch overhead against the 30-minute cap is a separate open gate, deferred by
Hamm; compliance is not inferred from earlier worker timings.
