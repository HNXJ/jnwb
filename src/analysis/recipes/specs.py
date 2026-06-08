"""Specification dataclasses for analysis recipes.

Defines the contract between data, analysis parameters, and outputs.
Every spec includes shape expectations, units, and axis preservation rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Literal, Sequence, Mapping, Any, Tuple

# Type aliases for clarity
SignalClass = Literal["SPK", "SPK_SMOOTH", "MUAe", "LFP", "TFR", "BAND_POWER"]
TimeBase = Literal["p1_relative", "omission_relative", "flash_relative", "NWB_absolute"]
LayerStatus = Literal["unresolved", "putative", "validated"]
AnalysisKind = Literal[
    "spike_rate",
    "smoothed_spike_rate",
    "tfr",
    "band_power",
    "spectral_coherence",
    "spike_lfp_mi",
    "spike_phase_locking",
    "pac",
    "Y_tensor",
    "H_harmony",
]

# Canonical areas per project specification
# Note: V3d and V3a are kept separate (not collapsed)
CANONICAL_AREAS = ["V1", "V2", "V3d", "V3a", "V4", "MT", "MST", "TEO", "FST", "FEF", "PFC"]

# Publication-ready band definitions (Hz)
# Values are (low_freq, high_freq) tuples. None for high_freq means open-ended.
PUBLICATION_BANDS: dict[str, tuple[float, float | None]] = {
    "delta": (0.0, 3.0),
    "theta": (3.0, 7.0),
    "alpha": (8.0, 12.0),
    "beta_L": (12.0, 20.0),
    "beta_H": (20.0, 30.0),
    "gamma_L": (32.0, 50.0),
    "gamma_M": (50.0, 90.0),
    "gamma_H": (90.0, None),
}


@dataclass(frozen=True)
class EventSpec:
    """Specification for event timing extraction.
    
    Shape expectations:
    - Output is dict[str, np.ndarray] mapping condition -> onset times
    - Each array is 1D float64, shape (n_trials,)
    
    Units:
    - All times are in seconds, NWB time base
    
    Time base:
    - "p1_relative": times are relative to P1 stimulus onset (0 ms)
    - "omission_relative": times are relative to omission event
    - "flash_relative": times are relative to flash event
    - "NWB_absolute": raw NWB timestamps (uncommon for analysis)
    
    Trial structure:
    - Event vectors preserve trial order from NWB intervals table
    - No trial averaging at this stage
    """
    event: str = "p1"  # Event marker to align to
    conditions: tuple[str, ...] = (
        "AAAB", "AXAB", "AAXB", "AAAX",
        "BBBA", "BXBA", "BBXA", "BBBX",
        "RRRR", "RXRR", "RRXR", "RRRX",
    )
    time_unit: str = "seconds"
    time_base: TimeBase = "p1_relative"
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class WindowSpec:
    """Specification for temporal windowing around events.
    
    Shape expectations:
    - Window is applied to each trial independently
    - Output arrays gain a time axis of length n_time_samples
    
    Units:
    - pre_ms, post_ms: milliseconds relative to event onset
    - baseline_ms: (start_ms, end_ms) for baseline normalization
    
    Time base preservation:
    - All timing is relative to the event specified in EventSpec
    - p1_relative: 0 ms = P1 stimulus onset
    
    Example:
        WindowSpec(pre_ms=-500, post_ms=1000, baseline_ms=(-500, -50))
        -> Extracts 1500 ms window with 450 ms baseline for dB normalization
    """
    pre_ms: float
    post_ms: float
    baseline_ms: tuple[float, float] | None = None
    time_base: TimeBase = "p1_relative"
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    @property
    def duration_ms(self) -> float:
        """Total window duration in milliseconds."""
        return self.post_ms - self.pre_ms
    
    def to_samples(self, fs_hz: float) -> tuple[int, int]:
        """Convert window to sample indices relative to event onset.
        
        Returns (pre_samples, post_samples) where:
        - pre_samples is negative (samples before event)
        - post_samples is positive (samples after event)
        """
        pre_samples = int(self.pre_ms / 1000.0 * fs_hz)
        post_samples = int(self.post_ms / 1000.0 * fs_hz)
        return pre_samples, post_samples


@dataclass(frozen=True)
class SignalSpec:
    """Specification for signal extraction and preprocessing.
    
    Shape expectations by signal_class:
    - SPK: (trials, units, time_bins) for binned; ragged for unbinned
    - SPK_SMOOTH: (trials, units, time) after Gaussian convolution
    - MUAe: (trials, channels, time) multi-unit activity envelope
    - LFP: (trials, channels, time) raw or preprocessed LFP
    - TFR: (trials, channels, freqs, time) time-frequency representation
    - BAND_POWER: (trials, channels, time) band-limited power
    
    Units:
    - SPK: spike counts per bin (int) or binary (0/1)
    - SPK_SMOOTH: firing rate (Hz, continuous)
    - MUAe: arbitrary units (envelope amplitude)
    - LFP: microvolts (uV) or normalized
    - TFR: power (linear) or dB (normalized)
    - BAND_POWER: power (linear) or dB (normalized)
    
    Axis preservation:
    - trials: always preserved (no trial averaging)
    - units: preserved for SPK, SPK_SMOOTH
    - channels: preserved for MUAe, LFP, TFR, BAND_POWER
    - freqs: preserved for TFR
    - time: preserved for all continuous signals
    
    Area/layer handling:
    - areas: subset of CANONICAL_AREAS (V3d/V3a not collapsed)
    - layer: "unresolved" by default, "superficial_putative" or "deep_putative" only if inferred
    - unit_filter: dict with keys like "area", "presence_ratio_min", "layer"
    - channel_filter: dict with keys like "area", "channel_indices"
    
    Note on gamma:
    - Not treated as universal prediction-error signal
    - Analysis context determines interpretation
    """
    signal_class: SignalClass
    areas: tuple[str, ...] = tuple(CANONICAL_AREAS)
    layer: str = "unresolved"  # Default: no layer information
    unit_filter: Mapping[str, Any] = field(default_factory=dict)
    channel_filter: Mapping[str, Any] = field(default_factory=dict)
    sampling_rate_hz: float = 1000.0
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnalysisSpec:
    """Specification for analysis computation.
    
    Shape expectations:
    - Input shapes preserved through analysis chain
    - Aggregation only if explicitly requested (aggregation != "none")
    
    Analysis kinds:
    - spike_rate: PSTH in Hz, trial x unit x time
    - smoothed_spike_rate: Gaussian-convolved PSTH
    - tfr: multitaper time-frequency representation
    - band_power: frequency-band-limited power
    - spectral_coherence: LFP-LFP coherence spectrum
    - spike_lfp_mi: mutual information between spikes and LFP power
    - spike_phase_locking: PPC/PLV spike-field coupling
    - pac: phase-amplitude coupling (MI)
    - Y_tensor: D(B, A, P, L) band-area-epoch-layer tensor
    - H_harmony: cross-area harmony matrices from Y
    
    Units:
    - bands: Hz, using PUBLICATION_BANDS or custom
    - time: milliseconds (ms) for display, seconds for NWB storage
    - power: linear or dB (10*log10)
    - MI: bits (mutual information)
    - PLV/PPC: 0-1 (phase locking strength)
    - PAC-MI: 0-1 (modulation index)
    
    Trial preservation:
    - preserve_trials=True: keeps trial dimension (default)
    - Aggregation options: "none", "mean", "median", "sem"
    
    Note on claim safety:
    - All analysis outputs are computational_scaffold = True
    - truth_safe_unverified = True for these tensors
    - Claims require additional validation/calibration
    """
    analysis_kind: AnalysisKind
    bands: Mapping[str, tuple[float, float | None]] = field(
        default_factory=lambda: dict(PUBLICATION_BANDS)
    )
    condition_contrast: tuple[str, str] | None = None  # e.g., ("AXAB", "AAAB")
    preserve_trials: bool = True
    aggregation: str = "none"  # "none", "mean", "median", "sem"
    notes: str = ""  # Human-readable analysis notes
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutputSpec:
    """Specification for output storage.
    
    Path pattern:
        outputs/analysis_recipes/<repo_sha>_<nwb_sha8>/<recipe_id>/
            arrays/
            tables/
            figures/
            notebooks/
            manifests/
            reports/
            warnings/
    
    Control flags:
    - save_arrays: Save .npz array files
    - save_tables: Save .csv table files
    - save_figure: Save .html preview figures
    - save_notebook: Save .ipynb executable notebooks
    
    Manifest requirement:
    - Every recipe must save a manifest JSON with full provenance
    - Manifest includes: specs, source functions, git SHA, warnings
    """
    output_root: Path
    recipe_id: str
    save_arrays: bool = True
    save_tables: bool = True
    save_figure: bool = True
    save_notebook: bool = True
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
    
    def get_recipe_dir(self) -> Path:
        """Get the full recipe output directory."""
        return self.output_root / self.recipe_id
    
    def get_subdir(self, subdir: str) -> Path:
        """Get a subdirectory path (arrays, tables, figures, etc.)."""
        return self.get_recipe_dir() / subdir


@dataclass
class RecipeResult:
    """Result container for a completed analysis recipe.
    
    Tracks all outputs from a recipe execution for provenance and reporting.
    
    Fields:
    - recipe_id: Unique identifier for this recipe run
    - status: "SUCCESS", "PARTIAL", "FAILED", "BLOCKED"
    - output_root: Base directory for outputs
    - arrays: Mapping of array name -> file path (.npz)
    - tables: Mapping of table name -> file path (.csv)
    - figures: Mapping of figure name -> file path (.html)
    - notebooks: Mapping of notebook name -> file path (.ipynb)
    - manifest_path: Path to the recipe manifest JSON
    - warnings: List of warning dicts with "code" and "message"
    - metadata: Additional recipe-specific metadata
    
    Claim status:
    - All RecipeResults default to truth_safe_unverified = True
    - The tensors are computational_scaffold = True
    - Actual scientific claims require further validation
    """
    recipe_id: str
    status: str = "PENDING"  # PENDING, SUCCESS, PARTIAL, FAILED, BLOCKED
    output_root: str = ""
    arrays: dict[str, str] = field(default_factory=dict)
    tables: dict[str, str] = field(default_factory=dict)
    figures: dict[str, str] = field(default_factory=dict)
    notebooks: dict[str, str] = field(default_factory=dict)
    manifest_path: str | None = None
    warnings: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (includes all nested dicts)."""
        return asdict(self)
    
    def add_warning(self, code: str, message: str) -> None:
        """Add a warning to the result."""
        self.warnings.append({"code": code, "message": message})
    
    @property
    def claim_status(self) -> str:
        """Return the claim safety status for this recipe result.
        
        Default is truth_safe_unverified = True.
        """
        return "truth_safe_unverified"
    
    @property
    def computational_scaffold(self) -> bool:
        """All recipe outputs are computational scaffolds, not validated claims."""
        return True
