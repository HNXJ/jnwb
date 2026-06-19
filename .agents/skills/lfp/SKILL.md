---
name: lfp
description: >
  LFP preprocessing, spectral band-power extraction, coherence, spike-field
  coupling (SFC/PPC), and spectrolaminar (vFLIP2) laminar mapping for the
  Omission project. All operations on Stable-Plus channels only.
---

# Skill: lfp — LFP Signal Processing Pipeline

## Purpose
Complete reference for LFP preprocessing, frequency-band power, coherence
between areas, SFC/PPC computations, and spectrolaminar layer mapping.
Any agent performing LFP work should load this skill first.

---

## 1. Imports and Constants

```python
from src.analysis.lfp.lfp_preproc   import preprocess_lfp, bandpass_filter
from src.analysis.lfp.lfp_tfr       import compute_tfr, n_cycles_for_freqs
from src.analysis.lfp.lfp_constants import (
    FS_LFP,                          # 1000.0 Hz
    BANDS,                           # {"Theta":(3,7), "Alpha":(8,12), ...}
    CANONICAL_AREAS,
    SEQUENCE_TIMING_MS,
    OMISSION_ANALYSIS_WINDOWS_MS,
    CONDITION_MAP,
    GOLD, VIOLET, GRAY, WHITE        # aesthetic palette
)
from src.analysis.lfp.sfc           import compute_sfc
from src.analysis.lfp.lfp_laminar_mapping import compute_spectrolaminar_profiles, get_laminar_crossover
from src.analysis.coherence.coherence    import compute_lfp_lfp_coherence
```

---

## 2. Preprocessing

```python
# lfp_data: (channels, time) in µV, sampled at FS_LFP = 1000 Hz
from src.analysis.lfp.lfp_preproc import preprocess_lfp

lfp_clean = preprocess_lfp(
    lfp_data,          # (C, T) raw µV
    fs=FS_LFP,
    notch_hz=60.0,     # remove line noise
    highpass_hz=0.5,   # remove DC drift
    lowpass_hz=300.0,  # anti-alias
    method="fir",
)
# Returns (C, T) array in same units
```

---

## 3. Epoch Cutting

```python
import numpy as np

def cut_epochs(lfp_clean, onsets_sec, pre_ms=-1000, post_ms=4000, fs=1000.0):
    """
    Cut LFP epochs around p1 onsets.
    Returns (n_trials, n_channels, n_timepoints).
    pre_ms  : samples before onset (negative = before)
    post_ms : samples after onset
    """
    pre_samp  = int(abs(pre_ms)  * fs / 1000)
    post_samp = int(abs(post_ms) * fs / 1000)
    n_channels, n_total = lfp_clean.shape
    epochs = []
    for t_onset in onsets_sec:
        idx = int(round(t_onset * fs))
        t0, t1 = idx - pre_samp, idx + post_samp
        if t0 < 0 or t1 > n_total:
            continue
        epochs.append(lfp_clean[:, t0:t1])
    return np.stack(epochs, axis=0)  # (trials, channels, time)
```

Standard window: **-1000 ms to +4000 ms** from p1 onset (5001 samples at 1 kHz).

---

## 4. Frequency Band Power

```python
from scipy.signal import welch

def compute_band_power(epoch, fs=1000.0, bands=BANDS):
    """
    epoch: (time,) or (channels, time)
    Returns dict: band_name → power (µV²/Hz, averaged over [fmin, fmax])
    """
    if epoch.ndim == 1:
        epoch = epoch[np.newaxis, :]
    result = {}
    f, psd = welch(epoch, fs=fs, nperseg=min(256, epoch.shape[-1]), axis=-1)
    for band, (fmin, fmax) in bands.items():
        mask = (f >= fmin) & (f <= fmax)
        result[band] = float(np.mean(psd[:, mask]))
    return result
```

**Canonical bands** (from `BANDS`):
| Band | Range |
|------|-------|
| Theta | 3–7 Hz |
| Alpha | 8–12 Hz |
| l-beta | 14–20 Hz |
| h-beta | 20–30 Hz |
| Gamma_L | 32–80 Hz |
| Gamma_H | 80–200 Hz |

---

## 5. LFP–LFP Coherence Between Areas

```python
from src.analysis.coherence.coherence import compute_lfp_lfp_coherence

# lfp_a, lfp_b: (trials, time) — single-channel epochs from two areas
result = compute_lfp_lfp_coherence(lfp_a, lfp_b, fs=FS_LFP)
freqs  = result["frequencies"]   # Hz array
coh    = result["coherence"]      # [0, 1] magnitude-squared coherence

# For multi-channel, pass (trials, channels, time) — function averages over trials
```

**Omission contexts for coherence analysis**:
- `p1` (stimulus): `(0, 531)` ms
- `d1` (ISI baseline): `(531, 1031)` ms
- `p2` omission window (AXAB/BXBA/RXRR): `(1031, 1562)` ms
- `p3` omission window (AAXB/BBXA/RRXR): `(2062, 2593)` ms
- `p4` omission window (AAAX/BBBX/RRRX): `(3093, 3624)` ms

---

## 6. Spike-Field Coherence / PPC

```python
from src.analysis.lfp.sfc import compute_sfc

# spike_times_sec: 1-D array of spike timestamps in seconds
# lfp_epoch: (time,) or (n_trials, time) LFP strip around the event
sfc_result = compute_sfc(
    spike_times_sec=spike_times,
    lfp_epoch=lfp_epoch,
    fs=FS_LFP,
    freqs=np.arange(2, 100),
)
ppc    = sfc_result["ppc"]     # Pairwise Phase Consistency array
freqs  = sfc_result["freqs"]   # Hz
```

---

## 7. Spectrolaminar (vFLIP2) Laminar Mapping

```python
from src.analysis.lfp.lfp_laminar_mapping import (
    compute_spectrolaminar_profiles,
    get_laminar_crossover,
)

# lfp_data_probe: (n_channels, n_time) for a single probe
profiles = compute_spectrolaminar_profiles(lfp_data_probe, fs=FS_LFP)
# profiles: {"gamma": (n_channels,), "alpha_beta": (n_channels,)}

crossover_result = get_laminar_crossover(lfp_data_probe, fs=FS_LFP)
l4_channel   = crossover_result["crossover"]       # float channel index of L4
orientation  = crossover_result["orientation"]     # "normal" or "inverted"
```

**Interpretation**:
- Channels **above** L4 crossover → **Superficial (L2/3)**
- Channels **below** L4 crossover → **Deep (L5/L6)**
- Rule: Gamma peaks superficially; Alpha/Beta peaks deep.

---

## 8. dB Normalization

```python
def normalize_db(power, baseline_mask):
    """
    power: (freqs, time)
    baseline_mask: boolean array over time axis
    Returns dB-normalized (freqs, time)
    """
    baseline_mean = np.mean(power[:, baseline_mask], axis=1, keepdims=True)
    return 10.0 * np.log10(power / (baseline_mean + 1e-30))
```

Baseline window: **-500 ms to 0 ms** (`fx` epoch) from p1 onset.

---

## 9. Key Files

| File | Role |
|------|------|
| [lfp_constants.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_constants.py) | All constants, bands, timing |
| [lfp_preproc.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_preproc.py) | Filtering, preprocessing |
| [lfp_pipeline.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_pipeline.py) | High-level pipeline runner |
| [lfp_tfr.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_tfr.py) | Multitaper TFR engine |
| [sfc.py](file:///D:/workspace/omission/src/analysis/lfp/sfc.py) | SFC / PPC |
| [coherence.py](file:///D:/workspace/omission/src/analysis/coherence/coherence.py) | LFP–LFP coherence |
| [lfp_laminar_mapping.py](file:///D:/workspace/omission/src/analysis/lfp/lfp_laminar_mapping.py) | vFLIP2 spectrolaminar |
| [connectivity.py](file:///D:/workspace/omission/src/analysis/lfp/connectivity.py) | Cross-area connectivity |
