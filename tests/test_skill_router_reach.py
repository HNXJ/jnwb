"""The root skill reaches every skill, and each skill describes itself once.

`skills/jnwb/SKILL.md` is the entry point: a skill it never names is reachable only by an
agent that already knows it exists. Each skill also carries its description twice, in the
SKILL.md frontmatter and in `agents/openai.yaml`, and a host reads whichever file it loads;
two texts for one description let the two hosts route differently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

SKILLS = Path(__file__).resolve().parents[1] / "skills"
ROUTER = SKILLS / "jnwb" / "SKILL.md"


def _skill_dirs() -> list[str]:
    names = sorted(p.parent.name for p in SKILLS.glob("*/SKILL.md"))
    assert len(names) >= 8, f"only {len(names)} skills found under {SKILLS}"
    return names


def _routing_section(text: str) -> str:
    """The router's section 2, up to the next level-2 heading."""
    match = re.search(r"^## 2\. .*$", text, re.M)
    assert match, "the router has no section 2 to route from"
    return text[match.end():].split("\n## ", 1)[0]


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} has no frontmatter"
    return yaml.safe_load(text.split("---", 2)[1])


def test_the_router_names_every_skill_in_its_routing_section() -> None:
    section = _routing_section(ROUTER.read_text(encoding="utf-8"))
    unreached = [s for s in _skill_dirs() if s != "jnwb" and f"`{s}`" not in section]
    assert not unreached, f"the router's routing section never names {unreached}"


def test_a_skill_named_only_outside_the_routing_section_is_unreached() -> None:
    """The section boundary is what makes the check above mean routing, not mention."""
    text = "## 1. Trigger\n`jnwb-demo` is mentioned here.\n## 2. Routing\n| a | `jnwb-x` |\n## 3. X\n"
    section = _routing_section(text)
    assert "`jnwb-x`" in section and "`jnwb-demo`" not in section


def _routed_operations(text: str) -> list[str]:
    """The `jnwb.` operation each routing bullet opens with, in order."""
    return re.findall(r"^- `(jnwb\.[\w.]+)", text, re.M)


def test_each_operation_has_one_routing_row() -> None:
    """`raster_psth` had a row in both `jnwb-spiking` and `jnwb-figures`, saying different things."""
    owners: dict[str, list[str]] = {}
    for skill in _skill_dirs():
        for op in _routed_operations((SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")):
            owners.setdefault(op, []).append(skill)
    assert owners, "no routing row was found; this test checks nothing"
    shared = {op: skills for op, skills in owners.items() if len(skills) > 1}
    assert not shared, f"operations routed by more than one row: {shared}"


def test_a_row_repeated_in_two_skills_is_found() -> None:
    row = "- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Binned arrays.\n"
    assert _routed_operations(row + "- plain bullet\n") == ["jnwb.raster_psth"]


def test_the_docs_skill_table_is_the_skill_directories_and_states_no_count() -> None:
    """`docs/agents.md` wrote the skill count in prose, a second copy of the directory listing."""
    page = (SKILLS.parent / "docs" / "agents.md").read_text(encoding="utf-8")
    table = page.partition("| Skill | Covers |")[2].partition("\n\n")[0]
    listed = re.findall(r"^\| `([\w-]+)` \|", table, re.M)
    assert sorted(listed) == _skill_dirs(), f"the table lists {listed}"
    words = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+"
    counted = re.findall(rf"\b(?:{words})\b(?= (?:domain )?skills\b)", page, re.I)
    assert not counted, f"docs/agents.md states a skill count: {counted}"


@pytest.mark.parametrize("skill", _skill_dirs())
def test_openai_yaml_description_equals_the_skill_description(skill: str) -> None:
    md = _frontmatter(SKILLS / skill / "SKILL.md")["description"]
    host = yaml.safe_load(
        (SKILLS / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )["interface"]["description"]
    assert isinstance(md, str) and isinstance(host, str)
    assert host == md, f"{skill}: openai.yaml says {host!r}; SKILL.md says {md!r}"
