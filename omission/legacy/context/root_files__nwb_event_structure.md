# NWB Event Structure & Mapping

**Reference**: Sub-C31o-230823 (representative session with FEF units)

## Overview

The NWB intervals table (`nwb.intervals['omission_glo_passive']`) contains **4,163 rows representing individual events**, not trials. Each trial contains ~11-12 events across its duration.

---

## Event Codes & Types

### Code Mapping (Event Code → Event Type → Stimulus Number)

| Code | event_code_type | stimulus_number | Meaning | Notes |
|------|-----------------|-----------------|---------|-------|
| **9** | trial start | nan | Trial begins | One per trial |
| **100** | fix cue appearance | 1.0 | Fixation cue | One per trial |
| **101** | task_event_2 | 2.0 | **P1 stimulus** | ~80% of trials |
| **102** | task_event_3 | 3.0 | **P2 stimulus** | Conditional (omission possible) |
| **103** | task_event_4 | 4.0 | **P3 stimulus** | Conditional (omission possible) |
| **104** | task_event_5 | 5.0 | **P4 stimulus** | Conditional (omission possible) |
| **50** | end code | nan | Trial ends | One per trial |
| **40** | reward | nan | Reward delivered | Multiple per session |

### Key Insight: Use `stimulus_number` Not `codes`

**BHV (MonkeyLogic) uses odd codes**: P1=101, P2=103, P3=105, P4=107  
**NWB uses sequential codes**: P1=101, P2=102, P3=103, P4=104

**Solution**: Use the **`stimulus_number` field** which is universal and unambiguous:
- stimulus_number = 1.0 → fixation cue
- stimulus_number = 2.0 → P1 stimulus
- stimulus_number = 3.0 → P2 stimulus
- stimulus_number = 4.0 → P3 stimulus
- stimulus_number = 5.0 → P4 stimulus

---

## Interval Table Columns (40 total)

### Timing & Event Identification
- **start_time**: Event onset (seconds from session start)
- **stop_time**: Event offset
- **codes**: Event code (9, 40, 50, 100, 101, 102, 103, 104)
- **event_code_type**: Human-readable event label
- **stimulus_number**: Phase identifier (1-5 for stimuli, nan for non-stimulus events)

### Trial Metadata
- **trial_num**: Trial number within session (1–351 unique values for session 230823)
- **task_block_number**: Block number (1–5)
- **task_condition_number**: Condition code (1–50, maps to 12 canonical conditions)
- **correct**: Trial outcome (1.0 = correct, 0.0 = error)
- **is_omission**: Flag for omission trials (nan or 1.0)

### Stimulus Properties (non-nan only for stimulus events)
- **contrast, contrast_max, contrast_min**: Gabor contrast
- **orientation**: Gabor angle (45° or 135°)
- **spatial_frequency**: Gabor spatial frequency
- **phase**: Gabor phase
- **size, shape, x_position, y_position, x_length, y_length**: Visual stimulus geometry
- **b_col, g_col, r_col**: RGB color values

### Structural/Fixed Fields
- **distance_to_screen**: 1060 mm (constant)
- **screen_width, screen_height**: 1000 × 620 pixels
- **screen_res_width, screen_res_height**: 1920 × 1080 pixels
- **fixation_window**: Fixation tolerance (varies by trial type)

---

## Event Count Verification (Session 230823)

**Total events**: 4,163  
**Unique trials**: 351 (trial_num values 1–351)

### Events per type:
- Trial start (code 9): 351
- Fixation cue (code 100): 351
- P1 stimulus (code 101, stimulus_number=2): 298
- P2 stimulus (code 102, stimulus_number=3): 272
- P3 stimulus (code 103, stimulus_number=4): 255
- P4 stimulus (code 104, stimulus_number=5): 235
- End code (code 50): 351
- Reward (code 40): 2,050

### Correct vs Error (All Events)
- Correct trials (correct=1.0): 3,590 events
- Error trials (correct=0.0): 573 events

### Correct P1 Events by Condition Group (12 groups)

| Group | Correct P1 Count |
|-------|------------------|
| AAAB | 222 |
| AXAB | 42 |
| AAXB | 42 |
| AAAX | 30 |
| BBBA | 215 |
| BXBA | 31 |
| BBXA | 42 |
| BBBX | 30 |
| RRRR | 118 |
| RXRR | 55 |
| RRXR | 27 |
| RRRX | 73 |
| **TOTAL** | **937** |

**Critical Invariant**: Correct P1 = Correct P2 = Correct P3 = Correct P4 (all equal counts per group)

---

## Temporal Alignment

### P1 as Universal Anchor
- **p1_onset_time** = trial's `start_time` (when stimulus_number=2)
- All phases align relative to this anchor

### Phase Timing (relative to p1_onset)
- **p1_relative baseline**: [−250, −50]ms
- **p2 stimulus**: [0, 250]ms
- **p3 stimulus**: [250, 500]ms
- **p4 stimulus**: [500, 750]ms
- **d1–d4 dynamics**: [750, 1750]ms

### Full Epoch Window
- **Total**: 2000 samples @ 1000 Hz (2 seconds)
- **Pre-stimulus**: 250 samples (−250ms)
- **Post-stimulus**: 1750 samples (+1750ms)

---

## Condition Taxonomy (12 Canonical Groups)

| Canonical ID | Label | Raw Condition Codes | Description |
|:------------:|-------|:------------------:|-------------|
| 1 | AAAB | 1, 2 | A-family control |
| 2 | AXAB | 3 | A-family omission (p2) |
| 3 | AAXB | 4 | A-family omission (p3) |
| 4 | AAAX | 5 | A-family omission (p4) |
| 5 | BBBA | 6, 7 | B-family control |
| 6 | BXBA | 8 | B-family omission (p2) |
| 7 | BBXA | 9 | B-family omission (p3) |
| 8 | BBBX | 10 | B-family omission (p4) |
| 9 | RRRR | 11–26 | Random control |
| 10 | RXRR | 27–34 | Random omission (p2) |
| 11 | RRXR | 35, 37, 39, 41 | Random omission (p3) |
| 12 | RRRX | 36, 38, 40, 42–50 | Random omission (p4) |

---

## Access Pattern (jNWB Binary Event Filtering)

```python
from pynwb import NWBHDF5IO

with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
    nwb = io.read()
    
    # Get interval table
    interval_df = nwb.intervals['omission_glo_passive'].to_dataframe()
    
    # Create binary event filters
    correct_events = interval_df['correct'] == 1.0
    p1_events = interval_df['stimulus_number'] == 2.0
    p2_events = interval_df['stimulus_number'] == 3.0
    
    # Combine filters (e.g., correct P1 events)
    p1_correct = correct_events & p1_events
    
    # Get onset times
    p1_onsets = interval_df.loc[p1_correct, 'start_time'].values
```

---

## Files & References

- **Session-by-session trial counts**: `context/specs/overview__nwb-data-oglo-session-by-session-table.md`
- **Task specification**: `context/specs/task-specification.md`
- **Constants mapping**: `src/analysis/contracts/constants.py`
- **Helper functions**: `scripts/jnwb_helper_functions.py`
