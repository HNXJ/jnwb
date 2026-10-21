"""vFLIP2 on seeded synthetic probes: a characterization of two crossover definitions.

    python scripts/vflip2_simulation.py [--write]

Planted probes come from jnwb.testing.synth_laminar_motif: 32 contacts at 100 um, fs 1000 Hz,
5000 samples, snr 4, with the generator's crossover at contact 8 + seed % 16 (contacts 8 to 23).
Null probes are the same call with snr 0, so they hold the shared background noise only. A
planted and a null probe with one seed share that background. Each probe is estimated by
jnwb.vflip2_from_lfp with contact_spacing 100 um and default arguments.

The script reports counts and crossover offsets and sets no pass or fail threshold. --write writes
artifacts/evidence/0.2.12/vflip2_simulation.md; without it, the same text is printed.
"""

from __future__ import annotations

import argparse
import inspect
import pathlib
import os
import sys
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Under JNWB_EXPECTED_PACKAGE_ROOT the checkout goes last, so the copy it names wins.
if os.environ.get("JNWB_EXPECTED_PACKAGE_ROOT"):
    if str(ROOT) not in sys.path:
        sys.path.append(str(ROOT))
elif str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jnwb  # noqa: E402
from jnwb.testing import synth_laminar_motif  # noqa: E402

N_CONTACTS = 32
PITCH_UM = 100.0
FS = 1000.0
N_SAMPLES = 5000
SNR = 4.0
SEEDS = tuple(range(100))
TOLERANCE_CONTACTS = 1
MASKED_SEED = 5
OUT_PATH = ROOT / "artifacts" / "evidence" / "0.2.12" / "vflip2_simulation.md"


def planted_contact(seed: int) -> int:
    """Generator crossover for a seed: 8 + seed % 16, so contacts 8 to 23 occur evenly."""
    return 8 + seed % 16


def build_probe(seed: int, *, snr: float) -> np.ndarray:
    """The generator's (n_contacts, n_samples) LFP for a seed; snr 0 gives the null.

    The planted contact is passed in both cases and has no effect at snr 0.
    """
    receipt = synth_laminar_motif(N_CONTACTS, N_SAMPLES, FS, c_crossover=float(planted_contact(seed)),
                                  pitch_um=PITCH_UM, snr=snr, rng=seed)
    return receipt.lfp


def band_edges() -> dict:
    """The generator's band edges at its defaults: gamma_freq +/- 15 Hz and beta_freq +/- 5 Hz."""
    params = inspect.signature(synth_laminar_motif).parameters
    gamma, beta = params["gamma_freq"].default, params["beta_freq"].default
    return {"gamma": (gamma - 15.0, gamma + 15.0), "beta": (beta - 5.0, beta + 5.0)}


def band_rows(lfp: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Mean PSD over each band, per contact: (gamma per contact, beta per contact).

    The PSD is jnwb.compute_psd at its default segment length (one second, so 1 Hz bins).
    """
    freqs, psd = jnwb.compute_psd(lfp, FS, axis=-1)
    edges = band_edges()

    def band(lo: float, hi: float) -> np.ndarray:
        keep = (freqs >= lo) & (freqs <= hi)
        return psd[:, keep].mean(axis=1)

    return band(*edges["gamma"]), band(*edges["beta"])


@dataclass(frozen=True)
class Outcome:
    seed: int
    contact: int
    accepted: bool
    crossover: Optional[int]
    omega: Optional[float]


def run_probe(seed: int, *, snr: float) -> Outcome:
    contact = planted_contact(seed)
    result = jnwb.vflip2_from_lfp(build_probe(seed, snr=snr), FS, contact_spacing=PITCH_UM)
    return Outcome(seed, contact, bool(result.accepted), result.crossover_channel, result.omega)


def run_sets(seeds: Sequence[int] = SEEDS) -> Tuple[List[Outcome], List[Outcome]]:
    planted = [run_probe(seed, snr=SNR) for seed in seeds]
    null = [run_probe(seed, snr=0.0) for seed in seeds]
    return planted, null


def within_one_contact(o: Outcome) -> bool:
    """Accepted, and crossover_channel within one contact of the generator's crossover."""
    return (o.accepted and o.crossover is not None
            and abs(o.crossover - o.contact) <= TOLERANCE_CONTACTS)


def counts(planted: Sequence[Outcome], null: Sequence[Outcome]) -> dict:
    return {
        "planted_probes": len(planted),
        "planted_accepted": sum(o.accepted for o in planted),
        "planted_within_one_contact": sum(within_one_contact(o) for o in planted),
        "null_probes": len(null),
        "null_accepted": sum(o.accepted for o in null),
    }


def _spread(values: Sequence[float]) -> Tuple[str, str, str]:
    """min, median and max as strings; 'none' for each when there are no values."""
    if not values:
        return "none", "none", "none"
    v = np.asarray(values, dtype=float)
    return f"{v.min():.3f}", f"{np.median(v):.3f}", f"{v.max():.3f}"


def _cell(value) -> str:
    return "-" if value is None else str(value)


def render(planted: Sequence[Outcome], null: Sequence[Outcome]) -> str:
    n = len(planted)
    seeds = [o.seed for o in planted]
    per_contact = Counter(o.contact for o in planted)
    accepted = [o for o in planted if o.accepted]
    far = [o for o in accepted if not within_one_contact(o)]
    no_window = sum(o.omega is None for o in planted)
    null_no_window = sum(o.omega is None for o in null)
    offsets = [o.crossover - o.contact for o in accepted if o.crossover is not None]
    c = counts(planted, null)
    masked_c = planted_contact(MASKED_SEED)
    _, masked_beta = band_rows(build_probe(MASKED_SEED, snr=SNR))
    masked_sup = masked_beta[: masked_c + 1].mean()
    masked_deep = masked_beta[masked_c + 1:].mean()
    p_omega = _spread([o.omega for o in planted if o.omega is not None])
    n_omega = _spread([o.omega for o in null if o.omega is not None])
    off = _spread(offsets)

    lines = [
        "# vFLIP2 on seeded synthetic probes (0.2.12)",
        "",
        "Written by `python scripts/vflip2_simulation.py --write`. Every number is computed by that script.",
        "",
        "## Design",
        "",
        f"- Planted probe: `synth_laminar_motif({N_CONTACTS}, {N_SAMPLES}, {FS:.1f}, "
        f"c_crossover=<generator crossover>, pitch_um={PITCH_UM:.1f}, snr={SNR:.1f}, rng=<seed>)`.",
        "- Null probe: the generator at `snr=0.0`, which leaves its shared 1/f background noise only; "
        "a planted and a null probe with one seed share that background.",
        f"- Estimator: `jnwb.vflip2_from_lfp(lfp, {FS:.1f}, contact_spacing={PITCH_UM:.1f})`, defaults.",
        f"- Seeds: {seeds[0]} to {seeds[-1]} ({n} probes per set).",
        f"- Generator crossover: {min(per_contact)} to {max(per_contact)}, "
        f"{min(per_contact.values())} to {max(per_contact.values())} probes per contact, "
        "contact = 8 + seed % 16.",
        f"- Within one contact: accepted, and `crossover_channel` within {TOLERANCE_CONTACTS} contact "
        "of the generator's crossover.",
        "- The generator's crossover is the contact where its gamma and beta amplitude weights are equal, "
        "and vFLIP2's is where the relative band-power profiles cross inside its selected window, so the "
        "offset below measures the gap between these two definitions, not an error rate.",
        f"- In raw power the 1/f background can mask the beta gradient at snr {SNR:.0f}: for seed {MASKED_SEED} "
        f"the raw beta mean is {masked_sup:.4f} on rows 0 to {masked_c} and {masked_deep:.4f} on rows "
        f"{masked_c + 1} to {N_CONTACTS - 1}.",
        "",
        "## Counts",
        "",
        "| set | probes | accepted | within one contact | accepted, more than one contact away | no window passed |",
        "|---|---|---|---|---|---|",
        f"| planted | {c['planted_probes']} | {c['planted_accepted']} | {c['planted_within_one_contact']} "
        f"| {len(far)} | {no_window} |",
        f"| null | {c['null_probes']} | {c['null_accepted']} | - | - | {null_no_window} |",
        "",
        "## Omega and crossover offset",
        "",
        "| set | probes with a window | omega min | omega median | omega max |",
        "|---|---|---|---|---|",
        f"| planted | {sum(o.omega is not None for o in planted)} | {p_omega[0]} | {p_omega[1]} | {p_omega[2]} |",
        f"| null | {sum(o.omega is not None for o in null)} | {n_omega[0]} | {n_omega[1]} | {n_omega[2]} |",
        "",
        f"Crossover minus generator crossover, accepted planted probes: min {off[0]}, median {off[1]}, "
        f"max {off[2]} (contacts).",
        "",
        "## Per probe",
        "",
        "| seed | generator crossover | planted accepted | planted crossover | planted omega | null accepted | null omega |",
        "|---|---|---|---|---|---|---|",
    ]
    for p, z in zip(planted, null):
        p_omega_cell = "-" if p.omega is None else f"{p.omega:.3f}"
        z_omega_cell = "-" if z.omega is None else f"{z.omega:.3f}"
        lines.append(f"| {p.seed} | {p.contact} | {p.accepted} | {_cell(p.crossover)} | "
                     f"{p_omega_cell} | {z.accepted} | {z_omega_cell} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true",
                        help=f"write {OUT_PATH.relative_to(ROOT).as_posix()}")
    args = parser.parse_args(argv)
    planted, null = run_sets()
    text = render(planted, null)
    if args.write:
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        # newline="\n": see scripts/generate_api_md.py.
        OUT_PATH.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT_PATH.relative_to(ROOT).as_posix()}")
    else:
        print(text, end="")
    c = counts(planted, null)
    print(f"summary: planted accepted {c['planted_accepted']} of {c['planted_probes']}; "
          f"planted within one contact {c['planted_within_one_contact']} of {c['planted_probes']}; "
          f"null accepted {c['null_accepted']} of {c['null_probes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
