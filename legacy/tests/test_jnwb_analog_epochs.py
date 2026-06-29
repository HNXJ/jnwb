"""Tests for jnwb LFP/MUAe analog epoch loading."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.jnwb.analog import (
    expected_n_samples,
    extract_analog_epoch_chunk,
    get_sampling_rate_hz,
    resolve_timeseries_from_path,
    time_axis_ms,
)
from src.jnwb.errors import (
    BLOCKED_ANALOG_EPOCH_OUT_OF_BOUNDS,
    BLOCKED_ANALOG_OBJECT_PATH_MISSING,
    BLOCKED_ANALOG_SAMPLING_RATE_MISSING,
    BLOCKED_ANALOG_TIMEBASE_UNSUPPORTED,
    JnwbBlockedError,
)
from src.jnwb.epochs import load_epochs
from src.jnwb.files import NWBFileRecord
from src.jnwb.schema import EventAddress, SignalAddress


class FakeTimeSeries:
    def __init__(
        self,
        data: np.ndarray,
        rate: float | None = 1000.0,
        unit: str = "volts",
        starting_time: float = 0.0,
        timestamps: np.ndarray | None = None,
    ):
        self.data = data
        self.rate = rate
        self.unit = unit
        self.starting_time = starting_time
        self.timestamps = timestamps


class FakeAcquisition(dict):
    pass


class FakeProcessingModule:
    def __init__(self, interfaces: dict):
        self.data_interfaces = interfaces


class FakeNWB:
    def __init__(self, acquisition: dict | None = None, processing: dict | None = None):
        self.acquisition = acquisition or {}
        self.processing = processing or {}


def _make_signal_addr(signal: str, n_ch: int, fs: float, path: str) -> SignalAddress:
    skey = "sub_V198o_ses_230714"
    ids = list(range(n_ch))
    return SignalAddress(
        signal=signal,  # type: ignore[arg-type]
        sessions=[skey],
        source_paths=["/fake/session.nwb"],
        object_paths={skey: path},
        ids_by_session={skey: ids},
        area_by_id={skey: {i: f"area{i}" for i in ids}},
        layer_by_id={skey: {i: None for i in ids}},
        probe_by_id={skey: {i: "probe0" for i in ids}},
        sampling_rate_by_session={skey: fs},
        units="volts",
    )


def _make_event_addr(n_events: int = 3) -> EventAddress:
    skey = "sub_V198o_ses_230714"
    events = [
        {
            "condition": "AAXB",
            "condition_number": 4,
            "onset_s": 2.0 + i * 0.5,
            "anchor": "p1",
            "code": 101,
            "omission_offset_ms": 2062,
        }
        for i in range(n_events)
    ]
    return EventAddress(
        task="omission_glo_passive",
        conditions=["AAXB"],
        condition_numbers=[4],
        anchor="p1",
        sessions=[skey],
        events_by_session={skey: events},
        time_unit="s",
        p1_code=101,
        correct_only=True,
    )


def test_lfp_shape_trial_channel_time():
    fs = 1000.0
    n_time = 10000
    data = np.arange(n_time * 4, dtype=np.float32).reshape(n_time, 4)
    ts = FakeTimeSeries(data, rate=fs)
    events = np.array([2.0, 2.5, 3.0])
    window = (-100, 300)
    out, time_ms = extract_analog_epoch_chunk(ts, [0, 1, 2, 3], events, window, fs=fs)
    n_samples = expected_n_samples(window, fs)
    assert out.shape == (3, 4, n_samples)
    assert len(time_ms) == n_samples
    assert time_ms[0] == pytest.approx(-100.0)
    assert time_ms[1] == pytest.approx(-99.0)


def test_muae_three_channels():
    fs = 500.0
    data = np.ones((5000, 3), dtype=np.float32)
    ts = FakeTimeSeries(data, rate=fs, unit="a.u.")
    out, _ = extract_analog_epoch_chunk(ts, [0, 1, 2], np.array([1.0]), (-50, 50), fs=fs)
    assert out.shape == (1, 3, expected_n_samples((-50, 50), fs))


def test_time_axis_ms_convention():
    fs = 1000.0
    window = (-100, 200)
    t = time_axis_ms(window, fs)
    assert len(t) == expected_n_samples(window, fs)
    assert t[-1] < window[1]


def test_out_of_bounds_blocks():
    fs = 1000.0
    data = np.zeros((1000, 2), dtype=np.float32)
    ts = FakeTimeSeries(data, rate=fs)
    with pytest.raises(JnwbBlockedError) as exc:
        extract_analog_epoch_chunk(ts, [0, 1], np.array([5.0]), (-100, 300), fs=fs)
    assert exc.value.code == BLOCKED_ANALOG_EPOCH_OUT_OF_BOUNDS


def test_missing_rate_blocks():
    ts = FakeTimeSeries(np.zeros((100, 2)), rate=None, timestamps=None)
    with pytest.raises(JnwbBlockedError) as exc:
        get_sampling_rate_hz(ts)
    assert exc.value.code == BLOCKED_ANALOG_SAMPLING_RATE_MISSING


def test_irregular_timestamps_block():
    ts = FakeTimeSeries(
        np.zeros((5, 2)),
        rate=None,
        timestamps=np.array([0.0, 0.001, 0.003, 0.004, 0.005]),
    )
    with pytest.raises(JnwbBlockedError) as exc:
        get_sampling_rate_hz(ts)
    assert exc.value.code == BLOCKED_ANALOG_TIMEBASE_UNSUPPORTED


def test_missing_object_path_blocks():
    nwb = FakeNWB(acquisition=FakeAcquisition())
    with pytest.raises(JnwbBlockedError) as exc:
        resolve_timeseries_from_path(nwb, "acquisition/missing")
    assert exc.value.code == BLOCKED_ANALOG_OBJECT_PATH_MISSING


def test_resolve_acquisition_path():
    ts = FakeTimeSeries(np.zeros((10, 2)), rate=1000.0)
    nwb = FakeNWB(acquisition=FakeAcquisition(lfp=ts))
    resolved = resolve_timeseries_from_path(nwb, "acquisition/lfp")
    assert resolved is ts


def test_chunked_matches_unchunked_synthetic(monkeypatch):
    fs = 1000.0
    n_time = 20000
    data = np.random.randn(n_time, 4).astype(np.float32)
    ts = FakeTimeSeries(data, rate=fs)

    rec = NWBFileRecord(
        path="/fake/session.nwb",
        session_id="ses-230714",
        subject="sub-V198o",
        date=None,
        task_names=["omission_glo_passive"],
        has_spk=True,
        has_lfp=True,
        has_muae=True,
    )

    def fake_iter(rec_in, signal_addr, event_addr, skey, events, window_ms, chunk_size, spec, backend, fail_on_empty):
        from src.jnwb import epochs as ep

        channel_ids = [int(ch) for ch in signal_addr.ids_by_session[skey]]
        effective_chunk = len(events) if chunk_size <= 0 else chunk_size
        for start in range(0, len(events), effective_chunk):
            end = min(start + effective_chunk, len(events))
            chunk_events = events[start:end]
            event_times = np.array([e["onset_s"] for e in chunk_events], dtype=np.float64)
            arr, time_ms = extract_analog_epoch_chunk(ts, channel_ids, event_times, window_ms, fs=fs)
            trial_df = pd.DataFrame(
                [{"session_id": skey, "condition": e["condition"]} for e in chunk_events]
            )
            signal_df = pd.DataFrame([{"channel_id": c} for c in channel_ids])
            yield ep.EpochBatch(
                data=arr,
                time_ms=time_ms,
                trial_metadata=trial_df,
                signal_metadata=signal_df,
                manifest={"session_id": skey},
            )

    monkeypatch.setattr(
        "src.jnwb.epochs._iter_analog_session_chunks",
        fake_iter,
    )

    sig = _make_signal_addr("LFP", 4, fs, "acquisition/lfp")
    ev = _make_event_addr(4)
    full = load_epochs([rec], sig, ev, window_ms=(-50, 50), chunk_size=100)
    chunked = load_epochs([rec], sig, ev, window_ms=(-50, 50), chunk_size=2)
    cat = np.concatenate([np.asarray(b.data) for b in chunked], axis=0)
    assert np.allclose(np.asarray(full.data), cat)


@pytest.mark.skipif(not Path(r"D:/analysis/nwb").exists(), reason="NWB root unavailable")
def test_load_lfp_live_smoke():
    import jnwb

    files = jnwb.list_nwb_files(r"D:/analysis/nwb")
    lfp_files = [f for f in files if f.has_lfp]
    if not lfp_files:
        pytest.skip("No LFP sessions")
    sig = jnwb.address_signals(lfp_files[:1], signal="LFP", require_area=False, max_items=4)
    ev = jnwb.address_events(lfp_files[:1], conditions=["AAXB"], anchor="p1", correct=True)
    batch = jnwb.load_epochs(
        lfp_files[:1],
        sig,
        ev,
        window_ms=(-50, 50),
        chunk_size=1000,
    )
    assert batch.data.ndim == 3
    assert batch.data.shape[0] == len(batch.trial_metadata)
    assert batch.data.shape[1] == len(batch.signal_metadata)
    assert batch.data.shape[2] == len(batch.time_ms)
