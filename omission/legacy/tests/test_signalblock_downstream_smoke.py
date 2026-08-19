import pytest
import numpy as np
from src.analysis.contracts import (
    make_fixture_signal_block,
    as_array,
    assert_signal_dims,
    summarize_signal_block,
    split_signal_axis
)

def test_as_array_preserves_shape():
    # 1. as_array returns data for SPK fixture block without changing shape.
    spk_block = make_fixture_signal_block("SPK", n_trials=3, n_units_or_channels=4, n_time=12)
    spk_data = as_array(spk_block)
    assert isinstance(spk_data, np.ndarray)
    assert spk_data.shape == (3, 4, 12)

    # 2. as_array returns data for LFP fixture block without changing shape.
    lfp_block = make_fixture_signal_block("LFP", n_trials=5, n_units_or_channels=8, n_time=30)
    lfp_data = as_array(lfp_block)
    assert isinstance(lfp_data, np.ndarray)
    assert lfp_data.shape == (5, 8, 30)

def test_assert_signal_dims():
    # 3. assert_signal_dims accepts SPK/SUA trial,unit,time.
    spk_block = make_fixture_signal_block("SPK")
    assert_signal_dims(spk_block, ("trial", "unit", "time"))
    
    sua_block = make_fixture_signal_block("SUA")
    assert_signal_dims(sua_block, ("trial", "unit", "time"))

    # 4. assert_signal_dims accepts MUAe/LFP trial,channel,time.
    muae_block = make_fixture_signal_block("MUAe")
    assert_signal_dims(muae_block, ("trial", "channel", "time"))
    
    lfp_block = make_fixture_signal_block("LFP")
    assert_signal_dims(lfp_block, ("trial", "channel", "time"))

    # 5. Wrong dims produce a clear failure.
    with pytest.raises(ValueError, match="dimensions .* do not match expected"):
        assert_signal_dims(spk_block, ("trial", "channel", "time"))

def test_summarize_signal_block():
    # 6. summarize_signal_block reports metadata and shape without biological claims.
    block = make_fixture_signal_block("SPK", n_trials=3, n_units_or_channels=5, n_time=15)
    summary = summarize_signal_block(block)
    
    assert summary["signal_class"] == "SPK"
    assert summary["session_id"] == "fixture_session"
    assert summary["condition"] == "AAAB"
    assert summary["shape"] == (3, 5, 15)
    assert summary["n_trials"] == 3
    assert summary["n_units_or_channels"] == 5
    assert summary["n_time"] == 15
    assert summary["time_base"] == "p1_relative"
    assert summary["truth_status"] == "truth_safe_unverified"

def test_synthetic_spk_mean():
    # 7. A small synthetic SPK block can compute a trivial mean over the time axis while preserving trial/unit axes.
    # fill_value=2.0 so mean over time axis (size 10) is also 2.0
    block = make_fixture_signal_block("SPK", n_trials=2, n_units_or_channels=3, n_time=10, fill_value=2.0)
    arr = as_array(block)
    
    axes = split_signal_axis(block)
    time_ax = axes["time_axis"]
    
    mean_val = np.mean(arr, axis=time_ax)
    assert mean_val.shape == (2, 3)
    np.testing.assert_allclose(mean_val, 2.0)

def test_synthetic_lfp_mean():
    # 8. A small synthetic LFP block can compute a trivial mean over the time axis while preserving trial/channel axes.
    block = make_fixture_signal_block("LFP", n_trials=4, n_units_or_channels=6, n_time=100, fill_value=5.5)
    arr = as_array(block)
    
    axes = split_signal_axis(block)
    time_ax = axes["time_axis"]
    
    mean_val = np.mean(arr, axis=time_ax)
    assert mean_val.shape == (4, 6)
    np.testing.assert_allclose(mean_val, 5.5)
