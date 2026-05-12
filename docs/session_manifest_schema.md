# Session Manifest Schema (V1)

The session manifest is the canonical source of truth for a recording session, providing the metadata required for enriched artifact indexing and reproducible analysis.

## Core Structure

### Session Level
- `session_id`: 6-digit identifier (e.g., `230630`).
- `subject_id`: Non-human primate identifier.
- `manifest_version`: Version of this schema.
- `truth_status`: `truth_safe_unverified`.

### Signals
- `has_spk`, `has_muae`, `has_lfp`, `has_behavior`: Boolean availability flags.
- `sampling_rates`: Dict mapping signal type to Hz (e.g., `{"LFP": 1000.0}`).

### Conditions
- `conditions`: List of `ConditionInfo` objects.
  - `code`: Task code (e.g., `AXAB`).
  - `label`: Human readable label.
  - `trial_count`: Total trials for this condition.
  - `is_omission`: True if it's an omission trial.
  - `omission_slot`: 2, 3, or 4.

### Timing
- `p1_epoch_ms`: Default extraction window relative to p1 onset.
- `omission_onsets_ms`: Predicted onset of omissions for different slots.
- `tfr_baseline_ms`: Window for spectral normalization.

### Anatomy
- `area_mappings`: Channel-level probe-to-area partitioning.
  - `area`: Normalized area name (V1, V4, PFC, etc.).
  - `probe`: Probe index (0, 1, 2).
  - `resolution_status`: `validated`, `provisional`, or `unresolved`.
- `units`: Unit-level metadata for SPK/SUA.
  - `unit_id`: `session-probe-unit`.
  - `peak_channel`: Index of peak waveform.
  - `area`: Assigned area.

## Usage
Analyses should ingest the `session_manifest.json` to populate the `metadata` fields in their `figure_manifest.json` outputs, ensuring the gallery builder can index them with full scientific context.
