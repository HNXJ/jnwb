"""Coverage of the jrsa paired-metric 95% bootstrap interval on independent AR(1) pairs (IB-44).

Pair s: two independent AR(1) series, coefficient 0.9, unit innovations, 100 burn-in samples
dropped, drawn from default_rng(s). The true correlation is 0, so coverage is the share of
intervals holding 0. Each call: jrsa(x, y, metric, bootstrap=999, permutations=0, rng=s, ...).

Usage: python calibrate_jrsa_block_bootstrap.py <worktree> <n_pairs> <metric> [n:null:block_len ...]
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.signal import lfilter

WORKTREE = sys.argv[1]
sys.path.insert(0, WORKTREE)
import jnwb  # noqa: E402

assert jnwb.__file__.replace("\\", "/").startswith(WORKTREE.replace("\\", "/")), jnwb.__file__

PHI, BURN, N_BOOT = 0.9, 100, 999


def job(args):
    metric, n, null, block_len, seed = args
    e = np.random.default_rng(seed).standard_normal((2, n + BURN))
    x, y = lfilter([1.0], [1.0, -PHI], e, axis=-1)[:, BURN:]
    res = jnwb.jrsa(x, y, metric=metric, bootstrap=N_BOOT, permutations=0, rng=seed,
                    null=null, block_len=block_len)
    lo, hi = np.asarray(res.ci, dtype=float)
    return float(lo), float(hi)


if __name__ == "__main__":
    n_pairs, metric = int(sys.argv[2]), sys.argv[3]
    configs = []
    for spec in sys.argv[4:]:
        n, null, bl = spec.split(":")
        configs.append((int(n), null, None if bl == "-" else int(bl)))
    print("jnwb from", jnwb.__file__)
    print(f"metric={metric} phi={PHI} bootstrap={N_BOOT} pairs seeds 0..{n_pairs - 1}")
    with ProcessPoolExecutor(20) as ex:
        for n, null, bl in configs:
            ci = np.array(list(ex.map(job, [(metric, n, null, bl, s) for s in range(n_pairs)],
                                      chunksize=5)))
            cover = float(np.mean((ci[:, 0] <= 0.0) & (0.0 <= ci[:, 1])))
            se = float(np.sqrt(cover * (1 - cover) / n_pairs))
            print(f"n={n:4d} null={null:5s} block_len={bl!s:4s} coverage={cover:.4f} "
                  f"(se {se:.4f}) mean width={float(np.mean(ci[:, 1] - ci[:, 0])):.4f}")
            sys.stdout.flush()
    print("rc=0")
