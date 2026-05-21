# Phase 2 Metadata/Data‑Contract Hardening Plan

**Repository:** `D:\workspace\omission`
**Branch:** `phase2-metadata-contracts`
**HEAD:** `860d3dc`

## Goals
1. Define a robust **real‑session manifest schema** that captures all required provenance fields.
2. Implement **condition‑code validation** to ensure every analysis run uses a registered condition identifier.
3. Establish an **area‑mapping provenance** pipeline that tracks area‑to‑probe/channel relationships and alias handling (DP→V4, V3/V3d/V3a).
4. Provide a **SignalBlock‑style return contract** for all data‑access functions (shape, dims, signal class, session, condition, time‑base, alignment, sampling rate, unit/channel IDs, area labels, provenance, warnings).
5. Split **integration tests** into:
   - **Fixture‑only tests** (run on CI, no data dependencies).
   - **Real‑data tests** guarded by the environment variable `OMISSION_DATA_ROOT` pointing to the raw data root.

## Manifest Schema (JSON) – Required Fields
- `subject` (string)
- `session_id` (string)
- `recording_date` (ISO‑8601 date)
- `task_type` / `block_type` (string)
- `condition_code_map` (object mapping condition names → codes)
- `trial_counts` (object mapping condition → integer)
- `probe_ids` (list of integers)
- `area_labels` (object mapping probe → list of area strings)
- `channel_ranges` (object mapping area → [start, end] inclusive)
- `dp_to_v4_alias` (boolean)
- `v3_variants` (list of strings, e.g., `V3d`, `V3a`)
- `signal_classes` (list: `SPK`, `MUAe`, `LFP`)
- `channel_counts_by_area` (object)
- `unit_counts_by_area` (object)
- `unit_peak_channels` (object mapping unit_id → channel)
- `area_resolution_status` (object mapping area → `resolved`|`unresolved`|`blacklisted`)
- `exclusions` (list of objects with `reason` and `details`)
- `source_files` (list of file paths used to generate the manifest)
- `hashes` (object mapping source_file → SHA‑256)
- `warnings` (list of strings)
- `generated_at` (timestamp)
- `generated_by` (script name)
- `git_commit` (SHA of the code used)
- `truth_status` (must be `truth_safe_unverified` for all generated manifests)

## SignalBlock Return Contract (Python dict example)
```python
{
    "data_shape": (n_trials, n_units, n_time),
    "dims": ["trial", "unit", "time"],
    "signal_class": "SPK",
    "session_id": "230630",
    "condition": "AXAB",
    "time_base": "ms",
    "alignment_event": "stim_onset",
    "window_ms": [-100, 500],
    "baseline_ms": [-100, 0],
    "sampling_rate": 1000,
    "unit_or_channel_ids": [0, 1, 2, ...],
    "area_labels": {0: "V1", 1: "V2", ...},
    "area_resolution_status": {"V1": "resolved", "V3": "unresolved"},
    "source_files": ["data/arrays/...", "metadata/session_230630.json"],
    "warnings": [],
    "provenance": {
        "generated_at": "2026-05-21T00:12:00Z",
        "generated_by": "build_signal_block.py",
        "git_commit": "860d3dc…",
    },
    "truth_status": "truth_safe_unverified",
}
```

## Validation Commands (to be run in CI)
1. `python -m compileall src tests scripts`
2. `python -m pytest -q` (fixture‑only tests)
3. `python scripts/audit_figure_registry.py` (ensures no missing modules)
4. `python scripts/validate_manifest.py --schema manifest_schema.json` (lint against schema)
5. `python scripts/validate_signalblock.py --example examples/signalblock.json`

## Stop Conditions
- Any manifest fails JSON‑schema validation.
- `git diff --name-status` shows changes to files outside `src/`, `tests/`, `reports/`, or `artifacts/`.
- Pytest fails.
- Registry audit reports missing modules.
- Generated HTML figures are modified without corresponding pipeline version bump.

## Truth Status
All new artifacts, manifests, and contracts are explicitly labeled `truth_safe_unverified` until a downstream review provides evidence‑based validation.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: coding-assistant / Plane: execution / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21 05:20
