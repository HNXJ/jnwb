# Methodology Part 1: Spiking Dynamics & Decoding Hierarchy

## 1. Data Alignment & Preprocessing
- **Reference**: All trials are aligned to **Code 101.0** (Presentation 1 Onset).
- **Buffer**: 1000ms pre-stimulus baseline included.
- **Filtering**: Only Correct trials (`TrialError == 0`) are used.
- **Normalization**: Unit firing rates are smoothed using a Gaussian kernel (sigma=20ms) for PSTH generation.

## 2. Information Decoding (SVM)
- **Classifier**: Linear Support Vector Machine (SVM).
- **Target 1 (Identity)**: A vs B stimulus classification during P1-P4.
- **Target 2 (Omission)**: Omission vs Standard (AAAX vs AAAB) during the P4 window.
- **Cross-Validation**: 5-fold CV with stratified trial splits.
- **Sliding Window**: 50ms window with 10ms steps to track information emergence.

## 3. Manifold Discovery (PCA)
- **Dimensionality Reduction**: Principal Component Analysis (PCA) performed on trial-averaged population activity.
- **Visualization**: First 3 PCs used to map the state-space trajectory of the surprise response.
- **Metrics**: Explained variance and Euclidean distance between "Standard" and "Rare" trajectories.

## 4. Latency Analysis
- **Threshold**: Surprise detection onset defined as the first point where decoding accuracy exceeds the 95th percentile of the baseline distribution.
- **Hierarchical Propagation**: Comparison of time-to-peak across all 11 areas.

---
*Status: Verified and Accepted.*
