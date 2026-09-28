"""False-positive rate under two true nulls, 500 seeds each, 199 surrogates."""
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"C:\workspace\jnwb")
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

N = 2000


def data(kind, seed):
    rng = np.random.default_rng(10_000 + seed)
    if kind == "independent":
        return rng.normal(size=N), rng.normal(size=N)
    s = rng.normal(size=N)
    return s + 0.5 * rng.normal(size=N), s + 0.5 * rng.normal(size=N)


def job(args):
    kind, seed = args
    warnings.simplefilter("ignore")
    x, y = data(kind, seed)
    g = jnwb.granger(x, y, order="auto", n_surrogates=199, rng=seed)
    te = jnwb.transfer_entropy(x, y, n_surrogates=199, rng=seed)
    te_nobc = jnwb.transfer_entropy(x, y, bias_correction=None, n_surrogates=199, rng=seed)
    psi = jnwb.phase_slope_index(x, y, fs=1000.0, bands=(5.0, 100.0), nperseg=100, n_surrogates=199, rng=seed)
    return kind, (g.p_x_to_y, g.p_y_to_x, te.p_x_to_y, te.p_y_to_x,
                  te_nobc.p_x_to_y, te_nobc.p_y_to_x, psi.p_net)


if __name__ == "__main__":
    jobs = [(k, s) for k in ("independent", "zero-lag mixing") for s in range(500)]
    with ProcessPoolExecutor(22) as ex:
        res = list(ex.map(job, jobs, chunksize=4))
    names = ["granger X->Y", "granger Y->X", "TE X->Y", "TE Y->X", "TE(no bias corr) X->Y",
             "TE(no bias corr) Y->X", "PSI (nperseg 100)"]
    for k in ("independent", "zero-lag mixing"):
        p = np.array([r[1] for r in res if r[0] == k], dtype=float)
        print(k)
        for i, n in enumerate(names):
            rate = np.mean(p[:, i] < 0.05)
            se = np.sqrt(0.05 * 0.95 / p.shape[0])
            print(f"  {n:24s} {rate:.3f}   (nominal 0.050, 2 SE = {2 * se:.3f})")
