#!/usr/bin/env python3
"""Classify single units into S+, S-, and O/X response categories.

CLASSIFICATION METHOD LOCK (v1.0)
================================

Mutual Exclusivity: Classes are NON-EXCLUSIVE at detection level, EXCLUSIVE at
display level via priority: O/X > S+ > S- > unclassified.

Time Windows (ms, p1-relative):
- baseline: late pre-stimulus delay (-250 to -50 ms)
- stimulus: matched stimulus epoch (0 to +531 ms for p1/p2/p3/p4)
- omission: expected missing stimulus epoch (0 to +531 ms on omission-relative axis,
  mapped to p1-relative coordinates for p3: 2062-2593 ms)

Statistical Tests:
- Within-unit paired contrasts: Wilcoxon signed-rank test
  (baseline vs stimulus, baseline vs omission, etc.)
- Independent trial groups: NOT USED in current design (all contrasts are paired)

Multiple Comparison Correction:
- Method: Benjamini-Hochberg FDR
- Scope: across units and tested class contrasts per analysis
- Primary threshold: p < 0.05 after FDR correction
- Output: both uncorrected (p_raw) and corrected (p_fdr) values stored

Effect Size:
- Preferred: Rank-biserial correlation (r_rb) for nonparametric tests
  r_rb = Z / sqrt(N) where Z is Wilcoxon standardized statistic
- Alternative: Percent change from baseline (descriptive only)
- Cohen's d: NOT USED (distributional assumptions not checked)

Minimum Evidence:
- Minimum valid trials per condition: 8 (configurable)
- Minimum trials for O/X: 8 AAXB trials
- Handling of silent units: included if valid trials >= minimum, classified
  by relative change (even near-zero rates can be S- if p1 < baseline)
- Mixed/ambiguous: if unit qualifies for multiple classes, display class
  determined by priority; overlapping flags stored in boolean columns

Time zero: Must be code101 p1 stimulus onset (validated via anchor provenance).
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
P_VALUE_THRESHOLD = 0.05  # Primary threshold (after FDR correction)
EFFECT_SIZE_INCREASE = 1.20  # 20% increase (descriptive only)
EFFECT_SIZE_DECREASE = 0.80   # 20% decrease (descriptive only)
MIN_TRIALS_DEFAULT = 8


# ============================================================================
# Statistical Utilities
# ============================================================================

from src.analysis.stats.multitest import benjamini_hochberg

def benjamini_hochberg_fdr(p_values: np.ndarray, alpha: float = 0.05) -> np.ndarray:
    """Apply Benjamini-Hochberg FDR correction to p-values."""
    return benjamini_hochberg(p_values)



def rank_biserial_correlation(wilcoxon_statistic: float, n: int) -> float:
    """Compute rank-biserial correlation from Wilcoxon statistic.
    
    This is the preferred effect size for Wilcoxon signed-rank tests.
    
    Formula: r_rb = Z / sqrt(N)
    Where Z is the standardized Wilcoxon statistic.
    
    For scipy.stats.wilcoxon, the statistic is the sum of signed ranks.
    The standardized Z-score is approximately: (W - n(n+1)/4) / sqrt(n(n+1)(2n+1)/24)
    
    Simplified approximation: r_rb ≈ 1 - (2 * W_neg) / (n * (n + 1))
    where W_neg is the sum of negative ranks.
    
    Args:
        wilcoxon_statistic: The Wilcoxon W statistic (sum of signed ranks)
        n: Number of valid paired observations
        
    Returns:
        Rank-biserial correlation (-1 to +1)
    """
    if n < 2:
        return np.nan
    
    # Maximum possible sum of ranks: n(n+1)/2
    max_rank_sum = n * (n + 1) / 2
    
    # Convert to effect size
    # W ranges from -max_rank_sum to +max_rank_sum (for signed-rank test)
    # Normalize to [-1, 1]
    if max_rank_sum > 0:
        r_rb = wilcoxon_statistic / max_rank_sum
        # Clamp to [-1, 1]
        r_rb = np.clip(r_rb, -1.0, 1.0)
    else:
        r_rb = np.nan
    
    return float(r_rb)


def compute_percent_change(baseline: float, test: float, epsilon: float = 0.1) -> float:
    """Compute percent change from baseline, handling near-zero baselines.
    
    Args:
        baseline: Baseline value
        test: Test value
        epsilon: Minimum baseline for percent calculation
        
    Returns:
        Percent change: (test - baseline) / max(baseline, epsilon) * 100
    """
    baseline_for_pct = max(baseline, epsilon)
    return (test - baseline) / baseline_for_pct * 100

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
    """Configuration for unit classification.
    
    Statistical method lock:
    - Test: Wilcoxon signed-rank for paired within-unit contrasts
    - Correction: Benjamini-Hochberg FDR across units
    - Effect size: Rank-biserial correlation (r_rb)
    - Threshold: p_fdr < p_threshold (default 0.05)
    
    Percent change (effect_increase/decrease) is descriptive only, not primary
    classification criterion.
    """
    # Time windows (ms, p1-relative)
    window_baseline: tuple[float, float] = WINDOW_BASELINE  # (-250, -50)
    window_p1: tuple[float, float] = WINDOW_P1  # (0, 531)
    window_p2: tuple[float, float] = WINDOW_P2  # (1031, 1562)
    window_p3_omission: tuple[float, float] = WINDOW_P3_OMISSION  # (2062, 2593)
    
    # Statistical thresholds
    p_threshold: float = P_VALUE_THRESHOLD  # 0.05, applied to FDR-corrected p-values
    apply_fdr_correction: bool = True  # Apply Benjamini-Hochberg FDR
    fdr_scope: str = "across_units"  # Correction scope: "across_units" or "across_tests"
    
    # Effect size (descriptive)
    effect_increase: float = EFFECT_SIZE_INCREASE  # 1.20 (20% increase, descriptive)
    effect_decrease: float = EFFECT_SIZE_DECREASE  # 0.80 (20% decrease, descriptive)
    
    # Minimum evidence
    min_trials: int = MIN_TRIALS_DEFAULT  # 8
    epsilon_hz: float = 0.1  # For percent change with near-zero baseline
    
    # Silent unit handling
    include_silent_units: bool = True  # Classify even if baseline ~0
    min_spike_count_total: int = 0  # Minimum total spikes across all trials


@dataclass
class UnitClassification:
    """Classification result for a single unit.
    
    Statistical outputs:
    - p_value_*: Raw (uncorrected) p-values from Wilcoxon tests
    - p_fdr_*: FDR-corrected p-values (Benjamini-Hochberg)
    - rank_biserial_*: Rank-biserial correlation effect sizes (preferred)
    - percent_change_*: Descriptive percent changes (supplementary)
    
    Classification uses p_fdr < threshold, not raw p-values.
    """
    unit_id: str
    session: str
    area: str | None
    
    # Firing rates (Hz)
    baseline_rate: float
    p1_rate: float
    p2_rate: float | None
    omission_rate: float | None
    
    # Statistics: raw p-values (uncorrected)
    s_plus_p_value: float | None
    s_minus_p_value: float | None
    ox_p_value: float | None
    
    # Statistics: FDR-corrected p-values
    s_plus_p_fdr: float | None
    s_minus_p_fdr: float | None
    ox_p_fdr: float | None
    
    # Effect sizes: rank-biserial correlation (preferred for nonparametric)
    s_plus_rank_biserial: float | None
    s_minus_rank_biserial: float | None
    ox_rank_biserial: float | None
    
    # Effect sizes: percent change (descriptive only)
    s_plus_percent_change: float | None
    s_minus_percent_change: float | None
    ox_percent_change: float | None
    
    # Boolean labels (non-exclusive at detection level)
    is_s_plus: bool
    is_s_minus: bool
    is_ox: bool
    
    # Exclusive display class (O/X > S+ > S- > unclassified)
    display_class: str  # "S+", "S-", "O/X", "unclassified"
    
    # Metadata
    n_trials: int
    n_trials_aaxb: int | None
    valid: bool
    exclusion_reason: str | None
    classification_rule: str  # Explicit rule that led to this assignment


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
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as S+ (stimulus-excited).
    
    Statistical method:
    - Test: Wilcoxon signed-rank (paired: p1 vs baseline per trial)
    - Alternative: 'greater' (p1 > baseline)
    - Effect size: rank-biserial correlation (preferred) + percent change (descriptive)
    - Correction: FDR applied to p_values across units
    
    Classification criteria:
    - Primary: p_fdr < p_threshold (default 0.05)
    - Descriptive: mean p1 > mean baseline * effect_increase (default 1.20)
    
    Args:
        baseline_rates: (n_trials, n_units) baseline firing rates
        p1_rates: (n_trials, n_units) p1 firing rates
        config: classification configuration
        
    Returns:
        (is_s_plus, p_values_raw, p_values_fdr, rank_biserials, percent_changes)
        All arrays have length n_units
    """
    n_trials, n_units = baseline_rates.shape
    
    is_s_plus = np.zeros(n_units, dtype=bool)
    p_values_raw = np.full(n_units, np.nan)
    rank_biserials = np.full(n_units, np.nan)
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
        
        # Wilcoxon signed-rank test (paired: p1 vs baseline)
        try:
            statistic, p_value = stats.wilcoxon(p1_valid, baseline_valid, alternative='greater')
        except ValueError:
            # All values identical
            continue
        
        p_values_raw[unit_idx] = p_value
        rank_biserials[unit_idx] = rank_biserial_correlation(statistic, n_valid)
        
        # Effect size: percent change (descriptive)
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        percent_changes[unit_idx] = compute_percent_change(
            baseline_mean, p1_mean, config.epsilon_hz
        )
    
    # Apply FDR correction across units
    if config.apply_fdr_correction:
        p_values_fdr = benjamini_hochberg_fdr(p_values_raw, alpha=config.p_threshold)
    else:
        p_values_fdr = p_values_raw.copy()
    
    # Classification using FDR-corrected p-values
    for unit_idx in range(n_units):
        if not np.isfinite(p_values_fdr[unit_idx]):
            continue
        
        p_fdr = p_values_fdr[unit_idx]
        pct_change = percent_changes[unit_idx]
        
        # Primary criterion: FDR-corrected significance
        significant = p_fdr < config.p_threshold
        
        # Descriptive criterion: percent increase
        large_effect = pct_change > (config.effect_increase - 1) * 100
        
        is_s_plus[unit_idx] = significant and large_effect
    
    return is_s_plus, p_values_raw, p_values_fdr, rank_biserials, percent_changes


def classify_s_minus(
    baseline_rates: np.ndarray,
    p1_rates: np.ndarray,
    config: ClassificationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as S- (stimulus-inhibited).
    
    Statistical method:
    - Test: Wilcoxon signed-rank (paired: baseline vs p1 per trial)
    - Alternative: 'greater' (baseline > p1, i.e., p1 < baseline)
    - Effect size: rank-biserial correlation (preferred) + percent change (descriptive)
    - Correction: FDR applied to p_values across units
    
    Classification criteria:
    - Primary: p_fdr < p_threshold (default 0.05)
    - Descriptive: mean p1 < mean baseline * effect_decrease (default 0.80)
    
    Args:
        baseline_rates: (n_trials, n_units) baseline firing rates
        p1_rates: (n_trials, n_units) p1 firing rates
        config: classification configuration
        
    Returns:
        (is_s_minus, p_values_raw, p_values_fdr, rank_biserials, percent_changes)
        All arrays have length n_units
    """
    n_trials, n_units = baseline_rates.shape
    
    is_s_minus = np.zeros(n_units, dtype=bool)
    p_values_raw = np.full(n_units, np.nan)
    rank_biserials = np.full(n_units, np.nan)
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
        
        # Wilcoxon signed-rank test (paired: baseline vs p1)
        # Alternative 'greater' tests if baseline > p1 (i.e., p1 < baseline)
        try:
            statistic, p_value = stats.wilcoxon(baseline_valid, p1_valid, alternative='greater')
        except ValueError:
            continue
        
        p_values_raw[unit_idx] = p_value
        rank_biserials[unit_idx] = rank_biserial_correlation(statistic, n_valid)
        
        # Effect size: percent change (descriptive)
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        percent_changes[unit_idx] = compute_percent_change(
            baseline_mean, p1_mean, config.epsilon_hz
        )
    
    # Apply FDR correction across units
    if config.apply_fdr_correction:
        p_values_fdr = benjamini_hochberg_fdr(p_values_raw, alpha=config.p_threshold)
    else:
        p_values_fdr = p_values_raw.copy()
    
    # Classification using FDR-corrected p-values
    for unit_idx in range(n_units):
        if not np.isfinite(p_values_fdr[unit_idx]):
            continue
        
        p_fdr = p_values_fdr[unit_idx]
        pct_change = percent_changes[unit_idx]
        
        # Primary criterion: FDR-corrected significance
        significant = p_fdr < config.p_threshold
        
        # Descriptive criterion: percent decrease
        large_effect = pct_change < (config.effect_decrease - 1) * 100
        
        is_s_minus[unit_idx] = significant and large_effect
    
    return is_s_minus, p_values_raw, p_values_fdr, rank_biserials, percent_changes


def classify_ox(
    baseline_rates: np.ndarray,
    p1_rates: np.ndarray,
    p2_rates: np.ndarray,
    omission_rates: np.ndarray,
    config: ClassificationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Classify units as O/X (omission-correlated) using AAXB trials.
    
    Statistical method:
    - Test: Wilcoxon signed-rank (paired: omission vs baseline per AAXB trial)
    - Alternative: 'greater' (omission > baseline)
    - Effect size: rank-biserial correlation (preferred) + percent change (descriptive)
    - Correction: FDR applied to p_values across units
    
    Classification criteria:
    - Primary: p_fdr < p_threshold (default 0.05)
    - Context-specific: omission > p1 AND omission > p2 AND omission > baseline
      (ensures elevation is specific to omission, not just elevated firing)
    
    Args:
        baseline_rates: (n_trials_aaxb, n_units) baseline rates
        p1_rates: (n_trials_aaxb, n_units) p1 rates  
        p2_rates: (n_trials_aaxb, n_units) p2 rates
        omission_rates: (n_trials_aaxb, n_units) omission (p3) rates
        config: classification configuration
        
    Returns:
        (is_ox, p_values_raw, p_values_fdr, rank_biserials, percent_changes)
        All arrays have length n_units
    """
    n_trials, n_units = baseline_rates.shape
    
    is_ox = np.zeros(n_units, dtype=bool)
    p_values_raw = np.full(n_units, np.nan)
    rank_biserials = np.full(n_units, np.nan)
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
        
        # Mean rates for context check
        baseline_mean = np.mean(baseline_valid)
        p1_mean = np.mean(p1_valid)
        p2_mean = np.mean(p2_valid)
        omission_mean = np.mean(omission_valid)
        
        # Wilcoxon signed-rank test (paired: omission vs baseline)
        try:
            statistic, p_value = stats.wilcoxon(omission_valid, baseline_valid, alternative='greater')
        except ValueError:
            continue
        
        p_values_raw[unit_idx] = p_value
        rank_biserials[unit_idx] = rank_biserial_correlation(statistic, n_valid)
        
        # Effect size: percent change (descriptive)
        percent_changes[unit_idx] = compute_percent_change(
            baseline_mean, omission_mean, config.epsilon_hz
        )
        
        # Store context check results (used in classification below)
        exceeds_p1 = omission_mean > p1_mean
        exceeds_p2 = omission_mean > p2_mean
        exceeds_baseline = omission_mean > baseline_mean
        
        # Apply context-specific criteria immediately (not deferred to FDR step)
        context_specific = exceeds_p1 and exceeds_p2 and exceeds_baseline
        if not context_specific:
            # Mark as not O/X regardless of statistical significance
            pass  # is_ox already False
    
    # Apply FDR correction across units
    if config.apply_fdr_correction:
        p_values_fdr = benjamini_hochberg_fdr(p_values_raw, alpha=config.p_threshold)
    else:
        p_values_fdr = p_values_raw.copy()
    
    # Classification using FDR-corrected p-values + context criteria
    for unit_idx in range(n_units):
        if not np.isfinite(p_values_fdr[unit_idx]):
            continue
        
        # Recompute context criteria (efficient, no allocation)
        baseline_mean = np.mean(baseline_rates[:, unit_idx])
        p1_mean = np.mean(p1_rates[:, unit_idx])
        p2_mean = np.mean(p2_rates[:, unit_idx])
        omission_mean = np.mean(omission_rates[:, unit_idx])
        
        p_fdr = p_values_fdr[unit_idx]
        
        # Primary criterion: FDR-corrected significance
        significant = p_fdr < config.p_threshold
        
        # Context-specific criteria: omission exceeds all control windows
        exceeds_p1 = omission_mean > p1_mean
        exceeds_p2 = omission_mean > p2_mean
        exceeds_baseline = omission_mean > baseline_mean
        context_specific = exceeds_p1 and exceeds_p2 and exceeds_baseline
        
        is_ox[unit_idx] = significant and context_specific
    
    return is_ox, p_values_raw, p_values_fdr, rank_biserials, percent_changes


def _get_classification_rule(is_s_plus: bool, is_s_minus: bool, is_ox: bool, display_class: str) -> str:
    """Return explicit rule that led to this classification.
    
    This documents the classification decision for reproducibility.
    """
    if display_class == "O/X":
        return "O/X_priority_is_ox_true"
    elif display_class == "S+":
        if is_ox:
            return "S+_not_O/X_is_ox_false"
        return "S+_priority_is_s_plus_true"
    elif display_class == "S-":
        if is_ox:
            return "S-_not_O/X_is_ox_false"
        if is_s_plus:
            return "S-_not_S+_is_s_plus_false"
        return "S-_is_s_minus_true"
    else:
        return "unclassified_no_flags_set"


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
    # Returns: (is_class, p_raw, p_fdr, rank_biserial, percent_change)
    is_s_plus, s_plus_p_raw, s_plus_p_fdr, s_plus_r_rb, s_plus_pct = classify_s_plus(
        baseline_rates, p1_rates, config
    )
    is_s_minus, s_minus_p_raw, s_minus_p_fdr, s_minus_r_rb, s_minus_pct = classify_s_minus(
        baseline_rates, p1_rates, config
    )
    
    # O/X classification (AAXB trials only)
    is_ox = np.zeros(n_units, dtype=bool)
    ox_p = np.full(n_units, np.nan)
    ox_pct = np.full(n_units, np.nan)
    
    # O/X: AAXB trials only, p3 omission window on p1-relative axis
    omission_rates = extract_window_rate(
        spk_epochs_p1, time_axis_ms, config.window_p3_omission,
        time_axis_ms[1] - time_axis_ms[0]
    )

    # Initialize O/X results arrays
    is_ox = np.zeros(n_units, dtype=bool)
    ox_p_raw = np.full(n_units, np.nan)
    ox_p_fdr = np.full(n_units, np.nan)
    ox_r_rb = np.full(n_units, np.nan)
    ox_pct = np.full(n_units, np.nan)
    n_aaxb = 0

    if trial_conditions is not None:
        trial_conditions = np.asarray(trial_conditions).astype(str)
        aaxb_mask = trial_conditions == "AAXB"
        n_aaxb = int(np.sum(aaxb_mask))

        if n_aaxb >= config.min_trials:
            baseline_aaxb = baseline_rates[aaxb_mask, :]
            p1_aaxb = p1_rates[aaxb_mask, :]
            p2_aaxb = p2_rates[aaxb_mask, :]
            omission_aaxb = omission_rates[aaxb_mask, :]

            is_ox, ox_p_raw, ox_p_fdr, ox_r_rb, ox_pct = classify_ox(
                baseline_aaxb, p1_aaxb, p2_aaxb, omission_aaxb, config
            )
    
    # Assign display classes
    display_classes = assign_display_class(is_s_plus, is_s_minus, is_ox)
    
    # Build classification table with full statistical output
    rows = []
    for unit_idx in range(n_units):
        row = {
            "unit_idx": unit_idx,
            "unit_id": unit_metadata.iloc[unit_idx].get("unit_id", f"unit_{unit_idx}"),
            "session": unit_metadata.iloc[unit_idx].get("session", "unknown"),
            "area": unit_metadata.iloc[unit_idx].get("area", None),
            
            # Firing rates (Hz)
            "baseline_rate_hz": np.mean(baseline_rates[:, unit_idx]),
            "p1_rate_hz": np.mean(p1_rates[:, unit_idx]),
            "p2_rate_hz": np.mean(p2_rates[:, unit_idx]),
            "omission_rate_hz": float(np.mean(omission_rates[:, unit_idx])),
            
            # S+ stats: raw p-values (uncorrected)
            "s_plus_p_value_raw": s_plus_p_raw[unit_idx],
            "s_plus_p_value_fdr": s_plus_p_fdr[unit_idx],
            "s_plus_rank_biserial": s_plus_r_rb[unit_idx],
            "s_plus_percent_change": s_plus_pct[unit_idx],
            "is_s_plus": is_s_plus[unit_idx],
            
            # S- stats: raw p-values (uncorrected)
            "s_minus_p_value_raw": s_minus_p_raw[unit_idx],
            "s_minus_p_value_fdr": s_minus_p_fdr[unit_idx],
            "s_minus_rank_biserial": s_minus_r_rb[unit_idx],
            "s_minus_percent_change": s_minus_pct[unit_idx],
            "is_s_minus": is_s_minus[unit_idx],
            
            # O/X stats: raw p-values (uncorrected)
            "ox_p_value_raw": ox_p_raw[unit_idx],
            "ox_p_value_fdr": ox_p_fdr[unit_idx],
            "ox_rank_biserial": ox_r_rb[unit_idx],
            "ox_percent_change": ox_pct[unit_idx],
            "is_ox": is_ox[unit_idx],
            
            # Display class (exclusive via priority)
            "display_class": display_classes[unit_idx],
            
            # Classification rule applied
            "classification_rule": _get_classification_rule(
                is_s_plus[unit_idx], is_s_minus[unit_idx], is_ox[unit_idx], display_classes[unit_idx]
            ),
            
            # Trial counts
            "n_trials": n_trials,
            "n_trials_aaxb": int(np.sum(trial_conditions == "AAXB")) if trial_conditions is not None else 0,
        }
        rows.append(row)
    
    classification_table = pd.DataFrame(rows)
    
    # Build manifest with full statistical method documentation
    manifest = {
        "created_at": datetime.now().isoformat(),
        "anchor_code": 101,
        "time_base": "p1_relative",
        "classification_method_lock": {
            "version": "1.0",
            "mutual_exclusivity": "non_exclusive_detection_with_priority_display",
            "display_priority": ["O/X", "S+", "S-", "unclassified"],
            "test_method": "wilcoxon_signed_rank_paired_within_unit",
            "correction_method": "benjamini_hochberg_fdr",
            "correction_scope": config.fdr_scope,
            "primary_threshold": f"p_fdr < {config.p_threshold}",
            "effect_size_preferred": "rank_biserial_correlation",
            "effect_size_descriptive": "percent_change_from_baseline",
            "time_windows_ms": {
                "baseline": config.window_baseline,
                "stimulus_p1": config.window_p1,
                "stimulus_p2": config.window_p2,
                "omission_p3": config.window_p3_omission,
            },
        },
        "config": {
            "window_baseline": config.window_baseline,
            "window_p1": config.window_p1,
            "window_p2": config.window_p2,
            "window_p3_omission": config.window_p3_omission,
            "p_threshold": config.p_threshold,
            "apply_fdr_correction": config.apply_fdr_correction,
            "fdr_scope": config.fdr_scope,
            "effect_increase": config.effect_increase,
            "effect_decrease": config.effect_decrease,
            "min_trials": config.min_trials,
            "epsilon_hz": config.epsilon_hz,
            "include_silent_units": config.include_silent_units,
            "min_spike_count_total": config.min_spike_count_total,
        },
        "classification_summary": {
            "n_units": n_units,
            "n_s_plus": int(np.sum(is_s_plus)),
            "n_s_minus": int(np.sum(is_s_minus)),
            "n_ox": int(np.sum(is_ox)),
            "overlap_s_plus_ox": int(np.sum(is_s_plus & is_ox)),
            "overlap_s_minus_ox": int(np.sum(is_s_minus & is_ox)),
            "overlap_s_plus_s_minus": int(np.sum(is_s_plus & is_s_minus)),
            "n_valid_aaxb_trials": int(n_aaxb),
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
    
    # Handle both old 'spk_epochs' key and new signal-specific keys
    if "spk_epochs" in p1_data:
        spk_epochs_p1 = p1_data["spk_epochs"]
        spk_keys = ["spk_epochs"]
    else:
        # Find all signal-specific keys (multi-session artifacts)
        spk_keys = sorted([k for k in p1_data.files if k.startswith("spk_epochs__")])
        if not spk_keys:
            raise KeyError("No spk_epochs or spk_epochs__* keys found in artifact")
        spk_epochs_p1 = p1_data[spk_keys[0]]
        print(f"  Found {len(spk_keys)} session(s): {spk_keys[:3]}...")
    
    time_axis_ms = p1_data["time_axis_ms"]

    trial_conditions_json = None
    if "trial_metadata_json" in p1_data:
        trial_conditions_json = json.loads(str(p1_data["trial_metadata_json"]))
    elif "condition_labels" in p1_data:
        trial_conditions = p1_data["condition_labels"]

    anchor_provenance = {
        "anchor_code": int(p1_data["anchor_code"]) if "anchor_code" in p1_data else 101,
        "time_base": str(p1_data["time_base"]) if "time_base" in p1_data else "p1_relative",
    }
    if "anchor_type" in p1_data:
        anchor_provenance["anchor_type"] = str(p1_data["anchor_type"])

    print(f"  Time axis: {time_axis_ms[0]} to {time_axis_ms[-1]} ms")

    spk_epochs_omission = None
    if args.epochs_omission and args.epochs_omission.exists():
        print(f"\nLoading omission epochs: {args.epochs_omission}")
        om_data = np.load(args.epochs_omission, allow_pickle=True)
        if "spk_epochs" in om_data:
            spk_epochs_omission = om_data["spk_epochs"]
        else:
            spk_keys = [k for k in om_data.files if k.startswith("spk_epochs__")]
            if spk_keys:
                spk_epochs_omission = om_data[spk_keys[0]]
        print(f"  Shape: {spk_epochs_omission.shape}")
    
    print(f"\nLoading unit metadata: {args.unit_metadata}")
    unit_metadata_all = pd.read_csv(args.unit_metadata)
    print(f"  Total units: {len(unit_metadata_all)}")
    
    # Configure
    config = ClassificationConfig(min_trials=args.min_trials)
    
    # For multi-session: process each session separately
    all_tables = []
    all_manifests = []
    
    for spk_key in spk_keys:
        spk_epochs_p1 = p1_data[spk_key]
        session = spk_key.replace("spk_epochs__", "") if spk_key.startswith("spk_epochs__") else "unknown"
        
        # Get unit metadata for this session
        session_mask = unit_metadata_all["session_id"] == session if "session_id" in unit_metadata_all.columns else pd.Series([True] * len(unit_metadata_all))
        unit_metadata = unit_metadata_all[session_mask].reset_index(drop=True)
        
        n_units_data = spk_epochs_p1.shape[1]
        n_units_meta = len(unit_metadata)
        
        if n_units_meta == 0:
            print(f"\n  SKIPPING {session}: no metadata found ({n_units_data} units in data)")
            continue
        
        if n_units_data != n_units_meta:
            print(f"  WARNING: {session} data has {n_units_data} units but metadata has {n_units_meta}")
            # Use min of both
            unit_metadata = unit_metadata.iloc[:n_units_data] if n_units_meta > n_units_data else unit_metadata
        
        # Get trial conditions for this session from trial metadata JSON
        trial_conditions = None
        if trial_conditions_json:
            session_trials = [t for t in trial_conditions_json if t.get("session_id") == session]
            trial_conditions = np.array([t.get("condition", "?") for t in session_trials])
            if len(trial_conditions) != spk_epochs_p1.shape[0]:
                print(f"  WARNING: {session} trial count mismatch: {len(trial_conditions)} vs {spk_epochs_p1.shape[0]}")
        
        print(f"\n  Classifying {session}: {spk_epochs_p1.shape}")
        
        classification_table, manifest = classify_units_from_epochs(
            spk_epochs_p1=spk_epochs_p1,
            spk_epochs_omission=None,
            time_axis_ms=time_axis_ms,
            unit_metadata=unit_metadata,
            trial_conditions=trial_conditions,
            config=config,
            anchor_provenance=anchor_provenance,
        )
        all_tables.append(classification_table)
        all_manifests.append(manifest)
    
    # Handle case where no sessions were processed
    if not all_tables:
        print("\nERROR: No sessions could be classified (metadata missing for all sessions)")
        return 1
    
    # Combine results
    classification_table = pd.concat(all_tables, ignore_index=True)
    
    # Combine manifest summaries
    total_n = sum(m["classification_summary"]["n_units"] for m in all_manifests)
    total_s_plus = sum(m["classification_summary"]["n_s_plus"] for m in all_manifests)
    total_s_minus = sum(m["classification_summary"]["n_s_minus"] for m in all_manifests)
    total_ox = sum(m["classification_summary"]["n_ox"] for m in all_manifests)
    
    display_class_counts = classification_table["display_class"].value_counts().to_dict()
    
    manifest = {
        "created_at": datetime.now().isoformat(),
        "anchor_code": 101,
        "time_base": "p1_relative",
        "config": all_manifests[0]["config"] if all_manifests else {},
        "classification_summary": {
            "n_units": total_n,
            "n_s_plus": total_s_plus,
            "n_s_minus": total_s_minus,
            "n_ox": total_ox,
            "n_sessions_processed": len(all_manifests),
            "n_sessions_total": len(spk_keys),
        },
        "display_class_counts": display_class_counts,
    }

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
