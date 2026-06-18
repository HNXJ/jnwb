"""
tests/test_spsam_pipeline.py — Automated tests for SpSAM pipeline primitives.

Tests:
  - map_group_to_lfp_key(): probe name variants
  - build_channel_area_map(): single-area, dual-area, tri-area probes
  - parse_location_to_areas(): parsing
  - extract_lfp_phase(): shape, finite output
  - compute_plv(): range [0,1], zero-spike edge case
  - compute_cross_correlation(): zero-variance edge case, known perfect correlation
"""
import sys
sys.path.insert(0, ".")
import pytest
import numpy as np
import pandas as pd

from src.analysis.spsam.spsam_pipeline import (
    map_group_to_lfp_key,
    parse_location_to_areas,
    build_channel_area_map,
    extract_lfp_phase,
    compute_plv,
    compute_cross_correlation,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_mock_elec_df(probe_layout):
    """
    Build a mock electrodes DataFrame.

    probe_layout: list of (group_name, location, n_ch)
    """
    rows = []
    global_idx = 0
    for g_name, loc, n_ch in probe_layout:
        for _ in range(n_ch):
            rows.append({
                "location":   loc,
                "group_name": g_name,
                "probe":      g_name,
                "group":      None,  # not used by build_channel_area_map
            })
            global_idx += 1
    df = pd.DataFrame(rows)
    df.index = range(len(df))
    return df


# ---------------------------------------------------------------------------
# map_group_to_lfp_key
# ---------------------------------------------------------------------------

class TestMapGroupToLfpKey:
    def test_probeA_variants(self):
        assert map_group_to_lfp_key("probeA") == ("probe_0_lfp", 0)
        assert map_group_to_lfp_key("PROBEA") == ("probe_0_lfp", 0)
        assert map_group_to_lfp_key("a")      == ("probe_0_lfp", 0)

    def test_probeB_variants(self):
        assert map_group_to_lfp_key("probeB") == ("probe_1_lfp", 1)
        assert map_group_to_lfp_key("b")      == ("probe_1_lfp", 1)

    def test_probeC_variants(self):
        assert map_group_to_lfp_key("probeC") == ("probe_2_lfp", 2)
        assert map_group_to_lfp_key("c")      == ("probe_2_lfp", 2)

    def test_unknown_fallback(self):
        key, idx = map_group_to_lfp_key("unknown")
        assert key == "probe_0_lfp"
        assert idx == 0


# ---------------------------------------------------------------------------
# parse_location_to_areas
# ---------------------------------------------------------------------------

class TestParseLocationToAreas:
    def test_single_area(self):
        assert parse_location_to_areas("PFC") == ["PFC"]

    def test_comma_separated(self):
        result = parse_location_to_areas("V4, MT")
        assert result == ["V4", "MT"]

    def test_semicolon_separated(self):
        result = parse_location_to_areas("V1; V2; V3")
        assert result == ["V1", "V2", "V3"]

    def test_empty_string(self):
        result = parse_location_to_areas("")
        # Should return ["unresolved"] or empty — just not crash
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# build_channel_area_map
# ---------------------------------------------------------------------------

class TestBuildChannelAreaMap:
    def test_single_probe_single_area(self):
        df = make_mock_elec_df([("probeA", "PFC", 128)])
        cam = build_channel_area_map(df)
        assert len(cam) == 128
        for idx, info in cam.items():
            assert info["area"] == "PFC"
            assert info["probe_id"] == 0
            assert 0 <= info["local_idx"] < 128

    def test_single_probe_dual_area(self):
        df = make_mock_elec_df([("probeA", "V4, MT", 128)])
        cam = build_channel_area_map(df)
        # First 64 → V4, last 64 → MT
        areas = [cam[i]["area"] for i in range(128)]
        assert all(a == "V4" for a in areas[:64])
        assert all(a == "MT" for a in areas[64:])

    def test_two_probes(self):
        df = make_mock_elec_df([("probeA", "PFC", 128), ("probeB", "V4, MT", 128)])
        cam = build_channel_area_map(df)
        assert len(cam) == 256
        # probeA: global 0-127 → PFC
        assert cam[0]["area"] == "PFC"
        assert cam[127]["area"] == "PFC"
        # probeB: global 128-191 → V4 (first 64), 192-255 → MT (last 64)
        assert cam[128]["area"] == "V4"
        assert cam[191]["area"] == "V4"   # last of first half
        assert cam[192]["area"] == "MT"   # first of second half

    def test_channel_count_correctness(self):
        df = make_mock_elec_df([("probeA", "FEF", 128), ("probeB", "PFC", 128), ("probeC", "MT", 128)])
        cam = build_channel_area_map(df)
        assert len(cam) == 384
        # All probeC channels → MT
        for i in range(256, 384):
            assert cam[i]["area"] == "MT"


# ---------------------------------------------------------------------------
# extract_lfp_phase
# ---------------------------------------------------------------------------

class TestExtractLfpPhase:
    def test_output_shape_1d(self):
        lfp = np.random.randn(500)
        phase = extract_lfp_phase(lfp, (4, 8))
        assert phase.shape == (500,)

    def test_output_shape_2d(self):
        lfp = np.random.randn(20, 500)
        phase = extract_lfp_phase(lfp, (35, 90))
        assert phase.shape == (20, 500)

    def test_output_is_finite(self):
        lfp = np.random.randn(20, 500)
        phase = extract_lfp_phase(lfp, (8, 30))
        assert np.all(np.isfinite(phase))

    def test_output_in_range(self):
        lfp = np.random.randn(20, 500)
        phase = extract_lfp_phase(lfp, (12, 20))
        assert np.all(phase >= -np.pi)
        assert np.all(phase <= np.pi)


# ---------------------------------------------------------------------------
# compute_plv
# ---------------------------------------------------------------------------

class TestComputePlv:
    def test_range(self):
        phase = np.random.uniform(-np.pi, np.pi, (10, 500))
        spikes = (np.random.rand(10, 500) > 0.97).astype(float)
        plv = compute_plv(phase, spikes)
        assert 0.0 <= plv <= 1.0

    def test_zero_spikes(self):
        phase = np.zeros((10, 500))
        spikes = np.zeros((10, 500))
        plv = compute_plv(phase, spikes)
        assert plv == 0.0

    def test_perfectly_locked(self):
        # All spikes at phase=0 → PLV should be close to 1
        n_spikes = 200
        phase = np.zeros((1, n_spikes))  # all zero phase
        spikes = np.ones((1, n_spikes))
        plv = compute_plv(phase, spikes)
        assert plv > 0.99


# ---------------------------------------------------------------------------
# compute_cross_correlation
# ---------------------------------------------------------------------------

class TestComputeCrossCorrelation:
    def test_zero_variance_spikes(self):
        lfp = np.random.randn(10, 500)
        spikes = np.zeros((10, 500))
        cc = compute_cross_correlation(lfp, spikes)
        assert cc == 0.0

    def test_zero_variance_lfp(self):
        lfp = np.zeros((10, 500))
        spikes = (np.random.rand(10, 500) > 0.97).astype(float)
        cc = compute_cross_correlation(lfp, spikes)
        assert cc == 0.0

    def test_perfect_correlation(self):
        x = np.random.randn(10, 500)
        cc = compute_cross_correlation(x, x)
        assert abs(cc - 1.0) < 1e-9

    def test_perfect_anticorrelation(self):
        x = np.random.randn(10, 500)
        cc = compute_cross_correlation(x, -x)
        assert abs(cc + 1.0) < 1e-9

    def test_range(self):
        lfp = np.random.randn(10, 500)
        spikes = (np.random.rand(10, 500) > 0.97).astype(float)
        cc = compute_cross_correlation(lfp, spikes)
        assert -1.0 <= cc <= 1.0


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
