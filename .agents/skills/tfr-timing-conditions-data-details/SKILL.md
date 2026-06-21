---
name: tfr-timing-conditions-data-details
description: >
  Condition mappings, sequence trial timings, and LFP TFR dataset directories details.
---

# Skill: tfr-timing-conditions-data-details — Trial Timings & Condition Mappings

## Purpose
Reference guide for task condition mappings, trial timelines, and accessing LFP Time-Frequency Representation (TFR) datasets in the Omission project.

---

## 1. Omission Condition Families
Task trials are divided into A, B, and R families, each containing control trials and omission trials:
- **A-Family**:
  - Control: `AAAB` (codes 1, 2)
  - Omissions: `AXAB` (code 3, slot 2), `AAXB` (code 4, slot 3), `AAAX` (code 5, slot 4)
- **B-Family**:
  - Control: `BBBA` (codes 6, 7)
  - Omissions: `BXBA` (code 8, slot 2), `BBXA` (code 9, slot 3), `BBBX` (code 10, slot 4)
- **R-Family**:
  - Control: `RRRR` (codes 11–26)
  - Omissions: `RXRR` (codes 27–34, slot 2), `RRXR` (codes 35, 37, 39, 41, slot 3), `RRRX` (codes 36, 38, 40, 42-50, slot 4)

---

## 2. Sequence Trial Timing
Each trial contains four stimulus slots (p1–p4) of 500 ms each, separated by 531 ms gray-screen inter-stimulus intervals (ISI):
- **Slot 1 (p1)**: [0, 500] ms
- **Slot 2 (p2)**: [1031, 1531] ms
- **Slot 3 (p3)**: [2062, 2562] ms
- **Slot 4 (p4)**: [3093, 3593] ms

---

## 3. Data Directory Structure
Processed TFR arrays reside under `D:/workspace/data/tfr_arrays/` as numpy files named `{session}-{probe}-{area}-{condition}.npy`.
- **Dimensions**: `(n_trials, n_channels, n_freqs, n_times)`
- **Frequencies**: 2 Hz to 150 Hz (log-spaced, 40 bins).
- **Time bins**: -1000 ms to 4000 ms relative to p1 onset.

---

## 4. Access Code Example
```python
import numpy as np
from pathlib import Path

tfr_path = Path("D:/workspace/data/tfr_arrays/sub-C31o_ses-230818_rec-A-PFC-RRRR.npy")
if tfr_path.exists():
    data = np.load(tfr_path)
    print("Loaded TFR shape:", data.shape)  # e.g., (40, 16, 40, 5000)
```
