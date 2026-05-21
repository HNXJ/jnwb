#!/usr/bin/env python3
# scripts/validate_bounded_signal_slice.py
"""
Phase 2I Bounded Real-Data SignalBlock Slice Smoke CLI Validator.
Exercises both synthetic fixture slice generation and safe gated real-data smoke checks.
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.contracts.bounded_slice import BoundedSliceRequest
from src.analysis.io.loader import DataLoader

def main():
    parser = argparse.ArgumentParser(description="Phase 2I Bounded Signal Slice CLI smoke validator")
    parser.add_argument("--fixture", action="store_true", help="Explicitly force fixture mode")
    parser.add_argument("--allow-real-data", action="store_true", help="Opt-in to allow real data checking")
    parser.add_argument("--source-path", help="Direct source file path to query")
    parser.add_argument("--signal-class", default="SPK", help="Target signal class (SPK, LFP, etc.)")
    parser.add_argument("--max-trials", type=int, default=1, help="Max trials bound")
    parser.add_argument("--max-units-or-channels", type=int, default=2, help="Max units/channels bound")
    parser.add_argument("--max-timepoints", type=int, default=100, help="Max timepoints bound")
    parser.add_argument("--max-bytes", type=int, default=1048576, help="Max bytes limit")
    parser.add_argument("--out", help="Optional report file path to save output JSON")
    args = parser.parse_args()

    print("Initializing Phase 2I Bounded Signal Slice CLI validator...")

    # Load data loader to resolve OMISSION_DATA_ROOT
    loader = DataLoader()
    data_root = loader.get_data_root()

    # Determine candidate path
    source_path = args.source_path
    if not source_path and args.allow_real_data:
        # If no explicit source path is given but real-data is allowed, try to find a manifest or file under OMISSION_DATA_ROOT
        if data_root and data_root.exists():
            candidates = loader.discover_session_manifest_paths(data_root)
            if candidates:
                source_path = str(candidates[0])
            else:
                # Fall back to checking any npy files
                npy_candidates = list(data_root.glob("**/*.npy"))
                if npy_candidates:
                    source_path = str(npy_candidates[0])

    # If both OMISSION_DATA_ROOT is absent and no --source-path is passed, print skipped and exit
    if not args.allow_real_data and not args.fixture:
        # Check environment
        if not os.environ.get("OMISSION_DATA_ROOT") and not args.source_path:
            print("SKIPPING: OMISSION_DATA_ROOT is absent and no --source-path is provided.")
            # Still run a quick fixture verification to confirm it works
            args.fixture = True

    # Construct request
    request = BoundedSliceRequest(
        session_id="cli_smoke_session",
        signal_class=args.signal_class,
        source_path=source_path,
        max_trials=args.max_trials,
        max_units_or_channels=args.max_units_or_channels,
        max_timepoints=args.max_timepoints,
        max_bytes=args.max_bytes,
        allow_real_data=args.allow_real_data and not args.fixture
    )

    print(f"Request: allow_real_data={request.allow_real_data}, source_path={request.source_path}")

    # Process via DataLoader
    result = loader.load_bounded_signal_slice(request)

    # Format output dictionary
    output_dict = {
        "status": result.status,
        "request": result.request,
        "errors": result.errors,
        "warnings": result.warnings,
        "bytes_read_estimate": result.bytes_read_estimate,
        "source_path": result.source_path,
        "raw_array_contents_read": result.raw_array_contents_read,
        "truth_status": result.truth_status,
        "has_signal_block": result.signal_block is not None
    }

    if result.signal_block:
        block = result.signal_block
        output_dict["signal_block_summary"] = {
            "signal_class": block.signal_class,
            "session_id": block.session_id,
            "dims": list(block.dims),
            "shape": block.data.shape if hasattr(block.data, "shape") else None,
            "area_labels": block.area_labels,
            "warnings": block.warnings
        }

    print("\n--- Bounded Slice Smoke Summary ---")
    print(json.dumps(output_dict, indent=2))
    print("------------------------------------\n")

    # If `--out` provided, write JSON
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output_dict, indent=2))
        print(f"[success] Output JSON saved to {out_path}")

    # Check status
    if result.status == "invalid":
        print(f"FAILED: Request validation failed with errors: {result.errors}")
        sys.exit(1)

    print("SUCCESS: CLI bounded signal slice smoke check completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()
