"""
tests/test_vis_shared_rules.py -- rules that more than one jnwb.vis panel relies on.

- Colorbar titles: ``plot_csd`` and ``plot_sorted_heatmap`` share one check. It refuses a blank
  title and a title that names ``value_unit``.
- Raster SEM ribbon: ``plot_multi_condition_raster_psth`` draws mean +/- 1.96 sample SEM across
  trials, pinned by a value worked out by hand.
- Crossover default: ``plot_opposing_gradients`` draws no crossover marker unless a depth is given.
- Exports: ``jnwb.vis.__all__`` is pinned as an exact list.
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

import jnwb.vis as vis  # noqa: E402
from jnwb.vis.canvas import PlotlyPublicationCanvas  # noqa: E402
from jnwb.vis.laminar import plot_csd, plot_opposing_gradients  # noqa: E402
from jnwb.vis.spiking import plot_multi_condition_raster_psth, plot_sorted_heatmap  # noqa: E402
from jnwb.vis.theme import COLORS  # noqa: E402

VIS_EXPORTS = [
    "PlotlyPublicationCanvas",
    "EpistemicArgumentObject",
    "serialize_argument_sidecar",
    "get_publication_layout_template",
    "configure_axis",
    "COLOR_PALETTES",
    "TOL_MUTED",
    "OKABE_ITO",
    "NATURE_ACCENTS",
    "canvas",
    "theme",
    "sidecar",
    "laminar",
    "spiking",
    "hierarchy",
    "spectral",
    "state_space",
    "wavemap",
    "plot_spectrolaminar_map",
    "plot_opposing_gradients",
    "plot_csd",
    "plot_multi_condition_raster_psth",
    "plot_sorted_heatmap",
    "plot_hierarchy_regression",
    "plot_spectral_modulation_matrix",
    "plot_granger_spectra",
    "plot_decoding_timecourse",
    "plot_rsm_heatmap",
    "plot_wavemap",
]


def _canvas(rows=1):
    return PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=rows, cols=1)


def _csd_panel(canvas, colorbar_title, value_unit="A/m³"):
    plot_csd(canvas, 0, 0, csd_matrix=np.ones((3, 4)), time_ms=np.arange(4.0),
             depths=np.arange(3.0), value_unit=value_unit, depth_unit="mm",
             colorbar_title=colorbar_title)


def _sorted_panel(canvas, colorbar_title, value_unit="A/m³"):
    plot_sorted_heatmap(canvas, 0, 0, np.ones((3, 4)), np.arange(4.0), value_unit=value_unit,
                        colorbar_title=colorbar_title)


COLORBAR_PANELS = [_csd_panel, _sorted_panel]
PANEL_IDS = ["plot_csd", "plot_sorted_heatmap"]


def _colorbar_text(canvas):
    (heatmap,) = [t for t in canvas.fig.data if isinstance(t, go.Heatmap)]
    return heatmap.colorbar.title.text


@pytest.mark.parametrize("panel", COLORBAR_PANELS, ids=PANEL_IDS)
def test_colorbar_title_names_the_quantity_and_the_unit_is_written_once(panel):
    canvas = _canvas()
    panel(canvas, "Rate")
    assert _colorbar_text(canvas) == "Rate (A/m³)"  # precondition: the quantity alone is accepted


@pytest.mark.parametrize("panel", COLORBAR_PANELS, ids=PANEL_IDS)
@pytest.mark.parametrize("title", ["CSD (A/m³)", "Rate in A/m³", "", "   "],
                         ids=["unit_csd", "unit_rate", "blank", "spaces"])
def test_colorbar_title_that_names_the_unit_or_is_blank_is_refused(panel, title):
    canvas = _canvas()
    with pytest.raises(ValueError, match="colorbar_title"):
        panel(canvas, title)
    assert len(canvas.fig.data) == 0  # refused before anything is drawn


@pytest.mark.parametrize("panel", COLORBAR_PANELS, ids=PANEL_IDS)
def test_z_score_is_a_quantity_under_unit_z_and_the_unit_z_is_still_refused(panel):
    """"z-score" names a z-scored quantity. Under value_unit "z" it was refused as the unit z;
    the unit z itself stays refused in every other form."""
    canvas = _canvas()
    panel(canvas, "z-score", value_unit="z")
    assert _colorbar_text(canvas) == "z-score (z)"  # precondition: the quantity is accepted
    for title in ("z", "Rate (z)", "z-score (z)"):
        with pytest.raises(ValueError, match="colorbar_title"):
            panel(_canvas(), title, value_unit="z")


def test_raster_psth_sem_ribbon_is_mean_plus_minus_1_96_sample_sem_by_hand():
    """Three trials with 1, 2 and 3 spikes in a 100 ms bin: rates 10, 20 and 30 Hz.

    By hand: the mean is 20. The squared deviations 100, 0 and 100 sum to 200. Dividing by
    n - 1 = 2 gives a sample variance of 100, so the sample SD is 10, and the SEM is 10 / sqrt(3),
    about 5.7735. The ribbon is mean +/- 1.96 SEM, so its upper edge is about 31.316. A ddof=0
    SEM gives an upper edge of about 29.24; a SEM with no division by sqrt(n) gives 39.6.
    """
    st = np.array([0.05, 1.02, 1.07, 2.01, 2.04, 2.09])
    onsets = np.array([0.0, 1.0, 2.0])
    spikes = [int(np.sum((st >= t0) & (st < t0 + 0.1))) for t0 in onsets]
    assert spikes == [1, 2, 3], "fixture must place 1, 2 and 3 spikes in the three bins"

    canvas = _canvas(rows=2)
    plot_multi_condition_raster_psth(canvas, 0, 0, 1, 0, st, {"trials": onsets},
                                     win_ms=(0.0, 100.0), bin_ms=100.0)
    traces = list(canvas.fig.data)
    ribbon_at = [k for k, t in enumerate(traces) if getattr(t, "fill", None) == "tonexty"]
    assert len(ribbon_at) == 1, "fixture must draw exactly one ribbon"  # precondition

    rates = [count / 0.1 for count in spikes]
    n = len(rates)
    mean = sum(rates) / n
    sample_sd = math.sqrt(sum((r - mean) ** 2 for r in rates) / (n - 1))
    sem = sample_sd / math.sqrt(n)
    assert mean == pytest.approx(20.0, rel=1e-12)
    assert sem == pytest.approx(10 / math.sqrt(3), rel=1e-12)

    upper = traces[ribbon_at[0]]
    lower = traces[ribbon_at[0] - 1]
    assert np.allclose(upper.y, mean + 1.96 * sem, rtol=1e-12)
    assert np.allclose(lower.y, max(0.0, mean - 1.96 * sem), rtol=1e-12)


def _opposing_crossover_traces(**kwargs):
    canvas = _canvas()
    depths = np.linspace(0.0, 1.0, 20)
    plot_opposing_gradients(canvas, 0, 0, gamma_power=1.0 - depths, alphabeta_power=depths,
                            depths=depths, depth_unit="relative", **kwargs)
    return [t for t in canvas.fig.data
            if t.line.dash == "dash" and t.line.color == COLORS["crossover"]]


def test_opposing_gradients_crossover_default_is_none():
    """No crossover depth is assumed: the default is None, and None draws no marker."""
    default = inspect.signature(plot_opposing_gradients).parameters["crossover_depth"].default
    assert default is None


def test_opposing_gradients_draws_a_crossover_marker_only_when_a_depth_is_given():
    assert len(_opposing_crossover_traces(crossover_depth=0.4)) == 1  # precondition: a given depth is drawn
    assert _opposing_crossover_traces() == []


def test_jnwb_vis_exports_are_pinned_as_an_exact_list():
    """A name removed from or added to the export list must change this test too."""
    assert sorted(vis.__all__) == sorted(VIS_EXPORTS), (
        f"added={sorted(set(vis.__all__) - set(VIS_EXPORTS))}, "
        f"removed={sorted(set(VIS_EXPORTS) - set(vis.__all__))}"
    )
    assert len(vis.__all__) == len(set(vis.__all__)), "an export is listed twice"
    for name in vis.__all__:
        assert hasattr(vis, name), f"{name} is in __all__ but not bound on jnwb.vis"
