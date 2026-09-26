"""Tutorial 06: Laminar Electrophysiology — CSD, vFLIP Alignment, zFLIP Waves, xFLIP Blocks.

Every signal here is synthetic, generated below.

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

    # 5. xFLIP Correlation Blocks
    # Synthetic: two contiguous blocks of 8 contacts, each driven by its own shared source,
    # so the true boundary sits between contacts 7 and 8. `xflip` partitions the contacts
    # into contiguous blocks and tests the partition against phase-randomised surrogates,
    # which keep each contact's autocorrelation and destroy the cross-contact coupling.
    n_per_block = 8
    blocks = np.empty((2 * n_per_block, n_samples))
    for b in range(2):
        source = rng.normal(size=n_samples)
        rows = slice(b * n_per_block, (b + 1) * n_per_block)
        blocks[rows] = 0.8 * source + 0.6 * rng.normal(size=(n_per_block, n_samples))

    xflip_res = jnwb.xflip(blocks, n_blocks=2, min_block_size=3, n_surrogates=200, rng=0)
    assert isinstance(xflip_res, jnwb.XFlipResult)
    # Read `accepted` before any boundary: a rejected partition still carries cuts.
    assert xflip_res.accepted, xflip_res.rejection_reason
    assert xflip_res.boundaries == (n_per_block,)
    print("xFLIP correlation-block result:")
    print(f"  Accepted: {xflip_res.accepted}")
    bounds = [(int(start), int(end)) for start, end in xflip_res.block_bounds]
    print(f"  Block bounds (half-open contact indices): {bounds}")
    print(f"  Omnibus p-value: {xflip_res.p_values['omnibus']:.4f}")
    print(f"  Boundary drop at contact {n_per_block}: "
          f"{xflip_res.boundary_drops[n_per_block]:.3f}")

    # With rng=None the surrogates draw fresh entropy, and the result records it:
    # passing `surrogate_seed_entropy` back as `rng` reproduces every p-value. Shown on
    # synthetic white noise, whose p-values vary with the surrogate stream; on the blocks
    # above every stream gives the floor 1/(n_surrogates + 1).
    noise = rng.normal(size=(12, 300))
    fresh = jnwb.xflip(noise, n_blocks=2, min_block_size=3, n_surrogates=50, rng=None)
    again = jnwb.xflip(noise, n_blocks=2, min_block_size=3, n_surrogates=50,
                       rng=fresh.surrogate_seed_entropy)
    assert again.p_values == fresh.p_values
    print(f"White noise: accepted={fresh.accepted}, omnibus p={fresh.p_values['omnibus']:.3f}, "
          f"reproduced from surrogate_seed_entropy: {again.p_values == fresh.p_values}")


if __name__ == "__main__":
    main()
