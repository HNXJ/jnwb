# Omission Context: Definitions and Standards
Version: 3.0 (Ultimate Stability)

## 1. Timing Definitions (Canonical)

| Type | Epoch | Window (ms) | Description |
|:---|:---:|:---:|:---|
| **Fixation Baseline** | `fx` | -500 to 0 | Always at the start of stimulus sequences. |
| **Delay Baseline** | `d1-d4` | Variable | The 500ms intervals between presentations. |
| **Presentation** | `p1-p4` | Variable | Stimulus presentation windows (531ms duration). |
| **Omission** | `x` | Variable | A presentation window where stimulus is omitted. |

### Specific Omission Slots:
- **p2**: `axab`, `bxba`, `rxrr`
- **p3**: `aaxb`, `bbxa`, `rrxr`
- **p4**: `aaax`, `bbbx`, `rrrx`

---

## 2. Functional Categorization

- **Stimulus-Positive (S+)**: Firing(Presentation) > Fixation Baseline (Significant).
- **Stimulus-Negative (S-)**: Firing(Presentation) < Fixation Baseline (Significant).
- **Omission-Positive (O+)**: Firing(Omission) > Fixation Baseline (Significant).
- **Omission-Negative (O-)**: Firing(Omission) < Fixation Baseline (Significant).

---

## 3. Ultimate Unit Stability

A unit is defined as **Ultimate Stable** if:
1.  **Isolation**: `isi-violations` < 0.5.
2.  **Trial-Level Consistency**: Average firing rate during **every single trial** of the `RRRR` group is **above 1.0 Hz** (minimum 1 spike per 1000ms window).
    *   *Requirement*: If there are 300 `RRRR` trials, the unit must have at least 1 spike per 1000ms in all 300 trials.

---

## 4. Visual Standards
- Trace Smoothing: **Gaussian Convolved (`sigma=50ms`)**.
- Shading: **±SEM patches** (20% opacity).
- Figure Layout: Rasters (`RRRR`, `RXRR`, `RRXR`) + Grouped PSTHs (A-Base, B-Base, Random).
