# Omission Paradigm Task Specification

This document details the behavioral paradigm, experimental configuration, trial definitions, and subject session cohorts.

---

## 1. Experimental Task Configuration
The experimental paradigm is designed to study sensory prediction, expectation, and surprise using sequential stimulus presentations with randomly omitted slots.

### Stimulus Sequences
Stimuli are presented in structured sequences of four consecutive slots separated by fixed delay intervals:
* **Slots**: Stimulus 1 ($\text{S}_1$) $\rightarrow$ Stimulus 2 ($\text{S}_2$) $\rightarrow$ Stimulus 3 ($\text{S}_3$) $\rightarrow$ Stimulus 4 ($\text{S}_4$).
* **Omissions**: On a randomized subset of trials, the stimulus in one of the slots ($\text{p}_2$, $\text{p}_3$, or $\text{p}_4$) is physically omitted (replaced by silence or a blank screen), while keeping the temporal structure of the sequence intact.

---

## 2. Trial Type Conditions
Each trial is classified into one of four conditions based on whether and where an omission occurred:

1. **RRRR (Regular Sequence)**: No omissions occur. All 4 stimuli are presented.
2. **RXRR (Slot 2 Omission)**: The stimulus at slot 2 ($\text{p}_2$) is omitted.
3. **RRXR (Slot 3 Omission)**: The stimulus at slot 3 ($\text{p}_3$) is omitted.
4. **RRRX (Slot 4 Omission)**: The stimulus at slot 4 ($\text{p}_4$) is omitted.

---

## 3. Behavior and Performance Metrics
* **Correct Trials**: Trials where the subject correctly maintained fixation or responded in accordance with the task rules (e.g., licking or saccading during a specific target window, or ignoring omissions when trained to do so).
* **Incorrect Trials**: Trials where the subject broke fixation prematurely or committed a response error.
* **Trial Filtering**: Standard neural analysis filters for `correct_only=True` trials to control for attention and arousal states.

---

## 4. Subject Session Cohorts
Electrophysiology recordings are compiled across three primary cohorts of animal subjects, each recording dozens of visual and frontal brain areas simultaneously:

* **C31o Cohort**: Chronic high-density visual and frontal cortex recordings (visual areas V1, V2, V3, V4, MT, TEO, MST, and frontal areas PFC, FEF).
* **V182o Cohort**: High-density recordings with active visual-attention task modulation.
* **V198o Cohort**: Simultaneous laminar probes targeting visual hierarchy and feedback loops.
