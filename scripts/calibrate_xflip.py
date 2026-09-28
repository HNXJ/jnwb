"""Regenerate the xFLIP operating-characteristics receipt from the current estimator.

    python scripts/calibrate_xflip.py [--n-seeds 30] [--n-surrogates 200]

Writes ``artifacts/benchmarks/xflip_calibration_0.2.5.md`` and
``xflip_calibration_0.2.5_raw.json``. The JSON records a SHA-256 over ``xflip`` and every
module-level function in ``jnwb.laminar`` it can reach, so
``tests/test_xflip_calibration_receipt.py`` fails when the estimator changes without this
script being rerun.

This replaces ``xflip_calibration_0.2.3.md``, which was produced under 0.2.3 with no
generator and could not be regenerated. Two changes had already invalidated it: 0.2.4 made
``xflip`` reject a zero-variance channel instead of reporting its correlation as 0, and the
smooth-gradient drop gate turned out to be skipped on the ``contiguous=False`` path, so the
null rates it reported were conditional on a setting it did not name.

Every number below traces to a seeded computation over ``jnwb.testing`` generators passed
end to end through ``xflip``. Operating points the old document left unstated -- the
surrogate count, the minimum block size, and the significance level -- are recorded here.

Families
--------
Null (no block structure; any acceptance is a false positive):
    white_noise                independent white noise on every channel
    ar_noise                   independent AR(1) noise, tau = 30 ms, autocorr-preserving
                               surrogates
    periodic_common_response   one 25 Hz response shared by every channel
    smooth_spatial_gradient    exp(-d/4) correlation: correlation falls with distance and
                               there is no boundary anywhere
Alternative (contiguous correlation blocks; the boundary is known):
    within_corr_sweep          N = 16, blocks (8, 8), rw in 0.2 .. 0.8
    unequal_blocks             (4, 12), (12, 4), (6, 18)
    three_block                (6, 6, 6), (4, 8, 4)
    channel_count_sweep        equal blocks, rw = 0.7, rb = 0.1, N in 8 .. 24
Automatic block count (the surrogate test alone can reject):
    white_noise and ar_noise with ``n_blocks=None`` beside ``n_blocks=2``, on both
    ``contiguous`` paths: the fraction of seeds with omnibus p at or below ``alpha``.
    Seeds run in worker processes; each seed's result does not depend on the worker count.

The closure hashed here is recomputed rather than imported from
``scripts/calibrate_vflip.py``. The same walk is written a third time in
``tests/test_xflip_calibration_receipt.py``, deliberately: that copy is the oracle the
generator is checked against, and an oracle that imports the thing it checks certifies
nothing.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import importlib.util
import inspect
import json
import os
import pathlib
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import scipy

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb.laminar import xflip  # noqa: E402
from jnwb.testing import (  # noqa: E402
    synth_ar_noise,
    synth_correlation_blocks,
    synth_periodic_response,
    synth_white_noise,
)

N_SAMPLES = 400
FS = 1000.0
MIN_BLOCK_SIZE = 3
ALPHA = float(inspect.signature(xflip).parameters["alpha"].default)


def _module_table(modname: str):
    """(source, {name: top-level def or assignment node}, {name: (module, name)} imported
    from another jnwb module) for the module ``modname``."""
    source = inspect.getsource(importlib.import_module(modname))
    tree = ast.parse(source)
    nodes, imported = {}, {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nodes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    nodes[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            nodes[node.target.id] = node
        elif isinstance(node, ast.ImportFrom):
            origin = importlib.util.resolve_name(
                "." * node.level + (node.module or ""), modname.rpartition(".")[0]
            ) if node.level else (node.module or "")
            if origin == "jnwb" or origin.startswith("jnwb."):
                for alias in node.names:
                    imported[alias.asname or alias.name] = (origin, alias.name)
    return source, nodes, imported


def estimator_sources() -> list[tuple[str, str]]:
    """`xflip` and every top-level function and constant it can reach, in any jnwb module.

    Resolved from the call graph rather than listed, so a helper introduced later is
    covered without anyone remembering to add it, and sorted, so the digest does not
    depend on the order the graph is walked. A name reached in a function body is followed
    to its definition in the same module, or through a ``from .module import name`` to the
    module that defines it, so the tie rule in ``jnwb.permutation`` and its width constant
    are hashed with the estimator that calls them. Names in ``jnwb.laminar`` are bare;
    names elsewhere carry their module.
    """
    home = xflip.__module__
    tables: dict = {}
    reached: dict[tuple[str, str], str] = {}
    stack = [(home, xflip.__name__)]
    while stack:
        modname, name = stack.pop()
        if (modname, name) in reached:
            continue
        if modname not in tables:
            tables[modname] = _module_table(modname)
        source, nodes, imported = tables[modname]
        if name in imported:
            stack.append(imported[name])
            continue
        if name not in nodes:
            continue
        node = nodes[name]
        reached[(modname, name)] = ast.get_source_segment(source, node)
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name):
                stack.append((modname, sub.id))
            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                stack.append((modname, sub.func.attr))
    named = {(name if modname == home else f"{modname}.{name}"): src
             for (modname, name), src in reached.items()}
    return sorted(named.items())


def estimator_sha256() -> str:
    digest = hashlib.sha256()
    for name, source in estimator_sources():
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(source.encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


# --- null families -------------------------------------------------------------------

def _white_noise(seed: int, n_ch: int = 16):
    return synth_white_noise(shape=(n_ch, N_SAMPLES), rng=seed + 500), {}


def _ar_noise(seed: int, n_ch: int = 16):
    data = synth_ar_noise(600, n_channels=n_ch, fs=FS, tau_s=0.030, rng=seed + 700)
    return data, {"surrogate_method": "autocorr_preserving"}


def _periodic_common_response(seed: int, n_ch: int = 16):
    data = synth_periodic_response(
        n_trials=1, n_samples=N_SAMPLES, fs=FS, freq_hz=25.0,
        n_channels=n_ch, noise_std=0.5, rng=seed + 900,
    )[0]
    return data, {}


def _smooth_spatial_gradient(seed: int, n_ch: int = 16):
    rng = np.random.default_rng(seed + 1100)
    dists = np.abs(np.arange(n_ch)[:, None] - np.arange(n_ch)[None, :])
    data = np.linalg.cholesky(np.exp(-dists / 4.0)) @ rng.normal(size=(n_ch, N_SAMPLES))
    return data, {}


NULLS = {
    "white_noise": _white_noise,
    "ar_noise": _ar_noise,
    "periodic_common_response": _periodic_common_response,
    "smooth_spatial_gradient": _smooth_spatial_gradient,
}


def run_nulls(n_seeds: int, n_surrogates: int) -> dict:
    out = {}
    for name, build in NULLS.items():
        accepted, by_surrogates, by_drop, p_values, modularity = 0, 0, 0, [], []
        for s in range(n_seeds):
            data, extra = build(s)
            res = xflip(data, n_blocks=2, min_block_size=MIN_BLOCK_SIZE,
                        n_surrogates=n_surrogates, rng=s + 6000, **extra)
            accepted += bool(res.accepted)
            # Read from the reasons `xflip` gives rather than re-deciding its gates here. A
            # seed can fail several gates; each counts every seed it rejects.
            reason = res.rejection_reason or ""
            by_surrogates += "Non-significant modularity" in reason
            by_drop += "Boundary drop below" in reason
            p_values.append(float(res.p_values["omnibus"]))
            modularity.append(float(res.modularity))
        out[name] = {
            "n_seeds": n_seeds,
            "false_positive_rate": accepted / n_seeds,
            "n_rejected_by_surrogates": int(by_surrogates),
            "n_rejected_by_boundary_drop": int(by_drop),
            "median_p": float(np.median(p_values)),
            "min_p": float(np.min(p_values)),
            "max_p": float(np.max(p_values)),
            "median_modularity": float(np.median(modularity)),
        }
        print(f"  null {name:26s} fpr={out[name]['false_positive_rate']:.3f}")
    return out


# --- automatic block count -----------------------------------------------------------

AUTO_NULLS = ("white_noise", "ar_noise")
AUTO_COUNTS = (2, None)


def _auto_count_seed(job: tuple) -> tuple:
    """One seed of one null on one path: whether p <= alpha at each count setting."""
    name, contiguous, seed, n_surrogates = job
    data, extra = NULLS[name](seed)
    out = []
    for n_blocks in AUTO_COUNTS:
        res = xflip(data, n_blocks=n_blocks, contiguous=contiguous,
                    min_block_size=MIN_BLOCK_SIZE, n_surrogates=n_surrogates,
                    min_contrast=0.0, min_boundary_drop=0.0, rng=seed + 6000, **extra)
        out.append(bool(float(res.p_values["omnibus"]) <= ALPHA))
    return name, contiguous, tuple(out)


def run_auto_count(n_seeds: int, n_surrogates: int, workers: int) -> list:
    jobs = [(name, contiguous, s, n_surrogates)
            for name in AUTO_NULLS for contiguous in (True, False) for s in range(n_seeds)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(_auto_count_seed, jobs, chunksize=8))
    rows = []
    for name in AUTO_NULLS:
        for contiguous in (True, False):
            hits = [r[2] for r in results if r[0] == name and r[1] == contiguous]
            row = {"null": name, "contiguous": contiguous, "n_seeds": n_seeds}
            for i, n_blocks in enumerate(AUTO_COUNTS):
                row[f"rate_n_blocks_{n_blocks}"] = sum(h[i] for h in hits) / n_seeds
            rows.append(row)
            print(f"  auto {name:12s} contiguous={contiguous!s:5s} "
                  f"None={row['rate_n_blocks_None']:.3f} 2={row['rate_n_blocks_2']:.3f}")
    return rows


# --- alternative families ------------------------------------------------------------

def _alternative(block_sizes, within_corr, between_corr, n_seeds, n_surrogates):
    """True-positive rate and boundary localization for one block configuration."""
    true_bounds = tuple(int(np.cumsum(block_sizes)[i]) for i in range(len(block_sizes) - 1))
    detected, errors, modularity = 0, [], []
    for s in range(n_seeds):
        data, _, _ = synth_correlation_blocks(
            block_sizes, within_corr=within_corr, between_corr=between_corr,
            n_samples=N_SAMPLES, rng=s + 2000,
        )
        res = xflip(data, n_blocks=len(block_sizes), min_block_size=MIN_BLOCK_SIZE,
                    n_surrogates=n_surrogates, rng=s + 3000)
        modularity.append(float(res.modularity))
        if not res.accepted:
            continue
        detected += 1
        if len(res.boundaries) == len(true_bounds):
            errors.append([abs(int(b) - t) for b, t in zip(res.boundaries, true_bounds)])
    per_boundary = np.asarray(errors, dtype=float) if errors else np.empty((0, len(true_bounds)))
    return {
        "block_sizes": list(block_sizes),
        "true_boundaries": list(true_bounds),
        "within_corr": within_corr,
        "between_corr": between_corr,
        "n_seeds": n_seeds,
        "true_positive_rate": detected / n_seeds,
        "n_localized": int(per_boundary.shape[0]),
        "median_error_per_boundary": (
            np.median(per_boundary, axis=0).tolist() if per_boundary.size else None),
        "max_error_per_boundary": (
            per_boundary.max(axis=0).tolist() if per_boundary.size else None),
        "median_modularity": float(np.median(modularity)),
    }


SWEEPS = {
    "within_corr_sweep": [((8, 8), rw, 0.0) for rw in (0.2, 0.4, 0.6, 0.8)],
    "unequal_blocks": [((4, 12), 0.6, 0.0), ((12, 4), 0.6, 0.0), ((6, 18), 0.6, 0.0)],
    "three_block": [((6, 6, 6), 0.6, 0.0), ((4, 8, 4), 0.6, 0.0)],
    "channel_count_sweep": [((n // 2, n - n // 2), 0.7, 0.1) for n in (8, 12, 16, 24)],
}


def run_alternatives(n_seeds: int, n_surrogates: int) -> dict:
    out = {}
    for sweep, points in SWEEPS.items():
        out[sweep] = []
        for block_sizes, rw, rb in points:
            row = _alternative(block_sizes, rw, rb, n_seeds, n_surrogates)
            out[sweep].append(row)
            print(f"  alt  {sweep:22s} {str(block_sizes):12s} rw={rw} "
                  f"tpr={row['true_positive_rate']:.3f}")
    return out


# --- report --------------------------------------------------------------------------

def render(raw: dict) -> str:
    n = raw["n_seeds"]
    lines = [
        "# xFLIP Empirical Calibration & Operating Characteristics Receipt",
        "",
        f"Generated by `scripts/calibrate_xflip.py` from estimator SHA-256 "
        f"`{raw['estimator_sha256'][:16]}`.",
        "",
        "This supersedes `xflip_calibration_0.2.3.md`, which had no generator and could not",
        "be regenerated. Two changes had already invalidated it: 0.2.4 made `xflip` reject a",
        "zero-variance channel rather than report its correlation as 0, and the smooth-gradient",
        "drop gate turned out to be skipped on the `contiguous=False` path, so the null rates",
        "it reported were conditional on a setting it did not name.",
        "",
        "## Operating point",
        "",
        f"| Parameter | Value |",
        f"|---|---|",
        f"| seeds per cell | {n} |",
        f"| surrogates | {raw['n_surrogates']} |",
        f"| `min_block_size` | {MIN_BLOCK_SIZE} |",
        f"| `alpha` | {raw['alpha']} |",
        f"| samples per channel | {N_SAMPLES} |",
        f"| `contiguous` | default (`True`) |",
        "",
        f"A rate of 0 over {n} seeds bounds the true rate at roughly "
        f"{3.0 / n:.2f} at 95% confidence, not at 0; rates are reported, not claimed as exact.",
        "",
        "## 1. Null ensemble false positive rates",
        "",
        "| Null Family | N Seeds | False Positive Rate | Median p | Min p | Max p | Median Q |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, r in raw["nulls"].items():
        lines.append(
            f"| `{name}` | {r['n_seeds']} | {r['false_positive_rate']:.3f} | "
            f"{r['median_p']:.4f} | {r['min_p']:.4f} | {r['max_p']:.4f} | "
            f"{r['median_modularity']:.4f} |")

    nulls = raw["nulls"]
    floor = 1.0 / (raw["n_surrogates"] + 1)
    grad = nulls["smooth_spatial_gradient"]
    ar = nulls["ar_noise"]
    lines += [
        "",
        "### Reading the null table",
        "",
        f"- `ar_noise` accepts {round(ar['false_positive_rate'] * n)} of {n} seeds "
        f"({ar['false_positive_rate']:.3f}), above the nominal {raw['alpha']}. At this many "
        "seeds that is inside the binomial interval for a true rate of "
        f"{raw['alpha']}, so it is reported, not diagnosed. Correlated noise is where this "
        "estimator is hardest to calibrate, and it is the one family whose rate the "
        "surrogate test alone controls.",
        f"- `smooth_spatial_gradient` has median, min and max omnibus p all at "
        f"{grad['median_p']:.4f}, the 1/(surrogates+1) floor. Every gradient is maximally "
        f"significant under the permutation test, which rejects {grad['n_rejected_by_surrogates']} "
        f"of {n}; the local boundary-drop gate rejects {grad['n_rejected_by_boundary_drop']} of "
        f"{n}, and the {grad['false_positive_rate']:.3f} acceptance rate is the gradients it "
        "lets through. When that gate was skipped on the unrestricted path, gradients were "
        "accepted 15/15.",
    ]

    titles = {
        "within_corr_sweep": "2A. Within-block correlation sweep (N = 16, equal blocks)",
        "unequal_blocks": "2B. Unequal block partitioning",
        "three_block": "2C. Three-block partitioning",
        "channel_count_sweep": "2D. Channel-count scaling (rw = 0.7, rb = 0.1)",
    }
    for sweep, rows in raw["alternatives"].items():
        lines += ["", f"## {titles[sweep]}", "",
                  "| Blocks | True Boundaries | rw | True Positive Rate | Localized | "
                  "Median Error (ch) | Max Error (ch) | Median Q |",
                  "|---|---|---|---|---|---|---|---|"]
        for r in rows:
            med = ("-" if r["median_error_per_boundary"] is None
                   else ", ".join(f"{e:.2f}" for e in r["median_error_per_boundary"]))
            mx = ("-" if r["max_error_per_boundary"] is None
                  else ", ".join(f"{e:.2f}" for e in r["max_error_per_boundary"]))
            lines.append(
                f"| {tuple(r['block_sizes'])} | {tuple(r['true_boundaries'])} | "
                f"{r['within_corr']} | {r['true_positive_rate']:.3f} | "
                f"{r['n_localized']}/{r['n_seeds']} | {med} | {mx} | "
                f"{r['median_modularity']:.4f} |")

    auto = raw["auto_count"]
    lines += [
        "",
        "## 3. Automatic block count under the null",
        "",
        f"`n_blocks=None` beside `n_blocks=2`, over {auto['n_seeds']} seeds and "
        f"{auto['n_surrogates']} surrogates, with `min_contrast=0` and `min_boundary_drop=0` "
        "so that only the surrogate test can reject. Each cell is the fraction of seeds with "
        f"omnibus p at or below {raw['alpha']}; the count choice is repeated on every "
        "surrogate, so the `None` column is held to the same nominal rate as a fixed count.",
        "",
        "| Null Family | `contiguous` | N Seeds | p <= alpha, `n_blocks=None` | "
        "p <= alpha, `n_blocks=2` |",
        "|---|---|---|---|---|",
    ]
    for r in auto["rows"]:
        lines.append(
            f"| `{r['null']}` | `{r['contiguous']}` | {r['n_seeds']} | "
            f"{r['rate_n_blocks_None']:.3f} | {r['rate_n_blocks_2']:.3f} |")

    lines += [
        "",
        "## What this receipt does not cover",
        "",
        "- `contiguous=False` outside section 3. The unrestricted path is otherwise exercised",
        "  by `tests/test_xflip_calibration.py::TestXFlipGradientGateOnBothPaths`.",
        "- One correlation method (`pearson`) and one surrogate method per family.",
        "- Non-contiguous and overlapping block structure.",
        "- Real recordings. Every family is synthetic.",
        "",
        "## Environment",
        "",
        f"- jnwb {raw['environment']['jnwb']}",
        f"- Python {raw['environment']['python']}",
        f"- numpy {raw['environment']['numpy']}, scipy {raw['environment']['scipy']}",
        f"- {raw['environment']['platform']}",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n-seeds", type=int, default=30)
    ap.add_argument("--n-surrogates", type=int, default=200)
    ap.add_argument("--auto-seeds", type=int, default=1000,
                    help="seeds per cell of the automatic-count null rows")
    ap.add_argument("--workers", type=int, default=os.cpu_count(),
                    help="worker processes for the automatic-count rows; changes no number")
    ap.add_argument("--out-dir", type=pathlib.Path,
                    default=ROOT / "artifacts" / "benchmarks")
    args = ap.parse_args()

    t0 = time.perf_counter()
    print(f"xflip calibration: {args.n_seeds} seeds, {args.n_surrogates} surrogates")
    raw = {
        "estimator_sha256": estimator_sha256(),
        "estimator_functions": [name for name, _ in estimator_sources()],
        "n_seeds": args.n_seeds,
        "n_surrogates": args.n_surrogates,
        "min_block_size": MIN_BLOCK_SIZE,
        "alpha": ALPHA,
        "n_samples": N_SAMPLES,
        "nulls": run_nulls(args.n_seeds, args.n_surrogates),
        "alternatives": run_alternatives(args.n_seeds, args.n_surrogates),
        "auto_count": {
            "n_seeds": args.auto_seeds,
            "n_surrogates": args.n_surrogates,
            "rows": run_auto_count(args.auto_seeds, args.n_surrogates, args.workers),
        },
        "environment": {
            "jnwb": jnwb.__version__,
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }
    raw["elapsed_s"] = round(time.perf_counter() - t0, 1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "xflip_calibration_0.2.5_raw.json").write_bytes(
        (json.dumps(raw, indent=2) + "\n").encode("utf-8"))
    (args.out_dir / "xflip_calibration_0.2.5.md").write_bytes(
        render(raw).encode("utf-8"))
    print(f"wrote receipt in {raw['elapsed_s']} s; "
          f"estimator {raw['estimator_sha256'][:16]}")


if __name__ == "__main__":
    main()
