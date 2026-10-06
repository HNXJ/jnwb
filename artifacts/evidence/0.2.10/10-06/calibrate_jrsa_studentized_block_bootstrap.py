"""Coverage of a studentized moving-block bootstrap-t for Pearson r on independent AR(1) pairs
(IB-44, ruled 2026-10-06). The candidate interval is written here, standalone; it is not in jnwb.

Pair s: two independent AR(1) series, coefficient 0.9, unit innovations, 100 burn-in samples
dropped, from default_rng(s); the same generator then draws the block starts. The true
correlation is 0. A replicate is floor(n/l) blocks of l samples with starts uniform on 0..n-l
(Kunsch 1989), x and y resampled together, 999 replicates. The se of a sample is the
delete-one-block jackknife over its blocks: non-overlapping blocks of l on the original, the
drawn blocks on a replicate. Interval: [r - q975 * se, r - q025 * se], q the quantiles of
t* = (r* - r) / se*. The percentile interval of the same replicates is printed beside it.

Usage: python calibrate_jrsa_studentized_block_bootstrap.py n_pairs n:l [n:l ...]
"""
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
from scipy.signal import lfilter

PHI, BURN, B = 0.9, 100, 999


def r_rows(x, y):
    x = x - x.mean(-1, keepdims=True)
    y = y - y.mean(-1, keepdims=True)
    return (x * y).sum(-1) / np.sqrt((x * x).sum(-1) * (y * y).sum(-1))


def jack_se(x, y, nb):
    """x, y: (..., nb, l) block arrays; delete-one-block jackknife se of r."""
    l = x.shape[-1]
    sh = x.shape[:-2]
    vals = []
    for j in range(nb):
        keep = [i for i in range(nb) if i != j]
        vals.append(r_rows(x[..., keep, :].reshape(*sh, -1), y[..., keep, :].reshape(*sh, -1)))
    v = np.stack(vals, -1)
    return np.sqrt((nb - 1) / nb * ((v - v.mean(-1, keepdims=True)) ** 2).sum(-1))


def job(args):
    n, l, seed = args
    rng = np.random.default_rng(seed)
    e = rng.standard_normal((2, n + BURN))
    x, y = lfilter([1.0], [1.0, -PHI], e, axis=-1)[:, BURN:]
    nb = n // l
    m = nb * l
    r = r_rows(x[:m], y[:m])
    se = jack_se(x[:m].reshape(nb, l), y[:m].reshape(nb, l), nb)
    starts = rng.integers(0, n - l + 1, size=(B, nb))
    idx = (starts[..., None] + np.arange(l)).reshape(B, nb, l)
    xb, yb = x[idx], y[idx]
    rb = r_rows(xb.reshape(B, -1), yb.reshape(B, -1))
    seb = jack_se(xb, yb, nb)
    t = (rb - r) / seb
    q025, q975 = np.quantile(t, [0.025, 0.975])
    lo, hi = r - q975 * se, r - q025 * se
    plo, phi_ = np.quantile(rb, [0.025, 0.975])
    return lo <= 0 <= hi, hi - lo, plo <= 0 <= phi_, phi_ - plo


if __name__ == "__main__":
    n_pairs = int(sys.argv[1])
    with ProcessPoolExecutor(12) as ex:
        for spec in sys.argv[2:]:
            n, l = map(int, spec.split(":"))
            out = np.array(list(ex.map(job, [(n, l, s) for s in range(n_pairs)], chunksize=10)),
                           dtype=float)
            c = out[:, 0].mean()
            cp = out[:, 2].mean()
            print(f"n={n} l={l} studentized cover={c:.4f} (se {np.sqrt(c*(1-c)/n_pairs):.4f}) "
                  f"width={out[:,1].mean():.3f} | percentile cover={cp:.4f} width={out[:,3].mean():.3f}",
                  flush=True)
