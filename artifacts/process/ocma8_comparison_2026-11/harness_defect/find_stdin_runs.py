"""List shell tool calls in session transcripts whose command runs the interpreter on stdin or with -c,
with what came back.

Usage: python find_stdin_runs.py <transcript.jsonl> [more.jsonl ...]
Per match: timestamp, file, tool, where the match sits (start of the command, or after which separator),
the command cut to 160 characters around the match, and the first 200 characters of the tool result
(a hook refusal shows there). The result is paired by tool_use id within the same file.
"""
import json
import pathlib
import re
import sys

PAT = re.compile(r"(?<![\w./-])python[0-9.]*(?:\.exe)?\s+(?:-[A-Za-z]+\s+)*-(?:c\b|(?=\s|$|<))")


def blocks(obj):
    if isinstance(obj, dict):
        if obj.get("type") in ("tool_use", "tool_result"):
            yield obj
        for v in obj.values():
            yield from blocks(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from blocks(v)


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict))
    return str(content)


def main(argv):
    total = 0
    for path in argv:
        uses, results = [], {}
        for line in pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            for b in blocks(row.get("message", {})):
                if b["type"] == "tool_use" and b.get("name") in ("Bash", "PowerShell"):
                    uses.append((row.get("timestamp"), b.get("name"), b.get("id"), b.get("input", {}).get("command", "")))
                elif b["type"] == "tool_result":
                    results[b.get("tool_use_id")] = (bool(b.get("is_error")), text_of(b.get("content")))
        for ts, tool, uid, cmd in uses:
            m = PAT.search(cmd)
            if not m:
                continue
            total += 1
            before = cmd[:m.start()].rstrip()
            where = "start" if not before else "after " + repr(before[-2:])
            a, b = max(0, m.start() - 60), min(len(cmd), m.end() + 100)
            shown = (cmd[a:m.start()] + ">>>" + cmd[m.start():m.end()] + "<<<" + cmd[m.end():b]).replace("\n", " \\n ")
            err, res = results.get(uid, (None, "(no result in this file)"))
            print(f"{ts} | {pathlib.Path(path).name[:18]} | {tool} | {where} | is_error={err} | {shown} || RESULT: "
                  + res[:200].replace("\n", " \\n "))
    print(f"TOTAL {total} matching commands in {len(argv)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
