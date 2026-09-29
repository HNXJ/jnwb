"""A standing rule writes its release labels as templates, never as one cycle's values.

The release gate derives the values it accepts from the declared version: `required-` plus the
version being released, `deferred-` plus the one after it. `AGENTS.md` section 11 and the problem
stack's header wrote them as `required-0.2.6` and `deferred-0.2.7`, so a triage in the next cycle
that followed the text wrote labels the gate reads as another cycle's. The rules now say
`required-<cycle>` and `deferred-<next>`, and this holds them to it.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: `required-0.2.6`, `deferred-0.2.7`, `release-step-0.2.6`: a label naming one cycle.
LITERAL_LABEL = re.compile(r"\b(?:required|deferred|release-step)-\d+\.\d+\.\d+")

#: Files that state rules for every cycle. The problem stack's header is one; its rows are not.
STANDING_FILES = ("AGENTS.md", "CONTRIBUTING.md", "artifacts/cooperation.md",
                  "artifacts/fact_stack.md")
STANDING_GLOBS = ("artifacts/agents/*.md", "artifacts/skills/*/SKILL.md")
PROBLEM_STACK = REPO_ROOT / "artifacts" / "problem_stack.md"


def _standing_texts() -> "dict[str, str]":
    paths = [REPO_ROOT / rel for rel in STANDING_FILES]
    for pattern in STANDING_GLOBS:
        paths.extend(sorted(REPO_ROOT.glob(pattern)))
    texts = {p.relative_to(REPO_ROOT).as_posix(): p.read_text(encoding="utf-8")
             for p in paths if p.is_file()}
    header = PROBLEM_STACK.read_text(encoding="utf-8").split("\n## Open", 1)[0]
    texts["artifacts/problem_stack.md (header)"] = header
    return texts


def test_the_sweep_reads_the_rules_it_is_written_for():
    texts = _standing_texts()
    assert "required-<cycle>" in texts["AGENTS.md"], "AGENTS.md no longer states the template"
    assert "deferred-<next>" in texts["artifacts/problem_stack.md (header)"], (
        "the problem stack's header was not read, or no longer states the template"
    )
    assert len(texts) >= 8, f"only {len(texts)} files read: {sorted(texts)}"


def test_no_standing_rule_names_a_literal_cycle_label():
    offenders = [f"{name}: {match}"
                 for name, text in _standing_texts().items()
                 for match in LITERAL_LABEL.findall(text)]
    assert not offenders, (
        f"standing rules name one cycle's label: {offenders}. Write `required-<cycle>` and "
        "`deferred-<next>`; the release gate derives the values from the declared version."
    )


def test_the_pattern_finds_each_literal_form_and_passes_the_templates():
    text = ("marked `required-0.2.6`, then `deferred-0.2.7` or `release-step-1.10.3`; "
            "the templates `required-<cycle>` and `deferred-<next>` are not labels")
    assert LITERAL_LABEL.findall(text) == ["required-0.2.6", "deferred-0.2.7",
                                           "release-step-1.10.3"]
