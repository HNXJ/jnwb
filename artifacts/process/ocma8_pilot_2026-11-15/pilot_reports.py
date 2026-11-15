"""Write each pilot agent's hand-back reports, verbatim from its transcript. Usage: pilot_reports.py <subagents dir> <usage.csv> <out dir>"""
import csv
import json
import sys
from pathlib import Path

root, out = Path(sys.argv[1]), Path(sys.argv[3])
out.mkdir(exist_ok=True)
for row in csv.DictReader(open(sys.argv[2], encoding="utf-8")):
    reports = []
    for ln in (root / f"agent-{row['agent']}.jsonl").read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            msg = json.loads(ln).get("message")
        except (ValueError, AttributeError):
            continue
        if not isinstance(msg, dict) or not isinstance(msg.get("content"), list):
            continue
        for c in msg["content"]:
            if isinstance(c, dict) and c.get("type") == "tool_use" and c.get("name") == "SubagentHandback":
                text = str((c.get("input") or {}).get("message", "")).strip()
                if text and text not in reports:
                    reports.append(text)
    assert reports, f"{row['role']} must have a hand-back"
    body = "".join(f"## Report {n}\n\n{t}\n\n" for n, t in enumerate(reports, 1))
    (out / f"{row['arm']}_{row['role']}.md").write_bytes(
        f"# {row['arm']} {row['role']} ({row['model']}), verbatim\n\n{body}".encode("utf-8"))
    print(row["arm"], row["role"], len(reports))
