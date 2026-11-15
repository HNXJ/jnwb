"""Do the two ledger readers' tracked inputs hold a row without a leading pipe? Read-only.

Usage: input_usage_check.py <jnwb tree>

Applies the baseline row rules of `learning_gate.ledger_rows` (3 or more cells, second cell a number) and of
`reconstruct_state.open_defect_classes` (6 or more cells, second a number, a colon in the first) to every line of
`artifacts/process/defect_classes.md`, the one file both read, with the baseline split
(`line.strip().strip("|").split("|")`), and counts the accepted rows by whether the stripped line starts with `|`.
Prints the counts and every accepted row that lacks the leading pipe. Fails if the file is absent or no row is
accepted (an empty examined set proves nothing).
"""
import sys
from pathlib import Path

path = Path(sys.argv[1]) / "artifacts" / "process" / "defect_classes.md"
lines = path.read_text(encoding="utf-8").splitlines()
RULES = {
    "learning_gate.ledger_rows": lambda c: len(c) >= 3 and c[1].isdigit(),
    "reconstruct_state.open_defect_classes": lambda c: len(c) >= 6 and c[1].isdigit() and ":" in c[0],
}
bad = 0
for name, accepts in RULES.items():
    rows = [(n, ln) for n, ln in enumerate(lines, 1)
            if accepts([c.strip() for c in ln.strip().strip("|").split("|")])]
    assert rows, f"{name}: no accepted row in {path}"
    bare = [(n, ln) for n, ln in rows if not ln.strip().startswith("|")]
    bad += len(bare)
    print(f"{name}: {len(lines)} lines, {len(rows)} accepted rows, {len(rows) - len(bare)} with a leading pipe, "
          f"{len(bare)} without")
    for n, ln in bare:
        print(f"  line {n}: {ln[:120]!r}")
print(f"RESULT: {bad} accepted rows without a leading pipe")
