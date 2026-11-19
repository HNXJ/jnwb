#!/usr/bin/env python3
"""Generate a deterministic, delayed broadband jaxfne rate fixture for jnwb.

Builds a two-area (`SiteA`, `SiteB`), single-layer (`L1`), one-unit-per-area
Wilson-Cowan-type rate network via jaxfne's public `NeuronalTensor` +
`construct` + `run_trials` + `to_jnwb_trials` path under four conditions:

1. `forward_x_to_y`: `SiteA -> SiteB` (`delay_ms=6.0`, `weight=0.6`)
2. `reverse_y_to_x`: `SiteB -> SiteA` (`delay_ms=6.0`, `weight=0.6`)
3. `uncoupled_null`: no cross-area connection (`n_edges=0`)
4. `zero_lag_common_source`: instantaneous mixture `site_0 = 0.7*Z + 0.3*Nx`,
   `site_1 = 0.7*Z + 0.3*Ny` built from uncoupled jaxfne rate simulations

Writes a compact compressed `.npz` archive and a matching `.provenance.json`
record pinning array byte digests and generator provenance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np

JNWB_ROOT = Path(__file__).resolve().parents[3]

DT_MS = 1.0
FS_HZ = 1000.0 / DT_MS
BURN_IN_STEPS = 200
N_SAMPLES = 1000
DURATION_MS = float(BURN_IN_STEPS + N_SAMPLES) * DT_MS
N_TRIALS = 16

TAU_MS = 5.0
TRANSFER = "threshold_linear"
GAIN = 1.0
SIGMA = 0.20
R0 = 1.0
DRIVE = 0.0

DELAY_MS = 6.0
DELAY_STEPS = 6
TARGET_EDGE_WEIGHT = 0.6
N_TOTAL_UNITS = 2
W_MECH = TARGET_EDGE_WEIGHT * math.sqrt(N_TOTAL_UNITS)
STATIC_SYNAPTIC_DT_MS = 2.0

COMMON_SOURCE_WEIGHT = 0.7
INDEPENDENT_NOISE_WEIGHT = 0.3

FORWARD_SEEDS = tuple(range(0, N_TRIALS))
REVERSE_SEEDS = tuple(range(100, 100 + N_TRIALS))
UNCOUPLED_SEEDS = tuple(range(200, 200 + N_TRIALS))
COMMON_Z_SEEDS = tuple(range(300, 300 + N_TRIALS))
COMMON_NX_SEEDS = tuple(range(316, 316 + N_TRIALS))
COMMON_NY_SEEDS = tuple(range(332, 332 + N_TRIALS))


def _import_jaxfne(jaxfne_repo: Path) -> tuple[Any, Any, Any, Any, Any, Any, Any]:
    repo_str = str(jaxfne_repo.resolve())
    if sys.path[0] != repo_str:
        sys.path.insert(0, repo_str)
    import jaxfne as jtfne
    from jaxfne import neuronal_tensor as nt
    from jaxfne.core import RuntimeConfig, Simulation, TrialBatch, TrialSpec
    from jaxfne.jnwb_view import to_jnwb_trials

    return jtfne, nt, RuntimeConfig, Simulation, TrialBatch, TrialSpec, to_jnwb_trials


def build_two_site_rate_tensor(nt: Any, direction: str) -> Any:
    """Return an explicit two-area rate NeuronalTensor (`forward`, `reverse`, or `uncoupled`)."""
    rate_params = {
        "tau_ms": TAU_MS,
        "transfer": TRANSFER,
        "gain": GAIN,
        "sigma": SIGMA,
        "r0": R0,
    }
    area_a = nt.Area(
        name="SiteA",
        layers=[
            nt.Layer(
                name="L1",
                n_neurons=1,
                neuron_types=[
                    nt.NeuronType.make(
                        "E",
                        fraction=1.0,
                        emitter="rate",
                        emitter_params=rate_params,
                        drive=DRIVE,
                    )
                ],
            )
        ],
        inter_connections=(),
    )
    area_b = nt.Area(
        name="SiteB",
        layers=[
            nt.Layer(
                name="L1",
                n_neurons=1,
                neuron_types=[
                    nt.NeuronType.make(
                        "E",
                        fraction=1.0,
                        emitter="rate",
                        emitter_params=rate_params,
                        drive=DRIVE,
                    )
                ],
            )
        ],
        inter_connections=(),
    )
    if direction == "uncoupled":
        conns: tuple[Any, ...] = ()
    elif direction in ("forward", "reverse"):
        src, dst = ("SiteA", "SiteB") if direction == "forward" else ("SiteB", "SiteA")
        conns = (
            nt.AreaConnection(
                source_area=src,
                source_layer="L1",
                source_neuron_type="E",
                target_area=dst,
                target_layer="L1",
                target_neuron_type="E",
                mechanism="AMPA",
                static=nt.StaticParams(dT_ms=STATIC_SYNAPTIC_DT_MS),
                plastic=nt.PlasticParams(w_mech=W_MECH),
                delay_ms=DELAY_MS,
            ),
        )
    else:
        raise ValueError(f"Unknown direction {direction!r}")

    return nt.NeuronalTensor(
        name=f"jnwb-delayed-broadband-{direction}",
        areas=[area_a, area_b],
        area_connections=conns,
    )


def construct_two_site_rate_model(
    jtfne: Any, nt: Any, direction: str, *, seed: int = 0
) -> Any:
    """Construct and validate the two-site rate model and its realized edge table."""
    tensor = build_two_site_rate_tensor(nt, direction)
    runtime = nt.RuntimeConfiguration(
        seed=seed,
        duration_ms=DURATION_MS,
        dt_ms=DT_MS,
        dtype="float32",
        emitter="rate",
        device="cpu",
        jit=False,
    )
    model = jtfne.construct(tensor, runtime)
    rows = model.neuron_table()
    if len(rows) != 2 or rows[0]["area"] != "SiteA" or rows[1]["area"] != "SiteB":
        raise RuntimeError(f"Unexpected neuron layout: {rows!r}")
    edges = model.edge_table()
    if direction == "uncoupled":
        if len(edges) != 0:
            raise RuntimeError(f"Expected 0 edges for uncoupled, got {edges!r}")
    else:
        expected_pre, expected_post = (0, 1) if direction == "forward" else (1, 0)
        if len(edges) != 1:
            raise RuntimeError(f"Expected 1 edge for {direction}, got {edges!r}")
        edge = edges[0]
        if int(edge["pre"]) != expected_pre or int(edge["post"]) != expected_post:
            raise RuntimeError(f"Unexpected edge endpoints for {direction}: {edge!r}")
        if int(edge["delay_steps"]) != DELAY_STEPS:
            raise RuntimeError(f"Expected delay_steps={DELAY_STEPS}, got {edge!r}")
        if not math.isclose(float(edge["weight"]), TARGET_EDGE_WEIGHT, rel_tol=1e-6, abs_tol=1e-6):
            raise RuntimeError(f"Expected weight={TARGET_EDGE_WEIGHT}, got {edge!r}")
    return model


def _run_batch(
    model: Any,
    seeds: tuple[int, ...],
    *,
    batch_id: str,
    RuntimeConfig: Any,
    Simulation: Any,
    TrialBatch: Any,
    TrialSpec: Any,
    to_jnwb_trials: Any,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Run deterministic trial batch and return post-burn-in `(n_trials, N_SAMPLES, 2)` float64."""
    sim = Simulation(
        duration_ms=DURATION_MS,
        dt_ms=DT_MS,
        seed=seeds[0],
        runtime=RuntimeConfig(
            dtype="float32",
            recurrent_backend="edge_list",
            enable_hdp=False,
            jit=False,
        ),
    )
    batch = TrialBatch(
        batch_id=batch_id,
        trials=tuple(TrialSpec(trial_id=f"{batch_id}_{i:02d}", seed=s) for i, s in enumerate(seeds)),
    )
    batch_res = model.run_trials(batch, sim)
    trials = to_jnwb_trials(batch_res)
    if not math.isclose(trials.fs_hz, FS_HZ, rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError(f"Unexpected sampling rate {trials.fs_hz}")
    if trials.n_steps != BURN_IN_STEPS + N_SAMPLES:
        raise RuntimeError(f"Unexpected n_steps {trials.n_steps}")
    first_meta = dict(trials.views[0].metadata)
    if int(first_meta.get("n_floored_to_one_step", -1)) != 0:
        raise RuntimeError(f"Unexpected floored edge count in metadata: {first_meta!r}")
    stacked = np.asarray(trials.stack("V_m")[:, BURN_IN_STEPS:, :], dtype=np.float64)
    if stacked.shape != (len(seeds), N_SAMPLES, 2):
        raise RuntimeError(f"Unexpected output shape {stacked.shape}")
    if not np.all(np.isfinite(stacked)):
        raise RuntimeError(f"Non-finite values in batch {batch_id}")
    if float(np.min(stacked)) <= 0.0:
        raise RuntimeError(
            f"Batch {batch_id} touched or crossed zero rate floor (min={np.min(stacked)})"
        )
    return stacked, first_meta


def generate_arrays(jaxfne_repo: Path) -> tuple[dict[str, np.ndarray], Any]:
    """Generate all fixture arrays deterministically from a jaxfne checkout."""
    jtfne, nt, RuntimeConfig, Simulation, TrialBatch, TrialSpec, to_jnwb_trials = _import_jaxfne(
        jaxfne_repo
    )
    forward_model = construct_two_site_rate_model(jtfne, nt, "forward")
    reverse_model = construct_two_site_rate_model(jtfne, nt, "reverse")
    uncoupled_model = construct_two_site_rate_model(jtfne, nt, "uncoupled")

    kw = {
        "RuntimeConfig": RuntimeConfig,
        "Simulation": Simulation,
        "TrialBatch": TrialBatch,
        "TrialSpec": TrialSpec,
        "to_jnwb_trials": to_jnwb_trials,
    }
    forward_xy, _ = _run_batch(forward_model, FORWARD_SEEDS, batch_id="forward_x_to_y", **kw)
    reverse_yx, _ = _run_batch(reverse_model, REVERSE_SEEDS, batch_id="reverse_y_to_x", **kw)
    uncoupled, _ = _run_batch(uncoupled_model, UNCOUPLED_SEEDS, batch_id="uncoupled_null", **kw)

    z_trials, _ = _run_batch(uncoupled_model, COMMON_Z_SEEDS, batch_id="common_z", **kw)
    nx_trials, _ = _run_batch(uncoupled_model, COMMON_NX_SEEDS, batch_id="common_nx", **kw)
    ny_trials, _ = _run_batch(uncoupled_model, COMMON_NY_SEEDS, batch_id="common_ny", **kw)
    common_source = np.stack(
        [
            COMMON_SOURCE_WEIGHT * z_trials[:, :, 0] + INDEPENDENT_NOISE_WEIGHT * nx_trials[:, :, 0],
            COMMON_SOURCE_WEIGHT * z_trials[:, :, 0] + INDEPENDENT_NOISE_WEIGHT * ny_trials[:, :, 0],
        ],
        axis=2,
    ).astype(np.float64)
    if float(np.min(common_source)) <= 0.0:
        raise RuntimeError(f"common_source touched zero floor (min={np.min(common_source)})")

    time_s = np.arange(N_SAMPLES, dtype=np.float64) * (DT_MS / 1000.0)
    site_names = np.array(["site_0", "site_1"])

    arrays = {
        "forward_x_to_y": forward_xy,
        "reverse_y_to_x": reverse_yx,
        "uncoupled_null": uncoupled,
        "zero_lag_common_source": common_source,
        "time_s": time_s,
        "site_names": site_names,
    }
    return arrays, jtfne


def _git_output(args: list[str], cwd: Path) -> str:
    return subprocess.check_output(["git", "-C", str(cwd), *args], text=True).strip()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_provenance(
    arrays: dict[str, np.ndarray],
    npz_path: Path,
    jaxfne_repo: Path,
    jtfne: Any,
) -> dict[str, Any]:
    """Assemble provenance dictionary binding array digests and generator parameters."""
    alpha = DT_MS / TAU_MS
    stationary_var = (SIGMA ** 2) / (2.0 - alpha)
    try:
        script_rel = Path(__file__).resolve().relative_to(JNWB_ROOT.resolve()).as_posix()
    except ValueError:
        script_rel = Path(__file__).name
    script_sha = _sha256_bytes(Path(__file__).resolve().read_bytes())

    array_meta = {
        name: {
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
            "sha256_of_bytes": _sha256_bytes(arr.tobytes()),
        }
        for name, arr in sorted(arrays.items())
    }

    return {
        "arrays": array_meta,
        "description": (
            "Synthetic broadband coupled two-site rate simulation from jaxfne's "
            "NeuronalTensor + construct(emitter='rate') + run_trials + to_jnwb_trials "
            "pipeline across forward, reverse, uncoupled, and zero-lag common-source "
            "conditions."
        ),
        "file_bytes": {"npz": int(npz_path.stat().st_size)},
        "generator_configuration": {
            "burn_in_ms": float(BURN_IN_STEPS) * DT_MS,
            "burn_in_steps": BURN_IN_STEPS,
            "common_source_mixture": {
                "common_weight": COMMON_SOURCE_WEIGHT,
                "independent_weight": INDEPENDENT_NOISE_WEIGHT,
                "note": (
                    "Instantaneous linear mixture of three uncoupled jaxfne rate "
                    "simulations (common Z, independent Nx, independent Ny); "
                    "zero planted lag."
                ),
            },
            "dt_ms": DT_MS,
            "duration_ms": DURATION_MS,
            "emitter": "rate",
            "gain": GAIN,
            "n_samples_kept": N_SAMPLES,
            "n_steps_simulated": BURN_IN_STEPS + N_SAMPLES,
            "n_trials": N_TRIALS,
            "r0": R0,
            "sigma": SIGMA,
            "static_synaptic_dt_ms": STATIC_SYNAPTIC_DT_MS,
            "tau_ms": TAU_MS,
            "time_convention": "time_s = arange(n_samples_kept) * dt_ms / 1000",
            "transfer": TRANSFER,
            "w_mech": W_MECH,
        },
        "ground_truth": {
            "discrete_arrival_lag_steps": DELAY_STEPS,
            "forward_direction": "site_0 -> site_1",
            "planted_synaptic_delay_ms": DELAY_MS,
            "rate_filter_tau_ms": TAU_MS,
            "realized_edge_weight": TARGET_EDGE_WEIGHT,
            "reverse_direction": "site_1 -> site_0",
            "spectral_family": "discrete AR(1) broadband low-pass (Wilson-Cowan rate unit)",
        },
        "item": "12-21",
        "sampling": {
            "dt_ms": DT_MS,
            "fs_hz": FS_HZ,
            "n_samples": N_SAMPLES,
            "n_sites": 2,
            "n_trials": N_TRIALS,
        },
        "seeds": {
            "common_nx_seeds": list(COMMON_NX_SEEDS),
            "common_ny_seeds": list(COMMON_NY_SEEDS),
            "common_z_seeds": list(COMMON_Z_SEEDS),
            "forward_seeds": list(FORWARD_SEEDS),
            "reverse_seeds": list(REVERSE_SEEDS),
            "uncoupled_seeds": list(UNCOUPLED_SEEDS),
        },
        "source": {
            "commit": _git_output(["rev-parse", "HEAD"], jaxfne_repo),
            "generator_file": script_rel,
            "generator_sha256": script_sha,
            "git_status_short_clean": _git_output(["status", "--short"], jaxfne_repo) == "",
            "jaxfne_version": str(getattr(jtfne, "__version__", "unknown")),
        },
        "theoretical_model": {
            "alpha": alpha,
            "coupled_difference_equation": (
                "r_post[t] = (1 - alpha) * r_post[t-1] + "
                "alpha * (1 + gain * weight * r_pre[t - d]) + noise_post[t]"
            ),
            "transfer_function": (
                "H(f) = alpha * gain * weight * exp(-i*2*pi*f*d*dt_s) / "
                "(1 - (1 - alpha) * exp(-i*2*pi*f*dt_s))"
            ),
            "uncoupled_one_sided_psd_formula": (
                "S(f) = 2 * dt_s * sigma^2 * alpha / "
                "(1 + (1 - alpha)^2 - 2 * (1 - alpha) * cos(2*pi*f*dt_s))"
            ),
            "uncoupled_stationary_variance": stationary_var,
        },
        "units": {
            "rates": "relative rate (threshold_linear, phi(0)=1), not volts",
            "time": "s",
        },
        "validation_scope": "synthetic ground-truth recovery only; not empirical validation",
    }


def write_fixture(jaxfne_repo: Path, out_npz: Path, out_provenance: Path) -> dict[str, Any]:
    """Generate arrays and write `.npz` plus `.provenance.json`."""
    arrays, jtfne = generate_arrays(jaxfne_repo)
    out_npz.parent.mkdir(parents=True, exist_ok=True)
    out_provenance.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out_npz, **arrays)
    provenance = build_provenance(arrays, out_npz, jaxfne_repo, jtfne)
    out_provenance.write_bytes(
        (json.dumps(provenance, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jaxfne-repo",
        type=Path,
        required=True,
        help="Path to clean jaxfne checkout used to build and simulate the fixture",
    )
    parser.add_argument("--out-npz", type=Path, required=True, help="Output compressed .npz path")
    parser.add_argument(
        "--out-provenance", type=Path, required=True, help="Output .provenance.json path"
    )
    args = parser.parse_args()
    prov = write_fixture(args.jaxfne_repo, args.out_npz, args.out_provenance)
    print(
        f"wrote {args.out_npz} ({prov['file_bytes']['npz']} bytes) "
        f"at jaxfne@{prov['source']['commit'][:8]}"
    )


if __name__ == "__main__":
    main()
