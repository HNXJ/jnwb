#!/usr/bin/env python3
"""Smoke test for jnwb LFP/MUAe analog epoch loading."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

import jnwb


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke jnwb analog epoch loading")
    parser.add_argument("--nwb-root", required=True)
    parser.add_argument("--signal", choices=["LFP", "MUAe"], required=True)
    parser.add_argument("--conditions", nargs="+", default=["AAAB", "AXAB", "AAXB", "AAAX"])
    parser.add_argument("--anchor", default="p1")
    parser.add_argument("--window-ms", nargs=2, type=int, required=True)
    parser.add_argument("--chunk-size", type=int, default=8)
    parser.add_argument("--max-channels", type=int, default=8)
    args = parser.parse_args()

    root = Path(args.nwb_root)
    if not root.exists():
        print("REAL_NWB_SMOKE_SKIPPED_NO_DATA")
        return 1

    files = jnwb.list_nwb_files(root)
    if args.signal == "LFP":
        files = [f for f in files if f.has_lfp]
    else:
        files = [f for f in files if f.has_muae]
    if not files:
        print("REAL_NWB_SMOKE_SKIPPED_NO_DATA")
        return 1

    smoke_session = jnwb.files.session_key_from_record(files[0])
    ev = jnwb.address_events(
        files,
        conditions=args.conditions,
        anchor=args.anchor,
        correct=True,
        sessions=[smoke_session],
    )
    sig = jnwb.address_signals(
        files,
        signal=args.signal,
        sessions=ev.sessions,
        require_area=False,
        max_items=args.max_channels,
    )

    epochs = jnwb.load_epochs(
        [f for f in files if f.path in sig.source_paths],
        sig,
        ev,
        window_ms=(args.window_ms[0], args.window_ms[1]),
        chunk_size=args.chunk_size,
    )
    batches = list(epochs) if not isinstance(epochs, jnwb.EpochBatch) else [epochs]
    for i, b in enumerate(batches):
        print(
            f"batch={i} shape={np.asarray(b.data).shape} "
            f"fs={b.manifest.get('sampling_rate_hz')} "
            f"path={b.manifest.get('object_path')}"
        )
    print("SUCCESS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
