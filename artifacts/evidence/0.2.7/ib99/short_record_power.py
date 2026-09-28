"""Acceptance of a clean wave on short records, where few segments saturate wPLI.

At N=256 zflip's default segmentation gives 3 segments, so a clean wave's pair wPLI is 1.0
and a surrogate pair can also reach 1.0, a tie that counts against the pair. Uses the
construction of tests/test_zflip_audit.py (a 6-contact wave, 50 um pitch, band 15-35 Hz)
with its noise level 0.005, and counts accepted runs over surrogate seeds.

Usage: python short_record_power.py <tree>
"""
import os
import sys
import warnings

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
sys.path.insert(1, os.path.join(tree, "tests"))
import numpy as np  # noqa: E402
import jnwb  # noqa: E402
from test_zflip_audit import TestSignConventionFromGroundTruth as T  # noqa: E402

assert os.path.abspath(jnwb.__file__).startswith(tree), jnwb.__file__
warnings.simplefilter("ignore")

for n in (256, 512, 1024, 2048):
    wave = T._variable_length_wave(n, noise=0.005)
    for s in (19, 99, 199):
        acc, reasons = 0, set()
        for seed in range(20):
            r = jnwb.zflip(wave, 1000.0, orientation="superficial_to_deep", pitch_um=50.0,
                           freq_range=(15.0, 35.0), n_surrogates=s, rng=seed)
            acc += int(r.accepted)
            if not r.accepted:
                reasons.add("pair" if "own phase surrogates" in r.rejection_reason else
                            r.rejection_reason[:60])
        print(f"N={n:5d} n_surrogates={s:3d}: accepted {acc:2d}/20 surrogate seeds; "
              f"refusals {sorted(reasons)}")
