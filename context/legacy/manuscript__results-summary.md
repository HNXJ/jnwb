---
status: canonical
scope: manuscript
source_of_truth: true
supersedes:
  - context/docs/reports/figures-1-to-6-summary.md
  - context/docs/spiking-manuscript-synthesis.md
last_reviewed: 2026-04-06
---

# Results Summary: The Cortical Hierarchy of Expectation

## 1. Global Objective
This project investigates the neural representation of visual expectation across 11 brain areas using a large-scale multi-scale dataset (6,040 neurons, 13 sessions). We aim to resolve the hierarchical propagation of prediction error and the precision-scaling of internal generative models.

## 2. Core Methodology & Standards
- **Alignment**: All signals aligned to **Presentation 1 Onset (Code 101.0)**.
- **Window**: 6000ms total (1000ms pre-stimulus baseline).
- **Validation**: V1 photodiode latency confirmed at 40–60ms.
- **Anatomy**: DP mapped to V4; V3 split into V3d/V3a; 128 channels per probe.
- **Statistics**: Cluster-based permutation tests for LFP; Wilcoxon rank-sum for tier contrasts; MMFF (Churchland 2010) for variability.

## 3. Key Findings: Figures 1–6

### 3.1 Population Dynamics & Functional Categories
- **Figure 1 (Firing Rates)**: Grand-average population activity shows massive stimulus-driven increases but high overlap during omissions, suggesting the "Omission Signal" is carried by a selective sub-population.
- **Figure 2 (Categories)**: Identified **211 high-fidelity omission neurons**, primarily in **Deep Layers (5/6)** of **PFC, FEF, and FST**.

### 3.2 Neural Variability & Precision (MMFF)
- **Figure 3 (Quenching)**: Neural variability (Fano Factor) is quenched across all areas upon stimulus onset. Visual areas (V1-V4) show rapid quenching, while PFC shows slower, sustained reduction.
- **Figure 4 (Precision Scaling)**: Variability is significantly **reduced** in stimuli following an omission compared to standard trials, supporting the **Predictive Precision** hypothesis (surprise triggers a gain-increase).

### 3.3 Decoding the Internal Model
- **Figure 5 (Identity & Context)**: High-order areas (PFC, FEF) significantly outperform sensory areas in decoding the *identity* of the missing stimulus (A vs. B).
- **Control**: Behavioral decoding (eye position/velocity) remained at chance (50%), confirming the surprise is an internal cognitive state.

### 3.4 Directionality: Top-Down Surprise
- **Figure 6 (Coordination)**: Spike-Spike CCG reveals that the surprise response in **PFC precedes V1 by ~38ms**.
- **Causality**: V1 $\to$ PFC dominance in Gamma (Error), while PFC $\to$ V1 dominance in Beta (Prediction).

## 4. State-Space Geometry (Manifolds)
- **Manifold Divergence**: Population vectors for Omission and Delay states reside in distinct manifolds. The divergence increases from **V1 (overlap)** to **PFC (separated)**, identifying the frontal cortex as the primary generator of the contextual state.
