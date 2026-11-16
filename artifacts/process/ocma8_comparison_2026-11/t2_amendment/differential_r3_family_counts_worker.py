"""Family counts of t2_differential_r3 at both acceptance seeds, with the checks the packet names.

Prints, per seed and mode, the scored inputs per family (readers built in brackets) and the exploratory
inputs. Exits non-zero on any failed assertion: a scored line ending in an escaped pipe, a scored
whitespace-padding input, an empty examined set for a new family, or a normalisation that changes a lone
backslash. Standard library only; run by path.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import t2_differential_r3 as t2  # noqa: E402

BSL, BROKEN = t2.BSL, t2.BROKEN
SEEDS = (2026111600, 1)
NEW_FAMILIES = {  # family -> modes in which it must be built
    "lone_backslash": ("preserved", "corrected"),
    "multi_escape": ("corrected",),
    "inner_ws": ("preserved", "corrected"),
    "multi_table": ("preserved", "corrected"),
}


def fail(message):
    print(f"FAIL {message}")
    sys.exit(1)


def family_of(rec):
    return next((label[4:] for label in rec["labels"] if label.startswith("fam=")), "existing")


def check_normalisation():
    cases = {
        "C:" + BSL + "dir": "C:" + BSL + "dir",                       # lone backslash kept
        "a" + BSL + BSL + "b": "a" + BSL + BSL + "b",                 # two lone backslashes kept
        "a" + BSL + "|b": "a" + BROKEN + "b",                         # escaped pipe -> broken bar
        "a" + BSL + BROKEN + "b": "a" + BROKEN + "b",                 # baseline form -> broken bar
    }
    for raw, want in cases.items():
        got = t2.norm(raw)
        if got != want:
            fail(f"norm({raw!r}) = {got!r}, want {want!r}")
    print("NORM ok: a lone backslash is left untouched; escaped pipe and broken bar both map to broken bar")


def check_input(seed, rec):
    family = family_of(rec)
    scored = rec["bucket"] != "exploratory"
    lines = rec["doc"].split("\n")
    if family == "ws_pad" and scored:
        fail(f"seed {seed}: scored whitespace-padding input {rec['id']}")
    if scored and any(line.strip().endswith(t2.TERMINAL_ENDS) for line in lines):
        fail(f"seed {seed}: scored input {rec['id']} has a line ending in an escaped pipe: {rec['doc']!r}")
    if not scored:
        return
    doc = rec["doc"]
    if family == "lone_backslash" and not doc.count(BSL) > doc.count(BSL + "|"):
        fail(f"seed {seed}: lone_backslash fixture without a lone backslash: {rec['id']}")
    if family == "multi_escape" and doc.count(BSL + "|") < 3:
        fail(f"seed {seed}: multi_escape fixture with fewer than 3 escaped pipes: {rec['id']}")
    if family == "inner_ws" and not re.search(r"\S(?: {2,4}|\t)\S", doc):
        fail(f"seed {seed}: inner_ws fixture without an inner run: {rec['id']}")
    if family == "multi_table" and doc.count("|---") < 2:
        fail(f"seed {seed}: multi_table fixture without two tables: {rec['id']}")


def main():
    check_normalisation()
    for seed in SEEDS:
        inputs = t2.generate(seed, t2.DEFAULT_ROWS)
        counts = defaultdict(Counter)   # (mode, family) -> Counter of 'scored' readers
        readers = defaultdict(set)      # (mode, family) -> readers with a scored input
        exploratory = Counter()
        totals = Counter()
        for rec in inputs:
            check_input(seed, rec)
            family = family_of(rec)
            totals[rec["mode"]] += 1
            if rec["bucket"] == "exploratory":
                exploratory[rec["mode"]] += 1
                continue
            counts[(rec["mode"], family)]["n"] += 1
            readers[(rec["mode"], family)].add(rec["reader"])
        for mode in ("preserved", "corrected"):
            print(f"SEED {seed} MODE {mode} inputs={totals[mode]} exploratory={exploratory[mode]}")
            for (m, family), counter in sorted(counts.items()):
                if m != mode:
                    continue
                print(f"  FAMILY {family} scored={counter['n']} readers={len(readers[(m, family)])}")
            for family, modes in NEW_FAMILIES.items():
                if mode in modes and counts[(mode, family)]["n"] == 0:
                    fail(f"seed {seed}: new family {family} has an empty examined set in {mode}")
            if not counts[(mode, "ws_pad")]["n"] == 0:
                fail(f"seed {seed}: ws_pad scored in {mode}")
        missing_inner = sorted({rec["reader"] for rec in inputs if rec["mode"] == "preserved"}
                               - readers[("preserved", "inner_ws")] - readers[("corrected", "inner_ws")])
        print(f"  NOT BUILT inner_ws (no cell with two words; share returned to existing variations): "
              f"{missing_inner}")
        print(f"  ASSERT seed {seed}: no scored line ends in an escaped pipe; no scored ws_pad; "
              f"every new family built in its modes; fixtures build their named case")


if __name__ == "__main__":
    main()
