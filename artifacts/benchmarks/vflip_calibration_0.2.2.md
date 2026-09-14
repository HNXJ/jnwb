# vFLIP Support Score (Omega) Calibration & Operating Characteristics Receipt

## 1. Null Ensemble False Positive Rates

| Null Family | Min Omega | Median Omega | Max Omega | FPR (tau=6.0) | FPR (tau=5.0) | FPR (tau=7.0) |
|---|---|---|---|---|---|---|
| `white_noise` | -27.63 | 4.67 | 6.31 | 0.100 | 0.333 | 0.000 |
| `uniform_1f` | -27.63 | 4.95 | 5.94 | 0.000 | 0.433 | 0.000 |
| `spatial_gradient` | -27.63 | 4.91 | 6.83 | 0.100 | 0.433 | 0.000 |
| `spectral_gradient_no_cross` | -27.63 | 2.04 | 7.54 | 0.033 | 0.033 | 0.033 |
| `multi_cross` | 6.45 | 6.98 | 8.81 | 1.000 | 1.000 | 0.467 |
| `orientation_conflict` | 7.26 | 8.40 | 9.02 | 1.000 | 1.000 | 1.000 |

## 2. Alternative Ensemble True Positive Rates & Recovery Error

### A. SNR Sweep (N=24)
| SNR | Median Omega | Median Error (ch) | TPR (tau=6.0) | TPR (tau=5.0) | TPR (tau=7.0) |
|---|---|---|---|---|---|
| 0.05 | 4.82 | 3.807 | 0.033 | 0.400 | 0.000 |
| 0.1 | 5.14 | 3.221 | 0.167 | 0.567 | 0.000 |
| 0.2 | 6.12 | 1.958 | 0.567 | 0.800 | 0.000 |
| 0.5 | 6.89 | 0.558 | 0.933 | 1.000 | 0.467 |
| 1.0 | 7.56 | 0.338 | 1.000 | 1.000 | 0.933 |
| 2.0 | 8.05 | 0.327 | 1.000 | 1.000 | 1.000 |
| 5.0 | 8.32 | 0.273 | 1.000 | 1.000 | 1.000 |

### B. Channel Count Sweep (SNR=1.0)
| N Channels | Median Omega | Median Error (ch) | TPR (tau=6.0) |
|---|---|---|---|
| 8 | 6.33 | 0.512 | 0.800 |
| 12 | 7.29 | 0.331 | 1.000 |
| 16 | 7.38 | 0.225 | 1.000 |
| 24 | 7.57 | 0.328 | 1.000 |
| 32 | 7.54 | 0.409 | 1.000 |
| 48 | 7.60 | 0.780 | 1.000 |
| 64 | 7.90 | 0.863 | 1.000 |

### C. Missing Contacts Sweep (N=24, SNR=1.0)
| Missing Fraction | Median Omega | Median Error (ch) | TPR (tau=6.0) |
|---|---|---|---|
| 0.0 | 7.56 | 0.338 | 1.000 |
| 0.1 | 7.58 | 0.301 | 1.000 |
| 0.2 | 7.63 | 0.339 | 1.000 |
| 0.3 | 7.62 | 0.410 | 1.000 |

## 3. Physical Equivalence Discretization Probe

Fixed physical column of depth 1200 um, true crossover at 600 um.

| Pitch (um) | N Contacts | Median Omega | Min Omega | Max Omega | Median z-Error (um) |
|---|---|---|---|---|---|
| 25.0 | 48 | 8.76 | 8.13 | 9.14 | 18.23 |
| 50.0 | 24 | 7.72 | 7.38 | 8.20 | 18.77 |
| 100.0 | 12 | 6.61 | 6.21 | 7.12 | 17.83 |