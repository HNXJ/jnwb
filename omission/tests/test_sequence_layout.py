"""Tests for omission sequence layout timing and Plotly shape builders."""

from __future__ import annotations

from omission.jnwb_ext.sequence_layout import (
    CANONICAL_AREAS_11,
    DUAL_AREA_FIRST_SLICE,
    DUAL_AREA_SECOND_SLICE,
    FULL_SEQUENCE_DURATION_MS,
    FULL_SEQUENCE_END_MS,
    FULL_SEQUENCE_START_MS,
    channel_slice_for_area,
    epoch_intervals,
    make_sequence_figure,
    normalize_area_name,
    omission_window_ms,
    parse_probe_areas,
    sequence_shapes,
)


def test_full_sequence_span_is_4624_ms():
    assert FULL_SEQUENCE_START_MS == -500.0
    assert FULL_SEQUENCE_END_MS == 4124.0
    assert FULL_SEQUENCE_DURATION_MS == 4624.0


def test_epoch_chain_matches_user_contract():
    eps = {e.name: e for e in epoch_intervals()}
    assert eps["fx"].start_ms == -500.0
    assert eps["p1"].start_ms == 0.0
    assert eps["d1"].start_ms == 531.0  # p1 + 531
    assert eps["p2"].start_ms == 1031.0  # d1 + 500
    assert eps["d2"].start_ms == 1562.0
    assert eps["p3"].start_ms == 2062.0
    assert eps["d3"].start_ms == 2593.0
    assert eps["p4"].start_ms == 3093.0
    assert eps["d4"].start_ms == 3624.0
    assert eps["d4"].end_ms == 4124.0


def test_omission_windows_r_family():
    assert omission_window_ms("RRRR") is None
    # RXRR: d1–p2–d2
    assert omission_window_ms("RXRR") == (531.0, 2062.0)
    # RRXR: d2–p3–d3
    assert omission_window_ms("RRXR") == (1562.0, 3093.0)
    # RRRX: d3–p4–d4
    assert omission_window_ms("RRRX") == (2593.0, 4124.0)


def test_sequence_shapes_are_vector_objects_not_images():
    shapes = sequence_shapes()
    assert len(shapes) >= 9  # at least one rect per epoch
    types = {s["type"] for s in shapes}
    assert "rect" in types
    assert "line" in types
    assert all("fillcolor" in s or s["type"] == "line" for s in shapes)


def test_make_sequence_figure_builds():
    fig = make_sequence_figure(highlight_omission="RXRR")
    assert fig.layout.shapes
    assert any(getattr(s, "type", None) == "rect" or s.type == "rect" for s in fig.layout.shapes)


def test_v3_dual_split_and_canonical_areas():
    assert parse_probe_areas("V3") == ("V3d", "V3a")
    assert parse_probe_areas("V3d, V3a") == ("V3d", "V3a")
    assert parse_probe_areas("V3d/V3a") == ("V3d", "V3a")
    assert parse_probe_areas("MT, MST") == ("MT", "MST")
    assert parse_probe_areas("V3, V1") == ("V3", "V1")
    assert parse_probe_areas("FEF") == ("FEF",)
    assert normalize_area_name("V3a") == "V3a"
    assert normalize_area_name("V3d") == "V3d"
    assert "V3d" in CANONICAL_AREAS_11
    assert "V3a" in CANONICAL_AREAS_11
    assert CANONICAL_AREAS_11.index("V3d") < CANONICAL_AREAS_11.index("V3a")
    assert channel_slice_for_area(("V3d", "V3a"), "V3d") == DUAL_AREA_FIRST_SLICE
    assert channel_slice_for_area(("V3d", "V3a"), "V3a") == DUAL_AREA_SECOND_SLICE
    assert channel_slice_for_area(("V3", "V1"), "V3") == slice(0, 64)
    assert channel_slice_for_area(("V3", "V1"), "V1") == slice(64, 128)
    assert channel_slice_for_area(("MT", "MST"), "MT") == slice(0, 64)
    assert channel_slice_for_area(("MT", "MST"), "MST") == slice(64, 128)
    assert channel_slice_for_area(("FEF",), "FEF") == slice(0, 128)
