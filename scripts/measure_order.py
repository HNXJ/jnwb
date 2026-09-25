"""Measure the computational order of jnwb exports as a fitted exponent in one named parameter.

Each spec calls one export at four or five sizes spanning at least a decade of its parameter.
Per size: the inputs are built outside the timed region, one untimed warm-up call runs, then
``--repeats`` timed calls with garbage collection disabled; the median is kept. The exponent is
the least-squares slope of log(median) on log(size), and ``r2`` is that fit's coefficient of
determination. Raw medians are printed beside every exponent.

Method, as ``artifacts/evidence/0.2.6/computational_order.md`` section 2 states it:

* BLAS/OpenMP pools are pinned to one thread with ``threadpoolctl.threadpool_limits(1)``, and the
  pin is verified: setting ``OMP_NUM_THREADS`` alone left 24 threads live on the machine this was
  calibrated on, and thread parallelism that grows with size suppresses the exponent.
* Sweeps run serially. Two at once contend for cores and corrupt both.
* ``jnwb`` is imported from the checkout this script sits in, and that is asserted: a copy in
  site-packages would otherwise be timed silently.
* ``--calibrate`` runs workloads of exactly known order first, so the method error on this host
  is on the record beside the result.

Usage::

    python scripts/measure_order.py --list
    python scripts/measure_order.py "phase_slope_index[n_samples_jackknife]" --repeats 5
    python scripts/measure_order.py --calibrate --json out.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable, Dict, List, NamedTuple, Sequence

import numpy as np
import threadpoolctl

ROOT = Path(__file__).resolve().parents[1]


def import_checkout_jnwb():
    """Import jnwb from this checkout, or refuse. Called by ``main``, never at import time.

    Importing this module must not touch ``sys.path``: a test that imports it while qualifying an
    installed jnwb would otherwise start timing, or testing, the checkout instead.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import jnwb

    if ROOT not in Path(jnwb.__file__).resolve().parents:
        raise SystemExit(f"jnwb imported from {jnwb.__file__}, not from {ROOT}; refusing to time it")
    return jnwb


class Spec(NamedTuple):
    parameter: str
    sizes: Sequence[int]
    #: Pinned values of every other input, stated so the row can be read without the code.
    held: str
    #: size -> zero-argument callable. Everything it closes over is built before timing.
    build: Callable[[int, Path], Callable[[], object]]


def _psi(jackknife: bool) -> Callable[[int, Path], Callable[[], object]]:
    def build(n: int, _tmp: Path) -> Callable[[], object]:
        import jnwb

        rng = np.random.default_rng(0)
        x = rng.normal(size=n)
        y = np.roll(x, 5) + rng.normal(size=n)
        return lambda: jnwb.phase_slope_index(
            x, y, fs=1000.0, nperseg=256, jackknife=jackknife, n_surrogates=0
        )

    return build


def _npz(n_file: int, n_slice: int, at_end: bool, tmp: Path) -> Callable[[], object]:
    import jnwb

    path = tmp / f"stored_{n_file}.npz"
    if not path.exists():
        np.savez(path, a=np.random.default_rng(0).normal(size=n_file))
    lo = n_file - n_slice if at_end else 0
    sl = (slice(lo, lo + n_slice),)
    return lambda: jnwb.stream_npz_array(path, "a", slice_tuple=sl)


SPECS: Dict[str, Spec] = {
    "phase_slope_index[n_samples]": Spec(
        "n_samples", (60_000, 200_000, 700_000, 2_000_000, 4_000_000),
        "1-D pair, fs=1000, nperseg=256, noverlap=128, bands=None, jackknife=False, n_surrogates=0",
        _psi(jackknife=False),
    ),
    "phase_slope_index[n_samples_jackknife]": Spec(
        "n_samples", (5_000, 12_000, 22_000, 35_000, 50_000),
        "1-D pair, fs=1000, nperseg=256, noverlap=128, bands=None, jackknife=True (default), "
        "n_surrogates=0",
        _psi(jackknife=True),
    ),
    "stream_npz_array[n_elements_in_file]": Spec(
        "n_elements_in_file", (100_000, 1_000_000, 4_000_000, 16_000_000),
        "float64, 1-D, ZIP_STORED (np.savez), the last 1000 elements",
        lambda n, tmp: _npz(n, 1000, True, tmp),
    ),
    "stream_npz_array[n_elements_sliced]": Spec(
        "n_elements_sliced", (1_000, 10_000, 100_000, 1_000_000, 4_000_000),
        "float64, 1-D, ZIP_STORED (np.savez), 4e6 elements in the file, the first k elements",
        lambda k, tmp: _npz(4_000_000, k, False, tmp),
    ),
}


def _py_double_loop(n: int, _tmp: Path) -> Callable[[], object]:
    def run() -> int:
        s = 0
        for i in range(n):
            for j in range(n):
                s += i ^ j
        return s

    return run


def _matmul(n: int, _tmp: Path) -> Callable[[], object]:
    a = np.random.default_rng(0).normal(size=(n, n))
    return lambda: a @ a


def _add(n: int, _tmp: Path) -> Callable[[], object]:
    a = np.random.default_rng(0).normal(size=n)
    return lambda: np.add(a, a)


#: Workloads whose order is known exactly; the fitted error on them bounds the method error.
CALIBRATION: Dict[str, tuple] = {
    # Starts above 1e6: below it the operands sit in cache and the per-element cost is lower.
    "np.add": (1.0, Spec("n", (1_000_000, 3_000_000, 10_000_000, 30_000_000), "float64", _add)),
    "python double loop": (2.0, Spec("n", (100, 300, 1000), "int xor", _py_double_loop)),
    "np.matmul": (3.0, Spec("n", (200, 400, 1000, 2048), "float64 square", _matmul)),
}


def pin_threads() -> threadpoolctl.threadpool_limits:
    limiter = threadpoolctl.threadpool_limits(limits=1)
    live = [p for p in threadpoolctl.threadpool_info() if p.get("num_threads") != 1]
    if live:
        raise SystemExit(f"thread pools still unpinned after threadpool_limits(1): {live}")
    return limiter


def time_call(fn: Callable[[], object], repeats: int) -> float:
    fn()
    samples = []
    for _ in range(repeats):
        gc.disable()
        try:
            t0 = time.perf_counter()
            fn()
            samples.append(time.perf_counter() - t0)
        finally:
            gc.enable()
    return statistics.median(samples)


def fit(sizes: Sequence[int], medians: Sequence[float]) -> Dict[str, float]:
    lx = np.log(np.asarray(sizes, dtype=float))
    ly = np.log(np.asarray(medians, dtype=float))
    slope, intercept = np.polyfit(lx, ly, 1)
    resid = ly - (slope * lx + intercept)
    ss_tot = float(np.sum((ly - ly.mean()) ** 2))
    r2 = 1.0 - float(np.sum(resid**2)) / ss_tot if ss_tot > 0 else float("nan")
    return {"exp": float(slope), "r2": r2, "t_span": float(max(medians) / min(medians))}


def sweep(name: str, spec: Spec, repeats: int, sizes: Sequence[int] | None, tmp: Path) -> Dict:
    sizes = tuple(sizes or spec.sizes)
    if max(sizes) < 10 * min(sizes):
        raise SystemExit(f"{name}: sizes {sizes} span less than a decade")
    medians = []
    for n in sizes:
        fn = spec.build(n, tmp)
        medians.append(time_call(fn, repeats))
        del fn
    row = {"spec": name, "parameter": spec.parameter, "held": spec.held,
           "sizes": list(sizes), "median_s": medians, "repeats": repeats}
    row.update(fit(sizes, medians))
    return row


def markdown(row: Dict) -> str:
    ms = ", ".join(f"{1e3 * t:.4g}" for t in row["median_s"])
    sizes = ", ".join(str(s) for s in row["sizes"])
    return (f"| `{row['spec']}` | {row['parameter']} | {sizes} | {ms} | {row['exp']:+.2f} | "
            f"{row['r2']:.3f} | {row['t_span']:.0f}x |")


def provenance(jnwb) -> Dict[str, object]:
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain",
                                     "--untracked-files=no"], capture_output=True, text=True,
                                    check=True).stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        head, dirty = "unknown", None
    return {
        "commit": head, "tracked_changes": dirty, "jnwb_file": jnwb.__file__,
        "python": sys.version.split()[0], "numpy": np.__version__,
        "machine": platform.machine(), "processor": platform.processor(),
        "platform": platform.platform(), "logical_cpus": os.cpu_count(),
        "thread_pools": [(p.get("internal_api"), p.get("num_threads"))
                         for p in threadpoolctl.threadpool_info()],
        "timing": "median of repeats after one untimed warm-up, gc disabled, perf_counter",
    }


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("specs", nargs="*", help="spec names; default: all")
    ap.add_argument("--list", action="store_true", help="print the spec names and exit")
    ap.add_argument("--repeats", type=int, default=5)
    ap.add_argument("--sizes", type=lambda s: [int(float(v)) for v in s.split(",")],
                    help="comma-separated size ladder overriding the spec's")
    ap.add_argument("--calibrate", action="store_true", help="run the known-order workloads first")
    ap.add_argument("--json", type=Path, help="also write every row and the provenance here")
    args = ap.parse_args(argv)

    jnwb = import_checkout_jnwb()
    if args.list:
        print(f"jnwb: {jnwb.__file__}")
        for name, spec in SPECS.items():
            print(f"{name}: {spec.held}")
        return 0
    unknown = [s for s in args.specs if s not in SPECS]
    if unknown:
        ap.error(f"unknown spec(s) {unknown}; see --list")

    limiter = pin_threads()
    try:
        prov = provenance(jnwb)
        print(json.dumps(prov, indent=1))
        rows: List[Dict] = []
        with tempfile.TemporaryDirectory() as tmp:
            if args.calibrate:
                for name, (true_order, spec) in CALIBRATION.items():
                    row = sweep(name, spec, args.repeats, None, Path(tmp))
                    row["true_order"] = true_order
                    rows.append(row)
                    print(f"calibration {name}: true {true_order:+.2f}, fitted {row['exp']:+.2f}, "
                          f"error {abs(row['exp'] - true_order):.2f}")
            for name in args.specs or list(SPECS):
                row = sweep(name, SPECS[name], args.repeats, args.sizes, Path(tmp))
                rows.append(row)
                print(markdown(row))
                sys.stdout.flush()
    finally:
        limiter.restore_original_limits()
    if args.json:
        args.json.write_text(json.dumps({"provenance": prov, "rows": rows}, indent=1),
                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
