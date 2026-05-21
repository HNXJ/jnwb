[Gemini 3.5 Flash][D:\workspace\omission][20260521-1735]

# Phase 2K Session Manifest Production Scaffold and Validation Report

This report documents the design, implementation, and verification of the production-grade session manifest validator/scaffold developed during Phase 2K.

## 1. Purpose

The objective of Phase 2K is to establish a non-destructive scaffolding and validation layer for session metadata. This scaffolding process discovers unique sessions, aggregates metadata-like file paths, inspects files for contract violations (e.g. area mapping normalization, unresolved generic areas), and determines signal availability. It does so without generating canonical manifests under `data/manifests/` or writing any files into `OMISSION_DATA_ROOT`.

## 2. Scanned Metadata Types

The scaffold scans and processes the following lightweight, metadata-like file formats:
- **JSON (`.json`)**: Configuration, session properties, subjects, conditions, and signal availability info.
- **CSV (`.csv`) / TSV (`.tsv`)**: Unit peak channel maps, local indexing, and probe segment assignments.
- **YAML (`.yaml`/`.yml`)**: Configuration and schema definitions.
- **TXT (`.txt`) / Markdown (`.md`)**: Context notes and descriptive files.

## 3. Blocked Raw Formats

To enforce Phase 2 strict safety protocols, high-density raw binary files are absolutely blocked from being opened, parsed, or loaded into memory:
- **Blocked formats**: `.nwb`, `.mat`, `.hdf5`, `.h5`, `.npy`, `.npz`
- **Safety Policy**: The loader checks for the presence of these files only through directory-entry metadata (`os.scandir` filename checks) to verify `signal_availability` (e.g., detecting if `ses230630-probe1-lfp-AXAB.npy` exists). The contents of these files are never opened or read.

## 4. Why Canonical Manifests Are Not Created Yet

Writing canonical manifests to `data/manifests/` or mutating the empirical data directory is strictly decoupled from the discovery phase. This ensures:
1. **Contract Integrity**: Metadata fields, subjects, date formatting, and probe area normalizations are validated before they are persisted as truth.
2. **Zero-Mutation Safe Workspace**: The indexing engine operates in a read-only fashion over the target raw/metadata directory.
3. **No Unverified Science**: Prevents any premature claims from being saved into the repo.

## 5. Missing-Field Semantics

If essential session descriptors (such as `subject`, `recording_date`, or `area_mappings`) cannot be found or resolved in the metadata-like files, the scaffold:
- Fills the respective field with `None` (or `unknown`/`False`).
- Appends a descriptive warning (e.g., `"Missing required field: subject"`) to the candidate's warnings list.
- **No Heuristics / Mocking**: Explicitly avoids mocking or faking values for missing entries.

## 6. Remaining Blockers Before Real Manifest Production

Before generating and saving canonical manifests, the following items must be verified/implemented:
1. **Empirical Area Bound Checks**: Aligning precise channel bounds to physical probe coordinate registers.
2. **Subject DB Convergence**: Linking with a single validated subject index.
3. **Final Downstream Figure Integration**: Proving that the exact schema produced is fully consumed by the analytical figures without modification.

## 7. Verification Evidence

All 12 major requirements have been verified via unit tests in `tests/test_manifest_scaffold.py`:
1. Gating check (missing data root skips cleanly).
2. JSON metadata discovery candidate matching.
3. CSV area violation detection.
4. Raw files ignored/not opened.
5. Missing required field handling.
6. normalization of DP areas.
7. warning on generic V3 areas.
8. CLI command validation writing exclusively to requested output paths.
9. Refusal to create directories under `data/manifests/`.
10. Gated paths (no usage of `D:/drive`).
11. Strict compliance to `truth_safe_unverified`.
12. CLI exit codes.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: implementation/contracts / Plane: implementation/contracts / Repo or Workspace: omission / Date: 2026-05-21

[Gemini 3.5 Flash][D:\workspace\omission][20260521-1735]
