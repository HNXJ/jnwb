---
name: jnwb-spiking
description: |
  Single-unit spike analysis using jnwb. Covers raster plots, PSTHs,
  autocorrelograms, omission response classification, phase-locking index,
  and unit quality scoring. Uses UnitAnalyzer object and raster_plot /
  psth_analysis / autocorrelogram canonical functions. Also wraps the
  jnwb.spiking module (compute_response_metrics, classify_omission_response).
---

# jnwb-spiking: Single-Unit Spike Analysis

Module root: `jnwb/` (repo root: `oa.paths.REPO_ROOT`)  
Primary files: `analyzers.py` (UnitAnalyzer), `functions.py` (raster_plot, psth_analysis, autocorrelogram), `spiking.py`

## Import

```python
import jnwb as oa
from jnwb import UnitAnalyzer
from jnwb import (
    raster_plot, psth_analysis, autocorrelogram,
    find_units, unit_quality_scores,
    compute_response_metrics, classify_omission_response, phase_locking_index,
)
```

## UnitAnalyzer Object

```python
# Raster aligned to trial onset
raster = UnitAnalyzer.raster(spike_times, trial_onsets, window_ms=(-500, 2000))
# Returns: {'raster': [[...], [...], ...], 'n_trials': 40, 'n_spikes': 980}

# PSTH with bootstrap CI
psth = UnitAnalyzer.psth(spike_times, trial_onsets, bin_size_ms=10)
# Returns: {'psth': array, 'sem': array, 'bin_centers': array, 'bootstrap_ci': {'lo': ..., 'hi': ...}}

# Autocorrelogram + refractory period test (supports device='cuda')
acg = UnitAnalyzer.autocorrelogram(spike_times, max_lag_ms=100, device='cuda')
# Returns: {'acg': array, 'refractory_period_violation': p_value, 'is_single_unit': bool}

# Quality metrics & classification tiers
quality = UnitAnalyzer.quality_metrics(spike_times, waveform_duration_us=400, firing_rate=15)

## Unit Quality Classification Tiers & Area Ordering (Canonical Corpus Rules)

- **Kilosort Good Units**: `quality == 1.0` (or `1`, `b'1.0'`). 4,450 units (51.8% of 21-session corpus).
- **Stable Units**: `presence_ratio >= 0.98` AND `firing_rate > 0.5 Hz` AND `snr > 0.5` (1,509 units).
- **MUA Units**: `firing_rate > 5.0 Hz` AND `isi_violations > 0.005` (0.5%) AND `presence_ratio > 0.98` (or `quality == 0.0`).
- **10 Ordered Separate Areas**: `V1`, `V2`, `V3a-d-v`, `V4` (mapped from `DP`), `MT`, `MST`, `TEO`, `FST`, `FEF`, `PFC`.

# Returns: {'firing_rate_hz': 15, 'refr_violations_pct': 2.1, 'is_good_single_unit': True, ...}
```

## Canonical Functions (session-level)

```python
session = oa.read('path/to/file.nwb')

## 12-Condition Omission Paradigm & Unit Classification (Westerberg 2024 / Garrett 2020)

The canonical visual omission paradigm defines 12 distinct trial condition codes:
- **A-Family**: `AAAB` (Slot 4 local oddball), `AAAX` (Slot 4 omission), `AAXB` (Slot 3 omission), `AXAB` (Slot 2 omission).
- **B-Family**: `BBBA` (Slot 4 local oddball), `BBBX` (Slot 4 omission), `BBXA` (Slot 3 omission), `BXBA` (Slot 2 omission).
- **Random Control**: `RRRR` (Random control), `RRRX` (Slot 4 random omission), `RRXR` (Slot 3 random omission), `RXRR` (Slot 2 random omission).

### Template Correlation Classification (5,000 Shuffles)

Unit responses are classified into **S+** (stimulus-driven), **S-** (suppressed), **O+** (omission-selective), and **Null/Other** via Spearman correlation of 9-element per-epoch firing rate vectors against binary templates (`scripts/template_correlation_selection.py`):
- **S+ Template**: `[0, 1, 0, 1, 0, 1, 0, 1, 0]` (Peaks on stimulus presentations).
- **S- Template**: `[1, 0, 1, 0, 1, 0, 1, 0, 1]` (Peaks during inter-stimulus intervals).
- **O+ Template**: One-hot vector peaking specifically at the omitted slot (e.g. Unit 51).
- **VIP Ramping & Adaptation Release**: VIP interneurons show pre-stimulus inter-stimulus ramping and strong omission ramping for familiar images (Garrett et al. 2020). Local oddball responses ($x-x-x-y$) emerge early in L2/3 feedforward stream, representing adaptation release rather than predictive error (Westerberg et al. 2024).

```python
# Raster via session
raster = raster_plot(session, unit_id=42, condition='AAXB', phase=3, window_ms=(-500, 2000))

# PSTH via session
psth = psth_analysis(session, unit_id=42, condition='AAXB', phase=3, bin_size_ms=10)

# Autocorrelogram via session
acg = autocorrelogram(session, unit_id=42, max_lag_ms=100)

# Find units by criteria
units_df = find_units(session, quality='stable_plus', area='V1', firing_rate_range=(1, 200))

# Unit quality scores
quality = unit_quality_scores(session, unit_id=42)
```

## OmissionSession Shortcut: raster_suite

```python
# Full suite: raster + PSTH + autocorrelogram in one call
session.raster_suite(unit_id=42, condition='AAXB', phase=3)
```

## jnwb.spiking Module Functions

```python
# Response metrics (baseline vs. evoked FR)
metrics = compute_response_metrics(spike_times, trial_onsets,
                                   baseline_window=(-0.250, -0.050),
                                   response_window=(0.0, 0.150))
# Returns: {'baseline_rate': ..., 'response_rate': ..., 'response_zscore': ...}

# Classify omission selectivity
stim_onsets = session.get_epochs(condition='AAAB')["start_time"].values
omission_onsets = session.get_epochs(condition='AAXB')["start_time"].values
omit_class = classify_omission_response(spike_times, stim_onsets, omission_onsets)
# Returns: {'sig_s': bool, 'sig_o': bool, 'stimulus_rate': ..., 'omission_rate': ...}

# Phase-locking index
pli = phase_locking_index(spike_times, lfp_phase_array, lfp_timestamps)
# Returns: {'pli': ..., 'preferred_phase': ..., 'rayleigh_pvalue': ...}
```

## Template-Correlation Classification (Canonical, 2026-07-13)

**This is the current canonical method for assigning S+/S-/O+/Null labels to single units.**
It supersedes the prior drift-stability-only selection (which checked CV/Spearman stability
but did not verify that a unit's response matched the shape implied by its class name).

Reference implementation: `scripts/archive_oneoff/template_correlation_selection.py`
Output: `outputs/classification/figure3_template_correlation_scan.csv` (330 rows for sub-C31o_ses-230823)

### Epoch template structure

The analysis window is the 9-epoch sequence: `[fx, p1, d1, p2, d2, p3, d3, p4, d4]`.
Per-epoch firing rate is computed over each epoch's real duration (from `EPOCH_ONSETS_MS`)
and normalized by that duration (Hz).

| Class | Template (9-element) | Description |
|-------|----------------------|-------------|
| S+    | `[0,1,0,1,0,1,0,1,0]` | Fires during stimulus slots (p1,p2,p3,p4) |
| S−    | `[1,0,1,0,1,0,1,0,1]` | Fires during delay/fixation slots |
| O+    | One-hot at omitted slot (RXRR→d2 omit→p2 slot, etc.), averaged across 3 omission conditions | Selective omission response |
| Null  | No significant correlation with any template (p≥0.05 permutation test) | Non-selective |

### Significance gate

Permutation test: shuffle the per-epoch rate vector 5000 times; p-value = fraction of
shuffled correlations exceeding the observed |r|. Threshold: **p < 0.05**.

**Priority when multiple templates are significant:**  
O+ > S+ ≈ S− (choose higher |r| to break ties). A unit classified O+ may also show
incidental S+/S− correlation — do not re-classify based on S template alone.

### Confirmed best picks for sub-C31o_ses-230823_rec (only session with real O+ units)

| Class | Unit (row index) | r | p |
|-------|-----------------|---|---|
| S+    | 337 | 0.985 | 0.008 |
| S−    | 261 | 0.985 | 0.003 |
| O+    | 51  | r_mean=0.769 (best across 3 omission conditions) | — |

**Why old picks were wrong:** S+ = unit 17 (r=0.46, p=0.19 — not significant); S− = unit 189
(r=0.04, p=0.89 — effectively uncorrelated). CV/drift alone is not sufficient.

### Open discrepancy (2026-07-13)

Units 240, 359, 360 are labeled "Other" by the pooled shuffle classifier
(`grand_unit_table_shuffle_sso.csv`) but rank top-10 S− template matches (r=0.92–0.95,
p<0.01). The pooled classifier may be under-calling S− units that fire strongly between
stimuli. Not resolved — investigate before trusting either classifier exclusively for S−.

### Extending to all sessions / multi-session

`scripts/archive_oneoff/template_correlation_selection.py` currently runs on one NWB session.
To extend to all 21 NWB sessions (or the `suite_tfr_ready=True` subset), wrap in a loop over
`artifacts/data/session_readiness.csv` rows where `suite_tfr_ready=True`, then append
results to a session-tagged CSV (`session_prefix`, `unit_id`, `r_Splus`, `p_Splus`, etc.).

## Response Classification (S+ / S− / O+ / Null)

The **canonical classifier** is `jnwb.unit_classification` (shuffle-test based, FDR-corrected,
multi-session) — the template-correlation method above provides a complementary approach
optimized for pattern-shape verification and exemplar unit selection for figures.

Grand unit table: `outputs/classification/grand_unit_table_shuffle_sso.csv`
- `display_class`: S+ | S− | O+ | Other (from pooled shuffle classifier)
- As of 2026-07-12: **43 S+, 1 O+, 19 S−, 20 Other** (sub-C31o_ses-230823_rec only)
- Session-wide counts across all sessions are in the grand table; stable-plus total varies by
  session — always re-derive from the CSV, do not hardcode.

## Footgun: "stable across trials" needs a drift metric, not just CV

Coefficient of variation (`std/mean` of per-trial spike count) is scale-invariant and does
**not** catch trial-order drift — a unit whose rate ramps monotonically up/down across the real
trial sequence can still score a low CV while looking visibly non-stationary in a rendered
raster. Confirmed real case: a unit with a moderate CV was sparse in early trials and dense in
late trials, caught only by actually rendering and looking at the raster, not by the CV number.
When "stable/consistent across trials" is a selection criterion (e.g. picking one exemplar unit
per class for a figure), use `abs(scipy.stats.spearmanr(trial_index, per_trial_spike_count)
.correlation)` instead (worst-case across conditions if multiple apply), and visually confirm
the rendered result before trusting the metric.

Relatedly: passing a canonical significance test (e.g. `jnwb.unit_classification.is_o_plus`,
which pools across all omission slots with FDR) is not the same claim as "this specific
condition/slot visibly shows the effect" — verify the specific comparison a figure will display,
don't assume classifier pass implies every individual panel looks convincing. See
`.agents/AGENTS.md` footgun #7 for a concrete case where the passing unit had the weakest visible
effect of all real candidates.

## Laminar Assignment (Putative Layer)

- **Superficial**: unit channel within ±10 channels of another verified superficial unit → N = 614
- **Deep**: unit channel within ±10 channels of another verified deep unit → N = 1,813
- **Unresolved**: ~25 % remain unresolved

## Diagnostic Verification Guidelines

### 1. Row Index vs. Kilosort ID Mapping (Mapping Validation check)
* **Crucial Rule**: The `get_spike_times(index)` method indexes by the **positional row index** of the unit dataframe, NOT the Kilosort `unit_id` column value.
* Always assert mapping correctness before indexing to avoid off-by-one errors (where you silently load a neighboring high-FR unit):
  ```python
  unit_row = ... # your mapping target
  assert units.loc[unit_row, 'unit_id'] == target_ks_id, f"Mapping mismatch: row {unit_row} is unit {units.loc[unit_row, 'unit_id']} not {target_ks_id}"
  ```

### 2. S+ Omission Slot Suppression
* An S+ unit must not only show standard visual slot activation (`stim > delay` modulation), but also show **genuine stimulus-driven drop** when that visual slot is omitted (i.e. `p2_RXRR < p2_RRRR`, `p3_RRXR < p3_RRRR`, `p4_RRRX < p4_RRRR`). 
* Always check the condition-specific epoch vectors (e.g. `mean_drop_hz = mean(RRRR_px - Omitted_px)`) to verify that the visual response is indeed suppressed in the absence of the stimulus.

