"""
Publication-Grade Visualization and Figure Generation

Comprehensive figure generation module for omission experiment analysis.
Consolidates logic from archived figure scripts and extends core raster/PSTH functions.

Provides production-ready functions for:
- Multi-unit raster grids with condition families
- PSTH arrays with statistical overlays
- Unit taxonomy and population plots
- Cross-unit comparison figures
- Publication-quality exports

Author: Consolidated from archived figure scripts
Date: 2026-06-25
"""

import logging
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

log = logging.getLogger(__name__)


# Condition families for organized visualization
CONDITION_FAMILIES = {
    "A": {
        "conditions": ["AAAB", "AXAB", "AAXB", "AAAX"],
        "codes": {
            "AAAB": [1, 2],
            "AXAB": [3],
            "AAXB": [4],
            "AAAX": [5],
        },
        "colors": {
            "AAAB": "#1565C0",  # Blue
            "AXAB": "#4CAF50",  # Green
            "AAXB": "#FF9800",  # Orange
            "AAAX": "#E53935",  # Red
        }
    },
    "B": {
        "conditions": ["BBBA", "BXBA", "BBXA", "BBBX"],
        "codes": {
            "BBBA": [6, 7],
            "BXBA": [8],
            "BBXA": [9],
            "BBBX": [10],
        },
        "colors": {
            "BBBA": "#00ACC1",  # Cyan
            "BXBA": "#8E24AA",  # Purple
            "BBXA": "#FFB300",  # Amber
            "BBBX": "#D81B60",  # Pink
        }
    },
    "R": {
        "conditions": ["RRRR", "RXRR", "RRXR", "RRRX"],
        "codes": {
            "RRRR": list(range(11, 27)),
            "RXRR": list(range(27, 35)),
            "RRXR": [35, 37, 39, 41],
            "RRRX": [36, 38, 40] + list(range(42, 51)),
        },
        "colors": {
            "RRRR": "#E5D429",  # Yellow
            "RXRR": "#0E9F58",  # Dark Green
            "RRXR": "#3E9BE5",  # Sky Blue
            "RRRX": "#D9541F",  # Orange Red
        }
    }
}


def raster_grid_by_family(
    session,
    unit_ids: List[Union[int, str]],
    family: str = 'A',
    phase: int = 2,
    max_units_per_page: int = 12,
    figsize: Tuple[float, float] = (16, 10)
) -> List[plt.Figure]:
    """
    Generate raster plots for multiple units organized by condition family.

    Creates grid of raster plots (one per unit) with separate subplots per condition
    within the family. Color-coded by condition for easy comparison.

    Args:
        session: OmissionSession object
        unit_ids: List of unit IDs to plot
        family: 'A', 'B', or 'R' (condition family)
        phase: stimulus_number (default: 2 = p1)
        max_units_per_page: Units per figure (default: 12 = 3x4 grid)
        figsize: Figure size in inches

    Returns:
        List of matplotlib figures

    Example:
        >>> figs = raster_grid_by_family(session, unit_ids, family='A')
        >>> for i, fig in enumerate(figs):
        ...     fig.savefig(f'raster_family_A_page{i}.png', dpi=300)
    """
    if family not in CONDITION_FAMILIES:
        raise ValueError(f"Family must be 'A', 'B', or 'R', got {family}")

    family_config = CONDITION_FAMILIES[family]
    conditions = family_config['conditions']
    colors = family_config['colors']

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

        for unit_idx, unit_id in enumerate(page_units):
            # Create subplot for this unit with multiple condition subplots
            ax_main = plt.subplot(rows, cols, unit_idx + 1)

            # Get epochs for each condition in this family
            condition_data = {}
            max_trials = 0

            for condition in conditions:
                try:
                    epochs = session.get_epochs(phase=phase, condition=condition, correct_only=True)
                    if len(epochs) > 0:
                        spike_times = session.get_spike_times(unit_id)
                        if spike_times is not None and len(spike_times) > 0:
                            condition_data[condition] = {
                                'epochs': epochs,
                                'spike_times': spike_times,
                                'color': colors[condition]
                            }
                            max_trials = max(max_trials, len(epochs))
                except:
                    continue

            if not condition_data:
                ax_main.text(0.5, 0.5, f'Unit {unit_id}\nNo data', ha='center', va='center')
                ax_main.set_xticks([])
                ax_main.set_yticks([])
                continue

            # Plot rasters colored by condition
            trial_offset = 0
            for condition, data in condition_data.items():
                epochs = data['epochs']
                spike_times = data['spike_times']
                color = data['color']

                for trial_idx, onset in enumerate(epochs['start_time'].values):
                    spikes_in_trial = spike_times[
                        (spike_times >= onset - 0.5) &
                        (spike_times <= onset + 1.0)
                    ]
                    spike_times_relative = spikes_in_trial - onset

                    ax_main.vlines(
                        spike_times_relative,
                        trial_offset + trial_idx,
                        trial_offset + trial_idx + 0.9,
                        colors=color,
                        linewidths=0.5,
                        alpha=0.8
                    )

                trial_offset += len(epochs)

            ax_main.set_xlim(-0.5, 1.0)
            ax_main.set_ylim(0, trial_offset)
            ax_main.set_xlabel('Time (s)')
            ax_main.set_ylabel('Trial')
            ax_main.set_title(f'Unit {unit_id}', fontsize=10, fontweight='bold')
            ax_main.axvline(0, color='k', linestyle='--', linewidth=1, alpha=0.3)
            ax_main.grid(True, alpha=0.2, axis='x')

            # Add condition legend if space
            if len(condition_data) <= 4:
                handles = [
                    plt.Line2D([0], [0], color=data['color'], linewidth=2)
                    for data in condition_data.values()
                ]
                labels = list(condition_data.keys())
                ax_main.legend(handles, labels, fontsize=7, loc='upper right')

        fig.suptitle(f'Raster Grid - Family {family} - Phase {phase}', fontsize=14, fontweight='bold')
        plt.tight_layout()
        figures.append(fig)

    return figures


def population_raster_summary(
    session,
    units_df: pd.DataFrame,
    condition: str = 'AAAB',
    phase: int = 2,
    sort_by: str = 'firing_rate',
    n_units: int = 20,
    figsize: Tuple[float, float] = (14, 10)
) -> plt.Figure:
    """
    Generate population raster summary showing top N units by metric.

    Args:
        session: OmissionSession
        units_df: Units DataFrame with metadata
        condition: Condition to plot
        phase: Stimulus phase
        sort_by: Metric to sort units ('firing_rate', 'snr', 'waveform_duration')
        n_units: Number of top units to show
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> fig = population_raster_summary(session, units_df, condition='AAAB', sort_by='snr')
        >>> fig.savefig('population_raster.png')
    """
    # Sort units by metric
    units_sorted = units_df.sort_values(sort_by, ascending=(sort_by != 'firing_rate'))
    top_units = units_sorted.head(n_units)

    fig, axes = plt.subplots(1, 1, figsize=figsize)

    epochs = session.get_epochs(phase=phase, condition=condition, correct_only=True)
    if len(epochs) == 0:
        ax.text(0.5, 0.5, f'No epochs for {condition} phase {phase}', ha='center', va='center')
        return fig

    # Plot all units as raster
    unit_offset = 0
    unit_labels = []
    unit_positions = []

    for idx, (_, unit_row) in enumerate(top_units.iterrows()):
        unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
        spike_times = session.get_spike_times(unit_id)

        if spike_times is None or len(spike_times) == 0:
            continue

        unit_labels.append(f"U{unit_id}")
        unit_positions.append(unit_offset + len(epochs) / 2)

        # Plot spikes for this unit across all trials
        for trial_idx, onset in enumerate(epochs['start_time'].values):
            spikes_in_trial = spike_times[
                (spike_times >= onset - 0.5) &
                (spike_times <= onset + 1.0)
            ]
            spike_times_relative = spikes_in_trial - onset

            axes.vlines(
                spike_times_relative,
                unit_offset + trial_idx,
                unit_offset + trial_idx + 0.9,
                colors='black',
                linewidths=0.3,
                alpha=0.7
            )

        unit_offset += len(epochs)

    axes.set_xlim(-0.5, 1.0)
    axes.set_ylim(0, unit_offset)
    axes.set_xlabel('Time relative to stimulus (s)', fontsize=11)
    axes.set_ylabel('Units', fontsize=11)
    axes.set_yticks(unit_positions)
    axes.set_yticklabels(unit_labels, fontsize=9)
    axes.axvline(0, color='red', linestyle='--', linewidth=1.5, alpha=0.5, label='Stim onset')
    axes.grid(True, alpha=0.2, axis='x')
    axes.legend()

    title = f'Population Raster - {condition} - Phase {phase}\n'
    title += f'Sorted by {sort_by.replace("_", " ").title()} (Top {n_units})'
    axes.set_title(title, fontsize=12, fontweight='bold')

    plt.tight_layout()
    return fig


def multi_phase_comparison(
    session,
    unit_id: Union[int, str],
    condition: str = 'AAAB',
    figsize: Tuple[float, float] = (14, 6)
) -> plt.Figure:
    """
    Compare rasters across all phases (p1-p4) for a single unit and condition.

    Args:
        session: OmissionSession
        unit_id: Unit to plot
        condition: Condition
        figsize: Figure size

    Returns:
        matplotlib figure

    Example:
        >>> fig = multi_phase_comparison(session, unit_id=42, condition='AAXB')
        >>> fig.savefig('multi_phase_unit_42.png')
    """
    fig, axes = plt.subplots(1, 4, figsize=figsize, sharex=True, sharey=True)
    fig.suptitle(f'Unit {unit_id} - {condition} - All Phases', fontsize=14, fontweight='bold')

    spike_times = session.get_spike_times(unit_id)
    if spike_times is None or len(spike_times) == 0:
        for ax in axes:
            ax.text(0.5, 0.5, 'No spikes', ha='center', va='center')
        return fig

    phase_labels = ['p1', 'p2', 'p3', 'p4']
    for phase_idx, (ax, phase_label) in enumerate(zip(axes, phase_labels)):
        phase = phase_idx + 2  # phases are 2, 3, 4, 5

        epochs = session.get_epochs(phase=phase, condition=condition, correct_only=True)
        if len(epochs) == 0:
            ax.text(0.5, 0.5, 'No epochs', ha='center', va='center')
            ax.set_title(phase_label)
            continue

        # Plot raster
        for trial_idx, onset in enumerate(epochs['start_time'].values):
            spikes_in_trial = spike_times[
                (spike_times >= onset - 0.5) &
                (spike_times <= onset + 1.0)
            ]
            spike_times_relative = spikes_in_trial - onset

            ax.vlines(
                spike_times_relative,
                trial_idx,
                trial_idx + 0.9,
                colors='black',
                linewidths=0.5,
                alpha=0.8
            )

        ax.set_xlim(-0.5, 1.0)
        ax.set_ylim(0, len(epochs))
        ax.axvline(0, color='red', linestyle='--', linewidth=1, alpha=0.5)
        ax.set_title(f'{phase_label}\n(n={len(epochs)})', fontsize=10)
        ax.grid(True, alpha=0.2)

    axes[0].set_ylabel('Trial')
    fig.text(0.5, 0.02, 'Time relative to stimulus (s)', ha='center', fontsize=11)

    plt.tight_layout()
    return fig


def save_figure_suite(
    figures: List[plt.Figure],
    output_dir: Union[str, Path],
    basename: str,
    dpi: int = 300,
    formats: List[str] = ['png', 'pdf']
) -> None:
    """
    Save a suite of figures to disk with consistent naming.

    Args:
        figures: List of matplotlib figures
        output_dir: Output directory
        basename: Base filename (will add page numbers and format)
        dpi: Resolution for raster formats
        formats: List of formats to save ('png', 'pdf', 'svg')

    Example:
        >>> figs = raster_grid_by_family(session, unit_ids)
        >>> save_figure_suite(figs, 'outputs/figures', 'raster_family_a')
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for fig_idx, fig in enumerate(figures):
        for fmt in formats:
            filename = f"{basename}_page{fig_idx+1}.{fmt}"
            filepath = output_dir / filename

            if fmt == 'pdf':
                fig.savefig(filepath, format='pdf', bbox_inches='tight')
            else:
                fig.savefig(filepath, format=fmt, dpi=dpi, bbox_inches='tight')

            log.info(f"Saved: {filepath}")
