# NWB Atlas for Omission Predictive Routing Dataset

A comprehensive, implementation-ready reference for navigating and extracting behavioral events, LFP signals, laminar information, and single-unit activities from Neurodata Without Borders (NWB) files in the V1-PFC Predictive Routing project.

---

## 0. Getting P1-Correct Onsets for a Condition Group

To align neural data to trials, we need correct P1 stimulus onset times. P1 is the first stimulus presentation in the trial sequence.
* **Anchor Identification:** Filter rows in `nwb.intervals['omission_glo_passive']` where `correct == 1.0` and `stimulus_number == 2.0` (which refers to the P1 stimulus).
* **Condition Mapping:** Condition numbers ($1 \text{ to } 50$) map to 12 canonical condition groups (e.g., `AAAB`, `AXAB`, `AAXB`, `AAAX`, etc.) using constants defined in [constants.py](file:///D:/workspace/omission/src/analysis/contracts/constants.py).

### Implementation

```python
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO
from src.analysis.contracts.constants import CONDITION_LABEL_TO_NUMBERS

def get_p1_correct_onsets(nwb_path: str, condition_group: str) -> np.ndarray:
    """
    Extracts correct P1 onset times (seconds) for a specific condition group.
    
    Args:
        nwb_path: Absolute or relative path to the NWB file.
        condition_group: Canonical label (e.g., 'AAAB', 'AAXB', 'AAAX', 'RRRR').
        
    Returns:
        np.ndarray: Onset times in seconds.
    """
    if condition_group not in CONDITION_LABEL_TO_NUMBERS:
        raise ValueError(f"Unknown condition group: {condition_group}. "
                         f"Choose from: {list(CONDITION_LABEL_TO_NUMBERS.keys())}")
                         
    allowed_codes = CONDITION_LABEL_TO_NUMBERS[condition_group]
    
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        intervals_df = nwb.intervals['omission_glo_passive'].to_dataframe()
        
        # Boolean filtering
        correct_mask = intervals_df['correct'] == 1.0
        p1_mask = intervals_df['stimulus_number'] == 2.0
        condition_mask = intervals_df['task_condition_number'].isin(allowed_codes)
        
        # Combined binary filter
        matched = correct_mask & p1_mask & condition_mask
        onsets = intervals_df.loc[matched, 'start_time'].values
        
        return onsets

# Example Usage:
# onsets = get_p1_correct_onsets("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb", "AAXB")
# print(f"Found {len(onsets)} correct P1 events for AAXB")
```

---

## 1. LFP Epoching & Probe-to-Area Identification

LFP recording channels are split across multiple high-density linear probes. Each probe spans specific cortical regions.
1. **Identify Electrodes & Brain Areas:** Filter the `nwb.electrodes` table to group channels by probe identifier (e.g., `probeA`, `probeB`, `probeC`) and retrieve their anatomical location (e.g., `FEF`, `V1`, `PFC`). Apply the alias mapping (such as resolving `DP` to `V4`).
2. **Epoch LFP Data:** Locate the raw/downsampled LFP acquisition series, calculate sample indices for pre/post-onset window boundaries, and extract the LFP tensor of shape `(Trials, Channels, Samples)` for that probe.

### Implementation

```python
def extract_probe_lfp_epochs(nwb_path: str, onsets: np.ndarray, probe_name: str, 
                             time_pre: float = 1.0, time_post: float = 4.0) -> tuple[np.ndarray, str, list[int]]:
    """
    Extracts LFP epochs for a single probe and identifies its brain area.
    
    Returns:
        tuple containing:
            - lfp_epochs: np.ndarray of shape (n_trials, n_channels, n_samples)
            - area_name: resolved anatomical location (e.g., 'FEF', 'V1')
            - channel_ids: list of original channel indices in the NWB file
    """
    from src.analysis.contracts.constants import AREA_ALIASES
    
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        
        # 1. Identify channels belonging to this probe
        elec_df = nwb.electrodes.to_dataframe()
        probe_mask = elec_df['probe'] == probe_name
        probe_channels = elec_df[probe_mask]
        
        if probe_channels.empty:
            raise ValueError(f"No channels found for probe: {probe_name}")
            
        channel_ids = probe_channels.index.tolist()
        
        # Identify and clean area location
        raw_location = probe_channels['location'].iloc[0]
        area_name = AREA_ALIASES.get(raw_location, raw_location)
        
        # 2. Extract LFP Time Series
        lfp_key = None
        for key in nwb.acquisition.keys():
            if 'lfp' in key.lower():
                lfp_key = key
                break
        if not lfp_key:
            raise ValueError("No LFP dataset found in acquisition.")
            
        lfp_series = nwb.acquisition[lfp_key]
        fs = int(lfp_series.rate)
        
        # Calculate sample offsets
        samples_pre = int(time_pre * fs)
        samples_post = int(time_post * fs)
        total_samples = samples_pre + samples_post
        
        lfp_data = lfp_series.data  # Handle via memory mapping if huge
        timestamps = lfp_series.timestamps[:]
        
        epochs = []
        for t_onset in onsets:
            idx = np.searchsorted(timestamps, t_onset)
            start_idx = idx - samples_pre
            end_idx = idx + samples_post
            
            # Bound checks
            pad_left = 0
            pad_right = 0
            if start_idx < 0:
                pad_left = -start_idx
                start_idx = 0
            if end_idx > len(timestamps):
                pad_right = end_idx - len(timestamps)
                end_idx = len(timestamps)
                
            # Extract only the channels belonging to the requested probe
            epoch = lfp_data[start_idx:end_idx, channel_ids]
            
            # Pad with NaN at session boundaries
            if pad_left > 0 or pad_right > 0:
                epoch = np.pad(epoch, ((pad_left, pad_right), (0, 0)), 
                               mode='constant', value=np.nan)
                               
            epochs.append(epoch.T)  # Transpose to (Channels, Samples)
            
        return np.array(epochs), area_name, channel_ids
```

---

## 2. Laminar Identification: Calculating vFLIP2 Spectrolaminar Motifs

The **vFLIP2** spectrolaminar mapping method (adapted from Mendoza-Halliday et al.) determines cortical layering boundaries using LFP power profiles.
* **Spectral Signatures:** Superficial layers exhibit strong power in the **Gamma band (35–80 Hz)**, whereas deep layers dominate in the **Alpha/Beta band (8–30 Hz)**.
* **Crossover Point:** The boundary between middle (L4) and deep layers is identified by the channel index where Alpha/Beta power crosses over and exceeds Gamma power.

### Implementation

```python
from scipy.signal import welch
from scipy.ndimage import gaussian_filter1d

def compute_vflip2_crossover(lfp_epochs_probe: np.ndarray, fs: float = 1000.0) -> float:
    """
    Computes depth-resolved PSD profiles and identifies the L4 crossover channel.
    
    Args:
        lfp_epochs_probe: np.ndarray of shape (Trials, Channels, Samples)
        fs: Sampling rate of LFP data.
        
    Returns:
        float: Interpolated channel index corresponding to the L4 crossover.
    """
    n_trials, n_chans, n_samples = lfp_epochs_probe.shape
    
    # Define frequency bands
    BANDS = {'alpha_beta': (8, 30), 'gamma': (35, 80)}
    psd_profiles = {band: np.zeros(n_chans) for band in BANDS}
    
    # 1. Compute PSD channel-by-channel
    for ch in range(n_chans):
        ch_data = lfp_epochs_probe[:, ch, :]
        f, pxx_trials = welch(ch_data, fs=fs, nperseg=512, axis=-1)
        mean_pxx = np.nanmean(pxx_trials, axis=0)
        
        for band_name, (f_min, f_max) in BANDS.items():
            mask = (f >= f_min) & (f <= f_max)
            psd_profiles[band_name][ch] = np.nanmean(mean_pxx[mask])
            
    # 2. Smooth profiles spatially
    for band_name in psd_profiles:
        nan_mask = np.isnan(psd_profiles[band_name])
        if not np.all(nan_mask):
            smoothed = gaussian_filter1d(np.nan_to_num(psd_profiles[band_name]), sigma=2.0)
            psd_profiles[band_name][~nan_mask] = smoothed[~nan_mask]
            
    # 3. Find Crossover
    ab = psd_profiles['alpha_beta']
    ga = psd_profiles['gamma']
    
    # Normalize profiles to 0-1
    ab_norm = ab / (np.nanmax(ab) + 1e-12)
    ga_norm = ga / (np.nanmax(ga) + 1e-12)
    
    diff = ga_norm - ab_norm
    crossover_idx = np.nan
    
    # Zero-crossing detector (Gamma > Alpha/Beta superficially -> Alpha/Beta > Gamma deeply)
    for i in range(len(diff) - 1):
        if diff[i] > 0 and diff[i+1] < 0:
            crossover_idx = i + (0 - diff[i]) / (diff[i+1] - diff[i])
            break
            
    return crossover_idx
```

---

## 3. Single-Unit Discovery, Quality Metrics, and Waveforms

Single-unit sorting metadata and waveform shapes reside in `nwb.units`. 
* **Quality Filters:** Vetted stable-plus analysis requires filtering units based on:
  - `snr > 0.8` (Signal-to-noise ratio)
  - `presence_ratio > 0.9` (Percentage of session active)
  - `isi_violations < 0.05` (Refractory period violation fraction)
* **Electrode Association:** The unit is mapped to its primary recording channel via `peak_channel_id`.

### Implementation

```python
def get_vetted_units_metadata(nwb_path: str) -> pd.DataFrame:
    """
    Retrieves and filters units according to quality controls.
    """
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        units_df = nwb.units.to_dataframe()
        elec_df = nwb.electrodes.to_dataframe()
        
        # Extract area location for each unit based on peak channel
        unit_areas = []
        for idx, row in units_df.iterrows():
            peak_ch = int(float(row['peak_channel_id']))
            unit_areas.append(elec_df.iloc[peak_ch]['location'])
        units_df['location'] = unit_areas
        
        # Apply vetting filter (Stable-Plus Vetting)
        quality_mask = (
            (units_df['snr'] > 0.8) &
            (units_df['presence_ratio'] > 0.9) &
            (units_df['isi_violations'] < 0.05)
        )
        
        return units_df[quality_mask]

def plot_unit_waveform(nwb_path: str, unit_id: int):
    """
    Plots the mean waveform trace for a specified unit.
    """
    import matplotlib.pyplot as plt
    
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        mean_waveform = nwb.units['waveform_mean'][unit_id]
        
        plt.figure(figsize=(5, 3))
        plt.plot(mean_waveform, color='#CFB87C', linewidth=2.5)  # Gold theme
        plt.title(f"Unit {unit_id} Mean Waveform")
        plt.xlabel("Samples (at sorting rate)")
        plt.ylabel("Amplitude (uV)")
        plt.grid(True, alpha=0.3)
        plt.show()
```

---

## 4. Standardized Trial-Channel-Sample Tensor Extraction & Trace Plotting

To analyze LFP, single-unit firing rates (convolved spikes), and MUAe signals concurrently, extract them into matching **`(Trials, Channels/Units, Samples)`** tensors with identical time-alignments:
* **Timebase Alignment:** $1000\text{ ms}$ pre-onset to $4000\text{ ms}$ post-onset of P1 ($5000\text{ samples}$ total at $1000\text{ Hz}$).
* **LFP:** Derived from acquisition datasets.
* **Single Units:** Derived from convolved spike rate matrices in `nwb.processing['convolved_spike_train']`.
* **MUAe:** Derived from `nwb.acquisition['probe_X_muae']` when available.

### Implementation

```python
def extract_standardized_tensors(nwb_path: str, onsets: np.ndarray, unit_ids: list[int],
                                 probe_name: str, channels: list[int]) -> dict[str, np.ndarray]:
    """
    Extracts LFP and convolved spike rate tensors aligned identically.
    Resulting tensors have shape: (Trials, Channels/Units, 5000)
    """
    tensors = {}
    time_pre, time_post = 1.0, 4.0  # 1000ms pre, 4000ms post
    
    # 1. Extract LFP
    lfp_epochs, _, _ = extract_probe_lfp_epochs(nwb_path, onsets, probe_name, time_pre, time_post)
    tensors['lfp'] = lfp_epochs  # (Trials, Channels, 5000)
    
    # 2. Extract Convolved Spike Rates
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        conv_module = nwb.processing['convolved_spike_train']
        conv_series = conv_module['convolved_spike_train_data']
        timestamps = conv_series.timestamps
        conv_data = conv_series.data
        
        fs = 1000  # Convolved spikes are downsampled to 1000Hz
        samples_pre = int(time_pre * fs)
        samples_post = int(time_post * fs)
        
        spk_epochs = []
        for t_onset in onsets:
            idx = np.searchsorted(timestamps, t_onset)
            start_idx = idx - samples_pre
            end_idx = idx + samples_post
            
            # Window slice
            epoch = conv_data[start_idx:end_idx, unit_ids]  # (Samples, Units)
            spk_epochs.append(epoch.T)  # Transpose to (Units, Samples)
            
        tensors['spikes'] = np.array(spk_epochs)  # (Trials, Units, 5000)
        
    return tensors
```

---

## 5. Raster Plotting: Single-Trial & Probe-Wide Multi-Unit Rasters

Spike raster plots are extracted from sparse spike timings in `nwb.units['spike_times']`.
* **Single-Unit Trial Raster:** Shows spike occurrences across all trials aligned to P1.
* **Multi-Unit Co-occurrence Raster:** Shows spikes of all units on the same probe during a single trial.

### Implementation

```python
import matplotlib.pyplot as plt

def plot_single_unit_raster(nwb_path: str, unit_id: int, onsets: np.ndarray, 
                            time_pre: float = 1.0, time_post: float = 4.0):
    """
    Plots spike rasters for a single unit across multiple trials.
    """
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        spike_times = nwb.units['spike_times'][unit_id]
        
        plt.figure(figsize=(10, 5))
        for trial_idx, t_onset in enumerate(onsets):
            t_start = t_onset - time_pre
            t_end = t_onset + time_post
            
            # Filter spikes in window
            trial_spikes = spike_times[(spike_times >= t_start) & (spike_times <= t_end)]
            # Align relative to onset
            aligned_spikes = (trial_spikes - t_onset) * 1000.0  # to ms
            
            plt.vlines(aligned_spikes, trial_idx - 0.4, trial_idx + 0.4, 
                       colors='#9400D3', linewidth=1.2)  # Violet theme
                       
        plt.xlim(-time_pre * 1000.0, time_post * 1000.0)
        plt.ylim(-1, len(onsets))
        plt.title(f"Single-Unit Raster (Unit {unit_id}) aligned to P1 Onset")
        plt.xlabel("Time relative to P1 (ms)")
        plt.ylabel("Trials")
        plt.grid(True, alpha=0.3)
        plt.show()

def plot_multi_unit_single_trial_raster(nwb_path: str, unit_ids: list[int], t_onset: float,
                                        time_pre: float = 1.0, time_post: float = 4.0):
    """
    Plots spike rasters of multiple units for a single trial window.
    """
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        
        plt.figure(figsize=(10, 6))
        for unit_y_idx, unit_id in enumerate(unit_ids):
            spike_times = nwb.units['spike_times'][unit_id]
            t_start = t_onset - time_pre
            t_end = t_onset + time_post
            
            trial_spikes = spike_times[(spike_times >= t_start) & (spike_times <= t_end)]
            aligned_spikes = (trial_spikes - t_onset) * 1000.0
            
            plt.vlines(aligned_spikes, unit_y_idx - 0.4, unit_y_idx + 0.4, 
                       colors='#CFB87C', linewidth=1.5)
                       
        plt.xlim(-time_pre * 1000.0, time_post * 1000.0)
        plt.ylim(-1, len(unit_ids))
        plt.title("Multi-Unit Raster - Single Trial Window")
        plt.xlabel("Time relative to P1 (ms)")
        plt.ylabel("Unit ID (relative)")
        plt.grid(True, alpha=0.3)
        plt.show()
```

---

## 6. Integrating Unit-to-LFP Relationships, Peak Channels, and Putative Layers

To link single units to their laminar sources:
1. **Find Peak Channel:** Query `nwb.units['peak_channel_id']` for the unit.
2. **Retrieve Crossover Point:** Compute the L4 crossover boundary index for the probe.
3. **Determine Putative Layer:** Classify the unit's depth index (relative to L4 crossover) into `Superficial (L2/3)`, `Middle (L4)`, or `Deep (L5/L6)`.
4. **Relate to LFP:** Correlate unit spiking activity with local LFP oscillations from the peak channel.

### Implementation

```python
def map_unit_to_laminar_compartment(nwb_path: str, unit_id: int, probe_lfp_epochs: np.ndarray, 
                                     probe_name: str) -> dict:
    """
    Determines the peak channel, laminar layer, and peak channel LFP trace for a single unit.
    """
    crossover_idx = compute_vflip2_crossover(probe_lfp_epochs)
    
    with NWBHDF5IO(nwb_path, 'r', load_namespaces=True) as io:
        nwb = io.read()
        units_df = nwb.units.to_dataframe()
        elec_df = nwb.electrodes.to_dataframe()
        
        # Get peak channel
        peak_ch_id = int(float(units_df.loc[unit_id, 'peak_channel_id']))
        
        # Filter electrode list for the unit's probe to determine relative index
        probe_chans = elec_df[elec_df['probe'] == probe_name].sort_values(by='depth')
        relative_idx = probe_chans.index.get_loc(peak_ch_id)
        
        # Assign layer based on distance to L4 crossover channel
        if relative_idx < crossover_idx - 1:
            layer = 'L2/3 (Superficial)'
        elif relative_idx <= crossover_idx + 1:
            layer = 'L4 (Middle)'
        else:
            layer = 'L5/L6 (Deep)'
            
        return {
            'unit_id': unit_id,
            'peak_channel_global': peak_ch_id,
            'peak_channel_relative_probe_idx': relative_idx,
            'crossover_channel_idx': crossover_idx,
            'putative_layer': layer,
            'location': elec_df.loc[peak_ch_id, 'location']
        }
```
