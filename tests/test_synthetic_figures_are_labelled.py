"""A documentation figure drawn from synthetic data says so beside it.

Every figure on the documentation site is generated from seeded synthetic signals
(`docs/generate_figures.py`, `examples/quickstart_jnwb.py`), and a reader who meets one on an
analysis page cannot tell that from the image. Nine of eleven captions did not say it. The
caption of a Markdown image is the paragraph that follows it. An `<img>` in an HTML table cell
is captioned by its cell's `<sub>` text, read after the paragraph that introduces the table;
outside a table, by the paragraph that follows the tag. The caption names the data as
synthetic, or the figure is listed below as empirical with the source it was computed from.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"

#: Figures computed from real data, by image path relative to `docs/`. None ship today; the
#: open-data tutorial prints its numbers rather than drawing them.
EMPIRICAL = {}
#: Images that are not figures, by path.
DECORATION = {"assets/jnwb-logo.png": "the project logo on the landing page"}

IMAGE = re.compile(r"^!\[[^\]]*\]\(([^)\s]+)\)\s*$", re.M)
IMG_TAG = re.compile(r'<img src="([^"]+)"[^>]*>')
#: The dark-scheme variant of a figure sits beside its light one; it is the same figure, so it
#: is neither counted again nor read as the light variant's caption.
DARK_VARIANT = "#only-dark"


def _markdown_captions(text: str):
    for m in IMAGE.finditer(text):
        if m.group(1).endswith(DARK_VARIANT):
            continue
        rest = text[m.end():].lstrip("\n")
        while (following := IMAGE.match(rest)) and following.group(1).endswith(DARK_VARIANT):
            rest = rest[following.end():].lstrip("\n")
        yield m.group(1), rest.split("\n\n", 1)[0]


def _tag_captions(text: str):
    for m in IMG_TAG.finditer(text):
        if m.group(1).endswith(DARK_VARIANT) or m.group(1) in DECORATION:
            continue
        table = text.rfind("<table", 0, m.start())
        if table > text.rfind("</table>", 0, m.start()):
            cell_end = text.find("</td>", m.end())
            sub = re.search(r"<sub>(.*?)</sub>", text[m.end():cell_end], re.S)
            intro = text[:table].rstrip().rsplit("\n\n", 1)[-1]
            yield m.group(1), f"{intro}\n{sub.group(1) if sub else ''}"
        else:
            rest = re.sub(r"^(\s*(</a>|<img [^>]*>))+", "", text[m.end():]).lstrip()
            yield m.group(1), rest.split("\n\n", 1)[0]


def figure_captions(text: str):
    """Each (image path, caption) on a page, for Markdown images and `<img>` tags."""
    yield from _markdown_captions(text)
    yield from _tag_captions(text)


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
    assert len(found) >= 17, f"only {len(found)} figures parsed; the reader has stopped working"
    assert sum(img.startswith("assets/figures/") for img in found) >= 16, found


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


def test_an_img_tag_is_read_in_a_table_and_outside_one(tmp_path):
    page = tmp_path / "p.md"
    page.write_text(
        "Examples:\n\n<table>\n  <tr>\n    <td>\n"
        '      <img src="assets/a.png#only-light">\n      <img src="assets/a.dark.png#only-dark">\n'
        "      <sub>Trace A</sub>\n    </td>\n  </tr>\n</table>\n\n"
        "Synthetic examples:\n\n<table>\n  <tr>\n    <td>\n"
        '      <a href="assets/b.png"><img src="assets/b.png#only-light"></a>\n'
        "      <sub>Trace B</sub>\n    </td>\n  </tr>\n</table>\n\n"
        '<img src="assets/c.png">\n\nPanel C is a trace.\n',
        encoding="utf-8",
    )
    captions = dict(figure_captions(page.read_text(encoding="utf-8")))
    assert captions["assets/b.png#only-light"] == "Synthetic examples:\nTrace B", captions
    assert unlabelled([page], root=tmp_path) == ["p.md: assets/a.png#only-light", "p.md: assets/c.png"]
