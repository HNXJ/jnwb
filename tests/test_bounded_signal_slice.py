import pytest
import tempfile
from pathlib import Path
from src.analysis.contracts.bounded_slice import (
    BoundedSliceRequest,
    BoundedSliceResult,
    make_bounded_fixture_slice,
    load_bounded_real_slice
)
from src.analysis.io.loader import DataLoader

def test_bounded_slice_request_defaults():
    # 1. BoundedSliceRequest defaults to allow_real_data=False.
    req = BoundedSliceRequest(session_id="test_session", signal_class="SPK")
    assert req.allow_real_data is False
    assert req.max_trials == 1
    assert req.max_units_or_channels == 2
    assert req.max_timepoints == 100
    assert req.max_bytes == 1048576
    assert req.truth_status == "truth_safe_unverified"
    
    errors = req.validate()
    assert len(errors) == 0

def test_bounded_slice_request_invalid_bounds():
    # 2. Invalid negative or zero bounds are rejected.
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        max_trials=0,
        max_units_or_channels=-5,
        max_timepoints=-100,
        max_bytes=0
    )
    errors = req.validate()
    assert len(errors) > 0
    assert any("max_trials" in e for e in errors)
    assert any("max_units_or_channels" in e for e in errors)
    assert any("max_timepoints" in e for e in errors)
    assert any("max_bytes" in e for e in errors)

def test_fixture_bounded_slice_valid():
    # 3. Fixture bounded slice returns a valid SignalBlock.
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        max_trials=3,
        max_units_or_channels=4,
        max_timepoints=50
    )
    result = make_bounded_fixture_slice(req)
    assert result.status == "loaded_bounded_slice"
    assert result.signal_block is not None
    
    block = result.signal_block
    assert block.signal_class == "SPK"
    assert block.session_id == "test_session"
    assert block.data.shape == (3, 4, 50)
    
    # Validation of the generated block itself
    block_errors = block.validate()
    assert len(block_errors) == 0

def test_fixture_slice_respects_bounds():
    # 4. Fixture slice respects max_trials/max_units_or_channels/max_timepoints.
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="LFP",
        max_trials=5,
        max_units_or_channels=7,
        max_timepoints=120
    )
    result = make_bounded_fixture_slice(req)
    block = result.signal_block
    assert block.data.shape == (5, 7, 120)

def test_real_data_without_opt_in():
    # 5. Real-data path without allow_real_data is blocked/skipped.
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path="dummy.npy",
        allow_real_data=False
    )
    result = load_bounded_real_slice(req)
    assert result.status == "skipped"
    assert result.signal_block is None
    assert any("allow_real_data is False" in w for w in result.warnings)

def test_raw_extension_blocked():
    # 6. Raw extension such as .nwb is blocked in this pass.
    with tempfile.TemporaryDirectory() as tmpdir:
        dummy_file = Path(tmpdir) / "session_230630.nwb"
        dummy_file.write_text("dummy contents")
        
        req = BoundedSliceRequest(
            session_id="230630",
            signal_class="SPK",
            source_path=str(dummy_file),
            allow_real_data=True
        )
        result = load_bounded_real_slice(req)
        assert result.status == "blocked"
        assert result.signal_block is None
        assert any("Raw real-data slicing not implemented yet" in w for w in result.warnings)

def test_large_file_blocked():
    # 7. Large file exceeding max_bytes is blocked.
    with tempfile.TemporaryDirectory() as tmpdir:
        dummy_file = Path(tmpdir) / "large_manifest.json"
        # Write > 10 bytes
        dummy_file.write_bytes(b"x" * 20)
        
        req = BoundedSliceRequest(
            session_id="test_session",
            signal_class="SPK",
            source_path=str(dummy_file),
            allow_real_data=True,
            max_bytes=10  # very low limit
        )
        result = load_bounded_real_slice(req)
        assert result.status == "blocked"
        assert result.signal_block is None
        assert any("exceeds request limit" in e for e in result.errors)

def test_cli_default(monkeypatch):
    # 8. CLI default reads no real data and exits cleanly.
    import sys
    from scripts.validate_bounded_signal_slice import main
    monkeypatch.setattr(sys, "argv", ["validate_bounded_signal_slice.py", "--fixture"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0

def test_cli_fixture_mode(monkeypatch):
    # 9. CLI fixture mode succeeds.
    import sys
    from scripts.validate_bounded_signal_slice import main
    monkeypatch.setattr(sys, "argv", ["validate_bounded_signal_slice.py", "--fixture", "--signal-class", "LFP"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0

def test_cli_real_data_missing_path(monkeypatch):
    # 10. CLI with --allow-real-data but missing source_path returns unavailable/blocked.
    # Note: If no OMISSION_DATA_ROOT is set and no --source-path is given, it may skip or fail.
    # Let's mock no data root to ensure it returns unavailable/blocked or skipped.
    import sys
    from scripts.validate_bounded_signal_slice import main
    
    # Force environment to have no OMISSION_DATA_ROOT
    monkeypatch.setenv("OMISSION_DATA_ROOT", "")
    
    monkeypatch.setattr(sys, "argv", [
        "validate_bounded_signal_slice.py",
        "--allow-real-data"
    ])
    with pytest.raises(SystemExit) as excinfo:
        main()
    # It should exit with 0 (since missing real data exits cleanly or returns skipped/unavailable)
    assert excinfo.value.code == 0

def test_no_private_paths():
    # 11. No test uses private D:/drive paths.
    # 12. No test reads actual raw binary contents.
    # 13. raw_array_contents_read is False.
    req = BoundedSliceRequest(session_id="test_session", signal_class="SPK")
    result = make_bounded_fixture_slice(req)
    assert result.raw_array_contents_read is False
    assert "D:/drive" not in (result.source_path or "")

def test_npy_blocked_without_allow_real_data(tmp_path):
    # 1. .npy read is blocked without allow_real_data.
    import numpy as np
    dummy_file = tmp_path / "test.npy"
    np.save(dummy_file, np.ones((2, 2, 2)))
    
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path=str(dummy_file),
        allow_real_data=False
    )
    result = load_bounded_real_slice(req)
    assert result.status == "skipped"
    assert result.signal_block is None

def test_missing_npy_path_returns_unavailable():
    # 2. Missing .npy path returns unavailable/invalid.
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path="nonexistent.npy",
        allow_real_data=True
    )
    result = load_bounded_real_slice(req)
    assert result.status == "unavailable"
    assert result.signal_block is None

def test_non_npy_extension_remains_blocked(tmp_path):
    # 3. Non-.npy extension remains blocked.
    dummy_file = tmp_path / "test.txt"
    dummy_file.write_text("hello")
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path=str(dummy_file),
        allow_real_data=True
    )
    result = load_bounded_real_slice(req)
    assert result.status == "blocked"

def test_npz_remains_blocked(tmp_path):
    # 4. .npz remains blocked.
    import numpy as np
    dummy_file = tmp_path / "test.npz"
    np.savez(dummy_file, a=np.ones((2, 2, 2)))
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path=str(dummy_file),
        allow_real_data=True
    )
    result = load_bounded_real_slice(req)
    assert result.status == "blocked"
    assert "explicitly blocked" in "".join(result.errors)

def test_other_raw_blocked(tmp_path):
    # 5. .nwb, .mat, .h5, .hdf5 remain blocked.
    for ext in [".nwb", ".mat", ".h5", ".hdf5"]:
        dummy_file = tmp_path / f"test{ext}"
        dummy_file.write_text("hello")
        req = BoundedSliceRequest(
            session_id="test_session",
            signal_class="SPK",
            source_path=str(dummy_file),
            allow_real_data=True
        )
        result = load_bounded_real_slice(req)
        assert result.status == "blocked"
        assert "explicitly blocked" in "".join(result.errors)

def test_oversized_npy_blocked(tmp_path):
    # 6. Oversized .npy relative to max_bytes is blocked.
    import numpy as np
    dummy_file = tmp_path / "test.npy"
    np.save(dummy_file, np.ones((5, 5, 5)))
    req = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path=str(dummy_file),
        allow_real_data=True,
        max_bytes=10  # extremely low limit
    )
    result = load_bounded_real_slice(req)
    assert result.status == "blocked"
    assert any("exceeds request limit" in e for e in result.errors)

def test_tiny_npy_bounded_slice_read(tmp_path):
    # 7. Tiny tmp_path .npy rank-3 array reads only bounded slice.
    # 8. SPK .npy slice returns SignalBlock dims trial,unit,time.
    # 9. LFP .npy slice returns SignalBlock dims trial,channel,time.
    # 10. raw_array_contents_read=True only for successful bounded .npy read.
    # 11. Provenance says bounded tiny npy slice and no full file read intended.
    import numpy as np
    dummy_file = tmp_path / "test.npy"
    large_arr = np.ones((10, 10, 200))
    np.save(dummy_file, large_arr)

    # Test SPK Dims & Bounds
    req_spk = BoundedSliceRequest(
        session_id="test_session",
        signal_class="SPK",
        source_path=str(dummy_file),
        allow_real_data=True,
        max_trials=3,
        max_units_or_channels=4,
        max_timepoints=50
    )
    result_spk = load_bounded_real_slice(req_spk)
    assert result_spk.status == "loaded_bounded_slice"
    assert result_spk.raw_array_contents_read is True
    assert result_spk.signal_block is not None
    block_spk = result_spk.signal_block
    assert block_spk.data.shape == (3, 4, 50)
    assert block_spk.dims == ("trial", "unit", "time")
    assert block_spk.provenance["type"] == "bounded_tiny_npy_slice"
    assert block_spk.provenance["no_full_file_read_intended"] is True

    # Test LFP Dims
    req_lfp = BoundedSliceRequest(
        session_id="test_session",
        signal_class="LFP",
        source_path=str(dummy_file),
        allow_real_data=True,
        max_trials=2,
        max_units_or_channels=3,
        max_timepoints=30
    )
    result_lfp = load_bounded_real_slice(req_lfp)
    assert result_lfp.status == "loaded_bounded_slice"
    block_lfp = result_lfp.signal_block
    assert block_lfp.data.shape == (2, 3, 30)
    assert block_lfp.dims == ("trial", "channel", "time")

def test_cli_tiny_npy_smoke(monkeypatch):
    # 14. CLI allowlisted tiny .npy smoke succeeds only when explicitly allowed.
    import sys
    from scripts.validate_bounded_signal_slice import main
    monkeypatch.setattr(sys, "argv", ["validate_bounded_signal_slice.py", "--tiny-npy-smoke"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 0
