from __future__ import annotations

import h5py
import numpy as np
import pytest

from omission.jnwb_ext.analog import load_muae_epochs
from jnwb.paths import nwb_dir


def _make_fixture(path, *, nested=False):
    with h5py.File(path, "w") as handle:
        electrodes = handle.create_group("general").create_group(
            "extracellular_ephys"
        ).create_group("electrodes")
        electrodes.create_dataset("id", data=np.arange(4, dtype=np.int16))
        electrodes.create_dataset(
            "location", data=np.asarray([b"V1"] * 4, dtype="S4")
        )
        electrodes.create_dataset(
            "probe", data=np.asarray([b"probeA"] * 4, dtype="S6")
        )
        intervals = handle.create_group("intervals").create_group(
            "omission_glo_passive"
        )
        intervals.create_dataset("start_time", data=[0.5])
        intervals.create_dataset("trial_num", data=[1.0])
        intervals.create_dataset("stimulus_number", data=[2.0])
        intervals.create_dataset("task_condition_number", data=[3.0])
        intervals.create_dataset("correct", data=[1.0])
        acquisition = handle.create_group("acquisition")
        series = acquisition.create_group("probe_0_muae")
        container = series.create_group("probe_0_muae_data") if nested else series
        container.create_dataset(
            "data", data=np.arange(3000 * 4, dtype=np.float32).reshape(3000, 4)
        ).attrs["unit"] = "volts"
        container.create_dataset("electrodes", data=np.arange(4, dtype=np.int8))
        starting_time = container.create_dataset("starting_time", data=np.asarray(0.0))
        starting_time.attrs["rate"] = 1000.0


def test_muae_accessor_fixture_contract(tmp_path):
    path = tmp_path / "sub-V198o_ses-230714.nwb"
    _make_fixture(path)
    batch = load_muae_epochs(
        path,
        condition="AXAB",
        alignment="omission",
        window_ms=(-100.0, 100.0),
    )
    assert batch.data.shape == (1, 4, 200)
    assert batch.data.dtype == np.float32
    assert batch.time_ms[100] == pytest.approx(0.0)
    assert batch.trial_metadata.loc[0, "trial_id"].endswith(
        "trial=1|condition=AXAB"
    )
    assert set(batch.signal_metadata["signal_class"]) == {"MUAe"}
    assert batch.manifest["alignment_event"] == "omission"
    assert batch.manifest["training_performed"] is False


def test_muae_accessor_real_session_smoke():
    try:
        path = nwb_dir() / "sub-C31o_ses-230823_rec.nwb"
    except FileNotFoundError:
        pytest.skip("real omission NWB root unavailable ($OMISSION_NWB_DIR unset)")
    if not path.is_file():
        pytest.skip("real omission NWB root unavailable")
    batch = load_muae_epochs(
        path,
        condition="AXAB",
        alignment="omission",
        areas=["FEF"],
        window_ms=(-10.0, 10.0),
        max_trials=1,
    )
    assert batch.data.ndim == 3
    assert batch.data.shape[0] == 1
    assert batch.data.shape[1] == len(batch.signal_metadata)
    assert batch.data.shape[2] == len(batch.time_ms)
    assert batch.trial_metadata.loc[0, "omission_position"] == "p2"


def test_muae_accessor_nested_electrical_series_rate(tmp_path):
    path = tmp_path / "sub-V182o_ses-260702.nwb"
    _make_fixture(path, nested=True)
    batch = load_muae_epochs(
        path,
        condition="AXAB",
        alignment="omission",
        window_ms=(-10.0, 10.0),
    )
    assert batch.data.shape == (1, 4, 20)
    assert batch.signal_metadata.loc[0, "sampling_rate_hz"] == pytest.approx(1000.0)
    assert batch.manifest["source_series"][0]["sampling_rate_hz"] == pytest.approx(1000.0)
