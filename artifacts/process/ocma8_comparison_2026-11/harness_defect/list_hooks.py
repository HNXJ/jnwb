"""Print which hook scripts a Claude settings file wires, without printing other settings.

Usage: python list_hooks.py <settings.json> [...]
Per file: the top-level keys, then event, matcher and each hook command's script names (tokens ending in
.py, .sh, .cmd or .ps1; nothing else of the command is printed).
"""
import json
import pathlib
import re
import sys

SCRIPT = re.compile(r"[^\s\"']+\.(?:py|sh|cmd|ps1)\b")


def main(argv):
    for path in argv:
        p = pathlib.Path(path)
        if not p.exists():
            print(f"{path}: missing")
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        print(f"{path}: keys {sorted(data)}")
        for event, groups in (data.get("hooks") or {}).items():
            for group in groups:
                names = [pathlib.PurePosixPath(s.replace("\\", "/")).name
                         for h in group.get("hooks", []) for s in SCRIPT.findall(str(h.get("command", "")))]
                print(f"  {event} | matcher {group.get('matcher')!r} | {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
