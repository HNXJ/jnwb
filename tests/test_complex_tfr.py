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
    # Admissibility correction of Torrence & Compo (1998) eq. 6: the Morlet is only a
    # wavelet if it integrates to zero. Omitting it left this reference agreeing with an
    # equally uncorrected implementation to 1e-5 while both responded to DC.
    carrier = carrier - (np.sum(gaussian_envelope * carrier) / np.sum(gaussian_envelope))
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
        """Probe 9: by default the COI mask bounds exactly the kernel support.

        It used to be built from `coi_sigma` (2.0) while the kernel was truncated at
        `cutoff_sigma` (4.0), so it cleared at half the region zero-padding actually
        reached: 96 against a kernel half-width of 191 at `n_cycles=3`.
        """
        x = np.ones(1000)
        f0 = 20.0
        n_c = 5.0
        tfr = complex_tfr(x, fs=fs, freqs=np.array([f0]), n_cycles=n_c)

        sigma_t = n_c / (2.0 * np.pi * f0)
        k_kernel = int(np.ceil(4.0 * sigma_t * fs))  # cutoff_sigma * sigma_t * fs = 64

        assert not np.any(tfr.coi_mask[0, :k_kernel])
        assert tfr.coi_mask[0, k_kernel]
        assert tfr.coi_mask[0, 500]
        assert tfr.coi_mask[0, 1000 - k_kernel - 1]
        assert not np.any(tfr.coi_mask[0, 1000 - k_kernel:])

    def test_probe09b_explicit_coi_sigma_is_honoured_and_warns_when_narrow(self, fs):
        """An explicitly passed coi_sigma still sets the region -- and says so when it
        marks contaminated samples as valid, which is the whole defect made opt-in.
        """
        x = np.ones(1000)
        f0, n_c = 20.0, 5.0
        sigma_t = n_c / (2.0 * np.pi * f0)

        with pytest.warns(RuntimeWarning, match="narrower than the kernel half-width"):
            narrow = complex_tfr(
                x, fs=fs, freqs=np.array([f0]), n_cycles=n_c, coi_sigma=2.0
            )
        k_narrow = int(np.ceil(2.0 * sigma_t * fs))
        assert not np.any(narrow.coi_mask[0, :k_narrow])
        assert narrow.coi_mask[0, k_narrow]

        import warnings as _warnings

        with _warnings.catch_warnings():
            _warnings.simplefilter("error", RuntimeWarning)
            wide = complex_tfr(
                x, fs=fs, freqs=np.array([f0]), n_cycles=n_c, coi_sigma=6.0
            )
        k_wide = int(np.ceil(6.0 * sigma_t * fs))
        assert not np.any(wide.coi_mask[0, :k_wide])

    @pytest.mark.parametrize("n_cycles", [3.0, 5.0, 10.0])
    def test_probe09c_no_sample_inside_the_mask_responds_to_a_dc_offset(self, n_cycles):
        """The behavioural form of the contract. A constant offset can only reach a sample
        through `mode="same"` zero-padding, so every sample the mask calls valid must be
        blind to it. The largest response inside the old mask was 28.6 / 18.6 / 9.42 on a
        unit-amplitude scale at n_cycles 3 / 5 / 10.
        """
        fs, n = 1000.0, 4000
        freqs = np.array([10.0])
        offset = complex_tfr(
            np.full(n, 1000.0), fs=fs, freqs=freqs, n_cycles=n_cycles
        )
        zero = complex_tfr(np.zeros(n), fs=fs, freqs=freqs, n_cycles=n_cycles)

        response = np.abs(offset.z[0] - zero.z[0])
        assert response.max() > 1.0, "the boundary region must actually be contaminated"
        assert response[offset.coi_mask[0]].max() < 1e-9

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

    def test_probe14_coi_mask_broadcasting_and_masking(self, fs, freqs):
        """Probe 14: coi_mask matches z shape and supports direct broadcasting/masking across arbitrary axes."""
        rng = np.random.default_rng(42)

        # 2D non-terminal: (times=400, channels=4), time_axis=0
        data_2d = rng.normal(size=(400, 4))
        tfr_2d = complex_tfr(data_2d, fs=fs, freqs=freqs, time_axis=0)
        assert tfr_2d.coi_mask.shape == tfr_2d.z.shape
        masked_power_2d = tfr_2d.power * tfr_2d.coi_mask
        assert masked_power_2d.shape == tfr_2d.z.shape
        valid_z_2d = tfr_2d.z[tfr_2d.coi_mask]
        assert len(valid_z_2d) > 0

        # 3D interior time axis: (trials=2, times=300, channels=3), time_axis=1
        data_3d = rng.normal(size=(2, 300, 3))
        tfr_3d = complex_tfr(data_3d, fs=fs, freqs=freqs, time_axis=1)
        assert tfr_3d.coi_mask.shape == tfr_3d.z.shape
        masked_power_3d = tfr_3d.power * tfr_3d.coi_mask
        assert masked_power_3d.shape == tfr_3d.z.shape
        valid_z_3d = tfr_3d.z[tfr_3d.coi_mask]
        assert len(valid_z_3d) > 0

        # 4D arbitrary axis: (epochs=2, subjects=2, times=250, channels=2), time_axis=2
        data_4d = rng.normal(size=(2, 2, 250, 2))
        tfr_4d = complex_tfr(data_4d, fs=fs, freqs=freqs, time_axis=2)
        assert tfr_4d.coi_mask.shape == tfr_4d.z.shape
        masked_power_4d = tfr_4d.power * tfr_4d.coi_mask
        assert masked_power_4d.shape == tfr_4d.z.shape
        assert tfr_4d.z[tfr_4d.coi_mask].ndim == 1



class TestMorletAdmissibilityAndDtype:
    """A wavelet that responds to DC, and a real dtype that discarded half
    the transform. Both used to be reachable through the public signature."""

    @pytest.mark.parametrize("n_cycles", [1.0, 2.0, 3.0, 5.0, 10.0])
    def test_the_kernel_integrates_to_zero_at_every_n_cycles(self, n_cycles):
        """`|sum(w)|` was 1.21 at n_cycles=1 against 4.7e-05 at n_cycles=5, so the
        DC response depended on the wavelet width."""
        _, w = morlet_wavelet(10.0, 1000.0, n_cycles=n_cycles)
        assert abs(np.sum(w)) < 1e-10

    @pytest.mark.parametrize("n_cycles", [1.0, 3.0, 5.0, 10.0])
    @pytest.mark.parametrize("offset", [0.0, 10.0, 1000.0])
    def test_a_constant_offset_does_not_enter_as_oscillatory_amplitude(self, n_cycles, offset):
        """A unit cosine on a 1000-unit offset reported a peak |z| of 1214.3 at
        n_cycles=1. The recovered amplitude must not depend on the offset at all."""
        fs = 1000.0
        f0 = 10.0
        t = np.arange(4000) / fs
        signal_only = complex_tfr(np.cos(2 * np.pi * f0 * t), fs, [f0], n_cycles=n_cycles)
        offset_added = complex_tfr(
            np.cos(2 * np.pi * f0 * t) + offset, fs, [f0], n_cycles=n_cycles
        )
        # Compare strictly inside the kernel support. Samples nearer the edge than the
        # kernel half-width convolve against `mode="same"` zero-padding, so the kernel's
        # zero sum no longer cancels a constant -- that residual is item 05-85, not this
        # one, and `coi_mask` does not currently cover it.
        sigma_t = n_cycles / (2.0 * np.pi * f0)
        half = int(np.ceil(4.0 * sigma_t * fs))
        interior = slice(half, len(t) - half)
        np.testing.assert_allclose(
            np.abs(offset_added.z)[0][interior],
            np.abs(signal_only.z)[0][interior],
            rtol=1e-8,
            atol=1e-8,
        )

    @pytest.mark.parametrize("n_cycles", [3.0, 5.0, 10.0])
    def test_the_documented_unit_cosine_amplitude_survives_the_correction(self, n_cycles):
        fs = 1000.0
        t = np.arange(4000) / fs
        res = complex_tfr(np.cos(2 * np.pi * 10.0 * t), fs, [10.0], n_cycles=n_cycles)
        peak = np.abs(res.z)[0][1000:3000].max()
        assert peak == pytest.approx(1.0, abs=1e-3)

    def test_energy_normalization_survives_the_correction(self):
        _, w = morlet_wavelet(10.0, 1000.0, n_cycles=5.0, normalization="energy")
        assert np.sum(np.abs(w) ** 2) == pytest.approx(1.0)

    @pytest.mark.parametrize("bad_dtype", [np.float64, np.float32, np.int64])
    def test_a_real_output_dtype_is_refused(self, bad_dtype):
        """`dtype=np.float64` returned a ComplexWarning and a float64 `.z`, so `.phase`
        and `.power` described the real part while `.normalization` and `.device` still
        reported a valid transform."""
        t = np.arange(500) / 1000.0
        with pytest.raises(ValueError, match="complex dtype"):
            complex_tfr(np.cos(2 * np.pi * 10 * t), 1000.0, [10.0], dtype=bad_dtype)

    @pytest.mark.parametrize("good_dtype", [np.complex64, np.complex128])
    def test_complex_dtypes_are_accepted(self, good_dtype):
        t = np.arange(500) / 1000.0
        res = complex_tfr(np.cos(2 * np.pi * 10 * t), 1000.0, [10.0], dtype=good_dtype)
        assert np.issubdtype(res.z.dtype, np.complexfloating)
