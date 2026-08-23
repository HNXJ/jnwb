"""Unit tests for jnwb.metadata -- generic unit/electrode metadata extraction, QC
classification, and census reporting, promoted 2026-08-23 from omission.jnwb_ext.metadata
(99%-jnwb-sufficiency normalization). The NWB-reading functions (get_all_units_metadata,
electrode_inventory) are exercised elsewhere against real files (omission/tests/); these tests
cover the pure DataFrame-transform functions with synthetic data, plus the public-API surface.
"""
from __future__ import annotations

import pandas as pd
import pytest

from jnwb.metadata import classify_unit_quality, unit_census_report, get_snr_analysis


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        from jnwb import (
            get_all_units_metadata, classify_unit_quality as pub_cuq,
            unit_census_report as pub_ucr, get_snr_analysis as pub_gsa,
            electrode_inventory,
        )
        assert pub_cuq is classify_unit_quality
        assert pub_ucr is unit_census_report
        assert pub_gsa is get_snr_analysis
        assert callable(get_all_units_metadata)
        assert callable(electrode_inventory)

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("get_all_units_metadata", "classify_unit_quality", "unit_census_report",
                     "get_snr_analysis", "electrode_inventory"):
            assert name in jnwb.__all__


def _synthetic_units():
    return pd.DataFrame({
        "unit_id": [1, 2, 3, 4],
        "session_id": [100, 100, 101, 101],
        "area": ["FEF", "FEF", "PFC", "PFC"],
        "layer": ["sup", "deep", "sup", "deep"],
        "quality": [1.0, 0.5, 1.0, 1.0],
        "snr": [2.0, 0.3, 1.5, 0.9],
        "firing_rate": [5.0, 0.05, 3.0, 0.2],
        "waveform_duration": [0.4, 0.3, 0.5, 0.35],
    })


class TestClassifyUnitQuality:
    def test_good_unit_passes_default_thresholds(self):
        df = classify_unit_quality(_synthetic_units())
        row = df[df["unit_id"] == 1].iloc[0]
        assert row["is_valid"]
        assert row["quality_class"] == "Good"

    def test_low_quality_and_snr_flagged_poor(self):
        df = classify_unit_quality(_synthetic_units())
        row = df[df["unit_id"] == 2].iloc[0]
        assert not row["is_valid"]
        assert row["quality_class"] == "Poor"
        assert any("quality<1.0" in f for f in row["issue_flags"])
        assert any("snr<1.0" in f for f in row["issue_flags"])

    def test_custom_thresholds_override_defaults(self):
        df = classify_unit_quality(_synthetic_units(), thresholds={"firing_rate": 10.0})
        # Every unit's firing_rate < 10.0 -> every unit flagged, none critical (not in critical_flags list)
        assert (df["quality_class"] == "Fair").all()

    def test_does_not_mutate_input(self):
        original = _synthetic_units()
        original_copy = original.copy()
        classify_unit_quality(original)
        pd.testing.assert_frame_equal(original, original_copy)


class TestUnitCensusReport:
    def test_groups_by_default_columns(self):
        census = unit_census_report(_synthetic_units())
        assert set(census["session_id"]) == {100, 101}
        assert "n_units" in census.columns

    def test_groups_by_custom_columns(self):
        census = unit_census_report(_synthetic_units(), group_by=["area"])
        assert set(census["area"]) == {"FEF", "PFC"}
        assert (census["n_units"] == 2).all()

    def test_missing_group_columns_are_dropped_not_errored(self):
        census = unit_census_report(_synthetic_units(), group_by=["area", "nonexistent_col"])
        assert "area" in census.columns
        assert "nonexistent_col" not in census.columns


class TestGetSnrAnalysis:
    def test_basic_stats(self):
        result = get_snr_analysis(_synthetic_units(), snr_threshold=1.0)
        assert result["n_units_with_snr"] == 4
        assert result["pass_count"] == 2  # snr 2.0 and 1.5 pass; 0.3 and 0.9 fail
        assert result["pass_rate"] == pytest.approx(0.5)

    def test_missing_snr_column_returns_empty_dict(self):
        df = _synthetic_units().drop(columns=["snr"])
        result = get_snr_analysis(df)
        assert result == {}

    def test_detail_breaks_down_by_session(self):
        result = get_snr_analysis(_synthetic_units(), snr_threshold=1.0, detail=True)
        assert "by_session" in result
        assert set(result["by_session"].keys()) == {100, 101}
