"""Restatements of the spikes-and-LFP rule agree with it in meaning, not in wording.

The canonical record is the fact row named S16 in ``artifacts/fact_stack.md``; the internal authority is
``AGENTS.md`` section 5. The public restatements may keep their own sentences. Sentences are read across line breaks. A sentence
that pools spikes or LFP must state the prohibition on the pooling verb, and no sentence that uses a
pooling word may grant a permission, an exception or a contrast. The record itself must pass the same test. Whether a sentence says exactly
what the record says is a review question; this test catches a contradiction or a dropped prohibition,
not every wording that could be wrong.
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACT_STACK = ROOT / "artifacts" / "fact_stack.md"
RESTATEMENTS = (".github/CONTRIBUTING.md", "docs/architecture.md", "skills/jnwb/SKILL.md", "AGENTS.md")

_POOL = re.compile(r"\bpool(?:s|ed|ing)?\b", re.IGNORECASE)
_SIGNAL = re.compile(r"\b(?:spikes?|SUA|MUA|LFP|them|both|across|modalit(?:y|ies)|observables?)\b", re.IGNORECASE)
_PROHIBITION = re.compile(
    r"\b(?:never|must not|must never|shall not|do not|does not|cannot|can not|not to|not allowed to|"
    r"not permitted to)\s+(?:be\s+)?pool"
    r"|(?<!not )\b(?:forbidden|prohibited|disallowed)\b", re.IGNORECASE)
_CONTRAST = re.compile(
    r"\bnot (?:true|required|necessary|needed)\b|\bnever\s+not\b|\bnot\s+never\b"
    r"|\b(?:avoid|avoids|avoiding|refuse|refuses|refusing|but|yet|however|although|though|"
    r"nevertheless|anyway|regardless|despite|instead|only|sometimes)\b", re.IGNORECASE)
_PERMISSION = re.compile(
    r"\b(?:may|can|could|might)\b(?:\s+\w+){0,2}\s+pool"
    r"|(?<!not )\b(?:okay|ok|fine|acceptable|allowed|permitted|freely|optional)\b"
    r"|\bnot (?:forbidden|prohibited|disallowed)\b|\bby default\b", re.IGNORECASE)
_EXCEPTION = re.compile(
    r"\b(?:when|if|provided|unless|except|once|as long as)\b|\bwith (?:a|an|the) namespace\b"
    r"|\bwith namespac", re.IGNORECASE)
_SPIKE = re.compile(r"\b(?:spikes?|SUA|MUA)\b", re.IGNORECASE)
_LFP = re.compile(r"\bLFP\b", re.IGNORECASE)


def sentences(text: str) -> list[str]:
    """Sentences of ``text``: paragraphs with their line breaks folded to spaces, split after . ; ! or ?."""
    out = []
    for paragraph in re.split(r"\n\s*\n", text):
        flat = " ".join(paragraph.split())
        out.extend(part for part in re.split(r"(?<=[.;!?])\s+", flat) if part)
    return out


def problems(text: str) -> list[str]:
    """Why ``text`` does not state the rule consistently: a missing prohibition, or a permission or exception.

    A sentence that pools signals (a spike, LFP, modality or signal-pair word) must state the prohibition
    on the pooling verb itself ("never pool", "must not be pooled", "forbidden"). Any sentence that uses a
    pooling word must grant no permission, no exception and no contrast (a negated rule, "but", "avoid").
    A block (paragraph or list item) that pools signals must name both spikes and LFP, so a dropped
    obligation (for example "Never pool spikes and EEG.") is reported.
    This is a fixed word list, not a parse: a contradiction phrased outside it passes.
    """
    pooled = [s for s in sentences(text) if _POOL.search(s)]
    signal = [s for s in pooled if _SIGNAL.search(s)]
    found = []
    if not any(_PROHIBITION.search(s) for s in signal):
        found.append("no sentence states the prohibition on pooling spikes with LFP")
    for s in signal:
        if not _PROHIBITION.search(s):
            found.append(f"a sentence pools signals without the prohibition: {s[:120]}")
    for s in pooled:
        if _PERMISSION.search(s) or _EXCEPTION.search(s) or _CONTRAST.search(s):
            found.append(f"a sentence grants a permission, an exception or a contrast: {s[:120]}")
    for block in re.split(r"\n\s*\n", text):
        flat = " ".join(block.split())
        pools = any(_POOL.search(s) and _SIGNAL.search(s) for s in sentences(flat))
        if pools and not (_SPIKE.search(flat) and _LFP.search(flat)):
            found.append(f"a block pools signals but does not name both spikes and LFP: {flat[:120]}")
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


# Probes from the independent review of 915cd91a (REVISE, 2026-11-25). Each REPORTED text grants a
# permission or states a pooling sentence without the prohibition; each PASSED text is consistent.
REPORTED = (
    "Never pool spikes and LFP.\nPool them freely.",
    "Never pool spikes and LFP.\nSpikes and LFP are pooled in the summary step.",
    "Never pool spikes and LFP; pooling is okay for a namespaced pair.",
    "LFP and spike data are never pooled, i.e. they remain separate; it is ok to pool them.",
    "Pooling spikes and LFP is acceptable, never mind.",
    "Spikes and LFP: pooling them is not forbidden.",
    "Never pool spikes and LFP.\nPool\nspikes and LFP freely.",
    "Spikes and LFP can be pooled with a namespace.",
    "Never pool spikes and LFP, but pool them in the report.",
    "It is not true that spikes and LFP are never pooled.",
    "Spikes and LFP are never not pooled.",
    "Do not avoid pooling spikes and LFP.",
    "We never refuse to pool spikes and LFP.",
    "Never pool spikes and LFP.\nPool them, never separately.",
    "Never pool spikes and LFP.\nNOT pooling is not required.",
    "Never pool spikes and LFP.\nPool them anyway.",
    "Pool them nevertheless.",
    "Never pool spikes and EEG.",
    "Never pool LFP and EEG.",
)
PASSED = (
    "Never pool spikes and LFP.",
    "Never pool\nspikes and LFP.",
    "LFP and spike data must never be pooled with each other.",
    "Never pool spikes and LFP, which can be confusing.",
    "Spikes and LFP are not allowed to be pooled.",
    "Spikes and LFP are distinct observables and must not be pooled.",
    "Implementation internals (pool mechanics, accumulator algorithms).\nNever pool spikes and LFP.",
    "Spikes and LFP are never pooled, namespaced or not.",
    "Spikes and LFP are not to be pooled.",
    "Pooling spikes and LFP is forbidden.",
)


def test_a_sentence_that_grants_a_permission_is_reported():
    for text in REPORTED:
        assert problems(text), f"not reported: {text!r}"


def test_a_consistent_sentence_is_not_reported():
    for text in PASSED:
        assert problems(text) == [], f"wrongly reported: {text!r}"
