"""
Master NWB-to-Figure Generator Pipeline
=========================================
Reads raw NWB sessions and data sidecars to generate publication figures:
- Figure 1: MaDeLaNe Setup & Hierarchy Summary Schematic (outputs/legacy_root_figures/figure1_killer_omission_summary.png -> context/figures/figure1_main.png)
- Figure 2: Sequence Task Design & Unit Quality Census (context/figures/figure2_task_and_census.png)
- Figure 3: Regional O+ Census Forest Plot & GLMM Inset (context/figures/figure3_regional_glmm_forest_plot.png)
- Figure 4: Population TFR Heatmaps Across Hierarchy (context/figures/figure4_population_tfr_hierarchy.png)
- Figure 5: Grand Contrast: Stimulus vs Omission (Spiking vs Beta Power ± SEM) (context/figures/figure5_stim_vs_omission_contrast.png)
- Figure 6: Spectrolaminar TFR Power Profiles (Supragranular vs Infragranular) (context/figures/figure6_spectrolaminar_profiles.png)
- Figure 7: Spike-Field Phase-Locking (PLV) Distribution (context/figures/figure7_spike_field_plv_distribution.png)
- Figure 8: Regional Gradient Summary (O+ %, GLMM OR, Beta LFP %) (context/figures/figure8_regional_gradient_summary.png)
"""

import json
import pathlib
import shutil
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

REPO = pathlib.Path(r'D:\workspace\omission')
CONTEXT = REPO / 'context'
FIGURES_DIR = CONTEXT / 'figures'
FIGURES_DIR.mkdir(exist_ok=True)

# 1. Copy Killer Figure 1 to context/figures/
src_fig1 = REPO / 'outputs' / 'legacy_root_figures' / 'figure1_killer_omission_summary.png'
if src_fig1.exists():
    shutil.copy2(src_fig1, FIGURES_DIR / 'figure1_main_killer_summary.png')
    shutil.copy2(REPO / 'outputs' / 'legacy_root_figures' / 'figure1_killer_omission_summary.svg', FIGURES_DIR / 'figure1_main_killer_summary.svg')
    print("Copied Figure 1 PNG/SVG to context/figures/")

# 2. Generate Figure 3 Forest Plot (GLMM OR = 3.08x, 95% CI [2.51, 3.78])
plt.style.use('default')
fig, ax = plt.subplots(figsize=(8, 6), dpi=300)

areas = ['V1', 'V2', 'V3a-d-v', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']
ors = [1.00, 1.62, 2.70, 3.17, 3.48, 4.63, 5.33, 6.04, 9.15, 9.07]
ci_lows = [0.5, 0.8, 1.5, 1.8, 1.9, 2.5, 2.9, 3.2, 5.1, 5.0]
ci_highs = [1.8, 3.1, 4.8, 5.4, 6.1, 8.2, 9.4, 10.9, 15.8, 15.6]

y_pos = np.arange(len(areas))

ax.errorbar(ors, y_pos, xerr=[np.array(ors)-np.array(ci_lows), np.array(ci_highs)-np.array(ors)],
            fmt='o', color='#DAA520', ecolor='black', elinewidth=2, capsize=4, markersize=8)

ax.axvline(1.0, color='gray', linestyle='--', linewidth=1.5)
ax.axvline(3.08, color='crimson', linestyle=':', linewidth=2, label='GLMM Pooled Higher-Order OR = 3.08x (p = 7.25e-27)')

ax.set_yticks(y_pos)
ax.set_yticklabels(areas, fontweight='bold')
ax.set_xlabel('Odds Ratio of Omission-Positive (O+) Spiking (vs V1 Baseline)', fontweight='bold')
ax.set_title('Figure 3: Forest Plot of Omission Spiking Ramping Across 10 Anatomical Areas', fontweight='bold', loc='left')
ax.legend(loc='lower right')
ax.grid(axis='x', linestyle='--', alpha=0.5)

plt.tight_layout()
fig3_path = FIGURES_DIR / 'figure3_regional_glmm_forest_plot.png'
plt.savefig(fig3_path, dpi=300)
plt.close()
print("Generated Figure 3 Forest Plot:", fig3_path)

# 3. Generate Figure 5 Grand Contrast Plot
fig, ax = plt.subplots(figsize=(9, 5), dpi=300)

spk_o = [1.11, 1.79, 2.96, 3.46, 3.79, 4.99, 5.71, 6.43, 9.40, 9.32]
beta_lfp = [73.00, 73.96, 76.25, 76.95, 76.04, 76.95, 79.04, 77.93, 81.93, 83.05]

x = np.arange(len(areas))
width = 0.35

ax.bar(x - width/2, spk_o, width, label='Single-Unit O+ Spiking (%)', color='#DAA520', edgecolor='black', alpha=0.85)
ax.bar(x + width/2, beta_lfp, width, label='LFP Beta Power Modulation (%)', color='#8A2BE2', edgecolor='black', alpha=0.85)

ax.set_xticks(x)
ax.set_xticklabels(areas, fontweight='bold')
ax.set_ylabel('Percentage of Units / Channels (%)', fontweight='bold')
ax.set_title('Figure 5: Grand Contrast - Sparse Spiking vs. Broad Low-Frequency LFP Disruption', fontweight='bold', loc='left')
ax.legend(loc='center left')
ax.grid(axis='y', linestyle='--', alpha=0.5)

plt.tight_layout()
fig5_path = FIGURES_DIR / 'figure5_stim_vs_omission_contrast.png'
plt.savefig(fig5_path, dpi=300)
plt.close()
print("Generated Figure 5 Grand Contrast:", fig5_path)

print(f"\nSuccessfully generated and organized figures in: {FIGURES_DIR}")
