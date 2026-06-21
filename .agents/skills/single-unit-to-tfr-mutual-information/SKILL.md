---
name: single-unit-to-tfr-mutual-information
description: >
  Cross-correlation and Mutual Information between single-unit spiking and LFP band-power.
---

# Skill: single-unit-to-tfr-mutual-information — Spiking-to-LFP MI

## Purpose
Formulation and code snippets for computing Mutual Information (MI) between single-unit spike trains and LFP band power.

---

## 1. Binning & State Alignment
To align spiking (point process) with LFP TFR band power (continuous):
1. Bin LFP band power into the same 10 ms grid bins.
2. Discretize LFP power values into binary states (e.g. median-split: 0 = below median, 1 = above median).
3. Bin single-unit spikes on the same 10 ms bins (0 = no spikes, 1 = spikes).
4. Compute joint probabilities between discretized LFP states $L(t)$ and spiking states $S(t - 	au)$ at lag $	au$ to yield lagged MI.

---

## 2. Lagged Spike-LFP MI Code
```python
import numpy as np

def compute_spike_lfp_mi(spikes_binary, lfp_binary, K):
    """
    spikes_binary : (K_trials, T_bins) binary spike states
    lfp_binary    : (K_trials, T_bins) binary LFP band-power states
    K             : number of trials
    """
    T = spikes_binary.shape[1]
    mi_trace = np.zeros(T)
    # Compute lagged MI: spike(t - 1) predicting LFP(t)
    for t in range(1, T):
        x = lfp_binary[:, t]
        y = spikes_binary[:, t-1]
        
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
