# Omission Project Overview

This document consolidates high-level summaries, subject inventories, experimental paradigms, oculomotor controls, and data availability.

---

## Project Purpose
The **Omission** project is a neurophysiological investigation into the neural representations of predicted but absent stimuli (omissions). By recording from multiple areas across the visual and prefrontal cortical hierarchy, we isolate "ghost signals" that reflect the brain's internal model, free from sensory input.

---

## High-Level Scientific Questions
1. **Hierarchical Evolution**: How does the representation of an omitted stimulus evolve as it moves up the cortical hierarchy (V1 → V2 → V3 → V4 → MT → MST → TEO → FST → FEF → PFC)?
2. **Laminar Signatures**: What are the laminar-specific signatures (superficial vs. deep layers) of predictive feedback during omissions?
3. **Ghost Decoding**: Can we decode the identity of a missing stimulus from neural activity alone, and how does this decoding accuracy relate to behavioral performance and oculomotor "proxies" (pupil dilation, microsaccades)?

---

## Subject Inventory

The canonical subject population consists of the following rhesus macaques:
- **sub-C31o** (Primary male subject)
- **sub-V198o** (Secondary female subject)

---

## Behavioral Task Details
The experiment utilizes an Omission Paradigm with regular temporal structure to set up expectations.

### Omission Paradigm Sequence
1. **Fixation**: Subject fixates on a central dot.
2. **Sequence Presentation**: A sequence of stimuli (e.g., A-A-A-B or B-B-B-A) is presented.
3. **Omission Trial**: On a subset of trials (approx. 20%), a predicted stimulus in the sequence is omitted (replaced by blank screen).
4. **Window of Analysis**: Spiking and LFP activity are analyzed during the omission window (0 to 1000ms relative to expected onset) to identify predictions.

---

## Oculomotor & Behavioral Controls
To ensure neural predictive signals are not oculomotor artifacts:
- **Pupil Dilation**: Tracked to account for arousal-state fluctuations.
- **Microsaccades**: Detected using Velocity-Threshold Identification (Engbert & Kliegl) to clean spiking windows.
- **Degree of Visual Angle (DVA)**: Strict threshold (DVA < 0.5°) enforced for central fixation.

---

## Data Availability
- **NWB Location**: The canonical `.nwb` sessions reside on local neuroscientific workstations at `D:/analysis/nwb/`.
- **Precomputed TFRs**: Channel-by-channel multitaper Time-Frequency representations are stored as `.npy` arrays at `D:/workspace/data/tfr_arrays/`.
