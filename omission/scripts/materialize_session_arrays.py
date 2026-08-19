#!/usr/bin/env python3
"""
Materialize trial-aligned spike arrays for a single hot window into fast-loading
memmap-friendly numpy arrays.

Scope (see artifacts/developer/progress.json entry for this script — do not expand):
  - Only the specific trial-aligned SPIKE arrays for one (phase, condition, window)
    combination are cached. LFP/MUAe and the full NWB are never touched here.
  - This does NOT replace omission.jnwb_ext.session.OmissionSession's lazy h5py/pynwb access; it
    caches a derived, repeatedly-recomputed slice (per-trial spike windows across many
    analysis scripts) so downstream code stops re-slicing the same spike trains.

Inputs:
  - artifacts/data/nwb_catalog.json          (session -> nwb path; from build_nwb_catalog.py)
  - <meta-root>/<stem>/units.csv             (unit_id, area, quality; from build_session_sidecars.py)
  - omission.jnwb_ext.session.OmissionSession             (get_epochs for trial onsets, get_spike_times per unit;
                                               itself backed by a disk pickle cache under
                                               artifacts/developer/.cache/)

Output layout (per session, per config):
  artifacts/data/materialized/<stem>/<tag>/
    manifest.json        - full config + shapes + dtypes + provenance
    unit_ids.npy          int64   (U,)            unit_id per row, in output order
    trial_onsets.npy      float64 (T,)             epoch start_time (s), in output order
    trial_index.csv                                human-readable trial provenance
    offsets.npy           int64   (U, T+1)         ragged-array offsets into spike_times_ms.npy
    spike_times_ms.npy     float32 (N,)             flat, trial-relative spike times (ms),
                                                     concatenated unit-major then trial-major

  Reconstruction for unit row u, trial row t:
      lo, hi = offsets[u, t], offsets[u, t + 1]
      spikes_ms = spike_times_ms[lo:hi]   # relative to trial_onsets[t], in ms

  spike_times_ms.npy is written as a plain .npy and is intended to be reopened with
  np.load(..., mmap_mode='r') for hot-path re-use across scripts.

tag = f"phase{phase}_{condition or 'all'}_w{w0}_{w1}"

Idempotent: if <out>/manifest.json exists with a matching config hash, the run is
skipped unless --overwrite is passed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import omission as oa  # noqa: E402
from jnwb import paths as _P


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--session",
        required=True,
        help="Session stem or substring filter (e.g. 'sub-C31o_ses-230823_rec' or 'C31o_ses-230823')",
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=Path("artifacts/data/nwb_catalog.json"),
        help="NWB catalog produced by scripts/build_nwb_catalog.py",
    )
    p.add_argument(
        "--meta-root",
        type=Path,
        default=Path(_P.meta_dir()),
        help="Sidecar metadata root produced by scripts/build_session_sidecars.py",
    )
    p.add_argument(
        "--out-root",
        type=Path,
        default=Path("artifacts/data/materialized"),
        help="Output root for materialized hot-window arrays",
    )
    p.add_argument(
        "--phase",
        type=int,
        default=2,
        help="stimulus_number to align to (1=fixation, 2=p1, 3=p2, 4=p3, 5=p4). Default: 2 (p1)",
    )
    p.add_argument(
        "--condition",
        default=None,
        help="Condition code/name understood by OmissionSession.get_epochs (e.g. 'AAXB'). "
        "Default: None (all conditions, correct trials only unless --include-incorrect)",
    )
    p.add_argument(
        "--window-ms",
        type=float,
        nargs=2,
        default=(-1000.0, 4000.0),
        metavar=("PRE_MS", "POST_MS"),
        help="Window relative to phase onset in ms. Default matches the repo-wide raster/"
        "stability convention: -1000 4000",
    )
    p.add_argument(
        "--include-incorrect",
        action="store_true",
        help="Include incorrect trials (default: correct trials only, matching "
        "OmissionSession.get_epochs default)",
    )
    p.add_argument(
        "--area",
        default=None,
        help="Optional area filter on the sidecar units.csv (e.g. 'V1')",
    )
    p.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Cap number of units materialized (smoke-test / dev use)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Recompute even if a matching manifest already exists",
    )
    return p.parse_args()


def resolve_session(catalog_path: Path, session_filter: str) -> Dict[str, Any]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    sessions = data.get("sessions", [])
    tok = session_filter.lower()
    matches = [
        s
        for s in sessions
        if tok in str(s.get("stem", "")).lower()
        or tok in str(s.get("session_prefix", "")).lower()
    ]
    if not matches:
        raise SystemExit(f"No session in {catalog_path} matches '{session_filter}'")
    # Prefer full (non-short) nwb if multiple match.
    full = [m for m in matches if not m.get("short_nwb")]
    chosen = full[0] if full else matches[0]
    if len(matches) > 1:
        print(
            f"[materialize] multiple catalog matches for '{session_filter}', "
            f"using stem={chosen['stem']}"
        )
    return chosen


def load_sidecar_units(meta_root: Path, stem: str, area: Optional[str]) -> pd.DataFrame:
    units_csv = meta_root / stem / "units.csv"
    if not units_csv.is_file() or units_csv.stat().st_size == 0:
        raise SystemExit(
            f"Sidecar units.csv missing for {stem} at {units_csv}. "
            "Run scripts/build_session_sidecars.py first."
        )
    df = pd.read_csv(units_csv)
    if area:
        df = df[df["area"] == area]
    return df.reset_index(drop=True)


def config_tag(
    phase: int, condition: Optional[str], window_ms: Tuple[float, float], area: Optional[str]
) -> str:
    cond_tag = condition if condition else "all"
    area_tag = f"_{area}" if area else ""
    return f"phase{phase}_{cond_tag}_w{int(window_ms[0])}_{int(window_ms[1])}{area_tag}"


def config_hash(cfg: Dict[str, Any]) -> str:
    blob = json.dumps(cfg, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def existing_manifest_matches(out_dir: Path, cfg_hash: str) -> bool:
    manifest_path = out_dir / "manifest.json"
    if not manifest_path.is_file():
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    return manifest.get("config_hash") == cfg_hash


def materialize(
    session,
    unit_ids: List[int],
    epochs: pd.DataFrame,
    window_ms: Tuple[float, float],
) -> Dict[str, np.ndarray]:
    w0_s, w1_s = window_ms[0] / 1000.0, window_ms[1] / 1000.0
    onsets = epochs["start_time"].to_numpy(dtype=np.float64)
    n_trials = len(onsets)
    n_units = len(unit_ids)

    offsets = np.zeros((n_units, n_trials + 1), dtype=np.int64)
    spike_chunks: List[np.ndarray] = []
    running = 0
    for u_i, uid in enumerate(unit_ids):
        spikes = session.get_spike_times(uid)
        offsets[u_i, 0] = running
        if spikes is None or len(spikes) == 0:
            offsets[u_i, 1:] = running
            continue
        spikes = np.asarray(spikes, dtype=np.float64)
        if not np.all(np.diff(spikes) >= 0):
            spikes = np.sort(spikes)
        for t_i, onset in enumerate(onsets):
            lo = np.searchsorted(spikes, onset + w0_s, side="left")
            hi = np.searchsorted(spikes, onset + w1_s, side="right")
            rel_ms = ((spikes[lo:hi] - onset) * 1000.0).astype(np.float32)
            spike_chunks.append(rel_ms)
            running += len(rel_ms)
            offsets[u_i, t_i + 1] = running

    spike_times_ms = (
        np.concatenate(spike_chunks) if spike_chunks else np.zeros((0,), dtype=np.float32)
    )
    return {
        "unit_ids": np.asarray(unit_ids, dtype=np.int64),
        "trial_onsets": onsets,
        "offsets": offsets,
        "spike_times_ms": spike_times_ms,
    }


def main() -> None:
    args = parse_args()
    window_ms = (float(args.window_ms[0]), float(args.window_ms[1]))

    session_row = resolve_session(args.catalog, args.session)
    stem = session_row["stem"]
    nwb_path = Path(session_row["path"])
    if session_row.get("short_nwb"):
        print(f"[materialize] warning: {stem} is a short-nwb (truncated) file")

    units_df = load_sidecar_units(args.meta_root, stem, args.area)
    if args.max_units is not None:
        units_df = units_df.head(args.max_units)
    unit_ids = [int(u) for u in units_df["unit_id"].tolist()]
    if not unit_ids:
        raise SystemExit(f"No units left after filtering for {stem} (area={args.area})")

    cfg = {
        "stem": stem,
        "phase": args.phase,
        "condition": args.condition,
        "window_ms": list(window_ms),
        "correct_only": not args.include_incorrect,
        "area": args.area,
        "max_units": args.max_units,
        "n_units_requested": len(unit_ids),
    }
    cfg_hash = config_hash(cfg)
    tag = config_tag(args.phase, args.condition, window_ms, args.area)
    out_dir = args.out_root / stem / tag
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.overwrite and existing_manifest_matches(out_dir, cfg_hash):
        print(f"[materialize] {out_dir} already up to date (config_hash={cfg_hash}); skipping "
              f"(use --overwrite to force)")
        return

    print(f"[materialize] loading session {stem} <- {nwb_path}")
    session = oa.read(nwb_path)

    epochs = session.get_epochs(
        phase=args.phase, condition=args.condition, correct_only=not args.include_incorrect
    )
    if len(epochs) == 0:
        raise SystemExit(
            f"No epochs matched phase={args.phase} condition={args.condition} "
            f"correct_only={not args.include_incorrect} for {stem}"
        )
    epochs = epochs.reset_index(drop=True)

    print(
        f"[materialize] {stem}: {len(unit_ids)} units x {len(epochs)} trials, "
        f"window_ms={window_ms}, phase={args.phase}, condition={args.condition}"
    )

    arrays = materialize(session, unit_ids, epochs, window_ms)

    np.save(out_dir / "unit_ids.npy", arrays["unit_ids"])
    np.save(out_dir / "trial_onsets.npy", arrays["trial_onsets"])
    np.save(out_dir / "offsets.npy", arrays["offsets"])
    np.save(out_dir / "spike_times_ms.npy", arrays["spike_times_ms"])

    trial_cols = [
        c
        for c in ["id", "trial_num", "stimulus_number", "task_condition_number", "correct",
                  "is_omission", "start_time"]
        if c in epochs.columns
    ]
    epochs[trial_cols].to_csv(out_dir / "trial_index.csv", index=False)

    sizes_bytes = {
        f.name: f.stat().st_size
        for f in out_dir.iterdir()
        if f.is_file() and f.suffix in (".npy", ".csv")
    }

    manifest = {
        "config_hash": cfg_hash,
        "config": cfg,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "nwb_path": str(nwb_path),
        "n_units": len(unit_ids),
        "n_trials": int(len(epochs)),
        "n_spikes_total": int(arrays["spike_times_ms"].shape[0]),
        "shapes": {
            "unit_ids": list(arrays["unit_ids"].shape),
            "trial_onsets": list(arrays["trial_onsets"].shape),
            "offsets": list(arrays["offsets"].shape),
            "spike_times_ms": list(arrays["spike_times_ms"].shape),
        },
        "dtypes": {
            "unit_ids": str(arrays["unit_ids"].dtype),
            "trial_onsets": str(arrays["trial_onsets"].dtype),
            "offsets": str(arrays["offsets"].dtype),
            "spike_times_ms": str(arrays["spike_times_ms"].dtype),
        },
        "file_bytes": sizes_bytes,
        "spike_times_units": "ms, relative to trial_onsets[t] (seconds, session clock)",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    total_bytes = sum(sizes_bytes.values())
    print(f"[materialize] wrote {out_dir} ({total_bytes / 1e6:.2f} MB total)")
    for name, sz in sizes_bytes.items():
        print(f"  {name}: {sz / 1e6:.3f} MB")


if __name__ == "__main__":
    main()
