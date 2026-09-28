"""The quickstart PSI example: segments, bins and lead p by nperseg, over data seeds.

Usage: python quickstart_psi.py <worktree> <n_seeds>
"""
import os
import sys
import warnings

WT = os.path.abspath(sys.argv[1])
sys.path.insert(0, WT)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

assert os.path.normcase(os.path.abspath(jnwb.__file__)).startswith(os.path.normcase(WT))
print("jnwb from", jnwb.__file__)
ns = int(sys.argv[2])
warnings.simplefilter("ignore")
for nperseg in (None, 80, 100):
    p, pc, warn = [], [], 0
    for seed in range(ns):
        rng = np.random.default_rng(seed)
        a = rng.normal(size=1000)
        b = np.roll(a, 5) + 0.5 * rng.normal(size=1000)
        r = jnwb.phase_slope_index(a, b, fs=1000.0, bands=(8.0, 30.0), nperseg=nperseg,
                                   n_surrogates=50, rng=0)
        p.append(r.p_x_to_y)
        pc.append(r.diagnostics["p_coupling_surrogate"])
        warn += bool(r.diagnostics["warnings"])
    p = np.array(p, float)
    print(f"nperseg={nperseg}: n_seg={r.params['n_segments']} bins={r.per_band['band']['n_freq_bins']}"
          f" lead p<0.05 in {np.mean(p < 0.05):.3f}, median lead p {np.median(p):.2g},"
          f" max {p.max():.2g}; coupling p<0.05 {np.mean(np.array(pc) < 0.05):.3f};"
          f" runs with a warning {warn}/{ns}")
