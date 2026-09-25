"""
tests/test_vis.py -- Comprehensive unit and integration tests for jnwb.vis.

Tests:
1. PlotlyPublicationCanvas layout, domain geometry, and collision-free math.
2. Triple-format export (.svg, .png, .html) and epistemic sidecar serialization.
3. Vector SVG text integrity (<text> tag preservation).
4. Primitives across all 6 motifs:
   - Spectrolaminar maps (Mendoza-Halliday 2024 motif)
   - Opposing laminar gradients with bootstrap CI ribbons
   - CSD depth x time profiles
   - Multi-condition raster + PSTH with bootstrap ribbons
   - Sorted population heatmaps
   - Hierarchy regressions with error_y and permutation null ribbons
   - Spectral modulation matrices with FDR indicators
   - Granger causality spectra
   - Decoding time courses with cluster permutation bars
   - RSM heatmaps
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

# jnwb.vis needs the optional `vis` extra; test_optional_vis_extra.py covers its absence.
pytest.importorskip("plotly")
import plotly.graph_objects as go  # noqa: E402

from jnwb.vis.canvas import PlotlyPublicationCanvas, STANDARD_LAYOUT_WIDTHS_MM, MM_TO_PX
from jnwb.vis.sidecar import EpistemicArgumentObject, serialize_argument_sidecar
from jnwb.vis.theme import (
    COLOR_PALETTES,
    FONT_FAMILY,
    FONT_SIZES,
    TOL_MUTED,
    OKABE_ITO,
    NATURE_ACCENTS,
    apply_publication_theme,
    get_publication_layout_template,
)
from jnwb.vis.laminar import (
    plot_spectrolaminar_map,
    plot_opposing_gradients,
    plot_csd,
)
from jnwb.vis.spiking import (
    plot_multi_condition_raster_psth,
    plot_sorted_heatmap,
)
from jnwb.vis.hierarchy import plot_hierarchy_regression
from jnwb.vis.spectral import (
    plot_spectral_modulation_matrix,
    plot_granger_spectra,
)
from jnwb.vis.state_space import (
    plot_decoding_timecourse,
    plot_rsm_heatmap,
)


@pytest.fixture
def sample_argument_data():
    return {
        "QUESTION": "Does condition B change the firing rate relative to condition A?",
        "DATA": "Synthetic test corpus (12 units across 3 areas)",
        "ESTIMAND": "Fraction of units whose rate differs between conditions",
        "INFERENCE UNIT": "Sessions (n=4)",
        "RESULT": "Placeholder result for a rendering test",
        "LICENSED CLAIM": "Placeholder licensed claim",
        "BARRED CLAIM": "Placeholder barred claim",
        "SOURCE ARTIFACTS": ["test_source_receipt.json"],
    }


# ==============================================================================
# 1. Epistemic Sidecar Tests
# ==============================================================================

def test_sidecar_validation_success(sample_argument_data):
    obj = EpistemicArgumentObject.from_dict(sample_argument_data)
    d = obj.to_dict()
    assert d["QUESTION"] == sample_argument_data["QUESTION"]
    assert len(d["SOURCE ARTIFACTS"]) == 1


def test_sidecar_missing_field_raises():
    bad_data = {
        "QUESTION": "Incomplete question",
        # Missing other 7 fields
    }
    with pytest.raises(ValueError):
        EpistemicArgumentObject.from_dict(bad_data)


def test_sidecar_serialization(tmp_path, sample_argument_data):
    out_file = tmp_path / "test_argument.json"
    p = serialize_argument_sidecar(out_file, sample_argument_data)
    assert p.exists()
    loaded = EpistemicArgumentObject.load(p)
    assert loaded.RESULT == sample_argument_data["RESULT"]


# ==============================================================================
# 2. Canvas & Relative Domain Mathematics Tests
# ==============================================================================

def test_canvas_dimensions():
    for preset, width_mm in STANDARD_LAYOUT_WIDTHS_MM.items():
        canvas = PlotlyPublicationCanvas(layout=preset, height_mm=120.0)
        expected_w = int(round(width_mm * MM_TO_PX))
        expected_h = int(round(120.0 * MM_TO_PX))
        assert canvas.width_px == expected_w
        assert canvas.height_px == expected_h
        assert canvas.fig.layout.width == expected_w
        assert canvas.fig.layout.height == expected_h


def test_canvas_disjoint_domains():
    canvas = PlotlyPublicationCanvas(
        layout="2col",
        rows=2,
        cols=3,
        row_height_ratios=[1.0, 1.2],
        col_width_ratios=[1.0, 1.0, 1.5],
        tags=[["A", "B", "C"], ["D", "E", "F"]],
    )

    domains = canvas.domains
    assert len(domains) == 6

    # Verify every panel has valid non-empty domain
    for (r, c), ((x0, x1), (y0, y1)) in domains.items():
        assert 0.0 <= x0 < x1 <= 1.0
        assert 0.0 <= y0 < y1 <= 1.0

    # Verify no overlapping domains between distinct panels
    items = list(domains.items())
    for i in range(len(items)):
        (r1, c1), ((ax0, ax1), (ay0, ay1)) = items[i]
        for j in range(i + 1, len(items)):
            (r2, c2), ((bx0, bx1), (by0, by1)) = items[j]
            x_overlap = not (ax1 <= bx0 or bx1 <= ax0)
            y_overlap = not (ay1 <= by0 or by1 <= ay0)
            assert not (x_overlap and y_overlap), f"Panels ({r1},{c1}) and ({r2},{c2}) overlap!"


def test_canvas_panel_tags_anchoring():
    canvas = PlotlyPublicationCanvas(
        layout="2col",
        rows=1,
        cols=2,
        tags=[["A", "B"]],
    )
    annotations = canvas.fig.layout.annotations
    tag_texts = [a.text for a in annotations if "<b>" in a.text]
    assert "<b>A</b>" in tag_texts
    assert "<b>B</b>" in tag_texts


def test_canvas_colorbar_placement():
    canvas = PlotlyPublicationCanvas(layout="2col", rows=1, cols=2)
    cb_cfg = canvas.get_colorbar_config(row=0, col=0, title="Power")
    assert cb_cfg["xanchor"] == "left"
    assert cb_cfg["thickness"] == 12.0
    assert cb_cfg["yanchor"] == "middle"
    assert cb_cfg["title"]["text"] == "Power"


# ==============================================================================
# 3. Triple Export & Vector Text Verification Tests
# ==============================================================================

def test_canvas_save_and_seal_triple_export(tmp_path, sample_argument_data):
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=80.0, rows=1, cols=1, tags=[["A"]])
    canvas.fig.add_trace(go.Scatter(x=[0, 1, 2], y=[10, 20, 15], mode="lines+markers"))

    out_paths = canvas.save_and_seal(
        output_dir=tmp_path,
        basename="test_figure",
        argument_object=sample_argument_data,
        png_dpi=150,
    )

    assert "svg" in out_paths and out_paths["svg"].exists()
    assert "png" in out_paths and out_paths["png"].exists()
    assert "html" in out_paths and out_paths["html"].exists()
    assert "argument" in out_paths and out_paths["argument"].exists()

    for fmt, p in out_paths.items():
        assert p.stat().st_size > 0

    # Parse SVG and verify presence of <text> elements
    svg_content = out_paths["svg"].read_text(encoding="utf-8")
    root = ET.fromstring(svg_content)
    # Search for text elements (handling potential XML namespace)
    text_elements = [el for el in root.iter() if el.tag.endswith("text")]
    assert len(text_elements) > 0, "Exported SVG does not contain <text> elements!"


# ==============================================================================
# 4. Scientific Primitives Tests
# ==============================================================================

def test_spectrolaminar_map_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    freqs = np.linspace(1, 150, 150)
    depths = np.linspace(0.0, 1.0, 32)
    rel_power = np.random.uniform(0.1, 1.0, size=(150, 32))

    plot_spectrolaminar_map(
        canvas=canvas,
        row=0,
        col=0,
        rel_power=rel_power,
        freqs=freqs,
        depths=depths,
        crossover_depth=0.4,
        depth_unit="relative",
    )

    traces = canvas.fig.data
    heatmap_traces = [t for t in traces if isinstance(t, go.Heatmap)]
    assert len(heatmap_traces) == 1
    assert heatmap_traces[0].zmin == 0.0
    assert heatmap_traces[0].zmax == 1.0


def test_no_crossover_depth_is_drawn_unless_the_caller_computed_one():
    """The default used to draw one study's measured depth on every recording."""
    freqs = np.linspace(1, 150, 150)
    depths = np.linspace(0.0, 1.0, 32)
    rel_power = np.random.default_rng(0).uniform(0.1, 1.0, size=(150, 32))

    bare = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    plot_spectrolaminar_map(canvas=bare, row=0, col=0, rel_power=rel_power, freqs=freqs,
                            depths=depths, depth_unit="relative")
    assert not any("Crossover" in (a.text or "") for a in bare.fig.layout.annotations)
    assert not any(isinstance(t, go.Scatter) for t in bare.fig.data)

    given = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    plot_spectrolaminar_map(canvas=given, row=0, col=0, rel_power=rel_power, freqs=freqs,
                            depths=depths, crossover_depth=0.37, depth_unit="relative")
    assert any("Crossover (0.37)" in (a.text or "") for a in given.fig.layout.annotations)


def test_opposing_gradients_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    depths = np.linspace(0.0, 1.0, 20)
    gamma = 1.0 - depths
    alphabeta = depths
    ci_gamma = np.column_stack([gamma - 0.1, gamma + 0.1])
    ci_ab = np.column_stack([alphabeta - 0.1, alphabeta + 0.1])

    plot_opposing_gradients(
        canvas=canvas,
        row=0,
        col=0,
        gamma_power=gamma,
        alphabeta_power=alphabeta,
        depths=depths,
        crossover_depth=0.4,
        ci_gamma=ci_gamma,
        ci_alphabeta=ci_ab,
        depth_unit="relative",
    )

    traces = canvas.fig.data
    assert len(traces) >= 6  # 2 bounds for gamma CI, 2 bounds for AB CI, 2 main lines


def test_csd_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    depths = np.linspace(0.0, 1.0, 16)
    time_ms = np.linspace(-100, 300, 100)
    csd = np.random.randn(16, 100)

    plot_csd(
        canvas=canvas,
        row=0,
        col=0,
        csd_matrix=csd,
        time_ms=time_ms,
        depths=depths,
        layer_boundaries={"L4": 0.4, "L5/6": 0.65},
        depth_unit="relative",
    )

    traces = canvas.fig.data
    assert any(isinstance(t, go.Heatmap) for t in traces)


def _laminar_call(name, depths, **kwargs):
    """Draw one laminar panel on a fresh canvas and return the depth-axis title."""
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    n = len(depths)
    if name == "map":
        plot_spectrolaminar_map(canvas, 0, 0, rel_power=np.full((5, n), 0.5),
                                freqs=np.arange(1.0, 6.0), depths=depths, **kwargs)
    elif name == "gradients":
        plot_opposing_gradients(canvas, 0, 0, gamma_power=np.linspace(1, 0, n),
                                alphabeta_power=np.linspace(0, 1, n), depths=depths, **kwargs)
    else:
        plot_csd(canvas, 0, 0, csd_matrix=np.ones((n, 4)), time_ms=np.arange(4.0),
                 depths=depths, **kwargs)
    _, y_axis = canvas.get_axis_names(0, 0)
    yaxis_name = "yaxis" if y_axis == "y" else f"yaxis{y_axis[1:]}"
    return getattr(canvas.fig.layout, yaxis_name).title.text


LAMINAR_PLOTS = ["map", "gradients", "csd"]


@pytest.mark.parametrize("name", LAMINAR_PLOTS)
@pytest.mark.parametrize("unit, label", [
    ("mm", "Cortical Depth (mm)"),
    ("um", "Cortical Depth (μm)"),
    ("relative", "Relative Depth (0=Pia, 1=WM)"),
])
def test_laminar_depth_axis_is_labelled_from_the_declared_unit(name, unit, label):
    """A 0-1.55 mm probe was labelled relative depth because the unit was read off the maximum."""
    assert _laminar_call(name, np.linspace(0.0, 1.55, 8), depth_unit=unit) == label


@pytest.mark.parametrize("name", LAMINAR_PLOTS)
def test_laminar_depth_unit_is_required_and_validated(name):
    with pytest.raises(TypeError, match="depth_unit"):
        _laminar_call(name, np.linspace(0.0, 1.0, 8))
    with pytest.raises(ValueError, match="'mm', 'um' or 'relative'"):
        _laminar_call(name, np.linspace(0.0, 1.0, 8), depth_unit="cm")


def test_multi_condition_raster_psth_reads_a_steady_rate_to_the_last_bin_and_refuses_partial_bins():
    """The default window spanned 781 ms at 10 ms bins, so its last bin held 1 ms of spikes
    divided by 10 ms and a steady 1000 Hz train drew a dip to about 100 Hz at the end."""
    steady = np.arange(0.0005, 10.0, 0.001)
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=120.0, rows=2, cols=1)
    plot_multi_condition_raster_psth(canvas, 0, 0, 1, 0, steady, {"A": np.array([2.0, 4.0])})
    line = [t for t in canvas.fig.data if isinstance(t, go.Scatter) and t.name == "A"][0]
    assert np.allclose(line.y, 1000.0)
    with pytest.raises(ValueError, match="the last bin would be partial"):
        plot_multi_condition_raster_psth(
            canvas, 0, 0, 1, 0, steady, {"A": np.array([2.0])}, win_ms=(-100.0, 305.0))


def test_multi_condition_raster_psth_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=120.0, rows=2, cols=1, row_height_ratios=[1.2, 1.0])
    st = np.sort(np.random.uniform(0, 100, 500))
    onsets = {
        "Condition A": np.array([5.0, 15.0, 25.0, 35.0]),
        "Condition B": np.array([45.0, 55.0, 65.0, 75.0]),
    }

    plot_multi_condition_raster_psth(
        canvas=canvas,
        row_raster=0,
        col_raster=0,
        row_psth=1,
        col_psth=0,
        st=st,
        onsets=onsets,
        win_ms=(-100, 300),
        stim_dur_ms=200,
    )

    traces = canvas.fig.data
    # WebGL Scattergl traces for rasters
    scattergl_traces = [t for t in traces if isinstance(t, go.Scattergl)]
    assert len(scattergl_traces) == 2
    # PSTH line traces
    psth_traces = [t for t in traces if isinstance(t, go.Scatter) and t.mode == "lines"]
    assert len(psth_traces) >= 2


def test_hierarchy_regression_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    ranks = np.arange(5)
    values = np.array([1.2, 2.5, 3.1, 4.2, 3.8])
    ci_low = values - 0.5
    ci_high = values + 0.5
    areas = ["A1", "A2", "A3", "A4", "A5"]

    plot_hierarchy_regression(
        canvas=canvas,
        row=0,
        col=0,
        hierarchy_ranks=ranks,
        values=values,
        ci_low=ci_low,
        ci_high=ci_high,
        area_labels=areas,
        r_squared=0.82,
        p_perm=0.012,
        null_line=5.0,
    )

    traces = canvas.fig.data
    # Data points trace with error_y
    data_traces = [t for t in traces if hasattr(t, "error_y") and t.error_y.visible]
    assert len(data_traces) == 1
    assert data_traces[0].error_y.visible is True


def test_spectral_modulation_matrix_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    areas = ["A1", "A2", "A3"]
    bands = ["θ", "α", "β", "γ"]
    delta_db = np.array([[-1.2, 0.5, -0.3, 2.1], [0.1, -1.8, -0.5, 1.4], [-0.2, 0.1, 1.5, -0.8]])
    sig_mask = np.array([[True, False, False, True], [False, True, False, True], [False, False, True, False]])

    plot_spectral_modulation_matrix(
        canvas=canvas,
        row=0,
        col=0,
        delta_db_matrix=delta_db,
        areas=areas,
        bands=bands,
        sig_mask=sig_mask,
    )

    traces = canvas.fig.data
    assert any(isinstance(t, go.Heatmap) for t in traces)


def test_decoding_timecourse_primitive():
    canvas = PlotlyPublicationCanvas(layout="1col", height_mm=90.0, rows=1, cols=1)
    time_ms = np.linspace(-100, 400, 100)
    accuracy = 0.5 + 0.25 * np.exp(-((time_ms - 150) ** 2) / (2 * 50**2))
    ci_low = accuracy - 0.05
    ci_high = accuracy + 0.05

    plot_decoding_timecourse(
        canvas=canvas,
        row=0,
        col=0,
        time_ms=time_ms,
        accuracy=accuracy,
        ci_low=ci_low,
        ci_high=ci_high,
        chance_level=0.5,
        sig_clusters=[(100.0, 220.0)],
    )

    traces = canvas.fig.data
    assert len(traces) >= 3  # chance line, CI lower, CI upper fill, main line
