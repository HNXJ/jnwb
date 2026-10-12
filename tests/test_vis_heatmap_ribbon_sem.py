"""
tests/test_vis_heatmap_ribbon_sem.py -- three pins from the display review.

1. ``plot_sorted_heatmap`` refuses ``category_labels`` before it draws anything: the argument
   names unit groups but gives no mapping from labels to rows, so it cannot be drawn yet.
2. ``plot_decoding_timecourse`` draws its CI ribbon only when ``ci_low`` and ``ci_high`` are
   both given, and its docstring and ``docs/vis.md`` say so.
3. ``raster_psth`` SEM is the sample standard deviation (ddof=1) over the square root of the
   trial count, pinned by a value worked out by hand.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from jnwb.viz import raster_psth

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

from jnwb.vis.canvas import PlotlyPublicationCanvas  # noqa: E402
from jnwb.vis.spiking import plot_sorted_heatmap  # noqa: E402
from jnwb.vis.state_space import plot_decoding_timecourse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RIBBON_RULE = "drawn only when both ``ci_low`` and ``ci_high`` are given"


def test_sorted_heatmap_without_category_labels_still_draws():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    plot_sorted_heatmap(canvas, 0, 0, np.ones((3, 4)), np.arange(4.0), value_unit="z")
    assert [t for t in canvas.fig.data if isinstance(t, go.Heatmap)]


def test_sorted_heatmap_refuses_category_labels_before_drawing():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    with pytest.raises(ValueError, match="category_labels"):
        plot_sorted_heatmap(canvas, 0, 0, np.ones((3, 4)), np.arange(4.0), value_unit="z",
                            category_labels=["a", "b", "c"])
    assert len(canvas.fig.data) == 0


def _ribbon_count(**bounds):
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    plot_decoding_timecourse(canvas, 0, 0, np.arange(4.0), np.full(4, 0.6), **bounds)
    return sum(1 for t in canvas.fig.data if t.fill == "tonexty")


def test_decoding_ribbon_is_drawn_only_with_both_bounds():
    lo, hi = np.full(4, 0.5), np.full(4, 0.7)
    assert _ribbon_count() == 0
    assert _ribbon_count(ci_low=lo) == 0
    assert _ribbon_count(ci_high=hi) == 0
    assert _ribbon_count(ci_low=lo, ci_high=hi) == 1


def test_decoding_docstring_says_the_ribbon_needs_both_bounds():
    assert RIBBON_RULE in " ".join(plot_decoding_timecourse.__doc__.split())


def test_docs_vis_row_says_the_ribbon_needs_both_bounds():
    rows = [line for line in (ROOT / "docs" / "vis.md").read_text(encoding="utf-8").splitlines()
            if line.startswith("| `plot_decoding_timecourse`")]
    assert len(rows) == 1, "docs/vis.md must hold one plot_decoding_timecourse row"
    assert "drawn only when both `ci_low` and `ci_high` are given" in rows[0]


def test_raster_psth_sem_is_sample_sd_over_root_n_by_hand():
    """Three trials with 1, 2 and 3 spikes in a 100 ms bin: rates 10, 20 and 30 Hz.

    By hand: the mean is 20. The squared deviations 100, 0 and 100 sum to 200. Dividing by
    n - 1 = 2 gives a sample variance of 100, so the sample SD is 10. The SEM divides that by
    sqrt(3), giving 10 / sqrt(3), about 5.7735. A ddof=0 SEM gives about 4.7140; no division
    by sqrt(n) gives 10. Neither matches.
    """
    st = np.array([0.05, 1.02, 1.07, 2.01, 2.04, 2.09])
    onsets = np.array([0.0, 1.0, 2.0])
    spikes = [int(np.sum((st >= t0) & (st < t0 + 0.1))) for t0 in onsets]
    assert spikes == [1, 2, 3], "fixture must place 1, 2 and 3 spikes in the three bins"

    _, mean, sem = raster_psth(st, onsets, (0.0, 100.0), bin_ms=100.0)

    rates = [count / 0.1 for count in spikes]
    n = len(rates)
    m = sum(rates) / n
    sum_sq = sum((r - m) ** 2 for r in rates)
    sample_sd = math.sqrt(sum_sq / (n - 1))
    expected = sample_sd / math.sqrt(n)
    assert mean[0] == pytest.approx(20.0, rel=1e-12)
    assert expected == pytest.approx(10 / math.sqrt(3), rel=1e-12)
    assert sem[0] == pytest.approx(expected, rel=1e-12)
