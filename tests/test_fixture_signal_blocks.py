import pytest
import numpy as np
from src.analysis.contracts.fixture_signal_blocks import make_fixture_signal_block, make_fixture_signal_blocks_for_all_signals
from src.analysis.io.loader import DataLoader
from src.analysis.contracts.signal_block import SignalBlock

def test_spk_sua_muae_lfp_shapes():
    # 1. SPK fixture block shape is trial x unit x time.
    spk_block = make_fixture_signal_block(
        signal_class="SPK",
        n_trials=4,
        n_units_or_channels=5,
        n_time=20
    )
    assert spk_block.data.shape == (4, 5, 20)
    assert spk_block.dims == ("trial", "unit", "time")

    # 2. SUA fixture block shape is trial x unit x time.
    sua_block = make_fixture_signal_block(
        signal_class="SUA",
        n_trials=3,
        n_units_or_channels=2,
        n_time=15
    )
    assert sua_block.data.shape == (3, 2, 15)
    assert sua_block.dims == ("trial", "unit", "time")

    # 3. MUAe fixture block shape is trial x channel x time.
    muae_block = make_fixture_signal_block(
        signal_class="MUAe",
        n_trials=6,
        n_units_or_channels=7,
        n_time=30
    )
    assert muae_block.data.shape == (6, 7, 30)
    assert muae_block.dims == ("trial", "channel", "time")

    # 4. LFP fixture block shape is trial x channel x time.
    lfp_block = make_fixture_signal_block(
        signal_class="LFP",
        n_trials=2,
        n_units_or_channels=4,
        n_time=50
    )
    assert lfp_block.data.shape == (2, 4, 50)
    assert lfp_block.dims == ("trial", "channel", "time")

def test_time_base_preservation():
    # 5. time_base p1_relative and omission_relative are both preserved.
    block_p1 = make_fixture_signal_block("LFP", time_base="p1_relative")
    assert block_p1.time_base == "p1_relative"

    block_om = make_fixture_signal_block("LFP", time_base="omission_relative")
    assert block_om.time_base == "omission_relative"

def test_v3_generic_warning():
    # 6. generic V3 area label produces warning/unresolved status.
    block = make_fixture_signal_block("LFP", area_labels=["V1", "V3", "PFC"])
    assert any("generic unresolved V3" in w for w in block.warnings)

def test_dp_area_normalization():
    # 7. DP area label normalizes or is represented consistently with existing contract rules.
    block = make_fixture_signal_block("LFP", area_labels=["DP", "DP (V4)", "V1"])
    assert block.area_labels == ["V4", "V4", "V1"]

def test_wrong_signal_class():
    # 8. wrong signal_class is rejected or returns validation error.
    with pytest.raises(ValueError, match="SignalBlock validation failed"):
        make_fixture_signal_block("INVALID_SIGNAL_CLASS")

def test_dataloader_fixture_wrapper():
    # 9. DataLoader fixture wrapper returns a valid SignalBlock.
    loader = DataLoader()
    block = loader.make_fixture_signal_block("SPK")
    assert isinstance(block, SignalBlock)
    assert not block.validate()

    block_loaded = loader.load_fixture_signal_block("MUAe")
    assert isinstance(block_loaded, SignalBlock)
    assert not block_loaded.validate()

def test_provenance():
    # 10. provenance states no raw data read.
    block = make_fixture_signal_block("SPK")
    assert block.provenance.get("type") == "fixture_synthetic"
    assert block.provenance.get("message") == "no raw data read"

def test_all_signals_helper():
    blocks = make_fixture_signal_blocks_for_all_signals()
    assert "SPK" in blocks
    assert "MUAe" in blocks
    assert "LFP" in blocks
    for name, block in blocks.items():
        assert block.signal_class == name
        assert not block.validate()
