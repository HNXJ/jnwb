"""Calibration of transfer_entropy and phase_slope_index p under true nulls.

Imports jnwb from the worktree named on the command line and asserts it did.
Usage: python calibrate.py <worktree> <te|psi|all> [n_seeds]
"""
import math
import os
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor

WT = os.path.abspath(sys.argv[1])
sys.path.insert(0, WT)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

_f = os.path.normcase(os.path.abspath(jnwb.__file__))
assert _f.startswith(os.path.normcase(WT)), _f

FS = 1000.0
BAND = (5.0, 100.0)


def band2se(p, n):
    return 2 * math.sqrt(p * (1 - p) / n)


def ar(e, a=0.8):
    out = np.empty_like(e)
    out[0] = e[0]
    for t in range(1, e.size):
        out[t] = a * out[t - 1] + e[t]
    return out


def make(kind, n_tr, n, rng):
    X = np.empty((n_tr, n))
    Y = np.empty((n_tr, n))
    for i in range(n_tr):
        if kind == "zl":
            s = rng.normal(size=n)
            X[i] = s + 0.5 * rng.normal(size=n)
            Y[i] = s + 0.5 * rng.normal(size=n)
        elif kind == "indep":
            X[i] = rng.normal(size=n)
            Y[i] = rng.normal(size=n)
        elif kind == "indep_ar":
            X[i] = ar(rng.normal(size=n))
            Y[i] = ar(rng.normal(size=n))
        else:
            raise KeyError(kind)
    return (X[0], Y[0]) if n_tr == 1 else (X, Y)


def te_job(args):
    kind, n, bins, k, l, nsur, seed = args
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(700_000 + seed)
    x, y = make(kind, 1, n, rng)
    r = jnwb.transfer_entropy(x, y, k=k, l=l, bins=bins, n_surrogates=nsur, rng=seed)
    return r.p_x_to_y, r.p_y_to_x


def psi_job(args):
    kind, n_tr, n, nperseg, nsur, seed = args
    warnings.simplefilter("ignore")
    rng = np.random.default_rng(3_000_000 + seed)
    x, y = make(kind, n_tr, n, rng)
    r = jnwb.phase_slope_index(x, y, fs=FS, bands=BAND, nperseg=nperseg,
                               n_surrogates=nsur, rng=seed)
    pc = r.diagnostics.get("p_coupling_surrogate")
    return (r.p_net if r.p_net is not None else np.nan,
            pc if pc is not None else np.nan, r.params["n_segments"])


def rate_line(label, p, ns):
    p = np.asarray(p, float)
    finite = np.isfinite(p)
    return (f"{label:44s} seeds={ns} rate={np.mean(p[finite] < 0.05):.3f} "
            f"[0.05 +- {band2se(0.05, ns):.3f}] n_undefined={int((~finite).sum())}")


def run_te(ex, ns):
    print("TE, default bias_correction='mm', n_surrogates=199: P(p < 0.05) X->Y and Y->X")
    grid = [("zl", 500, 4, 1, 1), ("zl", 2000, 4, 1, 1), ("zl", 4000, 4, 1, 1),
            ("zl", 2000, 8, 1, 1), ("zl", 2000, 4, 2, 2),
            ("indep", 2000, 4, 1, 1), ("indep", 500, 4, 1, 1), ("indep_ar", 2000, 4, 1, 1)]
    for kind, n, b, k, l in grid:
        t0 = time.time()
        res = np.array(list(ex.map(te_job, [(kind, n, b, k, l, 199, s) for s in range(ns)],
                                   chunksize=4)))
        lab = f"{kind} n={n} bins={b} k={k} l={l}"
        print("  " + rate_line(lab + " X->Y", res[:, 0], ns))
        print("  " + rate_line(lab + " Y->X", res[:, 1], ns), f"({time.time() - t0:.0f} s)")
        sys.stdout.flush()


def run_psi(ex, ns):
    print("PSI band (5, 100) Hz, fs 1000, jackknife=True: lead p = p_net; "
          "coupling p = diagnostics['p_coupling_surrogate']")
    grid = [("zl", 1, 2000, 50, 0), ("zl", 1, 2000, 100, 0), ("zl", 1, 2000, 200, 0),
            ("zl", 10, 400, 100, 0), ("indep", 1, 2000, 100, 0), ("indep", 10, 400, 100, 0),
            ("indep", 1, 2000, 50, 0), ("indep", 1, 2000, 200, 0)]
    for kind, n_tr, n, nps, nsur in grid:
        res = np.array(list(ex.map(psi_job, [(kind, n_tr, n, nps, nsur, s) for s in range(ns)],
                                   chunksize=8)))
        lab = f"{kind} {n_tr}x{n} nperseg={nps} nseg={int(res[0, 2])}"
        print("  " + rate_line(lab + " lead", res[:, 0], ns))
        sys.stdout.flush()
    # One setting with surrogates: the lead p must equal the no-surrogate lead p, and the
    # coupling p keeps its old (coupling) behaviour.
    ns2 = min(ns, 500)
    a = np.array(list(ex.map(psi_job, [("zl", 1, 2000, 100, 199, s) for s in range(ns2)],
                             chunksize=4)))
    b = np.array(list(ex.map(psi_job, [("zl", 1, 2000, 100, 0, s) for s in range(ns2)],
                             chunksize=8)))
    same = np.array_equal(a[:, 0], b[:, 0], equal_nan=True)
    print("  " + rate_line("zl 1x2000 nperseg=100 surr199 lead", a[:, 0], ns2),
          f"lead p identical to no-surrogate run: {same}")
    print("  " + rate_line("zl 1x2000 nperseg=100 surr199 coupling", a[:, 1], ns2))


if __name__ == "__main__":
    what = sys.argv[2]
    ns = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    print("jnwb from", jnwb.__file__)
    with ProcessPoolExecutor(22) as ex:
        if what in ("te", "all"):
            run_te(ex, ns)
        if what in ("psi", "all"):
            run_psi(ex, ns)
    print("rc=0")
