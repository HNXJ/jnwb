from __future__ import annotations

import numpy as np

from src.analysis.lfp.lfp_tfr import n_cycles_for_freqs


def test_n_cycles_for_freqs_theta_alpha_beta_gamma():
    # Use a representative set of frequencies across bands.
    freqs = np.array([5.0, 10.0, 20.0, 40.0], dtype=float)
    n_cycles = n_cycles_for_freqs(freqs)

    # Policy (see lfp_tfr.default_band_time_support_ms):
    # Theta support = 1200ms = 1.2s
    # Alpha/Beta support = 200ms = 0.2s
    # Gamma support = 150ms = 0.15s
    expected = np.array([1.2 * 5.0, 0.2 * 10.0, 0.2 * 20.0, 0.15 * 40.0], dtype=float)

    assert n_cycles.shape == freqs.shape
    assert np.all(np.isfinite(n_cycles))
    assert np.allclose(n_cycles, expected, rtol=1e-6, atol=1e-6)

