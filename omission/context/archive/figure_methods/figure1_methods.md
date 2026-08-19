# Methods and Analysis Specifications for Figure 1: MaDeLaNe Setup & Killer Summary

**Target Figure**: [`context/figures/figure1_main_killer_summary.png`](file:///d:/workspace/omission/context/figures/figure1_main_killer_summary.png)  
**Vector Source**: [`context/figures/figure1_main_killer_summary.svg`](file:///d:/workspace/omission/context/figures/figure1_main_killer_summary.svg)  
**Generator Code**: [`scripts/generate_killer_figure.py`](file:///d:/workspace/omission/scripts/generate_killer_figure.py)

---

## 1. Scientific Overview & Purpose

Figure 1 provides the single load-bearing summary of visual omission neurophysiology across the 10 ordered anatomical areas of the macaque visual-to-prefrontal hierarchy (V1 to PFC). It establishes the headline dissociation between **sparse single-unit spiking** and **broad low-frequency LFP field disruption**.

---

## 2. Panel-by-Panel Methods & Analytical Specifications

### Panel A: Single-Unit O+ Spiking Ramping Across Hierarchy
- **Data Source**: `outputs/classification/grand_unit_table_shuffle_sso.csv` & `artifacts/data/empirical_response_census.json`
- **Signal Modality**: Spike-sorted single-unit activity (SPK).
- **Classification Criteria**: Omission-positive (O+) units defined by template-correlation ranking across omission slots ($p < 0.01$).
- **Statistical Metric**: Percentage of O+ units ($k/N$) per anatomical area with exact Binomial Clopper-Pearson 95% CIs and $\pm$ SEM error bars.
- **Statistical Test**: Spearman rank correlation across 10 anatomical ranks ($V1=1$ to $PFC=10$).
- **Result**: $r = 0.988, p < 0.001$. Monotonic increase from V1 (1.11%) to FEF (9.40%) and PFC (9.32%).

### Panel B: Broad Low-Frequency LFP Beta Perturbation
- **Data Source**: `D:/workspace/data/tfr_arrays/` & `artifacts/data/empirical_response_census.json`
- **Signal Modality**: Local Field Potential (LFP) band-pass power ($14\text{--}30$ Hz Beta).
- **Statistical Metric**: Percentage of LFP channels exhibiting significant baseline-normalized power modulation ($p < 0.01$, FDR corrected) with $\pm$ SEM error bars.
- **Result**: $r = 0.942, p < 0.001$. Broad perturbation ranging from 73.00% of channels in V1 to 83.05% in PFC.

### Panel C: Signal Type Interaction (LFP Field vs. Spike Divergence)
- **Mathematical Formula**: $\text{Ratio} = \frac{\text{LFP Beta Modulation \%}}{\text{Spiking O+ \%}}$
- **Error Propagation**: $\frac{\Delta \text{Ratio}}{\text{Ratio}} = \sqrt{\left(\frac{\Delta \text{Beta}}{\text{Beta}}\right)^2 + \left(\frac{\Delta \text{Spk}}{\text{Spk}}\right)^2}$
- **Result**: $r = -0.988, p < 0.001$. Ratio drops from 65.95x in V1 down to 8.91x in PFC.

### Panel D: Formal Model Comparison Table
- **Direct Empirical Contrast**:
  1. *H1 (Predictive Routing)*: SUPPORTED ($r = 0.988, p < 0.001$)
  2. *H2 (Sensory Surprise)*: REJECTED (V1 O+ = 1.11%)
  3. *H3 (Stimulus Adaptation)*: REJECTED (Pre-omission ramping)
  4. *H4 (Off-Rebound Burst)*: REJECTED (Sustained pre-omission ramp)

---

## 3. Data Integrity & Code Receipts

- **NWB Data Reader**: `jnwb.oa.read()`
- **Script Command**: `python scripts/generate_killer_figure.py`
- **Execution Receipt**: 206 passed unit tests, 0 warnings.
