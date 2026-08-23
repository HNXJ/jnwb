**SUPERSEDED (2026-08-22).** This is the pre-2026-06-25 agent orientation doctrine for an old
`D:\workspace\omission` layout: 13-session corpus (current: 22), `D:/analysis/nwb` /
`D:/workspace/omission` paths (no longer the layout), a 6,040-unit grand database (current:
9,061 units), and `.agents/skills/` files that do not exist in the current tree. **Do not follow
any instruction below as current doctrine** — current doctrine is [`omission/CLAUDE.md`](../../CLAUDE.md)
plus the `omission/.claude/skills/` skills it names. Kept for historical provenance only.

The "Spectral Relations & Network Analysis" section below claimed three established "Key
Findings" (Q1/Q2/Q3). Checked against the pipeline's own surviving output during normalization —
**not reproducible**: Q1 computed zero correlations, Q3's output is degenerate (near-constant
correlation, near-zero lag range), and Q2's cross-modal claim depends on Q1 which doesn't exist.
See [`spectral_relations_pipeline_2025_unverified.md`](../docs/spectral_relations_pipeline_2025_unverified.md)
for the full check. None of the three findings have been carried into current evidence.

---

# Omission Agent Memory (historical, superseded — see banner above)

This file is the local agent orientation note for `D:\workspace\omission`. Treat it as the first stop before doing single-unit, waveform, NWB, LFP, or figure work.

## Project Doctrine

- Omission is a missing expected stimulus, not a generic task-condition change.
- Use **correct trials only** for neural analysis unless explicitly auditing errors.
- Preserve signal classes: **SPK/SUA**, **MUAe**, and **LFP** are separate data products.
- Preserve session hierarchy and area/layer metadata before pooling.
- `p1` is the global alignment anchor for full-sequence analyses.
- Omission-relative analyses must preserve the surrounding `d-p-d-px-d` context.

## Canonical Data Topology

Primary raw NWB files live at:

```text
D:/analysis/nwb
```

There are 13 session `.nwb` files named:

```text
sub-<subject>_ses-<YYMMDD>_rec.nwb
```

Important derived data:

- `D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv`
  - Master 6,040-unit table.
  - Important fields include `session_id`, `unit_id`, `area`, `layer`, `probe_id`, `local_channel`, `peak_channel_global`, `is_stable`, `stable_plus`, `firing_rate`, `waveform_duration`, `sig_o_plus`, `sig_s_plus`, `sig_s_minus`, waveform-class flags.
- `D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json`
  - Spectrolaminar layer-mask and crossover configuration.
  - Main key: `by_key`.
  - Key format: `sub-<subject>_ses-<session>|<probe_letter>`.
- `D:/workspace/omission/outputs/data_index/batch_13nwb/`
  - `unit_address_book_all_sessions.csv`
  - `lfp_session_address_book_all_sessions.csv`
  - `event_timing_inventory_all_sessions.csv`
- `D:/workspace/data/tfr_arrays`
  - Precomputed TFR matrices.
  - Naming pattern: `<subject>_ses-<session>-<probe_letter>-<area>-<condition_code>.npy`.
- `D:/workspace/omission/outputs/publication_visual_review/tfr_correlations/cache/`
  - Trial-averaged aligned-power caches.
  - Naming pattern: `<area>_<layer>_aligned_power.npy`.

## NWB Event Model

The `nwb.intervals["omission_glo_passive"]` table is event-level, not trial-level. Repeated `trial_num` and repeated condition values are expected because each trial contributes multiple event rows.

Use the jNWB-style boolean filtering pattern:

```python
correct = interval["correct"] == 1.0
phase = interval["stimulus_number"] == phase_number
condition = interval["task_condition_number"].isin(condition_numbers)
events = correct & phase & condition
onsets = interval.loc[events, "start_time"].values
```

Do **not** count raw interval rows as trials without grouping or phase-filtering.

Phase identifiers:

| Phase | `stimulus_number` | NWB code | Meaning |
| --- | ---: | ---: | --- |
| fixation cue | 1 | 100 | fixation cue appearance |
| p1 | 2 | 101 | first stimulus, global alignment anchor |
| p2 | 3 | 102 | second stimulus / p2 omission slot |
| p3 | 4 | 103 | third stimulus / p3 omission slot |
| p4 | 5 | 104 | fourth stimulus / p4 omission slot |

Important caveat: behavioral `.mat`/BHV notes may use odd codes `101, 103, 105, 107`. NWB intervals use sequential event codes, but `stimulus_number` is the stable phase identifier. Prefer `stimulus_number` for phase selection.

## Condition Groups

Use these 12 canonical groups:

| Canonical ID | Condition | Raw condition numbers |
| ---: | --- | --- |
| 1 | AAAB | 1, 2 |
| 2 | AXAB | 3 |
| 3 | AAXB | 4 |
| 4 | AAAX | 5 |
| 5 | BBBA | 6, 7 |
| 6 | BXBA | 8 |
| 7 | BBXA | 9 |
| 8 | BBBX | 10 |
| 9 | RRRR | 11-26 |
| 10 | RXRR | 27-34 |
| 11 | RRXR | 35, 37, 39, 41 |
| 12 | RRRX | 36, 38, 40, 42-50 |

Current verification across all 13 NWB files: correct-event counts match exactly across p1, p2, p3, and p4 for every canonical condition group. Total correct complete-trial count per phase: **10,968**.

## Single Units and Waveforms

The current analysis focus is **single units and waveforms**.

Primary table:

```text
outputs/publication_figures/grand_database_6040_units.csv
```

Known active results from handoff:

- 49 verified omission units mapped across FEF/PFC.
- Session `230830` PFC required dual-crossover handling because of a white-matter gap.
- Unit 33 and Unit 77 in `230830` should map to **Deep** under the PFC dual-crossover bounds.
- MT/MST waveform split:
  - 287 initial units.
  - Waveforms detrended and min-max normalized to `[-1.0, 1.0]`.
  - Bottom third rejected as noisy/high-variance units: 97 units, about 34%.
  - Clean retained units: 190.
  - Median trough-to-peak split threshold: `1033.32 us`.
  - Narrow spiking: 86 units.
  - Wide spiking: 104 units.

Before extending these results, verify:

- whether waveform duration units are seconds, milliseconds, or microseconds in each source table;
- whether the median split was applied after the stated quality rejection;
- whether `stable_plus` is required for the exact analysis being run;
- whether area/layer mapping comes from the grand table, NWB electrodes, or `layer_masks.json`.

## FEF Spiking Reference

FEF exists in at least:

- `sub-C31o_ses-230823_rec.nwb`
- `sub-C31o_ses-230831_rec.nwb`

For `sub-C31o_ses-230823_rec.nwb`, prior inspection found:

- 368 total units.
- 156 FEF units, mapped via `nwb.electrodes.to_dataframe()["location"]` using `peak_channel_id`.
- `nwb.processing["convolved_spike_train"]["convolved_spike_train_data"]` shape:
  - `(20283769, 368)` = timepoints x units.
  - 1000 Hz timestamps.
- `nwb.units.to_dataframe()["spike_times"]` stores raw sparse spike times per unit.

Use convolved traces for continuous PSTH-like traces and raw spike times for rasters/counts. Do not conflate them.

## Spectral Relations & Network Analysis

The **spectral-relations-pipeline** is a production-grade multi-modal network analysis framework addressing three interconnected questions about omission encoding:

### Q1: Spectral Band Networks by Layer & Condition
- **Method**: Spearman rank correlation between areas within layer, with phase-randomized permutation testing (N=500)
- **Data**: 720 TFR files (all sessions, areas, conditions)
- **Bands**: Theta (4-8 Hz), Alpha (8-12 Hz), Beta (12-30 Hz), Low-gamma (30-55 Hz), High-gamma (55-90 Hz)
- **Conditions**: Stimulus, Baseline-pre-stim, Baseline-pre-omission, Omission, Baseline-post-omission
- **Statistics**: FDR correction (Benjamini-Hochberg, α<0.05) + dual threshold (|z|>1.96 effect size)
- **Key Finding**: Alpha and Beta bands show strongest inter-area correlations; ~73% of significant networks are condition-specific

### Q2: Spike Networks & Cross-Modal Comparison
- **Method**: Spearman correlation on 100ms spike-binned counts + permutation testing
- **Data**: 6,040 units across 13 NWB files
- **Lead Times**: Cross-correlation with variable lag (-500 to +500 ms)
- **Key Finding**: ~67% cross-modal consistency (LFP area-pairs preserved in spike networks); LFP leads spikes by 5-15ms

### Q3: Lead Time Analysis (Temporal Hierarchy)
- **Method**: Cross-correlation with variable lag across band/modality/area pairs
- **Significance**: Lag permutation test + FDR correction
- **Key Finding**: Temporal progression: Theta (-30ms, predictive) → Alpha (-10ms) → Beta (synchronous) → Gamma (+30ms, error confirmation)

### Pipeline Implementation
- **Location**: `scripts/spectral_relations_pipeline.py` and `scripts/spectral_network_visualizations.py`
- **Output Directory**: `outputs/spectral_relations_pipeline/`
- **Outputs**: 
  - `results/` — Q1, Q2, Q3 CSV files with full correlation/statistical data
  - `cache/` — Pickled intermediate DataFrames for rapid re-visualization
  - `figures/` — Network graphs, heatmaps, temporal hierarchies, cross-modal comparisons
- **Skill Reference**: `.agents/skills/spectral-relations-pipeline/SKILL.md` (parameter details, usage examples, troubleshooting)

### Critical Parameters
| Parameter | Value | Rationale |
|-----------|-------|---|
| N_PERMUTATIONS | 500 | Stable z-score estimates; power ≥0.95 |
| Z_THRESHOLD | 1.96 | Effect-size requirement (p<0.05 equivalent) |
| ALPHA_FDR | 0.05 | Standard significance threshold |
| SPIKE_BIN | 100ms | Matches behavioral response window |
| LAG_RANGE | ±500ms | Captures feedforward + feedback delays |

### Validated Methods & Assumptions
- **Permutation testing**: Shuffle sig2, recompute Spearman, z-score against distribution (correct method, avoids pseudo-pvalues)
- **Time window extraction**: +2000ms offset for behavioral baseline alignment within 4000ms TFR duration
- **FDR correction**: Applied across all comparisons within each question (conservative multi-comparison control)
- **Dual significance**: Requires BOTH FDR p<0.05 AND |z|>1.96 (prevents low-correlation noise)
- **Reproducibility**: PERMUTATION_SEED=42 ensures identical results across runs

### Limitations & Future Directions
1. **Temporal resolution**: 100ms spike binning masks sub-100ms dynamics; 10ms recommended for finer structure
2. **Layer anatomy**: CSD-based classification; imaging confirmation needed before strong anatomical claims
3. **Causality**: Correlations and leads are suggestive; optogenetics/inactivation required for directionality
4. **Behavior**: Correlations are task-agnostic; linking to performance/choice requires additional work

### When to Use This Pipeline
- Multi-modal network comparison (spectral vs spike)
- Inter-areal communication strength and directionality
- Frequency-band dynamics across behavioral conditions
- Temporal hierarchy of omission responses
- Cross-validation of LFP and spike networks

## Local Skills To Prefer

Read these skill files before implementation:

- `.agents/skills/spectral-relations-pipeline/SKILL.md` — Multi-modal network analysis (Q1/Q2/Q3 framework, methods, usage)
- `.agents/skills/nwb-io/SKILL.md`
- `.agents/skills/spiking/SKILL.md`
- `.agents/skills/single-unit-grand-table/SKILL.md`
- `.agents/skills/single-unit-raster-suite-and-traces/SKILL.md` when plotting rasters/traces.

## Current Agent Stance

Question everything that touches timing, condition grouping, waveform units, and layer assignment. The data are powerful, but small off-by-one or code-system errors will look biologically plausible if not caught.

