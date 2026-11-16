"""Validation 2, slot 2: one opencode Muse adjudication per isolated tree, in series.

Usage: python run_slot2.py <key.jsonl> <adj root> <packet template> <out dir>

For every key row with slot 2: fills {DIR} in the packet, runs delegate.py (opencode, review tier, read mode,
the isolated directory as root), copies the run's result.md to <out dir>/<label>_slot2.md and appends one line
to <out dir>/slot2_log.txt: label, attempt, return code, the last `VERDICT:` line or NONE. A run with no
verdict line is retried once (protocol section 2); a second failure is logged as REPLACE (a fresh Claude
reviewer then takes the slot). Trees are named only by label here; the key file is read for labels alone.
"""
import json
import pathlib
import re
import subprocess
import sys

DELEGATE = "C:/Users/nejath/.claude/skills/delegate-cli/delegate.py"
VERDICT = re.compile(r"^VERDICT: (PASS|FAIL|UNRESOLVED)\s*$", re.M)


def attempt(label, root, template, out, n):
    packet = out / f"{label}_packet.md"
    packet.write_text(template.replace("{DIR}", f"{root.as_posix()}/{label}"), encoding="utf-8", newline="\n")
    run_dir = out / f"{label}_run{n}"
    proc = subprocess.run([sys.executable, DELEGATE, str(packet), "--backend", "opencode", "--tier", "review",
                           "--dir", str(root / label), "--timeout", "1500", "--out", str(run_dir),
                           "--title", "adjudication"],
                          capture_output=True, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
    (out / f"{label}_summary{n}.txt").write_text(proc.stdout + "\n--- stderr ---\n" + proc.stderr,
                                                 encoding="utf-8", newline="\n")
    results = sorted(run_dir.rglob("result.md"))
    text = results[-1].read_text(encoding="utf-8", errors="replace") if results else ""
    found = VERDICT.findall(text)
    if found:
        (out / f"{label}_slot2.md").write_text(text, encoding="utf-8", newline="\n")
    return proc.returncode, found[-1] if found else None


def main(argv):
    key_path, root, template_path, out = (pathlib.Path(a) for a in argv)
    out.mkdir(parents=True, exist_ok=True)
    template = template_path.read_text(encoding="utf-8")
    labels = [row["label"] for row in map(json.loads, key_path.read_text(encoding="utf-8").splitlines())
              if row["slot"] == 2]
    with open(out / "slot2_log.txt", "a", encoding="utf-8", newline="\n") as log:
        for label in labels:
            if (out / f"{label}_slot2.md").exists():
                continue
            for n in (1, 2):
                rc, verdict = attempt(label, root, template, out, n)
                log.write(f"{label} attempt={n} rc={rc} verdict={verdict or 'NONE'}\n")
                log.flush()
                if verdict:
                    break
            else:
                log.write(f"{label} REPLACE\n")
                log.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
