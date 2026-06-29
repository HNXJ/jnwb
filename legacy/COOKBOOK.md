# jnwb Cookbook

> **Session:** `sub-C31o_ses-230823_rec.nwb` | FEF probe (probeA, 128 ch, 1 kHz LFP)
> **Anchor unit:** Unit 22 | FEF | Superficial | stable-plus | 20.1 Hz
> **Figures:** `outputs/publication_visual_review/jnwb_cookbook/`

Working code + real output for every major `jnwb` function category.

---

## Table of Contents

1. [Session Loading](#1-session-loading)
2. [Unit Access and Metadata](#2-unit-access-and-metadata)
3. [Spiking Analysis](#3-spiking-analysis)
4. [LFP - Trial-Averaged Spectrogram](#4-lfp---trial-averaged-spectrogram)
5. [LFP - Band-Power Traces](#5-lfp---band-power-traces)
6. [Population Analysis](#6-population-analysis)
7. [Pie Charts](#7-pie-charts)
8. [Statistics](#8-statistics)
9. [Diagnostics](#9-diagnostics)
10. [API Signatures and Known Stubs](#10-api-signatures-and-known-stubs)
11. [NWB Schema Notes](#11-nwb-schema-notes)

---

## 1. Session Loading

```python
import sys
sys.path.insert(0, "D:/workspace/omission")
import jnwb as oa

# Single session
session = oa.read("D:/analysis/nwb/sub-C31o_ses-230823_rec.nwb")

# All sessions in a directory
sessions = oa.batch_read("D:/analysis/nwb", pattern="*.nwb")

# Summary
info = session.info()
session.summary()
```

**`session.info()` fields (ses-230823):**

| Key | Value |
|---|---|
| `session_id` | `sub-C31o_ses-230823` |
| `n_units` | 368 total |
| `n_stable_plus` | 221 (109 FEF) |
| `areas` | `["FEF"]` |
| `lfp_probes` | `["probe_0_lfp", "probe_1_lfp", "probe_2_lfp"]` |

---

## 2. Unit Access and Metadata

```python
from jnwb import find_units, unit_channel_mapping
from jnwb import UnitAnalyzer
import numpy as np

# --- DataFrame access via session ---
all_units   = session.get_units()
fef_units   = session.get_units(area="FEF")
stable_fef  = session.get_units(area="FEF", quality="stable_plus")  # n=109
high_fr_fef = session.get_units(area="FEF", firing_rate_range=(10, 200))

# --- Canonical function ---
found = find_units(session, quality="stable_plus", area="FEF")
# -> DataFrame, 104 units (default FR floor applies)
# Index = unit_id (int); access via: found.loc[22]

# --- Quality metrics per unit ---
# NOTE: unit_quality_scores() is a stub that raises NotImplementedError.
# Use UnitAnalyzer directly:
row = stable_fef.loc[22]
spk = np.array(row["spike_times"])
metrics = UnitAnalyzer.quality_metrics(
    spike_times=spk,
    waveform_duration_us=float(row["waveform_duration"]),
    firing_rate=float(row["firing_rate"])
)
# -> {"firing_rate_hz": 20.1, "waveform_duration_us": ..., "is_single_unit": True}

# --- Channel mapping ---
chan_map = unit_channel_mapping(session)
# -> DataFrame: unit_id, channel_id, area, layer
```

**Unit DataFrame column reference:**

| Column | Type | Notes |
|---|---|---|
| `firing_rate` | float | Mean spike rate (Hz) |
| `snr` | float | Signal-to-noise ratio |
| `waveform_duration` | float | Peak-to-trough duration (us) |
| `presence_ratio` | float | Fraction of recording with activity |
| `stable_plus` | bool | Gate: is_stable=True, FR>1, SNR>0.8, presence>=0.98 |
| `spike_times` | list | Spike timestamps in seconds |
| `area` | str | Recording area (FEF, MT, V1, ...) |
| `layer` | str | Superficial, Deep, or Unresolved |
| `quality` | str | stable_plus / stable / mua / unstable |

> **Index name is `id` (integer).** Access: `units_df.loc[unit_id]`
>
> **stable_plus filter:** use `units[units["stable_plus"] == True]`
> (avoid bare boolean due to pandas NA semantics)

---

## 3. Spiking Analysis

```python
from pynwb import NWBHDF5IO
import numpy as np

# --- Load trial onsets ---
with NWBHDF5IO(nwb_path, "r") as io:
    nwb = io.read()
    idf = nwb.intervals["omission_glo_passive"].to_dataframe()

# CRITICAL: task_condition_number and stimulus_number are stored as string floats.
# Always cast before filtering.
idf["_cond"] = idf["task_condition_number"].astype(float)
idf["_stim"] = idf["stimulus_number"].astype(float)

aaxb = idf[(idf["_cond"] == 4.0) & (idf["_stim"] == 3.0)]  # n=80  AAXB p3
aaab = idf[(idf["_cond"].isin([1.0, 2.0])) & (idf["_stim"] == 3.0)]  # n=484 AAAB p3

# --- Spike retrieval ---
spk = np.array(stable_fef.loc[22]["spike_times"])

# --- Raster ---
def make_raster(spk, onsets, pre=-0.5, post=1.0):
    return [spk[(spk >= t + pre) & (spk < t + post)] - t for t in onsets]

raster = make_raster(spk, aaxb["start_time"].values)
# -> list of 80 arrays; each = spike times relative to event onset (seconds)

# --- PSTH ---
def make_psth(raster, pre=-0.5, post=1.0, bin_ms=20):
    bs   = bin_ms / 1000
    bins = np.arange(pre, post + bs, bs)
    mat  = np.array([np.histogram(tr, bins=bins)[0] for tr in raster], dtype=float)
    return bins[:-1] + bs/2, mat.mean(0)/bs, mat.std(0)/bs/np.sqrt(len(mat))

bin_centers, rate_hz, sem = make_psth(raster)
# rate_hz: array(75,) -- mean firing rate per bin in Hz

# --- Autocorrelogram ---
def make_acg(spk, max_lag=0.1, bin_ms=1):
    bs   = bin_ms / 1000
    bins = np.arange(-max_lag, max_lag + bs, bs)
    cnt  = np.zeros(len(bins) - 1)
    for si in spk:
        d = spk - si
        d = d[(d != 0) & (np.abs(d) <= max_lag)]
        cnt += np.histogram(d, bins=bins)[0]
    return (bins[:-1] + bs/2) * 1000, cnt / max(len(spk), 1)

lag_ms, acg = make_acg(spk)

# --- Via canonical jnwb functions (where implemented) ---
from jnwb import raster_plot, psth_analysis, autocorrelogram, compute_response_metrics

raster_result = raster_plot(session, unit_id=22, condition="AAXB", phase=3,
                             window_ms=(-500, 1000))
psth_result   = psth_analysis(session, unit_id=22, condition="AAXB", phase=3,
                               bin_size_ms=20)
acg_result    = autocorrelogram(session, unit_id=22, max_lag_ms=100)

metrics = compute_response_metrics(spk, aaxb["start_time"].values,
                                   baseline_window=(-500, 0),
                                   response_window=(0, 500))
```

**Example output - Unit 22 (FEF | Superficial | 20.1 Hz):**

![Raster + PSTH + ACG](outputs/publication_visual_review/jnwb_cookbook/01_spiking_raster_psth_acg.png)

*Top: spike rasters aligned to p3 slot onset (white dashed = t=0).
Bottom: mean PSTH +/- SEM at 20 ms bins.
Right: autocorrelogram — refractory trough confirms single-unit isolation.*

---

## 4. LFP - Trial-Averaged Spectrogram

```python
from pynwb import NWBHDF5IO
import numpy as np
from scipy.signal import spectrogram

# Probe layout:
#   probe_0_lfp -> probeA -> FEF       (ch 0-127)
#   probe_1_lfp -> probeB -> MT, MST   (ch 128-255)
#   probe_2_lfp -> probeC -> V1/V2/V3  (ch 256-383)

with NWBHDF5IO(nwb_path, "r") as io:
    nwb    = io.read()
    lfp    = nwb.acquisition["probe_0_lfp"]   # FEF probe
    lfp_ts = np.array(lfp.timestamps)          # shape: (20_282_770,)
    # lfp.data shape: (20_282_770, 128)

    # Estimate fs from timestamps (lfp.rate is None for this session)
    fs = round(len(lfp_ts) / (lfp_ts[-1] - lfp_ts[0]))   # 1000 Hz

    CH    = 64       # mid-array FEF channel
    WIN_S = 0.5      # +/- 0.5 s around event

    specs = []
    for _, row in aaxb.iterrows():
        t0  = row["start_time"]
        i0  = np.searchsorted(lfp_ts, t0 - WIN_S)
        i1  = np.searchsorted(lfp_ts, t0 + WIN_S)
        sig = np.array(lfp.data[i0:i1, CH], dtype=float)
        sig -= sig.mean()
        npg = int(fs * 0.1)
        f, t, Sxx = spectrogram(sig, fs=fs, nperseg=npg, noverlap=int(npg * 0.75))
        t -= WIN_S                                # align to t=0
        fm = (f >= 2) & (f <= 100)
        specs.append(Sxx[fm])

    avg_power_db = 10 * np.log10(np.mean(specs, axis=0) + 1e-15)
```

> **fs = 1000 Hz** for ses-230823. Always estimate from timestamps,
> not from `lfp.rate` which may be `None`.

**Example output:**

![LFP Spectrogram](outputs/publication_visual_review/jnwb_cookbook/02_lfp_spectrogram.png)

*Left/Centre: trial-averaged power (dB) for AAXB and AAAB, Ch 64.
Right: difference (Omission - Standard in dB). Dashed = event onset.*

---

## 5. LFP - Band-Power Traces

```python
from scipy.signal import butter, filtfilt

def bandpass(sig, lo, hi, fs):
    b, a = butter(4, [lo/(fs/2), hi/(fs/2)], btype="band")
    return filtfilt(b, a, sig)

# Canonical bands
bands = [
    ("delta 1-4 Hz",   1,  4),
    ("beta 13-30 Hz",  13, 30),
    ("gamma 30-80 Hz", 30, 80),
]

CH = 64
for band_name, lo, hi in bands:
    trials = []
    for _, row in aaxb.iterrows():
        t0  = row["start_time"]
        i0  = np.searchsorted(lfp_ts, t0 - 0.5)
        i1  = np.searchsorted(lfp_ts, t0 + 1.0)
        sig = np.array(lfp.data[i0:i1, CH], dtype=float)
        sig -= sig.mean()
        power = bandpass(sig, lo, hi, fs) ** 2
        trials.append(power)
    min_len = min(len(t) for t in trials)
    mat   = np.array([t[:min_len] for t in trials])
    t_ms  = np.linspace(-500, 1000, min_len)
    mean  = mat.mean(0)
    sem   = mat.std(0) / np.sqrt(len(mat))

# Spike-Field Coupling
from jnwb import spectral
ppc = spectral.spike_field_ppc(spk, lfp_signal, sfreq=fs, band="beta")
# -> {"ppc": float, "mean_phase": float, "rayleigh_p": float}
```

**Example output:**

![LFP Band Power](outputs/publication_visual_review/jnwb_cookbook/03_lfp_band_power.png)

*Solid = Omission (AAXB), Dashed = Standard (AAAB), shading = +/- 1 SEM.*

---

## 6. Population Analysis

```python
from jnwb import compare_populations, population_by_area

all_sp = session.get_units(quality="stable_plus")
# n=221 stable-plus; FEF: n=109, mean FR=6.84 Hz, std=4.03 Hz

fef_fr = all_sp[all_sp["area"] == "FEF"]["firing_rate"].astype(float).values

# By area - full distribution
areas = sorted(all_sp["area"].unique())
fr_by_area = {a: all_sp[all_sp["area"] == a]["firing_rate"].astype(float).values
              for a in areas}

# Canonical comparison function
# NOTE: criteria area names must exactly match values in units DataFrame
comp = compare_populations(
    session,
    criteria1={"area": "FEF", "quality": "stable_plus"},
    criteria2={"area": "MT",  "quality": "stable_plus"},
    metric="firing_rate"
)
# Example result (ses-230823):
# {"n1": 109, "n2": 3, "mean1": 6.84, "mean2": 8.45,
#  "parametric": {"test": "independent_t_test", "pval": 0.497},
#  "significant_parametric": False}
# Note: ses-230823 has only n=3 MT units -> low statistical power

by_area = population_by_area(session, metric="firing_rate")
```

**Example output:**

![Population by Area](outputs/publication_visual_review/jnwb_cookbook/04_population_fr_by_area.png)

*Violins show full distribution; white bars = medians; dots = individual units.*

---

## 7. Pie Charts

```python
from jnwb import pie_charts

pies_area  = pie_charts(session, criteria={"quality": "stable_plus"}, by_area=True)
# -> {"counts": {"FEF": 109, "MT": 3, ...}, "total": 221}

pies_layer = pie_charts(session, criteria={"quality": "stable_plus"}, by_layer=True)

# Direct DataFrame (always reliable)
all_u    = session.get_units()
q_counts = all_u["quality"].value_counts()
```

**Example output:**

![Pie Charts](outputs/publication_visual_review/jnwb_cookbook/05_pie_charts.png)

*Left: all 368 units by quality tier. Right: 221 stable-plus units by area.*

---

## 8. Statistics

```python
from jnwb import StatisticalAnalysis
import numpy as np

sa = StatisticalAnalysis()

all_sp = session.get_units(quality="stable_plus")
fef_fr = all_sp[all_sp["area"] == "FEF"]["firing_rate"].astype(float).values  # n=109
mt_fr  = all_sp[all_sp["area"] == "MT"]["firing_rate"].astype(float).values   # n=3

# --- Two-group comparison ---
result = sa.compare_groups(fef_fr, mt_fr, paired=False)
# Real output from ses-230823:
# {
#   "n1": 109, "n2": 3,
#   "mean1": 6.844, "mean2": 8.455,
#   "parametric": {
#       "test": "independent_t_test",
#       "statistic": -0.681, "pval": 0.497, "effect_size": -0.399
#   },
#   "non_parametric": {"test": "mann_whitney_u", "statistic": 120.0, "pval": 0.458},
#   "significant_parametric": False,
#   "significant_nonparametric": False
# }

# --- Bootstrap CI ---
ci = sa.bootstrap_ci(fef_fr, statistic_func=np.mean, n_bootstrap=2000)
# {
#   "statistic": 6.844,
#   "parametric_ci": (6.078, 7.610),
#   "bootstrap_ci":  (6.106, 7.637),
#   "bootstrap_std": 0.396
# }

# --- Correlation (FR vs SNR, all stable-plus, n=221) ---
corr = sa.correlate(
    all_sp["firing_rate"].astype(float).values,
    all_sp["snr"].astype(float).values
)
# {
#   "n": 221,
#   "parametric":     {"test": "pearson_r",    "statistic": -0.063, "pval": 0.353},
#   "non_parametric": {"test": "spearman_rho", "statistic": -0.161, "pval": 0.016},
#   "significant_nonparametric": True   <- weak negative FR/SNR, Spearman only
# }

# --- Multi-group (ANOVA + Kruskal-Wallis) ---
groups = {a: all_sp[all_sp["area"] == a]["firing_rate"].astype(float).values
          for a in areas}
multi = sa.compare_multiple_groups(groups)

# --- Permutation test ---
perm = sa.permutation_test(fef_fr, mt_fr, n_permutations=5000)
# -> {"observed_difference": float, "pval": float, "significant": bool}
```

**Example output - FEF vs MT:**

![Statistics](outputs/publication_visual_review/jnwb_cookbook/06_statistics_comparison.png)

*Bar = mean +/- SEM; dots = individual units; bracket = t-test verdict.*

---

## 9. Diagnostics

```python
from jnwb import audit_session, electrode_inventory, compare_sessions

# IMPORTANT: audit_session and electrode_inventory take a FILE PATH string,
# not an OmissionSession object.
audit = audit_session(nwb_path)          # str path
elec  = electrode_inventory(nwb_path)    # str path (or list of paths)
# -> DataFrame: channel_id, area, layer, probe, depth_um

# unit_census_report: pass the units DataFrame, not the session
from jnwb import unit_census_report
census = unit_census_report(session.get_units())   # DataFrame, not session

# Cross-session comparison
session_b = oa.read("D:/analysis/nwb/sub-C31o_ses-230816_rec.nwb")
diff = compare_sessions(session, session_b)
```

---

## 10. API Signatures and Known Stubs

Functions in `jnwb/functions.py` that raise `NotImplementedError`:

| Stub function | Working alternative |
|---|---|
| `unit_quality_scores(session, unit_id)` | `UnitAnalyzer.quality_metrics(spk, ...)` |
| `tfr_trial_average(session, ...)` | `TFRAnalyzer.trial_average(...)` |
| `tfr_compare_conditions(session, ...)` | `TFRAnalyzer.compare_conditions(...)` |
| `tfr_correlate_areas(session, ...)` | `TFRAnalyzer.correlate_areas(...)` |
| `tfr_spectrolaminar(session, ...)` | `TFRAnalyzer.by_layer(...)` |
| `tfr_permutation_test(session, ...)` | `StatisticalAnalysis.permutation_test(...)` |
| `get_snr_analysis(session)` | `UnitAnalyzer.quality_metrics(...)` |

Functions expecting a **path string**, not a session:

| Function | Correct signature |
|---|---|
| `audit_session(x)` | `audit_session(nwb_path: str)` |
| `electrode_inventory(x)` | `electrode_inventory(nwb_path: str or list[str])` |
| `unit_census_report(x)` | `unit_census_report(units_df: DataFrame)` |

Functions confirmed working with `OmissionSession`:
`find_units`, `unit_channel_mapping`, `raster_plot`, `psth_analysis`,
`autocorrelogram`, `compute_response_metrics`, `compare_populations`,
`population_by_area`, `pie_charts`, `StatisticalAnalysis.compare_groups`,
`StatisticalAnalysis.bootstrap_ci`, `StatisticalAnalysis.correlate`,
`StatisticalAnalysis.permutation_test`

---

## 11. NWB Schema Notes

### Interval columns

| NWB column | dtype | Gotcha |
|---|---|---|
| `task_condition_number` | str ("4.0") | Cast to float before filtering |
| `stimulus_number` | str ("3.0") | Cast to float before filtering |
| `start_time` | float (seconds) | Trial/event onset |
| `is_omission` | bool | True for omission events |

### Condition -> task_condition_number

| Condition | _cond | Omission slot |
|---|---|---|
| AAAB | 1.0, 2.0 | None |
| AXAB | 3.0 | p2 |
| AAXB | 4.0 | p3 |
| AAAX | 5.0 | p4 |
| BBBA | 6.0, 7.0 | None |
| BXBA | 8.0 | p2 |
| BBXA | 9.0 | p3 |
| BBBX | 10.0 | p4 |
| RRRR | 11-26 | None |
| RXRR/RRXR/RRRX | 27-50 | Random |

### stimulus_number -> phase/slot

| _stim | Slot |
|---|---|
| 1.0 | Fixation |
| 2.0 | p1 |
| 3.0 | p2/p3 (omission slot, condition-dependent) |
| 4.0 | p3/p4 |
| 5.0 | p4 |

### LFP probe layout

| NWB key | Probe | Area | Channels | fs |
|---|---|---|---|---|
| `probe_0_lfp` | probeA | FEF | 0-127 | 1000 Hz |
| `probe_1_lfp` | probeB | MT, MST | 128-255 | 1000 Hz |
| `probe_2_lfp` | probeC | V1, V2, V3 | 256-383 | 1000 Hz |

```python
# Always estimate fs from timestamps (lfp.rate may be None)
fs = round(len(lfp_ts) / (lfp_ts[-1] - lfp_ts[0]))   # = 1000 Hz (ses-230823)
```

---

*Generated from `sub-C31o_ses-230823_rec.nwb` | jnwb v1.0.0 | 2026-06-26*
