# Omission Agent Memory

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

## Local Skills To Prefer

Read these skill files before implementation:

- `.agents/skills/nwb-io/SKILL.md`
- `.agents/skills/spiking/SKILL.md`
- `.agents/skills/single-unit-grand-table/SKILL.md`
- `.agents/skills/single-unit-raster-suite-and-traces/SKILL.md` when plotting rasters/traces.

## Current Agent Stance

Question everything that touches timing, condition grouping, waveform units, and layer assignment. The data are powerful, but small off-by-one or code-system errors will look biologically plausible if not caught.

