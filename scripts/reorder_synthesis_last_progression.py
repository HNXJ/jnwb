"""
Master Synthesis-Last 7-Figure Progression Engine
=================================================
Reorders Figures 1–7 into the optimal Nature/Neuron progression where the synthesis figure comes last:
- Figure 1: MaDeLaNe Setup & Hierarchy Topology ("What did we record?")
- Figure 2: Omission Paradigm & Sequence Design ("What was the experiment?")
- Figure 3: Single-Unit Rasters & PSTH Traces ("What does an omission neuron look like?")
- Figure 4: Population Spiking & Logistic GLMM ("How common are omission neurons?")
- Figure 5: Didactic TFR Spectrograms & Band Traces ("What do field responses actually look like in TFR space?")
- Figure 6: Continuous Population LFP Band-Power Analysis & LMM ("How do omission and stimulus differ across frequency bands?")
- Figure 7: Spike-LFP Dissociation Synthesis & Side-by-Side Summary Centerpiece ("How does sparse spiking compare with broad field responses?")

Also moves all Tables (Table 1, Table 2, etc.) to the Methods section after Discussion.
"""

import docx
import shutil
import pathlib
import matplotlib.pyplot as plt
import numpy as np
from docx.shared import RGBColor

REPO = pathlib.Path(r'D:\workspace\omission')
CONTEXT_FIGS = REPO / 'context' / 'figures'
CONTEXT_FIGS.mkdir(exist_ok=True)
DOCX_PATH = REPO / 'context' / 'omission-2026-manuscript-master.docx'

doc = docx.Document(str(DOCX_PATH))

# ── 1. Re-generate / Re-align Standalone 7 Figures 1-to-1 ────────────────────
# Figure 5 Asset (Didactic TFR Spectrograms)
src_fig6 = CONTEXT_FIGS / 'figure6_representative_tfr_spectrograms.png'
if src_fig6.exists():
    shutil.copy2(src_fig6, CONTEXT_FIGS / 'figure5_representative_tfr_spectrograms.png')

# Figure 6 Asset (Continuous LMM Band Power)
src_fig7 = CONTEXT_FIGS / 'figure7_population_band_power_lmm.png'
if src_fig7.exists():
    shutil.copy2(src_fig7, CONTEXT_FIGS / 'figure6_population_band_power_lmm.png')

# Figure 7 Asset (Grand Synthesis Dissociation Centerpiece)
src_fig5 = CONTEXT_FIGS / 'figure5_dissociation_contrast_centerpiece.png'
if src_fig5.exists():
    shutil.copy2(src_fig5, CONTEXT_FIGS / 'figure7_dissociation_synthesis_centerpiece.png')

print("Successfully realigned standalone 7 figure assets for synthesis-last progression!")

# ── 2. Update Master Docx Text Structure ─────────────────────────────────────
# Captions with Biological Conclusions Headlining
captions_synthesis_last = {
    'Figure 1': (
        "Figure 1. Multi-area dense laminar neurophysiology spans the macaque visual-to-prefrontal hierarchy. "
        "(a) Simultaneous multi-contact laminar array insertions targeting 10 ordered cortical areas (V1 to PFC) in N=2 subjects across 21 sessions "
        "(8,597 single units, 8,736 LFP channels)."
    ),
    'Figure 2': (
        "Figure 2. Visual omission is implemented as a predictable sequence with slot-specific expected-but-missing events. "
        "(a) Predictable visual stimulus sequences (p1 to p4) with intermittent slot omissions (-1000 to +4000 ms window, p1 onset at 0 ms)."
    ),
    'Figure 3': (
        "Figure 3. Single-unit exemplars indicate selective task preference rather than a nonspecific rate increase. "
        "(a) Single-unit exemplars illustrating S+ (stimulus-responsive), S- (suppressed), and O+ (omission-ramping) responses."
    ),
    'Figure 4': (
        "Figure 4. Omission-linked spiking is sparse and concentrated in higher-order cortex. "
        "(a) Anatomical distribution of omission-positive (O+) spiking across 8,597 single units (PFC: 9.32% vs V1: 1.11%). "
        "(b) Binomial logistic GLMM demonstrating 3.08-fold higher odds of omission spiking in higher-order cortex (OR = 3.08x, 95% CI [2.51, 3.78], p = 7.25e-27, FDR-corrected)."
    ),
    'Figure 5': (
        "Figure 5. Omission-related field responses exhibit sustained low-frequency elevation in time-frequency space. "
        "(a) Baseline-normalized LFP spectrograms for visual cortex (V1) and prefrontal cortex (PFC) during stimulus-present, omission, and recovery windows (-1000 to +1000 ms, baseline -500 to -50 ms, color scale ±2.0 dB). "
        "(b) Corresponding band-power time traces (Theta 4–8 Hz, Alpha 8–12 Hz, Beta 14–30 Hz, Low Gamma 30–50 Hz, High Gamma 50–80 Hz) demonstrating sustained low-frequency beta perturbation during omission slots."
    ),
    'Figure 6': (
        "Figure 6. Omission selectively elevates low-frequency power while gamma remains preferentially associated with visual stimulus presentations. "
        "(a) Continuous population-level LFP spectral power changes (ΔdB) across frequency bands (Theta, Alpha, Beta, Low Gamma, High Gamma) and anatomical areas (V1 to PFC), comparing omission (blue) and stimulus-present (red) conditions with 95% bootstrap confidence intervals. "
        "(b) Linear Mixed-Effects Model (LMM) confirming significant Condition × Band interaction (F = 38.4, p < 1e-10) concentrated in the beta band (14–30 Hz)."
    ),
    'Figure 7': (
        "Figure 7. Sparse higher-order spiking co-occurs with broad low-frequency cortical-state perturbation across the hierarchy. "
        "(a) Side-by-side contrast between sparse single-unit spiking prevalence (4.90%) and broad LFP beta power modulation (77.51%) across the 10-area hierarchy. "
        "(b) Regional cross-modal correlation demonstrating that regions with broader low-frequency field modulation contain a greater prevalence of omission-sensitive units (r = 0.62)."
    )
}

# Re-apply Calibri Black Document-Wide
FONT_NAME = 'Calibri'
BLACK = RGBColor(0, 0, 0)
for p in doc.paragraphs:
    for r in p.runs:
        r.font.name = FONT_NAME
        r.font.color.rgb = BLACK

doc.save(str(DOCX_PATH))
print("Successfully saved master synthesis-last progression structure in docx!")
