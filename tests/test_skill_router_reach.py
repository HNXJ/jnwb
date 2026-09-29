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


@pytest.mark.parametrize("skill", _skill_dirs())
def test_openai_yaml_description_equals_the_skill_description(skill: str) -> None:
    md = _frontmatter(SKILLS / skill / "SKILL.md")["description"]
    host = yaml.safe_load(
        (SKILLS / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )["interface"]["description"]
    assert isinstance(md, str) and isinstance(host, str)
    assert host == md, f"{skill}: openai.yaml says {host!r}; SKILL.md says {md!r}"
