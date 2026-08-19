# NWB Analysis Documentation Index

**Comprehensive guide to event extraction, neural data alignment, and spike/LFP analysis for the Omission dataset**

---

## Quick Start

### I just want to extract LFP/spikes aligned to P1 events

→ Read: **nwb_data_extraction_guide.md** (Step 1–5)

```python
# 30-second workflow
onsets = get_onset_times(interval_df, correct_b & p1_b & aaab_b)
lfp = extract_lfp_aligned(nwb, onsets)
spk = extract_convolved_spikes_aligned(nwb, onsets, fef_unit_ids)
# Done. Save to disk.
```

### I want to understand the event structure first

→ Read: **nwb_event_structure.md** (Overview, Event Codes)

Key insight: Use `stimulus_number` (not raw codes) to identify phases.

### I want to map units to brain areas

→ Read: **nwb_neural_data_structure.md** (Electrodes & Units)

```python
units_df = nwb.units.to_dataframe()
elec_df = nwb.electrodes.to_dataframe()
peak_ch = int(float(units_df.iloc[unit_id]['peak_channel_id']))
area = elec_df.iloc[peak_ch]['location']  # 'FEF', 'V1', etc.
```

---

## Complete Documentation Map

### 1. **nwb_event_structure.md** (40 KB)
   **What**: Event codes, timing, condition mapping  
   **When**: Understanding how trials are organized in NWB  
   **Key sections**:
   - Event Code Mapping (code → event_type → stimulus_number)
   - Event Count Verification (4,163 events for session 230823)
   - Temporal Alignment (p1_relative as anchor)
   - Condition Taxonomy (12 groups from 50 codes)
   - Access pattern (jNWB binary filtering)

### 2. **nwb_neural_data_structure.md** (35 KB)
   **What**: Units, electrodes, spike data  
   **When**: Working with neural signals  
   **Key sections**:
   - Units Table (31 columns, spike metrics)
   - Electrodes Table (location, probe mapping)
   - Convolved Spike Train (1000 Hz dense array)
   - Brain Area Mapping (FEF=156 units, etc.)
   - Data sources (spike_times vs convolved_spikes)

### 3. **nwb_data_extraction_guide.md** (50 KB)
   **What**: Step-by-step extraction code  
   **When**: Implementing actual data extraction  
   **Key sections**:
   - 5-step workflow (filters → onsets → windows)
   - Binary event filter creation
   - LFP extraction (with edge padding)
   - Convolved spike extraction (multi-unit)
   - Multi-condition template
   - Validation checklist

### 4. **NEURAL_DATA_ANALYSIS_SUMMARY.md** (30 KB)
   **What**: Overview of discoveries  
   **When**: Designing overall architecture  
   **Key sections**:
   - Key numbers (10,968 trials, 156 FEF units)
   - Architecture (jNWB binary filtering)
   - Performance benchmarks
   - Next steps (generalized extraction)

---

## Data Summary

### Sessions Available (13 total)

| Subject | Sessions | Correct P1 | Has FEF |
|---------|----------|-----------|---------|
| C31o | 230630, 230816, 230818, 230823, 230825, 230830, 230831, 230901 | 8,690 | ✓ 230823, 230831 |
| V198o | 230629, 230714, 230719, 230720, 230721 | 2,278 | ✗ |

### Reference Session: 230823

```
Location: D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb (152 GB)
Duration: 20,283 seconds (~5.6 hours)
Correct P1 events: 937 (across all conditions)
Total units: 368
  - FEF units: 156
LFP channels: 128
Recording setup: 3 probes (probeA, B, C)
```

---

## Core Concepts

### 1. **stimulus_number** (Universal Phase Identifier)
```
stimulus_number = 1.0 → Fixation cue
stimulus_number = 2.0 → P1 stimulus  ← Use this for alignment
stimulus_number = 3.0 → P2 stimulus
stimulus_number = 4.0 → P3 stimulus
stimulus_number = 5.0 → P4 stimulus
stimulus_number = nan → Non-stimulus events
```

**Why it matters**: Resolves BHV (codes 101,103,105,107) vs NWB (codes 101,102,103,104) ambiguity

### 2. **p1_relative** (Universal Time Zero)
```
p1_onset = trial['start_time']
p1_relative baseline: [−250, −50] ms
p2: [0, 250] ms
p3: [250, 500] ms
p4: [500, 750] ms
d1–d4: [750, 1750] ms
```

**Why it matters**: Single anchor enables cross-session, cross-condition comparison

### 3. **Correct Trials Only**
```
Filter: interval_df['correct'] == 1.0
Result: 10,968 correct trials (all 13 sessions)
Invariant: P1 count = P2 count = P3 count = P4 count (verified)
```

**Why it matters**: Ensures comparable trial sets across phases

### 4. **Binary Event Filtering** (jNWB Pattern)
```python
correct_b = interval_df['correct'] == 1.0       # Boolean array
p1_b = interval_df['stimulus_number'] == 2.0
aaab_b = interval_df['task_condition_number'].isin([1, 2])

# Combine with boolean logic
matched = correct_b & p1_b & aaab_b              # All True where all match

# Get results
onsets = interval_df.loc[matched, 'start_time'].values
```

**Why it matters**: Scales easily, parallelizable, no loops needed

---

## File Locations

### Documentation (Read these)
```
context/
├── nwb_event_structure.md          ← Events, codes, timing
├── nwb_neural_data_structure.md    ← Units, electrodes, spikes
├── nwb_data_extraction_guide.md    ← Implementation walkthrough
├── NEURAL_DATA_ANALYSIS_SUMMARY.md ← Architecture & key numbers
└── README_NWB_ANALYSIS.md          ← This file
```

### Helper Code (Use these)
```
scripts/
├── jnwb_helper_functions.py        ← get_binary_events_for_code(), etc.
├── phase2a_complete_extraction.py  ← LFP epoch extraction (already run)
└── p1_p2_p3_p4_analysis.py         ← Phase consistency verification
```

### Raw Data (Read from these)
```
D:/analysis/nwb/
├── sub-C31o_ses-230630_rec.nwb     (21 GB)
├── sub-C31o_ses-230823_rec.nwb     (172 GB) ← FEF reference
├── sub-C31o_ses-230831_rec.nwb     (190 GB) ← FEF alternate
└── ... 10 more sessions

D:/workspace/data/other/checkpoints/oglo4/
├── ses230629_V1_code1_epochs.npy   (existing, unvalidated)
└── ... 980 more files
```

### Outputs (Already Created)
```
outputs/
├── epochs_full_sequence/           ← Phase 2A LFP epochs
│   ├── ses230630_AAAB_epochs.npy   (605 trials, 2000 samples, 128 ch)
│   ├── ... 12 conditions per session
│   └── validation_report.json
├── trial_manifests/                ← Trial-level metadata
│   ├── trial_manifest_correct_only.csv (119,710 rows)
│   └── session_summary.csv
└── neural_data_aligned/            ← To be created
```

---

## How to Use This Documentation

### Scenario 1: "I need P1 LFP for AAAB condition"
1. Skim: **nwb_event_structure.md** → Condition Taxonomy
2. Code: **nwb_data_extraction_guide.md** → Step 2 (Binary filters) + Step 4a (LFP extraction)
3. Use: `scripts/jnwb_helper_functions.py` → `extract_lfp_aligned()`

### Scenario 2: "I want to analyze FEF units across all P1 events"
1. Reference: **nwb_neural_data_structure.md** → Brain Area Mapping (FEF = 156 units)
2. Code: **nwb_data_extraction_guide.md** → Step 2 (correct_b & p1_b) + Step 4b (convolved spikes)
3. Use: `extract_convolved_spikes_aligned(nwb, onsets, fef_unit_ids)`

### Scenario 3: "I'm building a new analysis pipeline"
1. Architecture: **NEURAL_DATA_ANALYSIS_SUMMARY.md** → Implementation Steps
2. Implementation: **nwb_data_extraction_guide.md** → Multi-Phase, Multi-Condition Template
3. Helper functions: `scripts/jnwb_helper_functions.py`

### Scenario 4: "Something doesn't match my expectations"
1. Verify: **nwb_event_structure.md** → Event Count Verification
2. Check: **nwb_data_extraction_guide.md** → Validation Checklist
3. Debug: Compare against reference session 230823 numbers

---

## Key Numbers (Memorize These)

### Per-Session Averages
- **Correct P1 events**: ~837 (range: 220–967)
- **FEF units** (when present): 156
- **LFP channels**: 128
- **Recording duration**: ~5.7 hours
- **Sampling rate**: 1000 Hz (all data)

### Across All Sessions
- **Total correct trials**: 10,968
- **Total sessions**: 13
- **Sessions with FEF**: 2 (230823, 230831)
- **Condition groups**: 12 (AAAB, AXAB, …, RRRX)
- **Unique areas recorded**: 11 (V1, V2, V3, V4, MT, MST, PFC, TEO, FST, FEF, DP)

### Phase Consistency (Critical Invariant)
- **Correct P1 = P2 = P3 = P4** ✓ Verified across all sessions
- Session 230823: 937 correct events per phase
- Session 230630: 220 correct events per phase

---

## Common Tasks

### Extract LFP for one condition
```python
# From nwb_data_extraction_guide.md, Step 3–4
interval_df = nwb.intervals['omission_glo_passive'].to_dataframe()
correct_b = interval_df['correct'] == 1.0
p1_b = interval_df['stimulus_number'] == 2.0
aaab_b = interval_df['task_condition_number'].isin([1, 2])

onsets = interval_df.loc[correct_b & p1_b & aaab_b, 'start_time'].values
lfp = extract_lfp_aligned(nwb, onsets)  # (222, 2000, 128)
```

### Extract FEF spikes for all P1 events
```python
# Identify FEF units
fef_units = [uid for uid, area in unit_areas if area == 'FEF']

# Get all correct P1 onsets
onsets = interval_df.loc[correct_b & p1_b, 'start_time'].values

# Extract convolved spikes
spk = extract_convolved_spikes_aligned(nwb, onsets, fef_units)  # (937, 2000, 156)
```

### Validate extracted data
```python
# From nwb_data_extraction_guide.md, Validation Checklist
assert lfp.shape == (n_events, 2000, 128), "Shape mismatch"
assert np.isnan(lfp).sum() / lfp.size < 0.05, "Too many NaNs"
assert len(p1_onsets) == len(p2_onsets) == len(p3_onsets) == len(p4_onsets), "Phase count mismatch"
```

---

## Troubleshooting

### "stimulus_number shows as string, not float"
→ Convert: `float(row['stimulus_number']) == 2.0`

### "Why are P1 and P2 counts different?"
→ You may be mixing filter logic. Check: did you apply `correct_b` to both?

### "peak_channel_id is float, not int"
→ Convert: `int(float(row['peak_channel_id']))`

### "LFP has NaNs at edges"
→ Expected behavior. Extraction pads with NaN at session start/end. Document in metadata.

### "FEF unit count doesn't match documentation"
→ Verify electrode table in correct session. FEF mapping is per-session.

---

## Next Steps

1. **Implement generalized extraction** (use template from guide)
2. **Extract all phases/conditions** for analysis
3. **Validate cross-session consistency**
4. **Feed to downstream analysis** (figures, SpSAM, Granger)

---

**Status**: Documentation complete, implementation-ready  
**Last Updated**: 2026-06-17  
**Reference Implementation**: `scripts/jnwb_helper_functions.py`
