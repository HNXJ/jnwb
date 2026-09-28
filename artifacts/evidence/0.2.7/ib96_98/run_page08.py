"""Execute every ```python block of docs/08 in order, in one namespace, from the worktree.

Usage: python run_page08.py <worktree> [n_data_seeds]
With n_data_seeds > 0, also re-runs the network and topology blocks over that many data
seeds and reports the density distribution and the Z example's p values.
"""
import os
import re
import sys
import time
import warnings

WT = os.path.abspath(sys.argv[1])
sys.path.insert(0, WT)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

assert os.path.normcase(os.path.abspath(jnwb.__file__)).startswith(os.path.normcase(WT))
print("jnwb from", jnwb.__file__)
page = open(os.path.join(WT, "docs", "08_directed_connectivity_and_information.md"),
            encoding="utf-8").read()
blocks = re.findall(r"^```python\n(.*?)^```", page, re.M | re.S)
ns = {}
for i, b in enumerate(blocks):
    t0 = time.time()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        exec(compile(b, f"<block {i}>", "exec"), ns)
    print(f"--- block {i} ok {time.time() - t0:.2f} s, warnings: "
          f"{sorted({str(x.message)[:80] for x in w})}")

extra = int(sys.argv[2]) if len(sys.argv) > 2 else 0
if extra:
    warnings.simplefilter("ignore")
    dens, psi_p, z_pair, z_cond = [], [], [], []
    for seed in range(extra):
        rng = np.random.default_rng(seed)
        X = rng.normal(size=500)
        Y = np.zeros(500)
        Y[1:] = 0.6 * X[:-1] + 0.2 * rng.normal(size=499)
        net = jnwb.directed_network({"A": X, "B": Y, "C": rng.normal(size=500)},
                                    method="granger", order=2, fdr=True,
                                    n_surrogates=200, rng=0)
        topo = jnwb.network_topology((net["q_matrix"] < 0.05).astype(float), threshold=0.5)
        dens.append(topo["density"])
        xl = rng.normal(size=4000)
        yl = np.zeros(4000)
        yl[5:] = 0.6 * xl[:-5] + rng.normal(size=3995)
        r = jnwb.phase_slope_index(xl, yl, fs=1000.0,
                                   bands={"beta": (14.0, 30.0), "gamma": (32.0, 80.0)},
                                   nperseg=250)
        psi_p.append(r.p_net)
        z = rng.normal(size=2000)
        xd, yd = np.zeros(2000), np.zeros(2000)
        xd[1:] = 0.6 * z[:-1] + rng.normal(size=1999)
        yd[3:] = 0.6 * z[:-3] + rng.normal(size=1997)
        z_pair.append(jnwb.granger(xd, yd, order="auto", max_lag=20).p_x_to_y)
        z_cond.append(jnwb.granger(xd, yd, order="auto", max_lag=20, Z=z).p_x_to_y)
    print(f"{extra} data seeds: density values {sorted(set(dens))}, "
          f"mean {np.mean(dens):.3f} (true graph: 1 edge of 6, density 1/6)")
    print(f"PSI lead p < 0.05 in {np.mean(np.array(psi_p) < 0.05):.2f}")
    print(f"Z example: pairwise p < 0.05 in {np.mean(np.array(z_pair) < 0.05):.2f}, "
          f"given Z in {np.mean(np.array(z_cond) < 0.05):.2f}")
print("rc=0")
