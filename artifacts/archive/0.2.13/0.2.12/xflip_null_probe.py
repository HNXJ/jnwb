"""Does xflip accept a probe with distance-decaying correlation and no boundary?

Each contact sees the same sources through a smooth spatial kernel (volume conduction), with no
change in structure along the shaft. A test of laminar blocks should reject this.
"""
import sys

import numpy as np

sys.path.insert(0, "C:/workspace/jnwb")
import jnwb  # noqa: E402

n_ch, n_t, fs = 24, 4000, 1000.0
accepted = 0
for seed in range(10):
    rng = np.random.default_rng(seed)
    sources = rng.standard_normal((n_ch * 3, n_t))
    pos_src = np.linspace(-6, n_ch + 6, n_ch * 3)
    pos_ch = np.arange(n_ch)
    kernel = np.exp(-np.abs(pos_ch[:, None] - pos_src[None, :]) / 3.0)
    lfp = kernel @ sources + 0.2 * rng.standard_normal((n_ch, n_t))
    res = jnwb.xflip(lfp, n_surrogates=100, rng=seed)
    accepted += bool(res.accepted)
    print(seed, res.accepted, res.boundaries, round(res.modularity, 3), res.p_values.get("omnibus"),
          res.rejection_reason if hasattr(res, "rejection_reason") else "")
print("accepted", accepted, "of 10 boundary-free probes")
