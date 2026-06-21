---
name: single-unit-mutual-information
description: >
  Computing directional (lagged) Shannon Mutual Information between single-unit spike trains.
---

# Skill: single-unit-mutual-information — directional MI

## Purpose
Reference code and protocols for calculating directional (lagged) Shannon Mutual Information (MI) between single-unit spike trains.

---

## 1. Spike Binning Protocol
- Bin width: 100 ms.
- Step size: 10 ms.
- Window: -1000 to +5000 ms relative to p1 trial onset (600 time bins).
- State: Binary (0 = no spikes, 1 = one or more spikes in bin).

---

## 2. directional Lagged MI Formula
$$I(X_i(t); Y_j(t - 	au))$$
where lag $	au = 1$ bin (10 ms).

---

## 3. Vectorized MI Kernel
```python
import numpy as np

def compute_mi_matrix(X, Y, K):
    c11 = X.T @ Y
    c10 = X.T @ (1.0 - Y)
    c01 = (1.0 - X).T @ Y
    c00 = (1.0 - X).T @ (1.0 - Y)
    p11 = c11/K; p10 = c10/K; p01 = c01/K; p00 = c00/K
    px1 = np.mean(X, axis=0, keepdims=True).T
    px0 = 1.0 - px1
    py1 = np.mean(Y, axis=0, keepdims=True)
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
