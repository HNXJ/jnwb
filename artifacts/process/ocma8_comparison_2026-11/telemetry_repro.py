"""Reproduction for the silent subagent log (vwin-pc, 2026-11-15). Usage: _temp_sublog_repro.py <session transcript> <agent id> <tmp dir>

Separates the candidate causes: (1) hook not invoked (settings.json wiring), (2) hook invoked but logging broken
(write, permissions), (3) parsing broken. Calls the installed hook's record() on a real finished agent with the
log redirected to <tmp dir>, then reads ~/.claude/settings.json for the two events.
"""
import json
import os
import sys
from pathlib import Path

home = Path.home() / ".claude"
sys.path.insert(0, str(home / "hooks"))
import subagent_log  # noqa: E402

session, aid, tmp = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
tmp.mkdir(parents=True, exist_ok=True)
log = tmp / "subagent_runs.jsonl"
for f in (log, tmp / "subagent_starts.jsonl"):
    if f.exists():
        f.unlink()
base = {"agent_id": aid, "agent_type": "worker", "transcript_path": str(session), "session_id": session.stem, "cwd": "E:\\omission"}

# (2)+(3): start row, stop row, then a resume's start and stop; ids must be aid.1 then aid.2, one row per event
subagent_log.record({**base, "hook_event_name": "SubagentStart"}, log=log)
e1 = subagent_log.record({**base, "hook_event_name": "SubagentStop"}, log=log)
subagent_log.record({**base, "hook_event_name": "SubagentStart"}, log=log)
e2 = subagent_log.record({**base, "hook_event_name": "SubagentStop"}, log=log)
rows = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines()]
print("stop rows:", len(rows), [r["run_id"] for r in rows])
print("row 1:", {k: e1[k] for k in ("run_id", "agent", "model", "s", "out", "fresh_in", "cache_read", "tools", "verdict")})
assert len(rows) == 2 and rows[0]["run_id"] == f"{aid}.1" and rows[1]["run_id"] == f"{aid}.2", "one row per stop, ids in order"
assert e1["out"] > 0 and e1["model"], "the hook must parse the transcript"
assert all(r["session"] == session.stem for r in rows), "attributed to the session"

# real log: writable, and untouched by this script
real = home / "subagent_runs.jsonl"
print("real log writable:", os.access(real, os.W_OK), "rows:", sum(1 for _ in real.open(encoding="utf-8")),
      "rows naming this agent:", sum(aid in l for l in real.open(encoding="utf-8")))

# (1): wiring
hooks = json.loads((home / "settings.json").read_text(encoding="utf-8")).get("hooks") or {}
for ev in ("SubagentStop", "SubagentStart"):
    cmds = [h.get("command", "") for g in hooks.get(ev, []) for h in g.get("hooks", [])]
    print(f"settings.json {ev}: {len(cmds)} hook(s); subagent_log wired: {any('subagent_log' in c for c in cmds)}")
print("settings.json hook events:", sorted(hooks))
