#!/usr/bin/env python3
"""Run jnwb visual QC and NWB analysis control suite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analysis.visualization.jnwb_qc import (
    QCConfig,
    JnwbQCBlockedError,
    run_synthetic_fixture_qc,
    run_visual_qc,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="jnwb visual QC control suite")
    parser.add_argument("--nwb-root", default="D:/analysis/nwb")
    parser.add_argument("--conditions", nargs="+", default=["AAAB", "AXAB", "AAXB", "AAAX"])
    parser.add_argument("--window-ms", nargs=2, type=int, default=[-100, 300])
    parser.add_argument("--bin-ms", type=float, default=1.0)
    parser.add_argument("--max-sessions", type=int, default=1)
    parser.add_argument("--max-units", type=int, default=20)
    parser.add_argument("--max-channels", type=int, default=16)
    parser.add_argument("--out", default="outputs/jnwb_visual_qc")
    parser.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Run labeled synthetic fixture QC (no NWB reads)",
    )
    args = parser.parse_args()
    cmd = " ".join(sys.argv)
    out_dir = Path(args.out)

    if args.synthetic_only:
        run_synthetic_fixture_qc(out_dir, command=cmd)
        print("SYNTHETIC_FIXTURE_QC_SUCCESS")
        return 0

    nwb_root = Path(args.nwb_root)
    if not nwb_root.exists():
        print("REAL_NWB_VISUAL_QC_SKIPPED_NO_DATA")
        run_synthetic_fixture_qc(out_dir / "synthetic_fixture", command=cmd + " [fallback]")
        return 1

    cfg = QCConfig(
        nwb_root=nwb_root,
        out_dir=out_dir,
        conditions=args.conditions,
        window_ms=(args.window_ms[0], args.window_ms[1]),
        bin_ms=args.bin_ms,
        max_sessions=args.max_sessions,
        max_units=args.max_units,
        max_channels=args.max_channels,
        command=cmd,
        data_label="REAL_NWB",
    )
    try:
        bundle = run_visual_qc(cfg)
        print(f"SUCCESS: {len(bundle.get('panels', {}))} panels -> {out_dir}")
        return 0
    except JnwbQCBlockedError as exc:
        print(f"BLOCKED: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
