import numpy as np
import pytest
from src.analysis.coherence.coherence import compute_spectral_coherence

def test_spectral_coherence():
    # 1. Perfectly coherent signals at 10Hz
    fs = 1000.0
    t = np.arange(10000) / fs
    x = np.sin(2 * np.pi * 10 * t)
    y = np.sin(2 * np.pi * 10 * t + np.pi/3)  # phase shifted but fully coherent
    
    f, cxy = compute_spectral_coherence(x, y, fs=fs)
    
    # Coherence at 10Hz should be very high (near 1.0)
    idx_10hz = np.argmin(np.abs(f - 10.0))
    assert cxy[idx_10hz] > 0.95

    # 2. Uncorrelated white noise signals
    np.random.seed(42)
    x_rand = np.random.normal(0, 1, 10000)
    y_rand = np.random.normal(0, 1, 10000)
    
    f, cxy_rand = compute_spectral_coherence(x_rand, y_rand, fs=fs)
    # Mean coherence across frequencies should be low
    assert np.mean(cxy_rand) < 0.15
