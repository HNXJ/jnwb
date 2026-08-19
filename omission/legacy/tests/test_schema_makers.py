# -*- coding: utf-8 -*-
"""Tests for graphical schema makers.

Tests ensure dummy data shapes are correct, schema gallery writes expected files,
and no real NWB/MNE dependencies are required.
"""

import json
import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.analysis.visualization.schema_makers import (
    make_dummy_spike_band_correlation_data,
    make_dummy_moving_window_progression_data,
    plot_neuron_band_correlation_density_schema,
    plot_moving_window_correlation_progression_schema,
    write_schema_gallery,
    SCHEMA_WARNING,
    CORRELATION_NOT_CAUSALITY,
    LAGGED_NOT_CAUSAL,
    CANONICAL_BANDS,
)


class TestDummyDataShapes:
    """Test 1 & 2: Dummy data shapes are correct."""

    def test_spike_band_data_shapes_default(self):
        """Test default parameters produce expected shapes."""
        data = make_dummy_spike_band_correlation_data(seed=0)

        # Check spike_rate shape: (n_trials, n_time)
        assert data["spike_rate"].shape == (80, 300), \
            f"Expected spike_rate shape (80, 300), got {data['spike_rate'].shape}"

        # Check band_power shape: (n_bands, n_trials, n_time)
        n_bands = len(data["bands"])
        assert data["band_power"].shape == (n_bands, 80, 300), \
            f"Expected band_power shape ({n_bands}, 80, 300), got {data['band_power'].shape}"

        # Check time_ms shape
        assert data["time_ms"].shape == (300,), \
            f"Expected time_ms shape (300,), got {data['time_ms'].shape}"

        # Check bands match
        assert len(data["bands"]) == data["band_power"].shape[0], \
            "Bands count must match band_power first dimension"

    def test_spike_band_data_shapes_custom(self):
        """Test custom parameters produce expected shapes."""
        data = make_dummy_spike_band_correlation_data(
            n_trials=50,
            n_time=200,
            bands=("alpha", "beta", "gamma"),
            seed=42
        )

        assert data["spike_rate"].shape == (50, 200)
        assert data["band_power"].shape == (3, 50, 200)
        assert data["time_ms"].shape == (200,)
        assert data["bands"] == ("alpha", "beta", "gamma")

    def test_moving_window_data_shapes_default(self):
        """Test default moving-window parameters."""
        data = make_dummy_moving_window_progression_data(seed=1)

        n_sources = len(data["sources"])

        # Check corr shape: (n_sources, n_targets, n_windows, n_lags)
        assert data["corr"].shape == (n_sources, n_sources, 80, 41), \
            f"Expected corr shape ({n_sources}, {n_sources}, 80, 41), got {data['corr'].shape}"

        # Check time_ms shape
        assert data["time_ms"].shape == (80,), \
            f"Expected time_ms shape (80,), got {data['time_ms'].shape}"

        # Check lags_ms shape
        assert data["lags_ms"].shape == (41,), \
            f"Expected lags_ms shape (41,), got {data['lags_ms'].shape}"

        # Check sources match targets (square matrix)
        assert data["sources"] == data["targets"], \
            "Sources and targets should match for all-pairs correlation"

    def test_moving_window_data_shapes_custom(self):
        """Test custom moving-window parameters."""
        custom_sources = ("A", "B", "C")
        data = make_dummy_moving_window_progression_data(
            n_windows=60,
            n_lags=21,
            sources=custom_sources,
            seed=99
        )

        n_sources = len(custom_sources)
        assert data["corr"].shape == (n_sources, n_sources, 60, 21)
        assert data["time_ms"].shape == (60,)
        assert data["lags_ms"].shape == (21,)
        assert data["sources"] == custom_sources


class TestReproducibility:
    """Test deterministic behavior with seeds."""

    def test_spike_band_reproducibility(self):
        """Same seed produces identical data."""
        data1 = make_dummy_spike_band_correlation_data(seed=123)
        data2 = make_dummy_spike_band_correlation_data(seed=123)

        np.testing.assert_array_equal(data1["spike_rate"], data2["spike_rate"])
        np.testing.assert_array_equal(data1["band_power"], data2["band_power"])
        np.testing.assert_array_equal(data1["time_ms"], data2["time_ms"])

    def test_moving_window_reproducibility(self):
        """Same seed produces identical data."""
        data1 = make_dummy_moving_window_progression_data(seed=456)
        data2 = make_dummy_moving_window_progression_data(seed=456)

        np.testing.assert_array_equal(data1["corr"], data2["corr"])
        np.testing.assert_array_equal(data1["time_ms"], data2["time_ms"])
        np.testing.assert_array_equal(data1["lags_ms"], data2["lags_ms"])


class TestMetadata:
    """Test metadata includes required warnings."""

    def test_spike_band_metadata(self):
        """Test spike-band metadata includes schema warning."""
        data = make_dummy_spike_band_correlation_data(seed=0)

        assert "metadata" in data
        meta = data["metadata"]

        # Check required fields
        assert meta["schema_warning"] == SCHEMA_WARNING
        assert meta["status"] == "SCHEMA_ONLY_DUMMY_DATA"
        assert meta["correlation_not_causality"] is True

        # Check shape metadata
        assert meta["n_trials"] == 80
        assert meta["n_time"] == 300
        assert "time_range_ms" in meta

    def test_moving_window_metadata(self):
        """Test moving-window metadata includes schema warning and lag convention."""
        data = make_dummy_moving_window_progression_data(seed=1)

        assert "metadata" in data
        meta = data["metadata"]

        # Check required fields
        assert meta["schema_warning"] == SCHEMA_WARNING
        assert meta["status"] == "SCHEMA_ONLY_DUMMY_DATA"
        assert meta["lagged_correlation_not_causality"] == LAGGED_NOT_CAUSAL

        # Check lag convention
        assert "lag_convention" in meta
        lag_conv = meta["lag_convention"]
        assert "positive_lag" in lag_conv
        assert "negative_lag" in lag_conv
        assert "zero_lag" in lag_conv

        # Verify convention text includes clarity
        assert "precedes" in lag_conv["positive_lag"].lower() or "leads" in lag_conv["positive_lag"].lower()


class TestPlotFunctions:
    """Test 5: Plot functions do not require NWB/MNE."""

    def test_spike_band_plot_no_nwb(self):
        """Spike-band schema plot works with dummy data only."""
        data = make_dummy_spike_band_correlation_data(seed=0)

        # Should not raise any errors
        result = plot_neuron_band_correlation_density_schema(
            data,
            neuron_id="test_unit",
            area="V1",
            channel="probe0_ch001",
            out_html=None,  # Don't save
        )

        # Check result structure
        assert "title" in result
        assert result["schema_warning"] == SCHEMA_WARNING
        assert result["correlation_not_causality"] == CORRELATION_NOT_CAUSALITY
        assert "metadata" in result

    def test_moving_window_plot_no_nwb(self):
        """Moving-window schema plot works with dummy data only."""
        data = make_dummy_moving_window_progression_data(seed=1)

        # Should not raise any errors
        result = plot_moving_window_correlation_progression_schema(
            data,
            selected_pairs=None,
            out_html=None,  # Don't save
        )

        # Check result structure
        assert "title" in result
        assert result["schema_warning"] == SCHEMA_WARNING
        assert result["lagged_correlation_not_causality"] == LAGGED_NOT_CAUSAL
        assert "lag_convention" in result


class TestSchemaGallery:
    """Test 3: Schema gallery writes expected files."""

    def test_gallery_writes_files(self, tmp_path):
        """Test gallery creates all expected output files."""
        import shutil
        from pathlib import Path

        # Use temp directory
        test_dir = tmp_path / "schema_test"

        # Run gallery creation
        manifest = write_schema_gallery(out_dir=str(test_dir))

        # Check manifest structure
        assert manifest["phase"] == "GRAPHICAL_SCHEMA_LAYER"
        assert manifest["schema_only_dummy_data"] is True
        assert manifest["claim_status"] == "no_biological_claim"

        # Check expected files exist
        expected_files = [
            "spike_band_correlation_density_schema.html",
            "moving_window_correlation_progression_schema.html",
            "schema_gallery_index.html",
            "schema_manifest.json",
        ]

        for fname in expected_files:
            fpath = test_dir / fname
            assert fpath.exists(), f"Expected file not found: {fname}"

        # Check manifest.json content
        manifest_path = test_dir / "schema_manifest.json"
        with open(manifest_path) as f:
            saved_manifest = json.load(f)

        assert saved_manifest["schema_only_dummy_data"] is True
        assert len(saved_manifest["schemas"]) == 2
        assert "warnings" in saved_manifest

        # Check warnings include required text
        warnings_text = " ".join(saved_manifest["warnings"])
        assert "SCHEMA_ONLY_DUMMY_DATA" in warnings_text
        assert "Correlation does not imply causality" in warnings_text


class TestLagConvention:
    """Test 6: Positive lag convention appears in metadata."""

    def test_lag_convention_documented(self):
        """Lag convention clearly documented in output."""
        data = make_dummy_moving_window_progression_data(seed=1)

        lag_conv = data["metadata"]["lag_convention"]

        # Convention must be explicit
        assert "positive_lag" in lag_conv
        assert "negative_lag" in lag_conv
        assert "zero_lag" in lag_conv

        # Convention must describe what positive means
        positive_desc = lag_conv["positive_lag"].lower()
        assert any(term in positive_desc for term in ["lead", "precede", "source leads"])

    def test_lag_ranges(self):
        """Lag values span expected range."""
        data = make_dummy_moving_window_progression_data(n_lags=41, seed=1)

        lags = data["lags_ms"]
        # Should be centered around 0
        assert lags.min() < 0
        assert lags.max() > 0
        assert abs(lags[len(lags)//2]) < 1  # Middle ~0

        # Should be symmetric-ish
        assert abs(lags.min() + lags.max()) < 10  # ~ symmetric


class TestDataRanges:
    """Test that dummy data has reasonable ranges for visualization."""

    def test_spike_rate_nonnegative(self):
        """Spike rates should be non-negative (Hz-like)."""
        data = make_dummy_spike_band_correlation_data(seed=0)
        assert np.all(data["spike_rate"] >= 0), "Spike rates should be non-negative"

    def test_band_power_normalized(self):
        """Band power should be in [0, 1] range (normalized)."""
        data = make_dummy_spike_band_correlation_data(seed=0)
        assert np.all(data["band_power"] >= 0), "Band power min should be >= 0"
        assert np.all(data["band_power"] <= 1), "Band power max should be <= 1"

    def test_correlation_range(self):
        """Correlations should be in [-1, 1] range."""
        data = make_dummy_moving_window_progression_data(seed=1)
        assert np.all(data["corr"] >= -1), "Correlations should be >= -1"
        assert np.all(data["corr"] <= 1), "Correlations should be <= 1"


class TestCanonicalBands:
    """Test canonical bands constant."""

    def test_canonical_bands_exist(self):
        """Canonical bands tuple should exist and have expected bands."""
        assert len(CANONICAL_BANDS) == 8

        expected = ["delta", "theta", "alpha", "beta_L", "beta_H", "gamma_L", "gamma_M", "gamma_H"]
        for band in expected:
            assert band in CANONICAL_BANDS, f"Expected band {band} not found"


if __name__ == "__main__":
    # Run quick smoke tests
    print("Running schema maker tests...")

    # Test 1: Shapes
    TestDummyDataShapes().test_spike_band_data_shapes_default()
    print("✓ Test 1a passed: spike-band default shapes")

    TestDummyDataShapes().test_spike_band_data_shapes_custom()
    print("✓ Test 1b passed: spike-band custom shapes")

    TestDummyDataShapes().test_moving_window_data_shapes_default()
    print("✓ Test 2a passed: moving-window default shapes")

    TestDummyDataShapes().test_moving_window_data_shapes_custom()
    print("✓ Test 2b passed: moving-window custom shapes")

    # Test reproducibility
    TestReproducibility().test_spike_band_reproducibility()
    print("✓ Reproducibility test passed: spike-band")

    TestReproducibility().test_moving_window_reproducibility()
    print("✓ Reproducibility test passed: moving-window")

    # Test metadata
    TestMetadata().test_spike_band_metadata()
    print("✓ Metadata test passed: spike-band warnings")

    TestMetadata().test_moving_window_metadata()
    print("✓ Metadata test passed: moving-window warnings")

    # Test plot functions (no NWB)
    TestPlotFunctions().test_spike_band_plot_no_nwb()
    print("✓ Plot function test passed: spike-band (no NWB)")

    TestPlotFunctions().test_moving_window_plot_no_nwb()
    print("✓ Plot function test passed: moving-window (no NWB)")

    # Test lag convention
    TestLagConvention().test_lag_convention_documented()
    print("✓ Lag convention test passed: convention documented")

    # Test data ranges
    TestDataRanges().test_spike_rate_nonnegative()
    print("✓ Data range test passed: spike rates non-negative")

    TestDataRanges().test_band_power_normalized()
    print("✓ Data range test passed: band power normalized")

    TestDataRanges().test_correlation_range()
    print("✓ Data range test passed: correlations in [-1, 1]")

    print("\nAll smoke tests passed!")
    print("Run 'pytest tests/test_schema_makers.py -v' for full test suite.")
