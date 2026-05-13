# Omission Gallery Semantic Schema (V1)

Every artifact indexed in the omission gallery should ideally carry this metadata to enable scientific discovery and evidence-based auditing.

## Required Fields

| Field | Description | Example |
| :--- | :--- | :--- |
| `figure_id` | Canonical ID (e.g., f048) | `f048` |
| `artifact_id` | Unique string within figure | `unit_response_profiles` |
| `title` | Human-readable title | `Unit Response Profiles by Area` |
| `signal_class` | Primary data signal | `SPK/SUA`, `LFP`, `MUAe`, `behavior` |
| `analysis_family` | Methodology class | `TFR`, `SFC`, `PSTH`, `Granger` |
| `time_base` | Temporal alignment | `omission_relative`, `p1_relative` |
| `alignment_event` | Reference trigger | `omission_onset`, `p1_onset` |
| `window_ms` | Analysis window | `[-500, 1000]` |
| `baseline_ms` | Normalization window | `[-500, 0]` |
| `conditions` | Task conditions included | `["standard", "omission"]` |
| `controls` | Control conditions | `["surrogate_omission"]` |
| `contrast` | The key comparison | `omission vs standard` |
| `areas` | Brain areas included | `["V1", "V3d", "V4", "PFC"]` |
| `area_resolution_status` | Status of area mapping | `validated`, `provisional` |
| `averaging_level` | Level of data aggregation | `trial`, `session`, `subject` |
| `inferential_unit` | Unit for stats | `channel`, `unit`, `session` |
| `inference_tier` | Level of claim strength | `descriptive_channel_level` |
| `validation_status` | Build/Logic status | `prototype`, `validated` |
| `source_script` | Script that generated it | `src/f048_profile_analysis/main.py` |
| `registry_status` | Status in FigureRegistry | `ACTIVE_CANONICAL` |
| `artifact_hash` | SHA256 of the file | `a1b2c3d4...` |
| `public_safe` | Safe for GitHub Pages | `true` |
| `warnings` | Known data/logic issues | `["Low unit count in V4"]` |

## Allowed Values

### `signal_class`
- `SPK/SUA`: Single-unit activity (sorted).
- `MUAe`: Multi-unit activity (envelope/threshold).
- `LFP`: Local field potential.
- `behavior`: Eye position, pupil, etc.
- `metadata`: Session info, area maps.
- `model`: Simulation or decoding outputs.
- `mixed`: Multiple signals (e.g., SFC).
- `unknown`: Default for unparsed artifacts.

### `time_base`
- `p1_relative`: Aligned to the first pulse in a sequence.
- `omission_relative`: Aligned to the missing pulse onset.
- `stimulus_relative`: Aligned to generic stimulus onset.
- `full_sequence`: Long continuous window.
- `static_summary`: Non-temporal data (e.g., area maps).
- `unknown`: Default.

### `inference_tier`
- `descriptive_trial_level`: Single-trial observation.
- `descriptive_channel_level`: Per-channel/unit summaries (no pooling).
- `unit_level_session_summarized`: Pooled units within a session.
- `session_level_population`: Statistical unit is the session.
- `subject_cautious_N2`: Cross-subject inference (limited N).
- `exploratory_unvalidated`: Pilot or debug output.
- `unknown`: Default.
