"""Every documentation figure embed has a state line and a Still and an Interactive tab.

The MkDocs hook makes the tabs and the state line at build time, from the registry. These tests run
the hook over the real pages and over planted ones. The allowlist gate admits an iframe only from
the figures site, and the examined set must not be empty.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = REPO_ROOT / "scripts" / "figures"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, FIGURE_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


hook = _load("mkdocs_figure_hook")
registry = _load("figure_registry")
ENTRIES = registry.loads(registry.REGISTRY.read_text(encoding="utf-8"))
PAGES = sorted((REPO_ROOT / "docs").rglob("*.md"))

PAIR = (
    "![Planted](../assets/figures/fig01_addressing_laminar.png#only-light)\n"
    "![Planted](../assets/figures/fig01_addressing_laminar.dark.png#only-dark)\n"
)


#: Pages that embed a figure the hook does not turn into tabs, and why. A page outside the hook that
#: is not listed here fails the audit, and so does a listed page that no longer embeds one.
OUTSIDE_THE_HOOK = {
    "index.md": "the Figures gallery is raw HTML tiles, where the hook cannot place tabs",
    "quickstart.md": "assets/jnwb_quickstart.png comes from examples/quickstart_jnwb.py, which has no registry entry",
    "vis.md": "assets/vis/sorted_heatmap.png is a jnwb.vis Plotly export, which has no registry entry",
}
FIGURE_REF = re.compile(r"assets/(?:figures|vis)/|assets/jnwb_[a-z_]+\.png")


def _outside_the_hook(text: str) -> list:
    """The lines that embed a figure the hook does not turn into tabs."""
    return [line for line in text.split("\n")
            if FIGURE_REF.search(line) and not hook.LIGHT.match(line) and not hook.DARK.match(line)]


def test_every_page_that_embeds_a_figure_is_under_the_hook_or_listed():
    examined = 0
    outside = {}
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        examined += len(FIGURE_REF.findall(text))
        found = _outside_the_hook(text)
        if found:
            outside[page.relative_to(REPO_ROOT / "docs").as_posix()] = len(found)
    assert examined > 0, "no figure reference was examined; the audit walked nothing"
    assert set(outside) == set(OUTSIDE_THE_HOOK), f"outside the hook: {outside}; listed: {sorted(OUTSIDE_THE_HOOK)}"


def test_a_figure_outside_the_hook_is_named_by_the_audit():
    assert len(_outside_the_hook('![Planted](assets/vis/planted.png)')) == 1
    assert _outside_the_hook(PAIR) == []


def _embeds(text: str) -> int:
    return sum(1 for line in text.split("\n") if hook.LIGHT.match(line))


def test_every_figure_embed_in_the_docs_has_both_tabs_and_a_state_line():
    examined = 0
    for page in PAGES:
        text = page.read_text(encoding="utf-8")
        embeds = _embeds(text)
        if not embeds:
            continue
        examined += embeds
        built = hook.transform(text, ENTRIES)
        page_name = page.relative_to(REPO_ROOT).as_posix()
        assert built.count('=== "Still"') == embeds, page_name
        assert built.count('=== "Interactive"') == embeds, page_name
        assert built.count("Validation: ") == embeds, page_name
    assert examined > 0, "no figure embed was examined; the walk is wrong"


def test_the_iframes_of_the_built_docs_are_allowlisted_and_examined():
    iframes = 0
    for page in PAGES:
        built = hook.transform(page.read_text(encoding="utf-8"), ENTRIES)
        iframes += built.count("<iframe ")
        assert hook.iframe_violations(built) == [], page.relative_to(REPO_ROOT).as_posix()
    assert iframes > 0, "no iframe was examined; the allowlist gate read nothing"


def test_an_iframe_from_another_host_fails_the_allowlist_gate():
    planted = '<iframe src="https://example.com/fig.html"></iframe>'
    assert len(hook.iframe_violations(planted)) == 1


def test_an_embed_without_a_registry_entry_fails_the_build():
    with pytest.raises(hook.FigureError, match="fig01_addressing_laminar.png"):
        hook.transform(PAIR, {})


def test_an_embed_without_its_dark_twin_fails_the_build():
    with pytest.raises(hook.FigureError, match="dark"):
        hook.transform(PAIR.split("\n")[0] + "\n", ENTRIES)
