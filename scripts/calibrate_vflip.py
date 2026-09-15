"""Regenerate the vFLIP support-score calibration receipt from the current estimator.

    python scripts/calibrate_vflip.py [--n-seeds 30] [--n-jobs -1]

Writes ``artifacts/benchmarks/vflip_calibration_0.2.4.md`` and ``vflip_calibration_0.2.4_raw.json``.
The JSON records a SHA-256 of the ``vflip`` source; ``tests/test_vflip_calibration_receipt.py``
fails when the estimator changes without this script being rerun.

Every recording is synthetic, built by ``jnwb.testing`` generators and passed end to end
through ``vflip_from_lfp`` with default arguments, so each number below traces to a seeded
computation. A trial counts as accepted at threshold ``tau`` when the fit has no structural
rejection (orientation, peak distance, crossover) and ``support_score >= tau``.

Families
--------
Null (no single spectrolaminar crossover; any acceptance is a false positive):
    white_noise       independent white noise on every contact
    ar_background     independent 1/f-like AR(1) noise (tau = 30 ms) on every contact
    amplitude_ramp    AR background scaled by a linear broadband gain along the shaft
    parallel_bands    gamma and beta power fall together with depth (no crossover)
Structured non-motif (reported, not claimed as controlled):
    double_motif      two motif copies stacked along the shaft (two crossovers)
    orientation_mismatch  a deep_to_superficial motif analysed with the opposite declared
                      orientation; the correct outcome is rejection
Alternative (one crossover at the shaft midpoint):
    snr_sweep         N = 24, varying motif SNR
    channel_sweep     SNR = 1, N from 8 to 64
    missing_sweep     N = 24, SNR = 1, a fraction of interior contacts dead and masked
    pitch_sweep       one 1200 um column sampled at 25, 50, 100 and 150 um
Discretization of the null:
    grid_null_sweep   white noise, N = 24, over (recording length, nperseg); the score is
                      computed on the full Welch grid, so its null distribution depends on
                      how many bins that grid has
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import pathlib
import platform
import sys

import numpy as np
import scipy

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb._parallel import parallel_map  # noqa: E402
from jnwb.laminar import vflip, vflip_from_lfp  # noqa: E402
from jnwb.testing import synth_ar_noise, synth_laminar_motif, synth_white_noise  # noqa: E402

FS = 1000.0
N_SAMPLES = 5000
DEFAULT_TAU = float(inspect.signature(vflip).parameters["min_support_score"].default)
TAU_GRID = [round(0.25 * k, 2) for k in range(0, 49)]
STRUCTURAL_OK = (None, "insufficient_support")
OUT_DIR = ROOT / "artifacts" / "benchmarks"


def estimator_sha256() -> str:
    return hashlib.sha256(inspect.getsource(vflip).encode("utf-8")).hexdigest()


def _outcome(res, truth=None):
    error = None
    if truth is not None and res.accepted:
        error = float(abs(res.crossover_contact - truth))
    return {
        "score": float(res.support_score),
        "structural_ok": res.rejection_reason in STRUCTURAL_OK,
        "accepted": bool(res.accepted),
        "error_contacts": error,
    }


def _band_ramp(n_channels, gen, rising):
    """Band-limited sources whose power falls (or rises) linearly along the shaft."""
    from scipy import signal

    weights = np.linspace(1.0, 0.2, n_channels)
    if rising:
        weights = weights[::-1]
    out = synth_ar_noise(N_SAMPLES, n_channels=n_channels, tau_s=0.03, fs=FS, rng=gen)
    for lo, hi in ((65.0, 85.0), (13.0, 23.0)):
        sos = signal.butter(4, [lo, hi], btype="bandpass", fs=FS, output="sos")
        src = signal.sosfiltfilt(sos, gen.normal(size=(n_channels, N_SAMPLES)), axis=-1)
        out += 2.0 * weights[:, None] * src
    return out


def trial(job):
    family, param, seed = job
    gen = np.random.default_rng(seed)
    n = 24
    if family == "white_noise":
        return _outcome(vflip_from_lfp(synth_white_noise(shape=(n, N_SAMPLES), rng=gen), FS))
    if family == "ar_background":
        return _outcome(vflip_from_lfp(synth_ar_noise(N_SAMPLES, n_channels=n, tau_s=0.03, fs=FS, rng=gen), FS))
    if family == "amplitude_ramp":
        lfp = synth_ar_noise(N_SAMPLES, n_channels=n, tau_s=0.03, fs=FS, rng=gen)
        return _outcome(vflip_from_lfp(lfp * np.linspace(0.5, 2.0, n)[:, None], FS))
    if family == "parallel_bands":
        return _outcome(vflip_from_lfp(_band_ramp(n, gen, rising=False), FS))
    if family == "double_motif":
        half = n // 2
        a = synth_laminar_motif(half, N_SAMPLES, FS, c_crossover=(half - 1) / 2, snr=1.0, rng=gen).lfp
        b = synth_laminar_motif(half, N_SAMPLES, FS, c_crossover=(half - 1) / 2, snr=1.0, rng=gen).lfp
        return _outcome(vflip_from_lfp(np.vstack([a, b]), FS))
    if family == "orientation_mismatch":
        rec = synth_laminar_motif(n, N_SAMPLES, FS, c_crossover=(n - 1) / 2, snr=1.0,
                                  orientation="deep_to_superficial", rng=gen)
        return _outcome(vflip_from_lfp(rec.lfp, FS, orientation="superficial_to_deep"))
    if family == "snr_sweep":
        rec = synth_laminar_motif(n, N_SAMPLES, FS, c_crossover=(n - 1) / 2, snr=param, rng=gen)
        return _outcome(vflip_from_lfp(rec.lfp, FS), rec.crossover_contact)
    if family == "channel_sweep":
        rec = synth_laminar_motif(param, N_SAMPLES, FS, c_crossover=(param - 1) / 2, snr=1.0, rng=gen)
        return _outcome(vflip_from_lfp(rec.lfp, FS), rec.crossover_contact)
    if family == "missing_sweep":
        n_bad = int(round(param * n))
        bad = sorted(gen.choice(np.arange(1, n - 1), size=n_bad, replace=False).tolist()) if n_bad else None
        rec = synth_laminar_motif(n, N_SAMPLES, FS, c_crossover=(n - 1) / 2, snr=1.0,
                                  bad_channels=bad, rng=gen)
        res = vflip_from_lfp(rec.lfp, FS, bad_channel_mask=rec.bad_channel_mask)
        return _outcome(res, rec.crossover_contact)
    if family == "pitch_sweep":
        n_ch = int(round(1200.0 / param))
        rec = synth_laminar_motif(n_ch, N_SAMPLES, FS, c_crossover=(n_ch - 1) / 2, snr=1.0,
                                  pitch_um=param, rng=gen)
        res = vflip_from_lfp(rec.lfp, FS, contact_spacing=param)
        out = _outcome(res, rec.crossover_contact)
        out["n_channels"] = n_ch
        out["error_um"] = None if out["error_contacts"] is None else out["error_contacts"] * param
        return out
    if family == "grid_null_sweep":
        n_samples, nperseg = (int(v) for v in param.split("x"))
        lfp = synth_white_noise(shape=(n, n_samples), rng=gen)
        return _outcome(vflip_from_lfp(lfp, FS, nperseg=nperseg))
    raise ValueError(family)


NULLS = ["white_noise", "ar_background", "amplitude_ramp", "parallel_bands"]
STRUCTURED = ["double_motif", "orientation_mismatch"]
SWEEPS = {
    "snr_sweep": [0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0],
    "channel_sweep": [8, 12, 16, 24, 32, 48, 64],
    "missing_sweep": [0.0, 0.1, 0.2, 0.3],
    "pitch_sweep": [25.0, 50.0, 100.0, 150.0],
    "grid_null_sweep": ["5000x250", "5000x500", "5000x1000", "20000x1000", "20000x2000"],
}


def _summary(rows):
    scores = np.array([r["score"] for r in rows])
    ok = np.array([r["structural_ok"] for r in rows])
    errors = [r["error_contacts"] for r in rows if r["error_contacts"] is not None]
    curve = {str(t): float(np.mean(ok & (scores >= t))) for t in TAU_GRID}
    summary = {
        "n": len(rows),
        "median_score": float(np.median(scores)),
        "min_score": float(np.min(scores)),
        "max_score": float(np.max(scores)),
        "rate_at_default": float(np.mean([r["accepted"] for r in rows])),
        "rate_curve": curve,
        "median_error_contacts": float(np.median(errors)) if errors else None,
        "scores": scores.tolist(),
    }
    if rows and "error_um" in rows[0]:
        um = [r["error_um"] for r in rows if r["error_um"] is not None]
        summary["n_channels"] = rows[0]["n_channels"]
        summary["median_error_um"] = float(np.median(um)) if um else None
    return summary


def run(n_seeds: int, n_jobs: int) -> dict:
    jobs = []
    base = 10_000
    for k, fam in enumerate(NULLS + STRUCTURED):
        jobs += [(fam, None, base * (k + 1) + s) for s in range(n_seeds)]
    for k, (fam, values) in enumerate(SWEEPS.items()):
        for j, v in enumerate(values):
            jobs += [(fam, v, base * (20 + k) + 100 * j + s) for s in range(n_seeds)]
    results = parallel_map(trial, jobs, n_jobs=n_jobs)

    grouped: dict = {}
    for (fam, val, _), row in zip(jobs, results):
        grouped.setdefault(fam, {}).setdefault(str(val), []).append(row)

    return {
        "estimator_sha256": estimator_sha256(),
        "default_min_support_score": DEFAULT_TAU,
        "n_seeds": n_seeds,
        "n_samples": N_SAMPLES,
        "fs": FS,
        "environment": {
            "jnwb": jnwb.__version__,
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "python": platform.python_version(),
        },
        "tau_grid": TAU_GRID,
        "families": {
            fam: {val: _summary(rows) for val, rows in by_val.items()}
            for fam, by_val in grouped.items()
        },
    }


def _fmt(x, spec=".2f"):
    return "n/a" if x is None else format(x, spec)


def render(data: dict) -> str:
    tau = data["default_min_support_score"]
    alt_taus = [str(tau - 1.0), str(tau + 1.0)]
    fam = data["families"]
    lines = [
        "# vFLIP support-score calibration",
        "",
        f"Generated by `python scripts/calibrate_vflip.py` from `vflip` source SHA-256 "
        f"`{data['estimator_sha256'][:16]}`; {data['n_seeds']} seeds per cell, "
        f"{data['n_samples']} samples at {data['fs']:g} Hz, default arguments. "
        f"Environment: jnwb {data['environment']['jnwb']}, numpy {data['environment']['numpy']}, "
        f"scipy {data['environment']['scipy']}, Python {data['environment']['python']}. "
        "All recordings are synthetic; family definitions are in the script docstring.",
        "",
        f"Rates at a threshold count trials with no structural rejection and score >= threshold. "
        f"The default threshold is {tau:g}.",
        "",
        "## Null families (false-positive rate)",
        "",
        f"| Family | Median score | Max score | Rate at {float(alt_taus[0]):g} | Rate at {tau:g} | Rate at {float(alt_taus[1]):g} |",
        "|---|---|---|---|---|---|",
    ]
    for name in NULLS:
        s = fam[name]["None"]
        lines.append(
            f"| `{name}` | {s['median_score']:.2f} | {s['max_score']:.2f} | "
            f"{s['rate_curve'][alt_taus[0]]:.3f} | {s['rate_at_default']:.3f} | {s['rate_curve'][alt_taus[1]]:.3f} |"
        )
    lines += ["", "## Structured non-motif families (acceptance rate)", "",
              f"| Family | Median score | Rate at {tau:g} |", "|---|---|---|"]
    for name in STRUCTURED:
        s = fam[name]["None"]
        lines.append(f"| `{name}` | {s['median_score']:.2f} | {s['rate_at_default']:.3f} |")

    titles = {
        "snr_sweep": ("SNR sweep (N = 24)", "SNR"),
        "channel_sweep": ("Channel-count sweep (SNR = 1)", "N contacts"),
        "missing_sweep": ("Missing-contact sweep (N = 24, SNR = 1)", "Missing fraction"),
    }
    for key, (title, col) in titles.items():
        lines += ["", f"## {title}", "",
                  f"| {col} | Median score | Min score | Rate at {tau:g} | Median error (contacts) |",
                  "|---|---|---|---|---|"]
        for val in SWEEPS[key]:
            s = fam[key][str(val)]
            lines.append(f"| {val:g} | {s['median_score']:.2f} | {s['min_score']:.2f} | "
                         f"{s['rate_at_default']:.3f} | {_fmt(s['median_error_contacts'])} |")

    lines += ["", "## Null false-positive rate by frequency grid (white noise, N = 24)", "",
              f"| Samples | nperseg | Frequency bins | Median score | Rate at {tau:g} |",
              "|---|---|---|---|---|"]
    for val in SWEEPS["grid_null_sweep"]:
        s = fam["grid_null_sweep"][str(val)]
        n_samples, nperseg = (int(v) for v in val.split("x"))
        lines.append(f"| {n_samples} | {nperseg} | {nperseg // 2 + 1} | {s['median_score']:.2f} | "
                     f"{s['rate_at_default']:.3f} |")

    lines += ["", "## Physical equivalence (one 1200 um column, SNR = 1)", "",
              f"| Pitch (um) | N contacts | Median score | Min score | Rate at {tau:g} | Median error (um) |",
              "|---|---|---|---|---|---|"]
    for val in SWEEPS["pitch_sweep"]:
        s = fam["pitch_sweep"][str(val)]
        lines.append(f"| {val:g} | {s['n_channels']} | {s['median_score']:.2f} | {s['min_score']:.2f} | "
                     f"{s['rate_at_default']:.3f} | {_fmt(s['median_error_um'], '.1f')} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-seeds", type=int, default=30)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--out-dir", type=pathlib.Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    data = run(args.n_seeds, args.n_jobs)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "vflip_calibration_0.2.4_raw.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    (args.out_dir / "vflip_calibration_0.2.4.md").write_text(render(data), encoding="utf-8")
    print(render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
