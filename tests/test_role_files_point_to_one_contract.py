"""Each role file points to the one packet contract and the one loading order; it keeps no copy.

`artifacts/agents/authority.md` kept a loading order of its own that reached neither the
direction, the goal, the state nor the problem stack, and five role files each listed a private
subset of the packet fields, none of which named `BASELINE COMMIT`. The packet and its return
contract are defined in `artifacts/skills/jnwb-fact-action` section 5 and the order in
`AGENTS.md` section 3. So a role file names at most one packet field, one return field and one
authority file per block, and every `artifacts/skills/<name>` it or a repository skill points
at is a skill on disk.

The unit is the block, not the line: a copy written one field per bullet, one file per numbered
line, or inside a fenced block puts each name on a line of its own, and a per-line sweep passed
all three. A block is text between blank lines, and a fenced block is one block whatever it
holds. Field names are matched in capitals with or without backticks. A copy spread across
separate paragraphs, one name each, is still not caught.

Each sweep is a function over text, run once over the live files, where it must find nothing,
and once over text built to carry the defect, where it must find it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ROLES = REPO_ROOT / "artifacts" / "agents"
PROCESS_SKILL = REPO_ROOT / "artifacts" / "skills" / "jnwb-fact-action" / "SKILL.md"
REVIEW_POINTER = "artifacts/skills/jnwb-review"

#: The files `AGENTS.md` section 3 loads after itself. Two in one block is an order written out.
AUTHORITY_FILES = ("direction.md", "goal.md", "fact_stack.md", "state.md",
                   "problem_stack.md", "todo_stack.md")
SKILL_POINTER = re.compile(r"artifacts/skills/([\w-]+)")


def _contract_blocks() -> list[str]:
    section = PROCESS_SKILL.read_text(encoding="utf-8").split("## 5.", 1)[1].split("\n## ", 1)[0]
    return re.findall(r"```text\r?\n(.*?)```", section, re.S)


def _field_names(block: str) -> set[str]:
    return set(re.findall(r"^\s*([A-Z][A-Z ]*[A-Z]):", block, re.M))


def packet_fields() -> set[str]:
    """The packet's field names, read from the first `text` block of section 5."""
    return _field_names(_contract_blocks()[0])


def return_fields() -> set[str]:
    """The return contract's field names, read from the second `text` block of section 5."""
    return _field_names(_contract_blocks()[1])


def blocks(text: str) -> list[str]:
    """Text between blank lines; a fenced block stays whole."""
    found, current, fenced = [], [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
        if not fenced and not line.strip():
            if current:
                found.append("\n".join(current))
            current = []
        else:
            current.append(line)
    if current:
        found.append("\n".join(current))
    return found


def _named(names, block: str) -> set[str]:
    return {n for n in names if re.search(rf"(?<![A-Z]){re.escape(n)}(?![A-Z])", block)}


def copied_lists(text: str) -> list[str]:
    """Blocks naming two or more packet fields, return fields or authority files."""
    packet, contract = packet_fields(), return_fields()
    found = []
    for block in blocks(text):
        files = {f for f in AUTHORITY_FILES if re.search(rf"\b{re.escape(f)}\b", block)}
        if len(_named(packet, block)) >= 2 or len(_named(contract, block)) >= 2 or len(files) >= 2:
            found.append(block.strip())
    return found


def dangling_skill_pointers(text: str) -> list[str]:
    return sorted({name for name in SKILL_POINTER.findall(text)
                   if not (REPO_ROOT / "artifacts" / "skills" / name / "SKILL.md").is_file()})


def test_the_contract_is_read_from_the_skill():
    assert {"BASELINE COMMIT", "ALLOWED SCOPE", "ACCEPTANCE"} <= packet_fields()
    assert {"RESULT", "CLAIMS", "UNRESOLVED"} <= return_fields()


def test_no_role_file_copies_the_packet_the_contract_or_the_loading_order():
    roles = sorted(ROLES.glob("*.md"))
    assert len(roles) >= 6, f"only {len(roles)} role files read"
    offenders = {p.name: hits for p in roles
                 if (hits := copied_lists(p.read_text(encoding="utf-8")))}
    assert not offenders, (
        f"role files carry their own packet, return contract or loading order: {offenders}. "
        "Point to `artifacts/skills/jnwb-fact-action` section 5 and `AGENTS.md` section 3."
    )


PLANTED = {
    "fenced packet": "```text\nGOAL: <x>\n\nTODO ITEM: <x>\n\nBASELINE COMMIT: <x>\n```\n",
    "one field per bullet": "- `GOAL`\n- `TODO ITEM`\n- `ALLOWED SCOPE`\n",
    "numbered loading order": ("1. `AGENTS.md`\n2. `artifacts/direction.md`\n"
                               "3. `artifacts/goal.md`\n"),
    "unbackticked inline list": "Expects a packet specifying GOAL, TODO ITEM and ACCEPTANCE.\n",
    "restated return contract": "Returns `RESULT: PASS | DEFECT | BLOCKED`, `CLAIMS` and `UNRESOLVED`.\n",
}


@pytest.mark.parametrize("case", sorted(PLANTED))
def test_the_sweep_catches_a_copied_list(case):
    assert len(copied_lists(PLANTED[case])) == 1, case


def test_the_sweep_passes_a_single_field_and_separate_blocks():
    text = ("Mutates only files explicitly allowed in `ALLOWED SCOPE`.\n\n"
            "`OBSERVED BASELINE` is the reproduction command.\n")
    assert copied_lists(text) == []


def _fact_action_verification() -> str:
    return PROCESS_SKILL.read_text(encoding="utf-8").split("### V", 1)[1].split("\n### ", 1)[0]


@pytest.mark.parametrize("source", ["critic.md", "verifier.md", "docs-harness.md",
                                    "fact-action V"])
def test_each_reviewer_points_to_the_review_skill(source):
    text = (_fact_action_verification() if source == "fact-action V"
            else (ROLES / source).read_text(encoding="utf-8"))
    assert REVIEW_POINTER in text, f"{source} does not point to {REVIEW_POINTER}"


def test_every_pointer_to_a_repository_skill_resolves():
    sources = [*sorted(ROLES.glob("*.md")),
               *sorted((REPO_ROOT / "artifacts" / "skills").glob("*/SKILL.md")),
               REPO_ROOT / "AGENTS.md"]
    texts = {p.relative_to(REPO_ROOT).as_posix(): p.read_text(encoding="utf-8") for p in sources}
    assert REVIEW_POINTER in texts["AGENTS.md"], "AGENTS.md section 7 does not name the review skill"
    dangling = {name: d for name, t in texts.items() if (d := dangling_skill_pointers(t))}
    assert not dangling, f"pointers to skills that do not exist: {dangling}"
    assert dangling_skill_pointers("see `artifacts/skills/jnwb-reveiw`") == ["jnwb-reveiw"]
