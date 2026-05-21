# Fixture SignalBlock Loader Scaffolds Report (Phase 2G)

## Purpose
This report documents the design, implementation, and validation of Phase 2G: synthetic/fixture `SignalBlock` loader scaffolds. We have established a pure in-memory, zero-read generation facility for creating contract-compliant `SignalBlock` objects. This allows downstream downstream analytical code to run integration tests, trace pipeline configurations, and perform mathematical/statistical assertions without requiring or loading high-density raw binary files from disk.

## Fixture SignalBlock Fields and Structures
The generated synthetic `SignalBlock` instances include all necessary fields defined in the Omission contract system:
- `data`: A tiny, pre-allocated in-memory constant float matrix filled with customizable `fill_value` (defaulting to `0.0`).
- `dims`: A dimensions tuple matching target axes based on signal class rules:
  - SPK / SUA: `("trial", "unit", "time")`
  - MUAe / LFP: `("trial", "channel", "time")`
- `signal_class`: Validated experimental signal class (`"SPK"`, `"SUA"`, `"MUAe"`, `"LFP"`).
- `session_id`: Session label (default `"fixture_session"`).
- `condition`: Trial condition label (default `"AAAB"`).
- `time_base`: Preserved alignment time-base (supports `"p1_relative"`, `"omission_relative"`).
- `alignment_event`: The designated event timestamp index alignment label (default `"p1_onset"`).
- `window_ms`: An offset window range tuple (default `(-1000, 4000)`).
- `sampling_rate`: Auto-selected fallback rates based on constants: `30000.0` for SPK/SUA, `1000.0` for LFP/MUAe.
- `unit_or_channel_ids`: Dynamically formatted list of labels (e.g. `["fixture_session_unit_0", ...]`).
- `area_labels`: Custom or auto-selected canonical areas (normalized automatically; DP is normalized to V4, and unresolved generic V3 triggers appropriate warnings).
- `area_resolution_status`: Dictionary mapping unit/channel IDs to anatomical resolution status values.
- `provenance`: Gated receipt asserting `type: "fixture_synthetic"` and `message: "no raw data read"` to verify zero disk/file side-effects.
- `truth_status`: Enforced metadata contract safety tier.

## Supported Signal Classes
- **SPK** (Spiking Activity - multiunit)
- **SUA** (Single Unit Activity)
- **MUAe** (Multi-Unit Activity envelope)
- **LFP** (Local Field Potential)

## Shape Guarantees
The synthetic loader guarantees structural shape conformity:
- **SPK/SUA**: Exactly `(n_trials, n_units_or_channels, n_time)` with dimensions `("trial", "unit", "time")`.
- **MUAe/LFP**: Exactly `(n_trials, n_units_or_channels, n_time)` with dimensions `("trial", "channel", "time")`.
- **Anatomical Alignment**: The length of the `area_labels` and `unit_or_channel_ids` lists is strictly verified to match `n_units_or_channels` (the size of the unit/channel axis).

## What is Still Not Real-Data Loading
- No `.nwb`, `.mat`, `.h5`, `.hdf5`, `.npy`, or `.npz` arrays are opened, read, mapped, or queried on disk.
- All operations remain completely in-memory, relying on `numpy.full` matrix generation.
- There are no disk stat or lookup operations performed against actual neural dataset paths.

## Remaining Blockers
- **Safe Gated Accessors (Phase 3)**: Downstream production accessors still need to transition from fixture generation to reading mmap slices from real files, but only when `OMISSION_DATA_ROOT` is set and file checks succeed.
- **Pipeline smoke integration**: Downstream visualizers and figures must be updated to accept `SignalBlock` inputs rather than loose numpy matrices.

## Truth Status
- **Truth Tier Enforced**: `truth_safe_unverified`
- All files, records, and mock blocks verified under Phase 2G are strictly locked at `truth_safe_unverified`. No biological, manuscript, or model claims are promoted without receipt verification.

---
Footer: Agent: Antigravity / Model: Gemini 3.5 Flash / Role: Codebase Hardening Specialist / Plane: implementation/contracts / Repo or Workspace: D:\workspace\omission / Date: 2026-05-21
