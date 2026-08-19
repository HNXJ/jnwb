"""
Visual Quality Control and Multi-Session Inspection

New orthogonal jnwb module for comprehensive QC visualization.
Consolidates logic from archived Y-files:
- jnwb_visual_qc/ folder
- jnwb_visual_qc_multisession/ folder

Provides functions for plotting waveforms, noise distributions, and unit metrics
across single or multiple sessions for visual inspection and validation.

Author: New jnwb module
Date: 2026-06-25
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Union
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

log = logging.getLogger(__name__)

# Palette constants (generic; formerly imported from the omission-specific viz module,
# duplicated here directly since jnwb/ must not depend on omission/).
MADELANE_GOLD = "#CFB87C"
MADELANE_VIOLET = "#9400D3"
MADELANE_WHITE = "#FFFFFF"
MADELANE_GRAY = "#D3D3D3"
MADELANE_TEAL = "#00FFCC"
MADELANE_ORANGE = "#FF5E00"


def plot_unit_waveforms(
    unit_ids: List[Union[int, str]],
    waveforms_dict: Dict,
    max_units_per_page: int = 12,
    figsize: tuple = (16, 10)
) -> List[plt.Figure]:
    """
    Plot waveforms for multiple units (multi-unit grid).

    Args:
        unit_ids: List of unit IDs to plot
        waveforms_dict: Dict mapping unit_id → (n_spikes, n_samples) array
        max_units_per_page: Units per figure page (for large unit sets)
        figsize: Figure size (width, height)

    Returns:
        List of matplotlib figures

    Example:
        >>> waveforms = {unit_id: waveform_array for unit_id in unit_ids}
        >>> figs = plot_unit_waveforms(unit_ids, waveforms)
        >>> for fig in figs:
        ...     fig.savefig(f'unit_waveforms_{i}.png')
    """
    figures = []
    n_units = len(unit_ids)

    # Paginate if needed
    for page_start in range(0, n_units, max_units_per_page):
        page_end = min(page_start + max_units_per_page, n_units)
        page_units = unit_ids[page_start:page_end]

        fig = plt.figure(figsize=figsize)
        n_page_units = len(page_units)
        cols = 4
        rows = (n_page_units + cols - 1) // cols

        for idx, unit_id in enumerate(page_units):
            ax = plt.subplot(rows, cols, idx + 1)

            if unit_id in waveforms_dict:
                waveform = waveforms_dict[unit_id]
                if waveform.ndim == 2:
                    # Multiple spikes: plot mean and std
                    mean_wf = np.mean(waveform, axis=0)
                    std_wf = np.std(waveform, axis=0)

                    ax.plot(mean_wf, color=MADELANE_GOLD, linewidth=2, label='Mean')
                    ax.fill_between(
                        range(len(mean_wf)),
                        mean_wf - std_wf,
                        mean_wf + std_wf,
                        alpha=0.3,
                        color=MADELANE_GOLD,
                        label='±1 STD'
                    )
                else:
                    # Single waveform
                    ax.plot(waveform, color=MADELANE_GOLD, linewidth=2)

            ax.set_title(f'Unit {unit_id}', fontsize=10, fontweight='bold')
            ax.set_xlabel('Sample')
            ax.set_ylabel('Voltage (μV)')
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        figures.append(fig)

    return figures


def plot_unit_quality_distribution(
    units_df: pd.DataFrame,
    session_ids: Optional[List[int]] = None,
    figsize: tuple = (14, 8)
) -> plt.Figure:
    """
    Plot quality metric distributions (multi-panel).

    Visualizes: firing rate, SNR, waveform duration, quality flag distribution.

    Args:
        units_df: DataFrame with unit metrics (from get_all_units_metadata)
        session_ids: Optional list of sessions to filter (default: all)
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> fig = plot_unit_quality_distribution(all_units)
        >>> fig.savefig('unit_quality.png')
    """
    if session_ids is not None:
        units_df = units_df[units_df['session_id'].isin(session_ids)]

    fig, axes = plt.subplots(2, 3, figsize=figsize)
    fig.suptitle('Unit Quality Distribution', fontsize=14, fontweight='bold')

    # Firing rate
    ax = axes[0, 0]
    fr_vals = pd.to_numeric(units_df.get('firing_rate', []), errors='coerce').dropna()
    ax.hist(fr_vals, bins=30, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Firing Rate (spikes/sec)')
    ax.set_ylabel('Count')
    ax.set_title(f'Firing Rate (n={len(fr_vals)})')
    ax.axvline(fr_vals.mean(), color='r', linestyle='--', label=f'Mean: {fr_vals.mean():.1f}')
    ax.legend()

    # SNR
    ax = axes[0, 1]
    snr_vals = pd.to_numeric(units_df.get('snr', []), errors='coerce').dropna()
    ax.hist(snr_vals, bins=30, edgecolor='black', alpha=0.7)
    ax.set_xlabel('SNR')
    ax.set_ylabel('Count')
    ax.set_title(f'SNR (n={len(snr_vals)})')
    ax.axvline(snr_vals.mean(), color='r', linestyle='--', label=f'Mean: {snr_vals.mean():.2f}')
    ax.axvline(1.0, color='g', linestyle=':', label='Threshold: 1.0')
    ax.legend()

    # Waveform duration
    ax = axes[0, 2]
    wd_vals = pd.to_numeric(units_df.get('waveform_duration', []), errors='coerce').dropna()
    ax.hist(wd_vals, bins=30, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Waveform Duration (μs)')
    ax.set_ylabel('Count')
    ax.set_title(f'Waveform Duration (n={len(wd_vals)})')
    ax.axvline(wd_vals.mean(), color='r', linestyle='--', label=f'Mean: {wd_vals.mean():.0f}')
    ax.legend()

    # Quality score
    ax = axes[1, 0]
    q_vals = pd.to_numeric(units_df.get('quality', []), errors='coerce').dropna()
    ax.hist(q_vals, bins=20, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Quality')
    ax.set_ylabel('Count')
    ax.set_title(f'Quality Score (n={len(q_vals)})')
    ax.axvline(1.0, color='g', linestyle=':', label='Good threshold: 1.0')
    ax.legend()

    # Quality by area
    ax = axes[1, 1]
    if 'area' in units_df.columns and 'quality' in units_df.columns:
        unique_areas = list(units_df['area'].dropna().unique()[:8])
        for x_idx, area in enumerate(unique_areas):
            area_units = units_df[units_df['area'] == area]
            q_vals_area = pd.to_numeric(area_units['quality'], errors='coerce').dropna()
            if len(q_vals_area) > 0:
                rng = np.random.default_rng(42)
                jitter = rng.uniform(-0.15, 0.15, size=len(q_vals_area))
                ax.scatter(np.full(len(q_vals_area), x_idx) + jitter, q_vals_area, alpha=0.5, s=20)

        ax.set_xticks(range(len(unique_areas)))
        ax.set_xticklabels(unique_areas, rotation=45)
        ax.set_ylabel('Quality')
        ax.set_title('Quality by Area')
        ax.axhline(1.0, color='g', linestyle=':', alpha=0.5, label='Good threshold')
        ax.legend()

    # Stability flag distribution
    ax = axes[1, 2]
    if 'is_stable' in units_df.columns or 'stable_plus' in units_df.columns:
        stable_col = 'stable_plus' if 'stable_plus' in units_df.columns else 'is_stable'
        counts = units_df[stable_col].value_counts()
        labels = ['Unstable', 'Stable']
        ax.bar(range(len(counts)), counts.values)
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels([labels[i] if i < len(labels) else str(counts.index[i]) for i in range(len(counts))])
        ax.set_ylabel('Count')
        ax.set_title('Unit Stability Distribution')

        for i, v in enumerate(counts.values):
            ax.text(i, v, str(v), ha='center', va='bottom')

    plt.tight_layout()
    return fig


def plot_noise_vs_signal(
    units_df: pd.DataFrame,
    figsize: tuple = (12, 8)
) -> plt.Figure:
    """
    Plot signal-to-noise tradeoffs (multi-metric scatter).

    Shows relationships between SNR, firing rate, waveform duration, and quality.

    Args:
        units_df: DataFrame with unit metrics
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> fig = plot_noise_vs_signal(all_units)
        >>> fig.savefig('noise_vs_signal.png')
    """
    fig, axes = plt.subplots(2, 2, figsize=figsize)
    fig.suptitle('Signal vs. Noise Tradeoffs', fontsize=14, fontweight='bold')

    # SNR vs Firing Rate
    ax = axes[0, 0]
    snr_vals = pd.to_numeric(units_df.get('snr', []), errors='coerce')
    fr_vals = pd.to_numeric(units_df.get('firing_rate', []), errors='coerce')
    ax.scatter(fr_vals, snr_vals, alpha=0.5, s=30)
    ax.set_xlabel('Firing Rate (spikes/sec)')
    ax.set_ylabel('SNR')
    ax.set_title('SNR vs. Firing Rate')
    ax.grid(True, alpha=0.3)

    # SNR vs Waveform Duration
    ax = axes[0, 1]
    wd_vals = pd.to_numeric(units_df.get('waveform_duration', []), errors='coerce')
    ax.scatter(wd_vals, snr_vals, alpha=0.5, s=30)
    ax.set_xlabel('Waveform Duration (μs)')
    ax.set_ylabel('SNR')
    ax.set_title('SNR vs. Waveform Duration')
    ax.grid(True, alpha=0.3)

    # Quality vs Firing Rate
    ax = axes[1, 0]
    q_vals = pd.to_numeric(units_df.get('quality', []), errors='coerce')
    ax.scatter(fr_vals, q_vals, alpha=0.5, s=30)
    ax.set_xlabel('Firing Rate (spikes/sec)')
    ax.set_ylabel('Quality')
    ax.set_title('Quality vs. Firing Rate')
    ax.grid(True, alpha=0.3)

    # 3D projection: SNR, FR, Quality
    ax = axes[1, 1]
    if 'area' in units_df.columns:
        areas = units_df['area'].dropna().unique()[:6]  # Top 6 areas
        colors = plt.cm.tab10(np.linspace(0, 1, len(areas)))

        for area, color in zip(areas, colors):
            area_mask = units_df['area'] == area
            area_snr = snr_vals[area_mask]
            area_fr = fr_vals[area_mask]
            ax.scatter(area_fr, area_snr, alpha=0.6, s=40, label=area, color=color)

        ax.set_xlabel('Firing Rate (spikes/sec)')
        ax.set_ylabel('SNR')
        ax.set_title('SNR vs. FR by Area')
        ax.legend(loc='best', fontsize=8)
        ax.grid(True, alpha=0.3)
    else:
        ax.text(0.5, 0.5, 'Area info not available', ha='center', va='center')

    plt.tight_layout()
    return fig


def compare_session_quality(
    sessions_comparison_df: pd.DataFrame,
    figsize: tuple = (14, 6)
) -> plt.Figure:
    """
    Plot cross-session quality metrics.

    Args:
        sessions_comparison_df: DataFrame from diagnostics.compare_sessions()
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> comparison = diagnostics.compare_sessions(nwb_paths)
        >>> fig = plot_session_quality_comparison(comparison)
    """
    fig, axes = plt.subplots(1, 3, figsize=figsize)
    fig.suptitle('Cross-Session Quality Comparison', fontsize=14, fontweight='bold')

    x_pos = np.arange(len(sessions_comparison_df))

    # SNR across sessions
    ax = axes[0]
    snr_means = sessions_comparison_df['snr_mean'].values
    colors = ['green' if x > 1.0 else 'orange' if x > 0.5 else 'red' for x in snr_means]
    ax.bar(x_pos, snr_means, color=colors, alpha=0.7, edgecolor='black')
    ax.axhline(1.0, color='g', linestyle=':', linewidth=2, label='Good threshold')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(sessions_comparison_df['session_id'], rotation=45, ha='right')
    ax.set_ylabel('Mean SNR')
    ax.set_title('SNR Across Sessions')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # Units per session
    ax = axes[1]
    unit_counts = sessions_comparison_df['total_units'].values
    ax.bar(x_pos, unit_counts, alpha=0.7, edgecolor='black')
    ax.set_xticks(x_pos)
    ax.set_xticklabels(sessions_comparison_df['session_id'], rotation=45, ha='right')
    ax.set_ylabel('Total Units')
    ax.set_title('Unit Count by Session')
    ax.grid(True, alpha=0.3, axis='y')

    # SNR good rate
    ax = axes[2]
    if 'snr_good_rate' in sessions_comparison_df.columns:
        good_rates = sessions_comparison_df['snr_good_rate'].values * 100
        colors_rate = ['green' if x > 50 else 'orange' if x > 25 else 'red' for x in good_rates]
        ax.bar(x_pos, good_rates, color=colors_rate, alpha=0.7, edgecolor='black')
        ax.axhline(50, color='g', linestyle=':', linewidth=2, label='50% target')
        ax.set_xticks(x_pos)
        ax.set_xticklabels(sessions_comparison_df['session_id'], rotation=45, ha='right')
        ax.set_ylabel('% Units with SNR > 1.0')
        ax.set_title('SNR Pass Rate by Session')
        ax.legend()
        ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    return fig
