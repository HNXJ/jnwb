"""PSI lead-p rejection rates at the old and the new default segment count (D10(c)).

One 2000-sample trial at fs 1000 Hz. Old default: nperseg = n_times // 4 = 500 (7 segments).
New default: nperseg=None (190 samples, 20 segments). Scenarios, seed s per pair:
  mixing      x = w + 0.5 e1, y = w + 0.5 e2, w white (no lead; zero-lag common source)
  independent x, y white and independent (no coupling)
  lead        x white, y = x delayed 5 samples + 1.0 e (a true lead of x)
The rate is P(p_net < 0.05) of the jackknife t test, over bands (5, 100) Hz and None.

Usage: python calibrate_psi_default_segments.py <worktree> <n_seeds>
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

WORKTREE = sys.argv[1]
sys.path.insert(0, WORKTREE)
import jnwb  # noqa: E402

assert jnwb.__file__.replace("\\", "/").startswith(WORKTREE.replace("\\", "/")), jnwb.__file__

N, FS = 2000, 1000.0


def pair(scenario, seed):
    rng = np.random.default_rng(seed)
    if scenario == "mixing":
        w = rng.normal(size=N)
        return w + 0.5 * rng.normal(size=N), w + 0.5 * rng.normal(size=N)
    if scenario == "independent":
        return rng.normal(size=N), rng.normal(size=N)
    x = rng.normal(size=N + 5)
    return x[5:], x[:-5] + 1.0 * rng.normal(size=N)


def job(args):
    scenario, nperseg, bands, seed = args
    x, y = pair(scenario, seed)
    res = jnwb.phase_slope_index(x, y, fs=FS, nperseg=nperseg, bands=bands)
    return np.nan if res.p_net is None else res.p_net, res.params["n_segments"]


if __name__ == "__main__":
    n_seeds = int(sys.argv[2])
    print("jnwb from", jnwb.__file__)
    print(f"n={N} fs={FS} seeds 0..{n_seeds - 1}")
    with ProcessPoolExecutor(20) as ex:
        for scenario in ("mixing", "independent", "lead"):
            for bands in ((5.0, 100.0), None):
                for label, nperseg in (("old n//4", N // 4), ("new default", None)):
                    out = np.array(list(ex.map(
                        job, [(scenario, nperseg, bands, s) for s in range(n_seeds)],
                        chunksize=50)))
                    p = out[:, 0]
                    rate = float(np.mean(p < 0.05))
                    se = float(np.sqrt(rate * (1 - rate) / n_seeds))
                    print(f"{scenario:11s} bands={bands!s:12s} {label:11s} "
                          f"segments={int(out[0, 1]):3d} P(p<0.05)={rate:.4f} (se {se:.4f}) "
                          f"undefined={int(np.isnan(p).sum())}")
                    sys.stdout.flush()
    print("rc=0")
