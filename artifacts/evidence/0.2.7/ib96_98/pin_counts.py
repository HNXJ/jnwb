"""Rejection counts for the candidate pinned seed sets, on the tree named by argv[1].

Usage: python pin_counts.py <tree containing jnwb/>
"""
import os
import sys
import time
import warnings

ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

assert os.path.normcase(os.path.abspath(jnwb.__file__)).startswith(os.path.normcase(ROOT))
print("jnwb from", jnwb.__file__)


def zl(n, rng):
    s = rng.normal(size=n)
    return s + 0.5 * rng.normal(size=n), s + 0.5 * rng.normal(size=n)


warnings.simplefilter("ignore")
t0 = time.time()
te_p = []
for seed in range(16):
    x, y = zl(2000, np.random.default_rng(seed))
    r = jnwb.transfer_entropy(x, y, bins=8, n_surrogates=49, rng=seed)
    te_p += [r.p_x_to_y, r.p_y_to_x]
te_p = np.array(te_p)
print(f"TE bins 8 n 2000, 16 seeds x 2 directions: rejections {int((te_p < 0.05).sum())} "
      f"min p {te_p.min():.3f} ({time.time() - t0:.1f} s)")

t0 = time.time()
psi_p = []
for seed in range(20):
    x, y = zl(2000, np.random.default_rng(seed))
    r = jnwb.phase_slope_index(x, y, fs=1000.0, bands=(5.0, 100.0), nperseg=50,
                               n_surrogates=49, rng=seed)
    psi_p.append(r.p_net)
psi_p = np.array(psi_p, float)
print(f"PSI nperseg 50, 20 seeds, n_surrogates 49: p_net rejections "
      f"{int((psi_p < 0.05).sum())} ({time.time() - t0:.1f} s)")
