"""
Hierarchy-Wide MUA Sequence Response Profile
============================================
Plots mean firing rate timecourses across the cortical hierarchy (V1 → PFC)
for all units in the grand table, comparing Standard vs Global Omission conditions.

Uses: outputs/classification/grand_unit_table_shuffle_sso.csv
      (epoch-mean firing rates already computed per unit)

Output: outputs/publication_figures/figure_mua_hierarchy_sequence_profile.svg
        context/draft-assets/figures/figure_mua_hierarchy_sequence_profile.svg

This is a bar+error visualisation (mean ± SEM across units per area per epoch mean)
using the available epoch-summary columns, not raw spike trains.
"""
import pathlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import date

REPO = pathlib.Path(r'D:\workspace\omission')
GT_PATH = REPO / 'outputs' / 'classification' / 'grand_unit_table_shuffle_sso.csv'
OUT_DIR = REPO / 'outputs' / 'publication_figures'
ASSET_DIR = REPO / 'context' / 'draft-assets' / 'figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)
ASSET_DIR.mkdir(parents=True, exist_ok=True)

TODAY = str(date.today())

# ── Canonical palette (from omission-palette.mdc) ────────────────────────────
PALETTE = {
    'baseline':  '#6B7280',  # GRAY
    'standard':  '#3B82F6',  # BLUE
    'omission':  '#F59E0B',  # GOLD/AMBER
    'control':   '#8B5CF6',  # VIOLET
    'delay':     '#6B7280',  # GRAY
}

# ── Ordered areas ─────────────────────────────────────────────────────────────
AREA_ORDER = ['V1', 'V2', 'V3', 'V3d', 'V3v', 'V4', 'MT', 'MST', 'TEO', 'FST', 'FEF', 'PFC']

# ── Load grand table ──────────────────────────────────────────────────────────
gt = pd.read_csv(GT_PATH)
print(f"Grand table: {len(gt)} units, {gt['session_id'].nunique()} sessions")

# Normalize area names
gt['area_norm'] = gt['area'].str.strip().str.upper()
available_areas = [a for a in AREA_ORDER if a in gt['area_norm'].unique()]
print(f"Areas present: {available_areas}")

# ── Epoch-mean firing rates for the profile ───────────────────────────────────
# Available cols: mean_baseline_hz, mean_stim_hz, mean_delay_hz,
#                 mean_omission_hz, mean_control_slot_hz
EPOCH_COLS = {
    'Baseline\n(pre-seq)': 'mean_baseline_hz',
    'Stimulus\n(p1-p4)':   'mean_stim_hz',
    'Delay\n(d1-d4)':      'mean_delay_hz',
    'Omission\nwindow':    'mean_omission_hz',
    'Control\nslot':       'mean_control_slot_hz',
}

EPOCH_COLORS = {
    'Baseline\n(pre-seq)': PALETTE['baseline'],
    'Stimulus\n(p1-p4)':   PALETTE['standard'],
    'Delay\n(d1-d4)':      PALETTE['delay'],
    'Omission\nwindow':    PALETTE['omission'],
    'Control\nslot':       PALETTE['control'],
}

# ── Build figure ──────────────────────────────────────────────────────────────
n_areas = len(available_areas)
n_cols = min(4, n_areas)
n_rows = (n_areas + n_cols - 1) // n_cols

fig = plt.figure(figsize=(5 * n_cols, 4.5 * n_rows), facecolor='#0F172A')
fig.suptitle(
    f'Hierarchy-Wide MUA Sequence Response Profile\n'
    f'Mean Epoch Firing Rate (Hz) ± SEM across {len(gt):,} units, '
    f'{gt["session_id"].nunique()} sessions — {TODAY}',
    color='white', fontsize=13, fontweight='bold', y=1.01
)

gs = gridspec.GridSpec(n_rows, n_cols, figure=fig, hspace=0.55, wspace=0.4)

x_pos = np.arange(len(EPOCH_COLS))
bar_width = 0.65

area_stats = {}

for idx, area in enumerate(available_areas):
    row, col = divmod(idx, n_cols)
    ax = fig.add_subplot(gs[row, col])
    ax.set_facecolor('#1E293B')

    mask = gt['area_norm'] == area
    area_df = gt[mask]
    n_units = len(area_df)

    means, sems, colors = [], [], []
    for epoch_label, col_name in EPOCH_COLS.items():
        if col_name in area_df.columns:
            vals = area_df[col_name].dropna()
            m = vals.mean()
            s = vals.sem()
        else:
            m, s = 0.0, 0.0
        means.append(m)
        sems.append(s)
        colors.append(EPOCH_COLORS[epoch_label])

    bars = ax.bar(x_pos, means, bar_width, yerr=sems,
                  color=colors, alpha=0.85, edgecolor='white',
                  linewidth=0.5, error_kw=dict(ecolor='#CBD5E1', linewidth=1.2, capsize=3))

    # Annotate % change from baseline
    baseline_mean = means[0] if means[0] > 0 else 1e-6
    for xi, (m, bar) in enumerate(zip(means[1:], bars[1:]), start=1):
        pct = (m - baseline_mean) / baseline_mean * 100
        ax.text(xi, m + sems[xi] + 0.05, f'{pct:+.0f}%',
                ha='center', va='bottom', color='#CBD5E1', fontsize=6.5, fontweight='bold')

    ax.set_title(f'{area}  (n={n_units})', color='white', fontsize=10, fontweight='bold', pad=6)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(list(EPOCH_COLS.keys()), fontsize=7, color='#94A3B8')
    ax.set_ylabel('Mean FR (Hz)', color='#94A3B8', fontsize=8)
    ax.tick_params(colors='#94A3B8', labelsize=7)
    ax.spines['bottom'].set_color('#334155')
    ax.spines['left'].set_color('#334155')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_ylim(bottom=0)
    ax.yaxis.label.set_color('#94A3B8')

    area_stats[area] = {
        'n_units': n_units,
        'epochs': {k: {'mean': float(m), 'sem': float(s)}
                   for k, m, s in zip(EPOCH_COLS.keys(), means, sems)}
    }

# Hide unused subplots
for idx in range(len(available_areas), n_rows * n_cols):
    row, col = divmod(idx, n_cols)
    fig.add_subplot(gs[row, col]).set_visible(False)

# Legend
legend_patches = [
    plt.Rectangle((0, 0), 1, 1, color=c, label=lbl.replace('\n', ' '))
    for lbl, c in EPOCH_COLORS.items()
]
fig.legend(handles=legend_patches, loc='lower center', ncol=5,
           facecolor='#1E293B', edgecolor='#334155',
           labelcolor='white', fontsize=9, bbox_to_anchor=(0.5, -0.04))

plt.tight_layout()

# ── Save ──────────────────────────────────────────────────────────────────────
for out_path in [
    OUT_DIR / 'figure_mua_hierarchy_sequence_profile.svg',
    ASSET_DIR / 'figure_mua_hierarchy_sequence_profile.svg',
]:
    fig.savefig(out_path, format='svg', bbox_inches='tight',
                facecolor=fig.get_facecolor(), dpi=150)
    print(f'Saved: {out_path}')

# PNG for manuscript embedding
png_path = OUT_DIR / 'figure_mua_hierarchy_sequence_profile.png'
fig.savefig(png_path, format='png', bbox_inches='tight',
            facecolor=fig.get_facecolor(), dpi=150)
print(f'Saved: {png_path}')
plt.close(fig)

# ── Save stats sidecar ────────────────────────────────────────────────────────
sidecar_path = OUT_DIR / 'figure_mua_hierarchy_sequence_profile.meta.json'
with open(sidecar_path, 'w', encoding='utf-8') as f:
    json.dump({
        'generated': TODAY,
        'source': str(GT_PATH),
        'n_total_units': int(len(gt)),
        'n_sessions': int(gt['session_id'].nunique()),
        'areas': area_stats,
    }, f, indent=2)
print(f'Saved sidecar: {sidecar_path}')
print('\nHierarchy-Wide MUA Sequence Response Profile complete.')
