# Authoritative Data Topology for Single-Unit and Waveform Work

Status: working handout  
Scope: NWB data, TFR arrays, unit database, layer masks, event semantics, waveform/single-unit next steps  
Truth status: `truth_safe_unverified`

This document captures the current repository/workstation topology for downstream agents working on single units and waveforms.

## 1. Primary Raw Dataset Directories

### NWB Directory

```text
D:/analysis/nwb
```

Contains 13 session `.nwb` files for subjects `C31o` and `V198o`.

Filename pattern:

```text
sub-<subject>_ses-<session>_rec.nwb
```

Example:

```text
sub-C31o_ses-230823_rec.nwb
```

### TFR Array Directory

```text
D:/workspace/data/tfr_arrays
```

Contains precomputed time-frequency representation arrays.

Reported inventory:

- 720 `.npy` matrices.
- Filename pattern:

```text
<subject>_ses-<session>-<probe_letter>-<area>-<condition_code>.npy
```

Example:

```text
sub-C31o_ses-230823-C-FEF-AXAB.npy
```

## 2. Derived Indices and Manifests

### Vetted Unit Grand Database

```text
D:/workspace/omission/outputs/publication_figures/grand_database_6040_units.csv
```

Purpose:

- Master table of 6,040 recorded neurons.

Verified columns include:

- `grand_total_id`
- `session_id`
- `unit_id`
- `area`
- `layer`
- `probe_id`
- `local_channel`
- `peak_channel_global`
- `is_stable`
- `is_quality_good`
- `stable_plus`
- `firing_rate`
- `waveform_duration`
- stimulus selectivity fields: `sig_s_plus`, `sig_s_minus`
- omission selectivity fields: `sig_o_plus`, `omission_best_slot`
- waveform class flags: `wf_narrow`, `wf_mid`, `wf_wide`, `wf_very_wide`

### Layer Masks

```text
D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json
```

Purpose:

- Spectrolaminar superficial/deep boundary configuration based on CSD crossover indices.

Structure:

- Main key: `by_key`.
- Key pattern:

```text
sub-<subject>_ses-<session>|<probe_letter>
```

Example:

```text
sub-C31o_ses-230823|C
```

### Data Index Outputs

```text
D:/workspace/omission/outputs/data_index/batch_13nwb/
```

Important files:

- `unit_address_book_all_sessions.csv`
- `lfp_session_address_book_all_sessions.csv`
- `event_timing_inventory_all_sessions.csv`

These should be preferred over ad hoc rediscovery when available.

## 3. Preprocessed LFP Trace Cache

Cache directory:

```text
D:/workspace/omission/outputs/publication_visual_review/tfr_correlations/cache/
```

Reported cache:

- 22 `.npy` files = 11 areas x 2 layers.
- Naming pattern:

```text
<area>_<layer>_aligned_power.npy
```

Example:

```text
PFC_deep_aligned_power.npy
```

Load directly with:

```python
np.load(path)
```

Use this cache to avoid expensive TFR advanced indexing when the task only needs trial-averaged aligned traces.

## 4. NWB Interval Event Semantics

The NWB interval table is event-level. Repeated `trial_num`, `task_block_number`, and `task_condition_number` values are expected because each trial has multiple event rows.

Table:

```python
nwb.intervals["omission_glo_passive"]
```

Important columns:

- `start_time`
- `stop_time`
- `codes`
- `event_code_type`
- `stimulus_number`
- `task_block_number`
- `task_condition_number`
- `task_sequence`
- `trial_num`
- `correct`
- `is_omission`

Correct-trial filter:

```python
correct == 1.0
```

Do not use behavioral `TrialError == 0` directly in NWB interval work unless explicitly crosswalking to BHV. In NWB, the interval field is `correct`.

## 5. Phase Selection

Use `stimulus_number` for phase selection. It is safer than raw event code when crossing BHV and NWB conventions.

| Phase | `stimulus_number` | NWB code | Description |
| --- | ---: | ---: | --- |
| fixation cue | 1 | 100 | fixation cue |
| p1 | 2 | 101 | first stimulus / global anchor |
| p2 | 3 | 102 | second stimulus / p2 omission slot |
| p3 | 4 | 103 | third stimulus / p3 omission slot |
| p4 | 5 | 104 | fourth stimulus / p4 omission slot |

Known caveat:

- BHV/MonkeyLogic notes may describe p1-p4 as odd codes `101, 103, 105, 107`.
- NWB intervals observed locally use sequential codes `101, 102, 103, 104`.
- `stimulus_number` resolves this mismatch and should be the default phase selector.

## 6. Canonical Condition Groups

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

Correct p1/p2/p3/p4 event counts should match for each group. A prior full-session audit found exact matching across all 13 NWB files:

| Group | P1 | P2 | P3 | P4 |
| --- | ---: | ---: | ---: | ---: |
| AAAB | 2633 | 2633 | 2633 | 2633 |
| AXAB | 386 | 386 | 386 | 386 |
| AAXB | 382 | 382 | 382 | 382 |
| AAAX | 356 | 356 | 356 | 356 |
| BBBA | 2594 | 2594 | 2594 | 2594 |
| BXBA | 412 | 412 | 412 | 412 |
| BBXA | 391 | 391 | 391 | 391 |
| BBBX | 353 | 353 | 353 | 353 |
| RRRR | 1488 | 1488 | 1488 | 1488 |
| RXRR | 645 | 645 | 645 | 645 |
| RRXR | 342 | 342 | 342 | 342 |
| RRRX | 986 | 986 | 986 | 986 |

Total correct complete-trial count per phase: 10,968.

## 7. Current Single-Unit and Waveform Handoff

### Omission Cortical Layer Stats

Reported state:

- 49 verified omission units across FEF and PFC.
- Session `230830` PFC has dual-crossover bounds caused by a white-matter gap.
- Unit 33 and Unit 77 in the PFC session `230830` should map to **Deep** under those dual-crossover bounds.

Required verification before extending:

- Re-read the layer-mask key for `230830`.
- Confirm whether unit IDs refer to local NWB unit IDs, grand database `unit_id`, or `grand_total_id`.
- Confirm whether the deep/superficial assignment should use `peak_channel_global`, `local_channel`, or `peak_channel_id` from NWB.

### MT/MST Waveform Split

Reported state:

- Initial units: 287.
- Waveforms detrended.
- Waveforms min-max normalized to `[-1.0, 1.0]`.
- Bottom third rejected as noisy/high-variance units: 97 units, about 34%.
- Clean units retained: 190.
- Median trough-to-peak threshold: `1033.32 us`.
- Narrow spiking: 86 units.
- Wide spiking: 104 units.

Required verification before extending:

- Confirm whether `waveform_duration` in the grand database is stored in seconds, milliseconds, or microseconds.
- Confirm whether `1033.32 us` is derived after quality rejection.
- Confirm whether the split is median-only or should use a biologically fixed threshold for comparisons.
- Confirm whether “narrow” and “wide” should be labeled putative interneuron/pyramidal or kept descriptive.

## 8. FEF Unit Reference

Files with FEF electrodes observed:

- `sub-C31o_ses-230823_rec.nwb`
- `sub-C31o_ses-230831_rec.nwb`

For `sub-C31o_ses-230823_rec.nwb`, prior inspection found:

- 368 total units.
- 156 units map to FEF via electrode `location` and unit `peak_channel_id`.
- Convolved spike data:

```python
nwb.processing["convolved_spike_train"]["convolved_spike_train_data"]
```

Shape:

```text
(20283769, 368)
```

Interpretation:

- timepoints x units
- 1000 Hz

Raw spike times:

```python
nwb.units.to_dataframe()["spike_times"]
```

Use raw spike times for raster/count analyses. Use convolved traces for continuous single-unit traces. Do not mix these without naming the representation.

## 9. General Extraction Pattern

```python
interval = nwb.intervals["omission_glo_passive"].to_dataframe()

correct = pd.to_numeric(interval["correct"], errors="coerce") == 1.0
phase = pd.to_numeric(interval["stimulus_number"], errors="coerce") == 2.0  # p1
condition = pd.to_numeric(interval["task_condition_number"], errors="coerce").isin([1, 2])

p1_onsets = interval.loc[correct & phase & condition, "start_time"].to_numpy()
```

For p2/p3/p4:

```python
phase_number = {"p1": 2.0, "p2": 3.0, "p3": 4.0, "p4": 5.0}[phase_name]
```

## 10. Agent Operating Rules

- Do not treat `nwb.intervals` rows as unique trials without phase-filtering.
- Use correct trials only by default.
- Prefer `stimulus_number` for p1-p4 selection.
- Preserve SPK/SUA, MUAe, and LFP separation.
- Preserve area/layer/session identity.
- Before waveform conclusions, verify waveform units and quality filters.
- Before layer conclusions, verify unit ID namespace and layer-mask key.

