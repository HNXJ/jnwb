[Gemini 3.5 Flash][D:\workspace\omission][20260521-1447]

# Bounded Real-Data SignalBlock Slice Smoke Report (Phase 2I)

## Purpose
This report documents the design, implementation, and verification of Phase 2I: bounded real-data `SignalBlock` slice smoke check scaffolding. We have established rigorous safety gates and highly bounded metadata request structures that permit downstream analysis utilities to request, validate, and check real data-slices while keeping actual raw payload reads completely blocked by default.

## Request & Result Contracts
The newly established contracts in `src/analysis/contracts/bounded_slice.py` govern all opt-in slice requests:
1. **BoundedSliceRequest**:
   - `session_id`: Session label of target arrays.
   - `signal_class`: Validated experimental signal class.
   - `source_path`: Optional location of target files.
   - `max_trials`: Max trial count bound (default `1`).
   - `max_units_or_channels`: Max unit or channel count bound (default `2`).
   - `max_timepoints`: Max time points bound (default `100`).
   - `max_bytes`: Conservative size limit in bytes (default `1048576` [1 MB]).
   - `allow_real_data`: Strictly default `False` opt-in gate.
   - `truth_status`: `truth_safe_unverified`.
2. **BoundedSliceResult**:
   - `status`: Structured execution state (`skipped`, `unavailable`, `blocked`, `loaded_bounded_slice`, `invalid`).
   - `request`: Parameter footprint dictionary of the query.
   - `signal_block`: `SignalBlock` object or `None`.
   - `errors` / `warnings`: Operational telemetry arrays.
   - `bytes_read_estimate`: Count of processed bytes (default `0`).
   - `raw_array_contents_read`: Checked gate to prove no raw payload leakage.
   - `truth_status`: Enforced metadata tier.

## Real-Data Gating Rules
- **Opt-in Guard**: If `allow_real_data` is `False`, the request immediately skips real-data queries and yields `status="skipped"`.
- **Anatomical Context availability**: If `source_path` is missing or the target file does not exist, the loader returns a clean `status="unavailable"` instead of crashing.
- **Extension Gating**: Only explicitly allowlisted text/JSON and standard raw array extensions are allowed; other file formats are blocked.
- **Size Bounds**: Files whose total bytes exceed `max_bytes` are rejected with `status="blocked"`.

## Why Raw Real-Data File Slicing is Still Blocked
- High-density arrays (such as `.nwb`, `.mat`, `.h5`, `.hdf5`, `.npy`, `.npz` files) are explicitly intercepted and returned with `status="blocked"` and a warning `"Raw real-data slicing not implemented yet under Phase 2I doctrine"`.
- This ensures that the system verifies parameters and tests the validation pathways without parsing binary files, preventing any accidental biological claim promotions.

## What Remains Required Before Real Payload Access
- **Empirical Reader Implementation (Phase 2J)**: Implementation of highly targeted readers (e.g. `np.load(..., mmap_mode='r')` for `.npy` arrays) to extract bounded matrix slices.
- **Verification against SessionManifests**: Verification of channel/unit mappings against loaded `SessionManifest` structures during real slicing.

## Truth Status
- **Truth Tier**: `truth_safe_unverified`
- Enforces strict contract layer isolation; no empirical truth assertions or manuscript claims are made.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: implementation/contracts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21

[Gemini 3.5 Flash][D:\workspace\omission][20260521-1447]
