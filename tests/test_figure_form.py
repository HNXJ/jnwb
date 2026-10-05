"""Documentation figures are legible, placed, labelled and computed.

G1 and G2 of `docs/documentation_form.md`: no figure paints its own background (each corner pixel
is transparent), and each figure is drawn twice, a light and a dark variant, shown on its page
with `#only-light` and `#only-dark`. The page-side half of G2 (every shown figure is a pair, and
every fixed colour a generator writes reads on both page backgrounds) is read once, by
`scripts/docs_form_gate.py`; this module reads the pixels and the drawn figures.

Every figure the documentation generators draw (`docs/generate_figures.py` and
`examples/quickstart_jnwb.py`) is drawn here in both themes and inspected as drawn:

| Check | Holds when |
|---|---|
| theme contrast | each colour in a generator's `THEMES` reaches 4.5 (text) or 3 (marks) on that theme's page |
| ink contrast | under 5 % of the painted pixels sit below 1.5 against the page, colour-mapped meshes aside |
| legends | no legend box meets data, text or an arrow on any axes, nor a figure legend |
| text placement | no text meets another text, or data in the axes; every text lies inside the canvas |
| shared x | axes that share x span the same pixels |
| axis labels | every numeric axis has a label; a physical quantity names a unit in parentheses |
| declared unit | an axis plotting a result that declares `unit` names that unit |
| displayed size | the smallest text renders at 9 px or more at the width the page displays it |
| signed zero | no drawn number reads as a negative zero |
| style source | fonts, font sizes and figure width come from `docs/figure_style.py` |
| colormaps | every `cmap=` is perceptually uniform or a declared diverging map |
| computed values | every figure calls a public `jnwb` function; no reference line sits at a bare literal |
| captions | every `jnwb.<name>` in a title is public and named in the figure's caption |
| fits | a fit drawn over a log-log spectrum sits on the spectrum's grid, centred on it |
| palette | every colour drawn is a series colour, the highlight, the neutral or the theme's ink, and no generator types one |
| colour vision | the series and highlight colours drawn stay apart under deutan, protan and tritan simulation |
| type | every text is set in Liberation Sans and measures 8 to 11 pt |
| spines | no axes draws a top or right spine |
| panel letters | each panel of a multi-panel figure carries one bold letter, outside its title |
| line widths | every data line is 1.2 to 1.8 pt, taken from the style module |
| minus sign | no drawn text puts an ASCII hyphen where a minus belongs |
| variables | a legend entry for a named variable has that variable's colour, in every figure |

The three generators are `docs/generate_figures.py`, `examples/quickstart_jnwb.py` and
`examples/tutorials/09_open_data.py`, the last drawn from a synthetic result. Each check is
first shown to reject a figure built to break it.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from scripts import docs_form_gate as gate  # noqa: E402
from scripts.docs_form_gate import PAGE  # noqa: E402
from scripts.docs_form_gate import contrast as _contrast  # noqa: E402
from scripts.docs_form_gate import hex_colour as _hex  # noqa: E402
from scripts.docs_form_gate import illegible_literals as _illegible_literals  # noqa: E402
from scripts.docs_form_gate import luminance as _luminance  # noqa: E402
from scripts.docs_form_gate import themes_node as _themes_node  # noqa: E402
from tests.test_synthetic_figures_are_labelled import figure_captions  # noqa: E402

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
import matplotlib.colors as mcolors  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PathCollection, QuadMesh  # noqa: E402
from matplotlib.image import AxesImage  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.text import Text  # noqa: E402
from matplotlib.transforms import Bbox  # noqa: E402

import jnwb  # noqa: E402

DOCS = REPO_ROOT / "docs"
STYLE_MODULE = DOCS / "figure_style.py"
#: Every source the gate reads for a figure colour: the generators and the style module.
GATED = [REPO_ROOT / g for g in gate.GENERATORS]
assert STYLE_MODULE in GATED, "the gate does not read the style module"
GENERATORS = [g for g in GATED if g != STYLE_MODULE]
DOC_GENERATOR, QUICKSTART = GENERATORS
TUTORIAL = REPO_ROOT / "examples" / "tutorials" / "09_open_data.py"
#: Every file that draws a figure for the documentation or its examples.
SOURCES = [*GENERATORS, TUTORIAL]
_style_spec = importlib.util.spec_from_file_location("_figure_style", STYLE_MODULE)
STYLE = importlib.util.module_from_spec(_style_spec)
_style_spec.loader.exec_module(STYLE)
FIGURES = sorted((DOCS / "assets" / "figures").glob("*.png")) + sorted(
    (DOCS / "assets").glob("jnwb_quickstart*.png")
)

MIN_TEXT_CONTRAST = 4.5
MIN_MARK_CONTRAST = 3.0
DIM_INK = 1.5
MAX_DIM_INK_SHARE = 0.05

#: What each `THEMES` key colours. A key missing here fails, so a new colour is classified.
THEME_ROLES = {
    "fg": "text", "edge": "mark", "faint": "mark",
    "FG": "text", "FG2": "text", "FG3": "text", "FAINT": "mark",
    "highlight": "fill",
}
#: The bar each role clears against its own page: text, a mark, and a fill drawn as a window or band.
ROLE_CONTRAST = {"text": MIN_TEXT_CONTRAST, "mark": MIN_MARK_CONTRAST,
                 "fill": gate.MIN_FIXED_CONTRAST}
NOT_A_COLOUR = {"suffix", "stem", "formats"}

#: Widths, in CSS px, at which the built site displays a figure: a topic page at a 1440 px
#: viewport, and a cell of the two-column gallery on the landing page. A gallery image that
#: links to its full-size file is read at the full size.
PAGE_WIDTH_PX = 688
GALLERY_WIDTH_PX = 311
#: The content column of a 375 px phone with 16 px gutters. A figure shown wider is scaled down to it.
MOBILE_WIDTH_PX = 343
MIN_TEXT_PX = 9.0

PERCEPTUAL = {"viridis", "plasma", "inferno", "magma", "cividis"}
DIVERGING = {"RdBu", "RdBu_r", "PuOr", "PuOr_r", "BrBG", "BrBG_r"}
#: Reference positions that are theory, not data: zero.
THEORETICAL = {0}
#: Words that make an axis a physical quantity, and words that make it a count or a ratio.
PHYSICAL = re.compile(r"\b(time|frequency|rate|power|depth|lfp|psd|spectral density|amplitude|"
                      r"latency|delay|difference|voltage|distance)\b", re.I)
DIMENSIONLESS = re.compile(r"\b(ratio|index|count|fraction|score|accuracy|fold|probability)\b", re.I)
UNIT_TOKENS = {"s", "ms", "µs", "min", "Hz", "kHz", "m", "mm", "µm", "cm", "V", "mV", "µV", "dB",
               "%", "a.u.", "rad", "deg", "°", "bits", "dimensionless", "1"}
MAX_FIT_OFFSET_DECADES = 0.05
#: The rcParams a tick label's text is formatted under, each read when the figure is drawn.
TICK_TEXT_RC = ("axes.unicode_minus", "axes.formatter.use_mathtext", "axes.formatter.limits",
                "axes.formatter.useoffset", "axes.formatter.offset_threshold",
                "axes.formatter.min_exponent", "axes.formatter.use_locale", "text.usetex")


# ---------------------------------------------------------------------------------------------
# Colour


def _theme_contrast_failures(source: str) -> list[str]:
    """Each `THEMES[theme]` colour against that theme's page, at the bar for its role."""
    table = _themes_node(ast.parse(source))
    assert table is not None, "the generator defines no THEMES table"
    themes = ast.literal_eval(table)
    failures = []
    for theme, colours in themes.items():
        for key, value in colours.items():
            if key in NOT_A_COLOUR:
                continue
            role = THEME_ROLES.get(key)
            if role is None:
                failures.append(f"{theme}.{key}: no role declared in THEME_ROLES")
                continue
            colour = _hex(value, in_colour_argument=True)
            if colour is None:
                failures.append(f"{theme}.{key}: {value!r} is not a colour")
                continue
            need = ROLE_CONTRAST[role]
            ratio = _contrast(colour, PAGE[theme])
            if ratio < need:
                failures.append(f"{theme}.{key} {value} ({role}): {ratio:.2f} < {need}")
    return failures


def _dim_ink_share(rgba: np.ndarray, background: str, exempt: list[Bbox] = ()) -> float:
    """Share of painted pixels whose colour, composited on the page, is below `DIM_INK` against
    it. `rgba` is a uint8 canvas buffer, top row first; `exempt` boxes are in display pixels."""
    image = rgba.astype(float) / 255.0
    alpha = image[..., 3]
    # Half opacity and above: the anti-aliased fringe of every stroke and glyph is left out,
    # and so is a band drawn below half opacity.
    painted = alpha >= 0.5
    height = image.shape[0]
    for box in exempt:
        x0, x1 = int(np.floor(box.x0)), int(np.ceil(box.x1))
        r0, r1 = int(np.floor(height - box.y1)), int(np.ceil(height - box.y0))
        painted[max(r0, 0):max(r1, 0), max(x0, 0):max(x1, 0)] = False
    if not painted.any():
        return 0.0
    bg = np.array(mcolors.to_rgb(background))
    rgb = image[..., :3] * alpha[..., None] + bg * (1.0 - alpha[..., None])
    lin = np.where(rgb <= 0.03928, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    lum = lin @ np.array([0.2126, 0.7152, 0.0722])
    lb = _luminance(background)
    ratio = (np.maximum(lum, lb) + 0.05) / (np.minimum(lum, lb) + 0.05)
    return float(np.mean(ratio[painted] < DIM_INK))


# ---------------------------------------------------------------------------------------------
# Geometry: what is drawn where


@dataclass
class Mark:
    """One drawn thing in display pixels: a path (filled or not), a box, or marker centres."""
    what: str
    owner: object
    path: object = None
    filled: bool = False
    box: Bbox | None = None
    points: np.ndarray | None = None
    radius: float = 0.0

    def meets(self, box: Bbox) -> bool:
        if self.box is not None:
            return _area(self.box, box) > 0
        if self.points is not None:
            grown = box.padded(self.radius)
            return any(grown.contains(x, y) for x, y in self.points)
        return bool(self.path.intersects_bbox(box, filled=self.filled))


def _area(a: Bbox, b: Bbox) -> float:
    w = min(a.x1, b.x1) - max(a.x0, b.x0)
    h = min(a.y1, b.y1) - max(a.y0, b.y0)
    return max(w, 0.0) * max(h, 0.0)


def _marks(fig, renderer) -> list[Mark]:
    """Every data artist of every axes, and every annotation arrow, in display pixels."""
    marks = []
    px = fig.dpi / 72.0
    for index, ax in enumerate(fig.axes):
        clip = ax.get_window_extent(renderer)
        for line in ax.get_lines():
            if not line.get_visible():
                continue
            xy = line.get_transform().transform(np.column_stack(line.get_data()).astype(float))
            xy = xy[np.isfinite(xy).all(axis=1)]
            if line.get_linestyle() not in ("None", "none", "", " ") and len(xy) > 1:
                path = line.get_transform().transform_path(line.get_path())
                marks.append(Mark(f"axes {index}: line {line.get_label()!r}", line, path=path))
            if line.get_marker() not in (None, "None", "none", "", " ") and len(xy):
                marks.append(Mark(f"axes {index}: markers {line.get_label()!r}", line, points=xy,
                                  radius=line.get_markersize() / 2.0 * px))
        for patch in ax.patches:
            if patch.get_visible():
                path = patch.get_transform().transform_path(patch.get_path())
                marks.append(Mark(f"axes {index}: patch {patch.get_label()!r}", patch, path=path,
                                  filled=True))
        for coll in ax.collections:
            if not coll.get_visible():
                continue
            label = f"{coll.get_label()!r}"
            if isinstance(coll, QuadMesh):
                box = Bbox.intersection(coll.get_window_extent(renderer), clip)
                if box is not None:
                    marks.append(Mark(f"axes {index}: mesh {label}", coll, box=box))
            elif isinstance(coll, PathCollection):
                points = coll.get_offset_transform().transform(np.asarray(coll.get_offsets(), float))
                sizes = coll.get_sizes()
                radius = float(np.sqrt(sizes.max()) / 2.0 * px) if len(sizes) else 0.0
                marks.append(Mark(f"axes {index}: points {label}", coll, points=points, radius=radius))
            else:
                # A line contour is open paths; testing it as filled would close the cone of
                # influence into a polygon and report everything inside it.
                filled = bool(getattr(coll, "filled", coll.get_facecolor().size and
                                      np.any(coll.get_facecolor()[:, 3] > 0)))
                for p in coll.get_paths():
                    marks.append(Mark(f"axes {index}: collection {label}", coll,
                                      path=coll.get_transform().transform_path(p), filled=filled))
        for image in ax.images:
            if isinstance(image, AxesImage) and image.get_visible():
                box = Bbox.intersection(image.get_window_extent(renderer), clip)
                if box is not None:
                    marks.append(Mark(f"axes {index}: image", image, box=box))
    for text in [t for ax in fig.axes for t in ax.texts] + list(fig.texts):
        arrow = getattr(text, "arrow_patch", None)
        if arrow is not None and arrow.get_visible():
            marks.append(Mark(f"arrow of {text.get_text()!r}", text,
                              path=arrow.get_transform().transform_path(arrow.get_path())))
    return marks


def _annotations(fig) -> list[Text]:
    """Texts placed among the data: `ax.text`, `ax.annotate` and `fig.text`."""
    placed = [t for ax in fig.axes for t in ax.texts] + list(fig.texts)
    return [t for t in placed if t.get_visible() and t.get_text().strip()]


def _legends(fig):
    return [ax.get_legend() for ax in fig.axes if ax.get_legend() is not None] + list(fig.legends)


def _tick_label_ids(fig):
    ids = set()
    for ax in fig.axes:
        for axis in (ax.xaxis, ax.yaxis):
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                ids.update((id(tick.label1), id(tick.label2)))
    return ids


def _drawn_texts(fig) -> list[Text]:
    """Every visible, non-empty text the canvas draws, legend texts included."""
    ticks = _tick_label_ids(fig)
    texts = [t for t in fig.findobj(Text) if id(t) not in ticks and t.get_visible()
             and t.get_text().strip()]
    for ax in fig.axes:
        for axis, coord in ((ax.xaxis, 0), (ax.yaxis, 1)):
            lo, hi = sorted(axis.get_view_interval())
            slack = 1e-9 * max(abs(lo), abs(hi), 1.0)
            for minor in (False, True):
                for label in axis.get_ticklabels(minor=minor):
                    at = label.get_position()[coord]
                    if (label.get_visible() and label.get_text().strip()
                            and lo - slack <= at <= hi + slack):
                        texts.append(label)
    return texts


def _renderer(fig):
    """Draw the figure and return its renderer. A figure closed through pyplot can be left with
    a bare canvas (Matplotlib 3.11 leaves one), so an Agg canvas is attached first."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    if not hasattr(fig.canvas, "get_renderer"):
        FigureCanvasAgg(fig)
    fig.canvas.draw()
    return fig.canvas.get_renderer()


def _legend_overlaps(fig) -> list[str]:
    """Data, texts and arrows any legend is drawn over, on any axes of the figure.

    Any intersection is an overlap, framed legend or not: a box hides what is under it. Each
    legend, of an axes or of the figure, is compared with the artists of every axes, so a twin
    axes' data counts; meshes and images count by their drawn extent, point clouds and markers
    by their size, lines by their path, and an annotation by its text and its arrow."""
    renderer = _renderer(fig)
    marks = _marks(fig, renderer)
    texts = _annotations(fig)
    hits = []
    for legend in _legends(fig):
        box = legend.get_window_extent(renderer)
        own = set(map(id, legend.get_children()))
        hits += [m.what for m in marks if id(m.owner) not in own and m.meets(box)]
        hits += [f"text {t.get_text()!r}" for t in texts
                 if _area(t.get_window_extent(renderer), box) > 0]
    return hits


def _text_collisions(fig) -> list[str]:
    """Texts that meet each other, texts among the data that meet it, and texts off the canvas."""
    renderer = _renderer(fig)
    canvas = fig.bbox.padded(1.0)
    legend_texts = {id(t) for lg in _legends(fig) for t in lg.get_texts() + [lg.get_title()]}
    texts = _drawn_texts(fig)
    boxes = [(t, t.get_window_extent(renderer)) for t in texts]
    hits = []
    for t, box in boxes:
        if not (canvas.x0 <= box.x0 and box.x1 <= canvas.x1 and canvas.y0 <= box.y0 and box.y1 <= canvas.y1):
            hits.append(f"text {t.get_text()!r} leaves the canvas")
    free = [(t, b) for t, b in boxes if id(t) not in legend_texts]
    for i, (a, box_a) in enumerate(free):
        for b, box_b in free[i + 1:]:
            if _area(box_a, box_b) > 1.0:
                hits.append(f"text {a.get_text()!r} meets text {b.get_text()!r}")
    marks = _marks(fig, renderer)
    for t in _annotations(fig):
        box = t.get_window_extent(renderer)
        hits += [f"text {t.get_text()!r} meets {m.what}" for m in marks if m.owner is not t and m.meets(box)]
    return hits


def _shared_x_misalignment(fig, tolerance_px: float = 1.0) -> list[str]:
    width = fig.get_figwidth() * fig.dpi
    hits = []
    for i, ax in enumerate(fig.axes):
        for other in ax.get_shared_x_axes().get_siblings(ax):
            j = fig.axes.index(other) if other in fig.axes else -1
            if j <= i:
                continue
            a, b = ax.get_position(), other.get_position()
            shift = max(abs(a.x0 - b.x0), abs(a.x1 - b.x1)) * width
            if shift > tolerance_px:
                hits.append(f"axes {i} and {j} share x but differ by {shift:.0f} px")
    return hits


# ---------------------------------------------------------------------------------------------
# Labels and units


def _is_numeric(label: str) -> bool:
    text = label.replace("−", "-").strip()
    if text.startswith("$") and text.endswith("$"):
        return bool(re.search(r"\d", text)) and not re.search(r"\\(?!mathdefault|times)[A-Za-z]+", text)
    try:
        float(text.replace(",", ""))
    except ValueError:
        return False
    return True


def _names_a_unit(label: str) -> bool:
    groups = re.findall(r"\(([^()]*)\)\s*$", label.strip())
    if not groups:
        return False
    tokens = [t for t in re.split(r"[\s/·*×]+", groups[-1]) if t]
    cleaned = [re.sub(r"(\^-?\d+|[²³⁻¹])+$", "", t) for t in tokens]
    return bool(cleaned) and all(t in UNIT_TOKENS for t in cleaned)


def _axis_label_failures(fig) -> list[str]:
    """A numeric axis with tick labels drawn has a label; a physical quantity names its unit."""
    _renderer(fig)
    drawn = {id(t) for t in _drawn_texts(fig)}
    hits = []
    for index, ax in enumerate(fig.axes):
        if not ax.get_visible():
            continue
        for axis, name in ((ax.xaxis, "x"), (ax.yaxis, "y")):
            labels = [t.get_text() for minor in (False, True) for t in axis.get_ticklabels(minor=minor)
                      if id(t) in drawn]
            if not labels or not all(_is_numeric(t) for t in labels):
                continue
            text = axis.get_label().get_text().strip() if axis.get_label().get_visible() else ""
            if not text:
                hits.append(f"axes {index}: the {name} axis has no label")
            elif PHYSICAL.search(text) and not DIMENSIONLESS.search(text) and not _names_a_unit(text):
                hits.append(f"axes {index}: {text!r} names no unit")
    return hits


def _values(result) -> list[np.ndarray]:
    """The numbers a result object carries: one array of its scalars, and each array it holds."""
    fields = dict(vars(result)) if hasattr(result, "__dict__") else {}
    for name in getattr(result, "__dataclass_fields__", {}):
        fields[name] = getattr(result, name)
    scalars, arrays = [], []
    for value in list(fields.values()) + [v for d in fields.values() if isinstance(d, dict) for v in d.values()]:
        if isinstance(value, (int, float, np.floating)) and not isinstance(value, bool):
            scalars.append(float(value))
        elif isinstance(value, np.ndarray) and value.dtype.kind == "f":
            arrays.append(value.ravel())
    return [np.asarray(scalars)] + arrays


def _y_in_data(line, ax) -> bool:
    """Whether a line's y values are data values. `axvline` draws y from 0 to 1 in axes
    fractions, which match any result that happens to carry a 0 and a 1."""
    transform = line.get_transform()
    split = getattr(transform, "contains_branch_separately", None) or transform.contains_branch_seperately
    return bool(split(ax.transData)[1])


def _declared_unit_failures(fig, results) -> list[str]:
    """An axes whose line or bars are drawn from a result declaring `unit` names that unit."""
    declared = [r for r in results if isinstance(getattr(r, "unit", None), str)]
    hits = []
    for index, ax in enumerate(fig.axes):
        drawn = [np.asarray(line.get_ydata(), float) for line in ax.get_lines() if _y_in_data(line, ax)]
        drawn = [y for y in drawn if y.size > 1 and np.ptp(y) > 0]
        bars = np.asarray([p.get_height() for p in ax.patches if isinstance(p, Rectangle)], float)
        if bars.size:
            drawn.append(bars)
        for r in declared:
            if any(np.isin(y, arr).all() for y in drawn for arr in _values(r) if arr.size):
                if r.unit.lower() not in ax.get_ylabel().lower():
                    hits.append(f"axes {index}: {ax.get_ylabel()!r} does not name the unit {r.unit!r}")
    return hits


def _smallest_text_pt(fig) -> float:
    _renderer(fig)
    return min(t.get_fontsize() for t in _drawn_texts(fig))


def _displayed_px(points: float, figure_width_in: float, displayed_width_px: float) -> float:
    """Rendered height of a `points` font when a figure `figure_width_in` wide is shown at
    `displayed_width_px`. The dpi cancels: pt * dpi/72 * displayed / (width * dpi)."""
    return points * displayed_width_px / (72.0 * figure_width_in)


def _mobile_width_px(desktop_width_px: float) -> float:
    """The width a figure shown at `desktop_width_px` has on a phone: no wider than its column."""
    return min(desktop_width_px, MOBILE_WIDTH_PX)


def _fit_offsets(fig) -> list[str]:
    """A line labelled as a fit, drawn on log-log axes over a spectrum, sits on the spectrum's
    frequencies, and the spectrum's median log residual against it is near zero."""
    hits = []
    for index, ax in enumerate(fig.axes):
        if ax.get_xscale() != "log" or ax.get_yscale() != "log":
            continue
        lines = ax.get_lines()
        fits = [ln for ln in lines if "fit" in ln.get_label().lower()]
        data = [ln for ln in lines if ln not in fits and len(ln.get_xdata()) >= 10]
        for fit in fits:
            fx, fy = (np.asarray(v, float) for v in fit.get_data())
            for spectrum in data:
                dx, dy = (np.asarray(v, float) for v in spectrum.get_data())
                if not np.isin(fx, dx).all():
                    hits.append(f"axes {index}: {fit.get_label()!r} is drawn off the spectrum's grid")
                    continue
                offset = float(np.median(np.log10(dy[np.searchsorted(dx, fx)] / fy)))
                if abs(offset) > MAX_FIT_OFFSET_DECADES:
                    hits.append(f"axes {index}: the spectrum sits {offset:+.3f} decades from the fit")
    return hits


def _caption_failures(fig, caption: str) -> list[str]:
    titles = [ax.get_title(loc=loc) for ax in fig.axes for loc in ("left", "center", "right")]
    titles.append(fig.get_suptitle())
    hits = []
    for name in sorted({n for t in titles for n in re.findall(r"\bjnwb\.([A-Za-z_]\w*)", t)}):
        if name not in jnwb.__all__:
            hits.append(f"jnwb.{name} is not in jnwb.__all__")
        if not re.search(rf"\b{re.escape(name)}\b", caption):
            hits.append(f"the caption does not name {name}")
    return hits


# ---------------------------------------------------------------------------------------------
# Source rules


def _style_aliases(tree):
    modules, names = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[-1] == STYLE_MODULE.stem:
                    modules.add(a.asname or a.name)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[-1] == STYLE_MODULE.stem:
            names.update(a.asname or a.name for a in node.names)
    return modules, names


def _from_style(node, modules, names) -> bool:
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):
        base = node
        while isinstance(base, ast.Attribute):
            base = base.value
        return isinstance(base, ast.Name) and (base.id in modules or base.id in names)
    if isinstance(node, ast.Subscript):
        return _from_style(node.value, modules, names)
    return False


STYLE_KEYS = {"font.family", "font.serif", "font.sans-serif", "font.size", "axes.titlesize",
              "axes.labelsize", "xtick.labelsize", "ytick.labelsize", "legend.fontsize",
              "figure.titlesize"}


def _style_violations(source: str) -> list[str]:
    """Font family, font sizes and figure width taken from anywhere but the style module."""
    tree = ast.parse(source)
    modules, names = _style_aliases(tree)
    hits = [] if modules or names else [f"imports nothing from {STYLE_MODULE.name}"]
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value in STYLE_KEYS:
            hits.append(f"line {node.lineno}: sets {node.value}")
        if isinstance(node, ast.keyword) and node.arg == "fontsize" and not _from_style(node.value, modules, names):
            hits.append(f"line {node.value.lineno}: fontsize={ast.unparse(node.value)}")
        if isinstance(node, ast.keyword) and node.arg == "figsize":
            width = node.value.elts[0] if isinstance(node.value, ast.Tuple) else node.value
            if not _from_style(width, modules, names):
                hits.append(f"line {node.value.lineno}: figsize width {ast.unparse(width)}")
    return hits


def _colormap_violations(source: str) -> list[str]:
    tree = ast.parse(source)
    modules, names = _style_aliases(tree)
    hits = []
    for node in ast.walk(tree):
        values = []
        if isinstance(node, ast.keyword) and node.arg == "cmap":
            values.append(node.value)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) == "get_cmap":
            values += node.args[:1]
        for v in values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                if v.value not in PERCEPTUAL | DIVERGING:
                    hits.append(f"line {v.lineno}: cmap {v.value!r}")
            elif not _from_style(v, modules, names):
                hits.append(f"line {v.lineno}: cmap {ast.unparse(v)} cannot be checked")
    return hits


#: Reference-drawing calls and the arguments that are positions in data coordinates.
REFERENCE_CALLS = {"axhline": (1, {"y"}), "axvline": (1, {"x"}),
                   "axhspan": (2, {"ymin", "ymax"}), "axvspan": (2, {"xmin", "xmax"}),
                   "hlines": (1, {"y"}), "vlines": (1, {"x"})}


def _literal(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _literal(node.operand)
        return None if inner is None else -inner
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    return None


def _literal_references(source: str) -> list[str]:
    """Reference lines and spans drawn at a number typed into the call, zero aside."""
    tree = ast.parse(source)
    owner = {}
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for n in ast.walk(fn):
            owner.setdefault(id(n), fn.name)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in REFERENCE_CALLS):
            continue
        n_positional, keywords = REFERENCE_CALLS[node.func.attr]
        for arg in node.args[:n_positional] + [k.value for k in node.keywords if k.arg in keywords]:
            value = _literal(arg)
            if value is not None and value not in THEORETICAL:
                hits.append(f"{owner.get(id(node), '<module>')} line {node.lineno}: "
                            f"{node.func.attr} at the literal {value}")
    return hits


# ---------------------------------------------------------------------------------------------
# Drawing every figure


class _Recorder:
    """Stands in for the `jnwb` module inside a generator and logs each call and its result."""

    def __init__(self, module):
        self._module = module
        self.log: list | None = None

    def __getattr__(self, name):
        attr = getattr(self._module, name)
        if not callable(attr) or isinstance(attr, type(self._module)):
            return attr

        def call(*args, **kwargs):
            out = attr(*args, **kwargs)
            if self.log is not None:
                self.log.append((name, out))
            return out

        return call


@dataclass
class Drawn:
    fig: object
    calls: dict[str, list] = field(default_factory=dict)
    rgba: np.ndarray | None = None
    exempt: list = field(default_factory=list)
    #: The rcParams that decide the text of a tick label, as they stood when it was drawn. A
    #: figure drawn again outside the generator's context formats its ticks under the defaults.
    rc: dict = field(default_factory=dict)

    @property
    def results(self):
        return [out for log in self.calls.values() for _, out in log]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_registered(path: Path, name: str):
    """`_load` for a module that defines dataclasses, which look their module up by name."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _finish(drawn: Drawn) -> Drawn:
    """Draw now, under the rcParams the generator set, and keep the pixels and mesh extents."""
    fig = drawn.fig
    renderer = _renderer(fig)
    drawn.rc = {key: matplotlib.rcParams[key] for key in TICK_TEXT_RC}
    drawn.rgba =np.asarray(fig.canvas.buffer_rgba()).copy()
    drawn.exempt = [c.get_window_extent(renderer) for ax in fig.axes for c in ax.collections
                    if isinstance(c, QuadMesh)] + [im.get_window_extent(renderer)
                                                  for ax in fig.axes for im in ax.images]
    return drawn


def _draw_doc_figures() -> tuple[object, dict[str, Drawn]]:
    found = {}
    with matplotlib.rc_context():
        matplotlib.rcdefaults()
        generator = _load(DOC_GENERATOR, "_figure_generator")
        recorder = _Recorder(jnwb)
        generator.jnwb = recorder
        pending = {}
        generator._save = lambda fig, name: pending.__setitem__("fig", (fig, name))
        for theme in generator.THEMES:
            generator.apply_theme(theme)
            for key, draw in generator.FIGURES.items():
                log = []
                recorder.log = log
                draw()
                fig, name = pending.pop("fig")
                found[name.replace(".png", generator.SUFFIX)] = _finish(Drawn(fig, {draw.__name__: log}))
                plt.close("all")
        recorder.log = None
    return generator, found


def _draw_quickstart(out_dir: Path) -> dict[str, Drawn]:
    from matplotlib.figure import Figure

    found = {}
    save = Figure.savefig
    try:
        with matplotlib.rc_context():
            matplotlib.rcdefaults()
            quickstart = _load(QUICKSTART, "_quickstart_generator")
            quickstart.OUT = str(out_dir)
            recorder = _Recorder(jnwb)
            quickstart.jnwb = recorder
            calls: dict[str, list] = {}

            def wrap(fn):
                def panel(ax):
                    calls[fn.__name__] = recorder.log = []
                    try:
                        return fn(ax)
                    finally:
                        recorder.log = None
                panel.__name__ = fn.__name__
                return panel

            quickstart.PANELS = [(title, api, wrap(fn)) for title, api, fn in quickstart.PANELS]

            def capture(fig, path, *args, **kwargs):
                name = Path(str(path)).stem + ".png"
                if name not in found:
                    found[name] = _finish(Drawn(fig, dict(calls)))
                    calls.clear()

            Figure.savefig = capture
            quickstart.main()
    finally:
        Figure.savefig = save
        plt.close("all")
    return found


def _tutorial_result() -> dict:
    """A synthetic result of the shape the tutorial's `analyze` returns: four layers of a PSTH
    and band power at five contacts, one of them below zero."""
    t_ms = np.arange(-250.0, 750.0, 10.0)
    onset = np.where(t_ms > 0, 1.0 - np.exp(-t_ms / 80.0), 0.0)
    layers = {f"VISpm layer {i}": {"n_units": 6 + i, "rate_hz": 5.0 + (3.0 + 2.0 * i) * onset}
              for i in range(4)}
    return {"psth": {"t_ms": t_ms, "layers": layers},
            "lfp": {"db": np.array([1.2, 0.6, -0.4, 0.3, 0.8]),
                    "depth_um": np.array([50.0, 150.0, 250.0, 350.0, 450.0]),
                    "location": ["VISpm", "VISpm", "VISpm", "CA1", "CA1"]}}


def _draw_tutorial() -> dict[str, Drawn]:
    found = {}
    with matplotlib.rc_context():
        matplotlib.rcdefaults()
        tutorial = _load_registered(TUTORIAL, "_tutorial_09")
        for theme, ink in tutorial.THEMES.items():
            found[f"{ink['stem']}.png"] = _finish(Drawn(tutorial.draw(_tutorial_result(), theme)))
            plt.close("all")
    return found


@pytest.fixture(scope="module")
def drawn(tmp_path_factory):
    generator, found = _draw_doc_figures()
    found.update(_draw_quickstart(tmp_path_factory.mktemp("quickstart")))
    found.update(_draw_tutorial())
    found["generator"] = generator
    return found


def _registry():
    tree = ast.parse(DOC_GENERATOR.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "FIGURES" for t in node.targets):
            return sorted(k.value for k in node.value.keys)
    raise AssertionError("docs/generate_figures.py defines no FIGURES registry")


NAMES = [n for key in _registry() for n in (key, key.replace(".png", ".dark.png"))] + [
    "jnwb_quickstart.png", "jnwb_quickstart.dark.png"]
#: The tutorial's figure, drawn from a synthetic result. It is on no page, so the checks that
#: judge a figure as a page shows it do not read it; the style checks do.
TUTORIAL_NAMES = ["09_open_data.png", "09_open_data.dark.png"]
STYLE_NAMES = NAMES + TUTORIAL_NAMES

#: Figures that still fail a check, by check and figure, with what is wrong. A listed figure that
#: starts to pass fails the suite, so the entry is removed with the repair.
AWAITING: dict[tuple[str, str], str] = {}

#: Every embed fails the mobile-width check for one reason: the shared style sets the smallest
#: text at 8 pt in a 7.2 in figure, and a figure scaled to 343 px renders it at 5.3 px. The ruled
#: text range tops out at 11 pt, which renders at 7.3 px there, so the range cannot reach 9 px
#: at that width: the figure width would have to fall below 5.8 in. The embeds are listed one
#: by one so that a new embed is judged and not waved through.
_MOBILE_TEXT_TOO_SMALL = (
    f"smallest text renders at {_displayed_px(STYLE.SMALL, STYLE.WIDTH, MOBILE_WIDTH_PX):.1f} px "
    f"at {MOBILE_WIDTH_PX} px ({STYLE.SMALL:.0f} pt, {STYLE.WIDTH:.1f} in figure); the largest "
    f"ruled size, {STYLE.TEXT_RANGE_PT[1]:.0f} pt, renders at "
    f"{_displayed_px(STYLE.TEXT_RANGE_PT[1], STYLE.WIDTH, MOBILE_WIDTH_PX):.1f} px")
AWAITING.update({("displayed size at the mobile width", embed): _MOBILE_TEXT_TOO_SMALL for embed in (
    "02_paths_addressing_metadata.md:fig01_addressing_laminar.png",
    "04_spectral_analysis_and_tfr.md:fig04_psd_spectral_tilt.png",
    "04_spectral_analysis_and_tfr.md:fig06_aggregate_to_db.png",
    "05_artifact_detection_and_repair.md:fig10_artifact_repair.png",
    "06_spikes_psth_and_onset_dynamics.md:fig02_raster_psth.png",
    "06_spikes_psth_and_onset_dynamics.md:fig03_onset_fitting.png",
    "07_statistical_inference_and_nulls.md:fig08_permutation_null.png",
    "08_directed_connectivity_and_information.md:fig09_directed_connectivity.png",
    "09_decoding_and_visual_qc.md:fig07_population_decoding.png",
    "coherence_and_tfr.md:fig05_complex_tfr_coi.png",
    "index.md:fig03_onset_fitting.png",
    "index.md:fig05_complex_tfr_coi.png",
    "index.md:fig07_population_decoding.png",
    "index.md:fig08_permutation_null.png",
    "index.md:fig09_directed_connectivity.png",
    "index.md:fig10_artifact_repair.png",
    "quickstart.md:jnwb_quickstart.png",
)})


def _cases(check: str, names=NAMES):
    return [pytest.param(n, id=n, marks=pytest.mark.xfail(strict=True, reason=AWAITING[(check, n)]))
            if (check, n) in AWAITING else pytest.param(n, id=n) for n in names]


def _links_to_page_showing(href: str | None, stem: str) -> bool:
    """A thumbnail counts at page width only when it links to the built page (`<page>/`) that
    shows the same figure at page width in the reader's theme. A link to the PNG itself opens
    it on the browser's own background, where one of the two variants is unreadable."""
    if not href or not re.fullmatch(r"[\w-]+/", href):
        return False
    page = DOCS / f"{href[:-1]}.md"
    return page.is_file() and bool(
        re.search(rf"^!\[[^\]]*\]\({re.escape(stem)}\.png#only-light\)$",
                  page.read_text(encoding="utf-8"), re.M))


def _img_widths(text: str) -> list[tuple[str, int]]:
    """Each light-scheme `<img>` on a page and the width it is judged at: a thumbnail in a
    table at the gallery width, unless it links to the page that shows it at page width."""
    out = []
    for match in re.finditer(r'(?:<a href="([^"]+)">\s*)?<img src="(assets/[^"]+?)\.png#only-light"', text):
        linked = _links_to_page_showing(match.group(1), match.group(2))
        in_table = text.rfind("<table", 0, match.start()) > text.rfind("</table>", 0, match.start())
        out.append((match.group(2), PAGE_WIDTH_PX if linked or not in_table else GALLERY_WIDTH_PX))
    return out


def _embeds():
    """Each light-scheme figure on a page: (page, figure file name, displayed width, caption)."""
    out = []
    for page in sorted(DOCS.rglob("*.md")):
        text = page.read_text(encoding="utf-8")
        captions = dict(figure_captions(text))
        for stem, width in _img_widths(text):
            out.append((page.name, Path(stem).name + ".png", width,
                        captions.get(f"{stem}.png#only-light", "")))
        for match in re.finditer(r"^!\[[^\]]*\]\((assets/[^)\s]+?)\.png#only-light\)", text, re.M):
            out.append((page.name, Path(match.group(1)).name + ".png", PAGE_WIDTH_PX,
                        captions.get(f"{match.group(1)}.png#only-light", "")))
    return out


EMBEDS = _embeds()


def _embed_cases(check: str):
    cases = []
    for page, name, width, caption in EMBEDS:
        key = (check, f"{page}:{name}")
        marks = [pytest.mark.xfail(strict=True, reason=AWAITING[key])] if key in AWAITING else []
        cases.append(pytest.param(name, width, caption, id=f"{page}:{name}", marks=marks))
    return cases


# ---------------------------------------------------------------------------------------------
# The committed files and the pages


@pytest.mark.parametrize("png", FIGURES, ids=lambda p: p.name)
def test_no_figure_paints_its_own_background(png):
    import matplotlib.image as mpimg

    image = mpimg.imread(png)
    assert image.ndim == 3 and image.shape[2] == 4, f"{png.name} has no alpha channel"
    corners = image[[0, 0, -1, -1], [0, -1, 0, -1], 3]
    assert np.all(corners == 0), f"{png.name} paints a background: corner alpha {corners}"


def test_every_awaiting_entry_names_a_case():
    cases = set(NAMES) | {g.name for g in GENERATORS} | {STYLE_MODULE.name} | {
        f"{page}:{name}" for page, name, _, _ in EMBEDS}
    stale = [key for key in AWAITING if key[1] not in cases]
    assert not stale, f"entries that no test reads: {stale}"


def test_every_embed_is_inspected():
    assert len(EMBEDS) >= 16, EMBEDS
    assert {name for _, name, _, _ in EMBEDS} <= set(NAMES), EMBEDS


# ---------------------------------------------------------------------------------------------
# Colour


@pytest.mark.parametrize("generator", [pytest.param(g, id=g.name, marks=[pytest.mark.xfail(
    strict=True, reason=AWAITING[("theme contrast", g.name)])] if ("theme contrast", g.name) in AWAITING
    else []) for g in GATED])
def test_every_theme_colour_reads_on_its_own_page(generator):
    failures = _theme_contrast_failures(generator.read_text(encoding="utf-8"))
    assert not failures, f"{generator.name}: {failures}"


@pytest.mark.parametrize("name", _cases("ink contrast"))
def test_little_of_the_ink_is_too_faint_to_see(drawn, name):
    theme = "dark" if ".dark" in name else "light"
    item = drawn[name]
    share = _dim_ink_share(item.rgba, PAGE[theme], item.exempt)
    assert share <= MAX_DIM_INK_SHARE, f"{name}: {share:.1%} of the ink is below {DIM_INK} on the page"


def test_the_colour_checks_catch_their_cases():
    assert _illegible_literals('ax.plot(x, color="#000000")\n')
    assert _illegible_literals('ax.set_title("t", color="white")\n')
    assert _illegible_literals('ax.plot(x, color="navy")\n'), "a named colour is not parsed"
    assert _illegible_literals('ax.plot(x, color="k")\n')
    assert not _illegible_literals('ax.plot(x, color="#888888")\n')
    assert not _illegible_literals('open(path, "w")\n'), "a one-letter string read as a colour"
    faint = 'THEMES = {"light": {"fg": "#2d2d2d", "faint": "#e0e0e0"}, "dark": {"fg": "#e0e0e0", "faint": "#8a8a8a"}}\n'
    clean = 'THEMES = {"light": {"fg": "#2d2d2d", "faint": "#8a8a8a"}, "dark": {"fg": "#e0e0e0", "faint": "#8a8a8a"}}\n'
    assert _theme_contrast_failures(faint) == ["light.faint #e0e0e0 (mark): 1.32 < 3.0"]
    assert not _theme_contrast_failures(clean)
    assert _theme_contrast_failures('THEMES = {"light": {"new": "navy"}}\n')
    assert not _illegible_literals(faint), "a THEMES colour is left to the per-theme check"


def test_the_ink_check_sees_a_faint_fill_and_exempts_a_mesh():
    def render(colour):
        fig, ax = plt.subplots(figsize=(3, 2), dpi=100)
        fig.patch.set_alpha(0)
        ax.patch.set_alpha(0)
        ax.bar([0, 1, 2], [3, 2, 1], color=colour)
        fig.canvas.draw()
        rgba = np.asarray(fig.canvas.buffer_rgba()).copy()
        plt.close(fig)
        return rgba

    faint = render("#e0e0e0")
    clean = render("#7048e8")
    assert _dim_ink_share(faint, PAGE["light"]) > MAX_DIM_INK_SHARE
    assert _dim_ink_share(clean, PAGE["light"]) <= MAX_DIM_INK_SHARE
    fig, ax = plt.subplots(figsize=(3, 2), dpi=100)
    fig.patch.set_alpha(0)
    ax.axis("off")
    mesh = ax.pcolormesh(np.arange(4), np.arange(4), np.zeros((3, 3)), cmap="magma", vmin=0, vmax=1)
    fig.canvas.draw()
    floor = np.asarray(fig.canvas.buffer_rgba()).copy()
    exempt = [mesh.get_window_extent(fig.canvas.get_renderer())]
    plt.close(fig)
    assert _dim_ink_share(floor, PAGE["dark"]) > MAX_DIM_INK_SHARE, "magma's floor reads on dark"
    assert _dim_ink_share(floor, PAGE["dark"], exempt) <= MAX_DIM_INK_SHARE


# ---------------------------------------------------------------------------------------------
# Placement


@pytest.mark.parametrize("name", _cases("legends"))
def test_no_legend_covers_the_data(drawn, name):
    hits = _legend_overlaps(drawn[name].fig)
    assert not hits, f"{name}: a legend is drawn over {hits}"


@pytest.mark.parametrize("name", _cases("text placement"))
def test_no_text_meets_the_data_or_another_text(drawn, name):
    hits = _text_collisions(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", _cases("shared x"))
def test_axes_that_share_x_line_up(drawn, name):
    hits = _shared_x_misalignment(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


def _figure(**kw):
    return plt.subplots(**kw)


def _legend_reach_cases():
    """One figure per kind of artist a legend can be drawn over, keyed by that kind."""
    x, y = np.meshgrid(np.linspace(0, 1, 40), np.linspace(0, 1, 40))
    cases = {}

    fig, ax = _figure()
    ax.bar([1, 2, 3], [100, 100, 100])
    ax.axhline(50, label="baseline")
    ax.set_ylim(0, 105)
    ax.legend(frameon=False, loc="upper right")
    cases["a bar"] = fig
    fig, ax = _figure()
    ax.pcolormesh(x, y, x * y, shading="auto")
    ax.plot([], [], label="key")
    ax.legend(loc="upper left")
    cases["a mesh"] = fig
    fig, ax = _figure()
    ax.imshow(x * y, extent=(0, 1, 0, 1))
    ax.plot([], [], label="key")
    ax.legend(loc="upper left")
    cases["an image"] = fig
    fig, ax = _figure()
    ax.scatter([0.05], [0.95], s=40, label="one point")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left")
    fig.canvas.draw()
    box = ax.get_legend().get_window_extent(fig.canvas.get_renderer())
    assert box.contains(*ax.transData.transform((0.05, 0.95))), "the point must sit under the legend"
    cases["one point"] = fig
    fig, ax = _figure(figsize=(4, 3), dpi=100)
    ax.plot([0.0], [0.95], "o", ms=60, label="big markers")
    ax.set_xlim(-0.2, 1.2)
    ax.set_ylim(-0.2, 1.2)
    ax.legend(loc="upper left", frameon=False, markerscale=0.1)
    fig.canvas.draw()
    box = ax.get_legend().get_window_extent(fig.canvas.get_renderer())
    centre = ax.transData.transform((0.0, 0.95))
    assert not box.contains(*centre), "the marker case must keep its centre outside the legend"
    cases["a marker's edge"] = fig
    fig, ax = _figure()
    ax.plot([0, 1], [0, 0], label="left")
    twin = ax.twinx()
    twin.plot([0, 1], [1, 1], lw=3)
    twin.set_ylim(0, 1.05)
    ax.legend(loc="upper left")
    cases["a twin axes"] = fig
    fig, ax = _figure()
    ax.plot([0, 1], [1, 1], label="line")
    ax.set_ylim(0, 1.05)
    fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
    cases["a figure legend"] = fig
    fig, ax = _figure()
    ax.plot([], [], label="key")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.annotate("", xy=(0.05, 0.95), xytext=(0.9, 0.1), arrowprops=dict(arrowstyle="->"))
    ax.legend(loc="upper left")
    cases["an annotation arrow"] = fig
    fig, (a, b) = _figure(ncols=2)
    a.set_xlim(0, 1)
    a.set_ylim(0, 1)
    a.plot([], [], label="key")
    a.legend(loc="upper left")
    b.text(-0.95, 0.9, "text of the next axes", transform=b.transAxes)
    cases["another axes' text"] = fig
    return cases


def test_the_legend_check_sees_every_kind_of_artist():
    # The cases place a legend over an artist by layout, and the layout follows font size and
    # figure size. Build and measure them under Matplotlib's defaults, whatever an earlier test
    # left in rcParams.
    with plt.style.context("default"):
        cases = _legend_reach_cases()
        missed = [what for what, f in cases.items() if not _legend_overlaps(f)]
        for f in cases.values():
            plt.close(f)
    assert not missed, f"the legend check does not see {missed}"

    x, y = np.meshgrid(np.linspace(0, 1, 40), np.linspace(0, 1, 40))
    fig, ax = _figure()
    ax.bar([1, 2, 3], [100, 100, 100])
    ax.axhline(50, label="baseline")
    # A line contour's open arms reach the top corners; the legend sits between them.
    ax.contour(x * 4 + 0.5, y * 150, (x - 0.5) ** 2 * 4 - y, levels=[0.0], linestyles="--")
    ax.set_ylim(0, 150)
    ax.legend(frameon=False, loc="upper center")
    clean = _legend_overlaps(fig)
    plt.close(fig)
    assert not clean, clean


def test_the_text_check_catches_its_cases():
    cases = {}
    fig, ax = _figure()
    ax.axvline(0.5)
    ax.text(0.4, 0.5, "crossed by a line")
    cases["a line"] = fig
    fig, ax = _figure()
    ax.bar([0], [1.0])
    ax.text(0.0, 0.5, "over a bar", ha="center")
    cases["a bar"] = fig
    fig, ax = _figure()
    ax.text(0.2, 0.5, "first text")
    ax.text(0.25, 0.5, "second text")
    cases["a text"] = fig
    fig, ax = _figure()
    ax.text(1.4, 0.5, "past the edge", transform=ax.transAxes)
    cases["the canvas edge"] = fig
    fig, ax = _figure()
    ax.scatter([0.5], [0.5], s=400)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.text(0.51, 0.5, "beside a point's centre")
    cases["a marker"] = fig
    missed = [what for what, f in cases.items() if not _text_collisions(f)]
    fig, ax = _figure()
    ax.axvline(0.5)
    ax.bar([0], [0.3])
    ax.set_xlim(-0.5, 1)
    ax.set_ylim(0, 1)
    ax.text(0.6, 0.8, "clear of both")
    clean = _text_collisions(fig)
    for f in list(cases.values()) + [fig]:
        plt.close(f)
    assert not missed, f"the text check does not see {missed}"
    assert not clean, clean


def test_the_shared_x_check_catches_a_colorbar_narrowing_one_axes():
    fig, (a, b) = _figure(nrows=2, sharex=True)
    mesh = b.pcolormesh(np.arange(5), np.arange(3), np.ones((2, 4)))
    fig.colorbar(mesh, ax=b)
    narrowed = _shared_x_misalignment(fig)
    fig2, (c, d) = _figure(nrows=2, sharex=True, layout="constrained")
    mesh = d.pcolormesh(np.arange(5), np.arange(3), np.ones((2, 4)))
    fig2.colorbar(mesh, ax=[c, d])
    fig2.canvas.draw()
    aligned = _shared_x_misalignment(fig2)
    plt.close(fig)
    plt.close(fig2)
    assert narrowed and not aligned, (narrowed, aligned)


# ---------------------------------------------------------------------------------------------
# Labels, units and size


@pytest.mark.parametrize("name", _cases("axis labels"))
def test_every_numeric_axis_is_labelled_with_its_unit(drawn, name):
    hits = _axis_label_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", _cases("declared unit"))
def test_an_axis_names_the_unit_its_result_declares(drawn, name):
    hits = _declared_unit_failures(drawn[name].fig, drawn[name].results)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name,width,caption", _embed_cases("displayed size"))
def test_the_smallest_text_is_legible_where_the_page_shows_it(drawn, name, width, caption):
    fig = drawn[name].fig
    points = _smallest_text_pt(fig)
    px = _displayed_px(points, fig.get_figwidth(), width)
    assert px >= MIN_TEXT_PX, (
        f"{name}: {points:.1f} pt in a {fig.get_figwidth():.1f} in figure shown at {width} px "
        f"renders at {px:.1f} px")


@pytest.mark.parametrize("name,width,caption", _embed_cases("displayed size at the mobile width"))
def test_the_smallest_text_is_legible_at_the_mobile_width(drawn, name, width, caption):
    """A figure shown wider than the phone's content column is scaled down to it."""
    fig = drawn[name].fig
    shown = _mobile_width_px(width)
    points = _smallest_text_pt(fig)
    px = _displayed_px(points, fig.get_figwidth(), shown)
    assert px >= MIN_TEXT_PX, (
        f"{name}: {points:.1f} pt in a {fig.get_figwidth():.1f} in figure shown at {shown} px "
        f"renders at {px:.1f} px")


def test_the_mobile_width_reads_text_the_page_width_passes():
    """7.5 pt in a 7.2 in figure reads at the page width, not at the phone's; a narrower figure
    holds at both. A gallery cell, already narrower than the phone, keeps its own width."""
    assert _displayed_px(7.5, 7.2, PAGE_WIDTH_PX) >= MIN_TEXT_PX
    assert _displayed_px(7.5, 7.2, _mobile_width_px(PAGE_WIDTH_PX)) < MIN_TEXT_PX
    assert _displayed_px(7.5, 3.0, _mobile_width_px(PAGE_WIDTH_PX)) >= MIN_TEXT_PX
    assert _mobile_width_px(GALLERY_WIDTH_PX) == GALLERY_WIDTH_PX


#: A number that rounds to zero and prints its minus sign: "-0.0", "−0", "-0.00".
NEGATIVE_ZERO = re.compile(r"(?<![\w.])[-−]0(?:\.0+)?(?![\w.])")


def _negative_zeros(fig) -> list[str]:
    _renderer(fig)
    return [t.get_text() for t in _drawn_texts(fig) if NEGATIVE_ZERO.search(t.get_text())]


@pytest.mark.parametrize("name", _cases("signed zero"))
def test_no_number_reads_as_a_negative_zero(drawn, name):
    hits = _negative_zeros(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


def test_the_signed_zero_check_catches_its_cases():
    assert [s for s in ("-0.0", "−0", "x = -0.00", "(-0)") if NEGATIVE_ZERO.search(s)] == [
        "-0.0", "−0", "x = -0.00", "(-0)"]
    assert not [s for s in ("+0.0", "-0.5", "-10.0", "0.0", "t-0", "-0.05", "−0.01") if NEGATIVE_ZERO.search(s)]


def test_the_label_and_size_checks_catch_their_cases():
    assert _names_a_unit("Time (ms)") and _names_a_unit("PSD (a.u.²/Hz)")
    assert _names_a_unit("PSI per frequency bin (dimensionless)")
    assert not _names_a_unit("Mean Paired Difference (Δ Fire Rate)")
    assert not _names_a_unit("Power Spectral Density")
    fig, (a, b, c) = _figure(ncols=3)
    a.plot([1, 2], [1, 2])
    a.set_ylabel("Power Spectral Density")
    a.set_xlabel("Frequency (Hz)")
    b.plot([1, 2], [1, 2])
    b.set_xlabel("Frequency (Hz)")
    c.bar([0, 1], [1, 2])
    c.set_xticks([0, 1], ["AUC", "F1"])
    c.set_ylabel("Unit count")
    hits = _axis_label_failures(fig)
    plt.close(fig)
    assert hits == ["axes 0: 'Power Spectral Density' names no unit", "axes 1: the y axis has no label"], hits
    assert _displayed_px(6.4, 11.0, PAGE_WIDTH_PX) < MIN_TEXT_PX
    assert _displayed_px(7.5, 7.2, PAGE_WIDTH_PX) >= MIN_TEXT_PX


def test_the_declared_unit_check_catches_a_phase_slope_label(drawn):
    item = drawn["fig09_directed_connectivity.png"]
    ax = _axes_titled(item.fig, "phase_slope_index")
    kept = ax.get_ylabel()
    try:
        ax.set_ylabel("Phase Slope (rad/Hz)")
        planted = _declared_unit_failures(item.fig, item.results)
    finally:
        ax.set_ylabel(kept)
    assert planted and "'psi'" in planted[0], planted


def test_the_declared_unit_check_reads_data_values_not_axes_fractions():
    """An `axvline` spans y 0 to 1 in axes fractions; a result holding a 0 and a 1 is not drawn
    by it. The same values drawn as data are."""
    @dataclass
    class Result:
        low: float = 0.0
        high: float = 1.0
        unit: str = "log variance ratio"

    fig, (vertical, data) = _figure(ncols=2)
    vertical.plot([0, 1], [5, 7])
    vertical.axvline(0.5)
    vertical.set_ylabel("rate (Hz)")
    data.plot([0, 1], [0.0, 1.0])
    data.set_ylabel("influence")
    hits = _declared_unit_failures(fig, [Result()])
    plt.close(fig)
    assert hits == ["axes 1: 'influence' does not name the unit 'log variance ratio'"], hits


# ---------------------------------------------------------------------------------------------
# Source rules


@pytest.mark.parametrize("generator", [pytest.param(g, id=g.name, marks=[pytest.mark.xfail(
    strict=True, reason=AWAITING[("style source", g.name)])] if ("style source", g.name) in AWAITING
    else []) for g in GENERATORS])
def test_fonts_and_width_come_from_one_style_module(generator):
    hits = _style_violations(generator.read_text(encoding="utf-8"))
    assert not hits, f"{generator.name}: {hits}"


@pytest.mark.xfail(("style source", STYLE_MODULE.name) in AWAITING, strict=True,
                   reason=AWAITING.get(("style source", STYLE_MODULE.name), ""))
def test_the_style_module_sets_the_family_and_the_size_tiers():
    assert STYLE_MODULE.is_file(), f"{STYLE_MODULE.relative_to(REPO_ROOT)} does not exist"
    source = STYLE_MODULE.read_text(encoding="utf-8")
    for key in ("font.family", "font.size", "legend.fontsize", "xtick.labelsize"):
        assert f'"{key}"' in source, f"{STYLE_MODULE.name} does not set {key}"


@pytest.mark.parametrize("generator", GENERATORS, ids=lambda p: p.name)
def test_every_colormap_is_perceptual_or_declared_diverging(generator):
    hits = _colormap_violations(generator.read_text(encoding="utf-8"))
    assert not hits, f"{generator.name}: {hits}"


@pytest.mark.parametrize("generator", [pytest.param(g, id=g.name, marks=[pytest.mark.xfail(
    strict=True, reason=AWAITING[("computed values", g.name)])] if ("computed values", g.name) in AWAITING
    else []) for g in GENERATORS])
def test_no_reference_line_is_a_typed_number(generator):
    hits = _literal_references(generator.read_text(encoding="utf-8"))
    assert not hits, f"{generator.name}: {hits}"


@pytest.mark.parametrize("name", _cases("computed values"))
def test_every_figure_calls_a_public_jnwb_function(drawn, name):
    public = set(jnwb.__all__)
    empty = [fn for fn, log in drawn[name].calls.items() if not {n for n, _ in log} & public]
    assert drawn[name].calls and not empty, f"{name}: {empty or 'nothing'} calls no public jnwb function"


def test_the_source_rules_catch_their_cases():
    serif = ('plt.rcParams.update({"font.family": "serif"})\n'
             'fig, ax = plt.subplots(figsize=(7.2, 3))\nax.text(0, 0, "a", fontsize=7.0)\n')
    styled = ("import figure_style as style\nfig, ax = plt.subplots(figsize=(style.WIDTH, 3))\n"
              'ax.text(0, 0, "a", fontsize=style.SMALL)\n')
    assert len(_style_violations(serif)) == 4, _style_violations(serif)
    assert not _style_violations(styled)
    assert _colormap_violations('ax.pcolormesh(x, y, z, cmap="jet")\n')
    assert _colormap_violations('plt.get_cmap("rainbow")\n')
    assert not _colormap_violations('ax.pcolormesh(x, y, z, cmap="magma")\n')
    literal = ("def f(ax, t0):\n    ax.axvline(1000.0)\n    ax.axhline(y=-0.5)\n"
               "    ax.axvspan(200, 400)\n    ax.axvline(t0)\n    ax.axhline(0)\n"
               "    ax.axhline(t0, xmin=0.1)\n    ax.hlines(0.5, -0.4, 0.4)\n")
    assert len(_literal_references(literal)) == 5, _literal_references(literal)

    recorder = _Recorder(jnwb)
    recorder.log = log = []
    recorder.to_db(np.array([2.0]))
    assert log and log[0][0] == "to_db"
    assert recorder.CANONICAL_BANDS is jnwb.CANONICAL_BANDS


# ---------------------------------------------------------------------------------------------
# Captions and fits


@pytest.mark.parametrize("name,width,caption", _embed_cases("captions"))
def test_every_function_a_title_names_is_in_the_caption(drawn, name, width, caption):
    hits = _caption_failures(drawn[name].fig, caption)
    assert not hits, f"{name}: {hits}; caption: {caption!r}"


@pytest.mark.parametrize("name", _cases("fits"))
def test_a_drawn_fit_is_centred_on_its_spectrum(drawn, name):
    hits = _fit_offsets(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


def test_the_caption_check_catches_a_caption_that_misses_a_function():
    fig, ax = _figure()
    ax.set_title("A. Fit (jnwb.fit_exponential_onset)")
    assert _caption_failures(fig, "PSTH and exponential onset fit")
    assert not _caption_failures(fig, "One fit_exponential_onset result on a synthetic rate")
    ax.set_title("A. (jnwb.not_a_public_name)")
    assert "jnwb.not_a_public_name is not in jnwb.__all__" in _caption_failures(fig, "not_a_public_name")
    plt.close(fig)


def test_the_fit_check_catches_a_fit_of_another_spectrum():
    """The fit of `spectral_tilt`'s own one-segment spectrum, drawn over `compute_psd`'s."""
    fs = 1000.0
    rng = np.random.default_rng(12)
    t = np.arange(5000) / fs
    pink = np.cumsum(rng.standard_normal(t.size))
    lfp = (pink - pink.mean()) / pink.std() + 0.8 * np.sin(2 * np.pi * 10.0 * t)
    freqs, psd = jnwb.compute_psd(lfp, fs=fs)
    tilt = jnwb.spectral_tilt(lfp, sampling_rate=fs, freq_range=(2.0, 90.0))
    mask = (freqs >= 2.0) & (freqs <= 90.0)
    fig, (wrong, right) = _figure(ncols=2)
    wrong.loglog(freqs[1:120], psd[1:120], label="Welch PSD")
    wrong.loglog(freqs[mask], tilt["offset"] * freqs[mask] ** tilt["slope"], label="Power-law fit")
    fit = jnwb.aperiodic_fit(freqs[1:], psd[1:], freq_range=(15.0, 90.0))
    f = freqs[(freqs >= 15.0) & (freqs <= 90.0)]
    right.loglog(freqs[1:120], psd[1:120], label="Welch PSD")
    right.loglog(f, 10.0 ** (fit.offset - fit.exponent * np.log10(f)), label="Power-law fit")
    hits = _fit_offsets(fig)
    plt.close(fig)
    assert len(hits) == 1 and hits[0].startswith("axes 0"), hits


# ---------------------------------------------------------------------------------------------
# Content of three figures


def _title(ax) -> str:
    """The panel title wherever it is aligned: the left, centre and right titles, joined."""
    return " ".join(ax.get_title(loc=loc) for loc in ("left", "center", "right")).strip()


def _axes_titled(fig, needle):
    matches = [ax for ax in fig.axes if needle in _title(ax)]
    assert len(matches) == 1, [_title(ax) for ax in fig.axes]
    return matches[0]


def test_the_depth_class_panel_does_not_call_its_class_a_layer(drawn):
    # `classify_layer_from_depth` returns a geometric depth class; the function's name is the
    # only place the word may appear.
    ax = _axes_titled(drawn["fig01_addressing_laminar.png"].fig, "classify_layer_from_depth")
    words = _title(ax).replace("classify_layer_from_depth", "").lower()
    assert "layer" not in words and "cortical" not in words, _title(ax)


def test_the_power_law_line_is_the_fit_of_the_spectrum_under_it(drawn):
    """The fit line is the least-squares power law of the drawn spectrum over the fit's own
    bins, those bins start above the synthetic rhythm (the fit removes no peaks), and the slope
    in its label is that fit's slope."""
    ax = _axes_titled(drawn["fig04_psd_spectral_tilt.png"].fig, "aperiodic_fit")
    lines = {line.get_label().split(":")[0]: line for line in ax.get_lines()}
    psd_f, psd = (np.asarray(v, float) for v in lines["Welch PSD"].get_data())
    fit_f, fit = (np.asarray(v, float) for v in lines["Power-law fit"].get_data())
    assert np.isin(fit_f, psd_f).all(), "the fit is drawn at frequencies the spectrum is not"
    rhythm = drawn["generator"].FIG04_RHYTHM_HZ
    assert fit_f.min() > rhythm, f"the fit starts at {fit_f.min()} Hz, across the {rhythm} Hz peak"
    at = psd[np.searchsorted(psd_f, fit_f)]
    slope, intercept = np.polyfit(np.log10(fit_f), np.log10(at), 1)
    offset = np.max(np.abs(np.log10(fit) - (intercept + slope * np.log10(fit_f))))
    assert offset < 1e-6, f"the fit line is {offset:.3f} decades from the drawn spectrum's fit"
    shown = re.search(r"slope\s*=\s*([-−]?\d+\.\d+)", lines["Power-law fit"].get_label()).group(1)
    printed = float(shown.replace(TRUE_MINUS, "-"))
    assert printed == pytest.approx(slope, abs=0.005), (printed, slope)


def _shaded_sum(ax, line):
    """The drawn span labelled as summed, and the sum of the line's points inside it."""
    spans = [p for p in ax.patches if p.get_label().startswith("Summed")]
    assert len(spans) == 1, [p.get_label() for p in ax.patches]
    xs = spans[0].get_path().transformed(spans[0].get_patch_transform()).vertices[:, 0]
    x, y = (np.asarray(v, float) for v in line.get_data())
    inside = (x >= xs.min()) & (x <= xs.max())
    return float(y[inside].sum())


def test_the_psi_shading_covers_exactly_the_bins_the_net_value_sums(drawn):
    entry = drawn["fig09_directed_connectivity.png"]
    ax = _axes_titled(entry.fig, "phase_slope_index")
    psi = next(out for name, out in entry.calls["fig09_directed_connectivity"]
               if name == "phase_slope_index")
    line = next(ln for ln in ax.get_lines() if ln.get_label().startswith("Net PSI"))
    assert _shaded_sum(ax, line) == pytest.approx(psi.x_to_y, abs=1e-9), (
        "the points under the shading do not sum to the net PSI the function returned")


def test_the_psi_shading_check_catches_the_nominal_band_edges(drawn):
    entry = drawn["fig09_directed_connectivity.png"]
    ax = _axes_titled(entry.fig, "phase_slope_index")
    line = next(ln for ln in ax.get_lines() if ln.get_label().startswith("Net PSI"))
    psi = next(out for name, out in entry.calls["fig09_directed_connectivity"]
               if name == "phase_slope_index")
    fig, wide = plt.subplots()
    wide.plot(*line.get_data())
    wide.axvspan(*psi.per_band["band"]["band_hz"], label="Summed band")
    try:
        assert _shaded_sum(wide, wide.get_lines()[0]) != pytest.approx(psi.x_to_y, abs=1e-3)
    finally:
        plt.close(fig)


@pytest.mark.parametrize("href", [
    "assets/figures/fig05_complex_tfr_coi.png",
    "07_statistical_inference_and_nulls/",
    "no_such_page/",
], ids=["the raw PNG", "a page without the figure", "a missing page"])
def test_a_thumbnail_is_judged_at_gallery_width_unless_it_links_to_its_page(href):
    stem = "assets/figures/fig05_complex_tfr_coi"
    cell = f'<table><tr><td><a href="{{}}"><img src="{stem}.png#only-light"></a></td></tr></table>'
    assert _img_widths(cell.format("coherence_and_tfr/")) == [(stem, PAGE_WIDTH_PX)]
    assert _img_widths(cell.format(href)) == [(stem, GALLERY_WIDTH_PX)]


def test_the_psi_axis_carries_no_phase_slope_unit(drawn):
    # PSI is dimensionless (the result declares unit='psi'); rad/Hz reads it as dphi/df, the
    # step to a delay.
    ax = _axes_titled(drawn["fig09_directed_connectivity.png"].fig, "phase_slope_index")
    label = ax.get_ylabel()
    assert "rad" not in label and "Hz" not in label, label


# ---------------------------------------------------------------------------------------------
# The docs figure style. The checks read the drawn figure, since a
# default that no one set (the colour cycle, the font family) draws without a literal in any
# source; the palette and the line widths are also read in the source, so a generator cannot
# type its own.

from matplotlib.collections import Collection, LineCollection  # noqa: E402
from matplotlib.font_manager import weight_dict  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

#: The ruled values. `figure_style.py` is the one place a figure takes them from, and this is
#: the one place the suite spells them out.
RULED_SERIES = ("#1565c0", "#ff9800", "#00acc1", "#e53935")
RULED_HIGHLIGHT_DARK = "#cfb87c"
RULED_TEXT_PT = (8.0, 11.0)
RULED_LINE_PT = (1.2, 1.8)
TRUE_MINUS = "−"
#: An ASCII hyphen where a minus belongs: before a digit, and not after a character that makes it
#: a range ("0-7") or a compound.
ASCII_MINUS = re.compile(r"(?<![\w)\]-])-(?=\d)")
#: Colour-vision distance (CIE76 ΔE) the drawn colours keep: among the series and highlight, and
#: between the neutral and any of them.
MIN_CVD_DELTA_E = 20.0
MIN_CVD_NEUTRAL_DELTA_E = 15.0
#: Named variables and the legend labels that name them, one pattern each.
VARIABLE_LABELS = {
    "observed": r"^(observed|raw)\b",
    "truth": r"^(ground truth|true)\b",
    "fitted": r"\bfit(ted)?\b",
    "smoothed": r"^causal",
    "baseline": r"^majority baseline",
}
WIDTH_KEYS = {"lw", "linewidth", "linewidths"}


def _rgb_hex(colours) -> set[str]:
    """The visible colours of anything `to_rgba_array` reads, as lower-case hex without alpha."""
    rgba = mcolors.to_rgba_array(colours)
    return {mcolors.to_hex(row[:3]) for row in rgba if row[3] > 0}


def _drawn_colours(fig) -> dict[str, list[str]]:
    """Every colour the canvas paints with, from lines, markers, patches, collections and text,
    each with what drew it. Meshes and images are colour-mapped data and are not read."""
    _renderer(fig)
    found: dict[str, list[str]] = {}

    def add(colours, what):
        for colour in _rgb_hex(colours):
            found.setdefault(colour, []).append(what)

    for line in fig.findobj(Line2D):
        if not line.get_visible():
            continue
        what = f"line {line.get_label()!r}"
        if line.get_linestyle() not in ("None", "", " "):
            add([line.get_color()], what)
        if line.get_marker() not in (None, "None", "", " "):
            add([line.get_markerfacecolor(), line.get_markeredgecolor()], what)
    for patch in fig.findobj(Patch):
        if patch.get_visible():
            what = f"patch {patch.get_label()!r}"
            if patch.get_fill():
                add([patch.get_facecolor()], what)
            if patch.get_linewidth() > 0:
                add([patch.get_edgecolor()], what)
    for collection in fig.findobj(Collection):
        if collection.get_visible() and not isinstance(collection, QuadMesh):
            what = f"collection {collection.get_label()!r}"
            add(collection.get_facecolor(), what)
            if np.any(np.asarray(collection.get_linewidth()) > 0):
                add(collection.get_edgecolor(), what)
    for text in _drawn_texts(fig):
        add([text.get_color()], f"text {text.get_text()!r}")
    return found


def _ink(name: str) -> set[str]:
    """The ink colours of the theme `name` is drawn in, read from its generator's `THEMES`."""
    source = (DOC_GENERATOR if name.startswith("fig") else QUICKSTART if name.startswith("jnwb_")
              else TUTORIAL).read_text(encoding="utf-8")
    table = ast.literal_eval(_themes_node(ast.parse(source)))
    colours = table["dark" if ".dark" in name else "light"]
    return {mcolors.to_hex(v) for k, v in colours.items() if k not in NOT_A_COLOUR}


def _palette_strays(fig, ink: set[str], theme: str) -> list[str]:
    """Colours drawn that are no series, no neutral, not `theme`'s highlight and not its ink."""
    allowed = {mcolors.to_hex(c) for c in (*STYLE.SERIES, STYLE.HIGHLIGHT[theme], STYLE.NEUTRAL)} | ink
    return [f"{colour} by {drew[0]}" for colour, drew in sorted(_drawn_colours(fig).items())
            if colour not in allowed]


def _colour_literals(source: str) -> list[str]:
    """A colour typed into a figure source outside its `THEMES` table."""
    tree = ast.parse(source)
    table = _themes_node(tree)
    in_table = {id(n) for n in ast.walk(table)} if table is not None else set()
    in_argument = {id(n) for kw in ast.walk(tree) if isinstance(kw, ast.keyword)
                   and kw.arg in gate.COLOUR_ARGUMENTS for n in ast.walk(kw.value)}
    return [f"line {n.lineno}: {n.value}" for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in in_table
            and _hex(n.value, id(n) in in_argument) is not None]


def _width_literals(source: str) -> list[str]:
    """A line width typed into a figure source: anything but the style module's, or zero."""
    tree = ast.parse(source)
    modules, names = _style_aliases(tree)
    return [f"line {kw.value.lineno}: {kw.arg}={ast.unparse(kw.value)}" for kw in ast.walk(tree)
            if isinstance(kw, ast.keyword) and kw.arg in WIDTH_KEYS
            and not (isinstance(kw.value, ast.Constant) and kw.value.value == 0)
            and not _from_style(kw.value, modules, names)]


_CVD = {  # Machado, Oliveira and Fernandes (2009), severity 1.0, applied in linear sRGB
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413],
               [-0.011820, 0.042940, 0.968881]],
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216],
               [-0.003882, -0.048116, 1.051998]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602],
               [0.004733, 0.691367, 0.303900]],
}
_XYZ = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750],
                 [0.0193339, 0.1191920, 0.9503041]])
_WHITE = np.array([0.95047, 1.0, 1.08883])


def _lab(rgb: np.ndarray) -> np.ndarray:
    xyz = _XYZ @ rgb / _WHITE
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.array([116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])])


def _delta_e(a: str, b: str, kind: str) -> float:
    """CIE76 distance between two colours as a viewer with the `kind` deficiency sees them."""
    def seen(colour):
        rgb = np.array(mcolors.to_rgb(colour))
        lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
        lin = np.clip(np.array(_CVD[kind]) @ lin, 0.0, 1.0)
        return _lab(lin)
    return float(np.linalg.norm(seen(a) - seen(b)))


def _cvd_failures(colours, marks=(*STYLE.SERIES, *STYLE.HIGHLIGHT.values())) -> list[str]:
    """Pairs of the `marks` colours among `colours`, and the neutral against them, that two
    viewers of a colour-vision deficiency cannot tell apart."""
    colours = {mcolors.to_hex(c) for c in colours}
    marks = sorted(colours & {mcolors.to_hex(c) for c in marks})
    neutral = mcolors.to_hex(STYLE.NEUTRAL)
    hits = []
    for kind in _CVD:
        for i, a in enumerate(marks):
            for b in marks[i + 1:]:
                if (d := _delta_e(a, b, kind)) < MIN_CVD_DELTA_E:
                    hits.append(f"{a} and {b} are {d:.1f} apart under {kind}")
            if neutral in colours and (d := _delta_e(a, neutral, kind)) < MIN_CVD_NEUTRAL_DELTA_E:
                hits.append(f"{a} and the neutral are {d:.1f} apart under {kind}")
    return hits


def _text_size_failures(fig, bounds=RULED_TEXT_PT) -> list[str]:
    _renderer(fig)
    return [f"{t.get_text()!r} is {t.get_fontsize():g} pt" for t in _drawn_texts(fig)
            if not bounds[0] <= t.get_fontsize() <= bounds[1]]


def _font_failures(fig) -> list[str]:
    _renderer(fig)
    return [f"{t.get_text()!r} is set in {t.get_fontfamily()}" for t in _drawn_texts(fig)
            if t.get_fontfamily()[0] != STYLE.FONT]


def _spine_failures(fig) -> list[str]:
    return [f"axes {i} draws its {side} spine" for i, ax in enumerate(fig.axes)
            for side in ("top", "right") if ax.spines[side].get_visible()]


def _is_bold(text) -> bool:
    weight = text.get_fontweight()
    return (weight_dict.get(weight, 400) if isinstance(weight, str) else weight) >= 700


def _panel_axes(fig) -> list:
    """The axes that are panels: those that are no colorbar."""
    bars = {m.colorbar.ax for ax in fig.axes for m in (*ax.collections, *ax.images)
            if getattr(m, "colorbar", None) is not None}
    return [ax for ax in fig.axes if ax not in bars and ax.get_label() != "<colorbar>"]


def _panel_letter_failures(fig) -> list[str]:
    """One bold capital per panel of a multi-panel figure, in order, outside every title."""
    renderer = _renderer(fig)
    axes = _panel_axes(fig)
    if len(axes) < 2:
        return []
    letters = [t for t in _drawn_texts(fig) if re.fullmatch(r"[A-Z]", t.get_text()) and _is_bold(t)]
    want = [chr(ord("A") + i) for i in range(len(axes))]
    hits = []
    if sorted(t.get_text() for t in letters) != want:
        hits.append(f"bold letters {sorted(t.get_text() for t in letters)}, wanted {want}")
        return hits
    titles = {ax.get_title(loc=loc) for ax in axes for loc in ("left", "center", "right")} - {""}
    title_texts = [t for t in fig.findobj(Text) if t.get_text() in titles and t.get_visible()]
    for i, ax in enumerate(axes):
        if re.match(r"[A-Z][.:)]?\s", _title(ax)):
            hits.append(f"the title {_title(ax)!r} carries its own letter")
        corner = ax.get_window_extent(renderer)
        nearest = min(letters, key=lambda t: np.hypot(t.get_window_extent(renderer).x1 - corner.x0,
                                                      t.get_window_extent(renderer).y0 - corner.y1))
        if nearest.get_text() != want[i]:
            hits.append(f"axes {i} is lettered {nearest.get_text()}, wanted {want[i]}")
    for letter in letters:
        box = letter.get_window_extent(renderer)
        hits += [f"letter {letter.get_text()} sits inside the title {t.get_text()!r}"
                 for t in title_texts if _area(box, t.get_window_extent(renderer)) > 0]
    return hits


def _line_width_failures(fig, bounds=RULED_LINE_PT) -> list[str]:
    hits = []
    for i, ax in enumerate(fig.axes):
        if ax not in _panel_axes(fig):
            continue
        for line in ax.get_lines():
            if line.get_visible() and line.get_linestyle() not in ("None", "", " "):
                if not bounds[0] <= line.get_linewidth() <= bounds[1]:
                    hits.append(f"axes {i} line {line.get_label()!r} is {line.get_linewidth():g} pt")
        for c in ax.collections:
            if type(c) is LineCollection:
                for w in np.unique(np.asarray(c.get_linewidth(), float)):
                    if not bounds[0] <= w <= bounds[1]:
                        hits.append(f"axes {i} line collection is {w:g} pt")
    return hits


def _ascii_minus_failures(fig, rc=None) -> list[str]:
    """Texts with an ASCII hyphen as a minus, the tick labels formatted under `rc`. Mathtext is
    not read: it sets a hyphen as a minus sign, which is how a log axis writes `10^{-5}`."""
    with matplotlib.rc_context(rc or {}):
        _renderer(fig)
        return [t.get_text() for t in _drawn_texts(fig)
                if ASCII_MINUS.search(re.sub(r"\$[^$]*\$", "", t.get_text()))]


def _legend_colour(handle) -> str | None:
    """The colour a legend handle shows: a line's, or a patch's fill."""
    if isinstance(handle, Line2D):
        return mcolors.to_hex(handle.get_color())
    if isinstance(handle, Patch):
        return mcolors.to_hex(handle.get_facecolor() if handle.get_fill() else handle.get_edgecolor())
    return None


def _variable_entries(fig) -> dict[str, list[str]]:
    """Each named variable's legend entries in `fig`, as the hex colour each is drawn in."""
    found: dict[str, list[str]] = {name: [] for name in VARIABLE_LABELS}
    for legend in _legends(fig):
        for handle, text in zip(legend.legend_handles, legend.get_texts()):
            for name, pattern in VARIABLE_LABELS.items():
                if re.search(pattern, text.get_text().strip(), re.I) and _legend_colour(handle):
                    found[name].append(_legend_colour(handle))
    return found


def _variable_failures(fig) -> list[str]:
    return [f"{name} is {colour}, not {STYLE.VARIABLE[name]}" for name, colours in
            _variable_entries(fig).items() for colour in colours
            if colour != mcolors.to_hex(STYLE.VARIABLE[name])]


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_every_colour_drawn_is_a_palette_colour_or_the_ink(drawn, name):
    strays = _palette_strays(drawn[name].fig, _ink(name), "dark" if ".dark" in name else "light")
    assert not strays, f"{name}: {strays}"


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_no_figure_source_types_a_colour(source):
    hits = _colour_literals(source.read_text(encoding="utf-8"))
    assert not hits, f"{source.name}: {hits}"


def test_the_style_module_holds_the_ruled_palette():
    assert tuple(STYLE.SERIES) == RULED_SERIES, STYLE.SERIES
    assert STYLE.HIGHLIGHT["dark"] == RULED_HIGHLIGHT_DARK, STYLE.HIGHLIGHT
    assert tuple(STYLE.TEXT_RANGE_PT) == RULED_TEXT_PT and tuple(STYLE.LINE_RANGE_PT) == RULED_LINE_PT
    assert set(STYLE.VARIABLE) == set(VARIABLE_LABELS), "a named variable has no legend pattern"
    assert set(STYLE.VARIABLE.values()) <= {*STYLE.SERIES, STYLE.NEUTRAL}
    sizes = (STYLE.SMALL, STYLE.LABEL, STYLE.TITLE, STYLE.LETTER)
    assert all(RULED_TEXT_PT[0] <= s <= RULED_TEXT_PT[1] for s in sizes), sizes
    widths = (STYLE.LW_THIN, STYLE.LW, STYLE.LW_THICK)
    assert all(RULED_LINE_PT[0] <= w <= RULED_LINE_PT[1] for w in widths), widths


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_the_drawn_colours_stay_apart_under_colour_vision_deficiency(drawn, name):
    hits = _cvd_failures(_drawn_colours(drawn[name].fig))
    assert not hits, f"{name}: {hits}"


def test_the_palette_stays_apart_under_colour_vision_deficiency():
    for theme, highlight in STYLE.HIGHLIGHT.items():
        assert not _cvd_failures([*STYLE.SERIES, highlight, STYLE.NEUTRAL]), theme


def test_the_light_highlight_is_the_dark_one_darkened_to_the_fixed_colour_bar():
    """On the light page #cfb87c reads 1.94, under the bar for a fixed colour. The light theme
    draws the same hue, as dark as the bar needs and no darker."""
    import colorsys

    dark, light = (colorsys.rgb_to_hls(*mcolors.to_rgb(STYLE.HIGHLIGHT[t])) for t in ("dark", "light"))
    assert abs(dark[0] - light[0]) * 360 < 1.0, "the light highlight is another hue"
    assert light[1] < dark[1], "the light highlight is not darker"
    ratio = _contrast(_hex(STYLE.HIGHLIGHT["light"]), PAGE["light"])
    assert gate.MIN_FIXED_CONTRAST <= ratio < gate.MIN_FIXED_CONTRAST + 0.05, ratio
    assert _contrast(_hex(STYLE.HIGHLIGHT["dark"]), PAGE["light"]) < gate.MIN_FIXED_CONTRAST


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_every_text_is_set_in_arial_first(drawn, name):
    hits = _font_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits[:5]}"


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_every_text_measures_8_to_11_pt(drawn, name):
    hits = _text_size_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits[:5]}"


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_no_axes_draws_a_top_or_right_spine(drawn, name):
    hits = _spine_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_each_panel_carries_one_bold_letter_outside_its_title(drawn, name):
    hits = _panel_letter_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_every_data_line_is_1_2_to_1_8_pt(drawn, name):
    hits = _line_width_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_no_figure_source_types_a_line_width(source):
    hits = _width_literals(source.read_text(encoding="utf-8"))
    assert not hits, f"{source.name}: {hits}"


@pytest.mark.parametrize("name", STYLE_NAMES)
def test_no_drawn_text_uses_a_hyphen_for_a_minus(drawn, name):
    hits = _ascii_minus_failures(drawn[name].fig, drawn[name].rc)
    assert not hits, f"{name}: {hits}"


@pytest.mark.parametrize("name", NAMES)
def test_a_named_variable_has_one_colour_in_every_legend(drawn, name):
    hits = _variable_failures(drawn[name].fig)
    assert not hits, f"{name}: {hits}"


def test_every_named_variable_is_drawn_by_the_documentation_figures_and_the_quickstart(drawn):
    """The variable check reads legends, so it is vacuous for a variable no legend names: each
    one is named in a documentation figure and in the quickstart."""
    for name, patterns in {"docs": [n for n in NAMES if n.startswith("fig")],
                           "quickstart": ["jnwb_quickstart.png"]}.items():
        seen = {v for n in patterns for v, colours in _variable_entries(drawn[n].fig).items() if colours}
        assert seen == set(VARIABLE_LABELS), f"{name} names only {sorted(seen)}"


def test_the_tutorial_figure_comes_in_light_and_dark_and_takes_its_style(drawn, tmp_path):
    tutorial = _load_registered(TUTORIAL, "_tutorial_09_plot")
    with matplotlib.rc_context():
        paths = tutorial.plot(_tutorial_result(), tmp_path)
    assert [p.name for p in paths] == ["09_open_data.dark_page1.png", "09_open_data_page1.png"]
    import matplotlib.image as mpimg

    light, dark = (mpimg.imread(tmp_path / n) for n in ("09_open_data_page1.png",
                                                       "09_open_data.dark_page1.png"))
    assert light.shape[2] == dark.shape[2] == 4 and not np.array_equal(light, dark)
    assert not _style_violations(TUTORIAL.read_text(encoding="utf-8"))
    assert not _theme_contrast_failures(TUTORIAL.read_text(encoding="utf-8"))
    for name in TUTORIAL_NAMES:
        item = drawn[name]
        theme = "dark" if ".dark" in name else "light"
        assert _dim_ink_share(item.rgba, PAGE[theme], item.exempt) <= MAX_DIM_INK_SHARE, name


def test_the_style_checks_catch_their_cases():
    # Each departure the ruling names, built under the plain defaults, is flagged; the same
    # figure under the style module is not.
    with matplotlib.rc_context():
        matplotlib.rcdefaults()
        fig, (a, b) = plt.subplots(1, 2)
        a.plot([0, 1], [0, 1], color="#7048e8", lw=0.7, label="Raw")
        b.plot([0, 1], [0, -1], lw=2.0)
        a.set_title("A. both panels in one title")
        a.text(0.5, 0.5, "-0.5 and 10-40 Hz", fontsize=7.0)
        b.text(0.5, 0.2, "twelve", fontsize=12.0)
        a.legend()
        assert _palette_strays(fig, {"#2d2d2d"}, "light"), "a palette colour was not read"
        assert _spine_failures(fig) == ["axes 0 draws its top spine", "axes 0 draws its right spine",
                                        "axes 1 draws its top spine", "axes 1 draws its right spine"]
        assert len(_line_width_failures(fig)) == 2
        assert len(_text_size_failures(fig)) >= 2
        assert _font_failures(fig), "a DejaVu text passed for Arial"
        assert _panel_letter_failures(fig), "a figure with no letters passed"
        assert _ascii_minus_failures(fig) == ["-0.5 and 10-40 Hz"]
        assert _variable_failures(fig), "a Raw entry in a non-observed colour passed"
        plt.close(fig)
    with matplotlib.rc_context():
        matplotlib.rcdefaults()
        STYLE.apply()
        fig, (a, b) = plt.subplots(1, 2)
        a.plot([0, 1], [0, 1], color=STYLE.VARIABLE["observed"], lw=STYLE.LW, label="Raw")
        b.plot([0, 1], [0, -1], lw=STYLE.LW_THICK)
        STYLE.panel_title(a, "A", "left")
        STYLE.panel_title(b, "B", "right")
        a.text(0.5, 0.5, f"{STYLE.num(-0.5)} and 10-40 Hz", fontsize=STYLE.SMALL)
        a.legend(frameon=False)
        for failures in (_spine_failures, _line_width_failures, _text_size_failures,
                         _font_failures, _panel_letter_failures, _ascii_minus_failures,
                         _variable_failures):
            assert not failures(fig), (failures.__name__, failures(fig))
        assert not _palette_strays(fig, _rgb_hex(["#2d2d2d", "#8a8a8a"]) | {"#000000"}, "light")
        plt.close(fig)
        fig, ax = plt.subplots()
        ax.axvspan(0, 1, color=STYLE.HIGHLIGHT["dark"])
        assert _palette_strays(fig, set(), "light"), "the dark highlight passed on the light theme"
        assert not [s for s in _palette_strays(fig, set(), "dark") if "cfb87c" in s]
        plt.close(fig)
    with matplotlib.rc_context({"axes.unicode_minus": False}):
        fig, ax = plt.subplots()
        ax.plot([-2, -1], [-2, -1])
        _renderer(fig)
        held = {key: matplotlib.rcParams[key] for key in TICK_TEXT_RC}
    assert _ascii_minus_failures(fig, held), "ASCII-minus tick labels passed"
    assert not _ascii_minus_failures(fig), "a redraw under the defaults is not the drawn figure"
    plt.close(fig)
    assert _colour_literals('ax.plot(x, color="#7048e8")\nax.text(0, 0, "a", color="tab:blue")\n')
    assert not _colour_literals('THEMES = {"light": {"fg": "#2d2d2d"}}\nax.plot(x, color=style.SERIES[0])\n')
    literal = "import figure_style as style\nax.plot(x, lw=0.7)\nax.plot(x, lw=style.LW)\nax.fill(x, lw=0)\n"
    assert _width_literals(literal) == ["line 2: lw=0.7"]
    assert _ascii_minus_failures_in("(-3)") and not _ascii_minus_failures_in("0-7 and well-known")
    # The pair this check was written against: a red, a gold and a green at 13.5 to 15.1 apart.
    old = ["#d9534f", "#c3aa5f", "#2e7d32"]
    assert len(_cvd_failures(old, marks=old)) >= 2, "the old red, gold and green passed"
    assert not _cvd_failures(list(STYLE.SERIES))


def _ascii_minus_failures_in(text: str) -> list[str]:
    return [text] if ASCII_MINUS.search(text) else []
