"""A documentation figure's Interactive tab shows its panels as Plotly, or names the panel it cannot draw.

The converter takes the artists a figure drew and returns one Plotly figure. A planted figure built
from the artist kinds it supports converts with no reasons; a planted contour panel is named, and
its figure is not converted. The registry test checks the named panels of the real figures.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = REPO_ROOT / "scripts" / "figures"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, FIGURE_SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # a dataclass looks its module up while it loads
    spec.loader.exec_module(module)
    return module


interactive = _load("figure_interactive")


def _supported_figure():
    fig, (ax1, ax2) = plt.subplots(1, 2)
    ax1.plot([0.0, 1.0, 2.0], [0.0, 1.0, 4.0], color="#1565c0", label="curve")
    ax1.scatter([0.5, 1.5], [1.0, 2.0], color="#ff9800")
    ax1.add_patch(Rectangle((0.6, 0.0), 0.2, 3.0, facecolor="#cfb87c", alpha=0.5))
    ax1.text(0.05, 0.9, "A", transform=ax1.transAxes, fontweight="bold")
    ax2.imshow(np.arange(12.0).reshape(3, 4), origin="upper", extent=(0.0, 4.0, 0.0, 3.0))
    ax2.set_title("Heat")
    ax2.set_xlabel("time (ms)")
    return fig


def test_a_figure_of_supported_artists_converts_with_no_reasons():
    result = interactive.convert(_supported_figure())
    plt.close("all")
    assert result.reasons == [], result.reasons
    kinds = sorted(type(trace).__name__ for trace in result.figure.data)
    assert kinds == ["Heatmap", "Scatter", "Scatter"], kinds
    assert len(result.figure.layout.shapes) == 1
    assert result.n_points == 5, result.n_points


def test_a_figure_without_a_drawing_canvas_converts():
    """A figure built outside pyplot, or closed by it, holds a canvas that cannot render."""
    from matplotlib.backend_bases import FigureCanvasBase
    from matplotlib.figure import Figure

    fig = Figure()
    fig.add_subplot().plot([0.0, 1.0], [0.0, 1.0])
    assert type(fig.canvas) is FigureCanvasBase, "the fixture must hold a canvas that cannot render"
    result = interactive.convert(fig)
    assert result.reasons == [] and len(result.figure.data) == 1


def test_a_contour_panel_is_named_and_the_figure_is_not_converted():
    fig, ax = plt.subplots()
    ax.contour(np.arange(9.0).reshape(3, 3))
    result = interactive.convert(fig)
    plt.close("all")
    assert result.figure is None
    assert result.reasons == ["panel 1: contour set"], result.reasons


def test_an_axvspan_band_converts_as_a_shape_with_its_height_in_axes_fractions():
    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], [0.0, 1.0, 0.0])
    ax.axvspan(0.5, 1.5, color="#cfb87c", alpha=0.5)
    result = interactive.convert(fig)
    plt.close("all")
    assert result.reasons == [], result.reasons
    (band,) = result.figure.layout.shapes
    assert (band.xref, band.yref) == ("x", "y domain"), (band.xref, band.yref)
    assert (band.x0, band.x1, band.y0, band.y1) == (0.5, 1.5, 0.0, 1.0)


def test_a_band_drawn_as_a_rectangular_polygon_converts_as_a_shape():
    """Matplotlib before 3.9 returns axvspan's band as a Polygon of its five corners."""
    from matplotlib.patches import Polygon

    fig, ax = plt.subplots()
    ax.plot([0.0, 1.0, 2.0], [0.0, 1.0, 0.0])
    corners = [(0.5, 0.0), (0.5, 1.0), (1.5, 1.0), (1.5, 0.0), (0.5, 0.0)]
    ax.add_patch(Polygon(corners, transform=ax.get_xaxis_transform(), color="#cfb87c"))
    triangle = Polygon([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0)], color="#cfb87c")
    result = interactive.convert(fig)
    ax.add_patch(triangle)
    refused = interactive.convert(fig)
    plt.close("all")
    assert result.reasons == [], result.reasons
    (band,) = result.figure.layout.shapes
    assert (band.xref, band.yref) == ("x", "y domain"), (band.xref, band.yref)
    assert (band.x0, band.x1, band.y0, band.y1) == (0.5, 1.5, 0.0, 1.0)
    assert refused.reasons == ["panel 1: patch Polygon"], refused.reasons


def test_an_annotation_with_an_arrow_is_named():
    fig, ax = plt.subplots()
    ax.annotate("peak", xy=(1.0, 1.0), xytext=(0.2, 0.8), arrowprops=dict(arrowstyle="->"))
    result = interactive.convert(fig)
    plt.close("all")
    assert result.figure is None
    assert result.reasons == ["panel 1: annotation with an arrow"], result.reasons
