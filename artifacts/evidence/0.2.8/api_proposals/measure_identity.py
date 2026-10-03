"""08-08: numerical identity across CPU, parallel CPU and CUDA for every public operation that
takes an execution switch (device, n_jobs, backend), measured on this machine.

Gap definition (the one tests/test_execution_switch.py states): for each numeric leaf of the
result, max|got - ref| / max|ref| over finite entries; the operation's gap is the worst leaf.
A leaf whose shape or finite mask differs is reported as MISMATCH, never as a gap.

Run: python <this file> [--json out.json]
"""
from __future__ import annotations

# PyTorch before CuPy: on Windows, once CuPy has loaded cuSPARSE, importing torch fails
# (tests/test_execution_switch.py, test_pytorch_loads_after_cupy_linalg).
try:
    import torch  # noqa: F401
except Exception:  # noqa: BLE001
    torch = None

import json
import os
import pathlib
import platform
import sys
import time
import warnings
from dataclasses import fields, is_dataclass

WT = pathlib.Path(r"C:/workspace/jnwb/.claude/worktrees/lane-c-08-06")
sys.path.insert(0, str(WT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import jnwb  # noqa: E402
import jnwb._backend as backend  # noqa: E402
from jnwb.trajectory import compute_population_trajectory  # noqa: E402

assert pathlib.Path(jnwb.__file__).resolve().is_relative_to(WT.resolve()), jnwb.__file__

CUDA_RTOL = 1e-9  # stated in tests/test_execution_switch.py and jnwb/_backend.py
RECORD_FIELDS = ("execution", "parameters")


def arrays(obj, prefix=""):
    if is_dataclass(obj) and not isinstance(obj, type):
        # `execution` and `parameters` are records of the call (runtime, n_jobs, backend), not
        # results: a first run counted jrsa's wall time and its n_jobs echo as a numeric gap.
        obj = {f.name: getattr(obj, f.name) for f in fields(obj)
               if f.name not in RECORD_FIELDS}
    elif hasattr(obj, "execution") and hasattr(obj, "to_dict"):
        obj = {k: v for k, v in obj.to_dict().items() if k not in ("execution", "parameters")}
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            out.update(arrays(value, f"{prefix}.{key}"))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            out.update(arrays(value, f"{prefix}[{i}]"))
    elif isinstance(obj, (np.ndarray, float, int, np.number)) and not isinstance(obj, (bool, np.bool_)):
        arr = np.asarray(obj)
        if arr.dtype.kind in "fciu":
            out[prefix or "."] = arr
    return out


def compare(ref, got):
    """(worst relative gap, bit_identical, n_leaves) or raises on a structural mismatch."""
    a, b = arrays(ref), arrays(got)
    if a.keys() != b.keys():
        raise AssertionError(f"leaf sets differ: {sorted(set(a) ^ set(b))[:5]}")
    worst, identical = 0.0, True
    for key in a:
        x, y = a[key], b[key]
        if x.shape != y.shape:
            raise AssertionError(f"{key}: shape {x.shape} vs {y.shape}")
        fx, fy = np.isfinite(x), np.isfinite(y)
        if not np.array_equal(fx, fy):
            raise AssertionError(f"{key}: finite masks differ")
        if not np.array_equal(x, y, equal_nan=x.dtype.kind in "fc"):
            identical = False
        if fx.any():
            scale = float(np.max(np.abs(x[fx]))) or 1.0
            worst = max(worst, float(np.max(np.abs(x[fx] - y[fx]))) / scale)
    return worst, identical, len(a)


def run(fn):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        t0 = time.perf_counter()
        result = fn()
        dt = time.perf_counter() - t0
    msgs = [str(w.message) for w in caught if issubclass(w.category, RuntimeWarning)]
    return result, dt, msgs


def recorded_device(result):
    if hasattr(result, "device"):
        return result.device
    if hasattr(result, "execution"):
        return result.execution.get("device")
    if isinstance(result, dict):
        return result.get("device_used")
    return None


# ---- inputs: the sizes of tests/test_execution_switch.py ("small") and 8x longer ("large")
FS = 1000.0


def make_inputs(scale):
    rng = np.random.default_rng(0)
    t = np.arange(4000 * scale) / FS
    x = np.sin(2 * np.pi * 20 * t) + 0.5 * rng.standard_normal(t.size)
    y = np.roll(x, 7) + 0.5 * rng.standard_normal(t.size)
    return dict(
        X=x, Y=y,
        P=rng.random((20 * scale, 10)) + 0.1, B=rng.random((20 * scale, 10)) + 0.1,
        SPIKES=np.sort(rng.uniform(0.0, 50.0 * scale, 1500 * scale)),
        POP=rng.standard_normal((200 * scale, 12)),
        LAMINAR=rng.standard_normal((16, 2000 * scale)),
        scale=scale,
    )


class Session:
    def __init__(self, n_units=12, scale=1):
        r = np.random.default_rng(1)
        self._df = pd.DataFrame({"unit_id": list(range(n_units)), "area": ["V1"] * n_units,
                                 "quality": ["stable"] * n_units})
        self._spikes = {i: np.sort(r.uniform(0.0, 30.0, 200 * scale)) for i in range(n_units)}

    def get_units(self, quality=None, area=None):
        return self._df

    def get_spike_times(self, unit_id):
        return self._spikes.get(unit_id, np.array([]))


EPOCHS = pd.DataFrame({"start_time": np.arange(2.0, 26.0, 1.5)})


def device_calls(I):
    X, Y, P, B, S, POP, LAM, s = (I[k] for k in ("X", "Y", "P", "B", "SPIKES", "POP", "LAMINAR", "scale"))
    return {
        "band_power": lambda d: jnwb.band_power(X, fs=FS, freq_range=(13, 30), normalize=False, device=d),
        "relative_power": lambda d: jnwb.relative_power(P, B, axis=0, device=d),
        "spectral_tilt": lambda d: jnwb.spectral_tilt(X, fs=FS, device=d),
        "harmonic_analysis": lambda d: jnwb.harmonic_analysis(X, fs=FS, device=d),
        "imaginary_coherency": lambda d: jnwb.imaginary_coherency(X, Y, fs=FS, device=d),
        "wpli": lambda d: jnwb.wpli(X, Y, fs=FS, device=d),
        "cross_area_coherence": lambda d: jnwb.cross_area_coherence(
            X, Y, fs=FS, freq_bands="canonical", n_surrogates=5, device=d),
        "complex_tfr": lambda d: jnwb.complex_tfr(np.stack([X, Y]), FS, np.linspace(5, 80, 6), device=d),
        "granger_causality": lambda d: jnwb.granger_causality(X[:1500 * s], Y[:1500 * s], order=4, device=d),
        "UnitAnalyzer.autocorrelogram": lambda d: jnwb.UnitAnalyzer.autocorrelogram(S, device=d),
        "PopulationAnalyzer.population_trajectory":
            lambda d: jnwb.PopulationAnalyzer.population_trajectory(POP, device=d),
        "compute_population_trajectory":
            lambda d: compute_population_trajectory(Session(scale=s), "V1", EPOCHS, device=d),
        "rdm": lambda d: jnwb.rdm(POP[:30 * s], device=d),
        "vflip": lambda d: jnwb.vflip(np.abs(LAM[:, :64]) + 1.0, np.linspace(1, 200, 64), device=d),
        "vflip_from_lfp": lambda d: jnwb.vflip_from_lfp(LAM, FS, device=d),
        "jrsa": lambda d: jnwb.jrsa(POP[:30], POP[30:60], permutations=10 * s, null="iid", rng=0, device=d),
    }


def njobs_calls(I):
    rng = np.random.default_rng(3)
    s = I["scale"]
    Xc = rng.standard_normal((20, 40 * s)) + 0.3
    Yc = rng.standard_normal((20, 40 * s))
    sig = rng.standard_normal((4, 1500 * s))
    sig[1, 3:] += 0.5 * sig[0, :-3]
    return {
        "cluster_permutation_test": lambda n: jnwb.cluster_permutation_test(
            Xc, Yc, n_permutations=64 * s, rng=np.random.default_rng(11), n_jobs=n),
        "cross_area_coherence": lambda n: jnwb.cross_area_coherence(
            I["X"], I["Y"], fs=FS, freq_bands="canonical", n_surrogates=32, n_jobs=n),
        "directed_network": lambda n: jnwb.directed_network(
            sig, method="granger", n_jobs=n, n_surrogates=32, rng=7),
        "jrsa": lambda n: jnwb.jrsa(I["POP"][:30], I["POP"][30:60], permutations=50 * s,
                                    null="iid", rng=0, n_jobs=n),
    }


def main():
    out = {"machine": {
        "python": sys.version.split()[0], "platform": platform.platform(),
        "numpy": np.__version__, "jnwb": jnwb.__version__, "jnwb_file": jnwb.__file__,
        "cpu_count": os.cpu_count(),
        "cupy_cuda": backend.cupy_available(), "torch_cuda": backend.torch_cuda_available(),
        "jax_metal": backend.jax_metal_available(),
    }, "device": [], "n_jobs": [], "backend": [], "combined": []}
    try:
        import cupy as cp
        out["machine"]["cupy"] = cp.__version__
        out["machine"]["gpu"] = cp.cuda.runtime.getDeviceProperties(0)["name"].decode()
    except Exception as exc:  # noqa: BLE001
        out["machine"]["cupy"] = f"unavailable: {exc!r}"
    out["machine"]["torch"] = getattr(torch, "__version__", None)

    for size in (1, 8):
        I = make_inputs(size)
        for name, call in device_calls(I).items():
            row = {"op": name, "size": "small" if size == 1 else "large"}
            try:
                cpu, t_cpu, _ = run(lambda: call("cpu"))
                cpu2, _, _ = run(lambda: call("cpu"))
                cuda, t_cuda, msgs = run(lambda: call("cuda"))
                row["cpu_repeat_identical"] = compare(cpu, cpu2)[1]
                gap, ident, leaves = compare(cpu, cuda)
                row.update(gap=gap, bit_identical=ident, leaves=leaves,
                           recorded=recorded_device(cuda), warned=bool(msgs),
                           warning=msgs[0][:160] if msgs else "",
                           t_cpu_s=round(t_cpu, 4), t_cuda_s=round(t_cuda, 4),
                           within_rtol=gap <= CUDA_RTOL)
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            out["device"].append(row)
            print("device", row, flush=True)

        for name, call in njobs_calls(I).items():
            row = {"op": name, "size": "small" if size == 1 else "large"}
            try:
                ref, t1, _ = run(lambda: call(1))
                row["t_n1_s"] = round(t1, 4)
                for n in (2, 4, 8, -1):
                    got, tn, msgs = run(lambda: call(n))
                    gap, ident, leaves = compare(ref, got)
                    row[f"n{n}"] = {"gap": gap, "bit_identical": ident, "t_s": round(tn, 4),
                                    "warned": bool(msgs)}
                row["leaves"] = leaves
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            out["n_jobs"].append(row)
            print("n_jobs", row, flush=True)

        # jrsa's backend switch, against numpy.
        P30, P60 = I["POP"][:30], I["POP"][30:60]
        ref, _, _ = run(lambda: jnwb.jrsa(P30, P60, permutations=20, null="iid", rng=0, backend="numpy"))
        for b in ("auto", "scipy", "cupy", "jax", "torch"):
            row = {"op": "jrsa", "size": "small" if size == 1 else "large", "backend": b}
            try:
                got, _, msgs = run(lambda: jnwb.jrsa(P30, P60, permutations=20, null="iid", rng=0, backend=b))
                gap, ident, leaves = compare(ref, got)
                row.update(gap=gap, bit_identical=ident, recorded=got.execution.get("backend"),
                           warned=bool(msgs), warning=msgs[0][:160] if msgs else "")
            except Exception as exc:  # noqa: BLE001
                row["error"] = f"{type(exc).__name__}: {exc}"[:300]
            out["backend"].append(row)
            print("backend", row, flush=True)

        # Both switches at once, where an operation takes both.
        row = {"op": "cross_area_coherence", "size": "small" if size == 1 else "large",
               "switches": "device='cuda', n_jobs=8 vs device='cpu', n_jobs=1"}
        try:
            ref, _, _ = run(lambda: jnwb.cross_area_coherence(I["X"], I["Y"], fs=FS, freq_bands="canonical",
                                                              n_surrogates=32, device="cpu", n_jobs=1))
            got, _, msgs = run(lambda: jnwb.cross_area_coherence(I["X"], I["Y"], fs=FS, freq_bands="canonical",
                                                                 n_surrogates=32, device="cuda", n_jobs=8))
            gap, ident, leaves = compare(ref, got)
            row.update(gap=gap, bit_identical=ident, recorded=recorded_device(got), warned=bool(msgs))
        except Exception as exc:  # noqa: BLE001
            row["error"] = f"{type(exc).__name__}: {exc}"[:300]
        out["combined"].append(row)
        print("combined", row, flush=True)

    if "--json" in sys.argv:
        path = pathlib.Path(sys.argv[sys.argv.index("--json") + 1])
        path.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8", newline="\n")
        print("wrote", path)
    print("machine", out["machine"])


if __name__ == "__main__":
    main()
