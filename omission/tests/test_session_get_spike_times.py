from pathlib import Path

import pytest

import omission as oa

NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"


def _skip_if_missing():
    if not Path(NWB_PATH).exists():
        pytest.skip("Real test-session NWB file is missing.")


def test_get_spike_times_matches_by_raw_row_position():
    # session.get_spike_times(unit_id) resolves by the DataFrame's raw row
    # position - the actual, established identity convention used throughout
    # the real pipeline (omission.jnwb_ext.unit_classification.classify_session_units's
    # default `unit_ids = list(units_df.index)`, scripts/classify_units_shuffle_sso.py,
    # scripts/filter_units.py, scripts/list_stable_plus_units.py). Row
    # position is always globally unique within a session (pandas
    # RangeIndex), unlike the separate 'unit_id' DataFrame column (a
    # per-probe-local kilosort id, renamed from cluster_id, that resets to 0
    # on every probe - confirmed 2026-07-12 it can collide across 3+ areas
    # within a single session). This locks in that get_spike_times keeps
    # using row position as primary, not the column.
    _skip_if_missing()
    session = oa.read(NWB_PATH)
    units = session.get_units()
    row_position = units.index[10]

    spikes = session.get_spike_times(row_position)
    expected = units.loc[row_position, "spike_times"]

    assert spikes is not None
    assert len(spikes) == len(expected)


def test_get_spike_times_returns_none_for_out_of_range_id():
    _skip_if_missing()
    session = oa.read(NWB_PATH)
    n_units = len(session.get_units())

    result = session.get_spike_times(n_units + 10_000)

    assert result is None


def test_unit_id_column_is_numeric_across_sessions():
    # Regression test: enrich_units_dataframe's rename step (cluster_id ->
    # unit_id) never coerced the column to numeric. On this session it came
    # through as dtype=object holding strings like '156.0'. This column is
    # informational metadata (not the identity key used by get_spike_times/
    # classify_session_units, which use raw row position), but any code that
    # does inspect it directly (CSV exports, manual filtering) should get a
    # real numeric dtype rather than silently-unmatchable strings.
    _skip_if_missing()
    session = oa.read(NWB_PATH)
    assert session.get_units()["unit_id"].dtype.kind == "f"
