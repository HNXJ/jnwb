# NWB Data Extraction: Generalized Patterns

**Purpose**: Unified extraction framework for events, LFP, spike times, and convolved spike rates aligned to any event type (P1, P2, P3, P4, reward, etc.)

---

## Core Extraction Workflow

```
[1] Load NWB file
    ↓
[2] Create binary event filters (correct, event_type, condition, etc.)
    ↓
[3] Combine filters (e.g., correct AND p1 AND AAAB)
    ↓
[4] Get onset times for matched events
    ↓
[5] Extract aligned signal windows (LFP, convolved spikes, raw spikes)
    ↓
[6] Stack into tensors (n_events, n_timepoints, n_channels/units)
```

---

## Step 1: Load NWB

```python
from pynwb import NWBHDF5IO

nwb_path = "D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb"

with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
    nwb = io.read()
    
    # Verify key components
    assert nwb.intervals is not None, "No intervals table"
    assert 'omission_glo_passive' in nwb.intervals, "No omission_glo_passive table"
    assert nwb.units is not None, "No units table"
```

---

## Step 2: Create Binary Event Filters

### Pattern: One filter per criterion

```python
import numpy as np
import pandas as pd

# Load intervals table
interval_df = nwb.intervals['omission_glo_passive'].to_dataframe()

# Example filters (create as needed)
correct_b = (interval_df['correct'] == 1.0).values
p1_b = (interval_df['stimulus_number'] == 2.0).values
p2_b = (interval_df['stimulus_number'] == 3.0).values
p3_b = (interval_df['stimulus_number'] == 4.0).values
p4_b = (interval_df['stimulus_number'] == 5.0).values
reward_b = (interval_df['codes'] == 40.0).values

# Condition-specific filters
aaab_b = (interval_df['task_condition_number'].isin([1.0, 2.0])).values
axab_b = (interval_df['task_condition_number'] == 3.0).values
# ... etc for all 12 condition groups

# Block filter
block_1_b = (interval_df['task_block_number'] == 1.0).values
```

### Key Boolean Operators

```python
# AND (both must be true)
correct_p1 = correct_b & p1_b

# OR (either can be true)  
aaab_or_bbba = aaab_b | bbba_b

# NOT (negate)
errors = ~correct_b

# Complex combinations
correct_p1_aaab = correct_b & p1_b & aaab_b
correct_any_condition = correct_b & p1_b  # Works for all conditions
```

---

## Step 3: Get Onset Times

### For any matched event set

```python
# Get onset times for matched events
def get_onset_times(interval_df, binary_mask):
    """Extract start times for True indices in binary mask."""
    return interval_df.loc[binary_mask, 'start_time'].values

# Examples
p1_correct_onsets = get_onset_times(interval_df, correct_b & p1_b)
p2_correct_onsets = get_onset_times(interval_df, correct_b & p2_b)
p3_correct_onsets = get_onset_times(interval_df, correct_b & p3_b)

reward_onsets = get_onset_times(interval_df, reward_b)
aaab_correct_p1_onsets = get_onset_times(interval_df, correct_b & p1_b & aaab_b)

print(f"P1 correct events: {len(p1_correct_onsets)}")
print(f"P1 correct AAAB events: {len(aaab_correct_p1_onsets)}")
```

---

## Step 4: Extract Aligned Signal Windows

### 4a. LFP Extraction

```python
def extract_lfp_aligned(nwb, onset_times, time_pre=0.25, time_post=1.75):
    """
    Extract LFP windows aligned to event onsets.
    
    Args:
        nwb: NWBFile object
        onset_times: Array of event times (seconds from session start)
        time_pre: Seconds before onset
        time_post: Seconds after onset
    
    Returns:
        np.ndarray: (n_events, n_timepoints, n_channels)
    """
    
    # Find LFP data
    lfp_data = None
    lfp_timestamps = None
    lfp_fs = None
    
    for acq_name, acq in nwb.acquisition.items():
        if hasattr(acq, 'data') and hasattr(acq, 'rate'):
            if 'lfp' in acq_name.lower():
                lfp_data = acq.data[:]
                lfp_timestamps = acq.timestamps[:]
                lfp_fs = int(acq.rate)
                break
    
    if lfp_data is None:
        raise ValueError("No LFP data found")
    
    # Calculate window sizes
    samples_pre = int(time_pre * lfp_fs)
    samples_post = int(time_post * lfp_fs)
    total_samples = samples_pre + samples_post
    
    # Extract epochs
    epochs = []
    for onset_time in onset_times:
        # Find closest timestamp
        idx = np.searchsorted(lfp_timestamps, onset_time)
        start_idx = max(0, idx - samples_pre)
        end_idx = min(len(lfp_data), idx + samples_post)
        
        # Extract window
        epoch = lfp_data[start_idx:end_idx, :]
        
        # Pad if necessary (at edges)
        if epoch.shape[0] < total_samples:
            pad_top = idx - samples_pre - start_idx
            pad_bottom = total_samples - epoch.shape[0] - pad_top
            epoch = np.pad(epoch, ((pad_top, pad_bottom), (0, 0)), 
                          mode='constant', value=np.nan)
        
        epochs.append(epoch)
    
    return np.array(epochs)

# Usage
lfp_p1_correct = extract_lfp_aligned(nwb, p1_correct_onsets)
# Returns: (937 events, 2000 timepoints, 128 channels) for session 230823
```

### 4b. Convolved Spike Train Extraction

```python
def extract_convolved_spikes_aligned(nwb, onset_times, unit_ids, 
                                      time_pre=0.25, time_post=1.75):
    """
    Extract convolved spike signal windows aligned to event onsets.
    
    Args:
        nwb: NWBFile object
        onset_times: Array of event times
        unit_ids: List of unit IDs to extract (or list(range(n_units)) for all)
        time_pre: Seconds before onset
        time_post: Seconds after onset
    
    Returns:
        np.ndarray: (n_events, n_timepoints, n_units)
    """
    
    conv_data = nwb.processing['convolved_spike_train']['convolved_spike_train_data']
    timestamps = conv_data.timestamps
    data = conv_data.data
    
    # Infer sampling rate
    dt = np.diff(timestamps[:100]).mean()
    fs = 1.0 / dt  # ~1000 Hz
    
    # Calculate window sizes
    samples_pre = int(time_pre * fs)
    samples_post = int(time_post * fs)
    total_samples = samples_pre + samples_post
    
    # Extract epochs for specified units
    epochs = []
    for onset_time in onset_times:
        idx = np.searchsorted(timestamps, onset_time)
        start_idx = max(0, idx - samples_pre)
        end_idx = min(len(data), idx + samples_post)
        
        # Extract window
        epoch = data[start_idx:end_idx, :][:, unit_ids]
        
        # Pad if necessary
        if epoch.shape[0] < total_samples:
            pad_top = idx - samples_pre - start_idx
            pad_bottom = total_samples - epoch.shape[0] - pad_top
            epoch = np.pad(epoch, ((pad_top, pad_bottom), (0, 0)), 
                          mode='constant', value=np.nan)
        
        epochs.append(epoch)
    
    return np.array(epochs)

# Usage
fef_unit_ids = list(range(156))  # Unit IDs 0–155 are FEF
spk_fef_p1_correct = extract_convolved_spikes_aligned(
    nwb, p1_correct_onsets, fef_unit_ids
)
# Returns: (937 events, 2000 timepoints, 156 FEF units)
```

### 4c. Raw Spike Times Extraction

```python
def extract_spike_times_aligned(nwb, onset_times, unit_ids,
                                 time_pre=0.25, time_post=1.75):
    """
    Extract spike times (sparse) for windows around event onsets.
    
    Returns:
        List of lists: [unit_id][event_id] = array of spike times in window
    """
    
    units_df = nwb.units.to_dataframe()
    
    # Pre-allocate
    epochs = {uid: [] for uid in unit_ids}
    
    for onset_time in onset_times:
        # Define window
        window_start = onset_time - time_pre
        window_end = onset_time + time_post
        
        # Extract spike times for each unit in this window
        for unit_id in unit_ids:
            spike_times = units_df.iloc[unit_id]['spike_times']
            spikes_in_window = spike_times[
                (spike_times >= window_start) & (spike_times <= window_end)
            ]
            # Align to window start
            spikes_aligned = spikes_in_window - window_start
            epochs[unit_id].append(spikes_aligned)
    
    return epochs

# Usage
spike_times_fef = extract_spike_times_aligned(nwb, p1_correct_onsets, fef_unit_ids)
# Returns dict where spike_times_fef[unit_id][event_id] = array of spike times
```

---

## Step 5: Stack & Save Tensors

```python
# Stack epochs across all events and units
lfp_tensor = np.stack([lfp_p1_correct, lfp_p2_correct, lfp_p3_correct])
# Shape: (3 phases, 937 events, 2000 timepoints, 128 channels)

# For a single phase
spk_tensor = extract_convolved_spikes_aligned(nwb, p1_correct_onsets, fef_unit_ids)
# Shape: (937 events, 2000 timepoints, 156 FEF units)

# Save to disk
output_dir = Path("outputs/aligned_neural_data")
output_dir.mkdir(parents=True, exist_ok=True)

np.save(output_dir / f"ses230823_p1_correct_lfp.npy", lfp_p1_correct)
np.save(output_dir / f"ses230823_p1_correct_fef_spikes.npy", spk_tensor)

# Save metadata
metadata = {
    'session': 230823,
    'phase': 'P1',
    'condition': 'all_correct',
    'n_events': len(p1_correct_onsets),
    'n_timepoints': 2000,
    'time_pre_ms': 250,
    'time_post_ms': 1750,
    'sampling_rate': 1000,
    'n_lfp_channels': 128,
    'n_spk_units_fef': 156
}

with open(output_dir / f"ses230823_p1_metadata.json", 'w') as f:
    json.dump(metadata, f, indent=2)
```

---

## Multi-Phase, Multi-Condition Extraction Template

```python
def extract_complete_dataset(nwb, interval_df, session_id, output_dir):
    """
    Systematically extract P1, P2, P3, P4 for all 12 condition groups.
    """
    
    phases = {
        'P1': 2.0,
        'P2': 3.0,
        'P3': 4.0,
        'P4': 5.0,
    }
    
    conditions = {
        'AAAB': [1.0, 2.0],
        'AXAB': [3.0],
        'AAXB': [4.0],
        'AAAX': [5.0],
        'BBBA': [6.0, 7.0],
        'BXBA': [8.0],
        'BBXA': [9.0],
        'BBBX': [10.0],
        'RRRR': list(np.arange(11, 27)),
        'RXRR': list(np.arange(27, 35)),
        'RRXR': [35, 37, 39, 41],
        'RRRX': [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
    }
    
    # Get FEF units
    units_df = nwb.units.to_dataframe()
    elec_df = nwb.electrodes.to_dataframe()
    
    fef_units = []
    for unit_id, row in units_df.iterrows():
        peak_ch = int(float(row['peak_channel_id']))
        location = elec_df.iloc[peak_ch]['location']
        if location == 'FEF':
            fef_units.append(unit_id)
    
    # Create binary filters once
    correct_b = (interval_df['correct'] == 1.0).values
    
    # Extract per phase × condition
    for phase_name, stim_num in phases.items():
        phase_b = (interval_df['stimulus_number'] == stim_num).values
        
        for cond_name, cond_codes in conditions.items():
            cond_b = (interval_df['task_condition_number'].isin(cond_codes)).values
            
            # Combined filter
            matched = correct_b & phase_b & cond_b
            onsets = interval_df.loc[matched, 'start_time'].values
            
            if len(onsets) == 0:
                continue
            
            # Extract data
            lfp = extract_lfp_aligned(nwb, onsets)
            spk = extract_convolved_spikes_aligned(nwb, onsets, fef_units)
            
            # Save
            filename = f"ses{session_id}_{phase_name}_{cond_name}"
            np.save(output_dir / f"{filename}_lfp.npy", lfp)
            np.save(output_dir / f"{filename}_spk_fef.npy", spk)
            
            print(f"{phase_name} {cond_name}: {len(onsets)} events")

# Usage
output_dir = Path("outputs/neural_data_aligned")
extract_complete_dataset(nwb, interval_df, 230823, output_dir)
```

---

## Validation Checklist

After extraction, verify:

- ✓ **Shape consistency**: All epochs have same (n_events, 2000, n_channels)
- ✓ **NaN handling**: Document < 5% NaN values, mark bad epochs
- ✓ **Trial counts**: Verify P1 = P2 = P3 = P4 for each condition
- ✓ **Temporal alignment**: Check p1_onset aligned to start_time
- ✓ **Metadata saved**: Timestamp, sampling rate, condition labels
- ✓ **Signal sanity**: LFP baseline < stimulus power; spikes 0–1000 Hz range

---

## Key References

- **Event structure**: `nwb_event_structure.md`
- **Neural data**: `nwb_neural_data_structure.md`
- **Helper functions**: `scripts/jnwb_helper_functions.py`
- **Example session**: sub-C31o-230823 (FEF, 368 units, 937 P1 events)

---

## Performance Notes

For session 230823:
- **LFP extraction**: ~30 seconds (937 events × 128 channels)
- **Convolved spikes**: ~15 seconds (937 events × 156 FEF units)
- **Memory usage**: ~10 GB for full (3 probes) × (4 phases) × (12 conditions)

Optimize by:
- Extracting single condition at a time
- Using uint16 quantization for LFP (±5V range)
- Extracting subset of units/channels if full dataset too large
