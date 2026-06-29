# NWB Neural Data Structure: Units, Electrodes & Spikes

**Reference**: Sub-C31o-230823 (representative session with FEF recording)

## Data Sources Overview

| Data | Location | Structure | Sampling | Content |
|------|----------|-----------|----------|---------|
| **Raw spike times** | `nwb.units[unit_id].spike_times` | Sparse 1D array | Variable | Exact spike event times |
| **Convolved spikes** | `nwb.processing['convolved_spike_train']['convolved_spike_train_data']` | Dense 2D array | 1000 Hz | Smoothed spike rate |
| **Unit metadata** | `nwb.units` | Table | N/A | Quality metrics, cluster IDs |
| **Electrode metadata** | `nwb.electrodes` | Table | N/A | Channel locations, probe assignment |

---

## Units Table (`nwb.units`)

### Structure
- **Shape**: 368 rows (one per unit in session 230823)
- **Columns**: 31 metadata fields
- **Key identifier**: Row index = unit_id (0–367)

### Key Columns

#### Spike Data
- **spike_times**: Array of spike event times (seconds from session start)
  - Example unit 0: 139,729 spikes over 20,283 seconds
  - Sparse representation (only actual spike times stored)

#### Spike Waveform & Quality
- **amplitude**: Spike amplitude (microvolts)
- **waveform_mean**: Mean spike waveform shape (array of 91 samples)
- **waveform_halfwidth**: Width of action potential
- **waveform_duration**: Total waveform duration
- **peak_channel_id**: Which electrode channel shows largest spike amplitude

#### Clustering Quality
- **cluster_id**: Spike sorter cluster assignment
- **quality**: Quality rating (0.0–1.0)
- **silhouette_score**: Cluster separation metric
- **isolation_distance**: Distance to nearest other cluster
- **l_ratio**: Contamination measure
- **d_prime**: Signal-to-noise discriminability

#### Refractory Period Violations
- **isi_violations**: Interspike-interval violations (<1ms)
- **isi_mean**: Mean interspike interval (seconds)
- **isi_cv**: Coefficient of variation of ISI
- **isi_lv**: Local variation of ISI

#### Firing Properties
- **firing_rate**: Mean firing rate (Hz)
- **presence_ratio**: Fraction of recording where unit was active

#### Drift & Stability
- **cumulative_drift**: Total probe drift (micrometers)
- **max_drift**: Maximum drift in any direction
- **recovery_slope**: Recovery from drift
- **velocity_above**: Upward drift velocity
- **velocity_below**: Downward drift velocity

#### Additional Metrics
- **amplitude_cutoff**: Spike amplitude distribution edge
- **PT_ratio**: Putative pyramidal / Type-t ratio
- **snr**: Signal-to-noise ratio
- **spread**: Electrode spread
- **nn_hit_rate**: Nearest-neighbor hit rate
- **nn_miss_rate**: Nearest-neighbor miss rate
- **repolarization_slope**: Action potential repolarization rate

### Accessing Spike Data

```python
units_df = nwb.units.to_dataframe()

# Get all spikes for unit 0
unit_0_spikes = units_df.iloc[0]['spike_times']  # 1D array of spike times
print(f"Unit 0 had {len(unit_0_spikes)} spikes")

# Get quality metrics
quality = units_df.iloc[0]['quality']
firing_rate = units_df.iloc[0]['firing_rate']

# Get waveform
waveform = units_df.iloc[0]['waveform_mean']  # Shape: (91,)
```

---

## Electrodes Table (`nwb.electrodes`)

### Structure
- **Shape**: 384 rows (one per recording channel)
- **Columns**: 10 metadata fields

### Key Columns

#### Location & Probe
- **location**: Brain area(s) recorded by this electrode
  - Example values: 'FEF', 'PFC', 'V1, V2', 'MT, MST'
  - Can be compound (e.g., 'V1, V2' means channel spans both areas)
- **probe**: Which probe this channel belongs to (probeA, probeB, probeC)
- **group**: Probe group identifier
- **label**: Human-readable channel label

#### Spatial Position
- **x, y, z**: 3D coordinates of electrode tip (micrometers)

#### Physical Properties
- **imp**: Electrode impedance (ohms)
- **filtering**: Applied filtering description

### Accessing Electrode Data

```python
elec_df = nwb.electrodes.to_dataframe()

# Map units to areas via peak_channel_id
unit_peak_ch = int(float(units_df.iloc[unit_id]['peak_channel_id']))
unit_area = elec_df.iloc[unit_peak_ch]['location']

# Get all areas in session
all_areas = elec_df['location'].unique()
print(f"Areas: {all_areas}")

# Count channels per area
area_counts = elec_df['location'].value_counts()
```

---

## Convolved Spike Train (`nwb.processing['convolved_spike_train']`)

### Structure
- **Container**: `nwb.processing['convolved_spike_train']`
- **Data**: TimeSeries object `convolved_spike_train_data`
- **Shape**: (20,283,769 × 368) for session 230823
  - Dimension 0: Time samples @ 1000 Hz
  - Dimension 1: Units (368 units)
- **Data type**: float64
- **Content**: Exponentially-convolved spike rate (not binary)

### Accessing Convolved Data

```python
conv_module = nwb.processing['convolved_spike_train']
conv_data = conv_module['convolved_spike_train_data']

# Get shape and timing
print(f"Shape: {conv_data.data.shape}")  # (20283769, 368)
print(f"Timestamps: {len(conv_data.timestamps)}")

# Sampling rate
dt = np.diff(conv_data.timestamps[:100]).mean()
fs = 1.0 / dt  # ~1000 Hz

# Get convolved signal for one unit over full session
unit_convolved = conv_data.data[:, unit_id]  # (20283769,)

# Get a time window
t_start, t_end = 100.0, 200.0  # seconds
idx_start = np.searchsorted(conv_data.timestamps, t_start)
idx_end = np.searchsorted(conv_data.timestamps, t_end)
window_signal = conv_data.data[idx_start:idx_end, unit_id]
```

---

## Brain Area Mapping (Session 230823 Example)

### Electrodes by Area

| Brain Area | N Channels | N Units | Example Channel IDs |
|------------|-----------|---------|------------------|
| FEF | 128 | 156 | 0–127 |
| V1, V2, V3 | 128 | 112 | 128–255 |
| MT, MST | 128 | 100 | 256–383 |

### Identifying Units by Area

```python
# Get all FEF units
unit_areas = []
for unit_id, row in units_df.iterrows():
    peak_ch = int(float(row['peak_channel_id']))
    if peak_ch < len(elec_df):
        location = elec_df.iloc[peak_ch]['location']
    else:
        location = 'UNKNOWN'
    unit_areas.append((unit_id, location))

# Filter for FEF
fef_units = [uid for uid, area in unit_areas if area == 'FEF']
print(f"FEF units: {fef_units}")  # [0, 1, 2, ..., 155]
```

---

## Session-Specific Neural Data

### Session 230823 (FEF Session)

| Property | Value |
|----------|-------|
| **Total units** | 368 |
| **FEF units** | 156 |
| **Recording duration** | 20,283.77 seconds (~5.6 hours) |
| **Sampling rate** | 1000 Hz (convolved) |
| **Electrodes** | 384 channels (3 probes × 128) |
| **Correct P1 events** | 937 (across all conditions) |

### Available Files with FEF

1. `sub-C31o_ses-230823_rec.nwb` ← Primary reference
2. `sub-C31o_ses-230831_rec.nwb`

---

## Spike Data Extraction Pattern

### Raw Spike Times
```python
# Get sparse spike times for one unit
spike_times = units_df.iloc[unit_id]['spike_times']

# Filter to a time window
t_min, t_max = 100.0, 200.0
spikes_in_window = spike_times[(spike_times >= t_min) & (spike_times <= t_max)]
```

### Convolved Spike Rate (Recommended for Aligned Analysis)
```python
# Get convolved signal for a time window
conv_data = nwb.processing['convolved_spike_train']['convolved_spike_train_data']

t_start = 100.0
t_end = 200.0
idx_start = np.searchsorted(conv_data.timestamps, t_start)
idx_end = np.searchsorted(conv_data.timestamps, t_end)

# Extract for multiple units
for unit_id in fef_units:
    unit_signal = conv_data.data[idx_start:idx_end, unit_id]
    # unit_signal shape: (idx_end - idx_start,)
```

---

## Generalized Extraction Function Pattern

```python
def extract_neural_data_aligned(nwb, onset_times, unit_ids, 
                                 time_pre=0.25, time_post=1.75,
                                 data_source='convolved'):
    """
    Extract aligned neural data around event onsets.
    
    Args:
        nwb: NWBFile object
        onset_times: Array of event times (seconds from session start)
        unit_ids: List of unit IDs to extract
        time_pre: Seconds before onset
        time_post: Seconds after onset
        data_source: 'convolved' (default) or 'raw_spikes'
    
    Returns:
        np.ndarray: (n_events, n_timepoints, n_units)
    """
    
    if data_source == 'convolved':
        conv_data = nwb.processing['convolved_spike_train']['convolved_spike_train_data']
        timestamps = conv_data.timestamps
        data = conv_data.data
        
        epochs = []
        for onset in onset_times:
            idx_start = np.searchsorted(timestamps, onset - time_pre)
            idx_end = np.searchsorted(timestamps, onset + time_post)
            
            # Extract for all requested units
            epoch = data[idx_start:idx_end, unit_ids]
            epochs.append(epoch)
        
        return np.array(epochs)
    
    else:
        raise ValueError(f"Unknown data_source: {data_source}")
```

---

## References

- **NWB specification**: https://nwb-overview.readthedocs.io/
- **PyNWB documentation**: https://pynwb.readthedocs.io/
- **Session overview**: See `nwb-data-oglo-session-by-session-table.md`
- **Event structure**: See `nwb_event_structure.md`
