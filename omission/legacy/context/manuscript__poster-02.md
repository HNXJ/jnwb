# poster-02: omission reveals the functional role of neuronal oscillations in predictive routing

**Authors**: Hamed Nejat, Yihan (Sophy) Xiong, Jacob A. Westerberg, André M. Bastos  
**Affiliations**: Dept. of Psychology, Vanderbilt University (1); Vanderbilt Brain Institute (2); Dept. of Vision and Cognition, Netherlands Institute for Neuroscience, Amsterdam, Netherlands (3)  
**Lab**: Bastos Lab  

---

## overview

This poster presents a more mature, refined version of the omission study. It adds **single-neuron characterization**, demonstrates that **omission disinhibits expected spiking in a small subset of higher-order neurons (~N=20)**, and establishes that omission **pushes the cortical LFP toward a beta-band spectral harmony** — a shift from gamma-dominated stimulus processing to beta-dominated prediction maintenance. International collaboration with Netherlands Inst. for Neuroscience is reflected.

---

## section 1 — background: predictive routing

For local-field potential (LFP) and neuronal spiking in the cortex:
- **Feedforward signals** carry sensory information through **gamma (~40Hz)** oscillations
- **Feedback signals** carry predictions through **alpha/beta (~8–30Hz)** oscillations
- **More informative context** enhances alpha/beta → inhibits feedforward gamma
- **Predictable context** suppresses feedforward signal via alpha/beta gating

Conceptual diagram shows two cortical columns (A and B). Each column has:
- Superficial gamma spiking layers (feedforward)
- Deep alpha/beta layers (feedback/prediction)
- Bidirectional inter-column arrows

**Key question posed**: *"What happens if the expected sensory input is missing? (Omission)"*

---

## section 2 — sequential visual omission paradigm

Identical paradigm to Poster 1:
- **Common trial**: 4 sequential drifting gratings (S1–S4), ~531ms presentation, ~500ms inter-stimulus delay
- **Omit**: one stimulus replaced by gray screen (luminance-matched — no photodiode change)
- **Conditions**:
  - Common/standard: AAAB, BBBA, RRRR
  - Omission: AXAB, AAXB, AAAX (predictive); RXRR, RRXR, RRRX (random)

---

## section 3 — multi-area dense laminar neurophysiology

Same 11-area recording layout as Poster 1. Brain schematic shows:
- Top-down view with **contour plots** (colored ellipses) marking recording locations for each session
- Areas: 8a/FEF, LPFC, V3D, V3/A, V3, V2, V1, V4, FST, MST, MT, TEO
- Recording table with approximate channel counts and MUA response magnitudes
- Session-by-session electrode placement variability visible as overlapping contours

---

## section 4 — omission dampens low-frequency oscillations without changing gamma power (LFP, relative to baseline)

**The central and largest figure of this poster.**

- X-axis: −1000ms to +1000ms relative to visual stimulus 1 onset (p1 = 0ms)
- Timeline markers: Visual stim (red) → Delay → **Omission** (purple/shaded) → Delay
- Each row = one recording area, from V1 (top) to PFC (bottom)
- Multiple colored traces per area = different conditions (RXRR, RRXR, RRRX; each with distinct color)

**Key findings**:
- **Red arrows** point to **significant DECREASES in low-frequency (theta/alpha/beta) power** across all areas during the omission window
- **Gamma (~40Hz+) power remains stable** — does not increase, does not decrease
- The low-frequency dampening is:
  - **Widespread**: present from V1 through PFC
  - **Band-specific**: selective to theta/alpha/beta, sparing gamma
  - **Hierarchically amplified**: effect larger in higher-order areas (FEF, PFC)
- Caption states: *"Omission appears as widespread but band-specific changes in theta, alpha and beta power across the hierarchy"*

---

## section 5 — few higher-order single neurons respond to omission with significant increase in spiking activity

Three sub-panels showing population-level spiking statistics:

**N=2071 — neurons excited by stimulus** (largest group):
- Broad activation during stimulus presentations
- No significant change during omission window
- Bar chart shows % of these neurons per area

**N=1382 — neurons inhibited by stimulus**:
- Suppression during stimulus, rebound in delay
- Minimal omission response
- Area-wise distribution shown

**N=20 — correlated to omission** (key finding):
- A **small but consistent subset** (~20 neurons, predominantly in FEF/PFC/higher areas) shows significantly **increased spiking during the omission window**
- These are rare (~1% of responsive neurons)
- Bar chart shows these omission-selective neurons are concentrated in **higher-order cortex**

**Conclusion stated**: *"Higher order neurons control this low-frequency harmony"*

---

## section 6 — omission pushes the cortical LFP towards a spectral harmony in the beta band

**"More correlation in gamma during stimulus presentation, more in beta during omission"**

Sub-section contains 11×11 inter-area LFP correlation matrices (heatmaps) computed separately for:
- **Theta band** (stimulus vs. omission window)
- **Alpha band** (stimulus vs. omission window)
- **Beta band** (stimulus vs. omission window)
- **Gamma band** (stimulus vs. omission window)

**Key pattern**:
| Window | Gamma | Beta |
|--------|-------|------|
| Stimulus | High (+) correlation | Low (−) correlation |
| Omission | Low (−) correlation | High (+) correlation |

This "spectral flip" — from gamma-coherent network during stimulus to beta-coherent network during omission — is the central spectral finding.

**Two network diagrams**:
- **Beta network (omission)**: sparse, high-order dominated, hierarchical (PFC → FEF → MT/V1)
- **Gamma network (stimulus)**: denser, bidirectional, sensory-area dominated

Summary bar chart: **averaged beta/gamma correlation strength** across areas during stimulus vs. omission — confirming the significant swap in dominant spectral coupling mode.

---

## section 7 — lack of the expected signal with omission disinhibits the expected spiking

Circuit schematic explaining the mechanism:

- V1 → FEF feedforward (via gamma)
- FEF → V1 feedback (via alpha/beta) → **inhibits feedforward spiking**
- During **omission**: bottom-up gamma signal absent → feedback inhibition is not triggered → **disinhibition** of the feedforward pathway
- The N=20 omission neurons in FEF may be those detecting the prediction error and releasing the beta-mediated inhibition

Circuit components:
- Excitatory connections (arrows)
- Inhibitory interneurons (circles)
- Prediction signal nodes
- "Higher order area" label with V1 and FEF nodes

Caption note: *"Few higher order neurons control this low-frequency harmony across the cortex(!)"*

---

## section 8 — conclusions

1. **Spiking activity during omission is not increasingly informative** — the majority of neurons (~N=2071+1382) do not change their firing during omission
2. A significant fraction of neurons maintain activity similar to baseline (non-responsive to omission)
3. **Few neurons (N~20)** have finely tuned spiking activity specifically correlated to the omission
4. **Omission has the most significant impact on LFP oscillatory dynamics**, not spiking rates
5. **Oscillatory power correlation** shifts from the gamma-band network (during stimulus) to the **beta-band network during omission** — the spectral harmony reorganizes around prediction maintenance

---

## section 9 — acknowledgements

- F-31 NIMH; T32 training grants; Odyssey 2540, 338-297; Orion 0609-2493
- Vanderbilt Zions — since 2506; Vanderbilt graduate school funds (MF)
- Behavioral training and experimental procedures approved by Vanderbilt University IACUC

---

## comparison with poster 01

| Aspect | Poster 01 | Poster 02 |
|--------|-----------|-----------|
| International authors | No | Yes (Westerberg, Netherlands) |
| Focus | Spectral power changes during omission | Spectral harmony shift + single-neuron characterization |
| MUA result | No change in low-order cortex; weak FEF response | N~20 omission-selective neurons in high-order cortex |
| Main spectral claim | Low-frequency increases during omission | Beta-band synchrony coheres during omission; gamma during stimulus |
| Circuit model | Global spectral control via feedback | Disinhibition mechanism via beta feedback gating |
| Correlation matrices | Gamma-beta dissociation per area | Full theta/alpha/beta/gamma spectral harmony reorganization |
| TFR x-axis | −1000 to +1500ms | −1000 to +1000ms |

---

## key technical parameters

| Parameter | Value |
|-----------|-------|
| Recording type | Dense laminar neurophysiology (linear probes) |
| Brain areas | 11 (V1, V2, V4, MT, MST, TEO, FST, V3A, V3D, FEF, PFC/LPFC) |
| TFR analysis window | −1000 to +1000ms re p1 onset |
| Omission window | ~1531ms contextual window |
| Frequency range displayed | ~1–100Hz |
| Single-unit sample | N=2071 stim-excited, N=1382 stim-inhibited, N=20 omission-correlated |
| Baseline reference | Relative to fixation period (dB change) |
| Conditions | Predictive (A/B blocks) + Random, omissions at S2/S3/S4 |
