# Methodology Part 2: Spectral Coordination & Relative Power

## 1. Time-Frequency Representation (TFR)
- **Algorithm**: Short-Time Fourier Transform (STFT) via `scipy.signal.spectrogram`.
- **Windowing**: 100ms Hanning window.
- **Temporal Resolution**: 98% overlap (2ms steps) for high-fidelity onset detection.
- **Frequency Range**: 1-150 Hz (capturing Theta, Alpha, Beta, and Gamma bands).
- **Post-Processing**: 2D Gaussian smoothing (sigma=20ms) applied to the power spectrogram.

## 2. Relative Power Change (dB)
- **Window of Interest**: The ~1531ms window surrounding an omission (e.g., $d_3 \to p_4 \to d_4$).
- **Baseline Definition**: Average power per frequency during the serial delays *before* and *after* the omission window within the same trial.
- **Metric**: $10 \times \log_{10}(P_{time} / P_{baseline})$.
- **Normalization Goal**: Isolate internally generated "Ghost Signals" from background oscillatory fluctuations.

## 3. Band-Specific Analysis
- **Bands**: Theta (4-8Hz), Alpha (8-13Hz), Beta (13-30Hz), Gamma (35-80Hz).
- **Aggregation**: Area-specific traces calculated with $\pm$SEM shaded patches (0.2 opacity).

## 4. Safety Guard
- **Rule**: If a power trace contains all `NaN` or `0` values, the figure is not saved to the vault to ensure technical integrity.

## 5. Neural Variability Quenching (MMFF/MMV)
**Objective**: Quantify the reduction in across-trial variability as a proxy for predictive precision.
- **Algorithm (Spikes)**: Mean-Matched Fano Factor (Churchland 2010). Matches firing rate distributions across time bins to isolate variance changes from mean-rate changes.
- **Algorithm (LFP/MUAe)**: Across-trial variance normalized by the mean absolute value (MMV) at each time point.
- **Metric**: Total Variation Score (TV-Score) for channel quality assessment and artifact pruning.
- **Hypothesis**: The "internal expectation" of a stimulus quenches variability even when the physical stimulus is absent (Visual Void).

---
*Status: Verified and Accepted.*
