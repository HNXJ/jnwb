#!/usr/bin/env python
"""CLI wrapper around :mod:`jnwb.compression` -- fp32 + chunk + compress an NWB file.

The implementation lives in `jnwb/compression.py` (importable as `jnwb.compress_fp32`); this
file is only argument parsing and reporting, so there is exactly one copy of the logic and its
hard-won correctness notes. Read that module's docstring before changing conversion behavior.

Usage:
    python scripts/convert_nwb_compressed.py <input.nwb> <output.nwb> [--drop-convolved-spike-train]
    python scripts/convert_nwb_compressed.py <input.nwb> <output.nwb> --verify-only
    python scripts/convert_nwb_compressed.py <bloated.nwb> <compact.nwb> --compact-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# `python scripts/foo.py` puts scripts/ on sys.path[0], not the repo root, so jnwb is not
# importable without this. Repo convention -- matches compute_omission_identity_encoding.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jnwb.compression import compact, convert, verify_roundtrip  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("src", type=Path)
    ap.add_argument("dst", type=Path)
    ap.add_argument("--drop-convolved-spike-train", action="store_true")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--compact-only", action="store_true",
                     help="src is an already-converted (possibly bloated) file; just repack it into dst")
    args = ap.parse_args()

    if not args.src.exists():
        print(f"ERROR: source not found: {args.src}", file=sys.stderr)
        return 2

    if args.compact_only:
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        before = args.src.stat().st_size
        compact(args.src, args.dst)
        after = args.dst.stat().st_size
        print(f"compacted: {before/2**30:.2f} GiB -> {after/2**30:.2f} GiB "
              f"(reclaimed {(before-after)/2**30:.2f} GiB)")
        return 0

    if not args.verify_only:
        args.dst.parent.mkdir(parents=True, exist_ok=True)
        stats = convert(args.src, args.dst, drop_convolved=args.drop_convolved_spike_train)
        print(f"\n=== conversion stats ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        ratio = stats["src_bytes"] / stats["dst_bytes"] if stats["dst_bytes"] else float("nan")
        print(f"  size: {stats['src_bytes']/2**30:.2f} GiB -> {stats['dst_bytes']/2**30:.2f} GiB  ({ratio:.2f}x)")

    print("\n=== round-trip verification (byte samples + pynwb parse) ===")
    v = verify_roundtrip(args.src, args.dst)
    for c in v["checks"]:
        print(f"  {'OK  ' if c['ok'] else 'FAIL'}  {c['name']}: {c['detail']}")
    print(f"\nVERIFICATION {'PASSED' if v['ok'] else 'FAILED'}")
    return 0 if v["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
