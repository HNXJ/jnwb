"""Unit tests for jnwb.metadata -- generic unit/electrode metadata extraction, QC
classification, and census reporting. The NWB-reading functions (get_all_units_metadata,
electrode_inventory) are exercised elsewhere against real files (omission/tests/); these tests
cover the pure DataFrame-transform functions with synthetic data, plus the public-API surface.
"""
from __future__ import annotations

import pandas as pd
import pytest

import jnwb
from jnwb.metadata import (
    classify_unit_quality, unit_census_report, get_snr_analysis, filter_by_criteria,
    audit_units, audit_electrodes, assign_quality_tier, get_all_units_metadata,
    electrode_inventory,
)


class TestNwbReadErrors:
    def test_corrupt_nwb_surfaces_error_when_raise(self, tmp_path):
        bad = tmp_path / "bad.nwb"
        bad.write_bytes(b"not an hdf5 file")
        with pytest.raises(OSError):
            get_all_units_metadata(bad, on_read_error="raise")

    def test_every_path_failing_is_not_an_empty_cohort(self, tmp_path):
        """`on_read_error='skip'` is for carrying on with a partial result in a
        multi-file call. With nothing read there is no partial result, and the empty frame
        this used to return claimed an empty cohort instead of a failed read -- reported
        only through `log.error`, which `pytest.warns` and `-W error` cannot see.
        """
        bad = tmp_path / "bad.nwb"
        bad.write_bytes(b"not an hdf5 file")
        with pytest.raises(RuntimeError, match="all 1 of 1 path"):
            get_all_units_metadata(bad)
        with pytest.raises(RuntimeError, match="all 1 of 1 path"):
            electrode_inventory(bad)

    def test_a_nonexistent_path_raises_like_every_other_reader(self, tmp_path):
        """`inspect`, `events` and `unit_spike_times` all raise FileNotFoundError here."""
        missing = tmp_path / "absent.nwb"
        for reader in (get_all_units_metadata, electrode_inventory):
            with pytest.raises(FileNotFoundError, match="not found"):
                reader(missing)
        for name in ("inspect", "events", "unit_spike_times"):
            with pytest.raises(FileNotFoundError):
                getattr(jnwb, name)(missing)


class TestDepthClassColumn:
    def test_a_multi_file_read_emits_depth_class_and_warns_once_for_the_layer_copy(
            self, tmp_path):
        """Each file is enriched separately; the deprecated copy is announced once per call."""
        from jnwb.testing.nwb_fixtures import write_synth_nwb

        paths = [tmp_path / "ses-01_a.nwb", tmp_path / "ses-02_b.nwb"]
        for path in paths:
            write_synth_nwb(path)
        with pytest.warns(FutureWarning, match=r"'layer'.*'depth_class'.*0\.2\.7") as record:
            units = get_all_units_metadata(paths)
        ours = [w for w in record if "depth_class" in str(w.message)]
        assert len(ours) == 1, [str(w.message) for w in ours]
        assert ours[0].filename == __file__
        assert set(units["session_id"]) == {1, 2}
        # The synthetic units carry no peak channel, so the class is the honest 'Unknown'.
        assert set(units["depth_class"]) == {"Unknown"}
        pd.testing.assert_series_equal(units["layer"], units["depth_class"], check_names=False)


def test_a_quality_filter_with_no_usable_quality_excludes_every_unit_loudly(tmp_path):
    """A filter nothing can pass must not become a filter nothing is subjected to."""
    from datetime import datetime, timezone

    import numpy as np
    import pynwb

    nwb = pynwb.NWBFile(session_description="q", identifier="q-1",
                        session_start_time=datetime.now(timezone.utc))
    nwb.add_unit_column(name="quality", description="quality")
    for i in range(3):
        nwb.add_unit(spike_times=[0.1 * (i + 1), 0.9], quality=np.nan)
    path = tmp_path / "ses-01_q.nwb"
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)

    with pytest.warns(RuntimeWarning, match="no usable value"):
        units = get_all_units_metadata(path, filter_quality=True)
    assert len(units) == 0
    assert len(get_all_units_metadata(path)) == 3


def test_a_quality_filter_excludes_a_unit_of_unknown_stability(tmp_path):
    from datetime import datetime, timezone

    import pynwb

    nwb = pynwb.NWBFile(session_description="q", identifier="q-2",
                        session_start_time=datetime.now(timezone.utc))
    nwb.add_unit_column(name="quality", description="quality")
    for i, label in enumerate(["good", "", "mua"]):
        nwb.add_unit(spike_times=[0.1 * (i + 1), 0.9], quality=label)
    path = tmp_path / "ses-01_q.nwb"
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)

    every = get_all_units_metadata(path)
    assert every["is_stable"].isna().tolist() == [False, True, False]
    assert get_all_units_metadata(path, filter_quality=True)["quality"].tolist() == ["good"]


class TestPublicImport:
    def test_importable_from_top_level_jnwb(self):
        from jnwb import (
            get_all_units_metadata, classify_unit_quality as pub_cuq,
            unit_census_report as pub_ucr, get_snr_analysis as pub_gsa,
            electrode_inventory, filter_by_criteria as pub_fbc,
            audit_units as pub_au, audit_electrodes as pub_ae,
            assign_quality_tier as pub_aqt,
        )
        assert pub_cuq is classify_unit_quality
        assert pub_ucr is unit_census_report
        assert pub_gsa is get_snr_analysis
        assert pub_fbc is filter_by_criteria
        assert pub_au is audit_units
        assert pub_ae is audit_electrodes
        assert pub_aqt is assign_quality_tier
        assert callable(get_all_units_metadata)
        assert callable(electrode_inventory)

    def test_listed_in_jnwb_all(self):
        import jnwb
        for name in ("get_all_units_metadata", "classify_unit_quality", "unit_census_report",
                     "get_snr_analysis", "electrode_inventory", "filter_by_criteria",
                     "audit_units", "audit_electrodes", "assign_quality_tier"):
            assert name in jnwb.__all__

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

    def test_unknown_column_raises_when_configured(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        with pytest.raises(ValueError, match="unknown column"):
            filter_by_criteria(df, {"typo_col": 1}, unknown="raise")

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
        "depth_class": ["Superficial", "Deep", "Superficial", "Deep"],
        # A caller's own column of the old name, with values that differ from depth_class.
        "layer": ["sup", "sup", "sup", "sup"],
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
        # Every unit's firing_rate < 10.0 -> every unit flagged, none critical (not in critical_cols list)
        assert (df["quality_class"] == "Fair").all()

    def test_custom_quality_and_snr_threshold_flags_poor(self):
        # Custom quality threshold 1.5 -> units with quality 1.0 (unit 1, 3, 4) fail critical threshold
        df = classify_unit_quality(_synthetic_units(), thresholds={"quality": 1.5})
        row1 = df[df["unit_id"] == 1].iloc[0]
        assert row1["quality_class"] == "Poor"
        assert "quality<1.5" in row1["issue_flags"]

    def test_does_not_mutate_input(self):
        original = _synthetic_units()
        original_copy = original.copy()
        classify_unit_quality(original)
        pd.testing.assert_frame_equal(original, original_copy)


class TestUnitCensusReport:
    def test_groups_by_default_columns(self):
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error", FutureWarning)
            census = unit_census_report(_synthetic_units())
        assert set(census["session_id"]) == {100, 101}
        assert "n_units" in census.columns
        # The default groups on the geometric depth class, not the deprecated column.
        assert set(census["depth_class"]) == {"Superficial", "Deep"}
        assert "layer" not in census.columns
        assert (census["n_units"] == 1).all()

    def test_groups_by_custom_columns(self):
        census = unit_census_report(_synthetic_units(), group_by=["area"])
        assert set(census["area"]) == {"FEF", "PFC"}
        assert (census["n_units"] == 2).all()

    def test_a_default_call_on_a_frame_with_only_layer_warns_that_depth_is_not_split(self):
        units = _synthetic_units().drop(columns="depth_class")
        units["layer"] = ["Superficial", "Deep", "Superficial", "Deep"]
        with pytest.warns(FutureWarning, match=r"'depth_class'.*'layer'"):
            census = unit_census_report(units)
        assert "layer" not in census.columns

    def test_missing_group_columns_are_dropped_with_a_warning(self):
        with pytest.warns(UserWarning, match="nonexistent_col"):
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


class TestAssignQualityTier:
    def test_quality_zero_is_mua(self):
        tier = assign_quality_tier(
            pd.Series([0, 0]), pd.Series([1.0, 1.0]), pd.Series([5.0, 5.0])
        )
        assert (tier == "mua").all()

    def test_quality_one_above_thresholds_is_stable(self):
        tier = assign_quality_tier(
            pd.Series([1]), pd.Series([0.99]), pd.Series([1.0]),
            presence_threshold=0.98, snr_threshold=0.5,
        )
        assert tier.iloc[0] == "stable"

    def test_quality_one_below_thresholds_is_unstable(self):
        tier = assign_quality_tier(
            pd.Series([1]), pd.Series([0.5]), pd.Series([1.0]),
            presence_threshold=0.98, snr_threshold=0.5,
        )
        assert tier.iloc[0] == "unstable"

    def test_missing_snr_is_unstable_not_stable(self):
        tier = assign_quality_tier(
            pd.Series([1]), pd.Series([0.99]), pd.Series([float("nan")]),
        )
        assert tier.iloc[0] == "unstable"


def _write_minimal_nwb(path):
    """Four electrodes and two units, enough for both readers."""
    from datetime import datetime, timezone

    import pynwb

    nwb = pynwb.NWBFile(
        session_description="s", identifier="i",
        session_start_time=datetime.now(timezone.utc),
    )
    device = nwb.create_device(name="probe")
    group = nwb.create_electrode_group(
        name="probeA", description="d", location="V1", device=device
    )
    for z in range(4):
        nwb.add_electrode(
            x=0.0, y=0.0, z=float(z), location="V1", group=group, group_name="probeA"
        )
    nwb.add_unit_column(name="peak_channel_id", description="peak channel")
    nwb.add_unit(spike_times=[0.1, 0.2], peak_channel_id=0.0)
    nwb.add_unit(spike_times=[0.3], peak_channel_id=1.0)
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


class TestSessionIdFromFilename:
    """05-23, second half. `electrode_inventory` called `int(stem)` unconditionally, so a
    readable 4-electrode file named `mm_depth.nwb` raised ValueError -- which the broad
    read-error tuple swallowed as a failed read, returning DataFrame (0, 0). The sibling
    `get_all_units_metadata` already had the int-or-string fallback and returned (2, 10).
    """

    def test_a_non_numeric_stem_still_returns_the_electrodes(self, tmp_path):
        path = _write_minimal_nwb(tmp_path / "mm_depth.nwb")
        elecs = electrode_inventory(path)
        units = get_all_units_metadata(path)
        assert len(elecs) == 4, "a readable file is not an empty cohort"
        assert len(units) == 2
        assert elecs["session_id"].unique().tolist() == ["mm_depth"]
        assert units["session_id"].unique().tolist() == ["mm_depth"]

    def test_a_numeric_session_stem_is_still_an_int(self, tmp_path):
        path = _write_minimal_nwb(tmp_path / "ses-260724_ecephys.nwb")
        assert electrode_inventory(path)["session_id"].unique().tolist() == [260724]
        assert get_all_units_metadata(path)["session_id"].unique().tolist() == [260724]

    def test_both_readers_agree_on_the_session_id(self, tmp_path):
        for name in ("mm_depth.nwb", "ses-260724_ecephys.nwb"):
            path = _write_minimal_nwb(tmp_path / name)
            assert (
                electrode_inventory(path)["session_id"].unique().tolist()
                == get_all_units_metadata(path)["session_id"].unique().tolist()
            )

    def test_one_bad_path_among_several_still_skips(self, tmp_path):
        """Per-file skipping is what on_read_error='skip' is for, and it survives."""
        good = _write_minimal_nwb(tmp_path / "ses-260724_ecephys.nwb")
        bad = tmp_path / "corrupt.nwb"
        bad.write_bytes(b"not an hdf5 file")
        assert len(electrode_inventory([good, bad])) == 4
        assert len(get_all_units_metadata([good, bad])) == 2
