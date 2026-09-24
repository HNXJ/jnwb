"""Tutorial 06: Laminar Electrophysiology — CSD, vFLIP Alignment, and zFLIP Waves.

Run: python examples/tutorials/06_laminar.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# This file is run from a checkout, so prefer that checkout over any installed jnwb:
# Python puts this directory on sys.path, not the repository root. A run that is
# deliberately qualifying an installed copy says so with JNWB_EXPECTED_PACKAGE_ROOT,
# and then this guard stands aside -- otherwise it would quietly redirect CI's
# installed-wheel tutorial step back to the checkout.
import os

_CHECKOUT = Path(__file__).resolve().parents[2]
if not os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") and (
    _CHECKOUT / "jnwb" / "__init__.py"
).exists():
    sys.path.insert(0, str(_CHECKOUT))

import jnwb


def main() -> None:
    rng = np.random.default_rng(42)
    fs = 1000.0
    n_channels = 16
    n_samples = 2000
    times = np.arange(n_samples) / fs

    # 1. Synthetic Laminar Signals with Traveling Phase Delay
    # Generates a progressive phase shift across depth contacts
    lfp = np.zeros((n_channels, n_samples))
    center_freq = 20.0  # 20 Hz beta rhythm
    for ch in range(n_channels):
        phase_lag = ch * 0.15  # constant spatial phase gradient
        signal = np.sin(2.0 * np.pi * center_freq * times - phase_lag)
        noise = 0.2 * rng.normal(size=n_samples)
        lfp[ch] = signal + noise

    # 2. 1D Current Source Density (CSD)
    # Second spatial derivative with pitch=100 um
    csd = jnwb.current_source_density_1d(
        lfp,
        pitch_um=100.0,
        conductivity_s_per_m=0.3,
    )
    assert csd.shape == (n_channels - 2, n_samples)
    print(f"Computed 1D CSD: {csd.shape[0]} depth sites across {csd.shape[1]} samples")

    # 3. vFLIP Laminar Alignment Profile
    # Identifies spectrolaminar crossover contact and polarity
    vflip_res = jnwb.vflip_from_lfp(
        lfp,
        fs=fs,
        min_support_score=0.0,
        orientation="auto",
    )
    print(f"vFLIP result: accepted={vflip_res.accepted}, crossover={vflip_res.crossover_contact}, score={vflip_res.support_score:.2f}")

    # 4. zFLIP Inter-Contact Traveling Wave Analysis
    # Fits linear phase slope dphi/df and computes apparent phase velocity. `orientation`
    # says which end row 0 is; here channel 0 is the most superficial contact.
    zflip_res = jnwb.zflip(
        lfp,
        fs=fs,
        orientation="superficial_to_deep",
        pitch_um=100.0,
        freq_range=(15.0, 25.0),
        n_surrogates=20,
        seed=42,
    )
    assert isinstance(zflip_res, jnwb.ZFlipResult)
    print("zFLIP traveling wave result:")
    print(f"  Delay identifiable: {zflip_res.delay_identifiable}")
    print(f"  Direction in depth: {zflip_res.directionality}")
    print(f"  Apparent velocity: {zflip_res.apparent_velocity_m_s}")
    print(f"  Accepted: {zflip_res.accepted}")
    print(f"  Surrogate null p-value: {zflip_res.p_value:.3f}")


if __name__ == "__main__":
    main()
