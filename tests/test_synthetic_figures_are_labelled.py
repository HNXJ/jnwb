"""A documentation figure drawn from synthetic data says so beside it.

Every figure on the documentation site is generated from seeded synthetic signals
(`docs/generate_figures.py`, `examples/quickstart_jnwb.py`), and a reader who meets one on an
analysis page cannot tell that from the image. Nine of eleven captions did not say it. The
caption is the paragraph that follows the image; it names the data as synthetic, or the figure
is listed below as empirical with the source it was computed from.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

#: Figures computed from real data, by image path relative to `docs/`. None ship today; the
#: open-data tutorial prints its numbers rather than drawing them.
EMPIRICAL = {}

IMAGE = re.compile(r"^!\[[^\]]*\]\(([^)\s]+)\)\s*$", re.M)
#: The dark-scheme variant of a figure sits on the line after its light one; it is the same
#: figure, so it is neither counted again nor read as the light variant's caption.
DARK_VARIANT = "#only-dark"


def figure_captions(text: str):
    """Each (image path, caption) on a page: the caption is the next non-empty paragraph."""
    for m in IMAGE.finditer(text):
        if m.group(1).endswith(DARK_VARIANT):
            continue
        rest = text[m.end():].lstrip("\n")
        while (following := IMAGE.match(rest)) and following.group(1).endswith(DARK_VARIANT):
            rest = rest[following.end():].lstrip("\n")
        yield m.group(1), rest.split("\n\n", 1)[0]


def unlabelled(pages, root=DOCS):
    offenders = []
    for page in pages:
        for image, caption in figure_captions(page.read_text(encoding="utf-8")):
            if image in EMPIRICAL:
                continue
            if not re.search(r"\bsynthetic\b", caption, re.I):
                offenders.append(f"{page.relative_to(root).as_posix()}: {image}")
    return offenders


def _pages():
    return sorted(DOCS.rglob("*.md"))


def test_every_figure_says_it_is_synthetic():
    assert not unlabelled(_pages())


def test_the_reader_finds_every_figure():
    found = [img for page in _pages() for img, _ in figure_captions(page.read_text(encoding="utf-8"))]
    assert len(found) >= 11, f"only {len(found)} figures parsed; the reader has stopped working"


def test_an_unlabelled_caption_is_caught(tmp_path):
    page = tmp_path / "p.md"
    page.write_text(
        "Intro.\n\n![A](assets/a.png)\n\nPanel A is a trace.\n\n"
        "![B](assets/b.png)\n\nPanel B is a synthetic trace.\n",
        encoding="utf-8",
    )
    assert unlabelled([page], root=tmp_path) == ["p.md: assets/a.png"]


def test_the_dark_variant_is_skipped_to_reach_the_caption(tmp_path):
    page = tmp_path / "p.md"
    page.write_text(
        "![A](assets/a.png#only-light)\n![A](assets/a.dark.png#only-dark)\n\nPanel A is a trace.\n\n"
        "![B](assets/b.png#only-light)\n![B](assets/b.dark.png#only-dark)\n\nA synthetic trace.\n",
        encoding="utf-8",
    )
    assert unlabelled([page], root=tmp_path) == ["p.md: assets/a.png#only-light"]
