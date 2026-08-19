# Methodology Part 3: Representational Similarity Analysis (RSA/CKA)

## 1. Feature Space Construction
- **Items**: Defined by [Context x TimeWindow] pairs. Standard items include stimuli presentations (P1-P4) and delays (D1-D4).
- **Spiking Features**: Trial-averaged firing rates across neurons.
- **LFP Features**: Broadband spectral power (variance) across channels.
- **Alignment**: Items are perfectly time-synchronized between areas and modalities to allow second-order comparison.

## 2. RDM Construction
- **Metric**: Pearson Correlation distance (1 - r) used to compute the Representational Dissimilarity Matrix (RDM).
- **Acceleration**: JAX `vmap` and `numpy` vectorization utilized for 11x11 area-to-area batch processing.

## 3. Second-Order Similarity (CKA)
- **Algorithm**: Centered Kernel Alignment (CKA) with a linear kernel.
- **Benefit**: CKA is invariant to orthogonal transformations and isotropic scaling, enabling robust comparison between datasets with different dimensionalities (e.g., 500 units in V1 vs 128 channels in PFC).
- **Comparison Types**: 
    - Area-vs-Area (Spiking)
    - Area-vs-Area (LFP)
    - Modality-vs-Modality (Spiking-LFP within/across areas)

## 4. High-Fidelity Visualization
- **Standard**: Plotly heatmaps with `zsmooth='best'` (bicubic interpolation).
- **Aesthetic**: Madelane Golden Dark palette.
- **Hierarchy**: Analysis performed across 4 contexts (Delay, Omission, Stimulus, All-Time).

---
*Status: Verified and Accepted.*
