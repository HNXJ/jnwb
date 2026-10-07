"""Transfer entropy under zero-lag mixing: the surrogate-test excess by n, and what moves with it.

Pair s, default_rng(s): x = w + 0.5 e1, y = w + 0.5 e2, w white (no directed coupling).
transfer_entropy(x, y, bins=4, k=l=1, quantile, n_surrogates=199, rng=s), X -> Y only. Per n:
  rate      P(p_x_to_y < 0.05), the plug-in surrogate test the function reports
  excess    mean over pairs of 2 N ln2 (plug-in TE - mean plug-in TE of the surrogates), the
            observed value's offset from its null in chi-square units (0 if calibrated)
  cells     mean occupied (Y_t, Y_past, X_past) cells, data and surrogates (64 possible)
  mm_shift  mean over pairs of the Miller-Madow term the data's table carries minus the
            surrogates', the mechanism the 0.2.7 note names, in chi-square units
The surrogates are rebuilt here from the recorded child seed with the function's own scheme.

Usage: python te_excess_by_n.py <worktree> <n_pairs> <n> [<n> ...]
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

WORKTREE = sys.argv[1]
sys.path.insert(0, WORKTREE)
import jnwb  # noqa: E402
from jnwb.connectivity import _transfer_entropy as te_mod  # noqa: E402
from jnwb.connectivity._common import _surrogate_rng, _surrogate_source  # noqa: E402

assert jnwb.__file__.replace("\\", "/").startswith(WORKTREE.replace("\\", "/")), jnwb.__file__

B, N_SURR = 4, 199


def job(args):
    n, seed = args
    rng = np.random.default_rng(seed)
    w = rng.normal(size=n)
    x, y = w + 0.5 * rng.normal(size=n), w + 0.5 * rng.normal(size=n)
    res = jnwb.transfer_entropy(x, y, bins=B, n_surrogates=N_SURR, rng=seed)
    xq = te_mod._discretize(x[None], B, "quantile")
    yq = te_mod._discretize(y[None], B, "quantile")
    te_mm, plug, n_used, cells = te_mod._te_one_direction(xq, yq, 1, 1, 1, "mm")
    gen, _ = _surrogate_rng(seed, "transfer_entropy")
    s_plug, s_mm, s_cells = [], [], []
    for _ in range(N_SURR):
        xs = _surrogate_source(xq, gen).astype(np.int64)
        s_te, s_p, _, s_k = te_mod._te_one_direction(xs, yq, 1, 1, 1, "mm")
        s_plug.append(s_p)
        s_mm.append(s_te - s_p)
        s_cells.append(s_k)
        _surrogate_source(yq, gen)  # the function draws the Y -> X surrogate next
    scale = 2.0 * n_used * np.log(2.0)
    # The rebuilt null must be the function's: its p from the same draws, ties aside.
    rebuilt_p = (1 + np.sum(np.asarray(s_plug) >= plug)) / (N_SURR + 1)
    return (res.p_x_to_y, scale * (plug - np.mean(s_plug)), cells, np.mean(s_cells),
            scale * ((te_mm - plug) - np.mean(s_mm)), abs(rebuilt_p - res.p_x_to_y))


if __name__ == "__main__":
    n_pairs = int(sys.argv[2])
    sizes = [int(v) for v in sys.argv[3:]]
    print("jnwb from", jnwb.__file__)
    print(f"bins={B} k=l=1 n_surrogates={N_SURR} pairs seeds 0..{n_pairs - 1}")
    with ProcessPoolExecutor(20) as ex:
        for n in sizes:
            out = np.array(list(ex.map(job, [(n, s) for s in range(n_pairs)], chunksize=5)))
            rate = float(np.mean(out[:, 0] < 0.05))
            se = float(np.sqrt(rate * (1 - rate) / n_pairs))
            print(f"n={n:6d} rate={rate:.4f} (se {se:.4f}) "
                  f"excess={np.mean(out[:, 1]):+.3f} (se {np.std(out[:, 1]) / np.sqrt(n_pairs):.3f}) "
                  f"cells data={np.mean(out[:, 2]):.2f} surrogates={np.mean(out[:, 3]):.2f} "
                  f"mm_shift={np.mean(out[:, 4]):+.4f} "
                  f"max |rebuilt p - p|={np.max(out[:, 5]):.2g}")
            sys.stdout.flush()
    print("rc=0")
