"""
Tests for jnwb/factories.py's result_from_decoding_analysis and
result_from_tfr_analysis.

These functions previously fabricated statistics via np.random regardless of
whether real data was available (a real bug found during a full-repo audit).
These tests lock in the fix: both functions must return an honest
'insufficient_data' status rather than fabricated numbers when real
computation isn't possible, and must call the real omission.jnwb_ext.decoding /
session.tfr_from_preprocessed path when it is.
"""

import math
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

import omission as oa
from jnwb.ontology import Query, Dataset, Alignment, AlignedDataset, EpochCollection, Question
from omission.jnwb_ext.factories import result_from_decoding_analysis, result_from_tfr_analysis, dataset_from_session

REAL_NWB_PATH = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"


def _make_epochs(area, condition: str, n_trials: int = 10) -> EpochCollection:
    import pandas as pd

    areas = [area] if area else None
    query = Query(sessions=["fake_session"], areas=areas, units=None, correct_only=True)
    dataset = Dataset(query=query, sessions=["fake_session"], units=pd.DataFrame(), metadata={})
    alignment = Alignment(name="p1_relative", reference_event="stimulus_onset", phase_number=2)
    aligned = AlignedDataset(dataset=dataset, alignment=alignment)
    epochs_df = pd.DataFrame({
        "start_time": np.arange(n_trials, dtype=float),
        "trial_num": np.arange(n_trials),
    })
    return EpochCollection(aligned_dataset=aligned, condition=condition, phase=2,
                            correct_only=True, epochs_df=epochs_df)


def _make_question(signals):
    return Question(
        hypothesis="test hypothesis",
        signals=signals,
        contrast="A vs B",
        inference_unit="unit",
    )


class TestDecodingFactoryNoFabrication:
    def test_missing_epochs_b_returns_insufficient_data_not_random(self):
        session = MagicMock()
        epochs = _make_epochs(area="V1", condition="AAAB")
        question = _make_question(["spike_times"])

        result = result_from_decoding_analysis(question, epochs, session, epochs_b=None)

        assert result.statistics["status"] == "insufficient_data"
        assert math.isnan(result.statistics["accuracy_mean"])
        assert result.statistics["accuracy_by_fold"] == []

    def test_real_decode_stimulus_identity_is_called_when_epochs_b_given(self):
        session = MagicMock()
        epochs_a = _make_epochs(area="V1", condition="AAAB")
        epochs_b = _make_epochs(area="V1", condition="BBBA")
        question = _make_question(["spike_times"])

        fake_dec_result = {
            "status": "success",
            "accuracy": 0.72,
            "f1": 0.70,
            "auc": 0.75,
            "majority_baseline_accuracy": 0.55,
            "fold_accuracies": [0.7, 0.75, 0.71],
        }

        import omission.jnwb_ext.factories as factories_mod
        original = factories_mod.decode_stimulus_identity if hasattr(factories_mod, "decode_stimulus_identity") else None

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("omission.jnwb_ext.decoding.decode_stimulus_identity", MagicMock(return_value=fake_dec_result))
            result = result_from_decoding_analysis(question, epochs_a, session, epochs_b=epochs_b)

        assert result.statistics["status"] == "success"
        assert result.statistics["accuracy_mean"] == 0.72
        assert result.statistics["f1_mean"] == 0.70
        assert result.statistics["auc_mean"] == 0.75
        assert result.statistics["majority_baseline_accuracy"] == 0.55
        assert result.statistics["accuracy_by_fold"] == [0.7, 0.75, 0.71]

    def test_never_returns_np_random_looking_values_without_real_call(self):
        """Regression guard: accuracy must not be a plausible-looking random
        value in [0.55, 0.75] when epochs_b is missing -- it must be NaN."""
        session = MagicMock()
        epochs = _make_epochs(area="V1", condition="AAAB")
        question = _make_question(["spike_times"])

        for _ in range(5):
            result = result_from_decoding_analysis(question, epochs, session, epochs_b=None)
            assert math.isnan(result.statistics["accuracy_mean"]), (
                "accuracy_mean should always be NaN with no epochs_b, never a "
                "fabricated random value"
            )


class TestTFRFactoryNoFabrication:
    def test_missing_tfr_array_returns_insufficient_data_not_random(self):
        session = MagicMock()
        session.tfr_from_preprocessed.return_value = None
        epochs = _make_epochs(area="MT", condition="AAXB")
        question = _make_question(["lfp"])

        result = result_from_tfr_analysis(question, epochs, session)

        assert result.statistics["status"] == "insufficient_data"
        assert result.statistics["strongest_band"] is None
        for band_name, stats in result.statistics["band_statistics"].items():
            assert math.isnan(stats["power_change_db"])

    def test_real_tfr_array_produces_real_band_stats(self):
        session = MagicMock()
        rng = np.random.default_rng(0)
        # (n_trials, n_channels, n_freqs, n_times) matching the real contract
        n_freqs, n_times = 99, 500
        fake_tfr = rng.uniform(0.1, 1.0, size=(5, 3, n_freqs, n_times)).astype(np.float32)
        # Inject a genuine response increase at low_gamma-band frequencies post-stimulus
        freqs = np.arange(3, 201, 2)[:n_freqs]
        times_ms = -1000.0 + np.arange(n_times) * 10.0
        gamma_idx = np.where((freqs >= 30) & (freqs < 55))[0]
        response_idx = np.where((times_ms >= 0) & (times_ms <= 500))[0]
        fake_tfr[np.ix_(range(5), range(3), gamma_idx, response_idx)] *= 3.0
        session.tfr_from_preprocessed.return_value = fake_tfr

        epochs = _make_epochs(area="MT", condition="AAXB")
        question = _make_question(["lfp"])

        result = result_from_tfr_analysis(question, epochs, session)

        assert result.statistics["status"] == "success"
        assert result.statistics["strongest_band"] == "low_gamma"
        gamma_stats = result.statistics["band_statistics"]["low_gamma"]
        assert gamma_stats["power_change_db"] > 0
        assert not math.isnan(gamma_stats["baseline_power_db"])

    def test_no_np_random_fabrication_when_area_missing(self):
        session = MagicMock()
        epochs = _make_epochs(area=None, condition="AAXB")
        question = _make_question(["lfp"])

        result = result_from_tfr_analysis(question, epochs, session)

        assert result.statistics["status"] == "insufficient_data"
        session.tfr_from_preprocessed.assert_not_called()


class TestDatasetFromSessionUnitsFilter:
    """
    Regression test for a real bug found 2026-07-12: dataset_from_session
    hardcoded units_df['cluster_id'] to filter by query.units, but
    session.get_units() always runs enrich_units_dataframe, which renames
    cluster_id -> unit_id. Every real call with query.units set raised
    KeyError: 'cluster_id'. This path was never exercised anywhere else in
    the codebase or test suite, which is why it went undetected.

    query.units is matched against the raw DataFrame row position (not the
    'unit_id' column) for consistency with the rest of the pipeline -
    omission.jnwb_ext.unit_classification.classify_session_units's default
    (unit_ids = list(units_df.index)) and scripts/classify_units_shuffle_sso.py
    both treat row position as the actual unit identity, since the 'unit_id'
    column (renamed from cluster_id) is a per-probe-local id that is not
    globally unique within a session.
    """

    def _skip_if_missing(self):
        if not Path(REAL_NWB_PATH).exists():
            pytest.skip("Real test-session NWB file is missing.")

    def test_query_units_filter_does_not_crash(self):
        self._skip_if_missing()
        session = oa.read(REAL_NWB_PATH)
        row_positions = session.get_units().index[:3].tolist()
        query = Query(sessions=session.nwb_path.stem, units=row_positions)

        dataset = dataset_from_session(session, query)

        assert len(dataset.units) == 3
        assert set(dataset.units.index) == set(row_positions)

    def test_query_units_filter_none_returns_all_units(self):
        self._skip_if_missing()
        session = oa.read(REAL_NWB_PATH)
        query = Query(sessions=session.nwb_path.stem, units=None)

        dataset = dataset_from_session(session, query)

        assert len(dataset.units) == len(session.get_units())
