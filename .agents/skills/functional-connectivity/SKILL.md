---
name: functional-connectivity
description: >
  Directional Mutual Information (MI) functional connectivity between neurons
  and between area-layer groups in the Omission project. Covers neuron
  subselection, spike binning, vectorized MI computation, and HDF5 output.
---

# Skill: functional-connectivity — Directional MI Connectivity

## Purpose
Compute neuron-to-neuron and group-to-group (22-in-22) directional Mutual
Information across 12 condition groups and 600 time bins. This is the
canonical reference for anyone building or extending the MI pipeline.

---

## 1. Conceptual Overview

We compute **directional (lagged) MI** between binary spike states across trials:

$$I(X_i(t);\, Y_j(t-\tau))$$

- $X_i(t)$ = state of **target** neuron $i$ at time $t$ (0 or 1 across 40 trials)
- $Y_j(t-\tau)$ = state of **source** neuron $j$ at time $t - \tau$ (lag = 1 step = 10 ms)
- Computed for all 12 conditions, all 600 time bins → tensor of shape $(N, N, 12, 600)$
- MI in **bits** using the plugin estimator for binary variables

---

## 2. Neuron Subselection

```python
import pandas as pd

metadata = pd.read_csv("outputs/spsam/grand_unit_metadata.csv")

LAYERS = ["Superficial (L2/3)", "Deep (L5/L6)"]
CANONICAL_AREAS = ["V1", "V2", "V3", "V3a", "V3d", "V4", "FEF", "PFC", "MT", "MST", "TEO"]

stable_valid = metadata[metadata["is_stable"] & metadata["layer"].isin(LAYERS)].copy()

# Balanced selection: 50 superficial + 50 deep, round-robin over areas by SNR
def select_balanced(df_layer, n=50):
    by_area = {a: df_layer[df_layer["area"] == a]
                           .sort_values("snr", ascending=False)
                           .to_dict("records")
               for a in df_layer["area"].unique()}
    areas   = sorted(by_area.keys())
    result  = []
    while len(result) < n and any(by_area[a] for a in areas):
        for a in areas:
            if len(result) >= n:
                break
            if by_area[a]:
                result.append(by_area[a].pop(0))
    return pd.DataFrame(result)

selected = pd.concat([
    select_balanced(stable_valid[stable_valid["layer"] == "Superficial (L2/3)"], 50),
    select_balanced(stable_valid[stable_valid["layer"] == "Deep (L5/L6)"],        50),
], ignore_index=True)
# → 100 neurons total
```

---

## 3. Spike Binning (Vectorized)

Bins are 100 ms wide with 10 ms step. For each neuron × condition × trial:

```python
def bin_spikes(spike_times, onsets_sec, T=600):
    """
    Returns binary spike matrix: (K_trials, T_bins)
    K_trials : number of trials (≤ 40)
    T_bins   : 600 bins (100ms wide, 10ms step, from -1000ms to +5000ms)
    """
    K      = len(onsets_sec)
    binned = np.zeros((K, T), dtype=np.float32)
    bin_step = 0.010   # 10 ms step in seconds
    bin_size = 0.100   # 100 ms width in seconds

    for k, onset in enumerate(onsets_sec):
        t_lo = onset - 1.0
        t_hi = onset + 5.0
        trial_spikes = spike_times[(spike_times >= t_lo) & (spike_times <= t_hi)]
        rel_spikes   = trial_spikes - onset

        for spk in rel_spikes:
            r = spk + 1.0           # shift to positive range
            if r < 0:
                continue
            base_idx = int(np.floor(r * 100.0))   # 100 steps per second
            t_start  = max(0,     base_idx - 9)   # back-spread 90 ms (10 bins)
            t_end    = min(T - 1, base_idx)
            if t_start <= t_end:
                binned[k, t_start:t_end + 1] = 1.0
    return binned
```

---

## 4. Vectorized Binary MI Kernel (Validated)

The kernel has been validated against `sklearn.metrics.mutual_info_score`
(max abs error < 1e-6):

```python
def compute_mi_matrix(X, Y, K):
    """
    X : (K, N_x) — binary spike states of target neurons
    Y : (K, N_y) — binary spike states of source neurons
    Returns (N_x, N_y) MI matrix in bits.
    """
    c11 = X.T @ Y
    c10 = X.T @ (1.0 - Y)
    c01 = (1.0 - X).T @ Y
    c00 = (1.0 - X).T @ (1.0 - Y)

    p11 = c11 / K; p10 = c10 / K; p01 = c01 / K; p00 = c00 / K

    px1 = np.mean(X, axis=0, keepdims=True).T   # (N_x, 1)
    px0 = 1.0 - px1
    py1 = np.mean(Y, axis=0, keepdims=True)      # (1, N_y)
    py0 = 1.0 - py1

    def _term(pxy, px, py):
        pprod = np.maximum(px @ py, 1e-12)
        ratio = np.maximum(pxy / pprod, 1e-12)
        t = pxy * np.log2(ratio)
        t[pxy < 1e-12] = 0.0
        return t

    mi = (_term(p11, px1, py1) + _term(p10, px1, py0)
         + _term(p01, px0, py1) + _term(p00, px0, py0))
    return np.maximum(mi, 0.0).astype(np.float32)
```

---

## 5. Parallel Execution

```python
from concurrent.futures import ProcessPoolExecutor

# worker_job MUST be at module top-level for pickle compatibility
def worker_job(task):
    cond_idx, t_bin, sess_id, X, Y, K = task
    return cond_idx, t_bin, sess_id, compute_mi_matrix(X, Y, K)

# Build task list: one task per (condition, time_bin, session)
tasks = []
for cond_idx, cond in enumerate(ALL_CONDITIONS):
    for t in range(1, 600):
        for sess_id, binned in session_data.items():
            if cond not in binned:
                continue
            X = binned[cond][:, :, t]
            Y = binned[cond][:, :, t - 1]
            tasks.append((cond_idx, t, sess_id, X, Y, binned[cond].shape[0]))

# Run with 12 workers
with ProcessPoolExecutor(max_workers=12) as pool:
    results = pool.map(worker_job, tasks, chunksize=100)
```

**Expected performance** (24-core machine, 100 neurons):
- Data loading + binning: ~45 s (11 sessions)
- MI computation (79,000 slices): ~14 s
- Total: **~54 s**

---

## 6. Output Format (HDF5)

```python
import h5py, numpy as np

OUTPUT_PATH = "outputs/mi_connectivity/mi_functional_connectivity.h5"

with h5py.File(OUTPUT_PATH, "w") as f:
    # Primary connectivity tensors
    f.create_dataset("neuron_connectivity", data=conn_tensor,  # (100, 100, 12, 600)
                     compression="gzip", compression_opts=4)
    f.create_dataset("group_connectivity",  data=group_conn,   # (22, 22, 12, 600)
                     compression="gzip", compression_opts=4)

    # Group labels: 22 strings
    f.create_dataset("group_names",    data=np.array(GROUPS_22, dtype="S"))

    # Per-neuron metadata
    f.create_dataset("neuron_id",      data=selected["unit_id"].values)
    f.create_dataset("neuron_session", data=selected["session_id"].values.astype("S"))
    f.create_dataset("neuron_area",    data=selected["area"].values.astype("S"))
    f.create_dataset("neuron_layer",   data=selected["layer"].values.astype("S"))
```

**Read back**:
```python
with h5py.File(OUTPUT_PATH, "r") as f:
    nc = f["neuron_connectivity"][:]   # (100, 100, 12, 600)
    gc = f["group_connectivity"][:]    # (22,  22,  12, 600)
    groups = [n.decode() for n in f["group_names"][:]]
```

---

## 7. 22-Group Structure

Groups are ordered as `{area}_{layer}` for all combinations:

```python
CANONICAL_AREAS = ["V1","V2","V3","V3a","V3d","V4","FEF","PFC","MT","MST","TEO"]
LAYERS          = ["Superficial (L2/3)", "Deep (L5/L6)"]

GROUPS_22 = [f"{a}_{l}" for a in CANONICAL_AREAS for l in LAYERS]
# → ["V1_Superficial (L2/3)", "V1_Deep (L5/L6)", "V2_Superficial (L2/3)", ...]
```

Group-to-group connectivity uses **within-session pairs only** to avoid
artificially low inter-session MI values.

---

## 8. Key Files

| File | Role |
|------|------|
| [scripts/mi_functional_connectivity.py](file:///D:/workspace/omission/scripts/mi_functional_connectivity.py) | Full pipeline (canonical implementation) |
| [mi_functional_connectivity.h5](file:///D:/workspace/omission/outputs/mi_connectivity/mi_functional_connectivity.h5) | Pre-computed output (100 neurons) |
| [spiking/stats.py](file:///D:/workspace/omission/src/analysis/spiking/stats.py) | Lower-level MI helper |
| [selected_neurons.csv](file:///D:/workspace/omission/outputs/mi_connectivity/selected_neurons.csv) | Selected neuron manifest |
