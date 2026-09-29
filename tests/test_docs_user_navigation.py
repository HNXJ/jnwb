"""The documentation site is for readers of the library, not for its contributors.

About a sixth of the published words addressed contributors from the navigation: a 117-word
page whose own first sentence called itself a pointer, and a 2,800-word developer guide whose
sections 1-8 were the rules for changing `jnwb` -- on the user path, under "Tutorials &
Development", while `CONTRIBUTING.md` said those rules lived there and it said the mechanics
lived in `CONTRIBUTING.md`. The pointer page had already drifted inside that loop: it said
"gates 1-12" where the runner prints 13.

What a *caller* needs out of that guide -- the RNG, device, failure-state, shape and unit
conventions, and the per-operation table -- is documentation and stayed, as
`docs/10_operation_specifications.md`.

These tests hold the shape rather than the episode: every page is reachable, every nav entry
resolves, and nothing on the nav tells a reader about a file that ships in no artifact.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
MKDOCS = REPO_ROOT / "mkdocs.yml"

#: Paths a reader cannot open: `tests/` and `scripts/` are in neither the wheel nor the
#: sdist, and `PLACEHOLDER-DUMMY` is an internal scaffolding marker.
CONTRIBUTOR_MARKERS = (
    "tests/test_",
    "scripts/harness_gate.py",
    "scripts/release_gate.py",
    "artifacts/todo_stack.md",
    "PLACEHOLDER-DUMMY",
)


def nav_targets(mkdocs: Path = MKDOCS) -> list[str]:
    """Every `.md` file on the parsed nav of `mkdocs`, in order, as written.

    Read through YAML, so a commented-out line is not an entry: it is not on the site either.
    """
    config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
    found: list[str] = []

    def walk(node):
        if isinstance(node, str):
            if node.endswith(".md"):
                found.append(node)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)

    walk(config.get("nav") or [])
    return found


def _nav_targets():
    return nav_targets(MKDOCS)


def test_the_navigation_is_read_at_all():
    targets = _nav_targets()
    assert len(targets) >= 25, f"only {len(targets)} nav entries parsed; the reader is broken"


def test_no_nav_entry_is_dead():
    for target in _nav_targets():
        assert (DOCS / target).is_file(), f"mkdocs.yml navigates to missing docs/{target}"


def test_no_page_is_listed_twice():
    targets = _nav_targets()
    duplicates = {t for t in targets if targets.count(t) > 1}
    assert not duplicates, f"listed more than once on the nav: {sorted(duplicates)}"


def excluded_from_the_site(mkdocs: Path = MKDOCS) -> set[str]:
    """The `exclude_docs` entries of `mkdocs`: files under `docs/` the build does not publish."""
    config = yaml.safe_load(mkdocs.read_text(encoding="utf-8")) or {}
    return {line.strip() for line in (config.get("exclude_docs") or "").splitlines()
            if line.strip() and not line.strip().startswith("#")}


def _excluded_from_the_site():
    return excluded_from_the_site(MKDOCS)


def orphaned_pages(docs: Path = DOCS, mkdocs: Path = MKDOCS) -> set[str]:
    """Pages under `docs` that the build publishes and no live nav entry reaches."""
    present = {p.relative_to(docs).as_posix() for p in docs.rglob("*.md")}
    return present - set(nav_targets(mkdocs)) - excluded_from_the_site(mkdocs)


def test_no_page_is_orphaned():
    """Every published page is on the nav. A page the build excludes is not published."""
    orphans = orphaned_pages(DOCS, MKDOCS)
    assert orphans == set(), f"pages exist but are on no nav entry: {sorted(orphans)}"


def test_no_excluded_page_is_on_the_nav():
    """An excluded page on the nav is a dead link on the site, and would hide a user page."""
    excluded = _excluded_from_the_site()
    assert "documentation_form.md" in excluded, (
        "the exclusion list was not read, or the contributor contract is published again"
    )
    assert not excluded & set(_nav_targets()), (
        f"excluded from the build but on the nav: {sorted(excluded & set(_nav_targets()))}"
    )


def test_no_page_on_the_user_navigation_addresses_contributors():
    for target in _nav_targets():
        text = (DOCS / target).read_text(encoding="utf-8")
        for marker in CONTRIBUTOR_MARKERS:
            assert marker not in text, (
                f"docs/{target} names {marker!r}, which a reader who installed jnwb does not "
                "have; contributor material belongs in CONTRIBUTING.md or AGENTS.md"
            )


def test_no_published_page_names_the_release_checks_or_links_the_form_contract():
    """The landing and install pages described jnwb by its release checks, and the glossary
    linked the contributor contract that the build no longer publishes."""
    for page, phrase in (("index.md", "gate-enforced"), ("index.md", "release gate"),
                         ("install.md", "gate-enforced"), ("install.md", "release gate")):
        assert phrase not in (DOCS / page).read_text(encoding="utf-8"), (
            f"docs/{page} says {phrase!r}, which describes a repository check, not the library"
        )
    pages = [p for p in DOCS.rglob("*.md") if p.name != "documentation_form.md"]
    assert len(pages) >= 25, f"only {len(pages)} pages read"
    linking = [p.relative_to(DOCS).as_posix() for p in pages
               if re.search(r"\]\([^)]*documentation_form", p.read_text(encoding="utf-8"))]
    assert not linking, f"pages link the unpublished form contract: {linking}"


def test_the_specification_page_kept_what_only_it_documented():
    """The split had to preserve section 9.2, not merely move most of it."""
    spec = (DOCS / "10_operation_specifications.md").read_text(encoding="utf-8")
    for symbol in ("aperiodic_fit", "vflip", "vflip_from_lfp", "label_layers", "xflip",
                   "zflip", "probe_geometry", "stream_npz_array", "relative_power"):
        assert f"`{symbol}`" in spec, f"the operation table lost {symbol}"
    for convention in ("RNG Convention", "Device Convention", "Physical Units",
                       "Axis & Dimension Vocabulary", "Structured Return Types"):
        assert convention in spec, f"the cross-cutting invariants lost {convention}"
