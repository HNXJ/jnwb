"""Restatements of the spikes-and-LFP rule agree with it in meaning, not in wording.

The canonical record is the fact row named S16 in ``artifacts/fact_stack.md``; the internal authority is
``AGENTS.md`` section 5. The public restatements may keep their own sentences. A restatement passes when some
line that pairs pooling with spikes or LFP states the prohibition, and when no such line grants a
permission or an exception. The record itself must pass the same test. Whether a sentence says exactly
what the record says is a review question; this test catches a contradiction or a dropped prohibition.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACT_STACK = ROOT / "artifacts" / "fact_stack.md"
RESTATEMENTS = (".github/CONTRIBUTING.md", "docs/architecture.md", "skills/jnwb/SKILL.md", "AGENTS.md")

_POOL = re.compile(r"\bpool(?:s|ed|ing)?\b", re.IGNORECASE)
_SUBJECT = re.compile(r"\b(?:spikes?|SUA|MUA|LFP)\b", re.IGNORECASE)
_PROHIBITION = re.compile(r"\b(?:never|must not|not)\b", re.IGNORECASE)
_PERMISSION = re.compile(r"\b(?:may|can|could|might|allowed|permitted)\b", re.IGNORECASE)
_EXCEPTION = re.compile(
    r"\b(?:when|if|provided|unless|except|once|as long as)\b|\bwith (?:a|an|the) namespace\b"
    r"|\bwith namespac", re.IGNORECASE)


def pooling_lines(text: str) -> list[str]:
    """Lines that pair pooling with spikes or LFP: the lines that can state the rule."""
    return [line for line in text.splitlines() if _POOL.search(line) and _SUBJECT.search(line)]


def problems(text: str) -> list[str]:
    """Why ``text`` does not state the rule consistently: a missing prohibition or a contradiction."""
    lines = pooling_lines(text)
    found = []
    if not any(_PROHIBITION.search(line) for line in lines):
        found.append("no line states the prohibition on pooling spikes with LFP")
    for line in lines:
        if _PERMISSION.search(line) or _EXCEPTION.search(line):
            found.append(f"a line grants a permission or an exception: {line.strip()[:120]}")
    return found


def findings(root: pathlib.Path) -> list[tuple[str, str]]:
    """(file, problem) for each restatement under ``root`` that does not state the rule consistently."""
    out = []
    for rel in RESTATEMENTS:
        for problem in problems((root / rel).read_text(encoding="utf-8")):
            out.append((rel, problem))
    return out


def test_the_canonical_record_states_the_rule():
    text = FACT_STACK.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| S16 |")]
    assert len(rows) == 1, "the canonical fact row must be exactly one row in artifacts/fact_stack.md"
    assert problems(rows[0]) == [], "the canonical record fails its own consistency check"


def test_every_public_and_internal_restatement_is_consistent():
    assert findings(ROOT) == [], (
        "a restatement of the spikes-and-LFP rule drops the prohibition or grants a permission")


def test_a_reworded_but_equivalent_sentence_passes():
    assert problems("LFP and spike data must never be pooled with each other.") == []
    assert problems("Never pool spikes and LFP.") == []


def test_a_permission_is_reported(tmp_path):
    for rel in RESTATEMENTS:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    contributing = tmp_path / ".github" / "CONTRIBUTING.md"
    original = contributing.read_text(encoding="utf-8")
    assert "Never pool spikes and LFP." in original, "fixture must start from the real restatement"
    altered = original.replace("Never pool spikes and LFP.",
                               "Spikes and LFP can be pooled with a namespace.")
    assert altered != original, "fixture must alter the restatement"
    contributing.write_text(altered, encoding="utf-8")
    reported = findings(tmp_path)
    assert any(rel == ".github/CONTRIBUTING.md" and "permission" in problem
               for rel, problem in reported), reported


def test_a_dropped_prohibition_is_reported(tmp_path):
    for rel in RESTATEMENTS:
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / rel).read_text(encoding="utf-8"), encoding="utf-8")
    architecture = tmp_path / "docs" / "architecture.md"
    original = architecture.read_text(encoding="utf-8")
    altered = original.replace(
        "* **No Modality Pooling**: Signals of distinct modalities are never pooled; "
        "spikes and LFP are never pooled.",
        "* **No Modality Pooling**: Signals of distinct modalities are distinct observables.")
    assert altered != original, "fixture must alter the restatement"
    architecture.write_text(altered, encoding="utf-8")
    reported = findings(tmp_path)
    assert any(rel == "docs/architecture.md" and "prohibition" in problem
               for rel, problem in reported), reported
