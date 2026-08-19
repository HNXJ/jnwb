# Task Details: Sequential Visual Omission Task

## 🧠 Task setup
- **Behavioral controller**: We used MonkeyLogic (developed and maintained at the National Institute for Mental Health) to control the behavioral task. 
- **Visual stimuli information**: Visual stimuli were displayed using PROPixx Pro projectors (VPixx Technologies, Quebec, Canada) with a resolution of 1920 x 1080 at a 120 Hz refresh rate. The projector screen was positioned 57 cm in front of the monkey’s eyes. Luminance calibration was performed with a Photo Research PR-650 at the projector screen with a median value of 2.613 cd/m2.

## Important terms
- **Objective**: To receive reward, maintain eye-fixation for ~4500ms on the small white fixation point at the center of the screen.
- **Correct trials**: Trials in which the subject maintained eye fixation from the onset of the trial until its end.
- **No report**: The subject does not report the context. Only active behavior is eye fixation.
- **Visual stimuli**: A circular moving grating with 2Hz moving temporal frequency (much less than the screen refresh rate of 120Hz).
- **Visual stimulus A**: 45-degree rotated moving grating
- **Visual stimulus B**: 135-degree rotated moving grating
- **Background**: Background is always a plain gray screen with the luminance similar to the visual stimulus itself, such that the total luminance stays the same throughout the session.
- **Omission**: In this task, only in omission conditions, one of the presentations p2-4 is omitted from the sequenced. The important thing is that in the point of view of the subject, The screen is the same during initial fixation, inter-stimulus intervals, omissions, delays. 


## 🧠 Neural Representation of Internal Models
This project investigates the biological implementation of **Active Inference** in the primate brain by auditing the internal "generative model" during violations of temporal expectations.

- **The "Ghost" Signal (Contextual Persistence)**: The task features a **1531ms window** where the visual input (gray screen) is physically identical between conditions (e.g., `d1-p2-d2` in RRRR vs. RXRR). However, the neuronal activity diverges based on the internal expectation of a stimulus. We are measuring the brain's ability to generate "Something" (a prediction error or persistent model state) from "Nothing."
- **Multi-Scale Signal Integration**:
    - **SPK (Single-Units)**: Kilosort 2.5 identified neurons serving as the computational nodes for omission-specific encoding.
    - **MUAe (Multi-Unit Activity Envelope)**: Enveloped high-frequency (>1000Hz) signals representing the robust local population response.
    - **LFP (Local-Field Potential)**: Capturing the regional field dynamics used to dissociate top-down predictions (Gamma/Beta) from bottom-up errors.
- **Cortical Hierarchy Audit**: Our dataset spans 11 brain areas across three functional tiers:
    - **Low-Order Visual**: V1, V2.
    - **Mid-Order Visual**: V4, MT, MST, TEO, FST.
    - **High-Order / Executive**: FEF, PFC.
  This allows us to map the **Propagation of Surprise** and determine the latency of the "Neural Surprise" as it travels from sensory areas to frontal control regions.
- **Precision Scaling & Quenching**: By analyzing the stimulus presentation *immediately following* an omission (e.g., `p3` after `omit_p2`), we test the hypothesis that the brain "tightens" its predictive precision after a surprise, resulting in reduced neural variability (enhanced quenching) and more reliable encoding.

## 🔄 Condition Groups
- **AAAB**: Frequent sequence of Blocks-1-2 (Block A) with ~70% probability; All four presentations (A-A-A-B) in order
- **AXAB**: Rare sequence of Block-1 with ~10% probability; Second presentation was omitted (A-X-A-B) are presented in order 
- **AAXB**: Rare sequence of Block-1 with ~10% probability; Third presentation was omitted (A-A-X-B) are presented in order
- **AAAX**: Rare sequence of Block-1 with ~10% probability; Fourth presentation was omitted (A-A-A-X) are presented in order
- **BBBA**: Frequent sequence of Blocks-3-4 (Block B) with ~70% probability; All four presentations (B-B-B-A) in order
- **BXBA**: Rare sequence of Block-2 with ~10% probability; Second presentation was omitted (B-X-B-A) are presented in order 
- **BBXA**: Rare sequence of Block-2 with ~10% probability; Third presentation was omitted (B-B-X-A) are presented in order
- **BBBX**: Rare sequence of Block-2 with ~10% probability; Fourth presentation was omitted (B-B-B-X) are presented in order
- **RRRR**: Frequent sequence of Block-5 (Random control A/B) with ~40% probability; All four presentations (R-R-R-R) in order
- **RXRR**: Rare sequence of Block-3 with ~20% probability; Second presentation was omitted (R-X-R-R) are presented in order 
- **RRXR**: Rare sequence of Block-3 with ~10% probability; Third presentation was omitted (R-R-X-R) are presented in order
- **RRRX**: Rare sequence of Block-3 with ~30% probability; Fourth presentation was omitted (R-R-R-X) are presented in order

## 🔬 Electrophysiological Signal Notes
- **NWB Alignment Reference**: The "Golden Standard" for alignment in these NWB files is **Code 101.0** (onset of Presentation 1). Aligning to the trial's global `start_time` can lead to jitter or drifts depending on the block type.
- **Physiological Lag**: In V1, the first significant peak in firing rate occurs **40-60ms after the Photodiode jump**. This lag is consistent across sessions and serves as a primary validity check for temporal synchronization.
- **Data Export Window**: Our standardized 6000ms window uses a **1000ms pre-stimulus buffer** (relative to Code 101.0). 
  - **Sample 1000**: Absolute onset of Stimulus 1.
  - **Samples 0-1000**: Pre-stimulus baseline (including fixation).
- **Luminance and Omission**: Because the background is luminance-matched to the stimuli, the Photodiode signal remains flat during omissions. The omission response is therefore entirely internal (prediction error) and not sensory-driven.

## 🌊 Screen status and timing flow of each condition as a sequence

The following table represents the task flow.


**Keys**: `A/B` = Stimulus Identity | `R` = Random Stimulus A or B | `x` = Omission |
`rw` = Reward | `fx`: Fixation | `p1-4`: Presentation 1-4 |
`d1-4`: Delay 1-4 | `efx`: End of Fixation | `rw`: Reward |

| Time | -500 | | 0 | | 531 | | 1031 | | 1562 | | 2062 | | 2593 | | 3093 | | 3624 | | 4124 | |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Context** | **fx** || **p1** || **d1** || **p2** || **d2** || **p3** || **d3** || **p4** || **d4** || **efx** | **rw** ||
| | ||||||||||||||||||||||||
| **AAAB**     | || A || || A || || A || || B || || | rw ||
| **AXAB**     | || A || || x || || A || || B || || | rw ||
| **AAXB**     | || A || || A || || x || || B || || | rw ||
| **AAAX**     | || A || || A || || A || || x || || | rw ||
| **BBBA**     | || B || || B || || B || || A || || | rw ||
| **BXBA**     | || B || || x || || B || || A || || | rw ||
| **BBXA**     | || B || || B || || x || || A || || | rw ||
| **BBBX**     | || B || || B || || B || || x || || | rw ||
| **RRRR**     | || R || || R || || R || || R || || | rw ||
| **RXRR**     | || R || || x || || R || || R || || | rw ||
| **RRXR**     | || R || || R || || x || || R || || | rw ||
| **RRRX**     | || R || || R || || R || || x || || | rw ||

---
*Updated by Gemini CLI with full condition variants and synchronized sequence timing.*
