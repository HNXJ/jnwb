"""Would the installed hook's own pattern have matched the commands that ran? Read-only: the hook is not run.

Usage: python pattern_check.py <block_python_stdin.py> <transcript.jsonl> [...]
Takes the two assignments `_FLAGS = ...` and `PATTERN = re.compile(...)` from the hook's source text, compiles
them, and applies PATTERN.search to (a) every shell command in the transcripts that this script's own finder
flags as running the interpreter on stdin or with -c, (b) fixed controls: forms that must match and permitted
commands that must not.
"""
import importlib.util
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
MUST = ["python -c \"print(1)\"", "python - </dev/null", "cd x && python - </dev/null 2>/dev/null; ls",
        "ls; python -c 'import os'", "D=$(python -c 'print(1)')", "tail -1 f | python -c 'import sys'",
        "py -3 -c 'print(1)'", "python -X utf8 -I -"]
MUST_NOT = ["python script.py -c x", "python -m pytest -c x tests", "python tools/run.py --check",
            "git -C repo log -3", "python3 path/to/file.py - <in.txt"]


def hook_pattern(path):
    src = pathlib.Path(path).read_text(encoding="utf-8")
    m = re.search(r"^_FLAGS = .*?^PATTERN = re\.compile\(.*?\n(?=\S)", src, re.S | re.M)
    ns = {"re": re}
    exec(m.group(0), ns)  # two assignments from the hook's source, nothing else
    return ns["PATTERN"]


def main(argv):
    spec = importlib.util.spec_from_file_location("finder", HERE / "find_stdin_runs.py")
    finder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(finder)
    pattern = hook_pattern(argv[0])
    print("hook PATTERN:", pattern.pattern)
    ok = True
    for cmd in MUST:
        hit = bool(pattern.search(cmd))
        ok &= hit
        print(f"control must match     | {hit} | {cmd}")
    for cmd in MUST_NOT:
        hit = bool(pattern.search(cmd))
        ok &= not hit
        print(f"control must not match | {hit} | {cmd}")
    n = matched = 0
    for path in argv[1:]:
        import json
        for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            for b in finder.blocks(row.get("message", {})):
                if b["type"] == "tool_use" and b.get("name") in ("Bash", "PowerShell"):
                    cmd = b.get("input", {}).get("command", "")
                    if finder.PAT.search(cmd):
                        n += 1
                        matched += bool(pattern.search(cmd))
    print(f"commands found in {len(argv) - 1} transcripts: {n}; the hook's pattern matches {matched} of them")
    print("controls as expected:", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
