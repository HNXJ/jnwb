# Omission Neurons and Spectrolaminar Mapping Reference Guide

This document serves as the canonical spec and technical reference for reproducing the omission-responsive neuron identification, template waveform processing, and LFP spectrolaminar (vFLIP2) mapping.

---

## 1. How to Read Data from NWB Files
PyNWB provides the object-oriented wrapper around HDF5. To read the session data cleanly without resource leaks:

```python
from pynwb import NWBHDF5IO
import pandas as pd
import numpy as np

# Load session NWB
with NWBHDF5IO("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb", 'r', load_namespaces=True) as io:
    nwb = io.read()
    
    # 1. Units Table (Neuronal metadata and spikes)
    units_df = nwb.units.to_dataframe()
    
    # 2. Electrodes Table (Probe contact mapping)
    elec_df = nwb.electrodes.to_dataframe()
    
    # 3. Intervals (Trials and timing events)
    intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
    
    # 4. Raw LFP Data (Acquisition)
    lfp_series = nwb.acquisition['probe_0_lfp']
```

> [!IMPORTANT]
> PyNWB columns like `correct`, `stimulus_number`, `task_condition_number`, and `snr` are frequently stored as string objects (e.g. `'1.0'`). Always cast them via `pd.to_numeric` before performing comparisons.

---

## 2. Identifying Omission-Responsive Units
Omission units are verified neurons in PFC and FEF that significantly increase their firing rate during the omission window compared to the control condition.

### Selection Criteria:
1. **Quality Metrics**: `presence_ratio > 0.98` and `firing_rate > 1.0 Hz`
2. **Anatomical Mapping**: Peak channel located in `'PFC'` or `'FEF'` (determined by matching unit `peak_channel_id` to electrode table `location`).
3. **Response Gate**: Firing rate in the omission window (1100–1600 ms, 2100–2600 ms, or 3100–3600 ms aligned to first stimulus onset `p1`) must increase by $> 2.0\text{ Hz}$ compared to the control `RRRR` condition.

### Alignment Logic:
```python
# Condition code groupings
CONDITION_LABEL_TO_NUMBERS = {
    "RRRR": list(range(11, 27)),
    "RXRR": list(range(27, 35)),
    "RRXR": [35, 37, 39, 41],
    "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
}

def get_onsets_for_condition(intervals_df, cond_label):
    correct_val = pd.to_numeric(intervals_df['correct'], errors='coerce')
    stim_num_val = pd.to_numeric(intervals_df['stimulus_number'], errors='coerce')
    cond_num_val = pd.to_numeric(intervals_df['task_condition_number'], errors='coerce')
    matched = (correct_val == 1.0) & (stim_num_val == 2.0) & (cond_num_val.isin(CONDITION_LABEL_TO_NUMBERS[cond_label]))
    return intervals_df.loc[matched, 'start_time'].values
```

---

## 3. Waveform Processing and Fitting
Template waveforms (`waveform_mean`) extracted by spike sorters like Kilosort can suffer from baseline drift. A two-pass quality control pipeline handles detrending, alignment, and slope estimation.

```python
# Detrending, Trough-Alignment, and Normalization
def process_single_waveform(wf):
    # 1. Detrend: subtract linear trend between start and end of 82-sample array
    start_val = np.mean(wf[:5])
    end_val = np.mean(wf[-5:])
    x = np.arange(len(wf))
    trend = start_val + (end_val - start_val) * (x / (len(wf) - 1))
    wf_detrend = wf - trend
    
    # 2. Trough check and alignment (Reject off-center troughs)
    trough_idx = np.argmin(wf_detrend)
    if not (10 <= trough_idx <= 45):
        raise ValueError("Off-center trough, bad waveform")
        
    target_trough = 30
    shift = target_trough - trough_idx
    aligned = np.roll(wf_detrend, shift)
    if shift > 0:
        aligned[:shift] = aligned[shift]
    elif shift < 0:
        aligned[shift:] = aligned[shift-1]
        
    # 3. Normalize: set baseline (samples 0-10) to 0.0, trough to -1.0
    baseline = np.mean(aligned[:10])
    trough_val = aligned[target_trough]
    amp = abs(trough_val - baseline)
    if amp < 0.01:
         raise ValueError("Flat waveform outlier")
         
    norm_wf = (aligned - baseline) / amp
    return norm_wf
```

### Rise/Fall Slope Estimation:
* **Trough-to-Peak Duration**: `(t_post_peak - t_trough) * 33.33` us.
* **Fit slopes**: Computed via linear regression (`np.polyfit`) over the respective fall and rise samples.

```python
# Rise & Fall slopes
t_post_peak = 30 + np.argmax(norm_wf[30:65])
t_pre_peak = 15 + np.argmax(norm_wf[15:30])

fall_x = np.arange(t_pre_peak, 31)
fall_slope_fit = np.polyfit(fall_x, norm_wf[fall_x], 1)[0] / 0.033333 # unit/ms

rise_x = np.arange(30, t_post_peak + 1)
rise_slope_fit = np.polyfit(rise_x, norm_wf[rise_x], 1)[0] / 0.033333 # unit/ms
```

---

## 4. Spectrolaminar Motif (vFLIP2)
The spectrolaminar motif identifies Layer 4 (L4) as a power-crossover boundary between Gamma and Alpha/Beta power.

* **Alpha/Beta band**: 8–30 Hz (dominant in deep layers, L5/L6)
* **Gamma band**: 35–80 Hz (dominant in superficial layers, L2/3)

```python
from scipy.signal import welch
from scipy.ndimage import gaussian_filter1d

# Epoch ~20,000ms of LFP data in 6000ms chunks to match Welch window
# lfp_raw shape: (120000, 128) representing 120s of LFP data
lfp_epochs = lfp_raw.T.reshape(128, 20, 6000).transpose(1, 0, 2) # (20, 128, 6000)
data = lfp_epochs[:, :, 1000:6000]

# PSD profiles per channel
ab_power = np.zeros(128)
ga_power = np.zeros(128)
for ch in range(128):
    f, pxx = welch(data[:, ch, :], fs=1000.0, nperseg=512, axis=-1)
    mean_pxx = np.nanmean(pxx, axis=0)
    ab_power[ch] = np.mean(mean_pxx[(f >= 8) & (f <= 30)])
    ga_power[ch] = np.mean(mean_pxx[(f >= 35) & (f <= 80)])

# Smooth profiles spatially across probe contacts
ab_smooth = gaussian_filter1d(ab_power, sigma=2.0)
ga_smooth = gaussian_filter1d(ga_power, sigma=2.0)
```

---

## 5. Finding and Validating the Crossover
The crossover index is the channel where normalized Gamma power crosses below normalized Alpha/Beta power.

```python
# Normalize to max to balance different scales
ab_norm = ab_smooth / np.max(ab_smooth)
ga_norm = ga_smooth / np.max(ga_smooth)
diff = ga_norm - ab_norm

# Detect zero crossover from positive (Gamma dominant) to negative (Alpha/Beta dominant)
crossover_idx = np.nan
for i in range(len(diff) - 1):
    if diff[i] > 0 and diff[i+1] < 0:
        crossover_idx = i + (0 - diff[i]) / (diff[i+1] - diff[i])
        break
```

### Auditing Biological Orientation:
Verify that the below-crossover region (`channel > crossover_idx`) has greater Alpha/Beta dominance than the above-crossover region:
$$\text{Mean}(AB_{\text{below}}) > \text{Mean}(AB_{\text{above}})$$
If this inequality holds, the probe orientation is normal (Channel 0 is superficial, Channel 127 is deep). If flipped, swap the Superficial and Deep labels relative to the crossover point.

---

## 6. Mapping Units to Laminar Positions
Compare a unit's `peak_channel_id` to the session's crossover index to assign its putative layer:

```python
# Laminar assignment mapping contract (Normal Orientation)
c_idx = session_crossover_channel

if peak_channel < c_idx - 1:
    putative_layer = "Superficial (L2/3)"
elif peak_channel < c_idx + 1:
    putative_layer = "Middle (L4)"
else:
    putative_layer = "Deep (L5/L6)"
```
* Note: A margin of $\pm 1$ channel is classified as Middle (L4).
