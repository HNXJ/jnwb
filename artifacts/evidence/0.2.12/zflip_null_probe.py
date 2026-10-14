"""Does zflip accept a probe with zero-lag volume conduction and no delay?

Same boundary-free probe as xflip_null_probe.py: every contact mixes the same sources through a
smooth spatial kernel, instantaneously. There is no depth delay, so zflip should reject.
"""
import sys

import numpy as np

sys.path.insert(0, "C:/workspace/jnwb")
import jnwb  # noqa: E402

n_ch, n_t, fs = 24, 8000, 1000.0
accepted = 0
for seed in range(10):
    rng = np.random.default_rng(seed)
    sources = rng.standard_normal((n_ch * 3, n_t))
    pos_src = np.linspace(-6, n_ch + 6, n_ch * 3)
    kernel = np.exp(-np.abs(np.arange(n_ch)[:, None] - pos_src[None, :]) / 3.0)
    lfp = kernel @ sources + 0.2 * rng.standard_normal((n_ch, n_t))
    res = jnwb.zflip(lfp, fs, orientation="superficial_to_deep", pitch_um=100.0, rng=seed)
    accepted += bool(res.accepted)
    print(seed, res.accepted, res.rejection_reason)
print("accepted", accepted, "of 10 delay-free probes")
