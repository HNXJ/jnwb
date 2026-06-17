# Phase 2: Epoch Recovery Planning (Concrete Analysis Subproject)

**Status**: PLAN (ready to execute once Phase 1 validation gates pass)  
**Grounded in**: Phase 1 execution surface (now coherent), omission timing doctrine, manifest layer  
**Target**: Define epoch recovery as reproducible analysis with explicit inputs, outputs, schema, and figure hooks  
**Timeline**: 6 days implementation (Phase 1 prerequisites complete)

---

## 1. ANALYSIS CONTRACT

### 1.1 Inputs

**Primary Input**: NWB Session Files
```
Path: $OMISSION_DATA_ROOT/nwb/ses-{YYMMDD}.nwb
Format: NWB 2.0 (canonical Neurodata Without Borders)
Required Tables:
  - AnalogSeries (LFP, 1kHz sampling)
  - Units (spike times, unit metadata)
  - Trial metadata (condition codes, trial timings)
```

**Secondary Input**: A4 Trial-Count Validation Matrix
```
Path: reports/analysis_A4_trial_count_validation/trial_count_matrix.csv
Purpose: Source of truth for trial counts per session/condition
Schema:
  - session_id: str (YYMMDD)
  - condition: str (AAAB, AXAB, AAXB, AAAX, BBBA, BXBA, BBXA, BBBX, RRRR, RXRR, RRXR, RRRX)
  - trial_count: int (verified from A4)
  - truth_status: str (truth_safe_unverified)
```

**Tertiary Input**: Task Specification & Timing Reference
```
Path: context/specs/task-specification.md
Purpose: Canonical timing base and condition definitions
Required:
  - p1_relative baseline window: [-250, -50]ms (pre-stimulus)
  - p2 phase: [0, 250]ms (first stimulus or omission)
  - p3 phase: [250, 500]ms (second stimulus or omission)
  - p4 phase: [500, 750]ms (third stimulus or omission)
  - d1-d4 dynamics: [750, 1250]ms (post-stimulus ISI)
  - Omission onset times (p2, p3, p4 variants)
```

---

### 1.2 Outputs (Schema)

**Primary Output**: Aligned Epoch Arrays

```
Directory: outputs/epochs_full_sequence/

For each session:
  ses{YYMMDD}_epochs_lfp.npy
    Shape: (n_conditions, max_trials_per_condition, n_channels, n_timepoints)
    Actual shape: (12, 84, 128, 6000)  # 12 conditions, max 84 trials (RRRR), 128 channels, 6s @ 1kHz
    Dtype: float32
    Alignment: p1_relative time zero = NWB trial onset
    Baseline: dB relative to p1_relative [-250, -50]ms (deferred to Figure 4)

  ses{YYMMDD}_epochs_spk.sparse
    Type: Sparse COO array (scipy.sparse or equivalent)
    Shape: (n_conditions, max_trials, n_units, n_timepoints)
    Content: Spike binary or spike count per trial/unit/timepoint
    Alignment: Same as LFP (p1_relative zero)

  ses{YYMMDD}_epoch_metadata.json
    Schema:
    {
      "session_id": "230629",
      "n_conditions": 12,
      "conditions": ["AAAB", "AXAB", ...],
      "trial_counts": {"AAAB": 48, "AXAB": 6, ...},
      "n_channels": 128,
      "n_units": 354,
      "sampling_rate_hz": 1000,
      "epoch_window_ms": [-250, 1250],
      "epoch_samples": 6000,
      "p1_relative_baseline_ms": [-250, -50],
      "alignment_reference": "p1_relative_onset",
      "condition_alignments": {
        "AAAB": {"align_to": "p1_onset", "offset_ms": 0},
        "AXAB": {"align_to": "omission_p2_time", "offset_ms": 0},
        "AAXB": {"align_to": "omission_p3_time", "offset_ms": 0},
        ...
      },
      "truth_status": "truth_safe_unverified",
      "validation_receipt": "see validation_report.json"
    }
```

**Secondary Output**: Validation Receipt

```
File: outputs/epochs_full_sequence/validation_report.json

Schema:
{
  "timestamp": "2026-06-17T14:30:00Z",
  "session_id": "230629",
  "validation_status": "PASS" | "FAIL",
  "checks": {
    "shape_consistency": {
      "status": "PASS",
      "message": "All conditions produce (trial_count, 128, 6000)",
      "details": {
        "condition_shapes": {"AAAB": [48, 128, 6000], "AXAB": [6, 128, 6000], ...}
      }
    },
    "trial_count_match_a4": {
      "status": "PASS",
      "message": "All conditions match A4 trial-count-matrix.csv",
      "mismatches": []
    },
    "nan_density": {
      "status": "PASS",
      "message": "No NaN blocks > 50ms in any channel",
      "max_nan_block_ms": 0,
      "channels_with_nans": []
    },
    "alignment_sanity": {
      "status": "PASS",
      "message": "Baseline (p1) power < stimulus (p2/p3/p4) power",
      "p1_mean_power_db": -2.3,
      "p2_mean_power_db": 0.7,
      "p3_mean_power_db": 1.2,
      "p4_mean_power_db": 0.9
    },
    "spike_realism": {
      "status": "PASS",
      "message": "Spike counts realistic (0-1000 per trial)",
      "spike_count_range": [0, 987],
      "units_with_zero_spikes": 12
    },
    "cross_session_dims": {
      "status": "PASS",
      "message": "Epoch dims match across all 13 sessions",
      "sessions_checked": 13,
      "dim_agreement": "100%"
    }
  },
  "truth_status": "truth_safe_unverified",
  "analyst": "claude"
}
```

**Tertiary Output**: Cross-Session Consistency Report

```
File: outputs/epochs_full_sequence/cross_session_summary.md

- All 13 sessions processed without fatal errors
- All 156 session-condition pairs produce aligned arrays
- Cross-session dimension agreement: 100%
- No missing trials (A4 counts match epoch counts)
- Baseline power < stimulus power in 100% of conditions (sanity check pass)
- Figure 4–10 ready for generation
```

---

## 2. TIMING SPECIFICATION (CANONICAL REFERENCE)

### 2.1 P1-Relative Timeline (Universal Zero)

All epochs align to **p1_relative onset = t=0**. This is the trial start timestamp in NWB, typically 1000ms before the first stimulus in a baseline-heavy protocol.

```
p1_relative: [-250, -50]ms      Baseline window (pre-stimulus)
p2:          [0, 250]ms         First stimulus (or omission)
p3:          [250, 500]ms       Second stimulus (or omission)
p4:          [500, 750]ms       Third stimulus (or omission)
d1:          [750, 1000]ms      Post-stimulus dynamics (ISI phase 1)
d2:          [1000, 1250]ms     Post-stimulus dynamics (ISI phase 2)
d3:          [1250, 1500]ms     Post-stimulus dynamics (ISI phase 3, if recorded)
d4:          [1500, 1750]ms     Post-stimulus dynamics (ISI phase 4, if recorded)

Full window: [-250, 1250]ms = 6000 samples @ 1kHz
```

### 2.2 Condition-Specific Alignment Rules

**Control Conditions** (AAAB, BBBA, RRRR):
- Align to p1_onset (t=0 in p1_relative frame)
- All three p2/p3/p4 phases contain stimuli

**Omission Conditions**:
- **AXAB** (omission at p2): Align to omission_time_p2
  - p1_relative: baseline (all three trials have it)
  - p2: MISSING (omission window, not stimulus)
  - p3/p4: stimuli present (recovery phase)

- **AAXB** (omission at p3): Align to omission_time_p3
  - p1/p2: baseline + first stimulus
  - p3: MISSING (omission window)
  - p4/d1: recovery

- **AAAX** (omission at p4): Align to omission_time_p4
  - p1/p2/p3: baseline + stimuli
  - p4: MISSING (omission window)
  - d1/d2: recovery

**Random Control** (RRRR):
- Align to first random event onset (often offset from canonical p2)
- Treat as separate alignment baseline (documented in metadata)

### 2.3 Omission Window Specification

```
Omission onset: defined per session in NWB trial metadata (event code or trial type)
Omission_p2_time: Time when p2 stimulus WOULD occur (but is omitted)
Omission_p3_time: Time when p3 stimulus WOULD occur (but is omitted)
Omission_p4_time: Time when p4 stimulus WOULD occur (but is omitted)

CRITICAL: Omission time is NOT arbitrary; it is the expected stimulus onset in the baseline protocol.
Do NOT invent omission times; extract from NWB trial events or condition codes.
```

---

## 3. MANIFEST & ROUTING HOOKS

### 3.1 Session/Condition Discovery

```python
# Pseudocode: How epochs route to figures

from reports.analysis_A4_trial_count_validation import trial_count_matrix

for session_id in trial_count_matrix['session_id'].unique():
    for condition in trial_count_matrix['condition'].unique():
        n_trials = trial_count_matrix.loc[
            (session_id, condition), 'trial_count'
        ]
        
        # Load NWB, extract condition, align to omission_time or p1_onset
        epochs_lfp, epochs_spk = recover_epochs(
            session_id,
            condition,
            n_trials=n_trials,
            align_to=alignment_rule(condition)
        )
        
        # Save to outputs/epochs_full_sequence/
        save_epochs(session_id, condition, epochs_lfp, epochs_spk)
```

### 3.2 Figure Hooks (Dependency Chain)

```
outputs/epochs_full_sequence/
    ├─→ Figure 4: Band Power
    │   Input: ses{YYMMDD}_epochs_lfp.npy
    │   Compute: Power in [delta, theta, alpha, gamma]
    │   Output: f4_band_power_matrix.npy
    │
    ├─→ Figure 5: Granger Causality
    │   Input: f4_band_power_matrix.npy
    │   Compute: Spectral Granger (Wilson method)
    │   Output: f5_granger_causality.npy
    │
    ├─→ Figure 6: Spike-Field Coherence
    │   Input: ses{YYMMDD}_epochs_spk.sparse, ses{YYMMDD}_epochs_lfp.npy
    │   Compute: PLV by layer
    │   Output: f6_coherence_by_layer.npy
    │
    ├─→ Figure 7: PAC (Phase-Amplitude Coupling)
    │   Input: ses{YYMMDD}_epochs_lfp.npy
    │   Compute: Theta-Gamma coupling (MVL)
    │   Output: f7_pac_strength.npy
    │
    ├─→ Figure 8: Ghost Signals
    │   Input: ses{YYMMDD}_epochs_spk.sparse
    │   Compute: Decoding (stimulus vs. omission from spikes)
    │   Output: f8_ghost_decoding.npy
    │
    ├─→ Figure 9: State Manifold
    │   Input: ses{YYMMDD}_epochs_spk.sparse
    │   Compute: PCA/UMAP trajectory
    │   Output: f9_manifold_trajectory.npy
    │
    └─→ Figure 10: SpSAM (Integrated)
        Input: all above + Granger connectivity
        Compute: Spike-Spectral Attention Mechanism
        Output: f10_spsam_global.npy
```

---

## 4. ACCEPTANCE TESTS & VALIDATION

### 4.1 Test Suite: `tests/test_epoch_recovery.py`

```python
def test_epoch_shape_consistency():
    """All sessions/conditions produce correct shape."""
    assert epochs_lfp.shape == (max_trials, n_channels, 6000)

def test_trial_count_match_a4():
    """Trial counts match A4 matrix."""
    for session, condition in pairs:
        assert len(epochs) == trial_count_matrix.loc[(session, condition)]

def test_no_nan_blocks():
    """No NaN blocks > 50ms in LFP."""
    assert not (nan_mask.sum(axis=(1,2)) > 50).any()

def test_baseline_vs_stimulus_power():
    """p1 power < p2 power (sanity check)."""
    p1_power = epochs_lfp[:, :, :250].mean()
    p2_power = epochs_lfp[:, :, 250:500].mean()
    assert p2_power > p1_power * 1.1

def test_omission_signature():
    """Omission conditions show distinct p2/p3/p4 patterns."""
    assert omission_conditions_have_significant_effect()

def test_cross_session_consistency():
    """All 13 sessions have identical epoch dimensions."""
    dims = [epochs_lfp.shape for all sessions]
    assert len(set(dims)) == 1  # All same
```

### 4.2 Validation Receipts

After epoch recovery completes, the repo will contain:

```
outputs/epochs_full_sequence/
├── ses230629_epochs_lfp.npy
├── ses230629_epoch_metadata.json
├── ses230629_epochs_spk.sparse
├── ses230630_epochs_lfp.npy
├── ...
├── ses230901_epochs_lfp.npy
├── validation_report.json          ← CRITICAL: Pass/fail receipt
├── cross_session_summary.md         ← Summary table
└── PHASE_2_COMPLETION_RECEIPT.txt   ← Final gate document
```

**Final Gate (before Figure 4 generation)**:
- [ ] All 13 sessions have `epochs_lfp.npy` files
- [ ] All 156 session-condition pairs have metadata entries
- [ ] `validation_report.json` has status=PASS for all checks
- [ ] Cross-session dimensions 100% consistent
- [ ] No NaN blocks > 50ms
- [ ] Baseline power < stimulus power (sanity)
- [ ] pytest test_epoch_recovery.py passes 6/6 tests

---

## 5. IMPLEMENTATION ROADMAP

### 5.1 Phase 2A: Single-Session Prototype (3 days)

**Goal**: Recover epochs for ses-230629, validate alignment, document timing assumptions.

```
Day 1:
  - Load ses-230629.nwb
  - Extract trial metadata (condition codes, trial onsets)
  - Identify omission timing (p2, p3, p4 variants)
  - Cross-reference with A4 trial counts

Day 2:
  - Implement epoch extraction for all 12 conditions
  - Align to p1_relative or omission_time per condition
  - Shape validation: (trial_count, 128, 6000)
  - Generate epoch_metadata.json

Day 3:
  - Test alignment sanity (baseline < stimulus power)
  - Create validation_report.json for single session
  - Document any timing surprises in ops/ documentation
```

### 5.2 Phase 2B: Multi-Session Scaling (2 days)

**Goal**: Loop over all 13 sessions, ensure cross-session consistency.

```
Day 4:
  - Loop over sessions 230630–230901
  - Handle missing probes gracefully (use A4 manifest)
  - Verify trial count agreement with A4 matrix
  - Aggregate validation receipts

Day 5:
  - Cross-session dimension check (all (12, n, 128, 6000))
  - Spot-check 2–3 sessions for NaN/anomalies
  - Generate cross_session_summary.md
```

### 5.3 Phase 2C: Validation & Documentation (1 day)

**Goal**: Finalize validation gates, prepare for Figure 4 generation.

```
Day 6:
  - Run full test suite (tests/test_epoch_recovery.py)
  - Verify all 6 acceptance tests pass
  - Create PHASE_2_COMPLETION_RECEIPT.txt
  - Document any deviations from plan (e.g., timing anomalies, probe issues)
  - Final decision: Figure 4 generation can proceed
```

---

## 6. RISK MITIGATION

### Known Risks

1. **Missing Probes**: Some sessions have missing probes (e.g., ses-230901 missing Probe 1)
   - Mitigation: Use A4 manifest to know expected structure; create (active_probes, trials, channels, time)
   - Not a blocker; document and adjust Figure 4 to handle variable probe counts

2. **Timing Drift**: Omission onset time might drift ±5ms across trials
   - Mitigation: Interpolate if needed; log drift statistics in metadata
   - Not a blocker; apply within-trial jitter correction if needed

3. **NaN Gaps in LFP**: Some sessions may have brief recording gaps
   - Mitigation: Fail loudly if gap > 50ms; document which trials affected
   - Not a blocker; Figure 4 can exclude affected trials

4. **Spike Sorting Quality**: Units with poor refractory violations may skew results
   - Mitigation: Document unit quality metrics in metadata; Figure 8+ can filter
   - Not a blocker; deferred to figure-level QC

### Unresolved Risks (Do Not Block Epoch Recovery)

- Figure 4 normalization baseline (dB vs. z-score) — deferred to Figure 4 script
- SPK/SUA distinction — deferred to unit classification pipeline (not yet ACTIVE)
- MUAe vs. LFP mixture — deferred to signal class pipeline (if MUAe detected)

---

## 7. DOCTRINAL CONSTRAINTS (Preserved)

✅ **Omission is a missing expected stimulus**, not a generic condition change
✅ **p1_relative is universal time zero** across all sessions
✅ **Phase ordering (p1/p2/p3/p4/d1-d4) is canonical** and immutable
✅ **SPK/SUA, MUAe, LFP separation is strict** (no collapsing into generic "neural activity")
✅ **Area aliases (V3d/V3a, DP→V4) are preserved** from A4 manifest
✅ **Session-aware inference**: no cross-session pooling before per-session validation

---

## 8. SUCCESS CRITERIA (Gate Before Figure 4)

| Criterion | Status | Evidence |
|-----------|--------|----------|
| All 13 sessions have epochs | [ ] | 13 sessions in outputs/ |
| All 156 session-condition pairs aligned | [ ] | metadata counts match |
| Cross-session dims 100% consistent | [ ] | cross_session_summary.md |
| No NaN blocks > 50ms | [ ] | validation_report.json |
| Baseline < stimulus power | [ ] | alignment_sanity check PASS |
| 6/6 acceptance tests PASS | [ ] | pytest output |
| PHASE_2_COMPLETION_RECEIPT signed | [ ] | receipt file exists |

---

## 9. NEXT STEP

Once Phase 2 is complete:
1. Figure 4 (Band Power) generation can begin
2. Figures 5–9 can run in parallel (all depend on epochs + F4)
3. SpSAM development begins (in parallel, depends on completed F5–F8)
4. Figure 10 (Integration) runs last (depends on SpSAM + F5/F6)

**Critical Path**: Epochs (6 days) → F4 (2 days) → [F5–F9 parallel, 3 days] → SpSAM (10 days) → F10 (5 days) = ~30 days total to Figure 10

---

**Document Status**: Phase 2 planning complete. Ready for implementation gate.
