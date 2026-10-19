"""vFLIP2 acceptance under nuisance conditions: the sweep runner and its evidence file.

    python scripts/vflip2_nuisance.py [--n N] [--smoke] [--write]

Five sweeps (colored noise, a shared reference, spacing, SNR, the frequency grid). Each cell is a set of
probes from jnwb.testing.synth_vflip2_crossover, run through jnwb.vflip2_from_lfp at its defaults. Probe i
of every cell takes the depth and SeedSequence child that scripts/vflip2_recovery.py gives its probe i, so
the default cell's null is the recovery run's matched SNR-0 null. A refused probe is recorded with its
message. --smoke runs 5 probes per cell and prints only. --write runs the full sweeps, checks the default
cell's null against the recovery run probe by probe, and writes artifacts/evidence/0.2.13/vflip2_nuisance.md
and vflip2_nuisance.json; it writes nothing if that check fails.
"""

from __future__ import annotations

import os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import concurrent.futures as futures  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import pathlib  # noqa: E402
import sys  # noqa: E402
from typing import List, Optional, Tuple  # noqa: E402

import numpy as np  # noqa: E402
from scipy import signal  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
elif str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb.testing import synth_vflip2_crossover  # noqa: E402
from scripts import vflip2_recovery as rec  # noqa: E402

N_CONTACTS = rec.N_CONTACTS
FS = rec.FS
PITCH_UM = rec.PITCH_UM
SNR = rec.SNR
N_PROBES = rec.N_PROBES
TOLERANCE_CONTACTS = rec.TOLERANCE_CONTACTS
TAU_S = 0.03               # synth_vflip2_crossover's background time constant
REFERENCE_TAU_S = 0.03     # time constant of the shared reference
SMOKE_N = 5
TAUS = (0.005, 0.03, 0.1, 0.3)
RATIOS = (0.0, 0.5, 1.0, 2.0)
SPACINGS = (25.0, 50.0, 100.0, 150.0, 200.0)
SNRS = (0.5, 1.0, 2.0, 4.0, 8.0)
FREQS = (500.0, 1000.0, 2000.0)
SWEEPS = ("colored", "shared", "spacing", "snr", "grid")
SWEEP_TITLES = {
    "colored": "Colored noise (background time constant tau_s)",
    "shared": "Shared reference (variance ratio to the background)",
    "spacing": "Spacing (contact_spacing)",
    "snr": "SNR (planted sets; the null is SNR 0)",
    "grid": "Frequency grid (fs; n_samples = 5 s)",
}
SETTING_KEYS = ("tau_s", "shared_ratio", "spacing", "snr", "fs", "n_samples")
EVIDENCE_MD = rec.EVIDENCE / "vflip2_nuisance.md"
EVIDENCE_JSON = rec.EVIDENCE / "vflip2_nuisance.json"


def cell(sweep: str, name: str, **changes) -> dict:
    """One cell: its sweep and name, its probe settings, and whether it is a null (SNR 0) or planted set."""
    fields = dict(sweep=sweep, name=name, tau_s=TAU_S, shared_ratio=0.0, spacing=PITCH_UM, snr=SNR, fs=FS)
    fields.update(changes)
    fields["n_samples"] = int(round(5 * fields["fs"]))  # five seconds at every rate
    fields["kind"] = "null" if fields["snr"] == 0 else "planted"
    return fields


def default_cell(snr: float) -> dict:
    """The default cell (tau 0.03 s, no shared reference, 100 um, SNR 4, 1 kHz) at one SNR."""
    return cell("default", "default", snr=snr)


def is_default(c: dict) -> bool:
    """The default settings, at SNR 0 (the null) or SNR 4 (the planted set)."""
    return (c["tau_s"] == TAU_S and c["shared_ratio"] == 0.0 and c["spacing"] == PITCH_UM
            and c["fs"] == FS and c["snr"] in (0.0, SNR))


def sweep_cells(sweep: str) -> List[dict]:
    """The cells of one sweep: each setting as a null (SNR 0) and a planted set (SNR 4), except SNR."""
    if sweep == "colored":
        return [cell(sweep, f"tau {t:g} s", tau_s=t, snr=s) for t in TAUS for s in (0.0, SNR)]
    if sweep == "shared":
        return [cell(sweep, f"ratio {r:g}", shared_ratio=r, snr=s) for r in RATIOS for s in (0.0, SNR)]
    if sweep == "spacing":
        return [cell(sweep, f"{p:g} um", spacing=p, snr=s) for p in SPACINGS for s in (0.0, SNR)]
    if sweep == "snr":
        return [cell(sweep, f"snr {s:g}", snr=s) for s in (0.0,) + SNRS]
    if sweep == "grid":
        return [cell(sweep, f"{f:g} Hz", fs=f, snr=s) for f in FREQS for s in (0.0, SNR)]
    raise ValueError(f"sweep_cells: sweep must be one of {SWEEPS}, got {sweep!r}")


def shared_reference(rng: np.random.Generator, n_samples: int, fs: float) -> np.ndarray:
    """A unit-variance AR(1), drawn from rng: one series, added to every contact."""
    phi = float(np.exp(-1.0 / (fs * REFERENCE_TAU_S)))
    innovation_sd = float(np.sqrt(1.0 - phi * phi))
    first = rng.normal(0.0, 1.0)
    innovations = rng.normal(0.0, innovation_sd, size=n_samples - 1)
    return signal.lfilter([1.0], [1.0, -phi], np.concatenate([[first], innovations]))


def make_lfp(*, z0: int, child: int, snr: float, tau_s: float, shared_ratio: float,
             n_samples: int, fs: float) -> np.ndarray:
    """One probe: the synth probe from SeedSequence child `child`, plus the shared reference drawn from
    the same generator after the probe's own draws, at variance `shared_ratio` to the background."""
    rng = np.random.default_rng(rec.children()[child])
    probe = synth_vflip2_crossover(N_CONTACTS, n_samples, fs, z0=z0, snr=snr, tau_s=tau_s, rng=rng)
    reference = shared_reference(rng, n_samples, fs)
    return probe.lfp + np.sqrt(shared_ratio) * reference[None, :]


def estimate(lfp: np.ndarray, fs: float, spacing: float) -> dict:
    """vflip2_from_lfp at its defaults; a refusal comes back with its message instead of raising."""
    try:
        res = jnwb.vflip2_from_lfp(lfp, fs, contact_spacing=spacing)
    except ValueError as err:
        return {"accepted": False, "window": None, "zhat": None, "omega": None, "refused": str(err)}
    window = None if res.proximal_channel is None else [int(res.proximal_channel), int(res.distal_channel)]
    return {"accepted": bool(res.accepted), "window": window, "zhat": rec._none(res.crossover_channel),
            "omega": rec._none(res.omega), "refused": None}


def run_probe(job: dict) -> dict:
    """One probe of one cell. Its depth and child come from its index, as the recovery run assigns them."""
    cell_, index = job["cell"], job["index"]
    z0, child = rec.z0_for(index), rec.CHILD_MEASURED + index
    lfp = make_lfp(z0=z0, child=child, snr=cell_["snr"], tau_s=cell_["tau_s"],
                   shared_ratio=cell_["shared_ratio"], n_samples=cell_["n_samples"], fs=cell_["fs"])
    return dict(index=index, z0=z0, child=child, **estimate(lfp, cell_["fs"], cell_["spacing"]))


def recovered(probe: dict) -> bool:
    """Accepted, with the estimated crossover within one contact of the generator's depth z0."""
    zhat = probe["zhat"]
    return bool(probe["accepted"] and zhat is not None and abs(zhat - probe["z0"]) <= TOLERANCE_CONTACTS)


def measures(result: dict) -> dict:
    """Each measure of one cell: a count k of n, with its 95% Clopper-Pearson interval (the recovery run's _ci)."""
    n, k = result["n"], result["accepted"]
    out = {"acceptance": {"k": k, "n": n, "ci95": rec._ci(k, n)}}
    if result["cell"]["kind"] == "planted":
        k_rec = sum(recovered(p) for p in result["probes"])
        out["recovery"] = {"k": k_rec, "n": n, "ci95": rec._ci(k_rec, n)}
    return out


def run_cells(cells: List[dict], n: int, pool=None, report=None) -> List[dict]:
    """Every probe of every cell, one pool job per probe; cells come back in order, each reported when done."""
    out = []
    for c in cells:
        jobs = [{"cell": c, "index": i} for i in range(n)]
        rows = list(pool.map(run_probe, jobs)) if pool is not None else [run_probe(j) for j in jobs]
        refused = [r["refused"] for r in rows if r["refused"]]
        out.append({"cell": c, "n": n, "accepted": sum(r["accepted"] for r in rows),
                    "refused": len(refused), "messages": sorted(set(refused)), "probes": rows})
        if report is not None:
            report(out[-1])
    return out


def run_cell(cell_: dict, n: int) -> dict:
    return run_cells([cell_], n)[0]


def print_cell(r: dict) -> None:
    c = r["cell"]
    print(f"{c['sweep']} | {c['name']} | {c['kind']} | n {r['n']} | accepted {r['accepted']} | "
          f"refused {r['refused']}", flush=True)
    for msg in r["messages"]:
        print(f"  refused: {msg}", flush=True)


def _close(a: Optional[float], b: Optional[float]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=0.0)


def reproduction(results: List[dict]) -> dict:
    """The default cell's null, probe by probe, against the matched SNR-0 null of the recovery run."""
    default = next(r for r in results if is_default(r["cell"]) and r["cell"]["kind"] == "null")
    saved = json.loads(rec.JSON_PATH.read_text(encoding="utf-8"))
    block = saved["measures"]["null"]["6_null_acceptance"]
    recorded = saved["probes"]["null"]
    mismatch = {"accepted": 0, "window": 0, "child_and_depth": 0, "omega": 0, "zhat": 0}
    for g, r in zip(default["probes"], recorded):
        mismatch["accepted"] += g["accepted"] != r["accepted"]
        mismatch["window"] += g["window"] != r["window"]
        mismatch["child_and_depth"] += (g["child"], g["z0"]) != (r["child"], r["z0"])
        mismatch["omega"] += not _close(g["omega"], r["omega"])
        mismatch["zhat"] += not _close(g["zhat"], r["zhat"])
    same_length = len(default["probes"]) == len(recorded)
    ok = same_length and default["accepted"] == block["k"] and not any(mismatch.values())
    return {"k": default["accepted"], "n": default["n"], "recovery_file": rec.JSON_PATH.name,
            "recovery_k": block["k"], "recovery_n": block["n"], "same_length": same_length,
            "mismatch": mismatch, "ok": ok}


def _ci_text(block: dict) -> str:
    lo, hi = block["ci95"]
    return f"{block['k']} of {block['n']}, 95% CI [{lo}, {hi}]"


def _setting(c: dict) -> str:
    return c["name"] + (" (default cell)" if is_default(c) else "")


def _reproduction_text(rep: Optional[dict], n: int) -> str:
    if rep is None:
        return f"not run in this {n}-probe run; the full run checks it before writing."
    m = rep["mismatch"]
    return (f"its null gives {rep['k']} of {rep['n']}; {rep['recovery_file']} gives {rep['recovery_k']} of "
            f"{rep['recovery_n']} for the matched SNR-0 null. Probe mismatches: accepted {m['accepted']}, "
            f"window {m['window']}, child and depth {m['child_and_depth']}, omega {m['omega']}, "
            f"zhat {m['zhat']} (omega and zhat to relative 1e-12).")


def document(results: List[dict], rep: Optional[dict], n: int) -> Tuple[str, dict]:
    """The markdown evidence file and its JSON record, both built from the probe records in results."""
    lines = [
        "# vFLIP2 acceptance under nuisance conditions (0.2.13)",
        "",
        "Written by `python scripts/vflip2_nuisance.py --write`. Every number is computed by that script from "
        "the probe records in `vflip2_nuisance.json`.",
        "",
        "## Design",
        "",
        f"- Probes: {n} per cell. Probe i of every cell takes SeedSequence child {rec.CHILD_MEASURED} + i of "
        f"entropy 0x{rec.ENTROPY:04X} (the children of `scripts/vflip2_recovery.py`) and depth z0 = "
        f"{rec.Z0_FIRST} + i mod {rec.N_Z0}, as the recovery run's null and planted probes do.",
        f"- Null sets: SNR 0. Planted sets: SNR {SNR:g}, except the SNR sweep, which plants at each SNR in its "
        "table. Default cell: tau 0.03 s, no shared reference, 100 um, SNR 4, 1 kHz.",
        "- Colored noise: the background AR(1) time constant tau_s. Shared reference: an AR(1) with tau "
        f"{REFERENCE_TAU_S:g} s, drawn from the probe's generator after the probe's own draws, added to every "
        "contact at variance ratio r to the background.",
        "- Estimator: `jnwb.vflip2_from_lfp` at its defaults, with `contact_spacing` set by the cell. The "
        "frequency sweep keeps 5 s of data: n_samples = 5 fs.",
        "- Acceptance: the accepted fraction of n (null acceptance in null sets, planted acceptance in planted "
        "sets).",
        f"- Planted recovery: accepted, and |z_hat - z0| <= {TOLERANCE_CONTACTS} contact, over n. It is within "
        "one contact of the generator's z0, which mixes model mismatch with the nuisance effect; the oracle "
        "measure is in `vflip2_recovery.md` for the default cell only.",
        "- Intervals: exact two-sided 95% Clopper-Pearson, `_ci` of `scripts/vflip2_recovery.py` (it calls "
        "`jnwb.clopper_pearson`).",
        "- Refusals: a probe the estimator refuses is recorded with its message. It counts as not accepted, and "
        "n counts every probe of the cell.",
        f"- Default cell check: {_reproduction_text(rep, n)}",
    ]
    doc = {"contract": "artifacts/evidence/0.2.13/vflip2_generator_design.md", "entropy": rec.ENTROPY, "n": n,
           "children": {"first": rec.CHILD_MEASURED, "last": rec.CHILD_MEASURED + n - 1},
           "z0": {"first": rec.Z0_FIRST, "cycle": rec.N_Z0}, "tolerance_contacts": TOLERANCE_CONTACTS,
           "interval": "exact two-sided 95% Clopper-Pearson (scripts/vflip2_recovery.py::_ci)",
           "reproduction": rep, "sweeps": {}}
    for sweep in SWEEPS:
        rows = [r for r in results if r["cell"]["sweep"] == sweep]
        if not rows:
            continue
        lines += ["", f"## {SWEEP_TITLES[sweep]}", "",
                  "| Set | Setting | n | Acceptance, k of n, 95% CI | Planted recovery, k of n, 95% CI | Refused |",
                  "|---|---|---|---|---|---|"]
        doc["sweeps"][sweep] = []
        refusals = []
        for r in rows:
            c, m = r["cell"], measures(r)
            recovery = _ci_text(m["recovery"]) if "recovery" in m else "none"
            lines.append(f"| {c['kind']} | {_setting(c)} | {r['n']} | {_ci_text(m['acceptance'])} | "
                         f"{recovery} | {r['refused']} |")
            refusals += [f"{_setting(c)} ({c['kind']}): {msg}" for msg in r["messages"]]
            doc["sweeps"][sweep].append({
                "name": c["name"], "kind": c["kind"], "default": is_default(c),
                "settings": {k: c[k] for k in SETTING_KEYS}, "n": r["n"], "accepted": r["accepted"],
                "refused": r["refused"], "messages": r["messages"], "measures": m, "probes": r["probes"]})
        lines += ["", f"Source: `vflip2_nuisance.json`, `sweeps.{sweep}`: each cell's probe records; counts and "
                  "intervals are `measures()` of those records.", "",
                  "Refusals: " + ("; ".join(refusals) if refusals else "none") + "."]
    return "\n".join(lines) + "\n", doc


def write_outputs(md_text: str, doc: dict, md_path: pathlib.Path, json_path: pathlib.Path) -> None:
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(doc, indent=1, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8", newline="\n")
    md_path.write_text(md_text, encoding="utf-8", newline="\n")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=N_PROBES, help="probes per cell (default 100)")
    parser.add_argument("--smoke", action="store_true", help="5 probes per cell; prints only")
    parser.add_argument("--write", action="store_true", help="the full run: write the evidence files")
    args = parser.parse_args(argv)
    if not 1 <= args.n <= N_PROBES:
        parser.error(f"--n must be between 1 and {N_PROBES}: the children beyond that belong to other runs")
    if args.smoke and args.write:
        parser.error("--write needs the full run; --smoke prints only")
    if args.write and args.n != N_PROBES:
        parser.error(f"--write needs --n {N_PROBES}, the full run")
    n = SMOKE_N if args.smoke else args.n
    cells = [c for sweep in SWEEPS for c in sweep_cells(sweep)]
    with futures.ProcessPoolExecutor(max_workers=min(4, os.cpu_count() or 1)) as pool:
        checks = [{"cell": cells[0], "index": i} for i in range(5)]
        serial = [run_probe(j) for j in checks]
        pooled = list(pool.map(run_probe, checks))
        print(f"pool check: 5 probes serial vs pool {'identical' if serial == pooled else 'DIFFERENT'}",
              flush=True)
        if serial != pooled:
            print("summary: pool check failed; no sweep was run", flush=True)
            return 1
        results = run_cells(cells, n, pool, report=print_cell)
    total = sum(r["n"] for r in results)
    if not args.write:
        print(f"summary: {len(results)} cells, {total} probes ({n} per cell); files not written", flush=True)
        return 0
    rep = reproduction(results)
    if not rep["ok"]:
        print(f"REPRODUCTION FAILED: default null {rep['k']} of {rep['n']}; {rep['recovery_file']} null "
              f"{rep['recovery_k']} of {rep['recovery_n']}; mismatches {rep['mismatch']}", flush=True)
        print("summary: the default cell does not reproduce the recovery null; nothing written", flush=True)
        return 1
    md_text, doc = document(results, rep, n)
    write_outputs(md_text, doc, EVIDENCE_MD, EVIDENCE_JSON)
    print(f"wrote {EVIDENCE_MD.relative_to(ROOT).as_posix()} and {EVIDENCE_JSON.relative_to(ROOT).as_posix()}",
          flush=True)
    print(f"summary: {len(results)} cells, {total} probes; default null {rep['k']} of {rep['n']} reproduces "
          f"{rep['recovery_file']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
