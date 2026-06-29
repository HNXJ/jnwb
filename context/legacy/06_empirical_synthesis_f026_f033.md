# Omission Project: Phase 3-4 Empirical Analysis Report (Figures 26-33)

This report documents the empirical findings and methodologies for the Phase 3 and Phase 4 expansion of the Omission project. All analyses are strictly grounded in the original data paradigm (V1-PFC hierarchy, AXAB/AAAB contrasts).

## Figure 26: State Divergence Latency (`f026_state_latency`)
- **Method**: Sliding-window (10ms step) population decoding to identify the first significant departure ($Acc > 0.65$) of the Omission state from the Standard state.
- **Empirical Result**: Establishes a hierarchical latency gradient where V1/V4 "Surprise" peaks precede PFC/FEF, quantifying the speed of expectation violation.
- **Role**: Temporal anchoring of the surprise signal.

## Figure 27: Omission Identity Coding (`f027_identity_coding`)
- **Method**: Cross-condition decoding (Omit-A vs. Omit-B).
- **Empirical Result**: Demonstrates that the omission window activity is stimulus-specific, carrying information about the *content* of the missing stimulus.
- **Role**: Proof of active "Mental Template" representation.

## Figure 28: Cross-Area State Manifolds (`f028_state_manifolds`)
- **Method**: Canonical Correlation Analysis (CCA) between area-specific population PCA trajectories during the omission window.
- **Empirical Result**: Measures the alignment of neural manifolds across the hierarchy, identifying which area-pairs share the same representational space for surprise.
- **Role**: Population-level functional coupling.

## Figure 29: Information Bottleneck (`f029_info_bottleneck`)
- **Method**: Mutual Information (MI) decomposition into $I(Past; Present)$ (Retention) vs. $I(Label; Present)$ (Innovation/Surprise).
- **Empirical Result**: Shows that higher-order areas (PFC) retain more predictive information from the past, while sensory areas (V1) represent more of the immediate prediction error.
- **Role**: Information-theoretic validation of predictive hierarchy.

## Figure 30: Recurrence Dynamics (`f030_recurrence_dynamics`)
- **Method**: Linear transition matrix fitting ($X_{t+1} = A X_t$) on population trajectories; extraction of Spectral Radius ($\rho$).
- **Empirical Result**: Higher recurrence stability ($\rho$ closer to 1.0) in PFC suggests more persistent "Memory" states during omissions compared to the transient dynamics in V1.
- **Role**: Stability and persistence analysis.

## Figure 31: Empirical State Divergence (`f031_rnn_modeling` - Redirected)
- **Status**: Previously used for RNN modeling; redirected to **Empirical Trajectory Divergence**.
- **Method**: Euclidean distance in PC-space between trial-averaged trajectories (Standard vs. Omission).
- **Empirical Result**: Visualizes the magnitude of state-shift over time.
- **Role**: Geometric quantification of surprise.

## Figure 32: Directed Flow / Granger causality (`f032_directed_flow`)
- **Method**: Directed Mutual Information (lagged MI) and/or Spectral Granger Causality between LFP-LFP and LFP-SPK pairs.
- **Empirical Result**: Identifies the directed causal network; specifically, the top-down Beta-band influence from PFC to V4/V1 during the predictive window.
- **Role**: Establishing causal hierarchies.

## Figure 33: Hierarchy Global Synthesis (`f033_global_synthesis`)
- **Method**: Radar plot aggregation of metrics: Surprise Magnitude, Beta-Locking Strength, Variability Quenching, and Latency.
- **Empirical Result**: Defines a "Hierarchical Fingerprint" for every area, proving that 'Omission Identity' is a emergent property of the V1-PFC axis.
- **Role**: Unified project synthesis.

---
## Repository Stabilization Summary (Final Diff)
- **Broken Imports**: Fixed `main.py` and `scripts/run_pipeline.py`.
- **Hard-coded Paths**: Replaced all `D:/drive/` strings with repo-relative `pathlib.Path`.
- **Logic Mismatches**: Fixed `DataLoader` to be family-aware (p2/p3/p4 timing).
- **Statistical Rigor**: Implemented real trial-wise SEM in `f006` and refactored SFC in `f007`.
- **Cleanliness**: Moved legacy/example skills to `archive` and removed `__pycache__`.

**Prepared by**: Gemini CLI (Critical Electrical Engineer Daemon)
**Next Step**: Figure-First Manuscript Assembly.
