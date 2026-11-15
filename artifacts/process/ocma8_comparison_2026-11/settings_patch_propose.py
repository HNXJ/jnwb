"""Propose, never apply, the minimal settings.json change that restores subagent telemetry (jarness P-26).

Usage: settings_patch_propose.py <settings.json> <backup settings.json> <out.diff>
Reads both files, copies the SubagentStop and SubagentStart groups that run subagent_log.py from the backup into
a copy of the current "hooks" block, and writes a unified diff of that block alone (no other key is read out).
It writes only <out.diff>.
"""
import difflib
import json
import sys
from pathlib import Path

cur_p, bak_p, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
before = json.loads(cur_p.read_text(encoding="utf-8")).get("hooks") or {}
backup = json.loads(bak_p.read_text(encoding="utf-8")).get("hooks") or {}
after = json.loads(json.dumps(before))
added = []
for event in ("SubagentStop", "SubagentStart"):
    groups = [g for g in backup.get(event, []) if any("subagent_log.py" in h.get("command", "") for h in g.get("hooks", []))]
    assert groups, f"backup must wire subagent_log.py on {event}"
    have = [h.get("command", "") for g in after.get(event, []) for h in g.get("hooks", [])]
    assert not any("subagent_log.py" in c for c in have), f"{event} is already wired"
    after.setdefault(event, []).extend(groups)
    added.append(event)


def dump(d):
    return json.dumps({"hooks": d}, indent=2).splitlines(keepends=True)


diff = "".join(difflib.unified_diff(dump(before), dump(after), "settings.json (hooks, current)", "settings.json (hooks, proposed)", n=2))
assert diff, "the proposal must change something"
out.write_bytes(diff.replace("\r\n", "\n").encode("utf-8"))
print("events before:", sorted(before), "after:", sorted(after), "added:", added)
print("lines added:", sum(l.startswith("+") and not l.startswith("+++") for l in diff.splitlines()),
      "removed:", sum(l.startswith("-") and not l.startswith("---") for l in diff.splitlines()))
