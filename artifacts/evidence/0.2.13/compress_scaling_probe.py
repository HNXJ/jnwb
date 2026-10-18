"""P-344: does compress_fp32's 800->1600 series slope match raw HDF5 cost at the same op count?

Builds files with N series (acquisition/s_i/data float64, 200 samples, plus starting_time and rate),
times compress_fp32 on all N data paths, and times a raw h5py control that performs the same
per-series work: copy the group into a fresh file, then replace its data by a float32 dataset.
Writes one JSON receipt. Args: out_dir.
"""
import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np

sys.path.insert(0, "C:/workspace/jnwb")
import jnwb  # noqa: E402

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
SIZES = [400, 800, 1600, 3200]
REPEATS = 3


def build(n: int) -> Path:
    p = OUT / f"src_{n}.h5"
    rng = np.random.default_rng(n)
    with h5py.File(p, "w") as f:
        acq = f.create_group("acquisition")
        for i in range(n):
            g = acq.create_group(f"s_{i}")
            g.create_dataset("data", data=rng.standard_normal(200))
            st = g.create_dataset("starting_time", data=0.0)
            st.attrs["rate"] = 1000.0
    return p


def control(src: Path, dst: Path) -> None:
    with h5py.File(src, "r") as s, h5py.File(dst, "w") as d:
        for key in s:
            s.copy(s[key], d, name=key)
        for name in s["acquisition"]:
            path = f"acquisition/{name}/data"
            arr = d[path][()]
            del d[path]
            d.create_dataset(path, data=arr.astype(np.float32), chunks=True,
                             compression="gzip", compression_opts=1, shuffle=True)


rows = []
for n in SIZES:
    src = build(n)
    sel = [f"acquisition/s_{i}/data" for i in range(n)]
    t_lib, t_ctl = [], []
    for r in range(REPEATS):
        dst = OUT / f"dst_{n}_{r}.h5"
        t0 = time.perf_counter()
        jnwb.compress_fp32(src, dst, select=sel, verify=False)
        t_lib.append(time.perf_counter() - t0)
        dst.unlink()
        ctl = OUT / f"ctl_{n}_{r}.h5"
        t0 = time.perf_counter()
        control(src, ctl)
        t_ctl.append(time.perf_counter() - t0)
        ctl.unlink()
    rows.append({"n": n, "lib_s": t_lib, "control_s": t_ctl,
                 "lib_median": float(np.median(t_lib)), "control_median": float(np.median(t_ctl))})
    print(n, rows[-1]["lib_median"], rows[-1]["control_median"], flush=True)

for a, b in zip(rows, rows[1:]):
    b["lib_ratio_vs_half"] = b["lib_median"] / a["lib_median"]
    b["control_ratio_vs_half"] = b["control_median"] / a["control_median"]
receipt = {"jnwb": jnwb.__file__, "h5py": h5py.__version__, "hdf5": h5py.version.hdf5_version,
           "rows": rows}
(OUT / "p344_receipt.json").write_text(json.dumps(receipt, indent=1))
for r in rows[1:]:
    print(r["n"], "lib x%.2f" % r["lib_ratio_vs_half"], "control x%.2f" % r["control_ratio_vs_half"])
