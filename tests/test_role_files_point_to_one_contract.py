"""Each role file points to the one packet contract and the one loading order; it keeps no copy.

`artifacts/agents/authority.md` kept a loading order of its own that reached neither the
direction, the goal, the state nor the problem stack, and five role files each listed a private
subset of the packet fields, none of which named `BASELINE COMMIT`. The packet is defined in
`artifacts/skills/jnwb-fact-action` section 5 and the order in `AGENTS.md` section 3, so a role
file names at most one packet field or one authority file per line, and every
`artifacts/skills/<name>` it or a repository skill points at is a skill on disk.

Each sweep is a function over text, run once over the live files, where it must find nothing,
and once over a line built to carry the defect, where it must find it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ROLES = REPO_ROOT / "artifacts" / "agents"
PROCESS_SKILL = REPO_ROOT / "artifacts" / "skills" / "jnwb-fact-action" / "SKILL.md"

#: The files `AGENTS.md` section 3 loads. Two of them on one line is an order written out.
AUTHORITY_FILES = ("direction.md", "goal.md", "fact_stack.md", "state.md",
                   "problem_stack.md", "todo_stack.md")
SKILL_POINTER = re.compile(r"artifacts/skills/([\w-]+)")


def packet_fields() -> set[str]:
    """The field names of the packet block in section 5, read from the skill itself."""
    section = PROCESS_SKILL.read_text(encoding="utf-8").split("## 5.", 1)[1]
    block = section.split("```text", 1)[1].split("```", 1)[0]
    return set(re.findall(r"^([A-Z][A-Z ]+):", block, re.M))


def copied_lists(text: str, fields: set[str]) -> list[str]:
    """Lines naming two or more packet fields, or two or more authority files."""
    found = []
    for line in text.splitlines():
        named_fields = {f for f in fields if f"`{f}`" in line}
        named_files = {f for f in AUTHORITY_FILES if re.search(rf"\b{re.escape(f)}\b", line)}
        if len(named_fields) >= 2 or len(named_files) >= 2:
            found.append(line.strip())
    return found


def dangling_skill_pointers(text: str) -> list[str]:
    return sorted({name for name in SKILL_POINTER.findall(text)
                   if not (REPO_ROOT / "artifacts" / "skills" / name / "SKILL.md").is_file()})


def test_the_packet_is_read_from_the_skill():
    fields = packet_fields()
    assert {"BASELINE COMMIT", "ALLOWED SCOPE", "ACCEPTANCE"} <= fields, fields


def test_no_role_file_copies_the_packet_or_the_loading_order():
    fields = packet_fields()
    roles = sorted(ROLES.glob("*.md"))
    assert len(roles) >= 6, f"only {len(roles)} role files read"
    offenders = {p.name: copied_lists(p.read_text(encoding="utf-8"), fields) for p in roles}
    offenders = {name: lines for name, lines in offenders.items() if lines}
    assert not offenders, (
        f"role files carry their own packet list or loading order: {offenders}. Point to "
        "`artifacts/skills/jnwb-fact-action` section 5 and `AGENTS.md` section 3 instead."
    )


def test_the_sweep_catches_a_copied_list():
    fields = packet_fields()
    planted = ("Expects a packet specifying `GOAL`, `TODO ITEM`, and `DOMAIN SKILL`.\n"
               "Load `AGENTS.md` -> `artifacts/fact_stack.md` -> `artifacts/todo_stack.md`.\n"
               "Mutates only files explicitly allowed in `ALLOWED SCOPE`.\n")
    assert len(copied_lists(planted, fields)) == 2


def test_every_pointer_to_a_repository_skill_resolves():
    sources = [*sorted(ROLES.glob("*.md")),
               *sorted((REPO_ROOT / "artifacts" / "skills").glob("*/SKILL.md")),
               REPO_ROOT / "AGENTS.md"]
    texts = {p.relative_to(REPO_ROOT).as_posix(): p.read_text(encoding="utf-8") for p in sources}
    review_pointers = sum(t.count("artifacts/skills/jnwb-review") for t in texts.values())
    assert review_pointers >= 4, f"only {review_pointers} pointers to the review skill found"
    dangling = {name: d for name, t in texts.items() if (d := dangling_skill_pointers(t))}
    assert not dangling, f"pointers to skills that do not exist: {dangling}"
    assert dangling_skill_pointers("see `artifacts/skills/jnwb-reveiw`") == ["jnwb-reveiw"]
