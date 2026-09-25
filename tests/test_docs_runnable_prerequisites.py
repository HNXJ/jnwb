"""Every runnable instruction in the documentation states what it needs.

`examples/` is not a package, so `[tool.setuptools.packages.find] include = ["jnwb*"]`
leaves it out of the wheel, and `MANIFEST.in` grafts `skills` but not
`examples`, so it is out of the sdist too. `python examples/tutorials/NN_*.py` was
nonetheless the only runnable line on all nine tutorial pages and on `quickstart.md`, and
`install.md` led with `pip install jnwb` and offered a clone as a development alternative.
A reader who installed from PyPI was told to run a file they do not have, and the error
names a path rather than the reason.

These tests hold the statement and the fact it asserts together: one sweeps the pages that
give the instruction, the other reads the packaging configuration, so the note cannot
survive `examples/` starting to ship and cannot be dropped while it does not.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
RUN_INSTRUCTION = re.compile(r"python examples/")
# Checking only for the word "clone" would be satisfied by any page that happens to mention
# git; the prerequisite has to be stated where the instruction is.
PREREQUISITE = re.compile(r"neither the wheel nor the sdist.*?clone", re.S)
# And it has to be attached to each instruction rather than to the page: quickstart.md
# carries two, so a page-level check passed with the note under one of them deleted.
WINDOW = 400


def _pages_that_tell_a_reader_to_run_something_from_examples():
    pages = {}
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        if RUN_INSTRUCTION.search(text):
            pages[page.relative_to(REPO_ROOT).as_posix()] = text
    return pages


def test_the_sweep_finds_the_pages_it_is_written_for():
    """Non-vacuity: nine tutorials plus the quickstart carried the instruction."""
    pages = _pages_that_tell_a_reader_to_run_something_from_examples()
    assert len(pages) >= 10, f"only {len(pages)} pages matched; the sweep has stopped working"
    assert "docs/quickstart.md" in pages


def test_every_instruction_to_run_examples_says_a_clone_is_required():
    checked = 0
    for rel, text in _pages_that_tell_a_reader_to_run_something_from_examples().items():
        for match in RUN_INSTRUCTION.finditer(text):
            checked += 1
            window = text[match.start():match.start() + WINDOW]
            assert PREREQUISITE.search(window), (
                f"{rel} tells a reader to run {text[match.start():match.start() + 48]!r}, "
                "from an examples/ tree that ships in neither the wheel nor the sdist, "
                "without saying a clone is required"
            )
    assert checked >= 11, f"only {checked} instructions were checked"


def test_examples_still_ships_in_neither_artifact():
    """The premise of the note above, read from the configuration that decides it.

    If `examples/` is ever added to the wheel or the sdist, the pages become wrong in the
    other direction and this fails rather than leaving them wrong quietly.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["jnwb*"], (
        f"packages.find include is {include}; the wheel may now carry examples/"
    )

    manifest = (REPO_ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    for line in manifest.splitlines():
        directive = line.split("#", 1)[0].split()
        if directive and directive[0] in {"graft", "include", "recursive-include"}:
            assert not any(part.startswith("examples") for part in directive[1:]), (
                f"MANIFEST.in line {line!r} may put examples/ in the sdist"
            )


def test_the_documentation_figure_is_the_one_the_script_writes():
    """`docs/assets/jnwb_quickstart.png` is a copy, and a copy goes stale.

    It is the only rendering of the quickstart figure a documentation reader sees, and it
    was two weeks older than the script's own output -- showing a permutation panel the
    library no longer computes at all, since the script exited before writing anything.
    """
    for name in ("jnwb_quickstart.png", "jnwb_quickstart.dark.png"):
        rendered = REPO_ROOT / "examples" / "figures" / name
        published = DOCS / "assets" / name
        assert rendered.is_file() and published.is_file(), name
        assert published.read_bytes() == rendered.read_bytes(), (
            f"docs/assets/{name} differs from the figure "
            "examples/quickstart_jnwb.py writes; copy the rendered one over it"
        )
