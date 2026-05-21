# Bounded Real-Data Session Manifest Validator Report (Phase 2D)

## Purpose
This report documents the implementation and operational boundaries of the read-only metadata manifest validator (`scripts/validate_session_manifest_contract.py`). The validator is designed to ensure strict compliance of real-world metadata manifests with Phase 2 data schema contracts, protecting downstream analysis pipelines from silent channel drops, misassignments, or heuristic area resolution drifts.

## Script Path
- The validation script is located at [validate_session_manifest_contract.py](file:///D:/workspace/omission/scripts/validate_session_manifest_contract.py).
- Unit tests are located at [test_session_manifest_validator.py](file:///D:/workspace/omission/tests/test_session_manifest_validator.py).

## Skip Behavior
- **Guarded Mode**: If `--manifest` is not explicitly provided, and neither `--data-root` nor the environment variable `OMISSION_DATA_ROOT` is set, the validator exits cleanly with status `0` and prints:
  ```text
  No --manifest provided, and neither --data-root nor OMISSION_DATA_ROOT is set.
  SKIPPING: Bounded manifest validation skipped safely.
  ```
- This guarantees that automated continuous integration (CI) pipelines and standard test suites without access to external experimental raw/derived data skip smoothly without triggering failures.

## Real-Data Boundary
- **Strictly Read-Only**: The script never writes to, modifies, or copies the data directory or any configuration files inside `data-root`.
- **Config/Metadata Only**: Only metadata JSON and session manifests are inspected. No high-density raw datasets (e.g., NWB, MAT, HDF5, NPY neural recording matrices) are loaded or parsed.
- **No Secrets Logging**: Zero tokens, SSH credentials, private system paths, or environment secrets are exposed in console prints or saved report artifacts.

## Fields and Constraints Validated
- **Metadata Identity**: Enforces presence of primary structural identifiers (`session_id` and `subject`).
- **Fixture Containment**: Prevents fixture/synthetic manifests from being accidentally presented or evaluated as real metadata-derived manifests within real data roots.
- **Area Normalization Mapping**: Scans anatomical mappings to verify that `DP` (dorsal posterior) and `DP (V4)` mappings have been normalized strictly to `V4`.
- **Generic Unresolved V3 Warning**: Detects any unresolved `V3` area mappings (which should trigger warning behavior in SessionManifest rather than being silently parsed or mapped heuristics-wise).
- **Required Fields Loop**: Checks the presence of all required dataclass keys defined in the centralized contracts constants `REQUIRED_SESSION_MANIFEST_FIELDS`.

## What is Not Validated Yet (Future Scope)
- **High-Density Signal Alignment**: The validator does not yet check if real spike time stamps or continuous LFP traces align directly with behavioral events.
- **Trial-by-Trial Manifest Completeness**: Validation does not inspect if raw trial counts dynamically match total indices of loaded tensors in active memory.
- **Cross-Area Synchronization**: Verification of probe-level clock offsets is out-of-scope for the read-only schema phase.

## Truth Status
- **Enforced Status**: `truth_safe_unverified`
- All validated session manifests must declare `truth_status = "truth_safe_unverified"`. No biological claims, model performance status, or manuscript figure claims are promoted to higher-tier truth statuses without explicit scientific receipt verification.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: implementation/contracts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21
