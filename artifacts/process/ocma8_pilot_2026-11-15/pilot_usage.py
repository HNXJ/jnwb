"""Token usage of the pilot's agents, read from their transcripts. Usage: pilot_usage.py <subagents dir>

The preregistered source, ~/.claude/subagent_runs.jsonl, holds no row after 2026-11-11 on this host, so the same
quantities are summed from the transcripts with the log hook's rule: one usage per message id, the last row of a
streamed message counts. Seconds are the harness's duration_ms of each run (task notifications), since a
transcript's first-to-last span includes the idle time of a resumed agent. Prints one CSV row per agent.
"""
import json
import sys
from pathlib import Path

AGENTS = [  # arm, role, agent id, active seconds per run (task-notification duration_ms / 1000)
    ("A", "worker", "aa846af9704616dab", [208.198, 152.950]),
    ("A", "reviewer", "a857329a20af94d8d", [136.506, 126.612]),
    ("B", "helper", "a6073cb14527d4dda", [35.223]),
    ("B", "worker-1", "a73689e08c2044e83", [88.907]),
    ("B", "worker-2", "ad6fb99d6c03ef100", [212.125]),
    ("B", "keeper", "a9ab49cb771e06515", [213.076]),
    ("B", "checker", "a7eb123ac70904d71", [277.237]),
    ("B", "critic", "a6615f1f72763aa77", [270.329]),
    ("B", "reviewer", "a76068c2f338bebed", [139.773]),
]
if len(sys.argv) > 2:
    AGENTS.append(("eval", "evaluator", sys.argv[2], [float(sys.argv[3])]))

root = Path(sys.argv[1])
print("arm,role,agent,model,runs,seconds,messages,input,cache_write,cache_read,output")
for arm, role, aid, secs in AGENTS:
    turns = {}
    path = root / f"agent-{aid}.jsonl"
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(ln).get("message")
        except (ValueError, AttributeError):
            continue
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            turns[msg.get("id") or f"row{len(turns)}"] = (msg["usage"], msg.get("model") or "?")
    assert turns, f"{path} must hold usage rows"
    models = sorted({m for _, m in turns.values()})
    tot = {k: sum(u.get(k, 0) or 0 for u, _ in turns.values())
           for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")}
    print(f"{arm},{role},{aid},{'+'.join(models)},{len(secs)},{sum(secs):.0f},{len(turns)},{tot['input_tokens']},"
          f"{tot['cache_creation_input_tokens']},{tot['cache_read_input_tokens']},{tot['output_tokens']}")
