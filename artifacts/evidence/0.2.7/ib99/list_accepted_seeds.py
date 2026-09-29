"""The seeds of the independent-end-contact construction that zflip accepts, with pair details.

Same construction as calibrate_independent_contact.py, bandpassed noise, rng=0.
Usage: python list_accepted_seeds.py <tree>
"""
import os
import sys
import warnings

tree = os.path.abspath(sys.argv[1])
sys.path.insert(0, tree)
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, here)
import numpy as np  # noqa: E402
import jnwb  # noqa: E402
from calibrate_independent_contact import FS, TRUE_TAU, lagged, noise  # noqa: E402

assert os.path.abspath(jnwb.__file__).startswith(tree), jnwb.__file__
warnings.simplefilter("ignore")

base = lagged()
for kind in ("bandpassed", "white", "1/f^2"):
    for seed in range(100):
        d = base.copy()
        idx = 0 if seed % 2 else 4
        d[idx] = noise(kind, np.random.default_rng(10_000 + seed), base.shape[1])
        r = jnwb.zflip(d, FS, orientation="superficial_to_deep", pitch_um=100.0,
                       n_surrogates=50, rng=0)
        if r.accepted:
            print(f"{kind:10s} seed {10_000 + seed} contact {idx}: tau/true "
                  f"{r.tau_per_channel_s / TRUE_TAU:.2f} wpli {np.round(r.adjacent_wpli, 3).tolist()} "
                  f"r2 {np.round(r.adjacent_linearity_r2, 3).tolist()} p {r.p_value:.4f}")
