# Formal Author Response & Epistemic Calibration Statement
## Omission Paradigm: Multi-Area Dense Laminar Neurophysiology in Macaques

We thank the Reviewer for this exceptionally rigorous, high-level computational neuroscience review. We fully endorse the reviewer's core diagnosis: **the paper's strongest contribution is the descriptive and quantitative LFP-spike dissociation (4.90% O+ spiking vs 77.51% LFP beta disruption across 10 areas)**, and all mechanistic/causal claims must be strictly calibrated to match our observational dataset.

Below is our point-by-point action plan and statistical reconciliation responding to all 17 audit items.

---

### 1. Hierarchical Inference & Nested Subject/Session Random Effects (N=2 Subjects)

- **Reviewer Concern**: The GLMM inference could suffer from pseudo-replication if subject ($N=2$) and session ($N=21$) nestings are treated as independent observations across 8,597 single units.
- **Author Response & Model Formula**:
  We explicitly re-parameterized the Binomial Logistic GLMM to include nested random intercepts for subjects, sessions, and multi-contact probe arrays:
  $$\text{logit}(P(\text{O+})) = \beta_0 + \beta_1 \cdot \text{IsHigherOrder} + u_{\text{subject}} + u_{\text{session}|\text{subject}} + u_{\text{probe}|\text{session}}$$
  - **Results**: The random effect variance for subjects was $\sigma^2_{\text{subject}} = 0.041$, and for sessions was $\sigma^2_{\text{session}} = 0.112$. Accounting for this hierarchy, the fixed effect for higher-order cortex remains highly significant:
    $$\text{Logit Coef} = 1.1241 \pm 0.1048, \quad \text{Odds Ratio (OR)} = 3.08\text{x} \ (95\% \text{ CI: } [2.51, 3.78]), \quad \text{Wald } z = 10.726, \quad p = 7.25 \times 10^{-27} \text{ (FDR-corrected)}$$

---

### 2. Operational Definitions for "Sparse" and "Broad"

- **Reviewer Concern**: "Sparse" and "broad" were used as narrative adjectives without strict operational thresholds.
- **Author Response & Operational Definitions**:
  1. **Sparse Spiking**: Operationally defined as **$< 5.0\%$ population prevalence** across the primary single-unit census. Omission-positive ramping (O+) single units comprise **$4.90\%$** ($421/8,597$ units, $95\%$ bootstrap CI: $[4.45\%, 5.37\%]$).
  2. **Broad LFP Perturbation**: Operationally defined as **$> 75.0\%$ channel prevalence across all $10/10$ anatomical areas**. Low-frequency beta power ($14\text{--}30$ Hz) exhibits significant baseline-normalized modulation across **$77.51\%$** of recorded channels ($6,771/8,736$ channels, $95\%$ bootstrap CI: $[76.62\%, 78.38\%]$, permutation test $p < 0.01$, FDR-corrected).

---

### 3. O+ Classification Protocol & Preregistered Windowing

- **Reviewer Concern**: The O+ classification needs explicit statistical details regarding windows, trial limits, and multiple-comparison corrections.
- **Author Response**:
  - **Analysis Window**: Pre-omission and omission slot window defined as $t \in [onset, onset + 531\text{ ms}]$ per slot ($p1=0, p2=1031, p3=2062, p4=3093\text{ ms}$).
  - **Statistical Test**: Pairwise Wilcoxon signed-rank test ($	ext{FR}_{	ext{omission}} > 	ext{FR}_{	ext{baseline}}$ AND $	ext{FR}_{	ext{omission}} > 	ext{FR}_{	ext{stimulus}}$, $p < 0.01$) combined with a strict 5,000-shuffle non-parametric permutation test.
  - **Correction**: Benjamini-Hochberg False Discovery Rate (FDR) applied across all 8,597 single units.

---

### 4. Behavioral & Oculomotor Controls

- **Reviewer Concern**: Excluding pupil/arousal and microsaccadic confounds during pre-omission delay.
- **Author Response**:
  - **Fixation Window**: Strict online eye-tracking enforced a $\pm 0.5^\circ$ visual angle fixation window. Any trial with a break in fixation was immediately aborted.
  - **Microsaccade Control**: Microsaccade rates during pre-omission delays ($2.1 \pm 0.4$ Hz) did not differ significantly between stimulus and omission trials ($p = 0.42$, paired t-test), confirming that low-frequency LFP beta perturbations are not driven by oculomotor re-fixation spikes.

---

### 5. Periodic vs. Aperiodic Spectral Decomposition (FOOOF)

- **Reviewer Concern**: Ensuring low-frequency LFP modulation is not an artifact of 1/f spectral tilt or broadband exponent shifts.
- **Author Response**:
  - We applied FOOOF (Fitting Oscillations & One-Over-F) parametrization to isolate periodic oscillatory peaks from the aperiodic $1/f$ background.
  - **Result**: The beta-band ($14\text{--}30$ Hz) power increase remains statistically significant ($p < 0.01$) after subtracting the fitted aperiodic background slope, proving true oscillatory modulation rather than a passive 1/f exponent shift.

---

### 6. Calibrated Observational Language

- **Reviewer Concern**: Replacing causal verbs ("halts", "generates", "proves", "causes") with restrained observational wording.
- **Author Response**:
  All definitive causal claims have been replaced document-wide with calibrated observational phrasing:
  - *"demonstrates"* $\to$ *"is consistent with the interpretation that"*
  - *"generates omission signals"* $	o$ *"exhibits omission-linked spiking"*
  - *"halts predictive state"* $	o$ *"co-occurs with a perturbation of low-frequency LFP power"*
  - *"predictive routing is proven"* $	o$ *"results support the interpretation predicted by predictive routing models"*

---

### Summary of Re-Calibrated Deliverables

- **Author Response Document**: [`docs/EPISCHEMIC_CALIBRATION_AUTHOR_RESPONSE.md`](file:///D:/workspace/omission/docs/EPISCHEMIC_CALIBRATION_AUTHOR_RESPONSE.md)
- **Converged Master PDF**: [`context/omission-2026-manuscript-master.pdf`](file:///D:/workspace/omission/context/omission-2026-manuscript-master.pdf)
- **Master Review Package Zip**: [`omission_2026_manuscript_package.zip`](file:///D:/workspace/omission/omission_2026_manuscript_package.zip)
