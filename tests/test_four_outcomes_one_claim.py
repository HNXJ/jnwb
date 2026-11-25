"""The four outcomes of a skill task are one claim, restated in the docs and fixed in the code.

The canonical record is fact row K3 in ``artifacts/fact_stack.md``, held by
``tests/test_skill_decline_behaviour.py``. The restatements must name the same four outcomes. The code's
outcome values (``jnwb.ontology.Preflight.OUTCOMES``) are the API's names for them: the mapping below is
the precedence between the two vocabularies. A restatement may not weaken the rule with a permission
("may decline"). This is a lexical check; the equivalence of the wording is also judged by review.
"""

from __future__ import annotations

import pathlib
import re

from jnwb.ontology import Preflight

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACT_STACK = ROOT / "artifacts" / "fact_stack.md"

# K3's name for each outcome, and the value the code returns for it (precedence: K3 names the rule, the code
# names the API value; the two must map one to one).
MAPPING = {
    "supported": r"compose and execute",
    "request": r"request missing information",
    "failure": r"non-identifiability or failure",
    "decline": r"decline (?:an )?unsupported inference",
}

# Phrases each restatement must carry, as regular expressions, matched case-insensitively against its
# text with line breaks folded to spaces.
REQUIRED = {
    ".github/CONTRIBUTING.md": (
        r"four outcomes", r"compose and execute", r"request missing information",
        r"non-identifiability or failure", r"decline (?:an )?unsupported inference"),
    "artifacts/agents.md": (
        r"four outcomes", r"compose and execute", r"request missing information",
        r"non-identifiability or failure", r"decline (?:an )?unsupported inference"),
    "docs/architecture.md": (
        r"four outcomes", r"Decline", r"Request the input", r"Report the failure",
        r"Compose and execute the operations"),
    "docs/api.md": (r"one of the four outcomes",),
}

# A permission that weakens the rule: a task "may" decline, or declining is "optional".
PERMISSION = re.compile(r"\b(?:may|can|could|might) (?:decline|refuse)\b|\boptional(?:ly)? decline", re.I)


def _flat(text: str) -> str:
    return " ".join(text.split())


def missing(rel: str, text: str) -> list[str]:
    """The required phrases that ``text`` (the file ``rel``) does not carry, or a permission it grants."""
    flat = _flat(text)
    out = [f"{rel} lacks: {phrase}" for phrase in REQUIRED[rel] if not re.search(phrase, flat, re.I)]
    out += [f"{rel} grants a permission: {m.group(0)}" for m in PERMISSION.finditer(flat)]
    return out


def test_the_code_names_the_four_outcomes_the_docs_name():
    assert Preflight.OUTCOMES == ("supported", "request", "failure", "decline")
    assert set(MAPPING) == set(Preflight.OUTCOMES), "every code value needs one K3 name, and no more"


def test_the_canonical_row_names_all_four():
    rows = [line for line in FACT_STACK.read_text(encoding="utf-8").splitlines() if line.startswith("| K3 ")]
    assert len(rows) == 1, "K3 must be exactly one row in artifacts/fact_stack.md"
    for phrase in ("four outcomes", *MAPPING.values()):
        assert re.search(phrase, rows[0], re.I), f"K3 does not name: {phrase}"


def test_each_restatement_names_all_four_outcomes():
    problems = []
    for rel in REQUIRED:
        problems += missing(rel, (ROOT / rel).read_text(encoding="utf-8"))
    assert problems == [], problems


def test_a_restatement_that_drops_an_outcome_is_reported():
    text = (ROOT / ".github" / "CONTRIBUTING.md").read_text(encoding="utf-8")
    altered = text.replace("or decline an unsupported inference", "")
    assert altered != text, "fixture must alter the restatement"
    assert any("decline" in p for p in missing(".github/CONTRIBUTING.md", altered)), "a dropped decline passed"


def test_a_count_of_three_is_reported():
    text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    altered = text.replace("ends in one of four outcomes", "ends in one of three outcomes")
    assert altered != text, "fixture must alter the restatement"
    assert any("four outcomes" in p for p in missing("docs/architecture.md", altered)), "a count of three passed"


def test_a_permission_to_decline_is_reported():
    text = (ROOT / "artifacts" / "agents.md").read_text(encoding="utf-8")
    altered = text.replace("ends every task in one of four outcomes",
                           "may decline an unsupported inference, and ends every task in one of four outcomes")
    assert altered != text, "fixture must alter the restatement"
    assert any("permission" in p for p in missing("artifacts/agents.md", altered)), "a permission to decline passed"


def test_a_reworded_restatement_with_the_same_outcomes_passes():
    text = ("Every task a skill handles ends in one of four outcomes: compose and execute, request missing "
            "information, report non-identifiability or failure, or decline unsupported inference.")
    assert missing(".github/CONTRIBUTING.md", text) == []
