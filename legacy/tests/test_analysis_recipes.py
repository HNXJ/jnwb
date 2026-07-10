"""Tests for analysis recipe API.

Covers: specs serialization, event storage, signal extraction, analysis workflows.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    from src.analysis.recipes import (
        # Specs
        EventSpec,
        WindowSpec,
        SignalSpec,
        AnalysisSpec,
        OutputSpec,
        RecipeResult,
        CANONICAL_AREAS,
        PUBLICATION_BANDS,
        # Events
        get_event_timing_vectors,
        save_event_timing_vectors_npz,
        load_event_timing_vectors_npz,
        save_event_timing_vectors_json,
        export_event_timing_vectors_csv,
        # IO
        make_recipe_output_root,
        save_array_npz,
        save_table_csv,
        save_manifest_json,
        write_recipe_manifest,
        # Analyses
        run_spike_rate,
        run_smoothed_spike_rate,
        build_Y_tensor,
        build_H_harmony,
    )
except ModuleNotFoundError as exc:
    pytest.skip(
        f"legacy src.analysis.recipes not in this checkout: {exc}",
        allow_module_level=True,
    )


# ============================================================================
# Spec Tests
# ============================================================================

class TestEventSpec:
    """Test EventSpec dataclass."""
    
    def test_default_conditions(self):
        """Should have 12 canonical conditions."""
        spec = EventSpec()
        assert len(spec.conditions) == 12
        assert "AAAB" in spec.conditions
        assert "RRRX" in spec.conditions
    
    def test_serialization(self):
        """Should serialize to dictionary."""
        spec = EventSpec(event="p1", time_base="p1_relative")
        d = spec.to_dict()
        assert d["event"] == "p1"
        assert d["time_base"] == "p1_relative"
        assert "conditions" in d
    
    def test_immutability(self):
        """Should be frozen/immutable."""
        spec = EventSpec()
        with pytest.raises(Exception):
            spec.event = "flash"


class TestWindowSpec:
    """Test WindowSpec dataclass."""
    
    def test_duration_calculation(self):
        """Should compute duration correctly."""
        spec = WindowSpec(pre_ms=-500, post_ms=1000)
        assert spec.duration_ms == 1500
    
    def test_to_samples(self):
        """Should convert to sample indices."""
        spec = WindowSpec(pre_ms=-100, post_ms=500)
        pre_samp, post_samp = spec.to_samples(fs_hz=1000.0)
        assert pre_samp == -100
        assert post_samp == 500
    
    def test_baseline_optional(self):
        """Baseline should be optional."""
        spec = WindowSpec(pre_ms=-500, post_ms=1000)
        assert spec.baseline_ms is None
        
        spec_with_baseline = WindowSpec(
            pre_ms=-500, post_ms=1000,
            baseline_ms=(-500, -50)
        )
        assert spec_with_baseline.baseline_ms == (-500, -50)


class TestSignalSpec:
    """Test SignalSpec dataclass."""
    
    def test_default_layer_unresolved(self):
        """Layer should default to unresolved."""
        spec = SignalSpec(signal_class="SPK")
        assert spec.layer == "unresolved"
    
    def test_v3d_v3a_not_collapsed(self):
        """V3d and V3a should be separate in areas."""
        spec = SignalSpec(signal_class="LFP")
        assert "V3d" in spec.areas
        assert "V3a" in spec.areas
        assert "V3" not in spec.areas  # Not collapsed
    
    def test_unit_filter_dict(self):
        """Unit filter should accept dict."""
        spec = SignalSpec(
            signal_class="SPK",
            unit_filter={"area": "V1", "presence_ratio_min": 0.95}
        )
        assert spec.unit_filter["area"] == "V1"


class TestAnalysisSpec:
    """Test AnalysisSpec dataclass."""
    
    def test_publication_bands(self):
        """Should have publication-ready band definitions."""
        spec = AnalysisSpec(analysis_kind="band_power")
        assert "gamma_L" in spec.bands
        assert "gamma_M" in spec.bands
        assert "gamma_H" in spec.bands
    
    def test_preserve_trials_default(self):
        """Should preserve trials by default."""
        spec = AnalysisSpec(analysis_kind="spike_rate")
        assert spec.preserve_trials is True
    
    def test_aggregation_options(self):
        """Should support different aggregation options."""
        for agg in ["none", "mean", "median", "sem"]:
            spec = AnalysisSpec(analysis_kind="spike_rate", aggregation=agg)
            assert spec.aggregation == agg


class TestOutputSpec:
    """Test OutputSpec dataclass."""
    
    def test_subdirectories(self):
        """Should provide subdirectory paths."""
        spec = OutputSpec(
            output_root=Path("/tmp/outputs"),
            recipe_id="test_recipe"
        )
        assert spec.get_subdir("arrays") == Path("/tmp/outputs/test_recipe/arrays")
        assert spec.get_subdir("manifests") == Path("/tmp/outputs/test_recipe/manifests")


class TestRecipeResult:
    """Test RecipeResult dataclass."""
    
    def test_default_status(self):
        """Should default to PENDING status."""
        result = RecipeResult(recipe_id="test")
        assert result.status == "PENDING"
    
    def test_claim_status(self):
        """Should report truth_safe_unverified."""
        result = RecipeResult(recipe_id="test")
        assert result.claim_status == "truth_safe_unverified"
        assert result.computational_scaffold is True
    
    def test_add_warning(self):
        """Should add warnings."""
        result = RecipeResult(recipe_id="test")
        result.add_warning("TEST_CODE", "Test warning message")
        assert len(result.warnings) == 1
        assert result.warnings[0]["code"] == "TEST_CODE"


# ============================================================================
# Event Storage Tests
# ============================================================================

class TestEventVectorNpzRoundTrip:
    """Test NPZ save/load round-trip for event vectors."""
    
    def test_round_trip_preserves_vectors(self, tmp_path):
        """NPZ round-trip should preserve all vectors exactly."""
        original = {
            "AAAB": np.array([1.0, 2.5, 3.7, 8.2], dtype=np.float64),
            "AXAB": np.array([10.5, 15.2], dtype=np.float64),
            "AAXB": np.array([20.0, 25.5, 30.1], dtype=np.float64),
            "AAAX": np.array([], dtype=np.float64),  # Empty condition
        }
        
        metadata = {
            "nwb_file": "test.nwb",
            "subject_id": "sub-TEST",
            "session_id": "ses-001",
            "event": "p1",
        }
        
        # Save
        npz_path = tmp_path / "events.npz"
        save_event_timing_vectors_npz(original, npz_path, metadata=metadata)
        
        assert npz_path.exists()
        
        # Load
        loaded, loaded_meta = load_event_timing_vectors_npz(npz_path)
        
        # Verify
        assert set(loaded.keys()) == set(original.keys())
        
        for cond in original:
            np.testing.assert_array_equal(loaded[cond], original[cond])
            assert loaded[cond].dtype == np.float64
    
    def test_auto_compute_counts(self, tmp_path):
        """NPZ should auto-compute counts_by_condition."""
        event_vectors = {
            "AAAB": np.array([1.0, 2.0, 3.0, 4.0, 5.0]),
            "AXAB": np.array([10.0, 20.0]),
        }
        
        npz_path = tmp_path / "events.npz"
        save_event_timing_vectors_npz(event_vectors, npz_path)
        
        _, metadata = load_event_timing_vectors_npz(npz_path)
        
        assert "counts_by_condition" in metadata
        assert metadata["counts_by_condition"]["AAAB"] == 5
        assert metadata["counts_by_condition"]["AXAB"] == 2
    
    def test_standard_metadata_fields(self, tmp_path):
        """NPZ metadata should include standard fields."""
        event_vectors = {"AAAB": np.array([1.0, 2.0])}
        
        npz_path = tmp_path / "events.npz"
        custom_meta = {"custom_key": "custom_value"}
        save_event_timing_vectors_npz(event_vectors, npz_path, metadata=custom_meta)
        
        _, metadata = load_event_timing_vectors_npz(npz_path)
        
        assert metadata["time_unit"] == "seconds"
        assert metadata["time_base"] == "NWB"
        assert "conditions" in metadata
        assert "saved_at_utc" in metadata
        assert metadata["custom_key"] == "custom_value"


class TestEventVectorJsonExport:
    """Test JSON export for debugging/provenance."""
    
    def test_json_structure(self, tmp_path):
        """JSON should have readable structure with metadata."""
        event_vectors = {
            "AAAB": np.array([1.0, 2.0, 3.0]),
            "AXAB": np.array([10.0]),
        }
        
        json_path = tmp_path / "events.json"
        save_event_timing_vectors_json(
            event_vectors, json_path,
            metadata={"nwb_file": "test.nwb"}
        )
        
        assert json_path.exists()
        
        # Load and verify structure
        with open(json_path) as f:
            payload = json.load(f)
        
        assert payload["time_unit"] == "seconds"
        assert payload["time_base"] == "NWB"
        assert "counts_by_condition" in payload
        assert payload["counts_by_condition"]["AAAB"] == 3
        assert payload["counts_by_condition"]["AXAB"] == 1
        assert "event_vectors" in payload
        assert payload["metadata"]["nwb_file"] == "test.nwb"
        assert "saved_at_utc" in payload


class TestEventVectorCsvExport:
    """Test CSV export for interoperability (optional)."""
    
    def test_csv_long_table_format(self, tmp_path):
        """CSV export should be long-table format."""
        event_vectors = {
            "AAAB": np.array([1.0, 2.5, 3.7]),
            "AXAB": np.array([10.0, 20.0]),
        }
        
        csv_path = tmp_path / "events.csv"
        export_event_timing_vectors_csv(event_vectors, csv_path)
        
        assert csv_path.exists()
        
        # Load and verify structure
        df = pd.read_csv(csv_path)
        
        # Must be long-table format
        assert list(df.columns) == ["condition", "event", "onset_s", "trial_index"]
        
        # Should have 5 rows (3 + 2)
        assert len(df) == 5
        
        # Verify trial_index is sequential per condition
        aaab_rows = df[df["condition"] == "AAAB"]
        assert list(aaab_rows["trial_index"]) == [0, 1, 2]
        
        # Verify onset_s values preserved
        assert list(aaab_rows["onset_s"]) == [1.0, 2.5, 3.7]


# ============================================================================
# IO Tests
# ============================================================================

class TestMakeRecipeOutputRoot:
    """Test deterministic output root creation."""
    
    def test_directory_structure(self, tmp_path):
        """Should create all required subdirectories."""
        root = make_recipe_output_root(
            tmp_path,
            repo_sha="abc123",
            nwb_sha8="def45678",
            recipe_id="test_recipe"
        )
        
        assert root.exists()
        assert (root / "arrays").exists()
        assert (root / "tables").exists()
        assert (root / "figures").exists()
        assert (root / "notebooks").exists()
        assert (root / "manifests").exists()
        assert (root / "reports").exists()
        assert (root / "warnings").exists()


class TestSaveArrayNpz:
    """Test array saving to NPZ."""
    
    def test_save_and_load(self, tmp_path):
        """Should save and load arrays."""
        arr1 = np.array([1, 2, 3])
        arr2 = np.array([[4, 5], [6, 7]])
        
        path = tmp_path / "test.npz"
        save_array_npz(path, foo=arr1, bar=arr2)
        
        assert path.exists()
        
        loaded = np.load(path)
        np.testing.assert_array_equal(loaded["foo"], arr1)
        np.testing.assert_array_equal(loaded["bar"], arr2)


class TestSaveManifestJson:
    """Test manifest JSON saving."""
    
    def test_numpy_array_conversion(self, tmp_path):
        """Should convert numpy arrays to lists."""
        manifest = {
            "data": np.array([1, 2, 3]),
            "nested": {
                "values": np.array([[4, 5], [6, 7]]),
            },
            "number": np.int64(42),
            "float": np.float64(3.14),
        }
        
        path = tmp_path / "manifest.json"
        save_manifest_json(path, manifest)
        
        with open(path) as f:
            loaded = json.load(f)
        
        assert loaded["data"] == [1, 2, 3]
        assert loaded["nested"]["values"] == [[4, 5], [6, 7]]
        assert loaded["number"] == 42
        assert loaded["float"] == 3.14


# ============================================================================
# Analysis Tests
# ============================================================================

class TestRunSpikeRate:
    """Test spike rate computation."""
    
    def test_shape_preservation(self):
        """Should preserve trial x unit x time shape."""
        spk_epochs = {
            "AAAB": np.random.poisson(0.1, (10, 5, 100)),  # trials, units, time
        }
        
        rate_result = run_spike_rate(spk_epochs, fs=1000.0, preserve_trials=True)
        
        # rates_hz should have same shape as input
        assert rate_result["AAAB"]["rates_hz"].shape == (10, 5, 100)
        
        # mean_rate_hz should collapse trials
        assert rate_result["AAAB"]["mean_rate_hz"].shape == (5, 100)
    
    def test_hz_conversion(self):
        """Should convert counts to Hz correctly."""
        # 1ms bins at fs=1000, so 1 count = 1000 Hz
        spk_epochs = {
            "AAAB": np.ones((1, 1, 1), dtype=np.int32),  # 1 spike in 1ms
        }
        
        rate_result = run_spike_rate(spk_epochs, fs=1000.0)
        
        # 1 count in 1ms bin = 1000 Hz
        assert rate_result["AAAB"]["rates_hz"][0, 0, 0] == 1000.0


class TestRunSmoothedSpikeRate:
    """Test smoothed spike rate computation."""
    
    def test_shape_preservation(self):
        """Should preserve trial x unit x time shape."""
        spk_epochs = {
            "AAAB": np.random.poisson(0.1, (5, 3, 50)),
        }
        
        rate_result = run_smoothed_spike_rate(spk_epochs, sigma_ms=20.0, fs=1000.0)
        
        # Should preserve shape
        assert rate_result["AAAB"]["rates_hz"].shape == (5, 3, 50)


class TestBuildYTensor:
    """Test Y tensor construction."""
    
    def test_shape_band_area_epoch_layer(self):
        """Should produce shape (bands, areas, epochs, layers)."""
        # Create synthetic band power data
        band_power_epochs = {
            "AAAB": {
                "gamma_L": np.random.rand(10, 8, 50),  # trials, channels, time
            },
            "AXAB": {
                "gamma_L": np.random.rand(10, 8, 50),
            },
        }
        
        # Create channel map
        channel_map = pd.DataFrame({
            "channel_index_global": range(8),
            "channel_index_local": range(8),
            "area": ["V1", "V1", "V2", "V2", "V4", "V4", "MT", "MT"],
            "layer": ["unresolved"] * 8,
        })
        
        event_axis = {
            "AAAB": "p1",
            "AXAB": "p2",
        }
        
        Y_result = build_Y_tensor(
            band_power_epochs,
            channel_map,
            event_axis,
            bands=["gamma_L"],
            areas=["V1", "V2", "V4", "MT"],
            layers=("unresolved",),
        )
        
        # Y shape: (bands, areas, epochs, layers)
        assert Y_result["Y"].shape == (1, 4, 2, 1)
        assert Y_result["dims"] == ["band", "area", "epoch", "layer"]
    
    def test_v3d_v3a_not_collapsed(self):
        """V3d and V3a should remain separate."""
        # This is a structural test - actual data would be needed for full verification
        assert "V3d" in CANONICAL_AREAS
        assert "V3a" in CANONICAL_AREAS
        assert "V3" not in CANONICAL_AREAS


class TestBuildHHarmony:
    """Test H harmony matrix construction."""
    
    def test_shape_band_epoch_layer_area_area(self):
        """Should produce shape (bands, epochs, layers, areas, areas)."""
        # Create synthetic Y tensor
        Y = np.random.rand(2, 4, 3, 2)  # bands, areas, epochs, layers
        
        Y_result = {
            "Y": Y,
            "dims": ["band", "area", "epoch", "layer"],
            "coords": {
                "band": ["gamma_L", "gamma_M"],
                "area": ["V1", "V2", "V4", "MT"],
                "epoch": ["p1", "p2", "p3"],
                "layer": ["superficial", "deep"],
            },
            "D_definition": "Y = D(B, A, P, L)",
            "warnings": [],
        }
        
        H_result = build_H_harmony(Y_result, method="corr")
        
        # H shape: (bands, epochs, layers, areas, areas)
        assert H_result["H"].shape == (2, 3, 2, 4, 4)
        assert H_result["dims"] == ["band", "epoch", "layer", "area_from", "area_to"]
    
    def test_note_similarity_not_causality(self):
        """Should note that H is similarity, not causality."""
        Y_result = {
            "Y": np.random.rand(1, 2, 1, 1),
            "dims": ["band", "area", "epoch", "layer"],
            "coords": {
                "band": ["gamma"],
                "area": ["V1", "V2"],
                "epoch": ["p1"],
                "layer": ["unresolved"],
            },
            "warnings": [],
        }
        
        H_result = build_H_harmony(Y_result)
        
        assert "similarity" in H_result["note"].lower() or "harmony" in H_result["note"].lower()
        assert "not causality" in H_result["note"].lower() or "not directionality" in H_result["note"].lower()


# ============================================================================
# Integration Tests (marked as optional)
# ============================================================================

NWB_BASELINE = Path(r"D:\analysis\nwb\sub-C31o_ses-230630_rec.nwb")


@pytest.fixture
def has_baseline_nwb():
    """Check if baseline NWB exists."""
    return NWB_BASELINE.exists()


class TestGetEventTimingVectorsIntegration:
    """Integration tests with real NWB."""
    
    @pytest.mark.skipif(not NWB_BASELINE.exists(), reason="Baseline NWB not found")
    def test_returns_ndarray_not_list(self):
        """Should return dict[str, np.ndarray], not list."""
        result = get_event_timing_vectors(NWB_BASELINE, event="p1")
        
        assert isinstance(result, dict)
        
        for cond, times in result.items():
            assert isinstance(times, np.ndarray), f"{cond}: expected ndarray, got {type(times)}"
            assert times.dtype == np.float64
    
    @pytest.mark.skipif(not NWB_BASELINE.exists(), reason="Baseline NWB not found")
    def test_canonical_conditions(self):
        """Should return all 12 canonical conditions."""
        result = get_event_timing_vectors(NWB_BASELINE, event="p1")
        
        assert len(result) == 12
        for cond in ["AAAB", "AXAB", "AAXB", "AAAX", "BBBA", "BXBA", "BBXA", "BBBX", 
                     "RRRR", "RXRR", "RRXR", "RRRX"]:
            assert cond in result


# ============================================================================
# Claim Safety Tests
# ============================================================================

class TestClaimSafety:
    """Test that outputs are marked as computational scaffolds."""
    
    def test_Y_tensor_claim_status(self):
        """Y tensor should be truth_safe_unverified."""
        # Minimal Y_result structure
        Y_result = build_Y_tensor(
            band_power_epochs={},
            channel_area_layer_map=pd.DataFrame(),
            event_axis={},
            bands=[],
            areas=[],
        )
        
        assert Y_result["computational_scaffold"] is True
        assert Y_result["truth_safe_unverified"] is True
    
    def test_H_harmony_claim_status(self):
        """H harmony should be truth_safe_unverified."""
        Y_result = {
            "Y": np.random.rand(1, 2, 1, 1),
            "dims": ["band", "area", "epoch", "layer"],
            "coords": {
                "band": ["gamma"],
                "area": ["V1", "V2"],
                "epoch": ["p1"],
                "layer": ["unresolved"],
            },
            "warnings": [],
        }
        
        H_result = build_H_harmony(Y_result)
        
        assert H_result["computational_scaffold"] is True
        assert H_result["truth_safe_unverified"] is True
