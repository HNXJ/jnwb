"""scripts/vflip2_simulation.py on seeds 0 to 9: pinned counts and the preconditions they rest on.

The subset is the script's own first ten seeds (SEEDS[:10]), and every number comes from the
script's functions, so a change to its seed list or its SNR moves the counts and fails the pins.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from scripts import vflip2_simulation as sim  # noqa: E402

SUBSET = sim.SEEDS[:10]
PINNED = {
    "planted_probes": 10,
    "planted_accepted": 9,
    "planted_within_one_contact": 2,
    "null_probes": 10,
    "null_accepted": 3,
}
# 3 sigma bound on |Pearson r| between row index and log10 band power, for n_rows independent rows.
R_BOUND = 3 / np.sqrt(sim.N_CONTACTS)


@pytest.fixture(scope="module")
def outcomes():
    return sim.run_sets(seeds=SUBSET)


@pytest.fixture(scope="module")
def lfps():
    """Per seed: planted LFP at the script's SNR, null LFP at snr 0, and planted LFP at half the SNR."""
    return {
        seed: (sim.build_probe(seed, snr=sim.SNR), sim.build_probe(seed, snr=0.0),
               sim.build_probe(seed, snr=sim.SNR / 2))
        for seed in SUBSET
    }


def test_pinned_counts_on_seeds_0_to_9(outcomes):
    planted, null = outcomes
    assert len(planted) == len(null) == 10
    assert sim.counts(planted, null) == PINNED


def test_planted_and_null_share_their_background(lfps):
    """planted(s) = background + s * motif, the background drawn from the seed alone.

    So planted(SNR) - null = 2 * (planted(SNR/2) - null) holds only when all three calls draw
    one background, the null's included; the residual is background(planted) - background(null).
    """
    for seed, (planted, null, half) in lfps.items():
        assert np.allclose(planted - null, 2.0 * (half - null), rtol=1e-9, atol=1e-12), seed


def test_planted_component_carries_the_band_gradient(lfps):
    """Planted minus null (the motif alone): gamma higher on rows 0..c, beta higher on rows c+1..last."""
    for seed, (planted, null, _) in lfps.items():
        component = planted - null
        assert np.abs(component).max() > 0, seed
        c = sim.planted_contact(seed)
        gamma, beta = sim.band_rows(component)
        assert gamma[: c + 1].mean() > gamma[c + 1:].mean(), seed
        assert beta[c + 1:].mean() > beta[: c + 1].mean(), seed


def test_null_probes_have_no_larger_gradient_than_noise_allows(lfps):
    """For each null probe and band: |Pearson r(row index, log10 band power)| < 3 / sqrt(n_rows)."""
    rows = np.arange(sim.N_CONTACTS, dtype=float)
    for seed, (_, null, _) in lfps.items():
        for name, band in zip(("gamma", "beta"), sim.band_rows(null)):
            r = np.corrcoef(rows, np.log10(band))[0, 1]
            assert abs(r) < R_BOUND, (seed, name, r)
