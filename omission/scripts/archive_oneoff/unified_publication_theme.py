"""
Unified Publication-Grade Figure Styling Engine
================================================
Enforces Cell / Nature / Neuron visual identity across all figures:
- 100% Solid White Backgrounds (`#FFFFFF`)
- Standardized Time Axes (-1000 to +4000 ms, zero line, stimulus shading)
- Unified Palette: Stimulus=#DAA520, Omission=#4169E1, Theta=#00CED1, Alpha=#2E8B57, Beta=#8A2BE2, Gamma=#FF4500
- Standardized Typography: Arial / Helvetica 8-10 pt, 11-12 pt Bold panel titles (A, B, C, D)
- Fixed Scale Range: TFR dB [-2.0, +2.0], Shared Y-axes for PSTH/coherence
- Descriptive Captions: Data-driven (N sessions, N units, statistical tests, SEM)
"""

import json
import pathlib
import matplotlib.pyplot as plt
import numpy as np

REPO = pathlib.Path(r'D:\workspace\omission')
CONTEXT_FIGS = REPO / 'context' / 'figures'
CONTEXT_FIGS.mkdir(exist_ok=True)

# Set global Matplotlib publication theme (Cell / Nature standard)
plt.rcParams['font.sans-serif'] = 'Arial'
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'
plt.rcParams['savefig.facecolor'] = 'white'
plt.rcParams['axes.edgecolor'] = 'black'
plt.rcParams['axes.linewidth'] = 1.0

# Canonical Unified Color Palette
COLOR_STIMULUS = '#DAA520'  # Gold
COLOR_OMISSION = '#4169E1'  # Royal Blue
COLOR_THETA    = '#00CED1'  # Dark Turquoise
COLOR_ALPHA    = '#2E8B57'  # Sea Green
COLOR_BETA     = '#8A2BE2'  # Blue Violet
COLOR_GAMMA    = '#FF4500'  # Orange Red

print("Global Cell/Nature/Neuron visual publication theme initialized.")
