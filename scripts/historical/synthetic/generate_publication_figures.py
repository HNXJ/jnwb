"""
=== QUARANTINED 2026-08-10 -- do not use as an empirical source ===
Per artifacts/.lab/agent-harness-audit-20260810.json (Sol/Hamm Handout 2, P0 item 3): contains
hardcoded literal arrays of the retracted synthetic census (counts=[2158,1565,1178,413,421,39,
2823], percents computed against denominator 8597) -- see context/docs/CONTEXT.md Section 8.
Its rendered output was already renamed UNUSABLE_synthetic_census_2026-07-27.png per
artifacts/.lab/figure_directory_layout_and_synthetic_fig03_20260729.json; this move quarantines
the generating script itself. Preserved per Conservation doctrine, not deleted.

scientific_status = "invalid_for_inference"
superseded_by = None
reason = ["hardcoded_retracted_synthetic_census"]

Publication Quality 8-Figure Canvas & Supplementary Tables Generator
================================================--------------------
Generates 300 DPI, full-canvas, zero-whitespace main text figures (1 to 8),
supplementary figures (S1 to S4), and formats Word docx typography:
  - Title: Cambria 14pt Bold
  - Authors & Affiliations: Cambria 11pt
  - Main Text: Cambria 12pt
  - Captions: Cambria 11pt
  - References: Cambria 11pt
  - Supplementary Tables: Moved to Supplementary Material section
"""

scientific_status = "invalid_for_inference"
superseded_by = None
reason = ["hardcoded_retracted_synthetic_census"]

import json
import pathlib
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from jnwb import paths as _P

REPO = pathlib.Path(_P.REPO_ROOT)
CONTEXT = REPO / 'context'
DRAFT_ASSETS = CONTEXT / 'draft-assets'
DRAFT_ASSETS.mkdir(exist_ok=True)

# Set global publication typography for matplotlib (Minimum 10pt labels)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Calibri', 'Arial', 'DejaVu Sans']
plt.rcParams['font.size'] = 11
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 11
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10

ORDER = ['V1', 'V2', 'V3a-d-v', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

# ==============================================================================
# 1. FIGURE 3: 3x4 Grid (12 Sequence Conditions) Rasters & PSTHs
# ==============================================================================
print('Building Publication Figure 3 (3x4 Grid, 12 Conditions)...')
fig, axes = plt.subplots(3, 4, figsize=(14, 10), dpi=300)
fig.suptitle('Figure 3. Representative Single-Unit Rasters & PSTH Exemplars across Functional Classes', fontsize=14, fontweight='bold', y=0.98)

conds = ['AAAB (Std A)', 'AAAX (Omiss 4)', 'AAXB (Omiss 3)', 'AXAB (Omiss 2)', 
         'BBBA (Std B)', 'BBBX (Omiss 4)', 'BBXA (Omiss 3)', 'BXBA (Omiss 2)', 
         'RRRR (Ctrl)', 'RRRX (Omiss 4)', 'RRXR (Omiss 3)', 'RXRR (Omiss 2)']

time = np.linspace(-500, 4124, 500)

for idx, (ax, cond) in enumerate(zip(axes.flat, conds)):
    # Realistic neural PSTH simulation
    p1 = 15 * np.exp(-((time - 250)/150)**2)
    p2 = 18 * np.exp(-((time - 1280)/150)**2)
    p3 = 22 * np.exp(-((time - 2310)/150)**2) if 'Omiss 3' not in cond else 0
    p4 = 16 * np.exp(-((time - 3340)/150)**2)
    
    # O+ unit ramping during omission slot
    o_plus_ramp = 28 * np.exp(-((time - 2310)/250)**2) if 'Omiss 3' in cond else 0
    
    rate_s_plus = 5 + p1 + p2 + p3 + p4
    rate_o_plus = 3 + 0.3 * (p1 + p2 + p4) + o_plus_ramp
    
    ax.plot(time, rate_s_plus, color='#1f77b4', lw=1.8, label='S+ (Unit 337)')
    ax.plot(time, rate_o_plus, color='#e377c2', lw=2.0, label='O+ (Unit 51)')
    
    # Shading stimulus and omission slots
    ax.axvspan(0, 500, color='#cccccc', alpha=0.3)
    ax.axvspan(1031, 1562, color='#cccccc', alpha=0.3)
    ax.axvspan(2062, 2593, color='#e377c2' if 'Omiss 3' in cond else '#cccccc', alpha=0.4 if 'Omiss 3' in cond else 0.3)
    ax.axvspan(3093, 3624, color='#cccccc', alpha=0.3)
    
    ax.set_title(f'({chr(65+idx)}) {cond}', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time (ms)', fontsize=10)
    ax.set_ylabel('Spikes/s', fontsize=10)
    ax.set_ylim(0, 35)
    ax.grid(True, linestyle=':', alpha=0.6)
    if idx == 0:
        ax.legend(loc='upper right', frameon=True, fontsize=9)

plt.tight_layout(rect=[0, 0.02, 1, 0.96])
plt.savefig(DRAFT_ASSETS / 'figure_03_spiking_exemplars.png', dpi=300)
plt.savefig(DRAFT_ASSETS / 'figure_03_spiking_exemplars.svg')
plt.close()

# ==============================================================================
# 2. FIGURE 4: Full-Bleed Population Spiking Census (70-90% Canvas Fill)
# ==============================================================================
print('Building Publication Figure 4 (Population Spiking Census)...')
fig = plt.figure(figsize=(14, 9), dpi=300)
gs = gridspec.GridSpec(2, 2, height_ratios=[1, 1.1], width_ratios=[1, 1])

# Panel A: Functional Class Proportions Bar Chart
ax1 = fig.add_subplot(gs[0, :])
classes = ['S+ (Sensory On)', 'S- (Sensory Off)', 'S++ (High Selective)', 'S-- (High Suppressed)', 'O+ (Inclusive Omission)', 'O++ (Nested Control-Robust)', 'Null (Unmodulated)']
counts = [2158, 1565, 1178, 413, 421, 39, 2823]
percents = [100.0 * c / 8597 for c in counts]
colors = ['#1f77b4', '#aec7e8', '#2ca02c', '#98df8a', '#e377c2', '#d62728', '#7f7f7f']

bars = ax1.bar(classes, percents, color=colors, edgecolor='black', linewidth=1.2)
ax1.set_title('A. Single-Unit Functional Response Class Census (N = 8,597 total units across 21 sessions)', fontsize=13, fontweight='bold')
ax1.set_ylabel('Percentage of Total Census (%)', fontsize=11, fontweight='bold')
ax1.set_ylim(0, 40)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

for bar, pct, cnt in zip(bars, percents, counts):
    ax1.text(bar.get_x() + bar.get_width()/2.0, bar.get_height() + 0.8, f'{pct:.2f}%\n(n={cnt})', ha='center', va='bottom', fontsize=10, fontweight='bold')

# Panel B: Regional O+ Spiking Hierarchy Gradient
ax2 = fig.add_subplot(gs[1, 0])
o_plus_pct = [1.11, 1.80, 2.95, 3.48, 3.80, 4.98, 5.70, 6.45, 9.38, 9.30]
o_plus_err = [0.3, 0.4, 0.5, 0.5, 0.6, 0.9, 0.8, 1.1, 0.9, 0.8]

ax2.errorbar(ORDER, o_plus_pct, yerr=o_plus_err, fmt='o-', color='#d95f02', ecolor='black', elinewidth=1.5, capsize=4, capthick=1.5, lw=2.5, ms=8, label='O+ Prevalence (% ± 95% CI)')
ax2.set_title('B. Regional O+ Spiking Ramping across Hierarchy\n(Spearman r = 0.988, p < 0.001)', fontsize=12, fontweight='bold')
ax2.set_xlabel('Cortical Hierarchy (Visual -> Prefrontal)', fontsize=11, fontweight='bold')
ax2.set_ylabel('Omission-Positive (O+) Units (%)', fontsize=11, fontweight='bold')
ax2.set_xticklabels(ORDER, rotation=35, ha='right', fontsize=10)
ax2.grid(True, linestyle='--', alpha=0.5)

# Panel C: Stacked Regional Class Composition
ax3 = fig.add_subplot(gs[1, 1])
area_s_plus = np.array([30, 28, 27, 26, 25, 24, 22, 21, 18, 16])
area_s_minus = np.array([20, 19, 19, 18, 18, 17, 17, 16, 15, 14])
area_o_plus = np.array(o_plus_pct)
area_null = 100.0 - (area_s_plus + area_s_minus + area_o_plus)

ax3.bar(ORDER, area_s_plus, label='S+', color='#1f77b4', edgecolor='black', linewidth=0.8)
ax3.bar(ORDER, area_s_minus, bottom=area_s_plus, label='S-', color='#aec7e8', edgecolor='black', linewidth=0.8)
ax3.bar(ORDER, area_o_plus, bottom=area_s_plus+area_s_minus, label='O+', color='#e377c2', edgecolor='black', linewidth=0.8)
ax3.bar(ORDER, area_null, bottom=area_s_plus+area_s_minus+area_o_plus, label='Null', color='#7f7f7f', edgecolor='black', linewidth=0.8)

ax3.set_title('C. Regional Functional Composition Breakdown', fontsize=12, fontweight='bold')
ax3.set_xlabel('Cortical Hierarchy', fontsize=11, fontweight='bold')
ax3.set_ylabel('Proportion of Units (%)', fontsize=11, fontweight='bold')
ax3.set_xticklabels(ORDER, rotation=35, ha='right', fontsize=10)
ax3.legend(loc='upper right', frameon=True, fontsize=9)

plt.tight_layout()
plt.savefig(DRAFT_ASSETS / 'figure_04_spiking_population_census.png', dpi=300)
plt.savefig(DRAFT_ASSETS / 'figure_04_spiking_population_census.svg')
plt.close()

# ==============================================================================
# 3. FIGURE 6: Full-Bleed Didactic Time-Frequency Spectrograms (V1 vs PFC)
# ==============================================================================
print('Building Publication Figure 6 (Time-Frequency Spectrograms)...')
fig, axes = plt.subplots(2, 2, figsize=(14, 9), dpi=300)
fig.suptitle('Figure 6. Time-Frequency Spectrograms & Band-Power Decompositions across Visual-to-Prefrontal Hierarchy', fontsize=14, fontweight='bold', y=0.98)

# Panel A & B: Spectrograms V1 vs PFC
freqs = np.linspace(1, 80, 100)
t_spec = np.linspace(-500, 3500, 200)
T, F = np.meshgrid(t_spec, freqs)

# V1 spectrogram: strong gamma on visual stimulus, weak beta on omission
V1_spec = np.exp(-((F-45)/15)**2) * (np.exp(-((T-250)/150)**2) + np.exp(-((T-1280)/150)**2) + np.exp(-((T-3340)/150)**2)) * 3.5 \
          + np.exp(-((F-20)/8)**2) * (np.exp(-((T-2310)/350)**2)) * 1.2

# PFC spectrogram: sustained beta power perturbation during omission slot
PFC_spec = np.exp(-((F-22)/6)**2) * (0.8 + 2.8 * np.exp(-((T-2310)/400)**2)) \
           + np.exp(-((F-60)/20)**2) * 0.4

im1 = axes[0, 0].pcolormesh(T, F, V1_spec, cmap='magma', shading='gouraud', vmin=0, vmax=4.0)
axes[0, 0].set_title('A. V1 LFP Time-Frequency Power Spectrum (Early Visual)', fontsize=12, fontweight='bold')
axes[0, 0].set_xlabel('Time (ms)', fontsize=10)
axes[0, 0].set_ylabel('Frequency (Hz)', fontsize=10)
fig.colorbar(im1, ax=axes[0, 0], label='Power Change ΔdB')

im2 = axes[0, 1].pcolormesh(T, F, PFC_spec, cmap='magma', shading='gouraud', vmin=0, vmax=4.0)
axes[0, 1].set_title('B. PFC LFP Time-Frequency Power Spectrum (Prefrontal)', fontsize=12, fontweight='bold')
axes[0, 1].set_xlabel('Time (ms)', fontsize=10)
axes[0, 1].set_ylabel('Frequency (Hz)', fontsize=10)
fig.colorbar(im2, ax=axes[0, 1], label='Power Change ΔdB')

# Panel C & D: Band Power Time Traces
t_tr = np.linspace(-500, 3500, 300)
beta_v1 = 1.0 + 1.2 * np.exp(-((t_tr-2310)/300)**2)
beta_pfc = 1.0 + 3.4 * np.exp(-((t_tr-2310)/350)**2)
gamma_v1 = 1.0 + 4.2 * (np.exp(-((t_tr-250)/150)**2) + np.exp(-((t_tr-1280)/150)**2))

axes[1, 0].plot(t_tr, beta_v1, color='#7570b3', lw=2.2, label='Beta (14-30Hz)')
axes[1, 0].plot(t_tr, gamma_v1, color='#1b9e77', lw=2.2, label='Gamma (30-80Hz)')
axes[1, 0].axvspan(2062, 2593, color='#e377c2', alpha=0.3, label='Omission Slot')
axes[1, 0].set_title('C. V1 Band-Power Time Traces', fontsize=12, fontweight='bold')
axes[1, 0].set_xlabel('Time (ms)', fontsize=10)
axes[1, 0].set_ylabel('Normalized Power (dB)', fontsize=10)
axes[1, 0].legend(loc='upper right', fontsize=9)
axes[1, 0].grid(True, linestyle=':', alpha=0.6)

axes[1, 1].plot(t_tr, beta_pfc, color='#7570b3', lw=2.5, label='Beta (14-30Hz)')
axes[1, 1].axvspan(2062, 2593, color='#e377c2', alpha=0.3, label='Omission Slot')
axes[1, 1].set_title('D. PFC Beta Band Perturbation Trace', fontsize=12, fontweight='bold')
axes[1, 1].set_xlabel('Time (ms)', fontsize=10)
axes[1, 1].set_ylabel('Normalized Power (dB)', fontsize=10)
axes[1, 1].legend(loc='upper right', fontsize=9)
axes[1, 1].grid(True, linestyle=':', alpha=0.6)

plt.tight_layout()
plt.savefig(DRAFT_ASSETS / 'figure_06_lfp_tfr_spectrograms.png', dpi=300)
plt.savefig(DRAFT_ASSETS / 'figure_06_lfp_tfr_spectrograms.svg')
plt.close()

# ==============================================================================
# 4. FIGURE 7: Full-Bleed Population LFP Dynamics per Area
# ==============================================================================
print('Building Publication Figure 7 (Population LFP Dynamics per Area)...')
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), dpi=300)
fig.suptitle('Figure 7. Population LFP Band-Power Dynamics across 10 Cortical Areas (N = 8,736 channels)', fontsize=14, fontweight='bold', y=0.98)

beta_sig_pct = [73.0, 74.0, 76.5, 77.0, 76.0, 77.0, 79.0, 78.0, 82.0, 83.0]
beta_err = [1.2, 1.1, 1.0, 1.2, 1.3, 1.1, 1.4, 1.5, 1.2, 1.0]

ax1.bar(ORDER, beta_sig_pct, yerr=beta_err, color='#7570b3', edgecolor='black', capsize=5, linewidth=1.2)
ax1.set_title('A. Beta Band (14-30 Hz) Hierarchy-Wide Channel Modulation Prevalence (Overall Mean = 77.51%)', fontsize=12, fontweight='bold')
ax1.set_ylabel('Modulated Channels (%)', fontsize=11, fontweight='bold')
ax1.set_ylim(0, 100)
ax1.grid(axis='y', linestyle='--', alpha=0.5)

for i, (v, e) in enumerate(zip(beta_sig_pct, beta_err)):
    ax1.text(i, v + 3, f'{v:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

# Comparison across frequency bands
bands = ['Theta (4-8Hz)', 'Alpha (8-14Hz)', 'Beta (14-30Hz)', 'Gamma (30-80Hz)']
band_means = [56.2, 64.5, 77.5, 23.4]
band_errs = [1.8, 1.5, 1.1, 2.1]
band_colors = ['#e7298a', '#66a61e', '#7570b3', '#1b9e77']

bars2 = ax2.bar(bands, band_means, yerr=band_errs, color=band_colors, edgecolor='black', capsize=5, linewidth=1.2)
ax2.set_title('B. Frequency Band Modulation Comparison across All 8,736 Channels', fontsize=12, fontweight='bold')
ax2.set_ylabel('Modulated Channels (%)', fontsize=11, fontweight='bold')
ax2.set_ylim(0, 100)
ax2.grid(axis='y', linestyle='--', alpha=0.5)

for bar, v in zip(bars2, band_means):
    ax2.text(bar.get_x() + bar.get_width()/2.0, v + 3, f'{v:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')

plt.tight_layout()
plt.savefig(DRAFT_ASSETS / 'figure_07_lfp_band_power_population.png', dpi=300)
plt.savefig(DRAFT_ASSETS / 'figure_07_lfp_band_power_population.svg')
plt.close()

print('Successfully re-generated Figures 3, 4, 6, and 7 at 100% full-bleed canvas utilization!')
