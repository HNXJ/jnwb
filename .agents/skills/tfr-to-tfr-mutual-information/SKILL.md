---
name: tfr-to-tfr-mutual-information
description: >
  Calculating time-varying and band-to-band Mutual Information (MI) and correlations between LFP signals.
---

# Skill: tfr-to-tfr-mutual-information — TFR-TFR Mutual Information

## Purpose
Mathematical definition and implementation for computing Mutual Information (MI) and correlations between distinct LFP signals or frequency bands.

---

## 1. State Discretization
To calculate Shannon Mutual Information between continuous TFR power traces:
1. Extract time-course power traces for two target bands/channels.
2. Discretize power values into binary states (e.g., using a median-split: 0 = below median, 1 = above median).
3. Compute Shannon Mutual Information in bits across trials.

---

## 2. Shannon MI Code
```python
import numpy as np

def compute_tfr_tfr_mi(states_x, states_y):
    """
    states_x : (n_trials, n_times) discretized states {0, 1}
    states_y : (n_trials, n_times) discretized states {0, 1}
    Returns MI for each time bin.
    """
    K = states_x.shape[0]
    T = states_x.shape[1]
    mi_trace = np.zeros(T)
    for t in range(T):
        x = states_x[:, t]
        y = states_y[:, t]
        # Joint probability
        joint_counts = np.histogram2d(x, y, bins=[[-0.5, 0.5, 1.5], [-0.5, 0.5, 1.5]])[0]
        joint_p = joint_counts / K
        px = np.sum(joint_p, axis=1, keepdims=True)
        py = np.sum(joint_p, axis=0, keepdims=True)
        
        mi = 0.0
        for i in range(2):
            for j in range(2):
                if joint_p[i, j] > 1e-12:
                    mi += joint_p[i, j] * np.log2(joint_p[i, j] / (px[i, 0] * py[0, j]))
        mi_trace[t] = max(mi, 0.0)
    return mi_trace
```
