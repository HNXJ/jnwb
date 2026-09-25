"""Documentation figures follow rules G1 and G2 of `docs/documentation_form.md`.

G1: no figure encodes its own background colour. Every figure is written with a transparent
background, so each corner pixel is fully transparent.

G2: a figure is legible under both palette schemes. Each figure is drawn twice, a light variant
and a dark variant, and each page shows the variant for its scheme with `#only-light` and
`#only-dark`. A colour written into a generator outside its per-theme table is drawn identically
in both variants, so it must read on both page backgrounds: a contrast ratio of at least 2 against
white and against the slate background. A colour that fails is either moved into the table or
listed below with the reason it is drawn over something other than the page.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = REPO_ROOT / "docs"
GENERATORS = [REPO_ROOT / "docs" / "generate_figures.py", REPO_ROOT / "examples" / "quickstart_jnwb.py"]
FIGURES = sorted((DOCS / "assets" / "figures").glob("*.png")) + sorted(
    (DOCS / "assets").glob("jnwb_quickstart*.png")
)

PAGE_BACKGROUNDS = {"light": "#ffffff", "slate": "#1b1b1b"}
MIN_CONTRAST = 2.0

#: Colours drawn over a figure element rather than over the page, by generator function.
DRAWN_OVER_A_FIGURE = {
    "fig05_complex_tfr": {"white": "the cone-of-influence line over the TFR image",
                          "#2d2d2d": "the legend box behind white legend text"},
}

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
NAMED = {"white": "#ffffff", "black": "#000000", "k": "#000000", "w": "#ffffff"}
IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\((assets/[^)\s]+?)(\.dark)?\.png#only-(light|dark)\)$", re.M)
IMG_TAG = re.compile(r'<img src="(assets/[^"]+?)(\.dark)?\.png#only-(light|dark)"')


def _luminance(hex_colour: str) -> float:
    rgb = np.array([int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]) / 255.0
    lin = np.where(rgb <= 0.03928, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2])


def _contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _illegible_literals(source: str) -> list[str]:
    """Colour literals outside a `THEMES` table that fail contrast on either page background."""
    tree = ast.parse(source)
    in_table = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "THEMES" for t in node.targets):
            in_table.update(id(n) for n in ast.walk(node.value))
    owner = {}
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for n in ast.walk(fn):
            owner.setdefault(id(n), fn.name)
    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)) or id(node) in in_table:
            continue
        value = node.value
        colour = value if HEX.match(value) else NAMED.get(value)
        if colour is None:
            continue
        if value in DRAWN_OVER_A_FIGURE.get(owner.get(id(node)), {}):
            continue
        worst = min(_contrast(colour, bg) for bg in PAGE_BACKGROUNDS.values())
        if worst < MIN_CONTRAST:
            offenders.append(f"line {node.lineno}: {value} (contrast {worst:.2f})")
    return offenders


@pytest.mark.parametrize("png", FIGURES, ids=lambda p: p.name)
def test_no_figure_paints_its_own_background(png):
    import matplotlib.image as mpimg

    image = mpimg.imread(png)
    assert image.ndim == 3 and image.shape[2] == 4, f"{png.name} has no alpha channel"
    corners = image[[0, 0, -1, -1], [0, -1, 0, -1], 3]
    assert np.all(corners == 0), f"{png.name} paints a background: corner alpha {corners}"


@pytest.mark.parametrize("generator", GENERATORS, ids=lambda p: p.name)
def test_every_fixed_colour_reads_on_both_page_backgrounds(generator):
    offenders = _illegible_literals(generator.read_text(encoding="utf-8"))
    assert not offenders, f"{generator.name}: move these into THEMES or explain them: {offenders}"


def test_every_figure_on_a_page_has_both_variants():
    shown = {}
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        for stem, dark, scheme in IMAGE_LINE.findall(text) + IMG_TAG.findall(text):
            assert (scheme == "dark") == bool(dark), f"{page.name}: {stem} variant and scheme disagree"
            shown.setdefault((page.name, stem), set()).add(scheme)
    assert shown, "no themed figure found; the reader has stopped working"
    for (page, stem), schemes in shown.items():
        assert schemes == {"light", "dark"}, f"{page}: {stem} is shown only for {schemes}"
        for suffix in (".png", ".dark.png"):
            assert (DOCS / f"{stem}{suffix}").is_file(), f"{page}: {stem}{suffix} is missing"
    bare = [
        f"{page.name}: {m}"
        for page in sorted(DOCS.rglob("*.md"))
        for m in re.findall(r"[(\"](assets/(?:figures/[^)\s\"]+|jnwb_quickstart[^)\s\"]*)\.png)[)\"]",
                            page.read_text(encoding="utf-8"))
    ]
    assert not bare, f"a figure shown the same under both schemes: {bare}"


def test_the_colour_check_catches_a_hardcoded_foreground():
    assert _illegible_literals('ax.plot(x, color="#000000")\n')
    assert _illegible_literals('ax.set_title("t", color="white")\n')
    assert not _illegible_literals('ax.plot(x, color="#888888")\n')
    assert not _illegible_literals('THEMES = {"dark": {"fg": "#e0e0e0"}}\n')
