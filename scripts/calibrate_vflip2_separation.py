"""Regenerate the vFLIP-vFLIP2 separation agreement threshold (15-18).

    python scripts/calibrate_vflip2_separation.py [--n-draws 400] [--seed 0] [--out DIR] [--smoke]

One null probe: ``jnwb.testing.synth_laminar_motif`` at ``snr=0`` on a fixed 32-contact,
100 um-pitch shaft at 1000 Hz, each draw from a successive child of the seeded ``rng``.
Both estimators run with their acceptance gates open (vFLIP ``min_support_score`` and
vFLIP2 ``omega_cut`` at -1e9, both finite, so no sentinel bypasses anything), because on
null probes the gates closed leave almost no draw with both crossovers present. The gap
is the ``|vFLIP2 - vFLIP|`` crossover separation in contact spacings, the quantity
``fuse_laminar_anchors`` reports as ``separation_contacts``; draws where either
crossover is structurally absent leave it undefined and are counted, not filled in.
The threshold T is the 95th percentile of the defined gaps.

Writes ``vflip2_separation_0.2.14.md`` and ``vflip2_separation_0.2.14_raw.json`` to
``artifacts/benchmarks/calibration`` (or ``--out``). ``--smoke`` runs 8 draws, prints
the result and writes nothing. The script changes no default; the constant it feeds
lives in ``jnwb/laminar_curation.py`` and cites the receipt.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import platform
import sys
import time

import numpy as np
import scipy

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
elif str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb._rng import RNGLike, resolve_rng  # noqa: E402
from jnwb.laminar import vflip_from_lfp, vflip2_from_lfp  # noqa: E402
from jnwb.testing import synth_laminar_motif  # noqa: E402
from scripts import calibrate_xflip as _xflip_receipt  # noqa: E402

RELEASE = "0.2.14"
STEM = f"vflip2_separation_{RELEASE}"
OUT_DIR = ROOT / "artifacts" / "benchmarks" / "calibration"
GENERATOR = "jnwb.testing.synth_laminar_motif"
FS = 1000.0
PITCH_UM = 100.0
N_CONTACTS = 32
N_SAMPLES = 8000
C_CROSSOVER = 16.0
SNR_NULL = 0.0
#: Both acceptance gates open: finite, so no sentinel bypasses the acceptance logic;
#: the gap is then the structural-crossover disagreement on noise.
OPEN_GATE = -1e9
PERCENTILE = 95.0
N_DRAWS = 400
SEED = 0
SMOKE_DRAWS = 8


def estimator_shas() -> dict[str, str]:
    """SHA-256 of each estimator the gap runs through, by the rule ``calibrate_vflip``
    also uses: the estimator and everything it reaches in any jnwb module."""
    return {
        "vflip_from_lfp": _xflip_receipt.estimator_sha256(vflip_from_lfp),
        "vflip2_from_lfp": _xflip_receipt.estimator_sha256(vflip2_from_lfp),
    }


def gap_for_seed(seed: int) -> dict:
    """The open-gate crossovers and their gap, in contact spacings, of one null probe."""
    receipt = synth_laminar_motif(N_CONTACTS, N_SAMPLES, FS, c_crossover=C_CROSSOVER,
                                  pitch_um=PITCH_UM, snr=SNR_NULL,
                                  rng=np.random.default_rng(seed))
    first = vflip_from_lfp(receipt.lfp, FS, min_support_score=OPEN_GATE)
    second = vflip2_from_lfp(receipt.lfp, FS, contact_spacing=PITCH_UM,
                             omega_cut=OPEN_GATE)
    c1 = None if first.crossover_contact is None else float(first.crossover_contact)
    c2 = None if second.crossover_channel is None else float(second.crossover_channel)
    gap = abs(c2 - c1) if c1 is not None and c2 is not None else None
    return {"seed": seed, "vflip_contacts": c1, "vflip2_contacts": c2, "gap_contacts": gap}


def threshold(gaps: list[float]) -> float:
    """The 95th percentile of the defined gaps; NaN when no draw defines one."""
    return float(np.percentile(gaps, PERCENTILE)) if gaps else float("nan")


def run(rng: RNGLike = SEED, n_draws: int = N_DRAWS) -> dict:
    """Draw the null gap distribution: ``n_draws`` probes from successive children of
    the seeded ``rng``, and T, the 95th percentile of the defined gaps."""
    gen = resolve_rng(rng, func_name="calibrate_vflip2_separation")
    seeds = [int(gen.integers(0, 2**63 - 1)) for _ in range(n_draws)]
    trials = [gap_for_seed(seed) for seed in seeds]
    gaps = [t["gap_contacts"] for t in trials if t["gap_contacts"] is not None]
    ordered = sorted(gaps)
    return {
        "release": RELEASE,
        "declared_version": jnwb.__version__,
        "generator": GENERATOR,
        "fixed": {"n_contacts": N_CONTACTS, "n_samples": N_SAMPLES, "fs": FS,
                  "pitch_um": PITCH_UM, "c_crossover": C_CROSSOVER, "snr_null": SNR_NULL,
                  "vflip_min_support_score": OPEN_GATE, "vflip2_omega_cut": OPEN_GATE,
                  "percentile": PERCENTILE},
        "estimator": ["vflip_from_lfp", "vflip2_from_lfp"],
        "estimator_sha256": estimator_shas(),
        "n_draws": n_draws,
        "seeds": seeds,
        "trials": trials,
        "n_defined": len(gaps),
        "n_undefined": n_draws - len(gaps),
        "gap_median_contacts": (float(np.median(ordered)) if ordered else float("nan")),
        "gap_max_contacts": (float(ordered[-1]) if ordered else float("nan")),
        "threshold_contacts": threshold(gaps),
        "environment": {"jnwb": jnwb.__version__, "numpy": np.__version__,
                        "scipy": scipy.__version__, "python": platform.python_version(),
                        "platform": platform.platform()},
    }


def _finite_or_none(value):
    if isinstance(value, dict):
        return {key: _finite_or_none(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_or_none(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_raw(data, path) -> None:
    """Write ``data`` as strict JSON with LF endings. A non-finite float, such as an
    undefined gap, is written as null."""
    pathlib.Path(path).write_text(
        json.dumps(_finite_or_none(data), indent=1, allow_nan=False, default=str),
        encoding="utf-8", newline="\n")


def render(data: dict) -> str:
    env = data["environment"]
    fixed = data["fixed"]
    lines = [
        "# vFLIP-vFLIP2 separation agreement threshold (15-18)",
        "",
        (f"Qualifies release {data['release']}. Generated by "
         f"`python scripts/calibrate_vflip2_separation.py` from estimator SHA-256 "
         f"`{data['estimator_sha256']['vflip_from_lfp'][:16]}` (vFLIP) and "
         f"`{data['estimator_sha256']['vflip2_from_lfp'][:16]}` (vFLIP2); declared "
         f"package version {data['declared_version']} at generation; {data['n_draws']} "
         f"null draws. Environment: jnwb {env['jnwb']}, numpy {env['numpy']}, "
         f"scipy {env['scipy']}, Python {env['python']}."),
        "",
        "All recordings are synthetic: `jnwb.testing.synth_laminar_motif` at `snr=0` "
        "and no other generator. No project session is used.",
        "",
        "## Method",
        "",
        f"- Probe: {N_CONTACTS} contacts at fs {FS:g} Hz, pitch {PITCH_UM:g} um, "
        f"`c_crossover={C_CROSSOVER:g}` (immaterial at `snr=0`), `{N_SAMPLES}` samples "
        "per draw. Each draw comes from a successive child of the seeded `rng`, so one "
        "seed rebuilds the whole distribution.",
        "- Both estimators run with their acceptance gates open (`min_support_score` "
        f"and `omega_cut` at {OPEN_GATE:g}, finite, so no sentinel bypasses the "
        "acceptance logic). With the gates closed almost no null draw holds both "
        "crossovers, so the percentile would rest on a handful of joint acceptances; "
        "open, the gap is the structural-crossover disagreement on noise.",
        "- Gap: `|vflip2_crossover - vflip_crossover|` in contact spacings, the quantity "
        "`fuse_laminar_anchors` reports as `separation_contacts`. A draw where either "
        "crossover is structurally absent leaves the gap undefined and is counted, "
        "not filled in.",
        (f"- Threshold T: the {PERCENTILE:g}th percentile of the defined gaps, "
         f"`{data['threshold_contacts']:.4f}` contact spacings. `fuse_laminar_anchors` "
         "reads `'agree'` at or below T, `'disagree'` above it, and `'unresolved'` "
         "when the gap is undefined."),
        "",
        "## Result",
        "",
        f"- Draws: {data['n_draws']}; defined gaps {data['n_defined']}; undefined "
        f"{data['n_undefined']}.",
        f"- T (95th percentile): `{data['threshold_contacts']:.4f}` contact spacings.",
        f"- Median defined gap: `{data['gap_median_contacts']:.4f}`; largest: "
        f"`{data['gap_max_contacts']:.4f}`.",
        "",
        "## Fixed inputs",
        "",
        "| Argument | Value |",
        "|---|---|",
    ]
    for name, value in fixed.items():
        lines.append(f"| `{name}` | `{value}` |")
    lines += [
        "",
        "## Sources of the numbers",
        "",
        "- Gaps and T: recomputed from `trials` in the raw record; the percentile is "
        "`numpy.percentile` with its default linear interpolation.",
        "- Estimator code: the SHA-256 rule of `scripts/calibrate_xflip.py` that "
        "`scripts/calibrate_vflip.py` also uses (raw key `estimator_sha256`).",
        "- Declared version: `jnwb/__init__.py` (raw key `declared_version`); release "
        "set in `scripts/calibrate_vflip2_separation.py`.",
        "- Versions: raw key `environment`.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-draws", type=int, default=N_DRAWS)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--out", type=pathlib.Path, default=OUT_DIR,
                        help="receipt directory (default: artifacts/benchmarks/calibration)")
    parser.add_argument("--smoke", action="store_true",
                        help=f"{SMOKE_DRAWS} draws, for a quick check")
    args = parser.parse_args(argv)
    expected = pathlib.Path(os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") or ROOT).resolve()
    if expected not in pathlib.Path(jnwb.__file__).resolve().parents:
        raise SystemExit(f"jnwb was imported from {jnwb.__file__}, not from {expected}; "
                         "the receipt would describe other code")
    started = time.perf_counter()
    if args.smoke:
        data = run(args.seed, SMOKE_DRAWS)
        print(f"smoke: {data['n_draws']} draws, {data['n_defined']} defined, "
              f"T={data['threshold_contacts']:.4f} in {time.perf_counter() - started:.1f} s; "
              "no receipt written")
    else:
        data = run(args.seed, args.n_draws)
        args.out.mkdir(parents=True, exist_ok=True)
        write_raw(data, args.out / f"{STEM}_raw.json")
        (args.out / f"{STEM}.md").write_text(render(data), encoding="utf-8", newline="\n")
        print(f"wrote {STEM}.md and {STEM}_raw.json to {args.out}: {data['n_draws']} draws, "
              f"{data['n_defined']} defined in {time.perf_counter() - started:.1f} s; "
              f"T={data['threshold_contacts']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
