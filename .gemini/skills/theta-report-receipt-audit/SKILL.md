---
name: theta-report-receipt-audit
---
# theta-report-receipt-audit

## 1. Problem
Provides a final THETA receipt audit that aggregates the manifests and reports from Phase 00‑02 notebooks and validates that all required provenance fields are present before any downstream analysis or manuscript preparation.

## 2. Solution Architecture
- Scans the `outputs/runs/` directory for manifest JSON files.
- Verifies each manifest contains `repo_sha`, `repo_branch`, `run_root`, and artifact hashes.
- Confirms the `run_root` follows the required pattern `outputs/runs/<full_repo_sha>_<nwb_hash_prefix>/`.
- Generates a consolidated `theta_receipt_audit.json` summarizing pass/fail status per notebook and any blocker codes.

## 3. Trigger / Scope
- Triggered manually after Phase 00‑02 notebooks have been executed or as part of an automated pipeline.
- Applies to any repository using the Omission analysis framework.

## 4. Required Tools / Commands
- Python 3.14
- Standard library: `json`, `pathlib`, `re`
- Access to the repository root (detected via `git rev-parse --show-toplevel`).

## 5. Stop Conditions / Blocker Codes
- `MISSING_MANIFESTS`: No manifest JSON files found in the expected output directory.
- `INVALID_MANIFEST`: One or more manifests missing required keys or pattern mismatch.
- `DIRTY_REPO`: Repository has uncommitted changes when the audit runs.

## 6. Final Report Requirements
- Emits a JSON report `theta_receipt_audit.json` with fields:
  - `overall_status`: `PASS` or `FAIL`
  - `notebook_reports`: list of per‑notebook status objects
  - `errors`: list of blocker codes encountered
- The report is saved alongside the manifests in the `outputs/runs/` directory.
