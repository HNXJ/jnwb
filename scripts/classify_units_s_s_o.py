#!/usr/bin/env python3
"""Classify single units into S+, S-, and O/X response categories.

Classification rules:
- S+ (stimulus-excited): p1_rate > baseline * 1.20, Wilcoxon p < 0.05
- S- (stimulus-inhibited): p1_rate < baseline * 0.80, Wilcoxon p < 0.05
- O/X (omission-correlated): AAXB only, omission > p1 AND omission > p2 AND omission > baseline, Wilcoxon p < 0.05

Time zero must be code101 p1 stimulus onset.
"""

from __future__ import annotations

import argparse
import json
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.analysis.contracts.constants import (
    AAXB_CONDITION_NUMBER,
    AAXB_OMISSION_OFFSET_MS,
)


# ============================================================================
# Configuration
# ============================================================================

# Time windows (ms, p1-relative)
WINDOW_BASELINE = (-500, 0)
WINDOW_P1 = (0, 531)
WINDOW_P2 = (1031, 1562)
WINDOW_P3_OMISSION = (2062, 2593)

# Statistical thresholds
P_VALUE_THRESHOLD = 0.05
EFFECT_SIZE_INCREASE = 1.20  # 20% increase
EFFECT_SIZE_DECREASE = 0.80   # 20% decrease
MIN_TRIALS_DEFAULT = 8

# Typed blockers
BLOCKED_ANCHOR_NOT_CODE101 = "BLOCKED_ANCHOR_NOT_CODE101"
BLOCKED_ANCHOR_CODE100 = "BLOCKED_ANCHOR_CODE100"
BLOCKED_TIME_AXIS_NOT_P1_RELATIVE = "BLOCKED_TIME_AXIS_NOT_P1_RELATIVE"
BLOCKED_INSUFFICIENT_TIME_COVERAGE = "BLOCKED_INSUFFICIENT_TIME_COVERAGE"
BLOCKED_NONFINITE_DATA = "BLOCKED_NONFINITE_DATA"
BLOCKED_INSUFFICIENT_TRIALS = "BLOCKED_INSUFFICIENT_TRIALS"


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class ClassificationConfig:
    """Configuration for unit classification."""
    window_baseline: tuple[float, float] = WINDOW_BASELINE
    window_p1: tuple[float, float] = WINDOW_P1
    window_p2: tuple[float, float] = WINDOW_P2
    window_p3_omission: tuple[float, float] = WINDOW_P3_OMISSION
    p_threshold: float = P_VALUE_THRESHOLD
    effect_increase: float = EFFECT_SIZE_INCREASE
    effect_decrease: float = EFFECT_SIZE_DECREASE
    min_trials: int = MIN_TRIALS_DEFAULT
    epsilon_hz: float = 0.1  # For percent change with near-zero baseline


@dataclass
class UnitClassification:
    """Classification result for a single unit."""
    unit_id: str
    session: str
    area: str | None
    
    # Firing rates (Hz)
    baseline_rate: float
    p1_rate: float
    p2_rate: float | None
    omission_rate: float | None
    
    # Statistics
    s_plus_p_value: float | None
    s_minus_p_value: float | None
    ox_p_value: float | None
    
    # Percent changes
    s_plus_percent_change: float | None
    s_minus_percent_change: float | None
    ox_percent_change: float | None
    
    # Boolean labels (non-exclusive)
    is_s_plus: bool
    is_s_minus: bool
    is_ox: bool
    
    # Exclusive display class
    display_class: str  # "S+", "S-", "O/X", "unclassified"
    
    # Metadata
    n_trials: int
    n_trials_aaxb: int | None
    valid: bool
    exclusion_reason: str | None


# ============================================================================
# Validation Guards
# ============================================================================

def validate_anchor_provenance(epochs_dict: dict[str, Any]) -> dict[str, Any]:
    """Validate that epochs use code101 p1 anchor, not code100.
    
    Returns:
        Validation result dict with 'valid' and 'error' keys
    """
    result = {"valid": True, "error": None, "blocker": None}
    
    # Check for explicit anchor provenance
    anchor_code = epochs_dict.get("anchor_code")
    anchor_type = epochs_dict.get("anchor_type")
    time_base = epochs_dict.get("time_base")
    
    # Reject if explicitly code100
    if anchor_code == 100 or anchor_type == "fixation_cue":
        result["valid"] = False
        result["blocker"] = BLOCKED_ANCHOR_CODE100
        result["error"] = "Epochs use code100 fixation cue anchor - REJECTED"
        return result
    
    # Check time base
    if time_base and time_base not in ("p1_relative", "code101_relative"):
        result["valid"] = False
        result["blocker"] = BLOCKED_TIME_AXIS_NOT_P1_RELATIVE
        result["error"] = f"Time base is '{time_base}', not p1-relative"
        return result
    
    # Require explicit code101 or p1-relative
    if anchor_code != 101 and time_base != "p1_relative":
        result["valid"] = False
        result["blocker"] = BLOCKED_ANCHOR_NOT_CODE101
        result["error"] = "Cannot verify code101 anchor provenance"
        return result
    
    return result


def validate_time_coverage(
    time_axis_ms: np.ndarray,
    required_windows: list[tuple[float, float]],
) -> dict[str, Any]:
    """Validate that time axis covers all required windows.
    
    Returns:
        Validation result dict
    """
    result = {"valid": True, "error": None, "coverage": {}}
    
    t_min = time_axis_ms.min()
    t_max = time_axis_ms.max()
    
    for window_name, (w_start, w_end) in required_windows:
        covered = (t_min <= w_start) and (w_end <= t_max)
        result["coverage"][window_name] = {
            "required": (w_start, w_end),
            "available": (t_min, t_max),
            "covered": covered,
        }
        if not covered:
            result["valid"] = False
            result["error"] = f"Window {window_name} ({w_start}, {w_end}) not covered by time axis ({t_min}, {t_max})"
            result["blocker"] = BLOCKED_INSUFFICIENT_TIME_COVERAGE
    
    return result


def validate_data_quality(spk_epochs: np.ndarray) -> dict[str, Any]:
    """Validate spike epoch data quality.
    
    Returns:
        Validation result dict
    """
    result = {"valid": True, "error": None, "blocker": None}
    
    # Check for non-finite values
    if not np.all(np.isfinite(spk_epochs)):
        n_nonfinite = np.sum(~np.isfinite(spk_epochs))
        result["valid"] = False
        result["blocker"] = BLOCKED_NONFINITE_DATA
        result["error"] = f"Non-finite values in spike data: {n_nonfinite} elements"
        return result
    
    # Check shape
    if spk_epochs.ndim != 3:
        result["valid"] = False
        result["error"] = f"Expected 3D array (trial x unit x time), got {spk_epochs.ndim}D"
        return result
    
    return result


# ============================================================================
# Classification Functions
# ============================================================================

def extract_window_rate(
    spk_epochs: np.ndarray,
    time_axis_ms: np.ndarray,
    window_ms: tuple[float, float],
    bin_ms: float,
) -> np.ndarray:
    """Extract mean firing rate within time window.
    
    Args:
        spk_epochs: (n_trials, n_units, n_time_bins) spike count array
        time_axis_ms: time axis in ms
        window_ms: (start, end) window in ms
        bin_ms: bin width in ms
        
    Returns:
        (n_trials, n_units) mean firing rate in Hz for each trial-unit pair
    """
    # Find time indices within window
    mask = (time_axis_ms >= window_ms[0]) & (time_axis_ms < window_ms[1])
    
    if not np.any(mask):
        raise ValueError(f"No time bins in window {window_ms}")
    
    # Sum spikes in window, convert to Hz
    window_counts = spk_epochs[:, :, mask].sum(axis=2)  # (n_trials, n_units)
    window_duration_s = (window_ms[1] - window_ms[0]) / 1000.0
    window_rate_hz = window_counts / window_duration_s
    
    return window_rate_hz


def classify_s_plus(
    baseline_rates: np.ndarray,
    p1_rates: np.ndarray,
    config: ClassificationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as S+ (stimulus-excited).
    
    Args:
        baseline_rates: (n_trials, n_units) baseline firing rates
        p1_rates: (n_trials, n_units) p1 firing rates
        config: classification configuration
        
    Returns:
        (is_s_plus, p_values, percent_changes) arrays of length n_units
    """
    n_trials, n_units = baseline_rates.shape
    
    is_s_plus = np.zeros(n_units, dtype=bool)
    p_values = np.full(n_units, np.nan)
    percent_changes = np.full(n_units, np.nan)
    
    for unit_idx in range(n_units):
        baseline = baseline_rates[:, unit_idx]
        p1 = p1_rates[:, unit_idx]
        
        # Check minimum trials
        valid_trials = np.isfinite(baseline) & np.isfinite(p1)
        n_valid = np.sum(valid_trials)
        
        if n_valid < config.min_trials:
            continue
        
        baseline_valid = baseline[valid_trials]
        p1_valid = p1[valid_trials]
        
        # Wilcoxon signed-rank test
        try:
            statistic, p_value = stats.wilcoxon(p1_valid, baseline_valid, alternative='greater')
        except ValueError:
            # All values identical
            continue
        
        p_values[unit_idx] = p_value
        
        # Effect size: percent change
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        
        # Handle near-zero baseline with epsilon
        baseline_for_pct = max(baseline_mean, config.epsilon_hz)
        pct_change = (p1_mean - baseline_mean) / baseline_for_pct * 100
        percent_changes[unit_idx] = pct_change
        
        # Classification criteria
        significant = p_value < config.p_threshold
        large_effect = p1_mean > baseline_mean * config.effect_increase
        
        is_s_plus[unit_idx] = significant and large_effect
    
    return is_s_plus, p_values, percent_changes


def classify_s_minus(
    baseline_rates: np.ndarray,
    p1_rates: np.ndarray,
    config: ClassificationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as S- (stimulus-inhibited).
    
    Returns:
        (is_s_minus, p_values, percent_changes) arrays
    """
    n_trials, n_units = baseline_rates.shape
    
    is_s_minus = np.zeros(n_units, dtype=bool)
    p_values = np.full(n_units, np.nan)
    percent_changes = np.full(n_units, np.nan)
    
    for unit_idx in range(n_units):
        baseline = baseline_rates[:, unit_idx]
        p1 = p1_rates[:, unit_idx]
        
        valid_trials = np.isfinite(baseline) & np.isfinite(p1)
        n_valid = np.sum(valid_trials)
        
        if n_valid < config.min_trials:
            continue
        
        baseline_valid = baseline[valid_trials]
        p1_valid = p1[valid_trials]
        
        # Wilcoxon (less = baseline > p1)
        try:
            statistic, p_value = stats.wilcoxon(baseline_valid, p1_valid, alternative='greater')
        except ValueError:
            continue
        
        p_values[unit_idx] = p_value
        
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        
        baseline_for_pct = max(baseline_mean, config.epsilon_hz)
        pct_change = (p1_mean - baseline_mean) / baseline_for_pct * 100
        percent_changes[unit_idx] = pct_change
        
        significant = p_value < config.p_threshold
        large_effect = p1_mean < baseline_mean * config.effect_decrease
        
        is_s_minus[unit_idx] = significant and large_effect
    
    return is_s_minus, p_values, percent_changes


def classify_ox(
    baseline_rates: np.ndarray,
    p1_rates: np.ndarray,
    p2_rates: np.ndarray,
    omission_rates: np.ndarray,
    config: ClassificationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as O/X (omission-correlated) using AAXB trials.
    
    Args:
        baseline_rates: (n_trials_aaxb, n_units) baseline rates
        p1_rates: (n_trials_aaxb, n_units) p1 rates
        p2_rates: (n_trials_aaxb, n_units) p2 rates
        omission_rates: (n_trials_aaxb, n_units) omission (p3) rates
        config: classification configuration
        
    Returns:
        (is_ox, p_values, percent_changes) arrays
    """
    n_trials, n_units = baseline_rates.shape
    
    is_ox = np.zeros(n_units, dtype=bool)
    p_values = np.full(n_units, np.nan)
    percent_changes = np.full(n_units, np.nan)
    
    for unit_idx in range(n_units):
        baseline = baseline_rates[:, unit_idx]
        p1 = p1_rates[:, unit_idx]
        p2 = p2_rates[:, unit_idx]
        omission = omission_rates[:, unit_idx]
        
        valid_trials = (np.isfinite(baseline) & np.isfinite(p1) & 
                       np.isfinite(p2) & np.isfinite(omission))
        n_valid = np.sum(valid_trials)
        
        if n_valid < config.min_trials:
            continue
        
        baseline_valid = baseline[valid_trials]
        p1_valid = p1[valid_trials]
        p2_valid = p2[valid_trials]
        omission_valid = omission[valid_trials]
        
        # Mean rates
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        p2_mean = np.mean(p2_valid)
        omission_mean = np.mean(omission_valid)
        
        # Wilcoxon: omission vs baseline
        try:
            statistic, p_value = stats.wilcoxon(omission_valid, baseline_valid, alternative='greater')
        except ValueError:
            continue
        
        p_values[unit_idx] = p_value
        
        # Percent change
        baseline_for_pct = max(baseline_mean, config.epsilon_hz)
        pct_change = (omission_mean - baseline_mean) / baseline_for_pct * 100
        percent_changes[unit_idx] = pct_change
        
        # Classification criteria
        significant = p_value < config.p_threshold
        exceeds_p1 = omission_mean > p1_mean
        exceeds_p2 = omission_mean > p2_mean
        exceeds_baseline = omission_mean > baseline_mean
        
        is_ox[unit_idx] = significant and exceeds_p1 and exceeds_p2 and exceeds_baseline
    
    return is_ox, p_values, percent_changes


def assign_display_class(
    is_s_plus: np.ndarray,
    is_s_minus: np.ndarray,
    is_ox: np.ndarray,
) -> np.ndarray:
    """Assign exclusive display class with O/X precedence.
    
    Priority: O/X > S+ > S-
    
    Returns:
        Array of class labels ("S+", "S-", "O/X", "unclassified")
    """
    n_units = len(is_s_plus)
    display_classes = np.full(n_units, "unclassified", dtype=object)
    
    # O/X takes precedence
    display_classes[is_ox] = "O/X"
    
    # Then S+ (but not if already O/X)
    s_plus_only = is_s_plus & ~is_ox
    display_classes[s_plus_only] = "S+"
    
    # Then S- (but not if already O/X or S+)
    s_minus_only = is_s_minus & ~is_ox & ~is_s_plus
    display_classes[s_minus_only] = "S-"
    
    return display_classes


# ============================================================================
# Main Pipeline
# ============================================================================

def classify_units_from_epochs(
    spk_epochs_p1: np.ndarray,
    spk_epochs_omission: np.ndarray | None,
    time_axis_ms: np.ndarray,
    unit_metadata: pd.DataFrame,
    trial_conditions: np.ndarray | None = None,
    config: ClassificationConfig | None = None,
    anchor_provenance: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Classify units from spike epochs.
    
    Args:
        spk_epochs_p1: (n_trials, n_units, n_time) p1-aligned epochs
        spk_epochs_omission: (n_trials, n_units, n_time) omission-aligned epochs (optional)
        time_axis_ms: time axis in ms (p1-relative)
        unit_metadata: DataFrame with unit_id, session, area columns
        trial_conditions: array of condition labels per trial
        config: classification configuration
        anchor_provenance: dict with anchor_code, time_base info
        
    Returns:
        (classification_table, manifest) tuple
    """
    if config is None:
        config = ClassificationConfig()
    
    n_trials, n_units, n_time = spk_epochs_p1.shape
    
    # Validation guards
    if anchor_provenance:
        anchor_valid = validate_anchor_provenance(anchor_provenance)
        if not anchor_valid["valid"]:
            raise ValueError(f"Anchor validation failed: {anchor_valid['error']}")
    
    data_valid = validate_data_quality(spk_epochs_p1)
    if not data_valid["valid"]:
        raise ValueError(f"Data validation failed: {data_valid['error']}")
    
    # Check time coverage
    required_windows = [
        ("baseline", config.window_baseline),
        ("p1", config.window_p1),
        ("p2", config.window_p2),
    ]
    required_windows.append(("p3_omission", config.window_p3_omission))
    
    coverage_valid = validate_time_coverage(time_axis_ms, required_windows)
    if not coverage_valid["valid"]:
        raise ValueError(f"Time coverage failed: {coverage_valid['error']}")
    
    # Extract firing rates for all trials
    baseline_rates = extract_window_rate(
        spk_epochs_p1, time_axis_ms, config.window_baseline, 
        time_axis_ms[1] - time_axis_ms[0]
    )
    p1_rates = extract_window_rate(
        spk_epochs_p1, time_axis_ms, config.window_p1,
        time_axis_ms[1] - time_axis_ms[0]
    )
    p2_rates = extract_window_rate(
        spk_epochs_p1, time_axis_ms, config.window_p2,
        time_axis_ms[1] - time_axis_ms[0]
    )
    
    # S+ and S- classification (all trials)
    is_s_plus, s_plus_p, s_plus_pct = classify_s_plus(baseline_rates, p1_rates, config)
    is_s_minus, s_minus_p, s_minus_pct = classify_s_minus(baseline_rates, p1_rates, config)
    
    # O/X classification (AAXB trials only)
    is_ox = np.zeros(n_units, dtype=bool)
    ox_p = np.full(n_units, np.nan)
    ox_pct = np.full(n_units, np.nan)
    
  # O/X: AAXB trials only, p3 omission window on p1-relative axis
    omission_rates = extract_window_rate(
        spk_epochs_p1, time_axis_ms, config.window_p3_omission,
        time_axis_ms[1] - time_axis_ms[0]
    )

    if trial_conditions is not None:
        trial_conditions = np.asarray(trial_conditions).astype(str)
        aaxb_mask = trial_conditions == "AAXB"
        n_aaxb = int(np.sum(aaxb_mask))

        if n_aaxb >= config.min_trials:
            baseline_aaxb = baseline_rates[aaxb_mask, :]
            p1_aaxb = p1_rates[aaxb_mask, :]
            p2_aaxb = p2_rates[aaxb_mask, :]
            omission_aaxb = omission_rates[aaxb_mask, :]

            is_ox, ox_p, ox_pct = classify_ox(
                baseline_aaxb, p1_aaxb, p2_aaxb, omission_aaxb, config
            )
    
    # Assign display classes
    display_classes = assign_display_class(is_s_plus, is_s_minus, is_ox)
    
    # Build classification table
    rows = []
    for unit_idx in range(n_units):
        row = {
            "unit_idx": unit_idx,
            "unit_id": unit_metadata.iloc[unit_idx].get("unit_id", f"unit_{unit_idx}"),
            "session": unit_metadata.iloc[unit_idx].get("session", "unknown"),
            "area": unit_metadata.iloc[unit_idx].get("area", None),
            
            # Firing rates
            "baseline_rate_hz": np.mean(baseline_rates[:, unit_idx]),
            "p1_rate_hz": np.mean(p1_rates[:, unit_idx]),
            "p2_rate_hz": np.mean(p2_rates[:, unit_idx]),
            "omission_rate_hz": float(np.mean(omission_rates[:, unit_idx])),
            
            # S+ stats
            "s_plus_p_value": s_plus_p[unit_idx],
            "s_plus_percent_change": s_plus_pct[unit_idx],
            "is_s_plus": is_s_plus[unit_idx],
            
            # S- stats
            "s_minus_p_value": s_minus_p[unit_idx],
            "s_minus_percent_change": s_minus_pct[unit_idx],
            "is_s_minus": is_s_minus[unit_idx],
            
            # O/X stats
            "ox_p_value": ox_p[unit_idx],
            "ox_percent_change": ox_pct[unit_idx],
            "is_ox": is_ox[unit_idx],
            
            # Display class
            "display_class": display_classes[unit_idx],
            
            # Trial counts
            "n_trials": n_trials,
            "n_trials_aaxb": np.sum(trial_conditions == "AAXB") if trial_conditions is not None else None,
        }
        rows.append(row)
    
    classification_table = pd.DataFrame(rows)
    
    # Build manifest
    manifest = {
        "created_at": datetime.now().isoformat(),
        "anchor_code": 101,
        "time_base": "p1_relative",
        "config": {
            "window_baseline": config.window_baseline,
            "window_p1": config.window_p1,
            "window_p2": config.window_p2,
            "window_p3_omission": config.window_p3_omission,
            "p_threshold": config.p_threshold,
            "effect_increase": config.effect_increase,
            "effect_decrease": config.effect_decrease,
            "min_trials": config.min_trials,
            "epsilon_hz": config.epsilon_hz,
        },
        "classification_summary": {
            "n_units": n_units,
            "n_s_plus": int(np.sum(is_s_plus)),
            "n_s_minus": int(np.sum(is_s_minus)),
            "n_ox": int(np.sum(is_ox)),
            "overlap_s_plus_ox": int(np.sum(is_s_plus & is_ox)),
            "overlap_s_minus_ox": int(np.sum(is_s_minus & is_ox)),
            "overlap_s_plus_s_minus": int(np.sum(is_s_plus & is_s_minus)),
        },
        "display_class_counts": {
            cls: int(np.sum(display_classes == cls))
            for cls in ["S+", "S-", "O/X", "unclassified"]
        },
    }
    
    return classification_table, manifest


def main():
    parser = argparse.ArgumentParser(
        description="Classify single units into S+, S-, and O/X categories"
    )
    parser.add_argument(
        "--epochs-p1",
        type=Path,
        required=True,
        help="Path to p1-aligned SPK epochs NPZ file",
    )
    parser.add_argument(
        "--epochs-omission",
        type=Path,
        default=None,
        help="Path to omission-aligned SPK epochs NPZ file (for O/X)",
    )
    parser.add_argument(
        "--unit-metadata",
        type=Path,
        required=True,
        help="Path to unit metadata CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/f005/classification"),
        help="Output directory",
    )
    parser.add_argument(
        "--min-trials",
        type=int,
        default=MIN_TRIALS_DEFAULT,
        help=f"Minimum trials for classification (default {MIN_TRIALS_DEFAULT})",
    )
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("UNIT CLASSIFICATION: S+, S-, O/X")
    print("=" * 80)
    
    # Load data
    print(f"\nLoading epochs: {args.epochs_p1}")
    p1_data = np.load(args.epochs_p1, allow_pickle=True)
    spk_epochs_p1 = p1_data["spk_epochs"]
    time_axis_ms = p1_data["time_axis_ms"]

    trial_conditions = None
    if "condition_labels" in p1_data:
        trial_conditions = p1_data["condition_labels"]
    elif "trial_conditions" in p1_data:
        trial_conditions = p1_data["trial_conditions"]

    anchor_provenance = {
        "anchor_code": int(p1_data["anchor_code"]) if "anchor_code" in p1_data else 101,
        "time_base": str(p1_data["time_base"]) if "time_base" in p1_data else "p1_relative",
    }
    if "anchor_type" in p1_data:
        anchor_provenance["anchor_type"] = str(p1_data["anchor_type"])

    print(f"  Shape: {spk_epochs_p1.shape}")
    print(f"  Time axis: {time_axis_ms[0]} to {time_axis_ms[-1]} ms")
    if trial_conditions is not None:
        print(f"  Condition labels: {np.unique(trial_conditions)}")

    spk_epochs_omission = None
    if args.epochs_omission and args.epochs_omission.exists():
        print(f"\nLoading omission epochs: {args.epochs_omission}")
        om_data = np.load(args.epochs_omission, allow_pickle=True)
        spk_epochs_omission = om_data["spk_epochs"]
        print(f"  Shape: {spk_epochs_omission.shape}")
    
    print(f"\nLoading unit metadata: {args.unit_metadata}")
    unit_metadata = pd.read_csv(args.unit_metadata)
    print(f"  Units: {len(unit_metadata)}")
    
    # Configure
    config = ClassificationConfig(min_trials=args.min_trials)
    
    # Classify
    print("\nClassifying units...")
    classification_table, manifest = classify_units_from_epochs(
        spk_epochs_p1=spk_epochs_p1,
        spk_epochs_omission=spk_epochs_omission,
        time_axis_ms=time_axis_ms,
        unit_metadata=unit_metadata,
        trial_conditions=trial_conditions,
        config=config,
        anchor_provenance=anchor_provenance,
    )

    # Save outputs
    args.output.mkdir(parents=True, exist_ok=True)

    table_path = args.output / "unit_classification.csv"
    classification_table.to_csv(table_path, index=False)
    print(f"\nSaved classification table: {table_path}")

    diagnostics_path = args.output / "f005_classification_diagnostics.csv"
    classification_table.to_csv(diagnostics_path, index=False)
    print(f"Saved diagnostics: {diagnostics_path}")
    
    manifest_path = args.output / "classification_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved manifest: {manifest_path}")
    
    # Summary
    print("\n" + "=" * 80)
    print("CLASSIFICATION SUMMARY")
    print("=" * 80)
    for cls, count in manifest["display_class_counts"].items():
        print(f"  {cls}: {count}")
    
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
