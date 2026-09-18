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


def _nav_targets():
    """Every `.md` file named on the nav, in order, as written."""
    nav = MKDOCS.read_text(encoding="utf-8").split("\nnav:", 1)[1]
    nav = nav.split("\n\n\n", 1)[0]
    return re.findall(r":\s*([A-Za-z0-9_/\.\-]+\.md)\s*$", nav, re.M)


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


def test_no_page_is_orphaned():
    on_nav = set(_nav_targets())
    present = {p.relative_to(DOCS).as_posix() for p in DOCS.rglob("*.md")}
    assert present - on_nav == set(), (
        f"pages exist but are on no nav entry: {sorted(present - on_nav)}"
    )


def test_no_page_on_the_user_navigation_addresses_contributors():
    for target in _nav_targets():
        text = (DOCS / target).read_text(encoding="utf-8")
        for marker in CONTRIBUTOR_MARKERS:
            assert marker not in text, (
                f"docs/{target} names {marker!r}, which a reader who installed jnwb does not "
                "have; contributor material belongs in CONTRIBUTING.md or AGENTS.md"
            )


def test_the_specification_page_kept_what_only_it_documented():
    """The split had to preserve section 9.2, not merely move most of it."""
    spec = (DOCS / "10_operation_specifications.md").read_text(encoding="utf-8")
    for symbol in ("aperiodic_fit", "vflip", "vflip_from_lfp", "label_layers", "xflip",
                   "zflip", "probe_geometry", "stream_npz_array", "relative_power"):
        assert f"`{symbol}`" in spec, f"the operation table lost {symbol}"
    for convention in ("RNG Convention", "Device Convention", "Physical Units",
                       "Axis & Dimension Vocabulary", "Structured Return Types"):
        assert convention in spec, f"the cross-cutting invariants lost {convention}"
