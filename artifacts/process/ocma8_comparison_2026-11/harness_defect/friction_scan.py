"""Summarise ~/.claude/friction.jsonl by hook and rule: count, first and last timestamp, and the count for
one session. Prints no command text.

Usage: python friction_scan.py <friction.jsonl> <session id>
"""
import collections
import json
import pathlib
import sys


def main(argv):
    rows = []
    for line in pathlib.Path(argv[0]).read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    print(f"rows {len(rows)}; keys of the last row {sorted(rows[-1]) if rows else None}")
    by = collections.defaultdict(list)
    for r in rows:
        by[(r.get("hook"), r.get("rule"))].append(r)
    sess_key = next((k for k in ("session", "sess", "session_id") if rows and k in rows[-1]), None)
    print("hook | rule | count | first ts | last ts | count in the session")
    for key in sorted(by, key=lambda k: (str(k[0]), str(k[1]))):
        rs = by[key]
        ts = sorted(str(r.get("ts")) for r in rs)
        in_sess = sum(1 for r in rs if sess_key and str(r.get(sess_key, "")).startswith(argv[1][:8]))
        print(f"{key[0]} | {key[1]} | {len(rs)} | {ts[0]} | {ts[-1]} | {in_sess}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
