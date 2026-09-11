"""§1 harness: deterministic synthetic NWB fixtures."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

import h5py
import numpy as np
import pytest
from pynwb import NWBHDF5IO

from jnwb.nwb_io import read_nwb
from jnwb.testing.nwb_fixtures import (
    CODE_LABEL_A,
    CODE_LABEL_B,
    CODE_NUMERIC_A,
    CODE_NUMERIC_B,
    FLASH_TABLE,
    RF_TABLE,
    TASK_TABLE,
    SynthNWBBuildOptions,
    build_synth_nwb,
    canonical_co_resident_options,
    lfp_wrapped_options,
    numeric_codes_options,
    task_only_options,
    write_synth_nwb,
)

FORBIDDEN_FIXTURE_TOKENS = (
    "omission_glo_passive",
    "rf_mapping_v2",
    "AXAB",
    "BXBA",
    "omission-linked",
    "sub-C31o",
    "sub-V182o",
)


def _read_interval_df(nwb_path: Path, table_name: str):
    with NWBHDF5IO(str(nwb_path), "r") as io:
        nwb = io.read()
        assert table_name in nwb.intervals
        return nwb.intervals[table_name].to_dataframe()


@pytest.fixture(params=[
    canonical_co_resident_options(),
    lfp_wrapped_options(),
    numeric_codes_options(),
    task_only_options(),
], ids=["co_resident", "lfp_wrapped", "numeric_codes", "task_only"])
def variant_options(request):
    return request.param


class TestSynthNWBBuild:
    def test_write_and_reopen_pynwb(self, variant_options):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            receipt = write_synth_nwb(path, variant_options)
            with NWBHDF5IO(str(path), "r") as io:
                nwb = io.read()
            assert nwb.identifier == "TEST_SYNTH_CANONICAL"
            assert TASK_TABLE in nwb.intervals
            assert receipt.task_table == TASK_TABLE

    def test_read_through_jnwb_io(self, variant_options):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, variant_options)
            nwb = read_nwb(path)
            assert TASK_TABLE in nwb.intervals

    def test_interval_tables_and_columns_co_resident(self):
        opts = canonical_co_resident_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            task_df = _read_interval_df(path, TASK_TABLE)
            rf_df = _read_interval_df(path, RF_TABLE)
            flash_df = _read_interval_df(path, FLASH_TABLE)

        for col in (
            "start_time",
            "stop_time",
            "codes",
            "task_condition_number",
            "stimulus_number",
            "trial_num",
            "correct",
            "marker_flag",
        ):
            assert col in task_df.columns

        for col in (
            "codes",
            "x_position",
            "y_position",
            "x_position_negative",
            "y_position_negative",
            "contrast",
            "size",
            "spatial_frequency",
        ):
            assert col in rf_df.columns
        assert "task_condition_number" not in rf_df.columns

        for col in (
            "codes",
            "stimulus_number",
            "task_condition_number",
            "trial_num",
            "task_block_number",
        ):
            assert col in flash_df.columns
        assert "x_position" not in flash_df.columns

    def test_known_onsets_exact(self):
        opts = canonical_co_resident_options()
        _, receipt = build_synth_nwb(opts)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            task_df = _read_interval_df(path, TASK_TABLE)
            rf_df = _read_interval_df(path, RF_TABLE)
            flash_df = _read_interval_df(path, FLASH_TABLE)

        np.testing.assert_allclose(task_df["start_time"].to_numpy(), receipt.task_onsets_s)
        np.testing.assert_allclose(rf_df["start_time"].to_numpy(), receipt.rf_onsets_s)
        np.testing.assert_allclose(flash_df["start_time"].to_numpy(), receipt.flash_onsets_s)
        np.testing.assert_allclose(
            task_df["stop_time"].to_numpy(),
            task_df["start_time"].to_numpy(),
        )
        assert (flash_df["stop_time"] > flash_df["start_time"]).any()

    def test_ten_channels_and_fs_recoverable(self):
        opts = canonical_co_resident_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            with NWBHDF5IO(str(path), "r") as io:
                nwb = io.read()
                assert len(nwb.electrodes) == 10
                lfp = nwb.acquisition["probe_0_lfp"]
                if getattr(lfp, "neurodata_type", None) == "LFP":
                    lfp = list(lfp.electrical_series.values())[0]
                assert lfp.data.shape[1] == 10
                assert float(lfp.rate) == 1000.0

    def test_acquisition_styles_represented(self):
        with tempfile.TemporaryDirectory() as tmp:
            direct = Path(tmp) / "direct.nwb"
            wrapped = Path(tmp) / "wrapped.nwb"
            write_synth_nwb(direct, canonical_co_resident_options())
            write_synth_nwb(wrapped, lfp_wrapped_options())

            with h5py.File(direct, "r") as h:
                assert h["acquisition/probe_0_lfp"].attrs["neurodata_type"] in (
                    b"ElectricalSeries",
                    "ElectricalSeries",
                )
                assert "data" in h["acquisition/probe_0_lfp"]

            with h5py.File(wrapped, "r") as h:
                ndt = h["acquisition/probe_0_lfp"].attrs["neurodata_type"]
                ndt = ndt.decode() if isinstance(ndt, bytes) else str(ndt)
                assert ndt == "LFP"
                assert "probe_0_lfp_data" in h["acquisition/probe_0_lfp"]

    def test_string_codes_round_trip(self):
        opts = canonical_co_resident_options(codes_dtype="string")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            task_df = _read_interval_df(path, TASK_TABLE)
        codes = [str(c) for c in task_df["codes"].tolist()]
        assert CODE_LABEL_A in codes
        assert CODE_LABEL_B in codes

    def test_numeric_codes_round_trip(self):
        opts = numeric_codes_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            task_df = _read_interval_df(path, TASK_TABLE)
        codes = np.asarray(task_df["codes"], dtype=float)
        assert CODE_NUMERIC_A in codes
        assert CODE_NUMERIC_B in codes

    def test_multiple_tables_distinguishable(self):
        opts = canonical_co_resident_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            receipt = write_synth_nwb(path, opts)
            with NWBHDF5IO(str(path), "r") as io:
                names = sorted(io.read().intervals.keys())
        assert TASK_TABLE in names
        assert RF_TABLE in names
        assert FLASH_TABLE in names
        assert len(names) >= 3
        assert receipt.interval_table_names[0] == TASK_TABLE

    def test_task_only_single_relevant_table(self):
        opts = task_only_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            receipt = write_synth_nwb(path, opts)
            with NWBHDF5IO(str(path), "r") as io:
                names = list(io.read().intervals.keys())
        assert names == [TASK_TABLE]
        assert receipt.rf_table is None
        assert receipt.flash_table is None

    def test_no_forbidden_downstream_identifiers(self):
        opts = canonical_co_resident_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            blob = path.read_bytes().decode("latin-1", errors="ignore")
        for token in FORBIDDEN_FIXTURE_TOKENS:
            assert token not in blob

    def test_units_and_spikes_present(self):
        opts = canonical_co_resident_options()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "synth.nwb"
            write_synth_nwb(path, opts)
            with NWBHDF5IO(str(path), "r") as io:
                nwb = io.read()
                assert nwb.units is not None
                assert len(nwb.units) == 2
                spike_lengths = [
                    len(nwb.units["spike_times"][i]) for i in range(len(nwb.units))
                ]
                assert all(n > 0 for n in spike_lengths)
            with h5py.File(path, "r") as h:
                assert h["units/spike_times_index"].shape[0] == 2
