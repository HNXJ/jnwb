"""Showcase of docs/08_directed_connectivity_and_information.md against known ground truth.

Part A runs every Python block of the page, in order, in one namespace.
Part B runs the four directed estimators on eight scenarios whose true direction is known,
over N_SEEDS independent draws, and counts how often each direction tests significant.
Part C checks directed_network + network_topology on a chain with a bystander.
Part D checks spike mutual information on dependent vs independent trains.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO = Path(r"C:\workspace\jnwb")
sys.path.insert(0, str(REPO))
import numpy as np  # noqa: E402
import jnwb  # noqa: E402

OUT = Path(__file__).resolve().parent
N = 2000
FS = 1000.0
N_SEEDS = 20
N_SURR = 199
ALPHA = 0.05


# ---------------------------------------------------------------- scenarios
def ar_noise(rng, n):
    return rng.normal(size=n)


def scenario(name, seed):
    """Return X, Y, Z (Z may be None) and the true direction."""
    rng = np.random.default_rng(seed)
    e = lambda: rng.normal(size=N)  # noqa: E731
    if name == "X->Y":
        x = e(); y = np.zeros(N); ey = e()
        for t in range(1, N):
            y[t] = 0.3 * y[t - 1] + 0.5 * x[t - 1] + ey[t]
        return x, y, None
    if name == "Y->X":
        y = e(); x = np.zeros(N); ex = e()
        for t in range(1, N):
            x[t] = 0.3 * x[t - 1] + 0.5 * y[t - 1] + ex[t]
        return x, y, None
    if name == "independent":
        return e(), e(), None
    if name == "bidirectional":
        x = np.zeros(N); y = np.zeros(N); ex = e(); ey = e()
        for t in range(1, N):
            x[t] = 0.2 * x[t - 1] + 0.4 * y[t - 1] + ex[t]
            y[t] = 0.2 * y[t - 1] + 0.4 * x[t - 1] + ey[t]
        return x, y, None
    if name == "zero-lag mixing":
        s = e()
        return s + 0.5 * e(), s + 0.5 * e(), None
    if name == "weak X->Y":
        x = e(); y = np.zeros(N); ey = e()
        for t in range(1, N):
            y[t] = 0.3 * y[t - 1] + 0.1 * x[t - 1] + ey[t]
        return x, y, None
    if name == "beta X leads Y by 5 ms":
        # band-limited drive: X is a noisy 20 Hz rhythm, Y is X delayed 5 samples plus noise
        t = np.arange(N + 10) / FS
        phase = np.cumsum(2 * np.pi * (20 + 2 * rng.normal(size=t.size)) / FS)
        src = np.sin(phase) + 0.3 * rng.normal(size=t.size)
        x = src[10:] + 0.5 * e()
        y = src[5:-5] + 0.5 * e()
        return x, y, None
    if name == "common driver Z":
        z = e(); x = np.zeros(N); y = np.zeros(N); ex = e(); ey = e()
        for t in range(3, N):
            x[t] = 0.6 * z[t - 1] + ex[t]
            y[t] = 0.6 * z[t - 3] + ey[t]
        return x, y, z
    raise KeyError(name)


SCENARIOS = {  # name -> (X->Y should be significant, Y->X should be significant)
    "X->Y": (True, False),
    "Y->X": (False, True),
    "independent": (False, False),
    "bidirectional": (True, True),
    "zero-lag mixing": (False, False),
    "weak X->Y": (True, False),
    "beta X leads Y by 5 ms": (True, False),
    "common driver Z": (False, False),  # truth: no X-Y interaction at all
}


def run_one(args):
    name, seed = args
    warnings.simplefilter("ignore")
    x, y, z = scenario(name, seed)
    out = {}
    r = jnwb.granger(x, y, order="auto", max_lag=20, n_surrogates=N_SURR, rng=seed)
    out["granger"] = (r.p_x_to_y, r.p_y_to_x, r.net)
    r = jnwb.granger_spectral(x, y, fs=FS, order="auto", max_lag=20, n_surrogates=N_SURR, rng=seed)
    out["granger_spectral"] = (r.p_x_to_y, r.p_y_to_x, r.net)
    # PSI is one two-sided test; its direction is the sign of net (docstring). 39 Welch segments.
    r = jnwb.phase_slope_index(x, y, fs=FS, bands=(5.0, 100.0), nperseg=100, n_surrogates=N_SURR, rng=seed)
    out["phase_slope_index"] = (r.p_net if r.net > 0 else 1.0, r.p_net if r.net < 0 else 1.0, r.net)
    r = jnwb.transfer_entropy(x, y, k=1, l=1, delay=1, n_surrogates=N_SURR, rng=seed)
    out["transfer_entropy"] = (r.p_x_to_y, r.p_y_to_x, r.net)
    if z is not None:
        r = jnwb.granger(x, y, order="auto", max_lag=20, Z=z, n_surrogates=N_SURR, rng=seed)
        out["granger | Z"] = (r.p_x_to_y, r.p_y_to_x, r.net)
    return name, seed, out


# ---------------------------------------------------------------- part A
def part_a():
    text = (REPO / "docs" / "08_directed_connectivity_and_information.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```python\n(.*?)```", text, flags=re.S)
    ns: dict = {}
    rows = []
    for i, code in enumerate(blocks):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            t0 = time.perf_counter()
            try:
                exec(compile(code, f"docs08_block{i}", "exec"), ns)
                status = "ok"
            except Exception as exc:  # report, do not hide
                status = f"{type(exc).__name__}: {exc}"
            dt = time.perf_counter() - t0
        rows.append({"block": i, "status": status, "seconds": round(dt, 2),
                     "warnings": sorted({f"{x.category.__name__}: {str(x.message)[:120]}" for x in w})})
    facts = {
        "granger x_to_y": float(ns["result"].x_to_y), "granger p_x_to_y": float(ns["result"].p_x_to_y),
        "granger p_y_to_x": float(ns["result"].p_y_to_x),
        "psi x_to_y": float(ns["psi_res"].x_to_y), "te x_to_y bits": float(ns["te_res"].x_to_y),
        "te unit": ns["te_res"].unit, "mi_bin": float(ns["mi_bin"]), "mi_count": float(ns["mi_count"]),
        "network labels": list(ns["network"]["labels"]),
        "network matrix": np.round(ns["network"]["matrix"], 4).tolist(),
        "topology": {k: (v if not isinstance(v, np.ndarray) else v.tolist()) for k, v in ns["topo"].items()},
    }
    return rows, facts


# ---------------------------------------------------------------- part C
def part_c():
    res = []
    for seed in range(10):
        rng = np.random.default_rng(100 + seed)
        a = rng.normal(size=N); b = np.zeros(N); c = np.zeros(N); d = rng.normal(size=N)
        eb, ec = rng.normal(size=N), rng.normal(size=N)
        for t in range(1, N):
            b[t] = 0.5 * a[t - 1] + eb[t]
            c[t] = 0.5 * b[t - 1] + ec[t]
        net = jnwb.directed_network({"A": a, "B": b, "C": c, "D": d}, method="granger", order=2,
                                    fdr=True, n_surrogates=N_SURR, rng=seed)
        res.append(net)
    keys = sorted(res[0].keys())
    labels = list(res[0]["labels"])
    sig_key = next((k for k in ("significant", "sig", "significant_matrix") if k in res[0]), None)
    p_key = next((k for k in ("p_matrix", "pvalues", "p_values", "q_matrix", "q_values") if k in res[0]), None)
    edge_rate = None
    if sig_key or p_key:
        stack = np.array([(r[sig_key] if sig_key else (np.asarray(r[p_key]) < ALPHA)) for r in res], dtype=float)
        edge_rate = np.nanmean(stack, axis=0)
    topo = jnwb.network_topology(np.asarray(res[0]["matrix"]), threshold=0.05)
    return {"keys": keys, "labels": labels, "sig_key": sig_key, "p_key": p_key,
            "edge_rate": None if edge_rate is None else np.round(edge_rate, 2).tolist(),
            "matrix_seed0": np.round(np.asarray(res[0]["matrix"]), 4).tolist(),
            "topology_seed0_thr0.05": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in topo.items()}}


# ---------------------------------------------------------------- part D
def part_d():
    out = {"dependent": [], "independent": [], "symmetry_max_abs_diff": 0.0}
    for seed in range(20):
        rng = np.random.default_rng(200 + seed)
        s1 = np.sort(rng.uniform(0, 10, size=rng.poisson(200)))
        s2 = np.sort(np.clip(s1 + rng.normal(0, 0.002, size=s1.size), 0, 10))  # 2 ms jitter copy
        s3 = np.sort(rng.uniform(0, 10, size=rng.poisson(200)))
        kw = dict(time_window_s=(0.0, 10.0), bin_size_ms=10.0)
        dep = jnwb.spike_mutual_information(s1, s2, **kw)
        ind = jnwb.spike_mutual_information(s1, s3, **kw)
        rev = jnwb.spike_mutual_information(s2, s1, **kw)
        out["dependent"].append(dep); out["independent"].append(ind)
        out["symmetry_max_abs_diff"] = max(out["symmetry_max_abs_diff"], abs(dep - rev))
        out.setdefault("count_dependent", []).append(jnwb.spike_count_mutual_information(s1, s2, **kw))
        out.setdefault("count_independent", []).append(jnwb.spike_count_mutual_information(s1, s3, **kw))
    return {k: (float(np.mean(v)) if isinstance(v, list) else v) for k, v in out.items()} | {
        "dependent_min": float(np.min(out["dependent"])), "independent_max": float(np.max(out["independent"]))}


def main():
    head = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert Path(jnwb.__file__).resolve().is_relative_to(REPO), jnwb.__file__
    report = {"jnwb": jnwb.__file__, "version": jnwb.__version__, "commit": head,
              "N": N, "fs": FS, "seeds": N_SEEDS, "surrogates": N_SURR, "alpha": ALPHA}
    t0 = time.perf_counter()
    report["A_rows"], report["A_facts"] = part_a()
    print("part A", round(time.perf_counter() - t0, 1), "s", flush=True)

    jobs = [(name, s) for name in SCENARIOS for s in range(N_SEEDS)]
    t0 = time.perf_counter()
    with ProcessPoolExecutor(max_workers=20) as ex:
        results = list(ex.map(run_one, jobs))
    print("part B", round(time.perf_counter() - t0, 1), "s", flush=True)
    rates = {}
    for name in SCENARIOS:
        per = [o for n_, _, o in results if n_ == name]
        for est in per[0]:
            pxy = np.array([o[est][0] for o in per], dtype=float)
            pyx = np.array([o[est][1] for o in per], dtype=float)
            net = np.array([o[est][2] for o in per], dtype=float)
            rates.setdefault(name, {})[est] = {
                "rate_x_to_y": float(np.mean(pxy < ALPHA)), "rate_y_to_x": float(np.mean(pyx < ALPHA)),
                "median_net": float(np.median(net)), "nan_p": int(np.isnan(pxy).sum() + np.isnan(pyx).sum())}
    report["B_rates"] = rates
    report["B_expected"] = {k: list(v) for k, v in SCENARIOS.items()}

    t0 = time.perf_counter()
    report["C"] = part_c()
    report["D"] = part_d()
    print("parts C+D", round(time.perf_counter() - t0, 1), "s", flush=True)
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print("wrote", OUT / "report.json")


if __name__ == "__main__":
    main()
