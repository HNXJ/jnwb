"""Tests for continuous time-series operations and epoch extraction."""

from __future__ import annotations

import numpy as np
import pytest

import jnwb
from jnwb.continuous import epoch_continuous


class TestEpochContinuous:
    def test_public_export(self):
        assert hasattr(jnwb, "epoch_continuous")
        assert "epoch_continuous" in jnwb.__all__
        assert jnwb.epoch_continuous is epoch_continuous

    def test_impulse_alignment(self):
        fs = 1000.0
        n_samples = 3000
        data = np.zeros(n_samples, dtype=np.float64)
        impulse_sample = 1500
        impulse_time = impulse_sample / fs  # 1.5 s
        data[impulse_sample] = 42.0

        win_s = (-0.2, 0.3)
        epochs, t_axis = epoch_continuous(
            data,
            onsets=[impulse_time],
            win_s=win_s,
            fs=fs,
        )

        assert epochs.shape == (1, int(0.5 * fs))
        assert t_axis.shape == (int(0.5 * fs),)
        np.testing.assert_allclose(t_axis[0], -0.2)
        np.testing.assert_allclose(t_axis[-1], 0.3 - 1.0 / fs)

        # Impulse must be exactly at t = 0.0 s
        zero_idx = int(np.round(0.2 * fs))
        assert t_axis[zero_idx] == 0.0
        assert epochs[0, zero_idx] == 42.0
        assert np.sum(epochs[0] != 0.0) == 1

    def test_2d_multichannel(self):
        fs = 500.0
        n_samples = 2000
        n_channels = 8
        data = np.arange(n_samples * n_channels, dtype=np.float64).reshape(n_samples, n_channels)

        onsets = [0.5, 1.0, 1.5]
        win_s = (-0.1, 0.2)
        epochs, t_axis = epoch_continuous(
            data,
            onsets,
            win_s=win_s,
            fs=fs,
        )

        n_win = int(np.round(0.3 * fs))
        assert epochs.shape == (3, n_win, n_channels)
        assert t_axis.shape == (n_win,)

        # Verify exact slice for first onset (0.5 s -> sample 250)
        expected_first = data[250 - int(0.1 * fs) : 250 + int(0.2 * fs), :]
        np.testing.assert_allclose(epochs[0], expected_first)

    def test_boundary_policy_nan(self):
        fs = 1000.0
        data = np.ones(500, dtype=np.float64)
        # Onset at sample 20 (0.02 s), window (-0.05, 0.05) -> window extends from sample -30 to 70
        epochs, t_axis = epoch_continuous(
            data,
            onsets=[0.02],
            win_s=(-0.05, 0.05),
            fs=fs,
            boundary_policy="nan",
        )
        assert epochs.shape == (1, 100)
        # Pre-boundary samples (-30 to 0 -> 30 samples) should be NaN
        assert np.all(np.isnan(epochs[0, :30]))
        # Post-boundary samples (0 to 70 -> 70 samples) should be 1.0
        assert np.all(epochs[0, 30:] == 1.0)

    def test_boundary_policy_error(self):
        fs = 1000.0
        data = np.ones(500, dtype=np.float64)
        with pytest.raises(ValueError, match="extends outside data"):
            epoch_continuous(
                data,
                onsets=[0.02],
                win_s=(-0.05, 0.05),
                fs=fs,
                boundary_policy="error",
            )

    def test_boundary_policy_drop(self):
        fs = 1000.0
        data = np.ones(2000, dtype=np.float64)
        # First onset out of bounds, second onset in bounds
        onsets = [0.02, 1.0]
        epochs, _ = epoch_continuous(
            data,
            onsets=onsets,
            win_s=(-0.05, 0.05),
            fs=fs,
            boundary_policy="drop",
        )
        assert epochs.shape == (1, 100)
        assert np.all(epochs[0] == 1.0)

    def test_empty_onsets(self):
        fs = 1000.0
        data_1d = np.ones(500)
        epochs_1d, t_axis = epoch_continuous(data_1d, [], win_s=(-0.1, 0.2), fs=fs)
        assert epochs_1d.shape == (0, 300)
        assert t_axis.shape == (300,)

        data_2d = np.ones((500, 4))
        epochs_2d, _ = epoch_continuous(data_2d, [], win_s=(-0.1, 0.2), fs=fs)
        assert epochs_2d.shape == (0, 300, 4)

    def test_sample_onset_units(self):
        fs = 1000.0
        data = np.arange(1000, dtype=np.float64)
        epochs, _ = epoch_continuous(
            data,
            onsets=[500],
            win_s=(-0.01, 0.01),
            fs=fs,
            onset_unit="samples",
        )
        assert epochs.shape == (1, 20)
        np.testing.assert_allclose(epochs[0], data[490:510])

    def test_invalid_arguments_raise(self):
        data = np.zeros(100)
        with pytest.raises(ValueError, match="must be positive"):
            epoch_continuous(data, [0.0], win_s=(-0.1, 0.1), fs=0.0)
        with pytest.raises(ValueError, match="strictly less"):
            epoch_continuous(data, [0.0], win_s=(0.2, 0.1), fs=1000.0)
        with pytest.raises(ValueError, match="must be a 2-tuple"):
            epoch_continuous(data, [0.0], win_s=(-0.1,), fs=1000.0)  # type: ignore[arg-type]
        with pytest.raises(ValueError, match="must be 1D or 2D"):
            epoch_continuous(np.zeros((10, 10, 10)), [0.0], win_s=(-0.1, 0.1), fs=1000.0)
        with pytest.raises(ValueError, match="Unknown boundary_policy"):
            epoch_continuous(data, [0.0], win_s=(-0.1, 0.1), fs=1000.0, boundary_policy="invalid")  # type: ignore[arg-type]
