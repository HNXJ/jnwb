"""Sensitivity of vFLIP2's omega and acceptance to one input at a time.

The baseline is vflip2's defaults, with the contact spacing the fixture states (100 um). Two
probe sets:

- the Dryad power example: `power_example` in tests/fixtures/vflip2_matlab_reference.json, a
  31-by-250 PSD at 1 Hz bins, run through `vflip2`;
- 50 seeded synthetic probes (seeds 0..49): `synth_laminar_motif(n_channels=32, n_samples=5000,
  fs=1000, pitch_um=100, rng=seed)`, cut into 1 s trials and turned into a PSD by
  `_psd_hanning`, the function `vflip2_from_lfp` uses (1 Hz labels 1..150). The default run is
  checked to equal `vflip2_from_lfp` on every probe.

Changes, one at a time:

- bin width 0.5 Hz: each row linearly interpolated at 1.0, 1.5, ..., the last 1 Hz label.
  Bin width 2 Hz: the output bin labelled 2k Hz is the mean of the 1 Hz bins 2k-1 and 2k.
  The power example has only its PSD, so no FFT-length route exists for it.
- upper frequency 150, 200, 250 Hz: keep the columns labelled at most that value. A value
  above the PSD's last label is not run and is reported as skipped.
- contact spacing 50 um: linear interpolation between rows, midpoints inserted; 200 um: every
  second row.
- layer-4 thickness 0.4, 0.586, 0.8 mm: `layer4_thickness_mm`.
- orientation: rows reversed (orientation "both"), and `orientation="upright"`, `"inverted"`.
- omega_cut 4, 6, 8: `omega_cut`. Omega does not depend on it; only acceptance does.

Bin width and upper frequency are not vflip2 parameters: they are the frequency axis of the
PSD. The parameter list is read from `inspect.signature(vflip2)`.

Usage: `python scripts/vflip2_sensitivity.py` prints the tables; `--write` writes
artifacts/evidence/0.2.12/vflip2_sensitivity.md.
"""

from __future__ import annotations

import argparse
import inspect
import json
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "vflip2_matlab_reference.json"
EVIDENCE = REPO_ROOT / "artifacts" / "evidence" / "0.2.12" / "vflip2_sensitivity.md"
SEEDS = tuple(range(50))
FS = 1000.0
N_CHANNELS = 32
N_SAMPLES = 5000
PITCH_UM = 100.0
VARIANTS: Tuple[Tuple[str, Any], ...] = (
    ("bin width (Hz)", 0.5),
    ("bin width (Hz)", 2.0),
    ("upper frequency (Hz)", 150.0),
    ("upper frequency (Hz)", 200.0),
    ("upper frequency (Hz)", 250.0),
    ("contact spacing (um)", 50.0),
    ("contact spacing (um)", 200.0),
    ("layer-4 thickness (mm)", 0.4),
    ("layer-4 thickness (mm)", 0.586),
    ("layer-4 thickness (mm)", 0.8),
    ("orientation", "flip rows"),
    ("orientation", "upright"),
    ("orientation", "inverted"),
    ("omega_cut", 4.0),
    ("omega_cut", 6.0),
    ("omega_cut", 8.0),
)


def _checkout_jnwb():
    """This tree's jnwb, for the command line. A copy in site-packages would be measured
    silently, so the checkout goes first and the import is verified to have used it."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    import jnwb

    root = REPO_ROOT.resolve()
    location = Path(jnwb.__file__).resolve()
    if root not in location.parents:
        raise RuntimeError(f"imported jnwb from {location}, not from this tree ({root})")
    return jnwb


_checkout_jnwb()

from jnwb.laminar import _vflip2  # noqa: E402
from jnwb.laminar._vflip2 import LAYER4_THICKNESS_MM, OMEGA_CUT, vflip2, vflip2_from_lfp  # noqa: E402
from jnwb.testing.synth import synth_laminar_motif  # noqa: E402


class Skip(Exception):
    """A value the input does not reach: reported, not run."""


def head_commit() -> str:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
                          text=True, check=True)
    return proc.stdout.strip()


def load_power_example() -> Tuple[np.ndarray, np.ndarray, float, float]:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    case = next(c for c in doc["cases"] if c["name"] == "power_example")
    psd = np.array([[np.nan if v is None else v for v in row] for row in case["psd"]],
                   dtype=float)
    freqs = float(case["freqbinsize"]) * np.arange(1, psd.shape[1] + 1, dtype=float)
    return psd, freqs, float(case["intdist"]) * 1000.0, float(case["matlab"]["omega"])


def synthetic_probe(seed: int):
    """(PSD, 1 Hz labels, vflip2_from_lfp's result) for one seed, PSD built as vflip2_from_lfp
    builds it: 1 s trials, `_psd_hanning`."""
    lfp = synth_laminar_motif(n_channels=N_CHANNELS, n_samples=N_SAMPLES, fs=FS,
                              pitch_um=PITCH_UM, rng=seed).lfp
    per_trial = int(FS)
    n_trials = lfp.shape[1] // per_trial
    trials = lfp[:, :n_trials * per_trial].reshape(lfp.shape[0], n_trials, per_trial)
    trials = trials.transpose(0, 2, 1)
    psd = _vflip2._psd_hanning(trials, FS)
    freqs = np.arange(1, psd.shape[1] + 1, dtype=float)
    return psd, freqs, vflip2_from_lfp(lfp, FS, contact_spacing=PITCH_UM)


def _bin_width(psd: np.ndarray, freqs: np.ndarray, width: float):
    n = freqs.size
    if not np.array_equal(freqs, np.arange(1, n + 1, dtype=float)):
        raise ValueError("bin-width resampling needs 1 Hz labels 1..n")
    if width == 2.0:
        if n % 2:
            raise ValueError("2 Hz pairing needs an even number of 1 Hz bins")
        return 0.5 * (psd[:, 0::2] + psd[:, 1::2]), 2.0 * np.arange(1, n // 2 + 1, dtype=float)
    if width == 0.5:
        new = 0.5 * np.arange(2, 2 * n + 1, dtype=float)  # 1.0, 1.5, ..., n
        return np.array([np.interp(new, freqs, row) for row in psd]), new
    raise ValueError(f"no resampling for bin width {width}")


def make_inputs(variant: Tuple[str, Any], psd: np.ndarray, freqs: np.ndarray, spacing: float):
    """(PSD, labels, contact spacing, keyword arguments) for one variant; raises Skip."""
    group, value = variant
    kwargs: Dict[str, Any] = {}
    if group == "bin width (Hz)":
        psd, freqs = _bin_width(psd, freqs, value)
    elif group == "upper frequency (Hz)":
        if freqs[-1] < value:
            raise Skip(f"the PSD ends at {freqs[-1]:g} Hz")
        keep = freqs <= value
        psd, freqs = psd[:, keep], freqs[keep]
    elif group == "contact spacing (um)":
        if value == 200.0:
            psd, spacing = psd[0::2], 200.0
        elif value == 50.0:
            rows = np.empty((2 * psd.shape[0] - 1, psd.shape[1]))
            rows[0::2] = psd
            rows[1::2] = 0.5 * (psd[:-1] + psd[1:])
            psd, spacing = rows, 50.0
        else:
            raise ValueError(f"no resampling for spacing {value}")
    elif group == "layer-4 thickness (mm)":
        kwargs["layer4_thickness_mm"] = value
    elif group == "orientation":
        if value == "flip rows":
            psd = psd[::-1]
        else:
            kwargs["orientation"] = value
    elif group == "omega_cut":
        kwargs["omega_cut"] = value
    else:
        raise ValueError(f"unknown variant {variant!r}")
    return psd, freqs, spacing, kwargs


def run(psd: np.ndarray, freqs: np.ndarray, spacing: float, **kwargs) -> Dict[str, Any]:
    try:
        result = vflip2(psd, freqs, contact_spacing=spacing, **kwargs)
    except ValueError as exc:
        return {"omega": None, "accepted": False, "error": str(exc)}
    return {"omega": result.omega, "accepted": result.accepted, "error": None}


def probe_all(psd: np.ndarray, freqs: np.ndarray, spacing: float) -> Dict[Any, Dict[str, Any]]:
    out: Dict[Any, Dict[str, Any]] = {"default": run(psd, freqs, spacing)}
    for variant in VARIANTS:
        try:
            p2, f2, s2, kwargs = make_inputs(variant, psd, freqs, spacing)
        except Skip as exc:
            out[variant] = {"skip": str(exc)}
            continue
        out[variant] = run(p2, f2, s2, **kwargs)
    return out


def fmt(x: Optional[float], signed: bool = False) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.6f}" if signed else f"{x:.6f}"


def summarize(results: List[Dict[Any, Dict[str, Any]]], variant: Tuple[str, Any]) -> Dict[str, Any]:
    runs = [r[variant] for r in results]
    if "skip" in runs[0]:
        return {"skip": runs[0]["skip"]}
    base = [r["default"] for r in results]
    deltas = [r["omega"] - b["omega"] for r, b in zip(runs, base)
              if r["omega"] is not None and b["omega"] is not None]
    errors = sorted({r["error"] for r in runs if r["error"] is not None})
    return {
        "probes": len(runs),
        "accepted": sum(1 for r in runs if r["accepted"]),
        "flips": sum(1 for r, b in zip(runs, base) if r["accepted"] != b["accepted"]),
        "no_window": sum(1 for r in runs if r["omega"] is None and r["error"] is None),
        "errors": sum(1 for r in runs if r["error"] is not None),
        "error_text": "; ".join(errors),
        "n_delta": len(deltas),
        "median": statistics.median(deltas) if deltas else None,
        "min": min(deltas) if deltas else None,
        "max": max(deltas) if deltas else None,
    }


def collect(n_probes: int):
    psd, freqs, spacing, matlab_omega = load_power_example()
    power = probe_all(psd, freqs, spacing)
    d = power["default"]
    if d["error"] is not None or not d["accepted"]:
        raise RuntimeError(f"power example default must be accepted: {d}")
    if abs(d["omega"] - matlab_omega) > 1e-9 * abs(matlab_omega):
        raise RuntimeError(f"power example omega {d['omega']!r} != MATLAB {matlab_omega!r}")
    synth: List[Dict[Any, Dict[str, Any]]] = []
    for seed in SEEDS[:n_probes]:
        sp, sf, ref = synthetic_probe(seed)
        res = probe_all(sp, sf, PITCH_UM)
        got = res["default"]["omega"]
        if got != ref.omega or (got is None) != (ref.omega is None):
            raise RuntimeError(f"seed {seed}: PSD route omega {got!r} != vflip2_from_lfp "
                               f"{ref.omega!r}")
        synth.append(res)
        print(f"seed {seed}: default omega {fmt(got)} accepted {res['default']['accepted']}",
              flush=True)
    return power, synth, matlab_omega, spacing


def label(variant: Tuple[str, Any]) -> Tuple[str, str]:
    return variant[0], f"{variant[1]:g}" if isinstance(variant[1], float) else str(variant[1])


def render(power, synth, matlab_omega, power_spacing, sha: str, n_probes: int) -> str:
    sig = inspect.signature(vflip2)
    varied = ("contact_spacing", "orientation", "layer4_thickness_mm", "omega_cut")
    missing = [name for name in varied if name not in sig.parameters]
    if missing:
        raise RuntimeError(f"vflip2 lacks parameters {missing}")
    d = power["default"]
    lines = [
        "# vFLIP2 sensitivity: omega and acceptance, one input changed at a time",
        "",
        f"Generated by `scripts/vflip2_sensitivity.py --write` at commit `{sha}` (HEAD when the "
        "script ran).",
        f"Seeds: {', '.join(str(s) for s in SEEDS[:n_probes])} for the synthetic probes "
        f"(`synth_laminar_motif(n_channels={N_CHANNELS}, n_samples={N_SAMPLES}, fs={FS:g}, "
        f"pitch_um={PITCH_UM:g}, rng=seed)`, PSD as `vflip2_from_lfp` builds it). The Dryad power "
        "example is `power_example` in `tests/fixtures/vflip2_matlab_reference.json`; it has no "
        "random seed.",
        f"Defaults: contact spacing {power_spacing:g} um, orientation \"both\", layer-4 thickness "
        f"`LAYER4_THICKNESS_MM` = {LAYER4_THICKNESS_MM!r} mm, `OMEGA_CUT` = {OMEGA_CUT:g}, bin "
        "width 1 Hz, upper frequency = the PSD's last label.",
        f"Power example default omega {fmt(d['omega'])} against MATLAB {fmt(matlab_omega)} "
        "(agreement checked to rtol 1e-9 before writing).",
        "",
        "## vFLIP2 parameters (from `inspect.signature`)",
        "",
        "| name | default |",
        "|---|---|",
    ]
    for name, p in sig.parameters.items():
        default = "(required)" if p.default is inspect.Parameter.empty else repr(p.default)
        lines.append(f"| `{name}` | {default} |")
    lines += [
        "",
        "Varied as keywords: `contact_spacing`, `orientation`, `layer4_thickness_mm`, `omega_cut`. "
        "Not parameters: bin width (the spacing of `freqs`) and upper frequency (the last label "
        "of `freqs`); both are changed on the PSD's frequency axis.",
        "",
        "## Dryad power example (one probe)",
        "",
        "| setting | value | omega | change from default | accepted | note |",
        "|---|---|---|---|---|---|",
        f"| default | - | {fmt(d['omega'])} | 0 | {d['accepted']} | - |",
    ]
    for variant in VARIANTS:
        r = power[variant]
        setting, value = label(variant)
        if "skip" in r:
            lines.append(f"| {setting} | {value} | not run | n/a | n/a | {r['skip']} |")
            continue
        delta = None if r["omega"] is None or d["omega"] is None else r["omega"] - d["omega"]
        note = r["error"] or ("no window" if r["omega"] is None else "-")
        lines.append(f"| {setting} | {value} | {fmt(r['omega'])} | {fmt(delta, True)} | "
                     f"{r['accepted']} | {note} |")
    lines += [
        "",
        f"## Synthetic probes ({n_probes} seeds)",
        "",
        "Change from default is over the probes where both runs have a window. "
        "`flips` counts probes whose acceptance differs from the default run.",
        "",
        "| setting | value | probes run | accepted | flips | no window | errors | median change | "
        "min change | max change | note |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    base = summarize(synth, "default")
    lines.append(
        f"| default | - | {base['probes']} | {base['accepted']} | 0 | {base['no_window']} | "
        f"{base['errors']} | 0 | 0 | 0 | - |")
    for variant in VARIANTS:
        s = summarize(synth, variant)
        setting, value = label(variant)
        if "skip" in s:
            lines.append(f"| {setting} | {value} | not run | n/a | n/a | n/a | n/a | n/a | n/a | "
                         f"n/a | {s['skip']} |")
            continue
        note = s["error_text"] or "-"
        lines.append(
            f"| {setting} | {value} | {s['probes']} | {s['accepted']} | {s['flips']} | "
            f"{s['no_window']} | {s['errors']} | {fmt(s['median'], True)} | "
            f"{fmt(s['min'], True)} | {fmt(s['max'], True)} | {note} |")
    lines += [
        "",
        "## Method",
        "",
        "- Bin width 2 Hz: each output bin is the mean of two adjacent 1 Hz bins; its label is the "
        "even one. Bin width 0.5 Hz: linear interpolation at half-hertz labels within the input "
        "range. The power example has only its PSD, so it has no FFT-length route.",
        "- Upper frequency: the columns labelled at most the value; a value above the last label "
        "is not run.",
        "- Contact spacing 200 um: every second row. 50 um: linear interpolation between rows, "
        "midpoints inserted.",
        "- Flip rows: row order reversed, orientation \"both\".",
        "- omega_cut changes acceptance only: accepted is omega > omega_cut.",
        "",
        "Reproduce: `python scripts/vflip2_sensitivity.py --write` with the tree as the working "
        "directory.",
        "",
    ]
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="vFLIP2 sensitivity tables (see module docstring).")
    ap.add_argument("--write", action="store_true",
                    help=f"write {EVIDENCE.relative_to(REPO_ROOT).as_posix()}")
    ap.add_argument("--probes", type=int, default=len(SEEDS),
                    help="run the first N seeds (smoke runs); --write needs all of them")
    args = ap.parse_args(argv)
    if not 1 <= args.probes <= len(SEEDS):
        ap.error(f"--probes must be 1..{len(SEEDS)}")
    if args.write and args.probes != len(SEEDS):
        ap.error("--write needs all 50 probes")
    power, synth, matlab_omega, spacing = collect(args.probes)
    text = render(power, synth, matlab_omega, spacing, head_commit(), args.probes)
    if args.write:
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_bytes(text.encode("utf-8"))
        print(f"wrote {EVIDENCE.relative_to(REPO_ROOT).as_posix()}", flush=True)
    else:
        print(text, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
