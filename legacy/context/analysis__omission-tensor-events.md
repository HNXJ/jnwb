# Omission Task Tensor: Events and Windows

This document defines the canonical 12x9 event tensor for the Omission task.

## Temporal Windows (Columns)
The task sequence consists of 9 consecutive windows (duration 531ms for stim, 500ms for others):

| ID | Label | Onset (ms) | Content |
|---|---|---|---|
| 0 | fx | -500 | Fixation dot only |
| 1 | p1 | 0 | Stimulus A/B |
| 2 | d1 | 531 | Fixation dot only |
| 3 | p2 | 1031 | Stimulus A/B |
| 4 | d2 | 1562 | Fixation dot only |
| 5 | p3 | 2062 | Stimulus A/B |
| 6 | d3 | 2593 | Fixation dot only |
| 7 | p4 | 3093 | Stimulus A/B |
| 8 | d4 | 3624 | Fixation dot only |

## Condition Groups (Rows)
12 experimental conditions defined by their sequences:

*   **Standard (RRRR):** AAAB, BBBA, RRRR
*   **Omission 2 (RXRR):** AXAB, BXBA, RXRR
*   **Omission 3 (RRXR):** AAXB, BBXA, RRXR
*   **Omission 4 (RRRX):** AAAX, BBBX, RRRX

*Note: Stimuli (A, B, R) are visually distinct (moving gratings), while (X, fx, d) are fixation-only.*

## Physiological Unit Classification
Units must meet stability criteria:
1.  **Presence Ratio**: > 0.95
2.  **Firing Rate**: >= 1.0 Hz
3.  **Consistency**: No trial with 0 Hz spiking.

### Classification Logic
*   **S+ (Stimulus Positive)**: FR(p1) > FR(fx)
*   **S- (Stimulus Negative)**: FR(fx) > FR(p1)
*   **O+ (Omission Positive)**: FR(omit-window) > FR(preceding-delay)
    *   Example O2: FR([RXRR]-[p2]) > FR([RXRR]-[d1])

## High-Interest Omission Windows (1531ms)
Used for "Pure Prediction" vs "Pure Prediction Error" analysis:
1.  **[AXAB/BXBA/RXRR] - [d1, p2, d2]** (2nd Omission)
2.  **[AAXB/BBXA/RRXR] - [d2, p3, d3]** (3rd Omission)
3.  **[AAAX/BBBX/RRRX] - [d3, p4, d4]** (4th Omission)
