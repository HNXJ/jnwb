"""Tests for jnwb epoch shapes and chunking."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

import jnwb
from src.jnwb.epochs import _bin_edges, _extract_spk_epoch


class _FakeSpikeTimes:
    def __init__(self, data):
        self.data = data


class _FakeUnits:
    def __init__(self, spike_data):
        self.colnames = ["unit_id", "spike_times"]
        self._spikes = spike_data

    def __len__(self):
        return len(self._spikes)

    def __getitem__(self, key):
        if key == "unit_id":
            return [i for i in range(len(self._spikes))]
        if key == "spike_times":
            return self._spikes
        raise KeyError(key)


def test_spk_shape_trial_unit_time():
    units = _FakeUnits(
        [
            _FakeSpikeTimes(np.array([1.0, 1.01, 1.5])),
            _FakeSpikeTimes(np.array([1.02])),
        ]
    )
    events = np.array([1.0, 2.0])
    epochs = _extract_spk_epoch(units, [0, 1], events, (-100, 200), bin_ms=10.0)
    assert epochs.shape[0] == 2
    assert epochs.shape[1] == 2
    assert epochs.shape[2] == len(_bin_edges((-100, 200), 10.0)[0]) - 1


@pytest.mark.skipif(not Path(r"D:/analysis/nwb").exists(), reason="NWB root unavailable")
def test_load_epochs_spk_live_shape():
    files = jnwb.list_nwb_files(r"D:/analysis/nwb")
    spk_files = [f for f in files if f.has_spk]
    sig = jnwb.address_signals(spk_files[:1], signal="SPK", require_area=False, max_items=10)
    ev = jnwb.address_events(
        spk_files[:1],
        conditions=["AAXB"],
        anchor="p1",
        correct=True,
    )
    batch = jnwb.load_epochs(
        spk_files[:1],
        sig,
        ev,
        window_ms=(-100, 200),
        chunk_size=1000,
        bin_ms=10.0,
    )
    assert isinstance(batch, jnwb.EpochBatch)
    assert batch.data.ndim == 3
    assert batch.data.shape[0] == len(batch.trial_metadata)
    assert batch.data.shape[1] == len(batch.signal_metadata)


@pytest.mark.skipif(not Path(r"D:/analysis/nwb").exists(), reason="NWB root unavailable")
def test_chunked_matches_unchunked_tiny():
    files = jnwb.list_nwb_files(r"D:/analysis/nwb")
    spk_files = [f for f in files if f.has_spk]
    sig = jnwb.address_signals(spk_files[:1], signal="SPK", require_area=False, max_items=5)
    ev = jnwb.address_events(spk_files[:1], conditions=["AAXB"], anchor="p1", correct=True)

    full = jnwb.load_epochs(
        spk_files[:1], sig, ev, window_ms=(-50, 50), chunk_size=10000, bin_ms=10.0
    )
    chunked = jnwb.load_epochs(
        spk_files[:1], sig, ev, window_ms=(-50, 50), chunk_size=2, bin_ms=10.0
    )
    chunks = list(chunked)
    cat = np.concatenate([np.asarray(c.data) for c in chunks], axis=0)
    assert np.allclose(np.asarray(full.data), cat)
