# Sequence Timing and Temporal Dynamics

This document formalizes the temporal structure, epoch bounds, slot windows, and alignment policies for sequence analysis.

---

## 1. Sequence Epoch Timings (ms)
Each trial begins with a fixation period followed by four stimulus slots interspersed with delay intervals. Firing rates are calculated across 9 consecutive epochs, aligned relative to the onset of the first stimulus ($\text{p}_1 = 0\text{ ms}$):

| Epoch | Name | Start (ms) | End (ms) | Duration (ms) | Description |
|---|---|---|---|---|---|
| **0** | `fx` | -500.0 | 0.0 | 500.0 | Fixation/Pre-stimulus baseline |
| **1** | `p1` | 0.0 | 531.0 | 531.0 | Stimulus 1 Presentation |
| **2** | `d1` | 531.0 | 1031.0 | 500.0 | Delay 1 |
| **3** | `p2` | 1031.0 | 1562.0 | 531.0 | Stimulus 2 / Omission 2 |
| **4** | `d2` | 1562.0 | 2062.0 | 500.0 | Delay 2 |
| **5** | `p3` | 2062.0 | 2593.0 | 531.0 | Stimulus 3 / Omission 3 |
| **6** | `d3` | 2593.0 | 3093.0 | 500.0 | Delay 3 |
| **7** | `p4` | 3093.0 | 3624.0 | 531.0 | Stimulus 4 / Omission 4 |
| **8** | `d4` | 3624.0 | 4124.0 | 500.0 | Delay 4 / Post-sequence window |

* **Total Trial Span**: **4624 ms** (from -500 ms to 4124 ms).

---

## 2. Canonical Code Definitions
In `jnwb`, the timing dictionary and bounds are defined as:

```python
EPOCH_ONSETS_MS = {
    "fx": -500.0,
    "p1": 0.0,
    "d1": 531.0,
    "p2": 1031.0,
    "d2": 1562.0,
    "p3": 2062.0,
    "d3": 2593.0,
    "p4": 3093.0,
    "d4": 3624.0
}
```

---

## 3. Omission Slot-Window Definitions
The specific window tested by the omission response classifier (`is_o_plus`) corresponds exactly to the stimulus presentation duration of the omitted slot:
* **Slot 2 Omission (RXRR)**: $[1031.0, 1562.0]\text{ ms}$ relative to trial onset.
* **Slot 3 Omission (RRXR)**: $[2062.0, 2593.0]\text{ ms}$ relative to trial onset.
* **Slot 4 Omission (RRRX)**: $[3093.0, 3624.0]\text{ ms}$ relative to trial onset.

---

## 4. Alignment Policies
1. **Trial-Relative Time**: All spike times and LFP samples are aligned relative to the start of the first pulse (`p1` onset) of each trial, establishing $t = 0$ as the sequence start.
2. **Absolute NWB Time**: NWB files store timestamps in seconds relative to recording start. The conversion is:
   $$\text{timestamp}_{\text{rel}} = (\text{timestamp}_{\text{absolute}} - \text{trial\_start\_time}) \times 1000.0$$
