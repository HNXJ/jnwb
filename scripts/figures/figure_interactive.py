"""The Interactive tab of a documentation figure: the artists the figure drew, as one Plotly figure.

`convert` walks a matplotlib figure and maps each panel's lines, markers, collections, heatmaps,
rectangles, reference lines and text to Plotly, on the panel positions the figure drew. A panel
with any other artist is named as unconvertible, and a figure with one gets no HTML: its
Interactive tab shows the still. The styling is the publication template of `jnwb.vis`.

`n_points` counts the finite values of the line, marker and fill traces; heatmap cells are not
counted.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import plotly.graph_objects as go
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection, PathCollection, PolyCollection, QuadMesh
from matplotlib.colors import to_rgba
from matplotlib.contour import QuadContourSet
from matplotlib.image import AxesImage
from matplotlib.patches import Rectangle

from jnwb.vis.theme import get_publication_layout_template

#: Plotly sizes are in pixels: 100 per inch of the figure, 4/3 per matplotlib point.
PX_PER_INCH = 100
PX_PER_PT = 4.0 / 3.0
DASH = {"-": "solid", "--": "dash", ":": "dot", "-.": "dashdot"}
MARKER = {"o": "circle", "s": "square", "^": "triangle-up", "v": "triangle-down",
          "D": "diamond", "x": "x", "+": "cross"}
NO_LINE = ("None", "", " ", None)
NO_MARKER = (None, "", "None", "none", " ")
DIV_ID = "jnwb-figure"
#: The ink of each palette, as the still draws it, and the grid of each.
INK = {"light": "#2d2d2d", "dark": "#e0e0e0"}
GRID = {"light": "rgba(138,138,138,0.35)", "dark": "rgba(112,112,112,0.35)"}


class Unconvertible(Exception):
    """An artist the converter cannot draw; the message names it."""


@dataclass
class Converted:
    figure: Optional[go.Figure]
    reasons: List[str] = field(default_factory=list)
    n_points: int = 0
    height_px: int = 0


def _css(color: Any, alpha: Optional[float] = None) -> str:
    red, green, blue, opacity = to_rgba(color)
    if alpha is not None:
        opacity = alpha
    return f"rgba({round(red * 255)},{round(green * 255)},{round(blue * 255)},{opacity:.3f})"


def _colorscale(cmap) -> List[List[Any]]:
    return [[float(t), _css(cmap(float(t)))] for t in np.linspace(0.0, 1.0, 9)]


def _numeric(values) -> np.ndarray:
    try:
        return np.ma.filled(np.ma.asarray(values, dtype=float), np.nan).astype(float)
    except (TypeError, ValueError) as error:
        raise Unconvertible("non-numeric data") from error


def _finite(values: np.ndarray) -> int:
    return int(np.count_nonzero(np.isfinite(values)))


def _heatmap(x, y, z, cmap, clim, xa: str, ya: str) -> go.Heatmap:
    low, high = clim
    if low is None or high is None:
        low, high = float(np.nanmin(z)), float(np.nanmax(z))
    return go.Heatmap(x=x, y=y, z=z, colorscale=_colorscale(cmap), zmin=low, zmax=high,
                      showscale=True, xaxis=xa, yaxis=ya)


def _add_line(ax, line, xa: str, ya: str, traces: list, shapes: list) -> int:
    style, marker = line.get_linestyle(), line.get_marker()
    has_marker = marker not in NO_MARKER
    has_line = style not in NO_LINE
    if not has_line and not has_marker:
        return 0
    x, y = _numeric(line.get_xdata()), _numeric(line.get_ydata())
    if x.shape != y.shape:
        raise Unconvertible("line with unequal x and y")
    if line.get_transform() is not ax.transData:
        return _reference_line(x, y, xa, ya, line, shapes)
    if has_line and style not in DASH:
        raise Unconvertible(f"line style {style}")
    if has_marker and marker not in MARKER:
        raise Unconvertible(f"marker {marker}")
    label = line.get_label()
    name = label if label and not label.startswith("_") else None
    mode = "lines+markers" if has_line and has_marker else ("lines" if has_line else "markers")
    traces.append(go.Scatter(
        x=x, y=y, mode=mode, name=name or "", showlegend=name is not None, xaxis=xa, yaxis=ya,
        line=dict(color=_css(line.get_color()), width=float(line.get_linewidth()) * PX_PER_PT,
                  dash=DASH.get(style, "solid")),
        marker=dict(symbol=MARKER.get(marker, "circle"), color=_css(line.get_markerfacecolor()),
                    size=float(line.get_markersize()) * PX_PER_PT)))
    return _finite(x) if has_line or has_marker else 0


def _reference_line(x, y, xa: str, ya: str, line, shapes: list) -> int:
    """An axhline or axvline: one end in axes coordinates, the other in data."""
    color = _css(line.get_color())
    width = float(line.get_linewidth()) * PX_PER_PT
    if np.allclose(x, [0.0, 1.0]) and np.allclose(y, y[0]):
        shapes.append(dict(type="line", xref=f"{xa} domain", x0=0.0, x1=1.0, yref=ya,
                           y0=float(y[0]), y1=float(y[0]), line=dict(color=color, width=width)))
    elif np.allclose(y, [0.0, 1.0]) and np.allclose(x, x[0]):
        shapes.append(dict(type="line", xref=xa, x0=float(x[0]), x1=float(x[0]), yref=f"{ya} domain",
                           y0=0.0, y1=1.0, line=dict(color=color, width=width)))
    else:
        raise Unconvertible("line in axes coordinates")
    return 0


def _add_collection(ax, coll, xa: str, ya: str, traces: list) -> int:
    if isinstance(coll, QuadContourSet):
        raise Unconvertible("contour set")
    # A scatter's offsets are the data; every other collection's paths or coordinates are.
    in_data = (coll.get_offset_transform() if isinstance(coll, PathCollection)
               else coll.get_transform())
    if in_data is not ax.transData:
        raise Unconvertible("collection in axes coordinates")
    if isinstance(coll, QuadMesh):
        coords = np.asarray(coll.get_coordinates(), dtype=float)
        ny, nx = coords.shape[0] - 1, coords.shape[1] - 1
        x = (coords[0, :-1, 0] + coords[0, 1:, 0]) / 2
        y = (coords[:-1, 0, 1] + coords[1:, 0, 1]) / 2
        z = _numeric(coll.get_array()).reshape(ny, nx)
        traces.append(_heatmap(x, y, z, coll.get_cmap(), coll.get_clim(), xa, ya))
        return 0
    if isinstance(coll, LineCollection):
        colours = coll.get_colors()
        if len(colours) and any(not np.allclose(c, colours[0]) for c in colours):
            raise Unconvertible("line collection with several colours")
        xs: List[Optional[float]] = []
        ys: List[Optional[float]] = []
        for segment in coll.get_segments():
            segment = np.asarray(segment, dtype=float)
            xs.extend(segment[:, 0].tolist() + [None])
            ys.extend(segment[:, 1].tolist() + [None])
        widths = coll.get_linewidths()
        traces.append(go.Scatter(
            x=xs, y=ys, mode="lines", showlegend=False, xaxis=xa, yaxis=ya,
            line=dict(color=_css(colours[0]) if len(colours) else "rgba(0,0,0,1)",
                      width=float(widths[0]) * PX_PER_PT if len(widths) else 1.0 * PX_PER_PT)))
        return sum(1 for value in xs if value is not None)
    if isinstance(coll, PolyCollection):
        faces = coll.get_facecolor()
        count = 0
        for index, path in enumerate(coll.get_paths()):
            vertices = np.asarray(path.vertices, dtype=float)
            face = faces[min(index, len(faces) - 1)] if len(faces) else (0.0, 0.0, 0.0, 0.0)
            traces.append(go.Scatter(
                x=vertices[:, 0], y=vertices[:, 1], mode="lines", fill="toself", showlegend=False,
                hoverinfo="skip", xaxis=xa, yaxis=ya, fillcolor=_css(face), line=dict(width=0)))
            count += _finite(vertices[:, 0])
        return count
    if isinstance(coll, PathCollection):
        offsets = np.asarray(coll.get_offsets(), dtype=float)
        if offsets.size == 0:
            return 0
        faces = coll.get_facecolor()
        if len(faces) not in (1, len(offsets)):
            raise Unconvertible("scatter colours")
        sizes = np.sqrt(np.asarray(coll.get_sizes(), dtype=float)) * PX_PER_PT
        if len(sizes) not in (1, len(offsets)):
            raise Unconvertible("scatter sizes")
        traces.append(go.Scatter(
            x=offsets[:, 0], y=offsets[:, 1], mode="markers", showlegend=False, xaxis=xa, yaxis=ya,
            marker=dict(color=_css(faces[0]) if len(faces) == 1 else [_css(c) for c in faces],
                        size=float(sizes[0]) if len(sizes) == 1 else sizes.tolist())))
        return _finite(offsets[:, 0])
    raise Unconvertible(f"collection {type(coll).__name__}")


def _add_image(ax, image, xa: str, ya: str, traces: list) -> None:
    if not isinstance(image, AxesImage):
        raise Unconvertible(f"image {type(image).__name__}")
    if image.get_transform() is not ax.transData:
        raise Unconvertible("image in axes coordinates")
    array = _numeric(image.get_array())
    if array.ndim != 2:
        raise Unconvertible("RGB image")
    left, right, bottom, top = image.get_extent()
    ny, nx = array.shape
    x = left + (np.arange(nx) + 0.5) * (right - left) / nx
    if image.origin == "upper":
        y = top + (np.arange(ny) + 0.5) * (bottom - top) / ny
    else:
        y = bottom + (np.arange(ny) + 0.5) * (top - bottom) / ny
    traces.append(_heatmap(x, y, array, image.get_cmap(), image.get_clim(), xa, ya))


def _same_axis(transform, reference, axis: int) -> bool:
    """Whether `transform` maps one axis as `reference` does, checked at two probe points."""
    probes = np.array([[0.123, 0.456], [7.5, 3.25]])
    return bool(np.allclose(transform.transform(probes)[:, axis],
                            reference.transform(probes)[:, axis], atol=1e-6))


def _rectangle(ax, patch, xa: str, ya: str) -> Dict[str, Any]:
    if not isinstance(patch, Rectangle):
        raise Unconvertible(f"patch {type(patch).__name__}")
    transform = patch.get_data_transform()
    if transform is ax.transData:
        xref, yref = xa, ya
    else:
        # A band from axvspan or axhspan: one axis in data, the other in axes fractions.
        x_data, y_data = _same_axis(transform, ax.transData, 0), _same_axis(transform, ax.transData, 1)
        x_axes, y_axes = _same_axis(transform, ax.transAxes, 0), _same_axis(transform, ax.transAxes, 1)
        if not ((x_data and y_axes) or (x_axes and y_data)):
            raise Unconvertible("patch in axes coordinates")
        xref = xa if x_data else f"{xa} domain"
        yref = ya if y_data else f"{ya} domain"
    x0, y0 = patch.get_xy()
    face = to_rgba(patch.get_facecolor())[3] * (patch.get_alpha() if patch.get_alpha() is not None else 1.0)
    return dict(type="rect", xref=xref, yref=yref, x0=float(x0), x1=float(x0 + patch.get_width()),
                y0=float(y0), y1=float(y0 + patch.get_height()), layer="below",
                fillcolor=_css(patch.get_facecolor(), face),
                line=dict(width=float(patch.get_linewidth()) * PX_PER_PT,
                          color=_css(patch.get_edgecolor())))


def _annotation(ax, text, renderer, xa: str, ya: str) -> Dict[str, Any]:
    if getattr(text, "arrow_patch", None) is not None:
        raise Unconvertible("annotation with an arrow")
    box = text.get_window_extent(renderer)
    ha, va = text.get_horizontalalignment(), text.get_verticalalignment()
    px = {"left": box.x0, "right": box.x1}.get(ha, (box.x0 + box.x1) / 2)
    py = {"top": box.y1, "bottom": box.y0, "baseline": box.y0}.get(va, (box.y0 + box.y1) / 2)
    fx, fy = ax.transAxes.inverted().transform((px, py))
    return dict(text=text.get_text(), x=float(fx), y=float(fy), xref=f"{xa} domain",
                yref=f"{ya} domain", showarrow=False, textangle=float(text.get_rotation()),
                xanchor={"left": "left", "right": "right"}.get(ha, "center"),
                yanchor={"top": "top", "bottom": "bottom", "baseline": "bottom"}.get(va, "middle"),
                font=dict(size=round(text.get_fontsize() * PX_PER_PT, 1),
                          color=_css(text.get_color())))


def _tick_text(axis_values, labels: List[str]) -> Optional[Dict[str, Any]]:
    """Custom ticks when a tick label is not a number, as a categorical axis's labels are."""
    if len(labels) != len(axis_values) or not labels:
        return None
    for label in labels:
        try:
            float(label.replace("−", "-"))
        except ValueError:
            return dict(tickmode="array", tickvals=[float(v) for v in axis_values],
                        ticktext=labels)
    return None


def _axis(ax, which: str, span: List[float], anchor: str, domain: List[float], label: str,
          ticks: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    log = (ax.get_xscale() if which == "x" else ax.get_yscale()) == "log"
    values = [math.log10(v) if log else v for v in span]
    settings = dict(domain=domain, anchor=anchor, range=values, type="log" if log else "linear",
                    title=dict(text=label), showgrid=False, zeroline=False, showline=True)
    settings.update(ticks or {})
    return settings


def _panel(ax, number: int, renderer, shapes: list, annotations: list) -> Dict[str, Any]:
    suffix = "" if number == 1 else str(number)
    xa, ya = f"x{suffix}", f"y{suffix}"
    if ax.child_axes:
        raise Unconvertible("inset axes")
    for scale in (ax.get_xscale(), ax.get_yscale()):
        if scale not in ("linear", "log"):
            raise Unconvertible(f"{scale} scale")
    traces: list = []
    count = 0
    for line in ax.lines:
        count += _add_line(ax, line, xa, ya, traces, shapes)
    for coll in ax.collections:
        count += _add_collection(ax, coll, xa, ya, traces)
    for image in ax.images:
        _add_image(ax, image, xa, ya, traces)
    for patch in ax.patches:
        shapes.append(_rectangle(ax, patch, xa, ya))
    titles = [ax.title, getattr(ax, "_left_title", None), getattr(ax, "_right_title", None)]
    for text in [t for t in [*titles, *ax.texts] if t is not None and t.get_visible() and t.get_text()]:
        annotations.append(_annotation(ax, text, renderer, xa, ya))
    box = ax.get_position()
    x_ticks = _tick_text(ax.get_xticks(), [t.get_text() for t in ax.get_xticklabels()])
    y_ticks = _tick_text(ax.get_yticks(), [t.get_text() for t in ax.get_yticklabels()])
    axes = {
        f"xaxis{suffix}": _axis(ax, "x", list(ax.get_xlim()), ya, [box.x0, box.x1],
                                ax.get_xlabel(), x_ticks),
        f"yaxis{suffix}": _axis(ax, "y", list(ax.get_ylim()), xa, [box.y0, box.y1],
                                ax.get_ylabel(), y_ticks),
    }
    return dict(traces=traces, count=count, axes=axes)


def _template(scheme: str):
    template = copy.deepcopy(get_publication_layout_template())
    ink = INK[scheme]
    template.layout.paper_bgcolor = "rgba(0,0,0,0)"
    template.layout.plot_bgcolor = "rgba(0,0,0,0)"
    template.layout.font.color = ink
    for axis in (template.layout.xaxis, template.layout.yaxis):
        axis.linecolor = ink
        axis.tickcolor = ink
        axis.gridcolor = GRID[scheme]
    return template


def convert(fig) -> Converted:
    """The figure as one Plotly figure, or the reasons it has none."""
    # An Agg canvas of its own: a figure built outside pyplot, or closed by it, holds a
    # FigureCanvasBase, which cannot render.
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    renderer = canvas.get_renderer()
    height_px = round(fig.get_figheight() * PX_PER_INCH)
    width_px = round(fig.get_figwidth() * PX_PER_INCH)
    reasons: List[str] = []
    if fig.legends or fig.texts:
        reasons.append("figure: a figure-level legend or text")
    shapes: List[Dict[str, Any]] = []
    annotations: List[Dict[str, Any]] = []
    traces: list = []
    layout: Dict[str, Any] = {}
    count = 0
    panels = [ax for ax in fig.axes if ax.get_label() != "<colorbar>"]
    for number, ax in enumerate(panels, 1):
        try:
            panel = _panel(ax, number, renderer, shapes, annotations)
        except Unconvertible as error:
            reasons.append(f"panel {number}: {error}")
            continue
        traces.extend(panel["traces"])
        layout.update(panel["axes"])
        count += panel["count"]
    if reasons:
        return Converted(None, reasons, count, height_px)
    figure = go.Figure(data=traces)
    figure.update_layout(**layout, shapes=shapes, annotations=annotations, width=width_px,
                         height=height_px, margin=dict(l=60, r=30, t=30, b=50),
                         template=_template("light"))
    return Converted(figure, [], count, height_px)


#: Switches the figure's template when the page posts its palette; the default is light.
SWITCH = """(function () {
  var LIGHT = __LIGHT__;
  var DARK = __DARK__;
  var figure = document.getElementById("%s");
  window.addEventListener("message", function (event) {
    if (event.source !== window.parent || !event.data || event.data.type !== "jnwb-scheme") {
      return;
    }
    var template = event.data.scheme === "dark" ? DARK : LIGHT;
    Plotly.react(figure, figure.data, Object.assign({}, figure.layout, {template: template}));
  });
})();
""" % DIV_ID


def to_html(converted: Converted) -> str:
    if converted.figure is None:
        raise ValueError("a figure with an unconvertible panel has no interactive HTML")
    html = converted.figure.to_html(full_html=True, include_plotlyjs="cdn", div_id=DIV_ID,
                                    config={"displaylogo": False, "responsive": True})
    script = (SWITCH.replace("__LIGHT__", json.dumps(_template("light").to_plotly_json()))
              .replace("__DARK__", json.dumps(_template("dark").to_plotly_json())))
    return html.replace("</body>", f"<script>\n{script}</script>\n</body>")
