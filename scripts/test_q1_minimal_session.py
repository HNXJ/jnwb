#!/usr/bin/env python3
"""
Test Q1 on single session directly using SpectralRelationsPipeline.
Compare with debug output to find divergence.
"""

from pathlib import Path
from scripts.spectral_relations_pipeline import SpectralRelationsPipeline

# Initialize pipeline
pipeline = SpectralRelationsPipeline()

print(f"TFR files found: {len(pipeline.tfr_files)}")
print(f"Sessions in data: {sorted(set(int(f.split('ses-')[1].split('-')[0]) for f in pipeline.tfr_files))}")

# Run Q1
print("\n=== Running Q1 ===")
result = pipeline.run_q1_full_depth()

print(f"\n=== Q1 Result ===")
if result is not None:
    print(f"Q1 returned DataFrame with {len(result)} rows")
    print(f"Columns: {result.columns.tolist()}")
    print(f"\nFirst few rows:")
    print(result.head())
else:
    print("Q1 returned None")

print(f"\nq1_results list size: {len(pipeline.q1_results)}")
