import numpy as np
import pytest
from src.analysis.harmonic.harmonic import compute_nm_phase_coupling, compute_spk_lfp_plv
from src.analysis.lfp.stats import compute_modulation_index

def test_nm_phase_coupling():
    # 1. Perfect 1:2 coupling: phase_high = 2 * phase_low + offset
    t = np.linspace(0, 10, 1000)
    phase_low = 2 * np.pi * 6 * t  # 6 Hz
    phase_high = 2 * np.pi * 12 * t + np.pi/4  # 12 Hz with phase shift
    
    plv_1_2 = compute_nm_phase_coupling(phase_low, phase_high, n=2, m=1)
    assert pytest.approx(plv_1_2, abs=1e-5) == 1.0

    # 2. Perfect 1:3 coupling
    phase_high_3 = 2 * np.pi * 18 * t + np.pi/6  # 18 Hz
    plv_1_3 = compute_nm_phase_coupling(phase_low, phase_high_3, n=3, m=1)
    assert pytest.approx(plv_1_3, abs=1e-5) == 1.0

    # 3. Uncoupled signals
    np.random.seed(42)
    phase_rand = np.random.uniform(-np.pi, np.pi, 1000)
    plv_rand = compute_nm_phase_coupling(phase_low, phase_rand, n=2, m=1)
    assert plv_rand < 0.15

def test_spk_lfp_plv():
    # 1. Perfect locking: spikes occur at exactly the peak of 6Hz wave (timestamps = integer multiples of 1/6s)
    t = np.linspace(0, 10, 10000)
    lfp_phase = (2 * np.pi * 6 * t) % (2 * np.pi) - np.pi  # 6 Hz phase wrapped to [-pi, pi]
    
    spike_times = np.arange(0.5, 9.5, 1/6)  # spikes at 1/6s intervals, where phase is 0
    plv = compute_spk_lfp_plv(spike_times, lfp_phase, t)
    assert pytest.approx(plv, abs=0.05) == 1.0
    
    # 2. No locking
    np.random.seed(42)
    spike_times_rand = np.random.uniform(0, 10, 50)
    plv_rand = compute_spk_lfp_plv(spike_times_rand, lfp_phase, t)
    assert plv_rand < 0.3

def test_modulation_index():
    # Phase modulating amplitude
    t = np.linspace(0, 10, 10000)
    phase = np.sin(2 * np.pi * 6 * t)
    # Amplitude maximum at phase peak
    amplitude = 1 + np.sin(2 * np.pi * 6 * t)
    
    mi = compute_modulation_index(phase, amplitude, n_bins=18)
    assert mi > 0.05
