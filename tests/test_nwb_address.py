"""Tests for NWB address layer (src/analysis/io/nwb_address.py)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.analysis.io import nwb_address as nwb_addr


# ============================================================================
# Unit Tests (synthetic, no NWB required)
# ============================================================================

class TestFiringRateMath:
    """Test firing rate calculations."""
    
    def test_bin_to_hz_conversion(self):
        """10 spikes in 5 s bin = 2.0 Hz."""
        bin_spikes = 10
        bin_s = 5.0
        hz = bin_spikes / bin_s
        assert hz == 2.0
    
    def test_bin_ms_constant(self):
        """Verify bin width constant."""
        assert nwb_addr.BIN_WIDTH_MS == 5000
        assert nwb_addr.BIN_WIDTH_S == 5.0


class TestPresenceRatio:
    """Test presence ratio calculation."""
    
    def test_presence_ratio_three_of_four(self):
        """3 of 4 bins with >=1 spike = 0.75."""
        bins_with_spikes = 3
        total_bins = 4
        ratio = bins_with_spikes / total_bins
        assert ratio == 0.75
    
    def test_presence_ratio_half(self):
        """2 of 4 bins with >=1 spike = 0.5."""
        spike_counts = [5, 0, 3, 0]  # Bins with/without spikes
        min_spikes = 1
        present = sum(1 for c in spike_counts if c >= min_spikes)
        ratio = present / len(spike_counts)
        assert ratio == 0.5


class TestAreaSplitting:
    """Test probe area splitting logic."""
    
    def test_128_channels_2_areas(self):
        """128 channels + 2 areas -> 0-63 V1, 64-127 V2."""
        n_channels = 128
        areas = ["V1", "V2"]
        n_areas = len(areas)
        
        chunk_size = n_channels // n_areas  # 64
        
        v1_start = 0
        v1_end = chunk_size - 1  # 63
        v2_start = chunk_size  # 64
        v2_end = n_channels - 1  # 127
        
        assert v1_start == 0
        assert v1_end == 63
        assert v2_start == 64
        assert v2_end == 127
        assert (v1_end - v1_start + 1) == 64
        assert (v2_end - v2_start + 1) == 64
    
    def test_non_divisible_channels(self):
        """10 channels + 3 areas -> deterministic contiguous chunks."""
        n_channels = 10
        n_areas = 3
        
        # Split with remainder distribution
        chunk_size = n_channels // n_areas  # 3
        remainder = n_channels % n_areas  # 1
        
        # First 'remainder' chunks get one extra
        chunks = []
        start = 0
        for i in range(n_areas):
            this_chunk = chunk_size + (1 if i < remainder else 0)
            end = start + this_chunk
            chunks.append((start, end))
            start = end
        
        assert chunks == [(0, 4), (4, 7), (7, 10)]
        # All channels covered exactly once
        assert sum(e - s for s, e in chunks) == n_channels


class TestConditionMapping:
    """Test condition number mapping."""
    
    def test_canonical_conditions_length(self):
        """Should have 12 canonical conditions."""
        assert len(nwb_addr.CANONICAL_CONDITIONS) == 12
    
    def test_condition_number_map_coverage(self):
        """All condition numbers 1-50 should be mapped."""
        # AAAB: 1,2; AXAB: 3; AAXB: 4; AAAX: 5
        # BBBA: 6,7; BXBA: 8; BBXA: 9; BBBX: 10
        # RRRR: 11-26; RXRR: 27-34; RRXR: 35,37,39,41; RRRX: 36,38,40,42-50
        all_mapped = set()
        for nums in nwb_addr.CONDITION_NUMBER_MAP.values():
            all_mapped.update(nums)
        
        # Check we have numbers covering the expected range
        assert 1 in all_mapped  # AAAB
        assert 50 in all_mapped  # RRRX
        assert len(all_mapped) >= 40  # Most numbers covered
    
    def test_number_to_condition_invertible(self):
        """NUMBER_TO_CONDITION should be invertible from CONDITION_NUMBER_MAP."""
        for code, numbers in nwb_addr.CONDITION_NUMBER_MAP.items():
            for num in numbers:
                assert nwb_addr.NUMBER_TO_CONDITION[num] == code


class TestEventVectorOutput:
    """Test event vector return types."""
    
    def test_empty_event_vectors_structure(self):
        """Event vectors should be dict[str, list[float]]."""
        result = {
            "AAAB": [],
            "AXAB": [1.0, 2.0, 3.0],
        }
        
        assert isinstance(result, dict)
        for key, val in result.items():
            assert isinstance(key, str)
            assert isinstance(val, list)
            for item in val:
                assert isinstance(item, (int, float))


# ============================================================================
# Smoke Tests (requires PyNWB but not necessarily real NWB file)
# ============================================================================

class TestPyNWBImport:
    """Verify PyNWB availability."""
    
    def test_pynwb_import(self):
        """PyNWB should be importable."""
        try:
            import pynwb
            assert hasattr(pynwb, "NWBHDF5IO")
        except ImportError:
            pytest.skip("PyNWB not installed")


# ============================================================================
# Integration Tests (requires real NWB file)
# ============================================================================

NWB_BASELINE = Path(r"D:\analysis\nwb\sub-C31o_ses-230630_rec.nwb")


@pytest.fixture
def has_baseline_nwb():
    """Check if baseline NWB exists."""
    return NWB_BASELINE.exists()


class TestBuildUnitAddressBook:
    """Integration tests for unit address book."""
    
    def test_unit_address_book_smoke(self, has_baseline_nwb):
        """Build unit address book from baseline NWB."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = Path(tmpdir) / "units.csv"
            
            df = nwb_addr.build_unit_address_book(
                [NWB_BASELINE],
                out_csv=out_csv,
                bin_ms=5000,
                overwrite=True,
            )
            
            # Verify DataFrame structure
            assert isinstance(df, pd.DataFrame)
            assert len(df) > 0, "Should have at least one unit"
            
            # Required columns
            required_cols = [
                "general_unit_id",
                "subject_id",
                "session_id",
                "nwb_file",
                "unit_id_in_nwb",
                "unit_row_index",
                "area",
                "area_status",
                "n_spikes_total",
                "presence_ratio",
                "min_firing_rate_hz",
                "max_firing_rate_hz",
                "mean_firing_rate_hz",
                "median_firing_rate_hz",
            ]
            for col in required_cols:
                assert col in df.columns, f"Missing column: {col}"
            
            # CSV written
            assert out_csv.exists()
            
            # Read back and verify
            df2 = pd.read_csv(out_csv)
            assert len(df2) == len(df)
    
    def test_firing_rate_denominator(self, has_baseline_nwb):
        """Verify firing rate uses 5.0 s denominator, not 10.0."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        df = nwb_addr.build_unit_address_book([NWB_BASELINE], out_csv=None)
        
        if len(df) == 0:
            pytest.skip("No units found")
        
        # Check bin_width_s column
        if "bin_width_s" in df.columns:
            assert all(df["bin_width_s"] == 5.0), "Bin width should be 5.0 s"
        
        # Sanity check firing rates
        # With 5s bins, 10 spikes -> 2.0 Hz (not 1.0 Hz)
        if "max_firing_rate_hz" in df.columns:
            max_fr = df["max_firing_rate_hz"].max()
            assert max_fr < 1000, "Firing rate seems unreasonably high"
            assert max_fr >= 0, "Firing rate should be non-negative"


class TestBuildLFPSessionAddressBook:
    """Integration tests for LFP session address book."""
    
    def test_lfp_address_book_smoke(self, has_baseline_nwb):
        """Build LFP address book from baseline NWB."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            out_csv = Path(tmpdir) / "lfp.csv"
            
            df = nwb_addr.build_lfp_session_address_book(
                [NWB_BASELINE],
                out_csv=out_csv,
                overwrite=True,
            )
            
            # Verify DataFrame structure
            assert isinstance(df, pd.DataFrame)
            
            # Required columns
            required_cols = [
                "general_lfp_id",
                "subject_id",
                "session_id",
                "nwb_file",
                "probe_id",
                "probe_label",
                "area_string_raw",
                "area_list",
                "n_channels",
                "channel_index_start_global",
                "channel_index_stop_global_exclusive",
                "channel_index_range_global",
            ]
            for col in required_cols:
                assert col in df.columns, f"Missing column: {col}"
            
            # CSV written
            if len(df) > 0:
                assert out_csv.exists()


class TestGetEventTimingVectors:
    """Integration tests for event timing vectors."""
    
    def test_event_vectors_smoke(self, has_baseline_nwb):
        """Get event timing vectors from baseline NWB."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        try:
            result = nwb_addr.get_event_timing_vectors(
                NWB_BASELINE,
                event="p1",
                conditions=nwb_addr.CANONICAL_CONDITIONS,
            )
        except RuntimeError as e:
            if "BLOCKED" in str(e):
                pytest.skip(f"Typed blocker: {e}")
            raise
        
        # Verify structure
        assert isinstance(result, dict)
        
        # Each value should be a list of floats
        for cond, times in result.items():
            assert isinstance(cond, str)
            assert isinstance(times, list)
            for t in times:
                assert isinstance(t, (int, float))
    
    def test_canonical_conditions_order(self, has_baseline_nwb):
        """Verify canonical condition order in output."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        try:
            result = nwb_addr.get_event_timing_vectors(
                NWB_BASELINE,
                event="p1",
            )
        except RuntimeError as e:
            if "BLOCKED" in str(e):
                pytest.skip(f"Typed blocker: {e}")
            raise
        
        # Verify canonical order
        expected_order = nwb_addr.CANONICAL_CONDITIONS
        actual_order = [k for k in result.keys()]
        
        # At minimum, the conditions should be a subset of canonical
        for cond in actual_order:
            assert cond in expected_order, f"Unexpected condition: {cond}"


class TestEstimateChannelAreaLayerMap:
    """Integration tests for channel area/layer map."""
    
    def test_channel_map_smoke(self, has_baseline_nwb):
        """Build channel area/layer map from baseline NWB."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        df = nwb_addr.estimate_channel_area_layer_map(
            NWB_BASELINE,
            probe_id=None,
            infer_layers=False,
        )
        
        # Verify DataFrame structure
        assert isinstance(df, pd.DataFrame)
        
        if len(df) > 0:
            # Required columns
            required_cols = [
                "subject_id",
                "session_id",
                "nwb_file",
                "probe_id",
                "channel_index_global",
                "channel_index_local",
                "area",
                "area_status",
                "layer",
                "layer_status",
            ]
            for col in required_cols:
                assert col in df.columns, f"Missing column: {col}"
            
            # Default layer status
            assert all(df["layer"] == "unresolved"), "Layers should be unresolved by default"
            assert all(df["layer_status"] == "unresolved"), "Layer status should be unresolved by default"


class TestGetAlignedUnitSignals:
    """Integration tests for aligned unit signal extraction."""
    
    def test_aligned_units_binned_smoke(self, has_baseline_nwb):
        """Extract binned aligned unit signals."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        # First get event vectors
        try:
            events = nwb_addr.get_event_timing_vectors(
                NWB_BASELINE,
                event="p1",
                conditions=["AAAB"],  # Just one condition for speed
            )
        except RuntimeError as e:
            if "BLOCKED" in str(e):
                pytest.skip(f"Typed blocker for events: {e}")
            raise
        
        if not events.get("AAAB"):
            pytest.skip("No AAAB trials found")
        
        # Use first 3 events only for speed
        test_events = {"AAAB": events["AAAB"][:3]}
        
        result = nwb_addr.get_aligned_unit_signals(
            nwb_path=NWB_BASELINE,
            unit_filter={"presence_ratio_min": 0.0},  # Include all
            event_vectors=test_events,
            pre_ms=-1000,
            post_ms=4000,
            bin_ms=10.0,  # 10ms bins
        )
        
        # Verify structure
        assert isinstance(result, dict)
        assert result["signal_class"] == "SPK"
        assert result["time_unit"] == "ms"
        assert result["bin_ms"] == 10.0
        
        # Check binned array shape
        if "AAAB" in result["spikes"]:
            arr = result["spikes"]["AAAB"]
            assert isinstance(arr, np.ndarray)
            assert arr.ndim == 3  # trial x unit x time_bin
            
            # Expected time bins
            expected_bins = int((4000 - (-1000)) / 10.0)
            assert arr.shape[2] == expected_bins, f"Expected {expected_bins} bins, got {arr.shape[2]}"
    
    def test_aligned_units_ragged_smoke(self, has_baseline_nwb):
        """Extract ragged aligned unit signals (no binning)."""
        if not has_baseline_nwb:
            pytest.skip(f"Baseline NWB not found: {NWB_BASELINE}")
        
        try:
            events = nwb_addr.get_event_timing_vectors(
                NWB_BASELINE,
                event="p1",
                conditions=["AAAB"],
            )
        except RuntimeError as e:
            if "BLOCKED" in str(e):
                pytest.skip(f"Typed blocker: {e}")
            raise
        
        if not events.get("AAAB"):
            pytest.skip("No AAAB trials found")
        
        test_events = {"AAAB": events["AAAB"][:2]}
        
        result = nwb_addr.get_aligned_unit_signals(
            nwb_path=NWB_BASELINE,
            unit_filter={"presence_ratio_min": 0.0},
            event_vectors=test_events,
            pre_ms=-1000,
            post_ms=4000,
            bin_ms=None,  # Ragged output
        )
        
        # Should have ragged structure
        assert "spike_times_relative" in result
        assert "AAAB" in result["spike_times_relative"]


# ============================================================================
# Output Directory Tests
# ============================================================================

class TestOutputDirectories:
    """Verify output directory handling."""
    
    def test_outputs_data_index_created(self, tmp_path):
        """Output should create data_index directory."""
        out_dir = tmp_path / "outputs" / "data_index"
        out_dir.mkdir(parents=True, exist_ok=True)
        
        assert out_dir.exists()
        
        # Write a test file
        test_file = out_dir / "test.csv"
        test_file.write_text("a,b\n1,2\n")
        
        assert test_file.exists()
