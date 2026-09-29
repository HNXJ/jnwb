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
    "fig05_complex_tfr": {"white": "the legend text inside its dark box over the TFR image",
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


def _legend_overlaps(fig) -> list[str]:
    """Data a legend is drawn over: lines, contours, bars, spans, fills, point clouds and texts.

    Any intersection is an overlap, framed legend or not: a box hides the data under it. Each
    axes' own legend (``ax.get_legend()``) is compared with that axes' own artists. The check
    does not see:

    * any ``QuadMesh``, which is skipped wherever it is and whatever it covers (it is meant for
      a time-frequency map that fills the axes; the colour of legend text over it is left to
      `DRAWN_OVER_A_FIGURE`);
    * ``ax.images``, which are never inspected;
    * a scatter of a single point, whose marker path is tested in the wrong coordinates;
    * a marker's extent: a point cloud is tested at its centres, and a line at the path
      joining its points, so a marker whose centre is outside the box but whose edge is inside
      passes;
    * a twin axes: a legend is not compared with the artists of an axes sharing its area;
    * ``fig.legend``, and the arrow of an annotation.
    """
    from matplotlib.collections import QuadMesh

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    hits = []
    for index, ax in enumerate(fig.axes):
        legend = ax.get_legend()
        if legend is None:
            continue
        box = legend.get_window_extent(renderer)
        for line in ax.get_lines():
            if line.get_transform().transform_path(line.get_path()).intersects_bbox(box, filled=False):
                hits.append(f"axes {index}: line {line.get_label()!r}")
        for patch in ax.patches:
            if patch.get_window_extent(renderer).overlaps(box):
                hits.append(f"axes {index}: patch {patch.get_label()!r}")
        for coll in ax.collections:
            if isinstance(coll, QuadMesh):
                continue
            offsets = coll.get_offsets()
            # A line contour is open paths; testing it as filled would close the cone of influence
            # into a polygon and report everything inside it.
            filled = getattr(coll, "filled", True)
            if len(offsets) > 1:
                points = coll.get_offset_transform().transform(offsets)
                if any(box.contains(x, y) for x, y in points):
                    hits.append(f"axes {index}: points {coll.get_label()!r}")
            elif any(coll.get_transform().transform_path(p).intersects_bbox(box, filled=filled)
                     for p in coll.get_paths()):
                hits.append(f"axes {index}: collection {coll.get_label()!r}")
        for text in ax.texts:
            if text.get_window_extent(renderer).overlaps(box):
                hits.append(f"axes {index}: text {text.get_text()!r}")
    return hits


@pytest.fixture(scope="module")
def legend_overlaps():
    """Every figure the generator draws, in both themes, mapped to what its legends cover."""
    import importlib.util

    import matplotlib

    matplotlib.use("Agg")
    found = {}
    with matplotlib.rc_context():
        spec = importlib.util.spec_from_file_location("_figure_generator", GENERATORS[0])
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        generator._save = lambda fig, name: found.__setitem__(
            name.replace(".png", generator.SUFFIX), _legend_overlaps(fig))
        for theme in generator.THEMES:
            generator.apply_theme(theme)
            for draw in generator.FIGURES.values():
                draw()
                generator.plt.close("all")
    return found


def test_no_legend_covers_the_data(legend_overlaps):
    assert len(legend_overlaps) == 20, sorted(legend_overlaps)
    offenders = {name: hits for name, hits in legend_overlaps.items() if hits}
    assert not offenders, f"a legend is drawn over data: {offenders}"


@pytest.fixture(scope="module")
def drawn_figures():
    """fig01, fig04 and fig09 as drawn in the light theme, keyed by file name."""
    import importlib.util

    import matplotlib

    matplotlib.use("Agg")
    found = {}
    with matplotlib.rc_context():
        spec = importlib.util.spec_from_file_location("_figure_generator_drawn", GENERATORS[0])
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        found["generator"] = generator
        generator._save = lambda fig, name: found.__setitem__(name, fig)
        generator.apply_theme("light")
        for name in ("fig01_addressing_laminar.png", "fig04_psd_spectral_tilt.png",
                     "fig09_directed_connectivity.png"):
            generator.FIGURES[name]()
            generator.plt.close("all")
    return found


def _axes_titled(fig, needle):
    matches = [ax for ax in fig.axes if needle in ax.get_title()]
    assert len(matches) == 1, [ax.get_title() for ax in fig.axes]
    return matches[0]


def test_the_depth_class_panel_does_not_call_its_class_a_layer(drawn_figures):
    # `classify_layer_from_depth` returns a geometric depth class; the function's name is the
    # only place the word may appear.
    ax = _axes_titled(drawn_figures["fig01_addressing_laminar.png"], "classify_layer_from_depth")
    words = ax.get_title().replace("classify_layer_from_depth", "").lower()
    assert "layer" not in words and "cortical" not in words, ax.get_title()


def test_the_power_law_line_is_the_fit_of_the_spectrum_under_it(drawn_figures):
    """The fit line is the least-squares power law of the drawn spectrum over the fit's own
    bins, those bins start above the synthetic rhythm (the fit removes no peaks), and the slope
    in its label is that fit's slope."""
    ax = _axes_titled(drawn_figures["fig04_psd_spectral_tilt.png"], "B.")
    lines = {line.get_label().split(":")[0]: line for line in ax.get_lines()}
    psd_f, psd = (np.asarray(v, float) for v in lines["Welch PSD"].get_data())
    fit_f, fit = (np.asarray(v, float) for v in lines["Power-law fit"].get_data())
    assert np.isin(fit_f, psd_f).all(), "the fit is drawn at frequencies the spectrum is not"
    rhythm = drawn_figures["generator"].FIG04_RHYTHM_HZ
    assert fit_f.min() > rhythm, f"the fit starts at {fit_f.min()} Hz, across the {rhythm} Hz peak"
    drawn = psd[np.searchsorted(psd_f, fit_f)]
    slope, intercept = np.polyfit(np.log10(fit_f), np.log10(drawn), 1)
    offset = np.max(np.abs(np.log10(fit) - (intercept + slope * np.log10(fit_f))))
    assert offset < 1e-6, f"the fit line is {offset:.3f} decades from the drawn spectrum's fit"
    printed = float(re.search(r"slope=(-?\d+\.\d+)", lines["Power-law fit"].get_label()).group(1))
    assert printed == pytest.approx(slope, abs=0.005), (printed, slope)


def test_the_psi_axis_carries_no_phase_slope_unit(drawn_figures):
    # PSI is dimensionless (the result declares unit='psi'); rad/Hz reads it as dphi/df, the
    # step to a delay.
    ax = _axes_titled(drawn_figures["fig09_directed_connectivity.png"], "phase_slope_index")
    label = ax.get_ylabel()
    assert "rad" not in label and "Hz" not in label, label


def test_the_overlap_check_catches_a_legend_over_a_bar():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, (over, clear) = plt.subplots(1, 2)
    over.bar([1, 2, 3], [100, 100, 100])
    over.axhline(50, label="baseline")
    over.set_ylim(0, 105)
    over.legend(frameon=False, loc="upper right")
    clear.bar([1, 2, 3], [100, 100, 100])
    clear.axhline(50, label="baseline")
    clear.set_ylim(0, 150)
    clear.legend(frameon=False, loc="upper right")
    hits = _legend_overlaps(fig)
    plt.close(fig)
    assert hits and all(h.startswith("axes 0") for h in hits), hits


def test_the_overlap_check_catches_a_framed_legend_over_a_contour_but_not_over_a_mesh():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x, y = np.meshgrid(np.linspace(0, 1, 40), np.linspace(0, 1, 40))
    fig, (over, clear) = plt.subplots(1, 2)
    for ax in (over, clear):
        ax.pcolormesh(x, y, x * y, shading="auto")
        # A U-shaped line contour whose arms reach the top corners.
        ax.contour(x, y, (x - 0.5) ** 2 * 4 - y, levels=[0.0], linestyles="--")
        ax.plot([], [], ls="--", label="boundary")
    over.legend(frameon=True, loc="upper left")
    clear.legend(frameon=True, loc="upper center")
    hits = _legend_overlaps(fig)
    plt.close(fig)
    assert hits and all(h.startswith("axes 0: collection") for h in hits), hits


def test_the_colour_check_catches_a_hardcoded_foreground():
    assert _illegible_literals('ax.plot(x, color="#000000")\n')
    assert _illegible_literals('ax.set_title("t", color="white")\n')
    assert not _illegible_literals('ax.plot(x, color="#888888")\n')
    assert not _illegible_literals('THEMES = {"dark": {"fg": "#e0e0e0"}}\n')
