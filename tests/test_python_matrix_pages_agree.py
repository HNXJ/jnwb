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
TESTED = re.compile(r"(?:Tested in CI on|CI tests) ([\d., and]+\d)")
WINDOWS = "on Windows for all but the last"  # 3.15 is excluded on Windows (workflow.yml, goal row 12)


def claims(text: str) -> tuple[str | None, list[set[str]], bool]:
    """The floor, each tested-version sentence, and whether the Windows clause is stated."""
    floor = FLOOR.search(text)
    tested = [set(re.findall(r"\d+\.\d+", m.group(1))) for m in TESTED.finditer(text)]
    return (floor.group(1) if floor else None, tested, WINDOWS in text)


def disagreements(rel: str, text: str) -> list[str]:
    """Why the page ``rel`` does not state the declared floor, the tested set and the Windows exclusion."""
    floor, tested, windows = claims(text)
    out = []
    if floor != PYTHON_FLOOR:
        out.append(f"{rel} states floor {floor}, declared {PYTHON_FLOOR}")
    if not tested:
        out.append(f"{rel} states no tested-interpreter sentence")
    for stated in tested:
        if stated != set(PYTHON_CI_REQUIRED):
            out.append(f"{rel} states tested {sorted(stated)}, required {list(PYTHON_CI_REQUIRED)}")
    if not windows:
        out.append(f"{rel} lacks the Windows clause: {WINDOWS!r}")
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
    altered = text.replace(WINDOWS, "on Windows for all")
    assert altered != text, "fixture must alter the page"
    assert any("Windows" in p for p in disagreements("docs/install.md", altered)), "a Windows 3.15 claim passed"


def test_a_second_tested_sentence_that_drifts_is_reported():
    text = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    altered = text + "\n\nTested in CI on 3.12 and 3.14.\n"
    assert any("tested" in p for p in disagreements("docs/install.md", altered)), "a second drifted sentence passed"
