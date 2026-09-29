"""PSI power vs segment count; TE zero-lag calibration at 200 seeds; beta scenario with a beta band."""
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"C:\workspace\jnwb")
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

sys.path.insert(0, r"C:\Users\nejath\AppData\Local\Temp\claude\C--workspace-jnwb\18d30c63-6262-402d-b7b4-9da54d6715e0\scratchpad\showcase08")
from showcase import scenario, FS  # noqa: E402


def psi_job(args):
    name, seed, nperseg, band = args
    warnings.simplefilter("ignore")
    x, y, _ = scenario(name, seed)
    r = jnwb.phase_slope_index(x, y, fs=FS, bands=band, nperseg=nperseg, n_surrogates=199, rng=seed)
    return name, nperseg, str(band), r.net, r.p_net


def te_job(args):
    name, seed = args
    warnings.simplefilter("ignore")
    x, y, _ = scenario(name, seed)
    r = jnwb.transfer_entropy(x, y, k=1, l=1, delay=1, n_surrogates=199, rng=seed)
    return name, r.p_x_to_y, r.p_y_to_x


if __name__ == "__main__":
    jobs = [(n, s, nps, (5.0, 100.0)) for n in ("X->Y", "Y->X", "independent", "zero-lag mixing", "weak X->Y")
            for s in range(20) for nps in (500, 200, 100)]
    jobs += [("beta X leads Y by 5 ms", s, nps, (14.0, 30.0)) for s in range(20) for nps in (500, 200, 100)]
    with ProcessPoolExecutor(20) as ex:
        res = list(ex.map(psi_job, jobs))
        te = list(ex.map(te_job, [(n, s) for n in ("zero-lag mixing", "independent") for s in range(1000, 1200)]))
    print("PSI: rate p_net<0.05 and median net, by nperseg")
    keys = sorted({(r[0], r[1], r[2]) for r in res})
    for k in keys:
        rows = [r for r in res if (r[0], r[1], r[2]) == k]
        p = np.array([r[4] for r in rows], dtype=float); net = np.array([r[3] for r in rows])
        print(f"  {k[0]:24s} nperseg={k[1]:4d} band={k[2]:14s} rate={np.mean(p < 0.05):.2f}  "
              f"median net={np.median(net):+.3f}  sign+ {np.mean(net > 0):.2f}")
    print("TE, 200 fresh seeds each: rate p<0.05 (X->Y, Y->X)")
    for n in ("zero-lag mixing", "independent"):
        rows = [r for r in te if r[0] == n]
        pxy = np.array([r[1] for r in rows]); pyx = np.array([r[2] for r in rows])
        print(f"  {n:16s} {np.mean(pxy < 0.05):.3f} {np.mean(pyx < 0.05):.3f}  "
              f"either {np.mean((pxy < 0.05) | (pyx < 0.05)):.3f}")
