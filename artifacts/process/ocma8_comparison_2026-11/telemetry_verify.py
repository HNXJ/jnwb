"""Check the subagent logs after a verification run. Usage: telemetry_verify.py <runs before> <runs after> <starts before> <starts after> <session id> <agent id> [<agent id> ...]

Fails unless: every row present before is still present, byte for byte and in order (no unrelated row lost or
changed); the new rows belong only to the named agents; each new run id has exactly one stop row and one start row;
each stop row names the session, a model, a positive duration and output-token count; run numbers are 1..n per agent
with the parent link set from run 2 on.
"""
import collections
import json
import sys

rb, ra, sb, sa, session, agents = *sys.argv[1:6], sys.argv[6:]


def lines(p):
    return open(p, "rb").read().splitlines()


for name, before, after in (("runs", lines(rb), lines(ra)), ("starts", lines(sb), lines(sa))):
    assert after[:len(before)] == before, f"{name}: a row present before the run changed or is gone"
    print(f"{name}: {len(before)} rows before, all kept byte for byte; {len(after) - len(before)} new")
new_stops = [json.loads(ln) for ln in lines(ra)[len(lines(rb)):]]
new_starts = [json.loads(ln) for ln in lines(sa)[len(lines(sb)):]]
assert new_stops and new_starts, "the run must have written rows"
for label, rows in (("stop", new_stops), ("start", new_starts)):
    ids = collections.Counter(r["run_id"] for r in rows)
    assert all(v == 1 for v in ids.values()), f"{label}: duplicated run ids {[k for k, v in ids.items() if v > 1]}"
    owners = {r["run_id"].rsplit(".", 1)[0] for r in rows}
    assert owners == set(agents), f"{label}: rows for {sorted(owners)}, expected {sorted(agents)}"
    assert all(r["session"] == session for r in rows), f"{label}: a row names another session"
assert {r["run_id"] for r in new_stops} == {r["run_id"] for r in new_starts}, "each started run has its stop row"
for a in agents:
    mine = sorted((r for r in new_stops if r["run_id"].startswith(a + ".")), key=lambda r: r["run_id"])
    assert [r["run_id"] for r in mine] == [f"{a}.{n}" for n in range(1, len(mine) + 1)], f"{a}: run numbers"
    assert [r["parent_run_id"] for r in mine] == [None] + [f"{a}.{n}" for n in range(1, len(mine))], f"{a}: parent links"
    for r in mine:
        assert r["model"] and r["s"] > 0 and r["out"] > 0 and r["fresh_in"] > 0 and r["agent"], f"{r['run_id']}: empty field"
        print({k: r[k] for k in ("ts", "run_id", "parent_run_id", "agent", "model", "s", "out", "fresh_in", "cache_read", "tools", "verdict")})
print(f"PASS: {len(new_stops)} stop rows, {len(new_starts)} start rows, {len(agents)} agents, one row per run id")
