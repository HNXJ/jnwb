"""The root skill reaches every skill, and each skill describes itself once.

`skills/jnwb/SKILL.md` is the entry point: a skill it never names is reachable only by an
agent that already knows it exists. Each skill also carries its description twice, in the
SKILL.md frontmatter and in `agents/openai.yaml`, and a host reads whichever file it loads;
two texts for one description let the two hosts route differently. The router's routing table
is copied onto `docs/agents.md` for readers without a checkout, and the copy is held equal to it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

import jnwb

SKILLS = Path(__file__).resolve().parents[1] / "skills"
ROUTER = SKILLS / "jnwb" / "SKILL.md"
DOCS_AGENTS = SKILLS.parent / "docs" / "agents.md"
ROUTING_HEADER = "| Task | Skill |"


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


_ROW_HEAD_END = re.compile(r"`:\s")


def _routed_operations(text: str) -> list[str]:
    """Every `jnwb.` operation a routing bullet routes, in order.

    A routing bullet opens with one or more backticked calls and ends its head at the colon
    after the last of them. Every call in the head is routed by that bullet; a call named in
    the description after the colon is a mention, not a route. A bullet with no "`: " after a
    closing tick (the "→" rows, for one) has no such boundary and is read whole.
    """
    found: list[str] = []
    for line in text.splitlines():
        if not line.startswith("- `jnwb."):
            continue
        end = _ROW_HEAD_END.search(line)
        head = line[: end.start() + 1] if end else line
        found.extend(re.findall(r"`(jnwb\.[\w.]+)", head))
    return found


def test_each_operation_has_one_routing_row() -> None:
    """`raster_psth` had a row in both `jnwb-spiking` and `jnwb-figures`, saying different things."""
    owners: dict[str, list[str]] = {}
    for skill in _skill_dirs():
        for op in _routed_operations((SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")):
            owners.setdefault(op, []).append(skill)
    assert owners, "no routing row was found; this test checks nothing"
    shared = {op: skills for op, skills in owners.items() if len(skills) > 1}
    assert not shared, f"operations routed by more than one row: {shared}"


#: The rows `jnwb-paradigm` took from `jnwb-nwb-data`: experiment structure, timing and
#: conditions. `detect_trial_cycles` and `assign_subblock_quartiles` shared one row and moved as one.
PARADIGM_ROUTES = (
    "jnwb.assign_subblock_quartiles", "jnwb.detect_trial_cycles", "jnwb.epoch_continuous",
    "jnwb.EpochCollection", "jnwb.events", "jnwb.EventTable", "jnwb.resolve_interval_table",
)


def test_the_paradigm_rows_live_in_one_skill() -> None:
    """Each row `jnwb-paradigm` took is routed there once, and has left `jnwb-nwb-data`."""
    taken = _routed_operations((SKILLS / "jnwb-paradigm" / "SKILL.md").read_text(encoding="utf-8"))
    assert sorted(taken) == sorted(PARADIGM_ROUTES), f"jnwb-paradigm routes {sorted(taken)}"
    left = set(_routed_operations((SKILLS / "jnwb-nwb-data" / "SKILL.md").read_text(encoding="utf-8")))
    assert left, "no row of jnwb-nwb-data was read; the second check would pass on nothing"
    assert not left & set(PARADIGM_ROUTES), f"still routed by jnwb-nwb-data: {left & set(PARADIGM_ROUTES)}"


#: The rows `jnwb-qc` routes: the audits and the unit-quality classes and tiers from
#: `jnwb-nwb-data`, the plots from `jnwb-figures`, the unit-quality measures, and the result
#: records, which no skill routed before.
QC_ROUTES = (
    "jnwb.assign_quality_tier", "jnwb.audit_electrodes", "jnwb.audit_units",
    "jnwb.classify_unit_quality", "jnwb.enrich_units_dataframe", "jnwb.get_snr_analysis",
    "jnwb.isi_cv", "jnwb.Lineage", "jnwb.presence_ratio", "jnwb.Provenance",
    "jnwb.refractory_contamination", "jnwb.Result", "jnwb.spatial_derivative_sharpness",
    "jnwb.visual_qc", "jnwb.waveform_features", "jnwb.waveform_flatness", "jnwb.waveform_snr",
)


def test_the_qc_rows_live_in_one_skill() -> None:
    """Each row `jnwb-qc` routes is there once, and has left the skills it came from."""
    taken = _routed_operations((SKILLS / "jnwb-qc" / "SKILL.md").read_text(encoding="utf-8"))
    assert sorted(taken) == sorted(QC_ROUTES), f"jnwb-qc routes {sorted(taken)}"
    for source in ("jnwb-nwb-data", "jnwb-figures"):
        left = set(_routed_operations((SKILLS / source / "SKILL.md").read_text(encoding="utf-8")))
        assert left, f"no row of {source} was read; the check would pass on nothing"
        assert not left & set(QC_ROUTES), f"still routed by {source}: {left & set(QC_ROUTES)}"
    for symbol in QC_ROUTES:
        assert symbol.removeprefix("jnwb.") in jnwb.__all__, f"{symbol} is not exported"


def test_the_row_parser_reads_every_call_a_bullet_routes() -> None:
    rows = (
        "- `jnwb.raster_psth(st, onsets, win_ms, bin_ms)`: Binned arrays.\n"
        "- `jnwb.audit_units(nwb)`, `jnwb.audit_electrodes(nwb)`: Two audits.\n"
        "- `jnwb.jrsa(x1, x2)`: Reverse of `jnwb.granger(X, Y)`.\n"
        "- plain bullet naming `jnwb.band_power(x)`\n"
    )
    assert _routed_operations(rows) == [
        "jnwb.raster_psth", "jnwb.audit_units", "jnwb.audit_electrodes", "jnwb.jrsa"]


def test_a_second_call_routed_in_two_skills_is_found() -> None:
    """The second call of a two-call bullet is a route: routed again elsewhere, it is shared."""
    first = "- `jnwb.audit_units(nwb)`, `jnwb.audit_electrodes(nwb)`: Two audits.\n"
    second = "- `jnwb.audit_electrodes(nwb)`: One audit.\n"
    assert set(_routed_operations(first)) & set(_routed_operations(second)) == {
        "jnwb.audit_electrodes"}


def _table_rows(text: str, header: str) -> list[str]:
    """The body rows of the first table whose header line is `header`, stripped."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == header), None)
    assert start is not None, f"no table headed {header!r}"
    rows = []
    for line in lines[start + 1:]:
        line = line.strip()
        if not line.startswith("|"):
            break
        if not re.fullmatch(r"\|(?:\s*:?-+:?\s*\|)+", line):
            rows.append(line)
    return rows


_COUNT_WORDS = r"one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|\d+"
_SKILL_COUNT = re.compile(rf"\b(?:{_COUNT_WORDS})\b(?= (?:[\w-]+ ){{0,2}}skills\b)", re.I)


def _stated_skill_counts(text: str) -> list[str]:
    """Every number written in front of "skills", with at most two words between them."""
    return _SKILL_COUNT.findall(text)


def test_the_docs_skill_table_is_the_routers_table() -> None:
    """`docs/agents.md` kept a second skill table that disagreed with the router's."""
    router = _table_rows(_routing_section(ROUTER.read_text(encoding="utf-8")), ROUTING_HEADER)
    docs = _table_rows(DOCS_AGENTS.read_text(encoding="utf-8"), ROUTING_HEADER)
    assert router, "the router's routing table has no rows"
    assert docs == router, "docs/agents.md's routing table differs from the router's"


def test_the_docs_page_names_every_skill_and_states_no_count() -> None:
    """`docs/agents.md` wrote the skill count in prose, a second copy of the directory listing."""
    page = DOCS_AGENTS.read_text(encoding="utf-8")
    named = sorted(set(re.findall(r"`(jnwb(?:-[\w-]+)?)`", page)) & set(_skill_dirs()))
    assert named == _skill_dirs(), f"docs/agents.md names only {named}"
    counted = _stated_skill_counts(page)
    assert not counted, f"docs/agents.md states a skill count: {counted}"


@pytest.mark.parametrize("text", ["Nine shipped skills", "nine domain skills", "9 skills",
                                  "nine shipped domain skills"])
def test_a_planted_skill_count_is_caught(text: str) -> None:
    assert _stated_skill_counts(f"The repository has {text} in it.")


def test_a_skill_table_row_changed_on_one_side_is_caught() -> None:
    table = f"{ROUTING_HEADER}\n|---|---|\n| Spike trains | `jnwb-spiking` |\n\nAfter.\n"
    assert _table_rows(table, ROUTING_HEADER) == ["| Spike trains | `jnwb-spiking` |"]
    changed = table.replace("Spike trains", "Spike trains and LFP")
    assert _table_rows(changed, ROUTING_HEADER) != _table_rows(table, ROUTING_HEADER)


@pytest.mark.parametrize("skill", _skill_dirs())
def test_openai_yaml_description_equals_the_skill_description(skill: str) -> None:
    md = _frontmatter(SKILLS / skill / "SKILL.md")["description"]
    host = yaml.safe_load(
        (SKILLS / skill / "agents" / "openai.yaml").read_text(encoding="utf-8")
    )["interface"]["description"]
    assert isinstance(md, str) and isinstance(host, str)
    assert host == md, f"{skill}: openai.yaml says {host!r}; SKILL.md says {md!r}"
