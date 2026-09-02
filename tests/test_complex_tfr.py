"""Comprehensive test suite and numerical probes for jnwb.tfr.complex_tfr.

Verifies all required mathematical probes:
1. Sinusoid frequency localization (peak amplitude at target frequency)
2. Known sinusoid phase recovery (recovering exact analytical phase)
3. Impulse temporal localization
4. Linear amplitude scaling
5. Quadratic power scaling
6. Scalar vs vector cycles
7. 1D, multichannel, and nonterminal time_axis tensor shape preservation
8. Invalid inputs (fs, freqs, n_cycles, NaN/Inf) error handling
9. Edge / Cone of Influence (COI) exact boundary behavior
10. complex64 vs complex128 numerical precision
11. Direct compatibility with TFRAccumulator
12. Genuinely independent reference implementation comparison for complex coefficients
13. Adversarial nonterminal time_axis equivalence against 1D trace iteration
"""

import pytest
import numpy as np
from scipy import signal

import jnwb
from jnwb.tfr import complex_tfr, morlet_wavelet, ComplexTFR
from jnwb.tfr_accumulator import TFRAccumulator


def _independent_reference_morlet_cwt(x: np.ndarray, fs: float, f0: float, n_cycles: float) -> np.ndarray:
    """Genuinely independent reference implementation of continuous Morlet transform.

    Computes convolution via direct, independently coded continuous-time Morlet equation
    and discrete direct convolution (signal.convolve mode='same') without calling jnwb.tfr.
    """
    sigma_t = n_cycles / (2.0 * np.pi * f0)
    # 4-sigma truncation
    k_half = int(np.ceil(4.0 * sigma_t * fs))
    t_vec = np.arange(-k_half, k_half + 1, dtype=np.float64) / fs
    
    # Direct formula
    gaussian_envelope = np.exp(-0.5 * (t_vec / sigma_t) ** 2)
    carrier = np.exp(1j * 2.0 * np.pi * f0 * t_vec)
    kernel_raw = gaussian_envelope * carrier
    
    # L1 amplitude normalization factor: 2.0 / sum(gaussian_envelope)
    kernel_normalized = (2.0 / np.sum(gaussian_envelope)) * kernel_raw
    
    # Direct discrete convolution
    z_ref = signal.convolve(x, kernel_normalized, mode="same")
    return z_ref


class TestComplexTFRProbes:
    @pytest.fixture
    def fs(self):
        return 1000.0

    @pytest.fixture
    def freqs(self):
        return np.linspace(10.0, 60.0, 11)  # 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60 Hz

    def test_probe01_sinusoid_frequency_localization(self, fs, freqs):
        """Probe 1: Pure 30 Hz sinusoid must peak strictly at 30 Hz (freq index 4)."""
        t = np.arange(2000) / fs
        f_target = 30.0
        x = 1.0 * np.cos(2.0 * np.pi * f_target * t)

        tfr = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=7.0, normalization="amplitude")
        mid = 1000  # interior point away from boundaries
        power_spectrum = tfr.power[:, mid]

        peak_idx = int(np.argmax(power_spectrum))
        assert freqs[peak_idx] == f_target
        # Peak power of 1.0 unit amplitude cosine is 1.0 (relative error < 0.1%)
        assert pytest.approx(power_spectrum[peak_idx], rel=1e-3) == 1.0

    def test_probe02_known_sinusoid_phase_recovery(self, fs):
        """Probe 2: Recovers exact analytical phase at known latency."""
        t = np.arange(1000) / fs
        f0 = 25.0
        phi0 = np.pi / 4.0  # 45 degrees
        x = 2.0 * np.cos(2.0 * np.pi * f0 * t + phi0)

        tfr = complex_tfr(x, fs=fs, freqs=np.array([25.0]), n_cycles=6.0, normalization="amplitude")
        
        # Test phase across multiple interior time points
        for mid in [400, 500, 600]:
            true_phase = (2.0 * np.pi * f0 * t[mid] + phi0 + np.pi) % (2.0 * np.pi) - np.pi
            est_phase = tfr.phase[0, mid]
            assert pytest.approx(est_phase, abs=1e-4) == true_phase
            assert pytest.approx(tfr.amplitude[0, mid], rel=1e-3) == 2.0

    def test_probe03_impulse_temporal_localization(self, fs, freqs):
        """Probe 3: Delta impulse delta(t - t_impulse) produces peak envelope at t_impulse."""
        x = np.zeros(1000)
        t_impulse = 500
        x[t_impulse] = 1.0

        tfr = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=5.0)
        for fi in range(len(freqs)):
            peak_t = int(np.argmax(tfr.amplitude[fi]))
            assert peak_t == t_impulse

    def test_probe04_linear_amplitude_scaling(self, fs, freqs):
        """Probe 4: 2 * x(t) strictly doubles complex amplitude magnitude |Z|."""
        rng = np.random.default_rng(42)
        x = rng.normal(size=1000)

        tfr1 = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=5.0)
        tfr2 = complex_tfr(2.0 * x, fs=fs, freqs=freqs, n_cycles=5.0)

        np.testing.assert_allclose(tfr2.amplitude, 2.0 * tfr1.amplitude, rtol=1e-12)
        np.testing.assert_allclose(tfr2.z, 2.0 * tfr1.z, rtol=1e-12)

    def test_probe05_quadratic_power_scaling(self, fs, freqs):
        """Probe 5: 2 * x(t) strictly quadruples instantaneous power |Z|^2."""
        rng = np.random.default_rng(42)
        x = rng.normal(size=1000)

        tfr1 = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=5.0)
        tfr2 = complex_tfr(2.0 * x, fs=fs, freqs=freqs, n_cycles=5.0)

        np.testing.assert_allclose(tfr2.power, 4.0 * tfr1.power, rtol=1e-12)

    def test_probe06_scalar_vs_vector_cycles(self, fs, freqs):
        """Probe 6: Scalar n_cycles=5.0 matches full vector n_cycles=[5.0]*F byte-identically."""
        rng = np.random.default_rng(42)
        x = rng.normal(size=500)

        tfr_scalar = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=5.0)
        tfr_vector = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=np.full(len(freqs), 5.0))

        np.testing.assert_array_equal(tfr_scalar.z, tfr_vector.z)
        np.testing.assert_array_equal(tfr_scalar.coi_mask, tfr_vector.coi_mask)

        # Frequency-dependent cycles
        varying_cycles = np.linspace(3.0, 12.0, len(freqs))
        tfr_varying = complex_tfr(x, fs=fs, freqs=freqs, n_cycles=varying_cycles)
        assert tfr_varying.z.shape == tfr_scalar.z.shape

    def test_probe07_tensor_shapes_and_axes(self, fs, freqs):
        """Probe 7: Shape preservation across 1D, 2D (C, T), 3D (N, C, T) arrays."""
        rng = np.random.default_rng(42)
        n_freqs = len(freqs)

        # 1D: (T,) -> (F, T)
        x1 = rng.normal(size=400)
        tfr1 = complex_tfr(x1, fs=fs, freqs=freqs)
        assert tfr1.shape == (n_freqs, 400)
        assert tfr1.coi_mask.shape == (n_freqs, 400)

        # 2D: (C, T) -> (C, F, T)
        x2 = rng.normal(size=(8, 400))
        tfr2 = complex_tfr(x2, fs=fs, freqs=freqs, time_axis=-1)
        assert tfr2.shape == (8, n_freqs, 400)
        assert tfr2.coi_mask.shape == (8, n_freqs, 400)

        # 3D: (N, C, T) -> (N, C, F, T)
        x3 = rng.normal(size=(5, 4, 300))
        tfr3 = complex_tfr(x3, fs=fs, freqs=freqs, time_axis=-1)
        assert tfr3.shape == (5, 4, n_freqs, 300)
        assert tfr3.coi_mask.shape == (5, 4, n_freqs, 300)

    def test_probe08_invalid_inputs_error_handling(self, fs, freqs):
        """Probe 8: Explicit ValueErrors and TypeErrors on invalid inputs."""
        x = np.ones(200)

        # Non-positive fs
        with pytest.raises(ValueError, match="fs must be positive"):
            complex_tfr(x, fs=0.0, freqs=freqs)
        with pytest.raises(ValueError, match="fs must be positive"):
            complex_tfr(x, fs=-100.0, freqs=freqs)

        # Freqs above Nyquist
        with pytest.raises(ValueError, match="Nyquist"):
            complex_tfr(x, fs=100.0, freqs=np.array([10.0, 55.0]))

        # Unsorted or negative freqs
        with pytest.raises(ValueError, match="strictly positive"):
            complex_tfr(x, fs=fs, freqs=np.array([-5.0, 10.0]))
        with pytest.raises(ValueError, match="strictly monotonically increasing"):
            complex_tfr(x, fs=fs, freqs=np.array([30.0, 20.0]))

        # Non-positive n_cycles
        with pytest.raises(ValueError, match="n_cycles must be positive"):
            complex_tfr(x, fs=fs, freqs=freqs, n_cycles=0.0)

        # Non-finite data
        x_nan = x.copy()
        x_nan[10] = np.nan
        with pytest.raises(ValueError, match="contains NaN or Inf"):
            complex_tfr(x_nan, fs=fs, freqs=freqs)

    def test_probe09_edge_and_coi_exact_boundary(self, fs):
        """Probe 9: COI mask correctly bounds the declared coi_sigma * sigma_t edge region."""
        x = np.ones(1000)
        f0 = 20.0
        n_c = 5.0
        coi_sigma = 2.0
        tfr = complex_tfr(x, fs=fs, freqs=np.array([f0]), n_cycles=n_c, coi_sigma=coi_sigma)

        sigma_t = n_c / (2.0 * np.pi * f0)
        k_coi = int(np.ceil(coi_sigma * sigma_t * fs))  # 32 samples

        # Boundary samples [0, k_coi) must be False
        assert not np.any(tfr.coi_mask[0, :k_coi])
        # Sample k_coi onwards must be True
        assert tfr.coi_mask[0, k_coi]
        assert tfr.coi_mask[0, 500]
        assert tfr.coi_mask[0, 1000 - k_coi - 1]
        # Right boundary samples [1000 - k_coi, 1000) must be False
        assert not np.any(tfr.coi_mask[0, 1000 - k_coi:])

    def test_probe10_complex64_vs_complex128_precision(self, fs, freqs):
        """Probe 10: Downcasting to complex64 has numerical error bounded by single precision."""
        rng = np.random.default_rng(42)
        x = rng.normal(size=500)

        tfr128 = complex_tfr(x, fs=fs, freqs=freqs, dtype=np.complex128)
        tfr64 = complex_tfr(x, fs=fs, freqs=freqs, dtype=np.complex64)

        assert tfr128.dtype == np.complex128
        assert tfr64.dtype == np.complex64

        rel_err = np.abs(tfr128.z - tfr64.z) / (np.abs(tfr128.z) + 1e-12)
        assert np.max(rel_err) < 1e-5

    def test_probe11_tfaccumulator_compatibility(self, fs, freqs):
        """Probe 11: Direct seamless integration with TFRAccumulator."""
        n_ch = 4
        T = 800
        n_trials = 10
        t = np.arange(T) / fs
        rng = np.random.default_rng(42)

        acc = TFRAccumulator((n_ch, len(freqs), T))

        for _ in range(n_trials):
            # Phase-locked 20 Hz signal (index 2 in freqs) on channel 0
            sig = rng.normal(size=(n_ch, T))
            sig[0] += 2.0 * np.cos(2.0 * np.pi * 20.0 * t)

            tfr = complex_tfr(sig, fs=fs, freqs=freqs, n_cycles=5.0, time_axis=-1)
            assert tfr.shape == (n_ch, len(freqs), T)

            acc.add_trial(tfr.z, valid=tfr.coi_mask)

        # Verify derived sufficient statistics
        p = acc.power()
        itc = acc.itc()
        evoked = acc.evoked()

        assert p.shape == (n_ch, len(freqs), T)
        assert itc.shape == (n_ch, len(freqs), T)

        # Channel 0 at 20 Hz (index 2) must have high ITC in the interior
        assert itc[0, 2, 400] > 0.8
        # Noise channels / frequencies have low ITC
        assert itc[1, 5, 400] < 0.6

    def test_probe12_independent_reference_complex_coefficients_comparison(self, fs):
        """Probe 12: Independent comparison of complex coefficients against from-scratch CWT."""
        rng = np.random.default_rng(123)
        x = rng.normal(size=1200) + 1.5 * np.cos(2.0 * np.pi * 25.0 * np.arange(1200) / fs)
        f0 = 25.0
        n_c = 6.0

        # Run jnwb.complex_tfr
        tfr = complex_tfr(x, fs=fs, freqs=np.array([f0]), n_cycles=n_c, normalization="amplitude")
        z_jnwb = tfr.z[0]

        # Run independent reference implementation
        z_ref = _independent_reference_morlet_cwt(x, fs=fs, f0=f0, n_cycles=n_c)

        # Compare complex coefficients across full time series
        np.testing.assert_allclose(z_jnwb, z_ref, rtol=1e-10, atol=1e-10)

    def test_probe13_adversarial_nonterminal_time_axes_equivalence(self, fs, freqs):
        """Probe 13: Adversarial test for time_axis=0 (T, C) and time_axis=1 (N, T, C)."""
        rng = np.random.default_rng(999)
        n_freqs = len(freqs)

        # 1. 2D array (T=600, C=4) with time_axis=0
        data_2d = rng.normal(size=(600, 4))
        tfr_2d = complex_tfr(data_2d, fs=fs, freqs=freqs, time_axis=0)
        assert tfr_2d.shape == (n_freqs, 600, 4)

        for c in range(4):
            tfr_1d = complex_tfr(data_2d[:, c], fs=fs, freqs=freqs, time_axis=0)
            np.testing.assert_allclose(tfr_2d.z[:, :, c], tfr_1d.z, rtol=1e-12)
            np.testing.assert_array_equal(tfr_2d.coi_mask[:, :, c], tfr_1d.coi_mask)

        # 2. 3D array (N=3, T=500, C=5) with time_axis=1
        data_3d = rng.normal(size=(3, 500, 5))
        tfr_3d = complex_tfr(data_3d, fs=fs, freqs=freqs, time_axis=1)
        assert tfr_3d.shape == (3, n_freqs, 500, 5)

        for n in range(3):
            for c in range(5):
                tfr_1d = complex_tfr(data_3d[n, :, c], fs=fs, freqs=freqs, time_axis=0)
                np.testing.assert_allclose(tfr_3d.z[n, :, :, c], tfr_1d.z, rtol=1e-12)
                np.testing.assert_array_equal(tfr_3d.coi_mask[n, :, :, c], tfr_1d.coi_mask)
