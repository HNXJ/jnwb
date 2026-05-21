#!/usr/bin/env python3
# scripts/validate_signalblock_downstream_smoke.py
"""
Phase 2H Synthetic SignalBlock Downstream Consumer CLI Smoke Validator.
Instantiates fixture blocks, runs summaries and axis reductions, and prints verification JSON.
"""

import sys
import json
import argparse
import numpy as np
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.contracts import (
    make_fixture_signal_blocks_for_all_signals,
    as_array,
    assert_signal_dims,
    summarize_signal_block,
    split_signal_axis
)

def main():
    parser = argparse.ArgumentParser(description="Phase 2H Downstream Consumer CLI smoke validator")
    parser.add_argument("--out", help="Optional report file path to save validation output")
    args = parser.parse_args()
    
    print("Initializing Phase 2H synthetic SignalBlock downstream consumer CLI validator...")
    
    # 1. Generate all signals
    blocks = make_fixture_signal_blocks_for_all_signals(
        session_id="downstream_smoke_session",
        n_trials=4,
        n_units_or_channels=6,
        n_time=25,
        fill_value=3.5
    )
    
    results = {}
    for name, block in blocks.items():
        # Validate the block itself first
        validation_errors = block.validate()
        if validation_errors:
            print(f"Error: Block validation failed for {name}: {validation_errors}")
            sys.exit(1)
            
        # Get array data via adapter
        arr = as_array(block)
        
        # Verify shape
        shape = list(arr.shape)
        
        # Perform trivial mean reduction over time axis
        axes = split_signal_axis(block)
        time_ax = axes["time_axis"]
        mean_val = np.mean(arr, axis=time_ax)
        
        # Verify reduction shape is (n_trials, n_units_or_channels) -> (4, 6)
        reduction_shape = list(mean_val.shape)
        reduction_mean = float(np.mean(mean_val))
        
        # Get metadata summary via adapter
        summary = summarize_signal_block(block)
        
        # Build JSON results entry
        results[name] = {
            "metadata": summary,
            "data_shape": shape,
            "time_axis_index": time_ax,
            "reduction_shape": reduction_shape,
            "reduction_mean": reduction_mean,
            "is_reduction_correct": np.allclose(reduction_mean, 3.5),
            "axes_indices": axes
        }
        
    print("\n--- Downstream Validation Summary ---")
    print(json.dumps(results, indent=2))
    print("--------------------------------------\n")
    
    # Check correctness
    for name, res in results.items():
        if not res["is_reduction_correct"]:
            print(f"Error: Downstream reduction result incorrect for {name}.")
            sys.exit(1)
            
    print("SUCCESS: All downstream consumer checks completed successfully.")
    
    # Write output if requested
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"[success] Summary JSON saved to {out_path}")
        
    sys.exit(0)

if __name__ == "__main__":
    main()
