"""Regenerate the calibration receipt for the defaults of ``curate_and_label``.

    python scripts/calibrate_curation.py [--n-seeds 24] [--n-jobs -1] [--out DIR] [--smoke]

Each parameter in ``SWEPT`` moves alone to 0.5, 0.75, 1, 1.5 and 2 times its default, with every
other argument held. The probes come from ``jnwb.testing.synth_laminar_motif`` only; the null is
the same draws with ``snr=0``. A planted probe is recovered when its ``anchor_um`` lies within one
contact pitch of the truth, whatever its grade; a second column counts grades A to D only. A null
probe is accepted when it is graded A or B. ``--smoke`` runs 2 seeds and the first 2 parameters,
prints the result and writes nothing.

Every swept parameter runs on the probe family that plants what it decides, not on the plain
probe: the plain probe leaves all three counts at the default's (15 of 15 in the 0.2.13 receipt),
so the sweep places no default. Each family applies one rule of plant to the generator's draws, on
the planted and the null probe alike, and contributes one count the receipt checks for
movement: ``steady`` (snr 400) for ``n_windows``, ``stable_sd_um``, ``min_ok_windows`` and
``granular_thickness_um`` (grades, then input labels); ``edge`` (an anti-correlated contact pair at -0.3)
for ``edge_fraction`` and ``edge_jump_z`` (contacts outside cortex); ``lobe`` (a balanced spectral
wiggle each side of the crossover) for ``smooth_um``, ``min_lobe_um`` and ``min_lobe_amplitude``
(motif crossings); ``silent`` (two bands killed on the top three contacts) for
``silent_threshold`` (contacts outside cortex); ``consistency_a`` and ``consistency_b`` (a partial
low-band kill on the first contacts the defaults label deep in that probe, tuned so the deep
consistency straddles the threshold) for the two consistency grades; ``dead`` (three zeroed
contacts) for ``bad_zone_contacts``, ``bad_zone_fraction`` and ``max_interpolate_run`` (unusable
contacts). A parameter no value of whose family moves any count is named in the receipt with the
counts and the trial total it was read over.

Writes ``curation_calibration_0.2.14.md`` and ``curation_calibration_0.2.14_raw.json`` to
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

from scipy import signal

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

RELEASE = "0.2.14"
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
#: Every swept parameter runs on the probe family that plants what it decides.
FAMILY_OF = {
    "n_windows": "steady",
    "granular_thickness_um": "steady",
    "silent_threshold": "silent",
    "smooth_um": "lobe",
    "min_lobe_um": "lobe",
    "min_lobe_amplitude": "lobe",
    "bad_zone_contacts": "dead",
    "bad_zone_fraction": "dead",
    "edge_fraction": "edge",
    "edge_jump_z": "edge",
    "stable_sd_um": "steady",
    "min_ok_windows": "steady",
    "consistency_a": "consistency_a",
    "consistency_b": "consistency_b",
    "max_interpolate_run": "dead",
}
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


def _draws(seed: int, snr: float) -> tuple:
    """The crossover contact and depth, and the (contacts, epochs, samples) recording of one
    probe. Each epoch is one successive draw of ``synth_laminar_motif`` from the seed's
    generator, so the planted and the null probe share their draws."""
    gen = np.random.default_rng(seed)
    z0 = int(gen.integers(Z0_RANGE[0], Z0_RANGE[1] + 1))
    receipts = [synth_laminar_motif(N_CONTACTS, N_SAMPLES, FS, c_crossover=float(z0),
                                    pitch_um=PITCH_UM, snr=snr, rng=gen)
                for _ in range(N_EPOCHS)]
    epochs = [receipt.lfp for receipt in receipts]
    return (gen, z0, receipts[0].crossover_contact, receipts[0].crossover_depth_um,
            np.ascontiguousarray(np.transpose(np.array(epochs), (1, 0, 2))))


def _anticorrelate(lfp: np.ndarray, a: int, b: int, c: float) -> np.ndarray:
    """A copy of ``lfp`` with the correlation of contacts ``a`` and ``b`` planted at ``-c``,
    holding the variance of ``b``."""
    out = lfp.copy()
    s1 = float(np.abs(out[a]).mean()) + 1e-12
    s2 = float(np.abs(out[b]).mean()) + 1e-12
    out[b] = -c * (s2 / s1) * out[a] + np.sqrt(1 - c * c) * out[b]
    return out


def _sine(freq: float, mult: float, ref: np.ndarray) -> np.ndarray:
    t = np.arange(N_SAMPLES) / FS
    return mult * float(np.abs(ref).mean()) * np.sin(2 * np.pi * freq * t)


def _bandkill(x: np.ndarray, lo: float, hi: float, f: float) -> np.ndarray:
    sos = signal.butter(4, [lo / (FS / 2), hi / (FS / 2)], btype="band", output="sos")
    return x - f * signal.sosfiltfilt(sos, x, axis=-1)


def _probe(seed: int, planted: bool, family: str = "plain") -> tuple[float, float, np.ndarray]:
    """The crossover contact, its depth in um from the generator's receipt, and the
    (contacts, epochs, samples) recording of one probe of ``family``.

    ``steady`` is the same draws at snr 400; ``edge`` anti-correlates contacts 1 and 2 at
    -0.3; ``lobe`` adds a 120 Hz wiggle above the crossover and an 18 Hz wiggle below it;
    ``silent`` kills both motif bands on the top three contacts; ``consistency_a`` and
    ``consistency_b`` kill part of the low band on deep contacts, tuned so the deep consistency
    straddles the grade threshold; ``dead`` zeroes contacts 10 to 12.
    Each rule applies to the planted and the null probe alike; the consistency kill picks the
    deep contacts from that probe's own labels at the defaults."""
    snr = SNR if planted else 0.0
    if family in ("steady", "consistency_a", "consistency_b"):
        snr = 400.0 if planted else 0.0
    _, z0, contact, depth, lfp = _draws(seed, snr)
    if family == "edge":
        lfp = _anticorrelate(lfp, 1, 2, 0.3)
    elif family == "lobe":
        w = _sine(120.0, 1.5, lfp[z0 + 1])
        for c in (z0 + 1, z0 + 2):
            lfp[c] = lfp[c] + w[None, :]
        w = _sine(18.0, 1.5, lfp[z0 - 1])
        for c in (z0 - 2, z0 - 1):
            lfp[c] = lfp[c] + w[None, :]
    elif family == "silent":
        for c in range(3):
            lfp[c] = _bandkill(_bandkill(lfp[c], 10.0, 19.0, 0.3), 75.0, 150.0, 0.3)
    elif family in ("consistency_a", "consistency_b"):
        deep = [i for i, lab in enumerate(
            curate_and_label(lfp, FS, pitch_um=PITCH_UM, compute_xflip=False).labels)
            if lab == "deep"]
        for i in deep[:3 if family == "consistency_a" else 5]:
            lfp[i] = _bandkill(lfp[i], 10.0, 19.0, 0.5 if family == "consistency_a" else 0.6)
    elif family == "dead":
        lfp[10:13] = 0.0
    return (contact, depth, lfp)


def _run_one(job: tuple) -> dict:
    """One trial: a probe of the parameter's family through ``curate_and_label`` with one
    argument moved, or none. The trial records the family and the counts its plant moves:
    grades, contacts outside cortex, input contacts, unusable and interpolated contacts, and
    motif crossings."""
    name, value, seed, planted = job
    family = "plain" if name is None else FAMILY_OF[name]
    contact, depth, lfp = _probe(seed, planted, family)
    truth = depth if planted else None
    keys = {"param": name, "value": value, "seed": seed, "planted": planted,
            "family": family,
            "z0": int(contact), "crossover_contact": contact, "crossover_depth_um": depth,
            "truth_um": truth}
    kwargs = {} if name is None else {name: value}
    try:
        res = curate_and_label(lfp, FS, pitch_um=PITCH_UM, compute_xflip=False, **kwargs)
    except ValueError as exc:
        return {**keys, "refused": str(exc), "anchor_um": None, "anchor_source": None,
                "grade": None, "recovered": None, "recovered_ad": None, "graded_ab": None,
                "n_outside": None, "n_input": None, "n_unusable": None,
                "n_interpolated": None, "n_crossings": None}
    anchor = float(res.anchor_um) if np.isfinite(res.anchor_um) else None
    recovered = None if truth is None else (
        anchor is not None and abs(anchor - truth) <= RECOVERY_TOL_UM)
    recovered_ad = None if recovered is None else (recovered and res.grade in RECOVERY_GRADES)
    labels = np.asarray(res.labels)
    return {**keys, "refused": None, "anchor_um": anchor, "anchor_source": res.anchor_source,
            "grade": res.grade, "recovered": recovered, "recovered_ad": recovered_ad,
            "graded_ab": res.grade in ACCEPTED_GRADES,
            "n_outside": int((labels == "outside_cortex").sum()),
            "n_input": int((labels == "input").sum()),
            "n_unusable": int(np.asarray(res.unusable_mask).sum()),
            "n_interpolated": int(np.asarray(res.interpolated_mask).sum()),
            "n_crossings": int(res.n_crossings)}


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


#: Trial counts the families contribute, summed over a row's group.
FAMILY_COUNTS = ("n_outside", "n_input", "n_unusable", "n_interpolated", "n_crossings")


def _overlap(a: list, b: list) -> bool:
    return a[0] <= b[1] and b[0] <= a[1]


def _signature(row: dict) -> tuple:
    """Everything a swept value can move: the three rate counts, the grade histogram, and
    the family counts. Two rows with equal signatures moved nothing."""
    return (row.get("k_recovered"), row.get("k_recovered_ad"), row.get("k_accepted"),
            tuple(sorted(row.get("grades", {}).items())),
            tuple(row.get("counts", {}).get(k) for k in FAMILY_COUNTS),
            bool(row["refusals"]))


def _unreached_reason(summary: dict) -> str:
    """What the sweep measured for a parameter no swept value moved: how many values, over how
    many trials each, and the default's counts every one of them reproduced."""
    rows = summary["rows"]
    default = next(row for row in rows if row["is_default"])
    counts = ", ".join(f"{k} {default.get('counts', {}).get(k)}" for k in FAMILY_COUNTS)
    grades = ", ".join(f"{g} {n}" for g, n in sorted(default.get("grades", {}).items()))
    return (f"{len(rows) - 1} swept values on the {summary['family']} plant, "
            f"{default['n_planted']} planted and {default['n_null']} null trials each, all give the "
            f"default's counts (grades {grades or 'none'}; {counts})")


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
            measured = [t for t in group if t["refused"] is None]
            grades = dict(Counter(t["grade"] for t in measured))
            counts = {k: sum(t[k] for t in measured) for k in FAMILY_COUNTS}
            row.update(k_recovered=k_rec, recovery_ci=interval(k_rec, len(planted)),
                       k_recovered_ad=k_rec_ad, recovery_ad_ci=interval(k_rec_ad, len(planted)),
                       k_accepted=k_acc, acceptance_ci=interval(k_acc, len(null)),
                       grades=grades, counts=counts)
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
        default = next(row for row in rows if row["is_default"])
        default_sig = _signature(default)
        moved = [row["value"] for row in rows if not row["is_default"]
                 and _signature(row) != default_sig]
        summary[name] = {"rows": rows, "family": FAMILY_OF[name],
                         "moved": bool(moved), "moved_values": moved,
                         **stable_range(rows)}
    unreached = {name: _unreached_reason(summary[name]) for name in params
                 if not summary[name]["moved"]}
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
        "families": {name: FAMILY_OF[name] for name in params},
        "unreached": unreached,
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
        "- Probe families: each parameter runs on the plant that decides it, the same plant on "
        "the planted and the null probe. `steady` is snr 400 for `n_windows`, `stable_sd_um`, "
        "`min_ok_windows` and `granular_thickness_um`; `edge` anti-correlates contacts 1 and 2 "
        "at -0.3 for `edge_fraction` and `edge_jump_z`; `lobe` adds a 120 Hz wiggle above the "
        "crossover and an 18 Hz wiggle below it for `smooth_um`, `min_lobe_um` and "
        "`min_lobe_amplitude`; `silent` kills both motif bands on the top three contacts for "
        "`silent_threshold`; `consistency_a` and `consistency_b` kill part of the low band on "
        "deep contacts for the two consistency grades; `dead` zeroes contacts 10 to 12 for "
        "`bad_zone_contacts`, `bad_zone_fraction` and `max_interpolate_run`. Every trial also "
        "records its grades, contacts outside cortex, input contacts, unusable and interpolated "
        "contacts, and motif crossings; a swept value moves its default when any of these, or "
        "of the three rate counts, differs from the default's. A default no value moves is "
        "named below with the reason.",
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
        f"- Parameters no swept value moves on their family: "
        f"{', '.join(f'`{name}`' for name in data['unreached']) or 'none'}.",
        f"- Anchor source of the planted probes at the defaults: {sources}.",
        "",
        "## Defaults no plant reaches",
        "",
    ]
    if data["unreached"]:
        lines += ["| Parameter | Family | Reason |", "|---|---|---|"]
        for name, reason in data["unreached"].items():
            lines.append(f"| `{name}` | {data['families'][name]} | {reason} |")
    else:
        lines.append("Every default is moved by a swept value on its family's plant.")
    lines += [
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
        lines += ["", f"### `{name}` (default {data['defaults'][name]}, family {summary['family']})",
                  "",
                  f"Moved values: "
                  f"{', '.join(str(v) for v in summary['moved_values']) or 'none'}.",
                  "",
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
        "- Families, movement and unreached defaults: raw keys `families`, `summary` "
        "(`family`, `moved`, `moved_values`, `grades`, `counts`) and `unreached`.",
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
