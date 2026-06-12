#!/usr/bin/env python3
"""Build f005 A-family SPK p1 epoch artifact via jnwb."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import jnwb


def main() -> int:
    parser = argparse.ArgumentParser(description="Build A-family SPK p1 epochs for f005")
    parser.add_argument("--nwb-root", required=True, help="Root directory containing NWB files")
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["AAAB", "AXAB", "AAXB", "AAAX"],
    )
    parser.add_argument("--anchor", default="p1")
    parser.add_argument("--window-ms", nargs=2, type=int, default=[-1000, 4000])
    parser.add_argument("--bin-ms", type=float, default=1.0)
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10000,
        help="Trial chunk size during extraction (default: full session per chunk)",
    )
    parser.add_argument(
        "--out",
        default="outputs/f005/afamily_spk_p1_epochs.npz",
    )
    parser.add_argument(
        "--manifest",
        default="outputs/f005/afamily_spk_p1_epochs_manifest.json",
    )
    parser.add_argument(
        "--subject",
        default=None,
        help="Optional subject filter, e.g. sub-V198o",
    )
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help="Optional cap on number of event-bearing sessions to extract",
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = " ".join(sys.argv)

    print("Discovering NWB files...")
    files = jnwb.list_nwb_files(args.nwb_root)
    print(f"  Found {len(files)} files")

    manifest_df = jnwb.build_session_manifest(files, out=out_path.parent / "afamily_spk_p1_signal_inventory.csv")

    ev = jnwb.address_events(
        files,
        task="omission_glo_passive",
        conditions=args.conditions,
        anchor=args.anchor,
        correct=True,
    )
    session_list = ev.sessions
    if args.subject:
        subj = args.subject.replace("-", "_")
        session_list = [s for s in session_list if subj in s]
    if args.max_sessions is not None:
        session_list = session_list[: args.max_sessions]
    if not session_list:
        raise SystemExit("No sessions matched filters")

    files = [f for f in files if jnwb.files.session_key_from_record(f) in session_list]
    ev = jnwb.address_events(
        files,
        task="omission_glo_passive",
        conditions=args.conditions,
        anchor=args.anchor,
        correct=True,
        sessions=session_list,
    )
    sig = jnwb.address_signals(
        files,
        signal="SPK",
        areas=None,
        require_area=False,
        sessions=session_list,
    )

    jnwb.validate_signal_address(sig)
    jnwb.validate_event_address(ev)

    epochs = jnwb.load_epochs(
        files,
        sig,
        ev,
        window_ms=(args.window_ms[0], args.window_ms[1]),
        chunk_size=args.chunk_size,
        backend="numpy",
        bin_ms=args.bin_ms,
    )

    batches = list(epochs) if not isinstance(epochs, jnwb.EpochBatch) else [epochs]

    artifact_manifest = jnwb.save_epoch_artifact(
        batches,
        out=out_path,
        manifest=args.manifest,
        command=cmd,
        input_nwb_paths=[f.path for f in files],
    )

    loaded = jnwb.load_epoch_artifact(out_path)
    shape = [tuple(np.asarray(b.data).shape) for b in batches]
    trial_df = loaded.trial_metadata
    signal_df = loaded.signal_metadata

    receipts = pd.DataFrame(
        [
            {
                "artifact": str(out_path),
                "signal": "SPK",
                "conditions": ",".join(args.conditions),
                "shape": str(shape),
                "window_ms": f"{args.window_ms[0]},{args.window_ms[1]}",
                "bin_ms": args.bin_ms,
                "dtype": str(np.asarray(batches[0].data).dtype) if batches else "unknown",
                "status": "SUCCESS",
            }
        ]
    )
    receipts.to_csv(out_path.parent / "afamily_spk_p1_shape_receipts.csv", index=False)

    trial_df.to_csv(out_path.parent / "afamily_spk_p1_trial_metadata.csv", index=False)
    signal_df.to_csv(out_path.parent / "afamily_spk_p1_unit_metadata.csv", index=False)
    manifest_df.to_csv(out_path.parent / "afamily_spk_p1_signal_inventory.csv", index=False)

    print(f"Saved artifact: {out_path}")
    print(f"Shape: {shape}")
    print(f"Manifest: {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
