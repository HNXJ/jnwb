"""Apply the two-entry telemetry patch to settings.json (jarness P-26; Hamm 2026-11-15, option 1).

Usage: settings_patch_apply.py check|apply <settings.json> <source backup with the entries> <new backup path>
check: validates the baseline and the hook paths, writes nothing.
apply: the same checks, then copies the file byte for byte to <new backup path>, adds SubagentStop and
SubagentStart (the groups that run subagent_log.py, copied from the source backup), and re-reads the result:
every other key and every existing hook must be unchanged.
"""
import json
import re
import sys
from pathlib import Path

mode, cur_p, src_p, bak_p = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
EVENTS = ("SubagentStop", "SubagentStart")
EXPECT = [("Bash|PowerShell", "git_guard.py"), ("Bash|PowerShell", "run_guard.py"), ("Edit|Write|NotebookEdit", "run_guard.py")]


def commands(hooks):
    return [(ev, g.get("matcher", ""), h.get("command", "")) for ev, gs in hooks.items() for g in gs for h in g.get("hooks", [])]


def paths_ok(hooks):
    bad = []
    for ev, _, cmd in commands(hooks):
        m = re.search(r'"([^"]+\.py)"', cmd)
        assert m, f"{ev}: no quoted script path in the command"
        if not Path(m.group(1)).is_file():
            bad.append(m.group(1))
    return bad


raw = cur_p.read_bytes()
old = json.loads(raw.decode("utf-8"))  # raises on invalid JSON
hooks = old.get("hooks") or {}
assert sorted(hooks) == ["PreToolUse"], f"baseline: expected only PreToolUse, found {sorted(hooks)}"
got = [(m, Path(re.search(r'"([^"]+\.py)"', c).group(1)).name) for _, m, c in commands(hooks)]
assert got == EXPECT, f"baseline hooks differ: {got}"
assert not paths_ok(hooks), f"missing hook scripts before: {paths_ok(hooks)}"
src = json.loads(src_p.read_text(encoding="utf-8")).get("hooks") or {}
add = {ev: [g for g in src.get(ev, []) if any("subagent_log.py" in h.get("command", "") for h in g.get("hooks", []))] for ev in EVENTS}
assert all(len(v) == 1 for v in add.values()), "source backup must hold one subagent_log group per event"
nl = b"\r\n" if b"\r\n" in raw else b"\n"
indent = len(re.search(rb"\n( +)\"", raw).group(1))
roundtrip = (json.dumps(old, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith(b"\n") else "")).replace("\n", nl.decode()).encode("utf-8") == raw
print(f"baseline ok: 3 PreToolUse hooks, {len(raw)} bytes, newline {nl!r}, indent {indent}, byte round trip {roundtrip}")
if mode == "check":
    sys.exit(0)

assert mode == "apply" and not bak_p.exists(), "new backup path must not exist"
bak_p.write_bytes(raw)
assert bak_p.read_bytes() == raw, "backup must equal the original bytes"
new = json.loads(raw.decode("utf-8"))
for ev in EVENTS:
    new["hooks"][ev] = add[ev]
text = json.dumps(new, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith(b"\n") else "")
cur_p.write_bytes(text.replace("\n", nl.decode()).encode("utf-8"))

back = json.loads(cur_p.read_bytes().decode("utf-8"))
rest = json.loads(json.dumps(back))
for ev in EVENTS:
    assert [c for e, _, c in commands(back["hooks"]) if e == ev] == ['python "C:/Users/nejath/.claude/hooks/subagent_log.py"'], ev
    del rest["hooks"][ev]
assert rest == old, "every existing key and hook must be unchanged"
assert list(back) == list(old), "top-level key order kept"
assert not paths_ok(back["hooks"]), f"missing hook scripts after: {paths_ok(back['hooks'])}"
print(f"applied: events {sorted(back['hooks'])}; other keys equal; backup {bak_p} ({len(raw)} bytes); new size {cur_p.stat().st_size}")
