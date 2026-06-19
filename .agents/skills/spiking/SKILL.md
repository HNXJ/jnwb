---
name: spiking
description: >
  Single-unit spiking analysis for the Omission project: spike binning, PSTH
  construction, firing-rate traces, omission selectivity audit, waveform
  classification, and putative deep/superficial layer assignment.
---

# Skill: spiking — Single-Unit Spiking Analysis

## Purpose
Give an agent the exact recipes for all spiking computations: loading spike
times from NWB, constructing PSTHs, classifying omission responsiveness, and
assigning putative deep/superficial layer from waveform features.

---

## 1. Imports

```python
from pynwb import NWBHDF5IO
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from scipy.ndimage import gaussian_filter1d
from src.analysis.spiking.stats import compute_unit_metrics, compute_mutual_info
from src.analysis.spiking.putative_classification import classify_putative_type
from src.analysis.spiking.omission_hierarchy_utils import build_omission_hierarchy
```

---

## 2. Aligned PSTH Construction

```python
def compute_psth(spike_times, onsets_sec, pre_ms=-1000, post_ms=4000,
                 bin_ms=5.0, sigma_ms=40.0):
    """
    Compute trial-averaged PSTH.
    spike_times : 1-D array of timestamps in seconds.
    onsets_sec  : 1-D array of trial onset times in seconds.
    Returns:
        t_ms   : (n_bins,) bin centres in ms from p1 onset
        rate   : (n_bins,) mean firing rate in Hz
        sem    : (n_bins,) SEM in Hz
    """
    pre_s   = abs(pre_ms)  / 1000.0
    post_s  = abs(post_ms) / 1000.0
    n_bins  = int((pre_s + post_s) * 1000.0 / bin_ms)
    edges   = np.linspace(-pre_s, post_s, n_bins + 1)
    t_ms    = (edges[:-1] + edges[1:]) / 2.0 * 1000.0

    spike_counts = []
    for onset in onsets_sec:
        rel = spike_times - onset
        counts, _ = np.histogram(rel, bins=edges)
        spike_counts.append(counts.astype(float))

    spike_mat = np.stack(spike_counts)           # (trials, bins)
    rate      = np.mean(spike_mat, axis=0) / (bin_ms / 1000.0)    # Hz
    sem       = np.std(spike_mat, axis=0) / np.sqrt(len(onsets_sec)) / (bin_ms / 1000.0)

    if sigma_ms > 0:
        sigma_bins = sigma_ms / bin_ms
        rate = gaussian_filter1d(rate, sigma=sigma_bins)
        sem  = gaussian_filter1d(sem,  sigma=sigma_bins)

    return t_ms, rate, sem
```

Standard parameters:
- Pre-stimulus: **-1000 ms**
- Post-stimulus: **+4000 ms**
- Bin width: **5 ms**
- Gaussian sigma: **40 ms** (smoothing)

---

## 3. Trial-by-Trial Spike Matrix (for Rasters)

```python
def build_spike_matrix(spike_times, onsets_sec, pre_ms=-1000, post_ms=4000,
                       max_trials=40):
    """
    Returns list of aligned spike times per trial (for raster plots).
    Also returns binned boolean matrix (trials, time_bins) at 1 ms resolution.
    """
    onsets_sec = onsets_sec[:max_trials]
    total_ms   = int(abs(pre_ms) + abs(post_ms))
    binary_mat = np.zeros((len(onsets_sec), total_ms), dtype=np.float32)
    rasters    = []

    for k, onset in enumerate(onsets_sec):
        rel_ms  = (spike_times - onset) * 1000.0
        in_win  = rel_ms[(rel_ms >= pre_ms) & (rel_ms < post_ms)]
        rasters.append(in_win)
        idx = (in_win - pre_ms).astype(int)
        idx = idx[(idx >= 0) & (idx < total_ms)]
        binary_mat[k, idx] = 1.0

    return rasters, binary_mat   # list[ndarray], (trials, total_ms)
```

---

## 4. Omission Selectivity Audit (Strict Criteria)

A unit is **genuine omission-responsive** if it satisfies **all**:

| Criterion | Threshold |
|-----------|-----------|
| ΔFR (omission − control) | ≥ 4.0 Hz |
| Mann-Whitney U p-value | < 0.01 (one-sided `greater`) |
| Both requirements | in at least 1 family slot (A, B, or R) |

```python
from src.analysis.io.nwb_address import CONDITION_NUMBER_MAP, SEQUENCE_TIMING_MS

OMISSION_SLOTS = {
    # family → slot_name → {window_ms, omission_codes, ctrl_codes}
    "A": {
        "p2": {"window": (1031, 1531), "codes": [3],  "ctrl": [1, 2]},
        "p3": {"window": (2062, 2562), "codes": [4],  "ctrl": [1, 2]},
        "p4": {"window": (3093, 3593), "codes": [5],  "ctrl": [1, 2]},
    },
    "B": {
        "p2": {"window": (1031, 1531), "codes": [8],  "ctrl": [6, 7]},
        "p3": {"window": (2062, 2562), "codes": [9],  "ctrl": [6, 7]},
        "p4": {"window": (3093, 3593), "codes": [10], "ctrl": [6, 7]},
    },
    "R": {
        "p2": {"window": (1031, 1531), "codes": list(range(27, 35)),
               "ctrl": list(range(11, 27))},
        "p3": {"window": (2062, 2562), "codes": [35, 37, 39, 41],
               "ctrl": list(range(11, 27))},
        "p4": {"window": (3093, 3593), "codes": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
               "ctrl": list(range(11, 27))},
    },
}

MIN_DELTA_FR = 4.0   # Hz
MAX_P_VAL    = 0.01

def is_strict_omission(spike_times, intervals_df) -> bool:
    """Return True if the unit passes the strict omission audit."""
    for fam, slots in OMISSION_SLOTS.items():
        for slot_name, cfg in slots.items():
            w0_s, w1_s = cfg["window"][0] / 1000.0, cfg["window"][1] / 1000.0
            win_dur    = w1_s - w0_s

            def _rates(codes):
                from src.analysis.io.nwb_address import CONDITION_NUMBER_MAP
                correct = pd.to_numeric(intervals_df['correct'], errors='coerce') == 1.0
                stim    = pd.to_numeric(intervals_df['stimulus_number'], errors='coerce') == 2.0
                cond    = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce').isin(codes)
                onsets  = intervals_df.loc[correct & stim & cond, 'start_time'].values
                if len(onsets) < 5:
                    return None
                rates = []
                for onset in onsets:
                    t0, t1 = onset + w0_s, onset + w1_s
                    n = np.sum((spike_times >= t0) & (spike_times < t1))
                    rates.append(n / win_dur)
                return np.array(rates)

            om_rates   = _rates(cfg["codes"])
            ctrl_rates = _rates(cfg["ctrl"])
            if om_rates is None or ctrl_rates is None:
                continue
            diff = np.mean(om_rates) - np.mean(ctrl_rates)
            if diff < MIN_DELTA_FR:
                continue
            try:
                _, p = mannwhitneyu(om_rates, ctrl_rates, alternative='greater')
            except Exception:
                p = 1.0
            if p < MAX_P_VAL:
                return True
    return False
```

---

## 5. Waveform Classification (Putative E/I)

```python
from src.analysis.spiking.putative_classification import classify_putative_type

# waveform_mean: 1-D array of 82 voltage samples (at 30 kHz → 2.73 ms total)
# Returns: "narrow" (putative inhibitory) | "broad" (putative excitatory) | "ambiguous"
wf_class = classify_putative_type(waveform_mean)
```

Key waveform features (from SPSAM metadata CSV):
- `waveform_duration` (ms): trough-to-peak
- `waveform_halfwidth` (ms): FWHM of the trough
- Broad ≥ 0.5 ms duration → putative excitatory (pyramidal)
- Narrow < 0.35 ms → putative inhibitory (interneuron)

---

## 6. Putative Deep / Superficial Layer Assignment

Layer is determined by the **spectrolaminar L4 crossover channel** stored in the
SPSAM metadata CSV:

```python
# From grand_unit_metadata.csv
# layer column: "Deep (L5/L6)", "Superficial (L2/3)", "Middle (L4)", "unresolved"

metadata = pd.read_csv("outputs/spsam/grand_unit_metadata.csv")
stable   = metadata[metadata["is_stable"]].copy()

deep_units       = stable[stable["layer"] == "Deep (L5/L6)"]
superficial_units = stable[stable["layer"] == "Superficial (L2/3)"]
```

Manual rule: `peak_channel_id < crossover_channel_id` → **Superficial**,
`peak_channel_id > crossover_channel_id` → **Deep**.

---

## 7. Population Statistics

```python
from src.analysis.spiking.stats import compute_unit_metrics

# spk_arr: (trials, units, time) at 1 ms bins
metrics = compute_unit_metrics(
    spk_arr,
    baseline_window=(0, 500),       # in bin index
    response_window=(1031, 1562),   # p2 omission window
)
# metrics[unit_idx] → {"snr": float, "presence": float, "fr": float}
```

---

## 8. Firing Rate Groups

From SPSAM metadata — `group` column:
| Group | Description |
|-------|-------------|
| `omission` | FR increases at omission (ΔFR > 0, MW p<0.05) |
| `stimulus_positive` | FR increases at stimulus p1 |
| `stimulus_negative` | FR decreases at stimulus p1 |
| `unclassified` | Does not meet any criterion |

---

## 9. Key Files

| File | Role |
|------|------|
| [spiking/stats.py](file:///D:/workspace/omission/src/analysis/spiking/stats.py) | Unit metrics, MI |
| [spiking/putative_classification.py](file:///D:/workspace/omission/src/analysis/spiking/putative_classification.py) | Waveform E/I classification |
| [spiking/omission_hierarchy_utils.py](file:///D:/workspace/omission/src/analysis/spiking/omission_hierarchy_utils.py) | Omission hierarchy builder |
| [grand_unit_metadata.csv](file:///D:/workspace/omission/outputs/spsam/grand_unit_metadata.csv) | Pre-computed stable population |
