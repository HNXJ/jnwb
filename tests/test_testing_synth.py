"""Comprehensive tests and numerical verification for jnwb.testing.synth generators."""

import numpy as np
import pytest
import pynwb
from scipy import signal

import jnwb
from jnwb.testing.synth import (
    SynthLaminarReceipt,
    build_canonical_tutorial_nwb,
    _tutorial_unit_contacts,
    _validate_electrode_indices,
    synth_ar_noise,
    synth_correlation_blocks,
    synth_laminar_motif,
    synth_periodic_response,
    synth_phase_gradient,
    synth_unequal_groups,
    synth_white_noise,
)


class TestSynthWhiteNoise:
    def test_shapes_and_statistics(self):
        """Generates requested shapes with empirical mean and variance matching parameters."""
        shape = (10, 5000)
        noise = synth_white_noise(shape, scale=2.5, mean=1.0, rng=42)
        assert noise.shape == shape
        assert np.isclose(np.mean(noise), 1.0, atol=0.05)
        assert np.isclose(np.std(noise), 2.5, atol=0.05)

    def test_seed_determinism(self):
        """Same seed produces bit-identical noise; different seeds produce distinct noise."""
        n1 = synth_white_noise((5, 100), rng=123)
        n2 = synth_white_noise((5, 100), rng=123)
        n3 = synth_white_noise((5, 100), rng=456)
        np.testing.assert_array_equal(n1, n2)
        assert not np.array_equal(n1, n3)

    def test_invalid_scale(self):
        """Negative or non-finite scale raises ValueError."""
        with pytest.raises(ValueError, match="scale"):
            synth_white_noise(100, scale=-1.0)
        with pytest.raises(ValueError, match="scale"):
            synth_white_noise(100, scale=np.nan)


class TestSynthARNoise:
    def test_ar1_autocorrelation_decay(self):
        """AR(1) sample autocorrelation follows theoretical exponential decay."""
        fs = 1000.0
        tau = 0.05  # 50 ms time constant
        phi_true = np.exp(-1.0 / (fs * tau))
        n_samples = 20000

        x = synth_ar_noise(n_samples, tau_s=tau, fs=fs, rng=42)
        assert x.ndim == 1
        assert len(x) == n_samples

        # Compute empirical lag-1 autocorrelation
        r0 = np.var(x)
        r1 = np.mean((x[:-1] - np.mean(x)) * (x[1:] - np.mean(x)))
        phi_emp = r1 / r0
        assert np.isclose(phi_emp, phi_true, atol=0.02)

    def test_multichannel_shape(self):
        """n_channels > 1 returns (n_channels, n_samples) with uncorrelated cross-channels."""
        x = synth_ar_noise(5000, n_channels=4, tau_s=0.02, rng=42)
        assert x.shape == (4, 5000)
        corr = np.corrcoef(x)
        np.fill_diagonal(corr, 0.0)
        assert np.max(np.abs(corr)) < 0.1  # Channels are mutually independent

    def test_poles_and_stability_validation(self):
        """Valid AR(2) poles succeed; unstable poles outside unit circle raise ValueError."""
        # Stable AR(2)
        x = synth_ar_noise(1000, poles=[0.5, -0.2], rng=42)
        assert len(x) == 1000

        # Unstable AR(1): phi = 1.05
        with pytest.raises(ValueError, match="non-stationary"):
            synth_ar_noise(1000, poles=[1.05])

        # Conflicting arguments
        with pytest.raises(ValueError, match="Cannot specify both"):
            synth_ar_noise(1000, tau_s=0.05, poles=[0.5])


class TestSynthPeriodicResponse:
    def test_frequency_peak_localization(self):
        """Shared oscillation peaks strictly at declared frequency."""
        fs = 1000.0
        n_samples = 1000
        freq = 35.0
        trials = synth_periodic_response(20, n_samples, fs=fs, freq_hz=freq, amplitude=2.0, noise_std=0.1, rng=42)
        assert trials.shape == (20, n_samples)

        # Average power across trials peaks at 35 Hz
        fft_freqs = np.fft.rfftfreq(n_samples, 1.0 / fs)
        fft_power = np.mean(np.abs(np.fft.rfft(trials, axis=1)) ** 2, axis=0)
        peak_idx = int(np.argmax(fft_power))
        assert fft_freqs[peak_idx] == pytest.approx(freq, abs=2.0)

    def test_multichannel_shape(self):
        """Multichannel periodic response has shape (n_trials, n_channels, n_samples)."""
        data = synth_periodic_response(10, 500, fs=500.0, n_channels=3, rng=42)
        assert data.shape == (10, 3, 500)


class TestSynthCorrelationBlocks:
    def test_block_structure_recovery(self):
        """Within-block correlation is high; between-block correlation is low."""
        block_sizes = [4, 4, 4]
        data, labels, true_corr = synth_correlation_blocks(
            block_sizes, within_corr=0.8, between_corr=0.0, n_samples=5000, rng=42
        )
        assert data.shape == (12, 5000)
        assert len(labels) == 12
        np.testing.assert_array_equal(labels, [0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2])

        emp_corr = np.corrcoef(data)
        # Check block 0 within-correlation
        b0_within = emp_corr[0:4, 0:4]
        off_diag = ~np.eye(4, dtype=bool)
        assert np.all(np.isclose(b0_within[off_diag], 0.8, atol=0.05))

        # Check between-block correlation (block 0 vs block 1)
        b01_between = emp_corr[0:4, 4:8]
        assert np.all(np.isclose(b01_between, 0.0, atol=0.05))


class TestSynthPhaseGradient:
    def test_traveling_wave_slope(self):
        """Linear phase gradient produces consistent lag between adjacent channels."""
        fs = 1000.0
        n_samples = 2000
        delay = 0.005  # 5 ms per channel
        f0 = 20.0
        data = synth_phase_gradient(4, n_samples, fs=fs, f0=f0, delay_per_channel_s=delay, noise_std=0.0, rng=42)
        assert data.shape == (4, n_samples)

        # Cross-correlation peak between channel 0 and channel 1 should be at +5 samples (5 ms at 1000 Hz)
        xcorr = signal.correlate(data[1], data[0], mode="full")
        lags = signal.correlation_lags(n_samples, n_samples, mode="full")
        best_lag = lags[np.argmax(xcorr)]
        assert best_lag == pytest.approx(5, abs=1)


class TestSynthUnequalGroups:
    def test_sample_counts_and_effect_size(self):
        """Unequal group sizes generated with Cohen's d effect displacement."""
        g1, g2 = synth_unequal_groups(30, 70, n_features=5, effect_size=1.5, noise_std=1.0, rng=42)
        assert g1.shape == (30, 5)
        assert g2.shape == (70, 5)
        diff = np.mean(g2) - np.mean(g1)
        assert np.isclose(diff, 1.5, atol=0.2)


class TestSynthLaminarMotif:
    def test_laminar_motif_vflip_recovery(self):
        """Synthesized laminar motif is recovered by vflip at the ground-truth crossover."""
        n_ch = 20
        c_true = 9.0
        pitch = 50.0
        receipt = synth_laminar_motif(
            n_channels=n_ch,
            n_samples=6000,
            fs=1000.0,
            c_crossover=c_true,
            orientation="superficial_to_deep",
            pitch_um=pitch,
            snr=6.0,
            rng=42,
        )
        assert isinstance(receipt, SynthLaminarReceipt)
        assert receipt.lfp.shape == (n_ch, 6000)
        assert receipt.crossover_contact == c_true
        assert receipt.crossover_depth_um == c_true * pitch
        assert receipt.probe_geometry.is_linear

        # Run vflip_from_lfp on synthesized LFP
        res = jnwb.vflip_from_lfp(receipt.lfp, fs=receipt.fs, probe_geometry=receipt.probe_geometry)
        assert res.accepted
        assert res.orientation == "superficial_to_deep"
        assert res.crossover_contact == pytest.approx(c_true, abs=1.5)

    def test_bad_channels_injection(self):
        """Injected bad channels are flattened and flagged in bad_channel_mask."""
        receipt = synth_laminar_motif(n_channels=16, bad_channels=[3, 11], rng=42)
        assert receipt.bad_channel_mask[3]
        assert receipt.bad_channel_mask[11]
        assert not receipt.bad_channel_mask[0]
        # Dead channels have zero signal
        np.testing.assert_array_equal(receipt.lfp[3], 0.0)
        np.testing.assert_array_equal(receipt.lfp[11], 0.0)


class TestCanonicalTutorialNWB:
    def test_build_and_read_nwb(self, tmp_path):
        """Builds valid NWB file with electrodes, LFP, trials, and units."""
        out_file = tmp_path / "test_canonical_tutorial.nwb"
        nwb, gt = build_canonical_tutorial_nwb(out_file, n_channels=12, duration_s=3.0, n_trials=6, seed=42)

        assert out_file.exists()
        assert gt["n_channels"] == 12
        assert gt["n_trials"] == 6

        # Read back using pynwb
        with pynwb.NWBHDF5IO(str(out_file), "r") as io:
            read_nwb = io.read()
            assert read_nwb.session_description == "Canonical synthetic tutorial recording"
            assert len(read_nwb.electrodes) == 12
            assert "trials" in read_nwb.intervals
            assert len(read_nwb.intervals["trials"]) == 6
            assert "ecephys" in read_nwb.processing
            assert "LFP" in read_nwb.processing["ecephys"].data_interfaces
            assert len(read_nwb.units) == 2


class TestElectrodeRegionInvariant:
    """Every DynamicTableRegion index must address an existing electrode row.

    The canonical tutorial builder hardcoded unit electrodes [10] and [18], valid only while
    n_channels > 18. At n_channels=12 the second unit referenced a nonexistent row. Older HDMF
    accepted the dangling reference at write time and raised only on read; newer HDMF rejects it
    at write time, so CI failed on every matrix leg while a stale local environment passed.

    These probes assert the invariant directly rather than relying on a particular HDMF version
    to notice, so they fail against the pre-repair implementation on any supported dependency set.
    """

    @staticmethod
    def _unit_contacts(nwb):
        return [int(i) for u in range(len(nwb.units))
                for i in nwb.units["electrodes"][u].index]

    @pytest.mark.parametrize("n_channels", [24, 20, 19, 13, 12])
    def test_unit_electrode_indices_are_in_bounds(self, n_channels):
        """The defect: indices must be < the electrode table length for every shaft length."""
        nwb, gt = build_canonical_tutorial_nwb(
            n_channels=n_channels, duration_s=2.0, n_trials=4, seed=7)
        n_rows = len(nwb.electrodes)
        assert n_rows == n_channels
        for idx in self._unit_contacts(nwb):
            assert 0 <= idx < n_rows, (
                f"unit references electrode row {idx} but the table has {n_rows} rows")

    def test_default_shaft_preserves_the_historical_contacts(self):
        """The repair must not silently relocate units on the default probe."""
        contacts = _tutorial_unit_contacts(24)
        assert contacts == (10, 18)

    def test_units_occupy_distinct_contacts(self):
        for n_channels in (24, 12, 8, 4, 2):
            contacts = _tutorial_unit_contacts(n_channels)
            assert len(set(contacts)) == len(contacts), (n_channels, contacts)

    def test_ground_truth_reports_the_actual_contacts(self):
        """Callers must be able to read the mapping instead of guessing it."""
        nwb, gt = build_canonical_tutorial_nwb(
            n_channels=12, duration_s=2.0, n_trials=4, seed=7)
        assert gt["unit_contacts"] == (5, 9)
        assert sorted(self._unit_contacts(nwb)) == [5, 9]

    def test_lfp_region_is_one_to_one_with_electrodes(self):
        """n_data_channels == n_electrodes: the LFP region maps each column to one row."""
        nwb, gt = build_canonical_tutorial_nwb(
            n_channels=12, duration_s=2.0, n_trials=4, seed=7)
        es = nwb.processing["ecephys"].data_interfaces["LFP"].electrical_series["lfp"]
        assert es.data.shape[1] == len(nwb.electrodes) == 12
        assert [int(i) for i in es.electrodes.data] == list(range(12))

    def test_units_reference_a_strict_subset_of_electrodes(self):
        """n_data_channels < n_electrodes: subset semantics are supported for units."""
        nwb, gt = build_canonical_tutorial_nwb(
            n_channels=24, duration_s=2.0, n_trials=4, seed=7)
        contacts = set(self._unit_contacts(nwb))
        assert contacts.issubset(set(range(len(nwb.electrodes))))
        assert len(contacts) < len(nwb.electrodes)

    def test_out_of_range_index_fails_loudly(self):
        """n_data_channels > n_electrodes, and any dangling index, must raise -- never truncate."""
        with pytest.raises(ValueError, match="out of bounds"):
            _validate_electrode_indices([0, 1, 18], n_rows=12, label="probe")
        with pytest.raises(ValueError, match="out of bounds"):
            _validate_electrode_indices([-1], n_rows=12, label="probe")
        # The boundary itself: index == n_rows is one past the end.
        with pytest.raises(ValueError, match="out of bounds"):
            _validate_electrode_indices([12], n_rows=12, label="probe")
        _validate_electrode_indices([0, 11], n_rows=12, label="probe")   # valid: no raise

    def test_error_names_the_offending_indices_and_length(self):
        with pytest.raises(ValueError) as excinfo:
            _validate_electrode_indices([18], n_rows=12, label="tutorial unit electrodes")
        message = str(excinfo.value)
        assert "18" in message and "12" in message and "tutorial unit electrodes" in message

    def test_shaft_too_short_for_two_units_raises(self):
        with pytest.raises(ValueError, match="at least 2"):
            _tutorial_unit_contacts(1)

    def test_round_trip_write_read_preserves_region_and_series(self, tmp_path):
        """Round-trip through NWB: the region must survive write and read back in bounds."""
        out_file = tmp_path / "region_roundtrip.nwb"
        nwb, gt = build_canonical_tutorial_nwb(
            out_file, n_channels=12, duration_s=2.0, n_trials=4, seed=7)
        with pynwb.NWBHDF5IO(str(out_file), "r") as io:
            read_nwb = io.read()
            n_rows = len(read_nwb.electrodes)
            assert n_rows == 12
            es = read_nwb.processing["ecephys"].data_interfaces["LFP"].electrical_series["lfp"]
            assert es.data.shape[1] == n_rows
            for u in range(len(read_nwb.units)):
                for idx in read_nwb.units["electrodes"][u].index:
                    assert 0 <= int(idx) < n_rows

    def test_shaft_shorter_than_the_crossover_contact_raises(self):
        """Second defect these probes exposed: the crossover contact is fixed, the shaft is not.

        crossover_true was hardcoded at 10.5 while synth_laminar_motif requires
        c_crossover <= n_channels - 1, so every n_channels <= 10 failed deep inside the motif
        generator with a message about c_crossover rather than about the caller's argument.
        """
        with pytest.raises(ValueError, match="cannot represent the tutorial laminar crossover"):
            build_canonical_tutorial_nwb(n_channels=8, duration_s=2.0, n_trials=4, seed=7)
