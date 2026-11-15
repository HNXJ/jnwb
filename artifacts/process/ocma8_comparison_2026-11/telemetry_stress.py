"""Concurrent-write stress of subagent_log.record(). Usage: _temp_sublog_stress.py <hooks dir> <tmp dir> <procs> <runs per proc>

Each process logs <runs> agents: a start, a stop, and a second stop of the same run (the replace path), so every
process both appends and rewrites while the others do. Expected: one stop row per run id, procs*runs rows, no error.
Prints rows, missing run ids, run ids with more than one row, unparsable lines and worker errors.
"""
import json
import multiprocessing as mp
import sys
from pathlib import Path


def work(args):
    hooks, log, p, runs = args
    sys.path.insert(0, hooks)
    import subagent_log
    errors = []
    for i in range(runs):
        aid = f"p{p}r{i}"
        base = {"agent_id": aid, "agent_type": "worker", "agent_transcript_path": "none.jsonl", "session_id": "S"}
        try:
            subagent_log.record({**base, "hook_event_name": "SubagentStart"}, log)
            subagent_log.record({**base, "last_assistant_message": "working"}, log)
            subagent_log.record({**base, "last_assistant_message": "Verdict: PASS"}, log)
        except Exception as e:  # the hook's main() would swallow this; here it is counted
            errors.append(f"{aid}: {type(e).__name__}")
    return errors


if __name__ == "__main__":
    hooks, tmp, procs, runs = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    tmp.mkdir(parents=True, exist_ok=True)
    log = tmp / "runs.jsonl"
    for f in tmp.glob("*"):
        f.unlink()
    with mp.Pool(procs) as pool:
        errors = [e for es in pool.map(work, [(hooks, log, p, runs) for p in range(procs)]) for e in es]
    want = {f"p{p}r{i}.1" for p in range(procs) for i in range(runs)}
    seen, bad = {}, 0
    for ln in log.read_bytes().splitlines():
        try:
            r = json.loads(ln)
            seen.setdefault(r["run_id"], []).append(r["verdict"])
        except (ValueError, KeyError):
            bad += 1
    missing = want - set(seen)
    dup = {k for k, v in seen.items() if len(v) > 1}
    stale = {k for k, v in seen.items() if v[-1] != "PASS"}
    print(f"expected {len(want)} rows {sum(len(v) for v in seen.values())} missing {len(missing)} duplicated {len(dup)} "
          f"not-final {len(stale)} unparsable {bad} errors {len(errors)} {sorted(set(e.split(': ')[1] for e in errors))}")
    sys.exit(0 if not (missing or dup or stale or bad or errors) else 1)
