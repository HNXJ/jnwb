import numpy as np
import pytest
from jnwb.analyzers import UnitAnalyzer, PopulationAnalyzer
from jnwb.spectral import (
    harmonic_analysis,
    cross_area_coherence,
    spectral_tilt,
    band_power
)

def test_gpu_autocorrelogram():
    # Generate mock spike times (100 spikes)
    rng = np.random.default_rng(42)
    spike_times = np.sort(rng.uniform(0.0, 10.0, 100))
    
    # Run with default device
    res_cpu = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=100, bin_size_ms=1, device='cpu')
    assert 'acg' in res_cpu
    assert not res_cpu.get('error')

    # Run with cuda device (should execute on GPU or fall back cleanly)
    res_gpu = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=100, bin_size_ms=1, device='cuda')
    assert 'acg' in res_gpu
    assert not res_gpu.get('error')
    
    # Check shape/values consistency
    assert len(res_cpu['acg']) == len(res_gpu['acg'])


def test_harmonic_analysis_empty_signal_degrades_gracefully():
    """Migrated from legacy/tests/test_spectral_yfiles.py (2026-08-22): an empty
    signal must return a well-formed dict with a float fundamental_freq, not raise."""
    result = harmonic_analysis(np.array([]), 1000.0)
    assert "fundamental_freq" in result
    assert isinstance(result["fundamental_freq"], float)


def test_gpu_spectral_functions():
    # Generate mock LFP trace (1 second, 1000 Hz)
    rng = np.random.default_rng(42)
    t = np.linspace(0, 1, 1000)
    lfp = np.sin(2 * np.pi * 10 * t) + rng.normal(0, 0.1, 1000)
    
    # Test harmonic analysis
    res_harm_cpu = harmonic_analysis(lfp, sampling_rate=1000.0, device='cpu')
    res_harm_gpu = harmonic_analysis(lfp, sampling_rate=1000.0, device='cuda')
    assert res_harm_cpu['fundamental_freq'] > 0
    assert res_harm_gpu['fundamental_freq'] > 0

    # Test cross area coherence
    lfp2 = np.sin(2 * np.pi * 10 * t + 0.5) + rng.normal(0, 0.1, 1000)
    res_coh_cpu = cross_area_coherence(lfp, lfp2, sampling_rate=1000.0, device='cpu')
    res_coh_gpu = cross_area_coherence(lfp, lfp2, sampling_rate=1000.0, device='cuda')
    assert 'theta' in res_coh_cpu['band_coherence']
    assert 'theta' in res_coh_gpu['band_coherence']

    # Test spectral tilt
    res_tilt_cpu = spectral_tilt(lfp, sampling_rate=1000.0, device='cpu')
    res_tilt_gpu = spectral_tilt(lfp, sampling_rate=1000.0, device='cuda')
    assert 'exponent' in res_tilt_cpu
    assert 'exponent' in res_tilt_gpu

    # Test band power
    p_cpu = band_power(lfp, sampling_rate=1000.0, freq_range=(8, 12), device='cpu')
    p_gpu = band_power(lfp, sampling_rate=1000.0, freq_range=(8, 12), device='cuda')
    assert p_cpu != 0
    assert p_gpu != 0


def test_population_trajectory():
    # Mock data (100 time points, 10 neurons)
    rng = np.random.default_rng(42)
    X = rng.normal(0, 1, (100, 10))
    
    res_cpu = PopulationAnalyzer.population_trajectory(X, n_components=3, device='cpu')
    assert res_cpu['projection'].shape == (100, 3)
    assert res_cpu['components'].shape == (3, 10)
    assert len(res_cpu['explained_variance']) == 3
    assert len(res_cpu['explained_variance_ratio']) == 3
    
    res_gpu = PopulationAnalyzer.population_trajectory(X, n_components=3, device='cuda')
    assert res_gpu['projection'].shape == (100, 3)
    assert res_gpu['components'].shape == (3, 10)
    assert len(res_gpu['explained_variance']) == 3
    assert len(res_gpu['explained_variance_ratio']) == 3
