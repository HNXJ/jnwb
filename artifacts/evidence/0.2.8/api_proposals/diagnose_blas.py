"""Is directed_network's n_jobs gap the BLAS thread count inside workers?

Serial with BLAS limited to one thread, against n_jobs=4 (whose workers run one BLAS thread
each under joblib/loky) and against serial with default BLAS threads.
"""
import pathlib
import sys
import warnings

WT = pathlib.Path(r"C:/workspace/jnwb/.claude/worktrees/lane-c-08-06")
sys.path.insert(0, str(WT))
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np  # noqa: E402
from threadpoolctl import threadpool_info, threadpool_limits  # noqa: E402

import jnwb  # noqa: E402
from measure_identity import compare  # noqa: E402

warnings.simplefilter("ignore")
print("blas:", [(i.get("internal_api"), i.get("num_threads")) for i in threadpool_info()])
rng = np.random.default_rng(3)
_ = rng.standard_normal((20, 320)); _ = rng.standard_normal((20, 320))
sig = rng.standard_normal((4, 12000))
sig[1, 3:] += 0.5 * sig[0, :-3]


def call(n):
    return jnwb.directed_network(sig, method="granger", n_jobs=n, n_surrogates=32, rng=7)


serial_default = call(1)
with threadpool_limits(limits=1):
    serial_one = call(1)
par4 = call(4)
print("serial(default BLAS) vs serial(1 BLAS thread):", compare(serial_default, serial_one)[:2])
print("serial(1 BLAS thread) vs n_jobs=4:           ", compare(serial_one, par4)[:2])
print("serial(default BLAS) vs n_jobs=4:             ", compare(serial_default, par4)[:2])
