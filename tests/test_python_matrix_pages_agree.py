"""The Python versions the user-facing pages state agree with what the project declares and tests.

Precedence: goal row 12 (``artifacts/goal.md``) names the interpreters; ``scripts/gates/versions.py`` holds
the constants that enforce it (``PYTHON_FLOOR``, ``PYTHON_CI_REQUIRED``); the CI matrix in
``.github/workflows/workflow.yml`` runs them. Gate 8 (``check_python_floor_consistency``) reads README.md and
docs/install.md; no gate reads docs/index.md, so this test does, with the same sentence rules.
"""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))  # the installed-wheel run clears pythonpath

from scripts.gates.versions import PYTHON_CI_REQUIRED, PYTHON_FLOOR  # noqa: E402
from scripts.harness_gate import check_python_floor_consistency  # noqa: E402

PAGES = ("README.md", "docs/install.md", "docs/index.md")
FLOOR = re.compile(r"Requires Python \**(\d+\.\d+) or newer")
# The canonical tested-interpreter sentence as a whole: the declared versions, then the Windows exclusion
# (3.15 is excluded on Windows: workflow.yml, goal row 12).
CANON = re.compile(
    r"(?:Tested in CI on|CI tests) ((?:\d+\.\d+(?:, | and ))*\d+\.\d+)"
    r" on Linux, and on Windows for all but the last\.")
TESTED = re.compile(r"(?:Tested in CI on|CI tests) ")
TESTING = re.compile(r"\b(?:tested|tests|test|CI)\b", re.IGNORECASE)
WINDOWS = re.compile(r"\bWindows\b")


def sentences(text: str) -> list[str]:
    """The sentences of ``text``, split after . ! or ? and at line breaks."""
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def disagreements(rel: str, text: str) -> list[str]:
    """Why the page ``rel`` does not state the declared floor and tested set, and the Windows exclusion.

    Every floor sentence must state the declared floor. Every tested-interpreter claim must be the canonical
    sentence in full (the declared versions, then "on Linux, and on Windows for all but the last."). Every
    sentence that names Windows with a testing word must be a canonical sentence, so no second claim can add
    Windows testing, drop 3.15 or flip the exclusion.
    """
    out = []
    floors = FLOOR.findall(text)
    if not floors:
        out.append(f"{rel} states no floor 'Requires Python X.Y or newer'")
    out += [f"{rel} states floor {f}, declared {PYTHON_FLOOR}" for f in floors if f != PYTHON_FLOOR]
    canonical = list(CANON.finditer(text))
    if not canonical:
        out.append(f"{rel} states no canonical tested-interpreter sentence")
    for m in canonical:
        versions = set(re.findall(r"\d+\.\d+", m.group(1)))
        if versions != set(PYTHON_CI_REQUIRED):
            out.append(f"{rel} states tested {sorted(versions)}, required {list(PYTHON_CI_REQUIRED)}")
    for m in TESTED.finditer(text):
        if CANON.match(text, m.start()) is None:
            out.append(f"{rel} states a tested-interpreter claim other than the canonical sentence "
                       f"at offset {m.start()}")
    for sentence in sentences(text):
        if WINDOWS.search(sentence) and TESTING.search(sentence) and not CANON.search(sentence):
            out.append(f"{rel} states a Windows testing claim outside the canonical sentence: "
                       f"{sentence.strip()[:120]!r}")
    return out


def test_every_page_states_the_declared_floor_and_tested_set():
    problems = []
    for rel in PAGES:
        problems += disagreements(rel, (ROOT / rel).read_text(encoding="utf-8"))
    assert problems == [], problems


def test_gate_eight_agrees_with_the_pages_it_reads():
    assert check_python_floor_consistency(ROOT) == []


def test_a_page_that_drops_a_version_is_reported():
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    altered = text.replace("3.12, 3.13, 3.14 and 3.15", "3.12, 3.13 and 3.14")
    assert altered != text, "fixture must alter the page"
    assert any("tested" in p for p in disagreements("docs/index.md", altered)), "a dropped 3.15 passed"


def test_a_floor_that_drifts_is_reported():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    altered = text.replace("Requires Python **3.12 or newer**", "Requires Python **3.13 or newer**")
    assert altered != text, "fixture must alter the page"
    assert any("floor" in p for p in disagreements("README.md", altered)), "a drifted floor passed"


def test_a_windows_claim_that_includes_3_15_is_reported():
    text = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    altered = text.replace("on Linux, and on Windows for all but the last", "on Linux, and on Windows for all")
    assert altered != text, "fixture must alter the page"
    assert disagreements("docs/install.md", altered), "a Windows clause that drops the exclusion passed"


INDEX_CANON = "3.12, 3.13, 3.14 and 3.15 on Linux, and on Windows for all but the last."
# Each probe is one change to docs/index.md the review found passing: a Windows testing claim in a second
# sentence, a 3.15 claim in a second sentence, a Windows clause that flips, a second floor, a negated clause.
PROBES = (
    ("append", "Tested on Windows too."),
    ("append", "Python 3.15 is tested on Windows."),
    ("replace", ("on Linux, and on Windows for all but the last",
                 "on Linux and Windows, and on Windows for all but the last")),
    ("append", "Requires Python 3.9 or newer."),
    ("replace", ("and on Windows for all but the last", "and not on Windows for all but the last")),
    ("replace", ("on Linux, and on Windows for all but the last.",
                 "on Linux and Windows, then (on Windows for all but the last is outdated).")),
)


def test_each_review_probe_on_the_index_page_is_reported():
    text = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert INDEX_CANON in text, "fixture must start from the real sentence"
    for kind, change in PROBES:
        if kind == "append":
            altered = text + "\n\n" + change + "\n"
        else:
            old, new = change
            altered = text.replace(old, new)
            assert altered != text, f"fixture must alter the page: {old!r}"
        assert disagreements("docs/index.md", altered), f"not reported: {change!r}"


def test_a_second_tested_sentence_that_drifts_is_reported():
    text = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    altered = text + "\n\nTested in CI on 3.12 and 3.14.\n"
    assert any("tested" in p for p in disagreements("docs/install.md", altered)), "a second drifted sentence passed"
