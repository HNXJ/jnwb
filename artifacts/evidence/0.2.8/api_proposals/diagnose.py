"""Which leaves differ: jrsa repeat, jrsa n_jobs, directed_network n_jobs at the large size."""
try:
    import torch  # noqa: F401
except Exception:  # noqa: BLE001
    pass
import pathlib
import sys
import warnings

WT = pathlib.Path(r"C:/workspace/jnwb/.claude/worktrees/lane-c-08-06")
sys.path.insert(0, str(WT))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np  # noqa: E402

import jnwb  # noqa: E402
from measure_identity import arrays, make_inputs  # noqa: E402

warnings.simplefilter("ignore")


def diff(a, b, label):
    A, B = arrays(a), arrays(b)
    print(f"-- {label}: {len(A)} leaves")
    for k in A:
        x, y = A[k], B[k]
        if not np.array_equal(x, y, equal_nan=True):
            f = np.isfinite(x) & np.isfinite(y)
            scale = float(np.max(np.abs(x[f]))) if f.any() else 0.0
            d = float(np.max(np.abs(x[f] - y[f]))) if f.any() else float("nan")
            print(f"   {k:40} shape={x.shape} max|diff|={d:.3e} scale={scale:.3e} "
                  f"ref={np.ravel(x)[:3]} got={np.ravel(y)[:3]}")


I = make_inputs(1)
P30, P60 = I["POP"][:30], I["POP"][30:60]
a = jnwb.jrsa(P30, P60, permutations=50, null="iid", rng=0)
b = jnwb.jrsa(P30, P60, permutations=50, null="iid", rng=0)
diff(a, b, "jrsa repeat, n_jobs=1")
c = jnwb.jrsa(P30, P60, permutations=50, null="iid", rng=0, n_jobs=4)
diff(a, c, "jrsa n_jobs=4 vs 1")

I8 = make_inputs(8)
rng = np.random.default_rng(3)
_ = rng.standard_normal((20, 320)); _ = rng.standard_normal((20, 320))
sig = rng.standard_normal((4, 12000))
sig[1, 3:] += 0.5 * sig[0, :-3]
d1 = jnwb.directed_network(sig, method="granger", n_jobs=1, n_surrogates=32, rng=7)
d1b = jnwb.directed_network(sig, method="granger", n_jobs=1, n_surrogates=32, rng=7)
d4 = jnwb.directed_network(sig, method="granger", n_jobs=4, n_surrogates=32, rng=7)
diff(d1, d1b, "directed_network repeat n_jobs=1 (large)")
diff(d1, d4, "directed_network n_jobs=4 vs 1 (large)")
