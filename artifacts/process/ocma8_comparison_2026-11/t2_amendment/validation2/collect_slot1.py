"""Validation 2, slot 1: save each Claude adjudicator's final report from its agent transcript.

Usage: python collect_slot1.py <agents.txt> <tasks dir> <out dir>

<agents.txt> has one line per adjudication: `<label> <agent id>`. For each, reads <tasks dir>/agent-<agent id>.jsonl
(the session's subagent transcripts, JSON lines), takes the last text that holds a `VERDICT:` line and that the agent itself wrote (assistant
text, or the report argument of its hand-back call), and writes it to <out dir>/<label>_slot1.md. Prints
label, the verdict found and the text length; exits 1 when any report is missing.
"""
import json
import pathlib
import re
import sys

VERDICT = re.compile(r"^\s*VERDICT: (PASS|FAIL|UNRESOLVED)\s*$", re.M)


def texts(node, role=None):
    """Every string an assistant turn carries: text blocks and string inputs of its tool calls."""
    if isinstance(node, dict):
        role = node.get("role", role) if isinstance(node.get("role"), str) else role
        if node.get("type") == "text" and isinstance(node.get("text"), str) and role == "assistant":
            yield node["text"]
        if node.get("type") == "tool_use" and isinstance(node.get("input"), dict) and role == "assistant":
            for value in node["input"].values():
                if isinstance(value, str):
                    yield value
        for value in node.values():
            yield from texts(value, role)
    elif isinstance(node, list):
        for value in node:
            yield from texts(value, role)


def main(argv):
    agents, tasks, out = (pathlib.Path(a) for a in argv)
    out.mkdir(parents=True, exist_ok=True)
    missing = 0
    for line in agents.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        label, agent = line.split()[:2]
        report = None
        with open(tasks / f"agent-{agent}.jsonl", encoding="utf-8", errors="replace") as handle:
            for raw in handle:
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                for text in texts(event):
                    if VERDICT.search(text) and "PACKET.md" not in text[:200]:
                        report = text
        if report is None:
            missing += 1
            print(label, "NO REPORT")
            continue
        (out / f"{label}_slot1.md").write_text(report.strip() + "\n", encoding="utf-8", newline="\n")
        print(label, VERDICT.findall(report)[-1], len(report))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
