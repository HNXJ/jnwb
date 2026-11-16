Reporter's addendum (same session, read-only; no acknowledgement implied).

`~/.claude/settings.json` on vwin-pc was last written 2026-11-15T18:15Z (12:15 local). The OCMA-8 pilot proposed a hooks patch that only adds `SubagentStart` and `SubagentStop` entries for `subagent_log.py` (pilot record, `settings_hooks_proposed.diff`: one hunk, additions only, no line removed). That the 18:15Z write is this patch is inferred from the time and the file's present content. The first unrefused command in the evidence is at 2026-11-15T13:32Z and the hook's last logged refusal at 01:12Z, both before that write, so the wiring was lost between 01:12Z and 13:32Z on 2026-11-15 by something else (unknown). A backup `settings.json.bak-20261028-172509` exists beside the file; not read.

Pilot status for context: the OCMA-8 instrument is frozen and the pilot is not executed; this issue is tracked from `harness_defect/TRACKING.md` in the pilot record and nothing waits on the reporter.
