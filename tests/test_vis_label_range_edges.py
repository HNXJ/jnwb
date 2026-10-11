"""
tests/test_vis_label_range_edges.py -- Label and range edges of the laminar and hierarchy panels.

- plot_csd: a colorbar title that names the declared unit, or is blank, is refused; the depth
  hover names depth_unit.
- plot_spectrolaminar_map: infinite values are refused, NaN stays a gap; an empty rel_power
  raises a named error.
- plot_hierarchy_regression: the hover adds no literal "%" to the value.
"""

import re

import numpy as np
import pytest

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

from jnwb.vis.canvas import PlotlyPublicationCanvas  # noqa: E402
from jnwb.vis.hierarchy import plot_hierarchy_regression  # noqa: E402
from jnwb.vis.laminar import plot_csd, plot_spectrolaminar_map  # noqa: E402


def _canvas():
    return PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)


def _csd_heatmap(value_unit="A/m³", depth_unit="mm", **kwargs):
    canvas = _canvas()
    plot_csd(canvas, 0, 0, csd_matrix=np.ones((3, 4)), time_ms=np.arange(4.0),
             depths=np.arange(3.0), value_unit=value_unit, depth_unit=depth_unit, **kwargs)
    (heatmap,) = [t for t in canvas.fig.data if isinstance(t, go.Heatmap)]
    return heatmap


def test_csd_colorbar_title_that_names_the_declared_unit_raises():
    """A full label such as "CSD (A/m³)" doubled the unit: the colorbar read "CSD (A/m³) (A/m³)"."""
    assert _csd_heatmap(colorbar_title="CSD").colorbar.title.text == "CSD (A/m³)"
    assert _csd_heatmap(value_unit="A", colorbar_title="Amplitude").colorbar.title.text == "Amplitude (A)"
    with pytest.raises(ValueError, match="colorbar_title"):
        _csd_heatmap(colorbar_title="CSD (A/m³)")
    with pytest.raises(ValueError, match="colorbar_title"):
        _csd_heatmap(value_unit="A", colorbar_title="CSD (A)")


def test_csd_colorbar_title_that_is_blank_raises():
    """A whitespace-only title was accepted and put leading spaces before the unit."""
    assert _csd_heatmap().colorbar.title.text == "A/m³"  # precondition: no title is accepted
    for blank in ("", "   "):
        with pytest.raises(ValueError, match="colorbar_title"):
            _csd_heatmap(colorbar_title=blank)


def test_csd_depth_hover_names_depth_unit():
    """The depth hover carried no unit; each depth_unit must appear after the depth value."""
    for unit in ("mm", "um", "relative"):
        hover = _csd_heatmap(depth_unit=unit).hovertemplate
        assert f"Depth: %{{y:.3f}} {unit}<br>" in hover


def test_spectrolaminar_map_refuses_infinite_values_and_keeps_nan_as_a_gap():
    """Infinite values were drawn as gaps; NaN is the gap, and infinities are outside the [0, 1] scale."""
    base = np.full((5, 4), 0.5)
    base[0, 0] = np.nan
    kwargs = dict(freqs=np.arange(1.0, 6.0), depths=np.linspace(0.0, 1.0, 4), depth_unit="relative")
    plot_spectrolaminar_map(_canvas(), 0, 0, rel_power=base, **kwargs)  # precondition: NaN alone is accepted
    for bad in (np.inf, -np.inf):
        rel_power = base.copy()
        rel_power[2, 1] = bad
        with pytest.raises(ValueError, match="rel_power"):
            plot_spectrolaminar_map(_canvas(), 0, 0, rel_power=rel_power, **kwargs)


def test_spectrolaminar_map_names_rel_power_when_it_is_empty():
    """An empty rel_power must raise a named error, not fail inside numpy."""
    for log_freq in (True, False):
        rel_power = np.empty((0, 0))
        assert rel_power.size == 0  # precondition: the fixture is empty
        with pytest.raises(ValueError, match="rel_power"):
            plot_spectrolaminar_map(_canvas(), 0, 0, rel_power=rel_power, freqs=np.empty(0),
                                    depths=np.empty(0), log_freq=log_freq, depth_unit="relative")


def test_hierarchy_hover_adds_no_literal_percent_to_the_value():
    """The hover once appended "%" to every value; y_label names the unit now, so the hover must not."""
    v = np.array([80.0, 95.0, 110.0])
    canvas = _canvas()
    plot_hierarchy_regression(canvas, 0, 0, hierarchy_ranks=np.arange(3), values=v,
                              ci_low=v - 5, ci_high=v + 5, area_labels=["a", "b", "c"],
                              y_label="Onset latency (ms)")
    (points,) = [t for t in canvas.fig.data if hasattr(t, "error_y") and t.error_y.visible]
    assert "Value: %{y:.2f}" in points.hovertemplate  # precondition: the value field is present
    literal = re.sub(r"%\{[^}]*\}", "", points.hovertemplate)  # drop plotly's %{...} fields
    assert "%" not in literal
