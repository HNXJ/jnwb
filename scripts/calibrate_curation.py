"""Regenerate the calibration receipt for the defaults of ``curate_and_label``.

    python scripts/calibrate_curation.py [--n-seeds 24] [--n-jobs -1] [--out DIR] [--smoke]

Each parameter in ``SWEPT`` moves alone to 0.5, 0.75, 1, 1.5 and 2 times its default, with every
other argument held. The probes come from ``jnwb.testing.synth_laminar_motif`` only; the null is
the same draws with ``snr=0``. A planted probe is recovered when its ``anchor_um`` lies within one
contact pitch of the truth, whatever its grade; a second column counts grades A to D only. A null
probe is accepted when it is graded A or B. ``--smoke`` runs 2 seeds and the first 2 parameters,
prints the result and writes nothing.

Writes ``curation_calibration_0.2.13.md`` and ``curation_calibration_0.2.13_raw.json`` to
``artifacts/benchmarks/calibration`` (or ``--out``). The JSON records a SHA-256 over the code
``curate_and_label`` reaches, computed by the rule of ``scripts/calibrate_xflip.py`` that
``scripts/calibrate_vflip.py`` also uses. ``tests/test_curation_calibration_receipt.py`` fails when
that code changes without this script being rerun. The script changes no default.
"""

from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import pathlib
import platform
import sys
import time
from collections import Counter

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
from jnwb._parallel import parallel_map  # noqa: E402
from jnwb.laminar_curation import curate_and_label  # noqa: E402
from jnwb.testing import synth_laminar_motif  # noqa: E402
from scripts import calibrate_xflip as _xflip_receipt  # noqa: E402

RELEASE = "0.2.13"
STEM = f"curation_calibration_{RELEASE}"
OUT_DIR = ROOT / "artifacts" / "benchmarks" / "calibration"
GENERATOR = "jnwb.testing.synth_laminar_motif"
GENERATOR_ARGS = ("orientation", "gamma_freq", "beta_freq")  # left at the generator's defaults
FS = 1000.0
PITCH_UM = 100.0
N_CONTACTS = 32
N_EPOCHS = 40
N_SAMPLES = 1000
SNR = 20.0  # the recoverable-alternative SNR of scripts/calibrate_vflip.py (ALT_SNR)
Z0_RANGE = (10, 21)  # contacts, both ends included
RECOVERY_TOL_UM = PITCH_UM  # one contact pitch, bound included
ACCEPTED_GRADES = ("A", "B")
RECOVERY_GRADES = ("A", "B", "C", "D")  # the second recovery column counts these grades only
FACTORS = (0.5, 0.75, 1.0, 1.5, 2.0)
SWEPT = (
    "n_windows",
    "granular_thickness_um",
    "silent_threshold",
    "smooth_um",
    "min_lobe_um",
    "min_lobe_amplitude",
    "bad_zone_contacts",
    "bad_zone_fraction",
    "edge_fraction",
    "edge_jump_z",
    "stable_sd_um",
    "min_ok_windows",
    "consistency_a",
    "consistency_b",
    "max_interpolate_run",
)
#: Parameters that are fractions; a scaled value is clipped to at most 1.0.
FRACTIONS = ("bad_zone_fraction", "edge_fraction", "consistency_a", "consistency_b")
SMOKE_SEEDS = 2
SMOKE_PARAMS = 2
NULL_MEANS = (
    "null anchor_um: NaN, no anchor from the library; "
    "null truth_um: a null probe; null param and value: the "
    "default run; null recovered and recovered_ad: a null probe; "
    "null refused: the trial was measured; a NaN or "
    "infinite float is written as null"
)


def estimator_sources() -> list[tuple[str, str]]:
    """``curate_and_label`` and every top-level function, class and constant it reaches in any
    jnwb module, as code only."""
    return _xflip_receipt.estimator_sources(curate_and_label)


def estimator_sha256() -> str:
    return _xflip_receipt.estimator_sha256(curate_and_label)


def _probe(seed: int, planted: bool) -> tuple[float, float, np.ndarray]:
    """The crossover contact, its depth in um from the generator's receipt, and the
    (contacts, epochs, samples) recording of one probe. Each epoch is one successive draw of
    ``synth_laminar_motif`` from the seed's generator."""
    gen = np.random.default_rng(seed)
    z0 = int(gen.integers(Z0_RANGE[0], Z0_RANGE[1] + 1))
    snr = SNR if planted else 0.0
    receipts = [synth_laminar_motif(N_CONTACTS, N_SAMPLES, FS, c_crossover=float(z0),
                                    pitch_um=PITCH_UM, snr=snr, rng=gen)
                for _ in range(N_EPOCHS)]
    epochs = [receipt.lfp for receipt in receipts]
    return (receipts[0].crossover_contact, receipts[0].crossover_depth_um,
            np.ascontiguousarray(np.transpose(np.array(epochs), (1, 0, 2))))


def _run_one(job: tuple) -> dict:
    """One trial: a probe through ``curate_and_label`` with one argument moved, or none."""
    name, value, seed, planted = job
    contact, depth, lfp = _probe(seed, planted)
    truth = depth if planted else None
    keys = {"param": name, "value": value, "seed": seed, "planted": planted,
            "z0": int(contact), "crossover_contact": contact, "crossover_depth_um": depth,
            "truth_um": truth}
    kwargs = {} if name is None else {name: value}
    try:
        res = curate_and_label(lfp, FS, pitch_um=PITCH_UM, compute_xflip=False, **kwargs)
    except ValueError as exc:
        return {**keys, "refused": str(exc), "anchor_um": None, "anchor_source": None,
                "grade": None, "recovered": None, "recovered_ad": None, "graded_ab": None}
    anchor = float(res.anchor_um) if np.isfinite(res.anchor_um) else None
    recovered = None if truth is None else (
        anchor is not None and abs(anchor - truth) <= RECOVERY_TOL_UM)
    recovered_ad = None if recovered is None else (recovered and res.grade in RECOVERY_GRADES)
    return {**keys, "refused": None, "anchor_um": anchor, "anchor_source": res.anchor_source,
            "grade": res.grade, "recovered": recovered, "recovered_ad": recovered_ad,
            "graded_ab": res.grade in ACCEPTED_GRADES}


def interval(k: int, n: int) -> list:
    """The exact two-sided 95% Clopper-Pearson interval, ``[low, high]``, for ``k`` of ``n``."""
    low, high = jnwb.clopper_pearson(k, n)
    return [float(low), float(high)]


def scaled(name: str, default, factor: float):
    """``default`` times ``factor``. An int rounds to the nearest int with Python's ``round``, which
    sends a tie to the even integer (as ``scripts/calibrate_vflip.py`` rounds), and is held at
    least 1. A name in ``FRACTIONS`` is clipped to at most 1.0; other floats are not clipped."""
    if isinstance(default, int) and not isinstance(default, bool):
        return max(1, int(round(default * factor)))
    if name in FRACTIONS:
        return min(1.0, float(default * factor))
    return float(default * factor)


def sweep_points(name: str, default) -> list:
    """``(factor, value)`` for each distinct sweep value, in factor order. The default is always
    the x1 row. Any other value equal to the default, or already listed, is dropped, so each value
    keeps the first factor that gives it."""
    points = [(1.0, default)]
    for factor in FACTORS:
        if factor == 1.0:
            continue
        value = scaled(name, default, factor)
        if value != default and value not in [v for _, v in points]:
            points.append((factor, value))
    return sorted(points, key=lambda point: FACTORS.index(point[0]))


def _overlap(a: list, b: list) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def stable_range(rows: list) -> dict:
    """The values whose recovery interval overlaps the interval of the highest-recovery value, and
    whose acceptance interval overlaps the default's. A default outside them is flagged."""
    measured = [row for row in rows if not row["refusals"]]
    best = max(measured, key=lambda row: row["k_recovered"])
    default = next(row for row in measured if row["is_default"])
    stable = [row["value"] for row in measured
              if _overlap(row["recovery_ci"], best["recovery_ci"])
              and _overlap(row["acceptance_ci"], default["acceptance_ci"])]
    return {"best_value": best["value"], "stable_values": stable,
            "flagged": default["value"] not in stable}


def _rows(name: str, points: list, default_trials: list, grouped: dict) -> list:
    rows = []
    for factor, value in points:
        group = default_trials if factor == 1.0 else grouped[(name, value)]
        planted = [t for t in group if t["planted"]]
        null = [t for t in group if not t["planted"]]
        failures = [t["refused"] for t in group if t["refused"] is not None]
        row = {"factor": factor, "value": value, "is_default": factor == 1.0,
               "n_planted": len(planted), "n_null": len(null), "n_refused": len(failures),
               "refusals": sorted(set(failures))}
        if not failures:
            k_rec = sum(1 for t in planted if t["recovered"])
            k_rec_ad = sum(1 for t in planted if t["recovered_ad"])
            k_acc = sum(1 for t in null if t["graded_ab"])
            row.update(k_recovered=k_rec, recovery_ci=interval(k_rec, len(planted)),
                       k_recovered_ad=k_rec_ad, recovery_ad_ci=interval(k_rec_ad, len(planted)),
                       k_accepted=k_acc, acceptance_ci=interval(k_acc, len(null)))
        rows.append(row)
    return rows


def offset_distribution(trials: list) -> dict:
    """Anchor offsets, ``anchor_um - truth_um``, of the planted trials that gave an anchor, with
    the counts the receipt states. Nothing is removed, fitted or tuned."""
    planted = [t for t in trials if t["planted"] and t["refused"] is None]
    anchored = [t for t in planted if t["anchor_um"] is not None]
    offsets = np.array([t["anchor_um"] - t["truth_um"] for t in anchored], dtype=float)
    within = [t for t in anchored if abs(t["anchor_um"] - t["truth_um"]) <= RECOVERY_TOL_UM]
    out = {"n_planted": len(planted), "n_anchor": len(anchored), "n_recovered": len(within),
           "n_recovered_ad": sum(1 for t in within if t["grade"] in RECOVERY_GRADES),
           "n_positive": int(np.sum(offsets > 0)), "n_negative": int(np.sum(offsets < 0)),
           "n_grade_f": sum(1 for t in anchored if t["grade"] == "F")}
    if anchored:
        q25, median, q75 = (float(q) for q in np.percentile(offsets, [25, 50, 75]))
        out.update(mean_um=float(offsets.mean()),
                   sd_um=float(offsets.std(ddof=1)) if len(anchored) > 1 else math.nan,
                   min_um=float(offsets.min()), q25_um=q25, median_um=median, q75_um=q75,
                   max_um=float(offsets.max()))
    else:
        out.update(mean_um=math.nan, sd_um=math.nan, min_um=math.nan, q25_um=math.nan,
                   median_um=math.nan, q75_um=math.nan, max_um=math.nan)
    return out


def _generator_defaults() -> dict:
    """The generator arguments this script leaves at their signature defaults."""
    parameters = inspect.signature(synth_laminar_motif).parameters
    return {name: parameters[name].default for name in GENERATOR_ARGS}


def _held_inputs() -> dict:
    """Each argument of ``curate_and_label`` that is not swept, with its signature default.
    ``pitch_um`` and ``compute_xflip`` are fixed by this script."""
    held = {}
    for name, param in inspect.signature(curate_and_label).parameters.items():
        if name in ("lfp", "fs") or name in SWEPT or param.kind is inspect.Parameter.VAR_KEYWORD:
            continue
        if name == "pitch_um":
            held[name] = PITCH_UM
        elif name == "compute_xflip":
            held[name] = False
        else:
            held[name] = param.default
    return held


def run(n_seeds: int, n_jobs: int, params: tuple) -> dict:
    parameters = inspect.signature(curate_and_label).parameters
    defaults = {name: parameters[name].default for name in params}
    points = {name: sweep_points(name, defaults[name]) for name in params}
    seeds = list(range(n_seeds))
    jobs = [(None, None, seed, planted) for seed in seeds for planted in (True, False)]
    for name in params:
        for factor, value in points[name]:
            if factor != 1.0:
                jobs += [(name, value, seed, planted) for seed in seeds for planted in (True, False)]
    trials = parallel_map(_run_one, jobs, n_jobs=n_jobs)
    default_trials = [t for t in trials if t["param"] is None]
    refused = [t["refused"] for t in default_trials if t["refused"] is not None]
    if refused:
        raise RuntimeError(f"the default run was refused, so the probe layout is wrong: {refused[0]}")
    grouped: dict = {}
    for t in trials:
        if t["param"] is not None:
            grouped.setdefault((t["param"], t["value"]), []).append(t)
    summary = {}
    for name in params:
        rows = _rows(name, points[name], default_trials, grouped)
        summary[name] = {"rows": rows, **stable_range(rows)}
    return {
        "release": RELEASE,
        "declared_version": jnwb.__version__,
        "estimator": "curate_and_label",
        "estimator_sha256": estimator_sha256(),
        "estimator_functions": [name for name, _ in estimator_sources()],
        "n_seeds": n_seeds,
        "seeds": seeds,
        "params": list(params),
        "defaults": defaults,
        "sweep": {name: [{"factor": f, "value": v} for f, v in points[name]] for name in params},
        "held": _held_inputs(),
        "fixed": {"fs": FS, "pitch_um": PITCH_UM, "compute_xflip": False,
                  "n_contacts": N_CONTACTS, "n_epochs": N_EPOCHS, "n_samples": N_SAMPLES,
                  "snr_planted": SNR, "snr_null": 0.0, "z0_range": list(Z0_RANGE),
                  "generator": GENERATOR, "generator_defaults": _generator_defaults()},
        "recovery_tolerance_um": RECOVERY_TOL_UM,
        "accepted_grades": list(ACCEPTED_GRADES),
        "null_means": NULL_MEANS,
        "summary": summary,
        "flagged": [name for name in params if summary[name]["flagged"]],
        "offsets": offset_distribution(default_trials),
        "recovery_grades": list(RECOVERY_GRADES),
        "trials": trials,
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
    """Write ``data`` as strict JSON with LF endings. A non-finite float, such as a NaN anchor,
    is written as null; ``null_means`` in the record says what null stands for."""
    pathlib.Path(path).write_text(
        json.dumps(_finite_or_none(data), indent=1, allow_nan=False, default=str),
        encoding="utf-8", newline="\n")


def _ci(ci: list) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def _num(value: float) -> str:
    return "n/a" if math.isnan(value) else f"{value:.1f}"


def render(data: dict) -> str:
    env = data["environment"]
    trials = data["trials"]
    n_planted = sum(1 for t in trials if t["planted"])
    n_refused = sum(row["n_refused"] for name in data["params"]
                    for row in data["summary"][name]["rows"])
    flag_text = ", ".join(f"`{name}`" for name in data["flagged"]) or "none"
    counts = ("k_recovered", "k_recovered_ad", "k_accepted")
    unmoved = [name for name, summary in data["summary"].items()
               if len({tuple(row[k] for k in counts) for row in summary["rows"]}) == 1]
    at_default = Counter(str(t.get("anchor_source")) for t in trials
                         if t["planted"] and t["param"] is None and not t["refused"])
    sources = ", ".join(f"{name} {n}" for name, n in sorted(at_default.items())) or "none"
    lines = [
        "# Curation calibration: defaults of `curate_and_label`",
        "",
        (f"Qualifies release {data['release']}. Generated by `python scripts/calibrate_curation.py` "
         f"from estimator SHA-256 `{data['estimator_sha256'][:16]}`; declared package version "
         f"{data['declared_version']} at generation; {data['n_seeds']} seeds per cell; "
         f"{len(trials)} trials. Environment: jnwb {env['jnwb']}, numpy {env['numpy']}, "
         f"scipy {env['scipy']}, Python {env['python']}."),
        "",
        "All recordings are synthetic: `jnwb.testing.synth_laminar_motif` and its null. "
        "No project session is used.",
        "",
        "## Method",
        "",
        "- Probe: 32 contacts at fs 1000 Hz, pitch 100 um. `jnwb.testing.synth_laminar_motif` is "
        "called with `c_crossover` equal to the crossover contact `z0`, which is drawn uniformly "
        "from 10 to 21, both ends included, from the seed's generator. The planted probe has "
        f"`snr={SNR:g}`; the null is the same draws with `snr=0`, so it shares the planted probe's "
        "background and sources. The other generator arguments are at their defaults ("
        + ", ".join(f"`{name}` {value}" for name, value in data["fixed"]["generator_defaults"].items())
        + "), with no bad channels.",
        f"- Planted SNR: {SNR:g}, the `ALT_SNR` of `scripts/calibrate_vflip.py`. vFLIP's median error "
        "at that SNR is 1.23 contacts (`artifacts/benchmarks/calibration/vflip_calibration_0.2.4.md`, "
        "SNR sweep). That is a reference for vFLIP's own calibration, not a bound on the anchor here.",
        "- Epoch layout: `curate_and_label` takes (channels, epochs, samples), and the generator "
        "returns (channels, samples). Each probe is therefore 40 epochs of 1000 samples, each one "
        "successive draw of the generator at the probe's `z0` and `snr`, as in "
        "`tests/test_laminar_curation.py` (`synth`: `n_ep=40`, `n_s=1000`).",
        "- Truth: `crossover_depth_um` in the generator's receipt, which is `crossover_contact` "
        "times the pitch. `anchor_um` is `crossover_contact * pitch` "
        "(`jnwb/laminar_curation.py:957`). `crossover_contact` is a 0-based row index "
        "(`jnwb/laminar/_vflip.py:639-653`); the generator's band weights are 0.5 and 0.5 at the "
        "crossover contact (`jnwb/testing/synth.py`, `synth_laminar_motif`). Positions run from the "
        "first contact, with no half-pitch offset.",
        "- Recovery: `|anchor_um - truth_um| <= 100` um, one pitch with the bound included. A "
        "NaN anchor is not recovered. The grade does not enter this column: a grade F anchor is "
        "the motif crossing, kept with no claim on it, and counts here when it lies within the "
        "tolerance. The second recovery column counts only grades A to D. False acceptance: a null "
        "probe graded A or B.",
        "- Intervals: exact two-sided 95% Clopper-Pearson, `jnwb.clopper_pearson`.",
        "- Sweep: each parameter alone at its default times 0.5, 0.75, 1, 1.5 and 2, with every "
        "other argument at default. An int default rounds to the nearest int with Python's `round`, "
        "which sends a tie to the even integer, as `scripts/calibrate_vflip.py` rounds; it is held "
        "at least 1. A fraction is clipped to at most 1.0. A value equal to the default, or already "
        "listed, is dropped, so the default is always the x1 row.",
        "- Refusal: a value whose trial raises `ValueError` is recorded as refused, with the message, "
        "and has no rates.",
        "- Stable range: the values whose recovery interval overlaps the interval of the "
        "highest-recovery value, and whose false-acceptance interval overlaps the default's. A "
        "default outside its stable range is FLAGGED. The script changes no default.",
        "",
        "## Held inputs",
        "",
        "| Argument | Value | Source |",
        "|---|---|---|",
    ]
    for name, value in data["held"].items():
        source = ("fixed by this script" if name in ("pitch_um", "compute_xflip")
                  else "signature default")
        lines.append(f"| `{name}` | `{value}` | {source} |")
    lines += [
        "",
        "## Result",
        "",
        f"- Trials: {len(trials)}; planted {n_planted}, null {len(trials) - n_planted}; "
        f"refused {n_refused}.",
        f"- FLAGGED: {flag_text}.",
        f"- Parameters whose every swept value gives the default's three counts: "
        f"{len(unmoved)} of {len(data['summary'])}.",
        f"- Anchor source of the planted probes at the defaults: {sources}.",
        "",
        "## FLAGGED rows",
        "",
    ]
    if data["flagged"]:
        lines += ["| Parameter | Default | Highest-recovery value | Stable values |",
                  "|---|---|---|---|"]
        for name in data["flagged"]:
            summary = data["summary"][name]
            stable = ", ".join(str(v) for v in summary["stable_values"])
            lines.append(f"| `{name}` | {data['defaults'][name]} | {summary['best_value']} | "
                         f"{stable} |")
    else:
        lines.append("No default lies outside its stable range.")
    offsets = data["offsets"]
    lines += [
        "",
        "## Offsets of planted anchors at defaults",
        "",
        "Anchor minus truth, um, for each planted probe at the default arguments that gave an "
        "anchor. Nothing is removed, fitted or tuned.",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| Planted probes, not refused | {offsets['n_planted']} |",
        f"| With an anchor | {offsets['n_anchor']} |",
        f"| Within one pitch, any grade | {offsets['n_recovered']} |",
        f"| Within one pitch, grades A to D | {offsets['n_recovered_ad']} |",
        f"| Above truth; below truth | {offsets['n_positive']}; {offsets['n_negative']} |",
        f"| Grade F anchors | {offsets['n_grade_f']} |",
        f"| Mean; SD, um | {_num(offsets['mean_um'])}; {_num(offsets['sd_um'])} |",
        "| Minimum; 25%; median; 75%; maximum, um | "
        f"{_num(offsets['min_um'])}; {_num(offsets['q25_um'])}; {_num(offsets['median_um'])}; "
        f"{_num(offsets['q75_um'])}; {_num(offsets['max_um'])} |",
    ]
    for name in data["params"]:
        summary = data["summary"][name]
        stable = set(summary["stable_values"])
        lines += ["", f"### `{name}` (default {data['defaults'][name]})", "",
                  "| x | value | planted: recovered (95% CI) | planted: recovered, grades A to D "
                  "(95% CI) | null: graded A or B (95% CI) | stable | note |",
                  "|---|---|---|---|---|---|---|"]
        for row in summary["rows"]:
            if row["refusals"]:
                lines.append(f"| {row['factor']:g} | {row['value']} | refused | refused | refused | - | "
                             f"{row['n_refused']} trials refused: {'; '.join(row['refusals'])} |")
                continue
            note = "default" if row["is_default"] else ""
            if row["is_default"] and summary["flagged"]:
                note = "default; FLAGGED"
            lines.append(
                f"| {row['factor']:g} | {row['value']} | "
                f"{row['k_recovered']}/{row['n_planted']} {_ci(row['recovery_ci'])} | "
                f"{row['k_recovered_ad']}/{row['n_planted']} {_ci(row['recovery_ad_ci'])} | "
                f"{row['k_accepted']}/{row['n_null']} {_ci(row['acceptance_ci'])} | "
                f"{'yes' if row['value'] in stable else 'no'} | {note} |")
    lines += [
        "",
        "## Sources of the numbers",
        "",
        "- Defaults and held inputs: `inspect.signature(curate_and_label)`, read at run time "
        "(`jnwb/laminar_curation.py:672`; raw keys `defaults` and `held`).",
        "- Factors, seeds, epoch and sample counts, `z0` range, pitch, fs, snr, recovery tolerance "
        "and accepted grades: constants of `scripts/calibrate_curation.py` (raw key `fixed`). The "
        "generator and its defaults: `inspect.signature(synth_laminar_motif)`, read at run time "
        "(raw keys `fixed.generator` and `fixed.generator_defaults`).",
        "- Counts and rates: recomputed from `trials` in the raw record; intervals by "
        "`jnwb.clopper_pearson`.",
        "- Offsets and the second recovery column: raw keys `offsets`, `recovery_grades` and "
        "`recovery_tolerance_um`; the offsets come from the planted default trials, by "
        "`offset_distribution`.",
        "- Truth and anchor: `jnwb/laminar_curation.py:957`, `jnwb/laminar/_vflip.py:639-653`, "
        "`jnwb/testing/synth.py` (`synth_laminar_motif`).",
        "- Planted and null probes: `jnwb/testing/synth.py` (`synth_laminar_motif`).",
        "- Epoch layout: `tests/test_laminar_curation.py:30`.",
        "- Hash: `scripts/calibrate_xflip.py`, `estimator_sha256`, the rule that "
        "`scripts/calibrate_vflip.py` also uses.",
        "- Declared version: `jnwb/__init__.py:14` (raw key `declared_version`); release set in "
        "`scripts/calibrate_curation.py`.",
        "- Versions: raw key `environment`.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-seeds", type=int, default=24)
    parser.add_argument("--n-jobs", type=int, default=-1)
    parser.add_argument("--out", type=pathlib.Path, default=OUT_DIR,
                        help="receipt directory (default: artifacts/benchmarks/calibration)")
    parser.add_argument("--smoke", action="store_true",
                        help="2 seeds and the first 2 parameters, for a quick check")
    args = parser.parse_args(argv)
    expected = pathlib.Path(os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT") or ROOT).resolve()
    if expected not in pathlib.Path(jnwb.__file__).resolve().parents:
        raise SystemExit(f"jnwb was imported from {jnwb.__file__}, not from {expected}; "
                         "the receipt would describe other code")
    started = time.perf_counter()
    if args.smoke:
        n_seeds, params = SMOKE_SEEDS, SWEPT[:SMOKE_PARAMS]
    else:
        n_seeds, params = args.n_seeds, SWEPT
    data = run(n_seeds, args.n_jobs, params)
    if args.smoke:
        print(f"smoke: {len(data['trials'])} trials in {time.perf_counter() - started:.1f} s; "
              f"estimator {data['estimator_sha256'][:16]}; no receipt written")
    else:
        args.out.mkdir(parents=True, exist_ok=True)
        write_raw(data, args.out / f"{STEM}_raw.json")
        (args.out / f"{STEM}.md").write_text(render(data), encoding="utf-8", newline="\n")
        print(f"wrote {STEM}.md and {STEM}_raw.json to {args.out}: {len(data['trials'])} trials "
              f"in {time.perf_counter() - started:.1f} s; estimator {data['estimator_sha256'][:16]}")
    print(f"FLAGGED: {', '.join(data['flagged']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
