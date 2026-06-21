---
name: single-unit-grand-table
description: >
  Accessing and summarizing the 6,040 single-unit grand database, unit classifications, and responsive categories.
---

# Skill: single-unit-grand-table — Unit Classifications & Summaries

## Purpose
Reference guide for loading, querying, and summarizing single-unit databases in the Omission project.

---

## 1. Database Location
- **Path**: `outputs/publication_figures/grand_database_6040_units.csv` (CSV format).
- **Numpy format**: `outputs/publication_figures/grand_database_6040_units.npy` (list of dictionaries).

---

## 2. Responsive Categories
- **Stable-Plus / Prime**: `stable_plus == True` (firing_rate > 1 Hz, SNR > 0.8, 100% presence).
- **Omission Positive ($O+$)**: `sig_o_plus == True` & `sig_s_minus == False` (significantly active during gray omission window, not suppressed by stimulus).
- **Stimulus Suppressed ($S-$ / Fixation)**: `sig_s_minus == True`.
- **Stimulus Positive ($S+$)**: `sig_s_plus == True`.
- **Null**: `is_null == True`.

---

## 3. Summarization Script
```python
import pandas as pd

def load_and_summarize():
    df = pd.read_csv("outputs/publication_figures/grand_database_6040_units.csv")
    print("Total units:", len(df))
    # Group by area and count prime units
    prime = df[df["stable_plus"] == True]
    print(prime.groupby("area").size())
    return df
```
