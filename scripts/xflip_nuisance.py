"""xFLIP's null under nuisance structure: false-positive rates and planted-block recovery.

    python scripts/xflip_nuisance.py [--n 100] [--n-surrogates 200] [--smoke | --write]

Null cells carry no block structure, so an omnibus p at or below alpha is a false positive.
Planted cells add the receipt's (8, 8) correlation blocks to one nuisance, each at unit mean
power per contact (signal to nuisance ratio 1), and count a seed as recovered when ``xflip``
accepts and places its one boundary at contact 8 (exact) or within one contact.

Every cell runs ``xflip`` on the same data at ``n_blocks=None`` and at ``n_blocks=2``, with the
0.2.5 receipt's channel count, sample count, sampling rate, minimum block size, alpha and seed
rule (``scripts/calibrate_xflip.py``). Each rate carries an exact 95% Clopper-Pearson interval
from ``jnwb.clopper_pearson``. The length-4 Toeplitz null draws what the receipt's smooth-gradient
cell draws; ``--write`` checks that on the receipt's 30 seeds.

``--smoke`` runs three seeds per cell and prints only. ``--write`` also writes
``artifacts/evidence/0.2.13/xflip_nuisance.md`` and ``xflip_nuisance.json`` (every seed).
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import platform
import sys
import time
from functools import partial

import numpy as np
import scipy

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb.laminar import xflip  # noqa: E402
from jnwb.testing import synth_ar_noise, synth_correlation_blocks, synth_white_noise  # noqa: E402
from scripts import calibrate_xflip as receipt  # noqa: E402

N_CONTACTS = 16
N_SAMPLES = receipt.N_SAMPLES
FS = receipt.FS
MIN_BLOCK_SIZE = receipt.MIN_BLOCK_SIZE
ALPHA = receipt.ALPHA
#: The 0.2.5 receipt's surrogate count (``n_surrogates`` in its raw JSON).
N_SURROGATES = 200
#: Two-sided level of the Clopper-Pearson intervals (95%).
CI_ALPHA = 0.05
#: Block-count settings, keyed as the receipt names its automatic-count columns.
BLOCK_COUNTS = {"n_blocks_None": None, "n_blocks_2": 2}
#: Seed offsets: the receipt's null rule for xflip, and its alternative rule for planted blocks.
NULL_RNG, PLANTED_RNG = 6000, 3000
#: Planted blocks: the receipt's (8, 8) generator; the boundary sits before contact 8.
PLANTED_BLOCKS = (8, 8)
PLANTED_WITHIN, PLANTED_BETWEEN = 0.5, 0.1
PLANTED_BOUNDARY = PLANTED_BLOCKS[0]
RECEIPT_RAW = ROOT / "artifacts" / "benchmarks" / "calibration" / "xflip_calibration_0.2.5_raw.json"
OUT_DIR = ROOT / "artifacts" / "evidence" / "0.2.13"


# --- scaling and null families -------------------------------------------------------

def _unit_power(x):
    """``x`` times one positive factor, so the mean per-contact sample variance is 1. One factor
    for the whole array keeps every correlation and the ratio of the contacts' powers."""
    return x / math.sqrt(float(np.mean(np.var(x, axis=1))))


def toeplitz_null(seed, length):
    """Gaussian contacts with correlation exp(-d / length), d the distance in contacts.

    The draws follow the receipt's smooth-gradient generator, which is this function at 4.0.
    """
    rng = np.random.default_rng(seed + 1100)
    dists = np.abs(np.arange(N_CONTACTS)[:, None] - np.arange(N_CONTACTS)[None, :])
    return np.linalg.cholesky(np.exp(-dists / length)) @ rng.normal(size=(N_CONTACTS, N_SAMPLES))


def _heterogeneous_parts(seed, sigma):
    """Per-contact standard deviations, and the unit white draws they scale."""
    rng = np.random.default_rng(seed + 1300)
    sd = np.exp(sigma * rng.normal(size=N_CONTACTS))
    return sd, synth_white_noise((N_CONTACTS, N_SAMPLES), rng=rng)


def heterogeneous_null(seed, sigma):
    """White contacts whose standard deviations are lognormal with log-SD ``sigma``."""
    sd, white = _heterogeneous_parts(seed, sigma)
    return sd[:, None] * white


def common_reference_null(seed, ratio):
    """One AR(1) signal (tau 30 ms) shared by every contact, at variance ``ratio`` to each
    contact's own AR(1) noise. Both components are scaled to unit sample variance first."""
    rng = np.random.default_rng(seed + 1500)
    shared = synth_ar_noise(N_SAMPLES, n_channels=1, fs=FS, tau_s=0.030, rng=rng)
    own = synth_ar_noise(N_SAMPLES, n_channels=N_CONTACTS, fs=FS, tau_s=0.030, rng=rng)
    shared = shared / shared.std()
    own = own / own.std(axis=1, keepdims=True)
    return math.sqrt(ratio) * shared[None, :] + own


def _white_draws(seed):
    """The receipt's white-noise cell (seed rule +500)."""
    data, _ = receipt._white_noise(seed)
    return data


def average_reference_null(seed):
    """The receipt's white-noise cell, re-referenced to its channel average."""
    data = _white_draws(seed)
    return data - data.mean(axis=0, keepdims=True)


# --- planted cells -------------------------------------------------------------------

def _planted_blocks(seed):
    """The receipt's correlation blocks at unit mean power per contact (seed rule +2000)."""
    data, _, _ = synth_correlation_blocks(PLANTED_BLOCKS, within_corr=PLANTED_WITHIN,
                                          between_corr=PLANTED_BETWEEN, n_samples=N_SAMPLES,
                                          rng=seed + 2000)
    return _unit_power(data)


def planted_toeplitz(seed, length):
    """Planted blocks plus the Toeplitz null at ``length``, each at unit mean power."""
    return _planted_blocks(seed) + _unit_power(toeplitz_null(seed, length))


def planted_heterogeneous(seed, sigma):
    """Planted blocks plus the heterogeneous null at ``sigma``, each at unit mean power."""
    return _planted_blocks(seed) + _unit_power(heterogeneous_null(seed, sigma))


def planted_common_reference(seed, ratio):
    """Planted blocks plus the common-reference null at ``ratio``, each at unit mean power."""
    return _planted_blocks(seed) + _unit_power(common_reference_null(seed, ratio))


def planted_average_reference(seed):
    """Planted blocks plus white noise at unit power, re-referenced to the channel average."""
    summed = _planted_blocks(seed) + _unit_power(_white_draws(seed))
    return summed - summed.mean(axis=0, keepdims=True)


#: (family, parameter name, parameter value, surrogate method, builder), in run order. The method
#: is ``auto`` (xflip's default) except for the AR(1)-noise cells, which use ``autocorr_preserving``
#: as the receipt's AR row does.
NULL_CELLS = (
    [("smooth_toeplitz", "L", length, "auto", partial(toeplitz_null, length=length))
     for length in (1.0, 2.0, 4.0, 8.0)]
    + [("heterogeneous_noise", "sigma", sigma, "auto", partial(heterogeneous_null, sigma=sigma))
       for sigma in (0.5, 1.0)]
    + [("common_reference", "ratio", ratio, "autocorr_preserving",
        partial(common_reference_null, ratio=ratio)) for ratio in (0.5, 1.0, 2.0)]
    + [("average_reference", None, None, "auto", average_reference_null)]
)
PLANTED_CELLS = (
    [("smooth_toeplitz", "L", 4.0, "auto", partial(planted_toeplitz, length=4.0))]
    + [("heterogeneous_noise", "sigma", 0.5, "auto", partial(planted_heterogeneous, sigma=0.5))]
    + [("common_reference", "ratio", 1.0, "autocorr_preserving",
        partial(planted_common_reference, ratio=1.0))]
    + [("average_reference", None, None, "auto", planted_average_reference)]
)


# --- runs and summaries --------------------------------------------------------------

def run_cell(build, n_seeds, n_surrogates, method="auto", rng_offset=NULL_RNG):
    """Every seed of one cell at each block count: the omnibus p, the accepted flag, the reason
    ``xflip`` gives for a rejection, the modularity and the boundaries it reports."""
    rows = []
    for seed in range(n_seeds):
        data = build(seed)
        row = {"seed": seed}
        for key, n_blocks in BLOCK_COUNTS.items():
            res = xflip(data, n_blocks=n_blocks, min_block_size=MIN_BLOCK_SIZE,
                        n_surrogates=n_surrogates, surrogate_method=method,
                        rng=seed + rng_offset)
            row[key] = {
                "p_omnibus": float(res.p_values["omnibus"]),
                "accepted": bool(res.accepted),
                "rejection_reason": res.rejection_reason,
                "modularity": float(res.modularity),
                "boundaries": [int(b) for b in res.boundaries],
            }
        rows.append(row)
    return rows


def _rate(k, n):
    """``k`` of ``n`` with the exact Clopper-Pearson interval at ``CI_ALPHA``."""
    low, high = jnwb.clopper_pearson(k, n, alpha=CI_ALPHA)
    return {"k": int(k), "n": int(n), "rate": k / n, "ci": [float(low), float(high)]}


def null_summary(rows, key):
    """False positives by omnibus p at or below alpha, and by the accepted flag."""
    n = len(rows)
    return {
        "p_le_alpha": _rate(sum(row[key]["p_omnibus"] <= ALPHA for row in rows), n),
        "accepted": _rate(sum(row[key]["accepted"] for row in rows), n),
    }


def planted_summary(rows, key):
    """Accepted; exact (accepted with one boundary at contact 8); within one contact of it."""
    def recovered(row, tolerance):
        cell = row[key]
        return (cell["accepted"] and len(cell["boundaries"]) == 1
                and abs(cell["boundaries"][0] - PLANTED_BOUNDARY) <= tolerance)

    n = len(rows)
    return {
        "accepted": _rate(sum(row[key]["accepted"] for row in rows), n),
        "exact": _rate(sum(recovered(row, 0) for row in rows), n),
        "within_one": _rate(sum(recovered(row, 1) for row in rows), n),
    }


def design_checks(n_seeds=3, n_surrogates=N_SURROGATES):
    """The two facts the design section states, each computed on the seeds it reports."""
    kw = dict(min_block_size=MIN_BLOCK_SIZE, n_surrogates=n_surrogates)
    scaling = []
    for sigma in (0.5, 1.0):
        for seed in range(n_seeds):
            sd, white = _heterogeneous_parts(seed, sigma)
            plain = xflip(white, n_blocks=2, rng=seed + NULL_RNG, **kw)
            scaled = xflip(sd[:, None] * white, n_blocks=2, rng=seed + NULL_RNG, **kw)
            scaling.append({"sigma": sigma, "seed": seed,
                            "p_unscaled": float(plain.p_values["omnibus"]),
                            "p_scaled": float(scaled.p_values["omnibus"])})
    gates = []
    for seed in range(n_seeds):
        data = toeplitz_null(seed, 4.0)
        for key, n_blocks in BLOCK_COUNTS.items():
            default = xflip(data, n_blocks=n_blocks, rng=seed + NULL_RNG, **kw)
            zeroed = xflip(data, n_blocks=n_blocks, rng=seed + NULL_RNG,
                           min_contrast=0.0, min_boundary_drop=0.0, **kw)
            gates.append({"seed": seed, "count": key,
                          "p_default": float(default.p_values["omnibus"]),
                          "p_zeroed": float(zeroed.p_values["omnibus"])})
    return {
        "scaling": {"n_seeds": n_seeds, "sigmas": [0.5, 1.0],
                    "max_abs_diff": max(abs(r["p_unscaled"] - r["p_scaled"]) for r in scaling),
                    "pairs": scaling},
        "gates": {"n_seeds": n_seeds,
                  "identical": all(r["p_default"] == r["p_zeroed"] for r in gates),
                  "pairs": gates},
    }


def reproduction(rows, n_surrogates):
    """The length-4 null cell over the receipt's first seeds, against the receipt's raw values."""
    raw = json.loads(RECEIPT_RAW.read_text(encoding="utf-8"))
    rec = raw["nulls"]["smooth_spatial_gradient"]
    n = rec["n_seeds"]
    if len(rows) < n or n_surrogates != raw["n_surrogates"]:
        return {"run": False,
                "reason": f"needs at least {n} seeds at {raw['n_surrogates']} surrogates"}
    part, key = rows[:n], "n_blocks_2"
    p = np.array([row[key]["p_omnibus"] for row in part])
    reasons = [row[key]["rejection_reason"] or "" for row in part]
    mine = {
        "false_positive_rate": sum(row[key]["accepted"] for row in part) / n,
        "n_rejected_by_surrogates": sum("Non-significant modularity" in r for r in reasons),
        "n_rejected_by_boundary_drop": sum("Boundary drop below" in r for r in reasons),
        "median_p": float(np.median(p)),
        "min_p": float(np.min(p)),
        "max_p": float(np.max(p)),
        "median_modularity": float(np.median([row[key]["modularity"] for row in part])),
    }
    theirs = {name: rec[name] for name in mine}
    return {"run": True, "n_seeds": n, "mine": mine, "receipt": theirs,
            "equal": all(mine[name] == theirs[name] for name in mine)}


# --- output --------------------------------------------------------------------------

def _label(family, name, value):
    return family if name is None else f"{family} {name}={value:g}"


def _parameter(cell):
    return "-" if cell["parameter"] is None else f"{cell['parameter']} = {cell['value']:g}"


def _method(name):
    return "default (auto)" if name == "auto" else name


def _fmt(entry):
    return f"{entry['k']:3d}/{entry['n']:<4d}[{entry['ci'][0]:.3f}, {entry['ci'][1]:.3f}]"


def _cell(entry):
    return f"{entry['k']}/{entry['n']} [{entry['ci'][0]:.3f}, {entry['ci'][1]:.3f}]"


def render(record):
    """The receipt's Markdown, read from the record that the JSON file holds."""
    op, checks, repro = record["operating_point"], record["design_checks"], record["reproduction"]
    scaling, gates = checks["scaling"], checks["gates"]
    sigmas = ", ".join(f"{s:g}" for s in scaling["sigmas"])
    if scaling["max_abs_diff"] == 0:
        scaling_note = "So a heterogeneity cell tests the same null as white noise."
    else:
        scaling_note = "So the heterogeneity cells do not reduce to the white-noise null."
    null_families = {}
    for cell in record["null_cells"]:
        null_families.setdefault(cell["family"], []).append(cell)

    lines = [
        "# xFLIP null under nuisance structure",
        "",
        "Generated by `scripts/xflip_nuisance.py --write` from estimator SHA-256 "
        f"`{record['estimator_sha256'][:16]}`. Every number is read from "
        "`artifacts/evidence/0.2.13/xflip_nuisance.json`; each table names its key path.",
        "",
        "## Design",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| contacts | {op['n_contacts']} |",
        f"| samples per contact | {op['n_samples']} at {op['fs']:g} Hz, the receipt's operating point |",
        f"| seeds per cell | {op['n_seeds']} |",
        f"| surrogates | {op['n_surrogates']}, the 0.2.5 receipt's |",
        f"| min_block_size, alpha | {op['min_block_size']}, {op['alpha']} |",
        "| block counts | `n_blocks=None` and `n_blocks=2`, on every cell |",
        "| gates | defaults: min_contrast 0.05, min_boundary_drop 0.05 |",
        f"| intervals | `jnwb.clopper_pearson`, exact, two-sided, "
        f"{1 - op['ci']['alpha']:.0%} |",
        "| seed rule | null: +1100 Toeplitz, +1300 heterogeneous, +1500 common reference, "
        "+500 white (average reference); planted blocks +2000; xflip +6000 null, +3000 planted |",
        f"| signal to nuisance ratio (SNR), planted cells | {op['planted']['snr']:g}: each "
        "component at unit mean power per contact |",
        f"| planted blocks | {op['planted']['blocks']} contacts, within "
        f"{op['planted']['within_corr']}, between {op['planted']['between_corr']}, boundary "
        f"before contact {op['planted']['boundary']} |",
        "",
        "Statements:",
        "",
        "- Null cells have no block structure, so a false positive is an omnibus p at or below "
        "alpha. The `accepted` flag, which also needs the default gates, is reported beside it.",
        "- Planted cells add the receipt's correlation blocks to the nuisance at its middle "
        "value. Each component is scaled by one positive factor to unit mean power per contact, "
        "so correlations and the contacts' relative powers are kept. The average-reference cell "
        "sums white noise with the blocks and re-references the sum to its channel average.",
        "- Exact recovery means accepted with one boundary at contact 8. Within one contact "
        "means accepted with one boundary at contact 7, 8 or 9.",
        "- Surrogates: `autocorr_preserving` for the AR(1)-noise cells (common reference, null "
        "and planted); xflip's default `auto` (homogeneous) for the others. Each table gives "
        "the method.",
        "- The new cells draw 400 samples. The 0.2.5 receipt's `ar_noise` row draws 600 "
        "(`scripts/calibrate_xflip.py:238`) while its operating point says 400. The receipt is "
        "unchanged.",
        f"- Per-channel scaling leaves the omnibus p unchanged: max absolute difference "
        f"{scaling['max_abs_diff']:g} over {len(scaling['pairs'])} pairs (sigma {sigmas}, seeds "
        f"0 to {scaling['n_seeds'] - 1}; `design_checks.scaling`). {scaling_note}",
        f"- The gates do not move the omnibus p. With min_contrast and min_boundary_drop at 0, "
        f"p is identical in every pair: identical = {gates['identical']} over "
        f"{len(gates['pairs'])} pairs (`design_checks.gates`). The gates enter after p.",
        "",
        "## Null cells",
        "",
    ]
    for family, cells in null_families.items():
        lines += [
            f"### {family}",
            "",
            "Source: `null_cells`, the `summary` of each cell and count.",
            "",
            "| parameter | method | p <= alpha, n_blocks=None | p <= alpha, n_blocks=2 "
            "| accepted, n_blocks=None | accepted, n_blocks=2 |",
            "|---|---|---|---|---|---|",
        ]
        for cell in cells:
            s = cell["summary"]
            lines.append(
                f"| {_parameter(cell)} | {_method(cell['surrogate_method'])} | "
                f"{_cell(s['n_blocks_None']['p_le_alpha'])} | "
                f"{_cell(s['n_blocks_2']['p_le_alpha'])} | "
                f"{_cell(s['n_blocks_None']['accepted'])} | "
                f"{_cell(s['n_blocks_2']['accepted'])} |")
        lines.append("")

    lines += [
        "## Planted cells: (8, 8) blocks plus nuisance, SNR 1",
        "",
        "Source: `planted_cells`, the `summary` of each cell and count.",
        "",
        "| nuisance | parameter | method | count | accepted | exact (contact 8) "
        "| within one contact |",
        "|---|---|---|---|---|---|---|",
    ]
    for cell in record["planted_cells"]:
        for key in BLOCK_COUNTS:
            s = cell["summary"][key]
            lines.append(
                f"| {cell['family']} | {_parameter(cell)} | {_method(cell['surrogate_method'])} "
                f"| {key} | {_cell(s['accepted'])} | {_cell(s['exact'])} "
                f"| {_cell(s['within_one'])} |")
    lines.append("")

    lines += ["## Reproduction of the receipt's smooth-gradient cell", ""]
    if repro["run"]:
        lines += [
            f"Source: `reproduction`. The length-4 null cell over seeds 0 to "
            f"{repro['n_seeds'] - 1}, n_blocks=2, against "
            "`artifacts/benchmarks/calibration/xflip_calibration_0.2.5_raw.json`.",
            "",
            "| statistic | this run | receipt | equal |",
            "|---|---|---|---|",
        ]
        for name, value in repro["mine"].items():
            theirs = repro["receipt"][name]
            lines.append(f"| {name} | {value!r} | {theirs!r} | {value == theirs} |")
        lines += ["", f"Equal on every statistic: {repro['equal']}.", ""]
    else:
        lines += [f"Not run: {repro['reason']}.", ""]

    lines += ["## Environment", ""]
    lines += [f"- {key}: {value}" for key, value in record["environment"].items()]
    lines += ["", f"Wall time {record['elapsed_s']} s. Per-seed records are in "
                  "`xflip_nuisance.json`.", ""]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--n", type=int, default=100, help="seeds per cell")
    ap.add_argument("--n-surrogates", type=int, default=N_SURROGATES)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--smoke", action="store_true", help="three seeds per cell; prints only")
    mode.add_argument("--write", action="store_true", help="write the receipt and its JSON")
    args = ap.parse_args(argv)
    n_seeds = 3 if args.smoke else args.n
    if n_seeds < 1 or args.n_surrogates < 1:
        ap.error("--n and --n-surrogates must be at least 1")

    n_cells = len(NULL_CELLS) + len(PLANTED_CELLS)
    print(f"xflip null and planted cells: {len(NULL_CELLS)} null + {len(PLANTED_CELLS)} planted, "
          f"{n_seeds} seeds, {args.n_surrogates} surrogates, "
          f"{n_cells * n_seeds * len(BLOCK_COUNTS)} xflip calls")
    t0 = time.perf_counter()
    null_out, planted_out, rows_by_cell = [], [], {}
    for family, name, value, method, build in NULL_CELLS:
        rows = run_cell(build, n_seeds, args.n_surrogates, method=method, rng_offset=NULL_RNG)
        summary = {key: null_summary(rows, key) for key in BLOCK_COUNTS}
        null_out.append({"family": family, "parameter": name, "value": value,
                         "surrogate_method": method, "n_seeds": n_seeds,
                         "summary": summary, "seeds": rows})
        rows_by_cell[(family, value)] = rows
        for key in BLOCK_COUNTS:
            s = summary[key]
            print(f"  null    {_label(family, name, value):30s} {method:20s} {key:14s} "
                  f"p<=alpha {_fmt(s['p_le_alpha'])} accepted {_fmt(s['accepted'])}")
    for family, name, value, method, build in PLANTED_CELLS:
        rows = run_cell(build, n_seeds, args.n_surrogates, method=method,
                        rng_offset=PLANTED_RNG)
        summary = {key: planted_summary(rows, key) for key in BLOCK_COUNTS}
        planted_out.append({"family": family, "parameter": name, "value": value,
                            "surrogate_method": method, "n_seeds": n_seeds,
                            "summary": summary, "seeds": rows})
        for key in BLOCK_COUNTS:
            s = summary[key]
            print(f"  planted {_label(family, name, value):30s} {method:20s} {key:14s} "
                  f"accepted {_fmt(s['accepted'])} exact {_fmt(s['exact'])} "
                  f"within_one {_fmt(s['within_one'])}")

    checks = design_checks(n_surrogates=args.n_surrogates)
    repro = reproduction(rows_by_cell[("smooth_toeplitz", 4.0)], args.n_surrogates)
    elapsed = round(time.perf_counter() - t0, 1)
    print(f"design checks: scaling max abs diff {checks['scaling']['max_abs_diff']:g}; "
          f"gates identical {checks['gates']['identical']}")
    if repro["run"]:
        print(f"reproduction over {repro['n_seeds']} seeds: equal {repro['equal']}")
    print(f"wall time {elapsed} s")

    if args.write:
        record = {
            "estimator_sha256": receipt.estimator_sha256(),
            "operating_point": {
                "n_contacts": N_CONTACTS, "n_samples": N_SAMPLES, "fs": FS,
                "n_seeds": n_seeds, "n_surrogates": args.n_surrogates,
                "min_block_size": MIN_BLOCK_SIZE, "alpha": ALPHA,
                "block_counts": BLOCK_COUNTS,
                "ci": {"method": "jnwb.clopper_pearson", "alpha": CI_ALPHA},
                "planted": {"blocks": list(PLANTED_BLOCKS), "within_corr": PLANTED_WITHIN,
                            "between_corr": PLANTED_BETWEEN, "boundary": PLANTED_BOUNDARY,
                            "snr": 1.0},
            },
            "design_checks": checks,
            "reproduction": repro,
            "null_cells": null_out,
            "planted_cells": planted_out,
            "environment": {"jnwb": jnwb.__version__, "python": platform.python_version(),
                            "numpy": np.__version__, "scipy": scipy.__version__,
                            "platform": platform.platform()},
            "elapsed_s": elapsed,
        }
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "xflip_nuisance.json").write_bytes(
            (json.dumps(record, indent=2, allow_nan=False) + "\n").encode("utf-8"))
        (OUT_DIR / "xflip_nuisance.md").write_bytes(render(record).encode("utf-8"))
        print(f"wrote {OUT_DIR / 'xflip_nuisance.md'} and {OUT_DIR / 'xflip_nuisance.json'}")


if __name__ == "__main__":
    main()
