# poster-01: neural dynamics during omission support spectral aspects of the predictive routing model

**Authors**: Hamed Nejat, Yihan (Sophy) Xiong, Kaitlyn M. Gabhart, André M. Bastos  
**Affiliations**: Dept. of Psychology, Vanderbilt University (1); Vanderbilt Brain Institute (2)  
**Lab**: Bastos Lab  

---

## overview

This poster presents multi-area dense laminar neurophysiological evidence that **visual stimulus omission drives strong low-frequency spectral modulation across the cortical hierarchy**, while leaving MUA (multi-unit activity) largely unaffected in lower-order sensory cortex. Results support the Predictive Routing Model, in which alpha/beta oscillations carry top-down predictions and gamma carries feedforward sensory error signals.

---

## section 1 — background: predictive routing

Unpredictable context in cortex produces:
- Increased spiking activity (+MUA/SUA)
- Increased gamma (~40Hz+) spectral power
- Decreased alpha/beta (8–30Hz) spectral power

A conceptual diagram shows two cortical columns (A and B) with labeled gamma spiking layers and alpha/beta layers. Predictive vs. unpredictable conditions are contrasted. The key open question posed: *"Lack of the expected sensory input (omission) in the cortex (?)"*

---

## section 2 — sequential visual omission paradigm

The poster depicts the task structure:
- **Common trial**: 4 sequential grating presentations (S1–S4)
- **Omit control**: one of S2, S3, or S4 is omitted (gray screen, luminance-matched)
- **Block A (2022B)**: Predictive sequences — AAAB pattern
- Conditions include:
  - Predictive AAAB (standard)
  - Predictive omission sequences (AXAB, AAXB, AAAX)
  - Random RRRR (control)
  - Random omission sequences (RXRR, RRXR, RRRX)

Visual stimuli are circular drifting gratings (45° and 135°). Background is luminance-matched gray throughout — omissions are invisible from photometry.

---

## section 3 — multi-area dense laminar neurophysiology

Recording sites span **11 cortical areas** with linear silicon probes:
- **High-order/executive**: PFC, LPFC (8a/FEF)
- **Mid-order visual**: V3A, V3D, TEO, MST, MT
- **Low-order visual**: V2, V1, V4, FST

| Area | Channels | MUA responses |
|------|----------|--------------|
| PFC  | NE24     | ~330         |
| LPFC | —        | ~300         |
| TEO  | 387      | ~300         |
| MST  | 384      | ~420         |
| MT   | 512      | ~−150        |
| V3A  | 512      | ~−150        |
| V3   | 312      | ~−300        |
| V1   | 1382     | ~−1380       |
| **Total** | ~692 | ~−5610 |

A brain schematic (top-down and lateral) shows anatomical layout of recording sites color-coded by area.

---

## section 4 — omission does not affect MUA in lower-order sensory cortex

Multi-panel figure showing **MUA traces and TFRs** across conditions (Visual stim, S2/X2, S2/X3, S4/X4) for V1, MT, and FEF:
- V1 and MT show **no significant MUA change** during the omission window
- FEF (higher-order) shows a **time-specific, weak omission response** in MUA
- Interpretation: The omission signal is not primarily encoded in spiking rates of lower sensory areas; spectral/oscillatory dynamics carry the signal

---

## section 5 — time-frequency response (TFR) during omission: strong low-frequency modulation across the cortical hierarchy

**Central and largest figure on the poster.**

- X-axis: −1000ms to +1500ms relative to stimulus 1 onset (p1 = 0ms)
- Timeline markers: Visual stim → Delay → **Omission** (pink/shaded region) → Delay
- Each row = one brain area (V1 top, PFC bottom)
- Each colored trace = one frequency band or condition

**Key observations**:
- During the omission window: **pronounced increase in low-frequency power** (alpha/beta, ~8–30Hz) across all areas
- This effect is **hierarchically graded**: stronger in higher-order areas (FEF, PFC)
- Gamma power (~40Hz+) shows **no consistent increase** during omission
- The low-frequency modulation begins ~100–200ms after the expected stimulus onset and persists through the delay

---

## section 6 — spectral interactions not consistently correlated or aligned in hierarchy

Four sub-panels show inter-area spectral power correlation matrices (11×11 heatmaps):

1. **Stimulus window spectral power correlation**: high positive correlations across most area-pairs during stimulus; gamma-dominant network visible
2. **Omission window spectral power correlation**: correlation structure changes; beta/alpha dominant
3. **Gamma-beta dissociation during omission context**: separate gamma and beta networks emerge; not hierarchically ordered
4. **Spectral power correlation has the least change in FEF/PFC**: bar chart showing R² change across areas — FEF/PFC are most stable spectral nodes

Two circuit diagrams:
- **Beta network (omission)**: highlight of areas with increased beta connectivity during omission
- **Gamma network (stimulus)**: highlight of areas with increased gamma connectivity during stimulus

---

## section 7 — spectral tuning: global control on local microcircuits?

Circuit schematic with V1, MT, and FEF/V3A as nodes:
- Feedforward (gamma) pathways shown as upward arrows
- Feedback (alpha/beta) pathways shown as downward arrows
- Proposes that omission-driven beta synchrony in higher-order areas may globally suppress gamma in lower areas via feedback — "global control on local microcircuits"
- Open question: is spectral tuning hierarchically organized or area-specific?

---

## section 8 — conclusions

1. Bottom-up visual omission **significantly influences spectral power throughout the cortical hierarchy**
2. Spectral responses induced by omission are **pervasive across the entire cortical hierarchy**
3. Omission triggers **low-frequency oscillatory interactions**, supporting the predictive routing model
4. Spectral correlation reflects **frequency-specific sub-networks** across the cortical hierarchy — gamma during prediction, beta during omission

---

## section 9 — acknowledgements

Supported by NIMH-R00MH116100 (ANB), Vanderbilt science funds (AMB), Vanderbilt graduate NIH training grants. Behavioral training and experimental procedures approved by Vanderbilt University Institutional Animal Care and Use Committee (IACUC).

---

## key technical parameters (from poster)

| Parameter | Value |
|-----------|-------|
| Recording type | Dense laminar neurophysiology (linear probes) |
| Brain areas | 11 (V1, V2, V4, MT, MST, TEO, FST, V3A, V3D, FEF, PFC/LPFC) |
| Total channels | ~692 |
| TFR analysis window | −1000 to +1500ms re p1 onset |
| Omission window | ~1531ms (d1-to-d2 equivalent) |
| Frequency range | ~1–100Hz (alpha/beta: 8–30Hz, gamma: 40Hz+) |
| Conditions | Predictive (A/B blocks) + Random — with omissions at S2, S3, S4 |
