# PRP — omission
## Current Plan
- Establish remote SSH execution workflow to run fast analysis on remote NWB files and export to intermediate formats (e.g., `.npz`, `.parquet`).
- Verify remote python/conda environment dependencies for NWB processing.
- Create example script demonstrating fast remote preprocessing and local visual validation.
## Last Review
- 2026-07-06: Verified TFR trace visualization suite output with gaussian-smoothed lines and significance flat-lining.
## Progress Log
- 2026-07-06: Added planned analysis suites 01-10 to `plans.json`.
- 2026-07-06: Implemented gaussian trace smoothing and significance flat-lining in `jnwb/viz.py`.
- 2026-07-07: Pushed local dev branch commits to remote repository via SSH-agent.

