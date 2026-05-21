#!/usr/bin/env python3
# scripts/validate_fixture_signal_blocks.py
"""
Phase 2G Synthetic/Fixture SignalBlock CLI Smoke Validator.
Instantiates fixture blocks for all signal classes and prints validation status.
"""

import sys
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.analysis.contracts.fixture_signal_blocks import make_fixture_signal_blocks_for_all_signals
from src.analysis.contracts.constants import TRUTH_SAFE_UNVERIFIED

def main():
    print("Initializing Phase 2G synthetic SignalBlock CLI validator...")
    
    # 1. Generate all signals
    blocks = make_fixture_signal_blocks_for_all_signals(
        session_id="cli_smoke_session",
        n_trials=3,
        n_units_or_channels=4,
        n_time=15
    )
    
    results = {}
    for name, block in blocks.items():
        errors = block.validate()
        
        # Serialize fields without raw data arrays for JSON printing
        results[name] = {
            "signal_class": block.signal_class,
            "session_id": block.session_id,
            "dims": block.dims,
            "data_shape": list(block.data.shape),
            "time_base": block.time_base,
            "area_labels": block.area_labels,
            "warnings": block.warnings,
            "provenance": block.provenance,
            "truth_status": block.truth_status,
            "validation_errors": errors,
            "is_valid": len(errors) == 0
        }
        
    print("\n--- JSON Validation Summary ---")
    print(json.dumps(results, indent=2))
    print("--------------------------------\n")
    
    # Exit with 1 if any validation fails
    for name, res in results.items():
        if not res["is_valid"]:
            print(f"Error: SignalBlock validation failed for {name}: {res['validation_errors']}")
            sys.exit(1)
            
    print("SUCCESS: All synthetic SignalBlocks are valid and verified.")
    sys.exit(0)

if __name__ == "__main__":
    main()
