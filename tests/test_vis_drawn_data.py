"""
tests/test_vis_drawn_data.py -- jnwb.vis panels that dropped or misdrew data, or accepted data unlike their axes.

- A depth marker outside the depth range warns, naming the value, the range and a likely unit
  mismatch, and draws nothing; the drawing is otherwise unchanged.
- plot_hierarchy_regression: a NaN point leaves the fit with a warning; an interval that does not
  bracket its value is drawn from its own bounds; the statistic note sits above the drawn data;
  a fractional rank keeps its value in the tick label.
- plot_sorted_heatmap refuses a time axis of the wrong length; plot_multi_condition_raster_psth
  refuses more conditions than default colours instead of reusing one.
- plot_spectral_modulation_matrix takes its colour range from finite values only.
- Granger spectra, the RSM heatmap, the opposing-gradient intervals and the modulation significance
  mask refuse shapes that do not match their axes.
- An empty SOURCE ARTIFACTS entry is refused.
"""

import warnings

import numpy as np
import pytest

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

from jnwb.vis.canvas import PlotlyPublicationCanvas  # noqa: E402
from jnwb.vis.hierarchy import plot_hierarchy_regression  # noqa: E402
from jnwb.vis.laminar import plot_csd, plot_opposing_gradients, plot_spectrolaminar_map  # noqa: E402
from jnwb.vis.sidecar import EpistemicArgumentObject  # noqa: E402
from jnwb.vis.spectral import plot_granger_spectra, plot_spectral_modulation_matrix  # noqa: E402
from jnwb.vis.spiking import plot_multi_condition_raster_psth, plot_sorted_heatmap  # noqa: E402
from jnwb.vis.state_space import plot_rsm_heatmap  # noqa: E402


def _canvas(rows=1):
    return PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=rows, cols=1)


def _user_warnings(draw):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        draw()
    return [str(w.message) for w in caught if issubclass(w.category, UserWarning)]


def _traces(canvas, kind):
    return [t for t in canvas.fig.data if isinstance(t, kind)]


def _rank_ticks(ranks):
    canvas = _canvas()
    v = np.array([1.0, 2.0, 3.0])
    plot_hierarchy_regression(canvas, 0, 0, hierarchy_ranks=ranks, values=v, ci_low=v - 0.5,
                              ci_high=v + 0.5, area_labels=list("abc"), y_label="y")
    return list(canvas.fig.layout.xaxis.ticktext)


def test_crossover_outside_the_depth_range_warns_and_is_not_drawn():
    """A crossover in micrometres on millimetre depths was dropped with no word."""
    depths = np.linspace(0.0, 3.0, 4)
    freqs = np.arange(1.0, 6.0)
    rel_power = np.full((5, 4), 0.5)

    inside = _canvas()
    assert _user_warnings(lambda: plot_spectrolaminar_map(
        inside, 0, 0, rel_power=rel_power, freqs=freqs, depths=depths, crossover_depth=1.5,
        depth_unit="mm")) == []
    assert len(inside.fig.data) == 2  # precondition: an in-range crossover is drawn, with no warning

    outside = _canvas()
    messages = _user_warnings(lambda: plot_spectrolaminar_map(
        outside, 0, 0, rel_power=rel_power, freqs=freqs, depths=depths, crossover_depth=1200.0,
        depth_unit="mm"))
    assert len(messages) == 1, messages
    assert "1200" in messages[0] and "[0, 3]" in messages[0] and "unit" in messages[0]
    assert len(outside.fig.data) == 1, "only the heatmap is drawn; the crossover line is not"


def test_opposing_gradient_crossover_outside_the_depth_range_warns_and_is_not_drawn():
    depths = np.linspace(0.0, 3.0, 4)
    ones = np.ones(4)

    inside = _canvas()
    assert _user_warnings(lambda: plot_opposing_gradients(
        inside, 0, 0, gamma_power=ones, alphabeta_power=ones, depths=depths, crossover_depth=1.5,
        depth_unit="mm")) == []
    assert len(inside.fig.data) == 3  # precondition: an in-range crossover is drawn, with no warning

    outside = _canvas()
    messages = _user_warnings(lambda: plot_opposing_gradients(
        outside, 0, 0, gamma_power=ones, alphabeta_power=ones, depths=depths, crossover_depth=1200.0,
        depth_unit="mm"))
    assert len(messages) == 1, messages
    assert "1200" in messages[0] and "[0, 3]" in messages[0] and "unit" in messages[0]
    assert len(outside.fig.data) == 2, "the two profiles only; the crossover line is not drawn"


def test_csd_layer_boundary_outside_the_depth_range_warns_and_is_not_drawn():
    depths = np.array([0.0, 1.5, 3.0])
    csd = np.ones((3, 4))
    time_ms = np.arange(4.0)  # the zero-time line is drawn in both cases

    inside = _canvas()
    assert _user_warnings(lambda: plot_csd(
        inside, 0, 0, csd_matrix=csd, time_ms=time_ms, depths=depths,
        layer_boundaries={"L4": 1.5}, value_unit="A/m3", depth_unit="mm")) == []
    assert len(inside.fig.data) == 3  # precondition: heatmap, zero-time line and the in-range boundary

    outside = _canvas()
    messages = _user_warnings(lambda: plot_csd(
        outside, 0, 0, csd_matrix=csd, time_ms=time_ms, depths=depths,
        layer_boundaries={"L4": 1200.0}, value_unit="A/m3", depth_unit="mm"))
    assert len(messages) == 1, messages
    assert "L4" in messages[0] and "1200" in messages[0] and "[0, 3]" in messages[0]
    assert len(outside.fig.data) == 2, "heatmap and zero-time line only; the boundary is not drawn"


def test_hierarchy_fit_leaves_out_a_nan_point_and_says_how_many():
    """One NaN gave a NaN fit line with no warning."""
    ranks = np.arange(4.0)
    values = np.array([1.0, 2.0, 3.0, 4.0])
    clean = _canvas()
    assert _user_warnings(lambda: plot_hierarchy_regression(
        clean, 0, 0, hierarchy_ranks=ranks, values=values, ci_low=values - 0.5,
        ci_high=values + 0.5, area_labels=list("abcd"), y_label="y")) == []  # precondition

    nan_values = values.copy()
    nan_values[1] = np.nan
    canvas = _canvas()
    messages = _user_warnings(lambda: plot_hierarchy_regression(
        canvas, 0, 0, hierarchy_ranks=ranks, values=nan_values, ci_low=nan_values - 0.5,
        ci_high=nan_values + 0.5, area_labels=list("abcd"), y_label="y"))
    assert len(messages) == 1 and "1 point" in messages[0], messages
    (fit,) = [t for t in canvas.fig.data if t.name == "Linear Fit"]
    assert np.all(np.isfinite(fit.y))
    expected = np.polyval(np.polyfit(ranks[[0, 2, 3]], values[[0, 2, 3]], 1), fit.x)
    np.testing.assert_allclose(fit.y, expected, rtol=1e-12)


def test_interval_that_does_not_bracket_its_value_is_drawn_from_its_own_bounds():
    """A negative error-bar length was drawn for an interval whose lower bound lies above its value."""
    ranks = np.arange(4.0)
    values = np.array([2.0, 2.0, 3.0, 4.0])
    clean = _canvas()
    assert _user_warnings(lambda: plot_hierarchy_regression(
        clean, 0, 0, hierarchy_ranks=ranks, values=values, ci_low=values - 1.0,
        ci_high=values + 1.0, area_labels=list("abcd"), y_label="y")) == []  # precondition

    # Index 1: the value 2.0 lies below its lower bound 2.5.
    ci_low = np.array([1.0, 2.5, 2.5, 3.0])
    ci_high = np.array([3.0, 3.0, 3.5, 5.0])
    canvas = _canvas()
    messages = _user_warnings(lambda: plot_hierarchy_regression(
        canvas, 0, 0, hierarchy_ranks=ranks, values=values, ci_low=ci_low, ci_high=ci_high,
        area_labels=list("abcd"), y_label="y"))
    assert len(messages) == 1 and "[1]" in messages[0], messages

    (points,) = [t for t in canvas.fig.data if getattr(t, "error_y", None) is not None and t.error_y.visible]
    assert np.all(np.asarray(points.error_y.array) >= 0)
    assert np.all(np.asarray(points.error_y.arrayminus) >= 0)

    segments = [t for t in canvas.fig.data if getattr(t, "mode", None) == "lines"
                and getattr(t, "name", None) is None and t.y is not None and 2.5 in t.y]
    assert len(segments) == 1, "the interval is drawn as its own segment"
    assert tuple(segments[0].x[:2]) == (1.0, 1.0)
    assert tuple(segments[0].y[:2]) == (2.5, 3.0)


def test_statistic_note_sits_above_the_drawn_data_even_when_every_interval_is_negative():
    """With every ci_high negative the note moved below the data, because max * 1.05 is lower."""
    def note_y(values, ci_low, ci_high):
        canvas = _canvas()
        plot_hierarchy_regression(canvas, 0, 0, hierarchy_ranks=np.arange(len(values), dtype=float),
                                  values=values, ci_low=ci_low, ci_high=ci_high,
                                  area_labels=list("abc")[:len(values)], r_squared=0.5, y_label="y")
        (note,) = [a for a in canvas.fig.layout.annotations if "R²" in (a.text or "")]
        return note.y

    positive = np.array([1.0, 2.0, 3.0, 4.0])
    assert note_y(positive, positive - 0.5, positive + 0.5) == pytest.approx(1.05 * 4.5)  # precondition

    negative = np.array([-3.0, -2.0, -1.0])
    assert note_y(negative, negative - 1.0, np.array([-2.0, -1.0, -0.5])) > -0.5


def test_fractional_rank_keeps_its_value_in_the_tick_label():
    """int() labelled rank 0.5 as '0'."""
    assert _rank_ticks(np.arange(3.0)) == ["0", "1", "2"]  # precondition: whole ranks read as before
    assert _rank_ticks(np.array([0.5, 1.5, 2.5])) == ["0.5", "1.5", "2.5"]


def test_sorted_heatmap_refuses_a_time_axis_of_the_wrong_length():
    rate = np.ones((3, 4))
    plot_sorted_heatmap(_canvas(), 0, 0, rate, np.arange(4.0), value_unit="z")  # precondition
    refused = _canvas()
    with pytest.raises(ValueError, match=r"time_ms has 5 time points.*\(3, 4\)"):
        plot_sorted_heatmap(refused, 0, 0, rate, np.arange(5.0), value_unit="z")
    assert len(refused.fig.data) == 0, "a refused time axis must draw nothing"


def test_raster_psth_refuses_more_conditions_than_default_colours_instead_of_reusing_one():
    st = np.linspace(0.5, 3.0, 40)
    five = {f"c{i}": np.array([1.0 + 0.1 * i]) for i in range(5)}
    canvas = _canvas(rows=2)
    plot_multi_condition_raster_psth(canvas, 0, 0, 1, 0, st, five)  # precondition: five conditions
    colours = {t.name: t.line.color for t in canvas.fig.data
               if isinstance(t, go.Scatter) and t.name in five and t.mode == "lines"}
    assert len(colours) == 5 and len(set(colours.values())) == 5

    six = {f"c{i}": np.array([1.0 + 0.1 * i]) for i in range(6)}
    with pytest.raises(ValueError, match=r"6 conditions.*5 colours"):
        plot_multi_condition_raster_psth(_canvas(rows=2), 0, 0, 1, 0, st, six)
    plot_multi_condition_raster_psth(_canvas(rows=2), 0, 0, 1, 0, st, six,
                                     colors={name: "#123456" for name in six})  # an explicit map is not refused


def test_modulation_colour_range_ignores_a_nan_and_refuses_an_all_non_finite_matrix():
    """One NaN made the 98th percentile NaN, so the colour range had no limits."""
    areas, bands = ["a", "b"], ["x", "y"]
    finite = np.array([[1.0, -2.0], [3.0, -4.0]])
    canvas = _canvas()
    plot_spectral_modulation_matrix(canvas, 0, 0, delta_db_matrix=finite, areas=areas, bands=bands)
    (heatmap,) = _traces(canvas, go.Heatmap)
    assert heatmap.zmax == pytest.approx(np.percentile(np.abs(finite), 98))  # precondition: finite unchanged

    matrix = np.array([[1.0, np.nan], [2.0, 3.0]])
    assert np.isnan(matrix).sum() == 1  # precondition: one NaN
    canvas = _canvas()
    plot_spectral_modulation_matrix(canvas, 0, 0, delta_db_matrix=matrix, areas=areas, bands=bands)
    (heatmap,) = _traces(canvas, go.Heatmap)
    assert np.isfinite(heatmap.zmax)
    assert heatmap.zmax == pytest.approx(np.percentile([1.0, 2.0, 3.0], 98))
    assert heatmap.zmin == -heatmap.zmax
    with pytest.raises(ValueError, match="delta_db_matrix"):
        plot_spectral_modulation_matrix(_canvas(), 0, 0, delta_db_matrix=np.full((2, 2), np.nan),
                                        areas=areas, bands=bands)


def test_granger_spectra_refuses_series_and_ribbon_that_do_not_match_the_frequencies():
    freqs = np.arange(5.0)
    plot_granger_spectra(_canvas(), 0, 0, freqs, np.ones(5), np.ones(5),
                         null_ribbon=np.ones((5, 2)))  # precondition: matching shapes are accepted
    with pytest.raises(ValueError, match=r"gc_ff shape \(4,\).*freqs shape \(5,\)"):
        plot_granger_spectra(_canvas(), 0, 0, freqs, np.ones(4), np.ones(5))
    with pytest.raises(ValueError, match=r"gc_fb shape \(4,\).*freqs shape \(5,\)"):
        plot_granger_spectra(_canvas(), 0, 0, freqs, np.ones(5), np.ones(4))
    refused = _canvas()
    with pytest.raises(ValueError, match=r"null_ribbon shape \(3, 2\).*expected \(5, 2\)"):
        plot_granger_spectra(refused, 0, 0, freqs, np.ones(5), np.ones(5), null_ribbon=np.ones((3, 2)))
    assert len(refused.fig.data) == 0, "a refused ribbon must draw nothing"


def test_rsm_heatmap_refuses_a_matrix_that_does_not_match_its_labels():
    plot_rsm_heatmap(_canvas(), 0, 0, np.ones((2, 2)), ["a", "b"])  # precondition
    with pytest.raises(ValueError, match=r"rsm_matrix shape \(3, 3\).*2 labels.*\(2, 2\)"):
        plot_rsm_heatmap(_canvas(), 0, 0, np.ones((3, 3)), ["a", "b"])


def test_opposing_gradients_refuses_intervals_that_do_not_hold_one_pair_per_depth():
    depths = np.linspace(0.0, 1.0, 4)
    ones = np.ones(4)
    common = dict(gamma_power=ones, alphabeta_power=ones, depths=depths, depth_unit="relative")
    plot_opposing_gradients(_canvas(), 0, 0, ci_gamma=np.ones((4, 2)), ci_alphabeta=np.ones((4, 2)),
                            **common)  # precondition: one [lower, upper] pair per depth
    with pytest.raises(ValueError, match=r"ci_gamma shape \(3, 2\).*depths shape \(4,\)"):
        plot_opposing_gradients(_canvas(), 0, 0, ci_gamma=np.ones((3, 2)), **common)
    with pytest.raises(ValueError, match=r"ci_alphabeta shape \(4, 3\).*depths shape \(4,\)"):
        plot_opposing_gradients(_canvas(), 0, 0, ci_alphabeta=np.ones((4, 3)), **common)


@pytest.mark.parametrize("shape", [(3, 3), (1, 1)])
def test_modulation_significance_mask_must_match_the_matrix(shape):
    """A larger mask was accepted silently; a smaller one raised an IndexError."""
    kwargs = dict(delta_db_matrix=np.ones((2, 2)), areas=["a", "b"], bands=["x", "y"])
    plot_spectral_modulation_matrix(_canvas(), 0, 0, sig_mask=np.zeros((2, 2), dtype=bool),
                                    **kwargs)  # precondition: matching shapes are accepted
    refused = _canvas()
    with pytest.raises(ValueError, match=r"sig_mask shape \(\d, \d\).*\(2, 2\)"):
        plot_spectral_modulation_matrix(refused, 0, 0, sig_mask=np.ones(shape, dtype=bool), **kwargs)
    assert len(refused.fig.data) == 0, "a refused mask must draw nothing"


def test_modulation_significance_mask_refuses_a_nan_cell():
    """A float mask with NaN cast to True and marked the cell significant."""
    kwargs = dict(delta_db_matrix=np.ones((2, 2)), areas=["a", "b"], bands=["x", "y"])
    plot_spectral_modulation_matrix(_canvas(), 0, 0, sig_mask=np.array([[0.0, 1.0], [0.0, 0.0]]),
                                    **kwargs)  # precondition: a finite float mask is accepted
    with pytest.raises(ValueError, match="non-finite cell"):
        plot_spectral_modulation_matrix(_canvas(), 0, 0,
                                        sig_mask=np.array([[0.0, np.nan], [0.0, 0.0]]), **kwargs)


def test_hierarchy_axis_range_stays_finite_with_a_nan_rank():
    ranks = np.array([0.0, np.nan, 2.0, 3.0])
    values = np.array([1.0, 2.0, 3.0, 4.0])
    canvas = _canvas()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        plot_hierarchy_regression(canvas, 0, 0, hierarchy_ranks=ranks, values=values,
                                  ci_low=values - 0.5, ci_high=values + 0.5,
                                  area_labels=list("abcd"), y_label="y")
    assert tuple(canvas.fig.layout.xaxis.range) == pytest.approx((-0.6, 3.6), rel=1e-12)


def test_empty_source_artifact_is_refused():
    base = dict(QUESTION="q", DATA="d", ESTIMAND="e", **{"INFERENCE UNIT": "u", "RESULT": "r",
                "LICENSED CLAIM": "l", "BARRED CLAIM": "b"})
    single = EpistemicArgumentObject.from_dict(dict(base, **{"SOURCE ARTIFACTS": "receipt.json"}))
    assert single.SOURCE_ARTIFACTS == ["receipt.json"]  # precondition: a bare string is one path
    for source in ("", "   ", ["", "receipt.json"]):
        with pytest.raises(ValueError, match="SOURCE ARTIFACTS"):
            EpistemicArgumentObject.from_dict(dict(base, **{"SOURCE ARTIFACTS": source}))
