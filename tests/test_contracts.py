import pytest
import numpy as np
from src.analysis.contracts import SessionManifest, SignalBlock
from src.analysis.contracts.constants import (
    TRUTH_SAFE_UNVERIFIED,
    ALLOWED_SIGNAL_CLASSES,
    ALLOWED_TIME_BASES,
    AREA_ALIASES,
    GENERIC_UNRESOLVED_AREAS,
    REQUIRED_SESSION_MANIFEST_FIELDS,
    REQUIRED_SIGNAL_BLOCK_FIELDS
)

def test_session_manifest_validation_and_methods():
    # 1. SessionManifest loads fixture manifest and validates required fields
    manifest = SessionManifest(
        session_id="230630_fixture",
        subject="FixtureSubject",
        signal_availability={"SPK": True, "MUAe": False, "LFP": True}
    )
    
    errors = manifest.validate()
    assert not errors, f"Validation failed: {errors}"
    assert manifest.is_fixture()
    assert not manifest.is_real_metadata_derived()
    
    # 2. DP normalizes to V4
    assert SessionManifest.normalize_area("DP") == "V4"
    assert SessionManifest.normalize_area("DP (V4)") == "V4"
    assert SessionManifest.normalize_area("V1") == "V1"
    
    # 3. generic V3 triggers warning / unresolved status
    manifest_v3 = SessionManifest(
        session_id="230630_fixture",
        subject="FixtureSubject",
        channel_counts_by_area={"V3": 64},
        area_resolution_status={"V3": "unresolved"},
        signal_availability={"SPK": True, "MUAe": False, "LFP": True}
    )
    errors = manifest_v3.validate()
    assert not errors, f"Validation errors: {errors}"
    assert any("Area V3 is UNRESOLVED generic V3." in w for w in manifest_v3.warnings)

    # 4. fixture manifest cannot claim real_metadata_derived
    manifest_claims = SessionManifest(
        session_id="230630_fixture",
        subject="FixtureSubject",
        source_files=["some_file.npy"],
        hashes={"some_file.npy": "abcdef"},
        signal_availability={"SPK": True, "MUAe": False, "LFP": True}
    )
    assert manifest_claims.is_fixture()
    assert not manifest_claims.is_real_metadata_derived()
    errors = manifest_claims.validate()
    assert "Fixture manifest cannot claim real_metadata_derived." in errors

    # 5. truth_status defaults to truth_safe_unverified
    assert manifest.truth_status == "truth_safe_unverified"


def test_signal_block_validation():
    # Helper dummy data
    spk_data = np.zeros((10, 5, 100)) # 10 trials, 5 units, 100 time points
    lfp_data = np.zeros((10, 8, 1000)) # 10 trials, 8 channels, 1000 time points
    
    # 1. SignalBlock validates SPK shape trial x unit x time
    block_spk = SignalBlock(
        data=spk_data,
        dims=("trial", "unit", "time"),
        signal_class="SPK",
        session_id="230630_fixture",
        condition="AXAB",
        time_base="p1_relative",
        alignment_event="stim_onset",
        window_ms=(-100, 500),
        sampling_rate=1000.0,
        unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
        area_labels=["V1", "V1", "V2", "V2", "V4"]
    )
    errors = block_spk.validate()
    assert not errors, f"SPK validation failed: {errors}"
    
    # 2. SignalBlock validates LFP/MUAe shape trial x channel x time
    block_lfp = SignalBlock(
        data=lfp_data,
        dims=("trial", "channel", "time"),
        signal_class="LFP",
        session_id="230630_fixture",
        condition="AXAB",
        time_base="omission_relative",
        alignment_event="omission_onset",
        window_ms=(-500, 1000),
        sampling_rate=1000.0,
        unit_or_channel_ids=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
        area_labels=["V1", "V1", "V2", "V2", "V3", "V3", "V4", "V4"]
    )
    errors = block_lfp.validate()
    assert not errors, f"LFP validation failed: {errors}"
    # check that generic V3 triggered a warning
    assert any("Area labels contain generic unresolved V3." in w for w in block_lfp.warnings)
    
    # 3. SignalBlock rejects or reports wrong dims for signal class
    block_bad_dims = SignalBlock(
        data=spk_data,
        dims=("trial", "channel", "time"), # Expected ("trial", "unit", "time")
        signal_class="SPK",
        session_id="230630_fixture",
        condition="AXAB",
        time_base="p1_relative",
        alignment_event="stim_onset",
        window_ms=(-100, 500),
        sampling_rate=1000.0,
        unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
        area_labels=["V1", "V1", "V2", "V2", "V4"]
    )
    errors = block_bad_dims.validate()
    assert any("Expected dims" in err for err in errors)
    
    # 4. SignalBlock preserves time_base distinction
    assert block_spk.time_base == "p1_relative"
    assert block_lfp.time_base == "omission_relative"
    
    # Check invalid time base
    block_bad_tb = SignalBlock(
        data=spk_data,
        dims=("trial", "unit", "time"),
        signal_class="SPK",
        session_id="230630_fixture",
        condition="AXAB",
        time_base="invalid_time_base",
        alignment_event="stim_onset",
        window_ms=(-100, 500),
        sampling_rate=1000.0,
        unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
        area_labels=["V1", "V1", "V2", "V2", "V4"]
    )
    errors = block_bad_tb.validate()
    assert any("Invalid time_base" in err for err in errors)
    
    # Check area label length mismatch
    block_mismatch = SignalBlock(
        data=spk_data,
        dims=("trial", "unit", "time"),
        signal_class="SPK",
        session_id="230630_fixture",
        condition="AXAB",
        time_base="p1_relative",
        alignment_event="stim_onset",
        window_ms=(-100, 500),
        sampling_rate=1000.0,
        unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
        area_labels=["V1", "V1"] # Expecting 5 labels
    )
    errors = block_mismatch.validate()
    assert any("area_labels length" in err for err in errors)


def test_loader_contract_integration():
    from src.analysis.io.loader import DataLoader
    from src.scripts.build_session_manifest import build_manifest
    from pathlib import Path
    import os
    
    # Ensure fixture manifests are built if they do not exist
    out_dir = Path("artifacts/test_manifests")
    for session_id in ["230630", "230719"]:
        if not (out_dir / f"session_{session_id}_manifest.json").exists():
            build_manifest(session_id, str(out_dir), fixture_mode=True)
            
    # Instantiate DataLoader
    loader = DataLoader()
    
    # 1. fixture SessionManifest can be loaded through the new loader/helper path
    manifest = loader.load_session_manifest_fixture("230630")
    assert manifest.session_id == "230630"
    assert manifest.is_fixture()
    
    # 2. fixture manifest validation catches synthetic/fixture role
    from src.analysis.contracts import SessionManifest
    manifest_bad = SessionManifest(
        session_id="230630_fixture",
        subject="FixtureSubject",
        source_files=["some_file.npy"],
        hashes={"some_file.npy": "abcdef"},
        signal_availability={"SPK": True, "MUAe": False, "LFP": True}
    )
    errors = manifest_bad.validate()
    assert "Fixture manifest cannot claim real_metadata_derived." in errors
    
    # 3. DP normalizes to V4 through the same path DataLoader will use
    manifest_dp = loader.load_session_manifest_fixture("230719")
    areas = [m.area for m in manifest_dp.area_mappings]
    assert "V4" in areas
    assert "DP" not in areas
    assert "DP (V4)" not in areas
    
    # 4. generic V3 is preserved as unresolved/warning, not silently split
    v3_entry = [m for m in manifest.area_mappings if m.area == "V3"]
    assert len(v3_entry) > 0
    assert v3_entry[0].resolution_status == "unresolved"
    assert any("Area V3 on Probe 2 is UNRESOLVED generic V3." in w for w in manifest.warnings)
    
    # 5. SPK fixture zeros array wraps into SignalBlock as trial x unit x time
    spk_data = np.zeros((10, 5, 100))
    block_spk = loader.make_signal_block(
        data=spk_data,
        dims=("trial", "unit", "time"),
        signal_class="SPK",
        session_id="230630",
        condition="AXAB",
        time_base="p1_relative",
        alignment_event="stim_onset",
        window_ms=(-100, 500),
        sampling_rate=1000.0,
        unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
        area_labels=["V1", "V1", "V2", "V2", "V4"]
    )
    assert block_spk.dims == ("trial", "unit", "time")
    
    # 6. LFP fixture zeros array wraps into SignalBlock as trial x channel x time
    lfp_data = np.zeros((10, 8, 1000))
    block_lfp = loader.make_signal_block(
        data=lfp_data,
        dims=("trial", "channel", "time"),
        signal_class="LFP",
        session_id="230630",
        condition="AXAB",
        time_base="omission_relative",
        alignment_event="omission_onset",
        window_ms=(-500, 1000),
        sampling_rate=1000.0,
        unit_or_channel_ids=["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"],
        area_labels=["V1", "V1", "V2", "V2", "V3", "V3", "V4", "V4"]
    )
    assert block_lfp.dims == ("trial", "channel", "time")
    
    # 7. wrong dims are rejected or produce validation errors
    with pytest.raises(ValueError, match="SignalBlock validation failed"):
        loader.make_signal_block(
            data=spk_data,
            dims=("trial", "channel", "time"), # Wrong for SPK
            signal_class="SPK",
            session_id="230630",
            condition="AXAB",
            time_base="p1_relative",
            alignment_event="stim_onset",
            window_ms=(-100, 500),
            sampling_rate=1000.0,
            unit_or_channel_ids=["u1", "u2", "u3", "u4", "u5"],
            area_labels=["V1", "V1", "V2", "V2", "V4"]
        )
    
def test_metadata_contract_constants_convergence():
    # 1. Verify constants are defined correctly
    assert TRUTH_SAFE_UNVERIFIED == "truth_safe_unverified"
    assert "SPK" in ALLOWED_SIGNAL_CLASSES
    assert "LFP" in ALLOWED_SIGNAL_CLASSES
    assert "p1_relative" in ALLOWED_TIME_BASES
    assert "omission_relative" in ALLOWED_TIME_BASES
    assert AREA_ALIASES["DP"] == "V4"
    assert "V3" in GENERIC_UNRESOLVED_AREAS
    
    # 2. Verify SessionManifest's default and normalization are using the constants
    manifest = SessionManifest(
        session_id="constant_test_session",
        subject="FixtureSubject",
        signal_availability={"SPK": True, "MUAe": False, "LFP": True}
    )
    assert manifest.truth_status == TRUTH_SAFE_UNVERIFIED
    assert SessionManifest.normalize_area("DP") == AREA_ALIASES["DP"]
    
    # 3. Verify required fields are present
    assert "session_id" in REQUIRED_SESSION_MANIFEST_FIELDS
    assert "subject" in REQUIRED_SESSION_MANIFEST_FIELDS
    assert "truth_status" in REQUIRED_SESSION_MANIFEST_FIELDS
    assert "data" in REQUIRED_SIGNAL_BLOCK_FIELDS


def test_real_data_loader_integration():
    # 8. real-data integration test is skipped unless OMISSION_DATA_ROOT is set
    # 9. no test depends on D:/drive or private raw data
    import os
    data_root = os.environ.get("OMISSION_DATA_ROOT")
    if not data_root:
        pytest.skip("Skipping real-data integration test since OMISSION_DATA_ROOT is not set")
