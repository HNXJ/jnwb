# -*- coding: utf-8 -*-
"""Tests for NWB rate resolver.

Run with: pytest tests/test_nwb_rate_resolver.py -v
"""

import numpy as np
import pytest

from src.analysis.io.nwb_rate_resolver import (
    resolve_nwb_timeseries_rate,
    BLOCKED_LFP_RATE_UNRESOLVED,
)


class MockTimeSeries:
    """Mock NWB TimeSeries for testing."""

    def __init__(self, rate=None, timestamps=None, starting_time=None):
        self.rate = rate
        self._timestamps = timestamps
        self.starting_time = starting_time

    @property
    def timestamps(self):
        return self._timestamps


def test_resolver_uses_explicit_rate_when_present():
    """Test 1: resolver uses explicit rate when present."""
    ts = MockTimeSeries(rate=1000.0)
    rate, meta = resolve_nwb_timeseries_rate(ts, series_path="test/rate_present")

    assert rate == 1000.0
    assert meta["source"] == "rate"
    assert meta["series_path"] == "test/rate_present"
    assert len(meta["warnings"]) == 0


def test_resolver_computes_rate_from_timestamps():
    """Test 2: resolver computes rate from timestamps."""
    # Regular 1ms timestamps = 1000 Hz
    timestamps = np.arange(0, 1.0, 0.001)  # 0 to 1 second in 1ms steps
    ts = MockTimeSeries(rate=None, timestamps=timestamps)

    rate, meta = resolve_nwb_timeseries_rate(
        ts,
        series_path="test/timestamps_regular",
        timestamp_sample_size=100,  # Small sample for test
    )

    assert rate is not None
    assert abs(rate - 1000.0) < 0.1  # Should be ~1000 Hz
    assert meta["source"] == "timestamps"
    assert meta["n_timestamps_used"] == 100
    assert abs(meta["median_dt_s"] - 0.001) < 1e-9  # ~1ms dt
    assert meta["jitter_max"] is not None
    assert meta["jitter_max"] < 0.01  # Regular timestamps, low jitter


def test_resolver_rejects_missing_rate_and_timestamps():
    """Test 3: resolver rejects missing rate/timestamps without fallback."""
    ts = MockTimeSeries(rate=None, timestamps=None)

    rate, meta = resolve_nwb_timeseries_rate(ts, series_path="test/unresolvable")

    assert rate is None
    assert meta["source"] == "unresolved"
    assert meta["rate_hz"] is None
    assert len(meta["warnings"]) > 0
    assert "Could not resolve rate" in meta["warnings"][-1]


def test_resolver_uses_trusted_fallback_when_needed():
    """Test 4: resolver uses trusted fallback when no direct rate available."""
    ts = MockTimeSeries(rate=None, timestamps=None)

    rate, meta = resolve_nwb_timeseries_rate(
        ts,
        series_path="test/fallback",
        trusted_fallback_hz=2000.0,
    )

    assert rate == 2000.0
    assert meta["source"] == "trusted_fallback"
    assert meta["rate_hz"] == 2000.0
    assert any("trusted fallback" in w for w in meta["warnings"])


def test_resolver_handles_nonfinite_rate():
    """Test: resolver handles non-finite rate values."""
    ts = MockTimeSeries(rate=np.nan)

    rate, meta = resolve_nwb_timeseries_rate(ts, series_path="test/nan_rate")

    assert rate is None or rate != rate  # None or NaN
    assert meta["source"] != "rate"
    assert any("non-finite" in w for w in meta["warnings"])


def test_resolver_handles_irregular_timestamps():
    """Test: resolver warns on irregular timestamps."""
    # Irregular timestamps (jitter > 1% tolerance)
    base = np.arange(0, 1.0, 0.001)
    noise = np.random.RandomState(42).normal(0, 0.0001, len(base))
    timestamps = base + noise

    ts = MockTimeSeries(rate=None, timestamps=timestamps)

    rate, meta = resolve_nwb_timeseries_rate(
        ts,
        series_path="test/irregular",
        jitter_tolerance=0.001,  # Very strict tolerance
    )

    # Should fail due to high jitter
    assert rate is None or meta["source"] != "timestamps"
    assert meta["jitter_max"] is not None
    assert meta["jitter_max"] > 0.001


def test_resolver_insufficient_timestamps():
    """Test: resolver handles insufficient timestamps."""
    timestamps = np.array([0.0])  # Only 1 timestamp
    ts = MockTimeSeries(rate=None, timestamps=timestamps)

    rate, meta = resolve_nwb_timeseries_rate(ts, series_path="test/short")

    assert rate is None
    assert any("Insufficient timestamps" in w for w in meta["warnings"])


def test_resolver_negative_or_zero_timestamps():
    """Test: resolver handles non-positive dt."""
    timestamps = np.array([0.0, 0.0, 0.0])  # Zero dt
    ts = MockTimeSeries(rate=None, timestamps=timestamps)

    rate, meta = resolve_nwb_timeseries_rate(ts, series_path="test/zero_dt")

    assert rate is None
    assert any("non-positive" in w.lower() for w in meta["warnings"])


if __name__ == "__main__":
    # Run quick smoke tests
    print("Running rate resolver tests...")

    test_resolver_uses_explicit_rate_when_present()
    print("✓ Test 1 passed: explicit rate")

    test_resolver_computes_rate_from_timestamps()
    print("✓ Test 2 passed: timestamps rate computation")

    test_resolver_rejects_missing_rate_and_timestamps()
    print("✓ Test 3 passed: rejection without fallback")

    test_resolver_uses_trusted_fallback_when_needed()
    print("✓ Test 4 passed: trusted fallback")

    test_resolver_handles_nonfinite_rate()
    print("✓ Test 5 passed: non-finite rate handling")

    test_resolver_handles_irregular_timestamps()
    print("✓ Test 6 passed: irregular timestamp handling")

    test_resolver_insufficient_timestamps()
    print("✓ Test 7 passed: insufficient timestamps")

    test_resolver_negative_or_zero_timestamps()
    print("✓ Test 8 passed: non-positive dt handling")

    print("\nAll tests passed!")
