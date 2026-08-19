import pytest
from pathlib import Path

import omission.jnwb_ext.diagnostics as diag
import omission.jnwb_ext.metadata as meta

NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"


def _skip_if_missing():
    if not Path(NWB_PATH).exists():
        pytest.skip("Real test-session NWB file is missing.")


def test_audit_session_against_real_nwb():
    _skip_if_missing()
    audit = diag.audit_session(NWB_PATH)

    assert audit["session_id"] == "230823"
    assert audit["nwb_file"] == "sub-C31o_ses-230823_rec.nwb"
    assert not audit["errors"]
    assert audit["session_info"]["subject_id"]
    assert audit["units"]["total_units"] > 0
    assert audit["electrodes"]["total_electrodes"] > 0


def test_compare_sessions_against_real_nwb():
    _skip_if_missing()
    comparison = diag.compare_sessions([NWB_PATH])

    assert len(comparison) == 1
    row = comparison.iloc[0]
    assert row["session_id"] == "230823"
    assert row["total_units"] > 0
    assert row["total_electrodes"] > 0


def test_get_all_units_metadata_against_real_nwb():
    _skip_if_missing()
    units = meta.get_all_units_metadata(NWB_PATH)

    assert len(units) > 0
    # Real anatomical enrichment must have run (jnwb.addressing.enrich_units_dataframe)
    for col in ["unit_id", "area", "layer", "is_stable", "stable_plus", "session_id"]:
        assert col in units.columns
    assert (units["session_id"] == 230823).all()
    # At least some units resolve to a real, non-null area
    assert units["area"].notna().any()


def test_get_all_units_metadata_quality_filter_reduces_rows():
    _skip_if_missing()
    all_units = meta.get_all_units_metadata(NWB_PATH)
    filtered = meta.get_all_units_metadata(NWB_PATH, filter_quality=True, quality_threshold=1.0)

    assert len(filtered) <= len(all_units)
    assert (filtered["quality"] >= 1.0).all()


def test_get_all_units_metadata_missing_file_returns_empty_not_a_crash():
    units = meta.get_all_units_metadata("D:/analysis/nwb/does_not_exist_12345.nwb")
    assert units.empty


def test_get_all_units_metadata_snr_is_numeric_not_object():
    # Regression: enrich_units_dataframe only coerced firing_rate/waveform_duration
    # to numeric, not snr - which is dtype=str on some sessions (e.g. C31o) and
    # float64 on others (e.g. V182o). unit_census_report's snr aggregation used
    # to raise "TypeError: agg function failed [how->mean,dtype->object]" on
    # sessions where snr came through as strings.
    _skip_if_missing()
    units = meta.get_all_units_metadata(NWB_PATH)
    assert units["snr"].dtype.kind == "f"


def test_unit_census_report_against_real_nwb():
    _skip_if_missing()
    units = meta.get_all_units_metadata(NWB_PATH)
    census = meta.unit_census_report(units, group_by=["session_id", "area"])

    assert "n_units" in census.columns
    assert "snr_mean" in census.columns
    assert census["n_units"].sum() == len(units)
