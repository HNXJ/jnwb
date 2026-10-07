"""CPU vs CUDA loadings of PopulationAnalyzer.population_trajectory on float32 data whose
top two singular values differ by a set relative gap. Prints, per gap and seed, the largest
absolute loading difference over the first two components after the library's sign pin."""
import sys
import warnings

import numpy as np

import jnwb
from jnwb.analyzers import PopulationAnalyzer

print("jnwb from", jnwb.__file__)
import cupy as cp  # noqa: E402

print("cupy", cp.__version__, "devices", cp.cuda.runtime.getDeviceCount())

N_BINS, N_UNITS = 500, 20


def make_x(gap, seed):
    rng = np.random.default_rng(seed)
    u = rng.standard_normal((N_BINS, N_UNITS))
    u -= u.mean(axis=0)
    u, _ = np.linalg.qr(u)
    v, _ = np.linalg.qr(rng.standard_normal((N_UNITS, N_UNITS)))
    s = np.linspace(1.0, 0.1, N_UNITS)
    s[0] = 10.0
    s[1] = 10.0 * (1.0 - gap)
    s[2] = 5.0
    return ((u * s) @ v.T).astype(np.float32)


def run(gap, seed):
    X = make_x(gap, seed)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        cpu = PopulationAnalyzer.population_trajectory(X, n_components=3, device="cpu")
        gpu = PopulationAnalyzer.population_trajectory(X, n_components=3, device="cuda")
    assert cpu["device_used"] == "cpu" and gpu["device_used"] == "cuda", (cpu["device_used"], gpu["device_used"])
    assert cpu["components"].dtype == np.float32, cpu["components"].dtype
    s = np.linalg.svd(X.astype(np.float64), compute_uv=False)
    realized_gap = (s[0] - s[1]) / s[0]
    d12 = np.abs(cpu["components"][:2] - gpu["components"][:2]).max()
    d3 = np.abs(cpu["components"][2] - gpu["components"][2]).max()
    return realized_gap, d12, d3


for gap in (1.5e-5, 1e-4, 1e-3, 1e-2):
    rows = [run(gap, seed) for seed in range(10)]
    rg = np.array([r[0] for r in rows])
    d12 = np.array([r[1] for r in rows])
    d3 = np.array([r[2] for r in rows])
    print(f"gap={gap:.1e} realized={rg.min():.2e}..{rg.max():.2e} "
          f"max|dload| comps1-2 median={np.median(d12):.4g} min={d12.min():.4g} max={d12.max():.4g} "
          f"| comp3 max={d3.max():.3g}")
sys.stdout.flush()
