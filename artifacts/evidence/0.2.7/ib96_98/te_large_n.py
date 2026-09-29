"""TE plug-in surrogate rate under zero-lag mixing at larger n, fresh seeds.

Usage: python te_large_n.py <worktree> <n_seeds> <seed_offset> <n> [<n> ...]
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0], sys.argv[1], "te"] + sys.argv[2:]
import calibrate  # noqa: E402  (asserts jnwb comes from the worktree)


if __name__ == "__main__":
    ns, off = int(sys.argv[3]), int(sys.argv[4])
    sizes = [int(v) for v in sys.argv[5:]]
    print("jnwb from", calibrate.jnwb.__file__)
    with ProcessPoolExecutor(22) as ex:
        for n in sizes:
            res = np.array(list(ex.map(calibrate.te_job,
                                       [("zl", n, 4, 1, 1, 199, off + s) for s in range(ns)],
                                       chunksize=4)))
            for j, d in enumerate(("X->Y", "Y->X")):
                print("  " + calibrate.rate_line(f"zl n={n} bins=4 offset={off} {d}",
                                                 res[:, j], ns))
            either = np.mean(np.minimum(res[:, 0], res[:, 1]) < 0.05)
            print(f"  pooled directions rate={np.mean(res < 0.05):.4f} over {2 * ns} p-values;"
                  f" either direction {either:.3f}")
            sys.stdout.flush()
    print("rc=0")
