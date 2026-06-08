---
name: analysis-manifest-validation
---
# analysis-manifest-validation

## 1. Problem
Ensures that each notebook's manifest JSON contains all required provenance fields and conforms to the repository‑wide schema.

## 2. Solution Architecture
- Parses the manifest JSON produced by a notebook.
- Validates keys: `repo_sha`, `repo_branch`, `run_root`, and all artifact hash entries.
- Checks that `run_root` follows the pattern `outputs/runs/<full_repo_sha>_<nwb_hash_prefix>/`.

## 3. Trigger / Scope
- Triggered when a notebook execution finishes and emits a `manifest.json` file.
- Applies to any notebook in the `notebooks/` directory that produces a manifest.

## 4. Required Tools / Commands
- Python 3.14
- `json`, `re`, `pathlib`
- Access to the repository root (detected via `git rev-parse --show-toplevel`).

## 5. Stop Conditions / Blocker Codes
- `MISSING_MANIFEST`: Manifest file not found.
- `INVALID_SCHEMA`: Required keys missing or pattern mismatch.
- `DIRTY_REPO`: Repository has uncommitted changes.

## 6. Final Report Requirements
- Emits a JSON report with `status` (PASS/FAIL), `errors` (list of blocker codes), and a copy of the validated manifest.
- The report is saved alongside the manifest as `manifest_validation_report.json`.
