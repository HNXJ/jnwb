"""P-15: measure how much of AGENTS.md duplicates truth that lives somewhere else.

P-15 says AGENTS.md is 360+ lines against a contract requiring a thin router, and that the
duplication "has not been measured, so the size is not yet evidence of a defect". Size is a proxy
for duplication; duplication is the invariant. This measures the invariant.

Method: cut AGENTS.md into sections and every other authority into sentences. For each sentence
of AGENTS.md, find the best-matching sentence anywhere else and report the score. A high score
means the same claim has two homes and can disagree with itself, which is the actual defect.
Shingled Jaccard on 4-grams of words, which survives rewording better than a literal diff.
"""
import pathlib
import re
import sys
import unicodedata

# The sentences printed below are repository prose, so they carry whatever characters the
# authorities carry -- `→` among them. On Windows stdout defaults to cp1252, which cannot encode
# it, and the script died mid-listing with a UnicodeEncodeError that the suite reported as "the
# measurement script failed". A diagnostic that cannot print its own finding is not one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

#: Derived, never literal. This read `C:\workspace\jnwb` until 06-64 showed what that costs: the
#: script measured that one tree no matter which tree invoked it, so the ratchet in
#: `tests/test_agents_md_stays_a_router.py` stayed green with the AGENTS.md under test deleted.
#: A machine-local path in a script the suite shells out to makes the check a property of a laptop.
ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"

OTHERS = [
    ROOT / "artifacts" / "goal.md",
    ROOT / "artifacts" / "fact_stack.md",
    ROOT / "artifacts" / "problem_stack.md",
    ROOT / "artifacts" / "todo_stack.md",
    ROOT / "artifacts" / "direction.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs" / "documentation_form.md",
]
OTHERS += sorted(ROOT.glob("skills/*/SKILL.md"))
OTHERS += sorted(ROOT.glob("artifacts/agents/*.md"))
# Dispatchable subagent definitions. They route over the role files and AGENTS.md rather than
# restating either, and they are measured here so that stays true: a routing file nothing
# measures is precisely where a second home for a claim appears without anyone noticing.
OTHERS += sorted(ROOT.glob(".claude/agents/*.md"))

WORD = re.compile(r"[a-z0-9_]+")
N = 4


def words(text: str) -> list:
    text = unicodedata.normalize("NFKD", text).lower()
    return WORD.findall(text)


def shingles(text: str) -> set:
    w = words(text)
    return {tuple(w[i:i + N]) for i in range(max(0, len(w) - N + 1))}


def sentences(text: str):
    # Strip fenced code; a shared code block is a quotation, not a duplicated claim.
    text = re.sub(r"(?ms)^```.*?^```", " ", text)
    for raw in re.split(r"(?<=[.:!?])\s+|\n\n+|\n(?=[-|#])", text):
        s = " ".join(raw.split())
        if len(words(s)) >= 8:
            yield s


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# Index every other authority.
elsewhere = []
for path in OTHERS:
    if not path.exists():
        print(f"  MISSING (a pointer that went stale): {path.relative_to(ROOT)}")
        continue
    for s in sentences(path.read_text(encoding="utf-8")):
        elsewhere.append((path.relative_to(ROOT).as_posix(), s, shingles(s)))

text = AGENTS.read_text(encoding="utf-8")
total_lines = len(text.splitlines())

# Section boundaries, so the report says WHERE the duplication is.
sections = []
for m in re.finditer(r"(?m)^(##+ .*)$", text):
    sections.append((m.start(), m.group(1)))
sections.append((len(text), "EOF"))


def section_of(pos: int) -> str:
    name = "(preamble)"
    for start, title in sections:
        if start <= pos:
            name = title
        else:
            break
    return name


HIGH, MED = 0.34, 0.18
rows = []
for s in sentences(text):
    pos = text.find(s[:40])
    sh = shingles(s)
    best = max(elsewhere, key=lambda e: jaccard(sh, e[2]), default=None)
    score = jaccard(sh, best[2]) if best else 0.0
    rows.append((score, section_of(pos if pos >= 0 else 0), s, best[0] if best else "-", best[1] if best else ""))

rows.sort(key=lambda r: -r[0])
high = [r for r in rows if r[0] >= HIGH]
med = [r for r in rows if MED <= r[0] < HIGH]

# Say which tree was measured. A measurement that does not name its subject cannot be checked
# against the tree the caller meant, which is exactly how the hard-coded ROOT went unnoticed.
print(f"ROOT: {ROOT}")
print(f"AGENTS.md: {total_lines} lines, {len(rows)} claim-bearing sentences")
print(f"compared against {len(elsewhere)} sentences in {len(OTHERS)} other authorities\n")
print(f"DUPLICATED (Jaccard >= {HIGH}): {len(high)}  ({100*len(high)/max(1,len(rows)):.1f}%)")
print(f"ECHOED     (Jaccard >= {MED}):  {len(med)}  ({100*len(med)/max(1,len(rows)):.1f}%)\n")

by_section = {}
for score, sec, *_ in rows:
    b = by_section.setdefault(sec, [0, 0, 0])
    b[0] += 1
    if score >= HIGH:
        b[1] += 1
    elif score >= MED:
        b[2] += 1
print(f"{'section':44} {'sent':>5} {'dup':>4} {'echo':>5}")
for sec, (n, h, m) in sorted(by_section.items(), key=lambda kv: -kv[1][1]):
    print(f"{sec[:44]:44} {n:5} {h:4} {m:5}")

print(f"\nTOP DUPLICATES — each is one claim with two homes:")
for score, sec, s, where, other in high[:20]:
    print(f"\n  {score:.2f}  {sec[:52]}")
    print(f"        AGENTS.md: {s[:130]}")
    print(f"        {where}: {other[:130]}")

# The echo band is tested with its own baseline, so it has to be readable too. Listing only the
# duplicates left `test_echoed_claims_do_not_increase` able to fail while the script it names as
# the diagnostic printed nothing about the sentence that moved the count.
print(f"\nECHOES — each is a claim that reads like one elsewhere:")
for score, sec, s, where, other in med:
    print(f"\n  {score:.2f}  {sec[:52]}")
    print(f"        AGENTS.md: {s[:130]}")
    print(f"        {where}: {other[:130]}")
