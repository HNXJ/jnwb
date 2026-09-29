"""Why 256-sample records cannot pass the pair test and 512-sample ones can.

Both lengths give 3 segments at zflip's default segmentation (nperseg = min(max(N//2, 8),
256), half overlap). What differs is the in-band bin count at the default 15-35 Hz band:
3 at N=256 (df 7.8 Hz) and 5 at N=512 (df 3.9 Hz). A pair's wPLI is the mean over in-band
bins, so a surrogate reaches 1.0 only when every bin's imaginary cross-spectrum keeps one
sign across the 3 segments. This counts, per pair, the fraction of phase-randomised
surrogates whose pair wPLI ties or exceeds 1.0 by zflip's own counting rule.

Uses the construction of tests/test_zflip_audit.py (broadband) and a 25 Hz sinusoid wave
(narrowband), 1000 surrogates each.

Usage: python tie_mass.py <tree>
"""
import os
import sys
import warnings

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
sys.path.insert(1, os.path.join(tree, "tests"))
import numpy as np  # noqa: E402
from scipy import signal  # noqa: E402
import jnwb  # noqa: E402
from jnwb import laminar  # noqa: E402
from jnwb.permutation import _count_at_least_as_extreme  # noqa: E402
from test_zflip_audit import TestSignConventionFromGroundTruth as T  # noqa: E402

assert os.path.abspath(jnwb.__file__).startswith(tree), jnwb.__file__
warnings.simplefilter("ignore")
FS, BAND, S = 1000.0, (15.0, 35.0), 1000


def tie_mass(lfp, rng):
    n = lfp.shape[1]
    nperseg = min(max(n // 2, 8), 256)
    kw = dict(fs=FS, nperseg=nperseg, noverlap=nperseg // 2, boundary=None, padded=False,
              axis=-1, detrend="linear")
    f, _, Z = signal.stft(lfp, **kw)
    mask = (f >= BAND[0]) & (f <= BAND[1])
    hits = np.zeros(lfp.shape[0] - 1)
    for _ in range(S):
        _, _, Zs = signal.stft(laminar._surrogate_phase_randomize(lfp, rng), **kw)
        for i in range(lfp.shape[0] - 1):
            w, _ = laminar._wpli_from_cross_spectra(np.conj(Zs[i]) * Zs[i + 1])
            hits[i] += _count_at_least_as_extreme([np.mean(w[mask])], 1.0, "greater")
    return Z.shape[-1], int(mask.sum()), hits / S


for n in (256, 512):
    broad = T._variable_length_wave(n, noise=0.005)
    t = np.arange(n) / FS
    narrow = np.stack([np.sin(2 * np.pi * 25 * (t - 0.001 * c)) for c in range(6)])
    narrow += 0.005 * np.random.default_rng(3).standard_normal(narrow.shape)
    for name, lfp in (("broadband", broad), ("25 Hz sinusoid", narrow)):
        segs, bins, mass = tie_mass(lfp, np.random.default_rng(0))
        print(f"N={n} {name:15s}: {segs} segments, {bins} in-band bins, per-pair fraction of "
              f"surrogates at wPLI >= 1.0: {np.round(mass, 3).tolist()}")
