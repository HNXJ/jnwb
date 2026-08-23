"""Unit tests for jnwb.metadata -- generic unit/electrode metadata extraction, QC
classification, and census reporting, promoted 2026-08-23 from omission.jnwb_ext.metadata
(99%-jnwb-sufficiency normalization). The NWB-reading functions (get_all_units_metadata,
electrode_inventory) are exercised elsewhere against real files (omission/tests/); these tests
cover the pure DataFrame-transform functions with synthetic data, plus the public-API surface.
"""
from __future__ import annotations

import pandas as pd
import pytest

from jnwb.metadata import (
    classify_unit_quality, unit_census_report, get_snr_analysis, filter_by_criteria,
    audit_units, audit_electrodes,
)


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        from jnwb import (
            get_all_units_metadata, classify_unit_quality as pub_cuq,
            unit_census_report as pub_ucr, get_snr_analysis as pub_gsa,
            electrode_inventory, filter_by_criteria as pub_fbc,
            audit_units as pub_au, audit_electrodes as pub_ae,
        )
        assert pub_cuq is classify_unit_quality
        assert pub_ucr is unit_census_report
        assert pub_gsa is get_snr_analysis
        assert pub_fbc is filter_by_criteria
        assert pub_au is audit_units
        assert pub_ae is audit_electrodes
        assert callable(get_all_units_metadata)
        assert callable(electrode_inventory)

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("get_all_units_metadata", "classify_unit_quality", "unit_census_report",
                     "get_snr_analysis", "electrode_inventory", "filter_by_criteria",
                     "audit_units", "audit_electrodes"):
            assert name in jnwb.__all__

    def test_omission_functions_delegates_to_jnwb(self):
        functions = pytest.importorskip("omission.jnwb_ext.functions")
        assert functions._filter_units is filter_by_criteria

    def test_omission_diagnostics_delegates_to_jnwb(self):
        diagnostics = pytest.importorskip("omission.jnwb_ext.diagnostics")
        assert diagnostics._audit_units is audit_units
        assert diagnostics._audit_electrodes is audit_electrodes


class TestAuditUnits:
    def test_empty_dataframe_returns_zeroed_defaults(self):
        result = audit_units(pd.DataFrame({"x": []}))
        assert result["total_units"] == 0
        assert result["quality_distribution"] == {}

    def test_computes_quality_snr_firing_rate_stats(self):
        df = pd.DataFrame({
            "spike_times": [[0.1, 0.2], [], [0.3]],
            "quality": [1.0, 0.5, 1.0],
            "snr": [2.0, 0.5, 1.5],
            "firing_rate": [5.0, 0.1, 3.0],
        })
        result = audit_units(df)
        assert result["total_units"] == 3
        assert result["units_with_spike_times"] == 2
        assert result["quality_distribution"]["good_count"] == 2
        assert result["snr_stats"]["good_count"] == 2
        assert result["firing_rate_stats"]["max"] == pytest.approx(5.0)

    def test_missing_columns_produce_empty_sub_dicts(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = audit_units(df)
        assert result["quality_distribution"] == {}
        assert result["snr_stats"] == {}
        assert result["firing_rate_stats"] == {}


class TestAuditElectrodes:
    def test_counts_areas_and_unit_assignment(self):
        elec_df = pd.DataFrame({"location": ["V1, layer4", "V1, layer2", "PFC, layer5"]})
        units_df = pd.DataFrame({"peak_channel_id": [1, None, 3]})
        result = audit_electrodes(elec_df, units_df)
        assert result["total_electrodes"] == 3
        assert result["areas_represented"] == {"V1": 2, "PFC": 1}
        assert result["units_assigned"] == 2
        assert result["assignment_rate"] == pytest.approx(2 / 3)

    def test_missing_units_df_gives_zero_assignment(self):
        elec_df = pd.DataFrame({"location": ["V1"]})
        result = audit_electrodes(elec_df, units_df=None)
        assert result["units_assigned"] == 0
        assert result["assignment_rate"] == 0.0


class TestFilterByCriteria:
    def test_scalar_equality(self):
        df = pd.DataFrame({"area": ["V1", "V4", "V1"], "x": [1, 2, 3]})
        out = filter_by_criteria(df, {"area": "V1"})
        assert list(out["x"]) == [1, 3]

    def test_range_tuple(self):
        df = pd.DataFrame({"firing_rate": [1.0, 15.0, 50.0, 200.0]})
        out = filter_by_criteria(df, {"firing_rate": (10, 100)})
        assert list(out["firing_rate"]) == [15.0, 50.0]

    def test_list_membership(self):
        df = pd.DataFrame({"area": ["V1", "V4", "PFC"], "x": [1, 2, 3]})
        out = filter_by_criteria(df, {"area": ["V1", "V4"]})
        assert list(out["x"]) == [1, 2]

    def test_unknown_column_is_ignored_not_an_error(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        out = filter_by_criteria(df, {"nonexistent_col": "V1"})
        assert len(out) == 3

    def test_does_not_mutate_input(self):
        df = pd.DataFrame({"area": ["V1", "V4"], "x": [1, 2]})
        original = df.copy()
        filter_by_criteria(df, {"area": "V1"})
        pd.testing.assert_frame_equal(df, original)


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
