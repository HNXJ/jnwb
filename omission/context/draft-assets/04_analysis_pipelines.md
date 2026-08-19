# Core Analysis & Classification Pipelines

This document specifies the processing pipelines for single-unit omission responses, trial-by-trial stability, baseline normalization, and population dynamics.

---

## 1. Single-Unit Omission Classification
Neurons are classified into S+, S-, O+, and Null categories based on their response profiles:

* **S+ (Stimulus-Tracking)**: Responds to stimulus presentations. Firing rate peaks in `p1`, `p2`, `p3`, `p4` (except when omitted).
* **S- (Inverse Stimulus-Tracking)**: Responds during delay periods. Firing rate peaks in `fx`, `d1`, `d2`, `d3`, `d4`.
* **O+ (Omission-Responding)**: Firing rate elevates specifically during omitted stimulus slots.

### Permutation-Based Classification Pipeline
1. Firing rates are calculated for all 9 epochs across the three omission conditions (RXRR, RRXR, RRRX), forming a 27-element concatenated vector.
2. The Pearson correlation ($r$) is calculated between the concatenated firing rate vector and binary templates (e.g. $[0,0,0,1,0,0,0,0,0]$ for RXRR omission slot).
3. The empirical p-value is computed using a vectorized permutation test with 5000 random shuffles of the 27-element template:
   $$p = \frac{1}{N_{\text{shuffles}}} \sum_{i=1}^{N_{\text{shuffles}}} \mathbb{I}(r_{\text{shuffled}}^{(i)} \ge r_{\text{observed}})$$
4. Units are classified into categories using significance thresholds ($p < 0.05$ for S+, $p < 0.01$ for O+).

---

## 2. Trial-by-Trial Stability Verification (Drift Check)
To avoid selecting units that degrade or drift mid-session, stability is verified across correct trials:
1. Spike counts are computed within the sequence window ($-500\text{ ms}$ to $4124\text{ ms}$) for all correct trials.
2. The Spearman rank correlation coefficient ($\rho_{\text{drift}}$) is computed between trial index and trial spike counts.
3. **Enforcement Threshold**: Units with systematic drift $|\rho_{\text{drift}}| \ge 0.45$ are rejected as unstable.

---

## 3. Baseline-Subtracted Normalization
To control for global state changes, firing rates are normalized relative to pre-stimulus baseline:
$$\text{Rate}_{\text{normalized}}(t) = \text{Rate}_{\text{raw}}(t) - \text{Baseline}_{\text{fixation}}$$
Where $\text{Baseline}_{\text{fixation}}$ is the mean firing rate during the `fx` epoch ($-500\text{ ms}$ to $0\text{ ms}$).

---

## 4. Population Dynamics (SVM & PCA)
* **SVM Decoders**: Linear Support Vector Machines are trained to classify trial condition or decode elapsed time from population firing rate vectors, cross-validated using leave-one-out splits.
* **PCA State-Space**: Principal Component Analysis is applied to trial-averaged population matrices to project neural trajectories into low-dimensional subspaces.
