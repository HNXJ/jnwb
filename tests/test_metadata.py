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
    def test_a_multi_file_read_emits_depth_class_and_no_layer_column(self, tmp_path):
        """Each file is enriched separately; no ``layer`` column is written or warned about."""
        import warnings

        from jnwb.testing.nwb_fixtures import write_synth_nwb

        paths = [tmp_path / "ses-01_a.nwb", tmp_path / "ses-02_b.nwb"]
        for path in paths:
            write_synth_nwb(path)
        with warnings.catch_warnings(record=True) as record:
            warnings.simplefilter("always")
            units = get_all_units_metadata(paths)
        about_layer = [
            str(w.message) for w in record
            if issubclass(w.category, (FutureWarning, DeprecationWarning))
            or "layer" in str(w.message)
        ]
        assert about_layer == []
        assert "layer" not in units.columns
        assert set(units["session_id"]) == {1, 2}
        # The synthetic units carry no peak channel, so the class is the honest 'Unknown'.
        assert set(units["depth_class"]) == {"Unknown"}


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
        with pytest.warns(UserWarning, match=r"'depth_class'.*'layer' column is not read"):
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


class TestUndefinedQualityInput:
    """A quality function given a value it cannot compare reports that, never a verdict."""

    def test_classify_unit_quality_never_passes_undefined_input_as_good(self):
        nan = float("nan")
        frames = {
            "nan": pd.DataFrame({"quality": [nan, 1.0], "snr": [2.0, nan],
                                 "firing_rate": [5.0, 5.0]}),
            "labels": pd.DataFrame({"quality": ["mua", "noise"], "snr": [2.0, 2.0],
                                    "firing_rate": [5.0, 5.0]}),
            "absent": pd.DataFrame({"firing_rate": [5.0]}),
        }
        for case, frame in frames.items():
            out = classify_unit_quality(frame)
            assert (out["quality_class"] == "Unknown").all(), case
            assert not out["is_valid"].any(), case
        nan_flags = classify_unit_quality(frames["nan"])["issue_flags"].tolist()
        assert nan_flags == [["quality undefined"], ["snr undefined"]]
        absent_flags = classify_unit_quality(frames["absent"])["issue_flags"].iloc[0]
        assert absent_flags == ["quality absent", "snr absent"]
        # A measured critical failure outranks an undefined metric.
        mixed = pd.DataFrame({"quality": [nan], "snr": [0.2], "firing_rate": [5.0]})
        assert classify_unit_quality(mixed)["quality_class"].tolist() == ["Poor"]

    def test_assign_quality_tier_shares_enrich_rule_and_reports_undefined_as_unknown(self):
        from jnwb.addressing import enrich_units_dataframe

        nan = float("nan")
        # A candidate under enrich's is_stable is a stable/unstable tier; an unknown is_stable
        # is an unknown tier; a non-candidate is 'mua' only when declared so (0 or 'mua').
        expected = {0: "mua", 1: "stable", 2: "stable", 0.5: "unknown", -1: "unknown",
                    "good": "stable", "sua": "stable", "mua": "mua", " MUA ": "mua",
                    "noise": "unknown", "unsorted": "unknown", nan: "unknown"}
        for quality, tier_expected in expected.items():
            q = pd.Series([quality, None], dtype=object)
            tier = assign_quality_tier(q, pd.Series([1.0, 1.0]), pd.Series([5.0, 5.0]))
            assert tier.iloc[0] == tier_expected, quality
            enriched = enrich_units_dataframe(pd.DataFrame({"quality": q}), None)
            stable = enriched["is_stable"].iloc[0] if "is_stable" in enriched else pd.NA
            if pd.isna(stable):
                assert tier_expected == "unknown", quality
            else:
                assert bool(stable) == (tier_expected == "stable"), quality
        # The same arguments move both functions the same way.
        q = pd.Series([1.0, 2.0, 3.0])
        tier = assign_quality_tier(q, pd.Series([1.0] * 3), pd.Series([5.0] * 3),
                                   stable_threshold=2.0)
        enriched = enrich_units_dataframe(pd.DataFrame({"quality": q}), None,
                                          stable_threshold=2.0)["is_stable"]
        assert tier.tolist() == ["unknown", "stable", "stable"]
        assert enriched.tolist() == [False, True, True]
        labelled = assign_quality_tier(pd.Series(["Accepted ", "good", "mua"]),
                                       pd.Series([1.0] * 3), pd.Series([5.0] * 3),
                                       stable_labels=("accepted",))
        assert labelled.tolist() == ["stable", "unknown", "mua"]

    def test_assign_quality_tier_aligns_presence_and_snr_or_refuses(self):
        import numpy as np

        q = pd.Series([1, 1, 0], index=[10, 11, 12])
        tier = assign_quality_tier(q, np.array([0.99, 0.5, 0.99]), np.array([5.0, 5.0, 5.0]))
        assert tier.tolist() == ["stable", "unstable", "mua"]
        assert tier.index.tolist() == [10, 11, 12]
        on_index = assign_quality_tier(q, pd.Series([0.99, 0.5, 0.99], index=q.index),
                                       pd.Series([5.0] * 3, index=q.index))
        assert on_index.tolist() == ["stable", "unstable", "mua"]
        with pytest.raises(ValueError, match="trial_presence_fraction is not on the units"):
            assign_quality_tier(q, pd.Series([0.99] * 3), pd.Series([5.0] * 3, index=q.index))
        with pytest.raises(ValueError, match="snr is not on the units"):
            assign_quality_tier(q, np.array([0.99] * 3), pd.Series([5.0] * 3, index=[1, 2, 3]))
        with pytest.raises(ValueError, match="quality has 3 units"):
            assign_quality_tier(q, np.array([0.99] * 2), np.array([5.0] * 3))

    def test_assign_quality_tier_aligns_a_reordered_index_by_label(self):
        q = pd.Series([1, 1, 0], index=[10, 11, 12])
        presence = pd.Series([0.99, 0.5, 0.99], index=q.index)
        snr = pd.Series([5.0] * 3, index=q.index)
        permuted = presence.loc[[12, 10, 11]]
        assert assign_quality_tier(q, permuted, snr).tolist() == ["stable", "unstable", "mua"]
        # A groupby result comes back sorted by its key, not in the frame's row order.
        units = pd.DataFrame({"unit": ["c", "a", "b"], "quality": [1, 1, 0],
                              "presence": [0.99, 0.5, 0.99]}).set_index("unit")
        by_unit = units.groupby(level="unit")["presence"].mean()
        assert by_unit.index.tolist() == ["a", "b", "c"]
        tier = assign_quality_tier(units["quality"], by_unit,
                                   pd.Series([5.0] * 3, index=units.index))
        assert tier.tolist() == ["stable", "unstable", "mua"]
        with pytest.raises(ValueError, match=r"missing \[12\]"):
            assign_quality_tier(q, presence.rename({12: 13}), snr)
        with pytest.raises(ValueError, match=r"duplicated \[10\]"):
            assign_quality_tier(q, pd.concat([presence, presence.loc[[10]]]), snr)
        with pytest.raises(ValueError, match="quality has 3 units"):
            assign_quality_tier(q, 0.99, snr)

    def test_assign_quality_tier_reads_nullable_codes_and_no_bool_or_time_as_a_code(self):
        na = pd.NA
        for dtype, values in (("Int64", [0, 1, na]), ("Float64", [0.0, 1.0, na])):
            tier = assign_quality_tier(pd.Series(values, dtype=dtype), pd.Series([1.0] * 3),
                                       pd.Series([5.0] * 3))
            assert tier.tolist() == ["mua", "stable", "unknown"], dtype
        presence, snr = pd.Series([1.0] * 3), pd.Series([5.0] * 3)
        for quality in (pd.Series([True, False, na], dtype="boolean"),
                        pd.Series([True, False, False]),
                        pd.Series([True, False, 0], dtype=object),
                        pd.to_datetime(pd.Series(["2026-01-01"] * 3)),
                        pd.to_timedelta(pd.Series([0, 1, 2]), unit="s")):
            tier = assign_quality_tier(quality, presence, snr).tolist()
            expected = (["unknown", "unknown", "mua"] if quality.dtype == object
                        else ["unknown"] * 3)
            assert tier == expected, quality.dtype

    def test_quality_cut_offs_are_arguments(self, tmp_path):
        import pynwb
        from datetime import datetime, timezone

        snr = pd.DataFrame({"snr": [0.7, 0.7], "quality": [1.5, 1.5]})
        assert audit_units(snr)["snr_stats"]["good_rate"] == 0.0
        audit = audit_units(snr, snr_threshold=0.5, quality_threshold=2.0)
        assert audit["snr_stats"]["good_rate"] == 1.0
        assert audit["quality_distribution"]["good_count"] == 0

        nwb = pynwb.NWBFile(session_description="q", identifier="q-3",
                            session_start_time=datetime.now(timezone.utc))
        nwb.add_unit_column(name="quality", description="quality")
        for i, label in enumerate(["good", "sua", "accepted"]):
            nwb.add_unit(spike_times=[0.1 * (i + 1), 0.9], quality=label)
        path = tmp_path / "ses-01_q.nwb"
        with pynwb.NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
        kept = get_all_units_metadata(path, filter_quality=True, stable_labels=("accepted",))
        assert kept["quality"].tolist() == ["accepted"]

        # audit_units counts text labels by the shared rule; its default keeps the released
        # count of 'good' alone, and the caller widens it.
        labels = pd.DataFrame({"quality": ["good", " SUA", "accepted", "mua"]})
        assert audit_units(labels)["quality_distribution"]["good_count"] == 1
        assert audit_units(labels, stable_labels=("accepted",))[
            "quality_distribution"]["good_count"] == 1
        assert audit_units(labels, stable_labels=("good", "sua", "single", "stable", "clean"))[
            "quality_distribution"]["good_count"] == 1  # ' SUA' is not stripped
        # The released matching: case-insensitive, whitespace kept.
        assert audit_units(pd.DataFrame({"quality": [" good", "GOOD"]}))[
            "quality_distribution"]["good_count"] == 1

        numeric = pd.DataFrame({"quality": [1.0, 2.0]})
        path = tmp_path / "ses-02_q.nwb"
        nwb = pynwb.NWBFile(session_description="q", identifier="q-4",
                            session_start_time=datetime.now(timezone.utc))
        nwb.add_unit_column(name="quality", description="quality")
        for i, value in enumerate(numeric["quality"]):
            nwb.add_unit(spike_times=[0.1 * (i + 1), 0.9], quality=value)
        with pynwb.NWBHDF5IO(str(path), "w") as io:
            io.write(nwb)
        units = get_all_units_metadata(path, stable_threshold=2.0)
        assert units["is_stable"].tolist() == [False, True]

        # A bare string would be read as a set of one-letter labels.
        from jnwb.addressing import enrich_units_dataframe
        q = pd.Series(["good"])
        calls = {
            "enrich_units_dataframe": lambda: enrich_units_dataframe(
                pd.DataFrame({"quality": q}), None, stable_labels="good"),
            "audit_units": lambda: audit_units(pd.DataFrame({"quality": q}),
                                               stable_labels="good"),
            "assign_quality_tier": lambda: assign_quality_tier(
                q, pd.Series([1.0]), pd.Series([5.0]), stable_labels="good"),
            "get_all_units_metadata": lambda: get_all_units_metadata(
                path, stable_labels="good"),
        }
        for name, call in calls.items():
            with pytest.raises(TypeError, match=f"{name}: stable_labels"):
                call()

    def test_audit_units_reports_one_value_spread_as_nan_and_names_a_bad_unit(self):
        import numpy as np

        audit = audit_units(pd.DataFrame({"quality": [1.0], "snr": [2.0]}))
        assert np.isnan(audit["quality_distribution"]["std"])
        assert np.isnan(audit["snr_stats"]["std"])
        bad = pd.DataFrame({"unit_id": [11, 12],
                            "spike_times": [np.array([0.1]), float("nan")]})
        with pytest.raises(TypeError, match="unit 12"):
            audit_units(bad)

    def test_compare_old_new_criteria_refuses_undefined_classes_and_duplicate_keys(self):
        import inspect

        from jnwb.metadata import compare_old_new_criteria

        keys = dict(new_key=("session", "unit_row"), old_key=("session_prefix", "unit_row_idx"))
        old = pd.DataFrame({"session_prefix": ["s"] * 4, "unit_row_idx": [0, 1, 2, 3],
                            "keep_old": [True, False, True, False]})
        new = pd.DataFrame({"session": ["s"] * 4, "unit_row": [0, 1, 2, 3],
                            "keep": pd.array([True, None, pd.NA, float("nan")], dtype=object)})
        out = compare_old_new_criteria(new, old, "keep", "keep_old", **keys)
        assert out["transition"].tolist() == ["unchanged_included", "unknown", "unknown",
                                              "unknown"]
        boolean = new.assign(keep=pd.array([True, None, None, False], dtype="boolean"))
        out = compare_old_new_criteria(boolean, old, "keep", "keep_old", **keys)
        assert out["transition"].tolist() == ["unchanged_included", "unknown", "unknown",
                                              "unchanged_excluded"]

        duplicated = pd.concat([old, old.iloc[[0]]], ignore_index=True)
        with pytest.raises(ValueError, match="old_df has more than one row"):
            compare_old_new_criteria(new, duplicated, "keep", "keep_old", **keys)
        new_duplicated = pd.concat([new, new.iloc[[0]]], ignore_index=True)
        with pytest.raises(ValueError, match="new_df has more than one row"):
            compare_old_new_criteria(new_duplicated, old, "keep", "keep_old", **keys)

        signature = inspect.signature(compare_old_new_criteria)
        for name in ("new_key", "old_key"):
            assert signature.parameters[name].default is inspect.Parameter.empty, name

    def test_compare_old_new_criteria_refuses_a_non_boolean_class_by_name(self):
        from jnwb.metadata import compare_old_new_criteria

        keys = dict(new_key=("s", "u"), old_key=("s", "u"))
        old = pd.DataFrame({"s": ["x"] * 2, "u": [0, 1], "old": [True, False]})
        for bad in ("False", "no", 2):
            new = pd.DataFrame({"s": ["x"] * 2, "u": [0, 1], "new": [True, bad]})
            with pytest.raises(ValueError, match=r"new_df column 'new' holds"):
                compare_old_new_criteria(new, old, "new", "old", **keys)
        new = pd.DataFrame({"s": ["x"] * 2, "u": [0, 1], "new": [True, False]})
        with pytest.raises(ValueError, match=r"old_df column 'old' holds 'yes'"):
            compare_old_new_criteria(new, old.assign(old=["yes", "no"]), "new", "old", **keys)
        # 1 and 0 are the boolean classes, as released.
        out = compare_old_new_criteria(new.assign(new=[1, 0]), old.assign(old=[0, 0]),
                                       "new", "old", **keys)
        assert out["transition"].tolist() == ["gained", "unchanged_excluded"]

    def test_compare_old_new_criteria_reads_a_missing_old_class_as_unknown(self):
        from jnwb.metadata import compare_old_new_criteria

        keys = dict(new_key=("s", "u"), old_key=("s", "u"))
        new = pd.DataFrame({"s": ["x"] * 4, "u": [0, 1, 2, 3], "new": [True, False, True, True]})
        old = pd.DataFrame({"s": ["x"] * 3, "u": [0, 1, 2],
                            "old": [float("nan"), None, False]})
        out = compare_old_new_criteria(new, old, "new", "old", **keys)
        # A missing old class is undefined; a unit with no old row is still not screened.
        assert out["transition"].tolist() == ["unknown", "unknown", "gained", "gained"]
        assert out["old_screened"].tolist() == [False, False, True, False]

    def test_get_snr_analysis_example_states_the_inclusive_test(self):
        doc = get_snr_analysis.__doc__
        assert "SNR>=1.0" in doc
        assert "SNR>1.0" not in doc


class TestDegenerateCutOffs:
    """A cut-off or class that passes or fails every unit alike is refused by name."""

    def test_classify_unit_quality_refuses_degenerate_thresholds_by_name(self):
        frame = pd.DataFrame({"quality": [0.0, 1.0], "snr": [0.1, 2.0],
                              "firing_rate": [1.0, 1.0]})
        with pytest.raises(ValueError, match="classify_unit_quality: thresholds is empty"):
            classify_unit_quality(frame, {})
        for bad in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match=r"thresholds\['quality'\] is"):
                classify_unit_quality(frame, {"quality": bad})
        with pytest.raises(TypeError, match=r"thresholds\['snr'\] must be a finite number"):
            classify_unit_quality(frame, {"snr": None})
        repeated = pd.concat([frame, frame[["quality"]]], axis=1)
        with pytest.raises(ValueError, match=r"column\(s\) \['quality'\] occur more than once"):
            classify_unit_quality(repeated)
        # A finite cut-off keeps its released flag text.
        flags = classify_unit_quality(frame, {"quality": 1})["issue_flags"].tolist()
        assert flags == [["quality<1"], []]

    def test_audit_units_refuses_a_non_finite_cut_off(self):
        frame = pd.DataFrame({"quality": [0.0, 1.0], "snr": [0.1, 2.0]})
        for name in ("quality_threshold", "snr_threshold"):
            for bad in (float("nan"), float("inf")):
                with pytest.raises(ValueError, match=f"audit_units: {name} is"):
                    audit_units(frame, **{name: bad})

    def test_stability_rule_refuses_a_degenerate_threshold_or_empty_labels(self):
        from jnwb.addressing import enrich_units_dataframe

        q = pd.Series([0.0, 1.0])
        calls = {
            "enrich_units_dataframe": lambda **kw: enrich_units_dataframe(
                pd.DataFrame({"quality": q}), None, **kw),
            "assign_quality_tier": lambda **kw: assign_quality_tier(
                q, pd.Series([1.0] * 2), pd.Series([5.0] * 2), **kw),
            "audit_units": lambda **kw: audit_units(pd.DataFrame({"quality": ["good"]}), **kw),
        }
        for caller, call in calls.items():
            with pytest.raises(ValueError, match=f"{caller}: stable_labels is empty"):
                call(stable_labels=())
            if caller == "audit_units":
                continue
            for bad in (float("nan"), float("inf"), float("-inf")):
                with pytest.raises(ValueError, match=f"{caller}: stable_threshold is"):
                    call(stable_threshold=bad)
            with pytest.raises(TypeError, match=f"{caller}: stable_threshold must be"):
                call(stable_threshold=None)
        for name in ("presence_threshold", "snr_threshold"):
            with pytest.raises(ValueError, match=f"assign_quality_tier: {name} is"):
                calls["assign_quality_tier"](**{name: float("nan")})

    def test_an_infinite_quality_is_undefined(self):
        from jnwb.addressing import enrich_units_dataframe

        inf = float("inf")
        q = pd.Series([inf, -inf, 1.0, 0.0])
        tier = assign_quality_tier(q, pd.Series([1.0] * 4), pd.Series([5.0] * 4))
        assert tier.tolist() == ["unknown", "unknown", "stable", "mua"]
        stable = enrich_units_dataframe(pd.DataFrame({"quality": q}), None)["is_stable"]
        assert stable.isna().tolist() == [True, True, False, False]
        assert stable.iloc[2:].tolist() == [True, False]
        text = enrich_units_dataframe(pd.DataFrame({"quality": ["inf", "1"]}), None)
        assert text["is_stable"].isna().tolist() == [True, False]

    def test_assign_quality_tier_aligns_a_superset_index_by_label(self):
        q = pd.Series([1, 1, 0], index=["a", "b", "c"])
        # Computed on the full table; quality is a filtered subset. Extra labels, none missing.
        presence = pd.Series([0.1, 0.99, 0.5, 0.99], index=["z", "a", "b", "c"])
        snr = pd.Series([5.0, 5.0, 5.0, 0.0], index=["a", "b", "c", "y"])
        tier = assign_quality_tier(q, presence, snr)
        assert tier.tolist() == ["stable", "unstable", "mua"]
        assert tier.index.tolist() == ["a", "b", "c"]

    def test_assign_quality_tier_refuses_a_masked_entry(self):
        import numpy as np

        q = pd.Series([1, 1, 0])
        masked = np.ma.masked_array([0.99, 0.99, 0.99], mask=[True, False, False])
        with pytest.raises(ValueError, match="trial_presence_fraction is a masked array"):
            assign_quality_tier(q, masked, np.array([5.0] * 3))
        with pytest.raises(ValueError, match="snr is a masked array"):
            assign_quality_tier(q, np.array([0.99] * 3),
                                np.ma.masked_array([5.0] * 3, mask=[False, True, False]))
        unmasked = np.ma.masked_array([0.99, 0.5, 0.99], mask=False)
        assert assign_quality_tier(q, unmasked, np.array([5.0] * 3)).tolist() == [
            "stable", "unstable", "mua"]
        filled = masked.filled(np.nan)
        assert assign_quality_tier(q, filled, np.array([5.0] * 3)).tolist() == [
            "unstable", "stable", "mua"]

    def test_audit_units_states_that_its_nan_is_not_strict_json(self):
        import json

        import numpy as np

        audit = audit_units(pd.DataFrame({"quality": [1.0], "snr": [2.0]}))
        assert np.isnan(audit["quality_distribution"]["std"])
        with pytest.raises(ValueError):
            json.dumps(audit, allow_nan=False)
        doc = " ".join(audit_units.__doc__.split())
        assert "not strict JSON" in doc
        assert "allow_nan=False" in doc
