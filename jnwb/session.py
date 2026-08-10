"""
OmissionSession: Object-Oriented NWB Analysis Interface

High-level, user-friendly interface for omission experiment analysis.
Clean grammar: session.<method>(<args>) for all analysis types.

Author: Claude Code
Date: 2025-06-24
"""

import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union
import numpy as np
import pandas as pd
from pynwb import NWBHDF5IO

log = logging.getLogger(__name__)

# Anchored to the repo root, not the process's current working directory: a plain relative
# "artifacts/developer/.cache" silently creates a brand-new multi-GB cache tree wherever a
# script happens to be invoked from (found 2026-08-04 -- a fig03 rebuild run from inside
# context/figures/fig03_unit_census/ duplicated the entire 21-session NWB table cache, 6.7 GB,
# under that subdirectory instead of reusing the real one). This is a shared, multi-agent,
# multi-CLI workspace where CWD at invocation time is not controlled.
_REPO_ROOT = Path(__file__).resolve().parent.parent

# RRXR/RRRX task_condition_number -> stimulus-omission-slot assignment is NOT the same across
# subjects. Confirmed via is_omission cross-referencing (2026-07-30) for C31o/V198o: cond
# 35/37/39/41 omit stimulus_number=4 (p3, RRXR), cond 36/38/40/42-50 omit stimulus_number=5
# (p4, RRRX) -- an interleaved split. V182o has no is_omission column and this session's
# attempts to re-derive its mapping from oddball_status/codes/contrast were inconclusive (see
# artifacts/.lab/condition_number_crosswalk_v182o_investigation_20260730.json); the user
# supplied the authoritative mapping directly from the task-generation markdowns: V182o uses a
# contiguous split instead, RRXR=35-42, RRRX=43-50. Every other condition name/number in
# CONDITION_MAP_DEFAULT is confirmed the same across all three subjects and is not overridden.
CONDITION_MAP_DEFAULT = {
    'AAAB': [1, 2], 'AXAB': [3], 'AAXB': [4], 'AAAX': [5],
    'BBBA': [6, 7], 'BXBA': [8], 'BBXA': [9], 'BBBX': [10],
    'RRRR': list(range(11, 27)), 'RXRR': list(range(27, 35)),
    'RRXR': [35, 37, 39, 41], 'RRRX': [36, 38, 40] + list(range(42, 51)),
}
CONDITION_MAP_V182O = dict(CONDITION_MAP_DEFAULT, **{
    'RRXR': list(range(35, 43)), 'RRRX': list(range(43, 51)),
})


def condition_map_for_stem(stem: str) -> Dict[str, List[int]]:
    """RRXR/RRRX condition-number crosswalk, subject-aware. `stem` is the NWB filename stem
    (e.g. 'sub-V182o_ses-260629')."""
    return CONDITION_MAP_V182O if "V182o" in stem else CONDITION_MAP_DEFAULT


class OmissionSession:
    """
    Unified object-oriented interface for omission NWB analysis.

    Provides fast shortcuts for:
    - Epoched data extraction (trial-averaged, condition-filtered)
    - Single-unit finding and quality filtering
    - Channel-to-unit mapping
    - LFP channel area classification
    - TFR loading and visualization
    - Raster suites (raster + PSTH + autocorrelogram)
    - Pie chart generation by quality/area/metrics
    - Trial-averaged and channel-averaged plots
    - Spectrolaminar (layer-wise) analysis

    Example:
        >>> import jnwb as oa
        >>> session = oa.read('sub-C31o_ses-230823_rec.nwb')
        >>> session.trial_averaged_plot(area='V1', phase=2, condition='AAXB')
        >>> units = session.find_single_units(quality='stable_plus', area='V1')
        >>> session.raster_suite(unit_id=42)
        >>> session.pie_charts(criteria={'is_stable_plus': True, 'area': 'V1'})
    """

    def __init__(self, nwb_path: Union[str, Path], context: str = 'omission_glo_passive'):
        """
        Initialize session from NWB file.

        Args:
            nwb_path: Path to .nwb file
            context: Interval name for epoching (default: 'omission_glo_passive')
        """
        self.nwb_path = Path(nwb_path)
        self.context = context
        self.nwb = None
        self._metadata = {}
        self._units_df = None
        self._electrodes_df = None
        self._intervals_df = None
        self._spike_cache = {}

        self._load_nwb()
        log.info(f"✓ Loaded {self.nwb_path.name}")

    def _load_nwb(self):
        """Load NWB file and cache key dataframes."""
        from .addressing import enrich_units_dataframe
        import pickle
        import json

        session_name = self.nwb_path.stem
        cache_dir = _REPO_ROOT / "artifacts" / "developer" / ".cache"
        cache_dir.mkdir(parents=True, exist_ok=True)

        units_cache = cache_dir / f"{session_name}_units.pkl"
        elecs_cache = cache_dir / f"{session_name}_electrodes.pkl"
        intervals_cache = cache_dir / f"{session_name}_intervals.pkl"
        meta_cache = cache_dir / f"{session_name}_metadata.json"

        # Check if all cache files exist
        if units_cache.exists() and elecs_cache.exists() and intervals_cache.exists() and meta_cache.exists():
            try:
                with open(units_cache, "rb") as f:
                    self._units_df = pickle.load(f)
                with open(elecs_cache, "rb") as f:
                    self._electrodes_df = pickle.load(f)
                with open(intervals_cache, "rb") as f:
                    self._intervals_df = pickle.load(f)
                with open(meta_cache, "r", encoding="utf-8") as f:
                    self._metadata = json.load(f)
                log.info(f"✓ Loaded cached NWB tables for {session_name} from disk cache")
                return
            except Exception as e:
                log.warning(f"Failed to read disk cache for {session_name}: {e}. Reloading from NWB.")

        with NWBHDF5IO(str(self.nwb_path), 'r', load_namespaces=True) as io:
            nwb = io.read()

            # Cache electrodes first so we can map units to them
            if nwb.electrodes is not None:
                self._electrodes_df = nwb.electrodes.to_dataframe()
                if 'group' in self._electrodes_df.columns:
                    self._electrodes_df = self._electrodes_df.drop(columns=['group'])

            # Cache and enrich units
            if nwb.units is not None:
                raw_units = nwb.units.to_dataframe().copy()
                self._units_df = enrich_units_dataframe(raw_units, self._electrodes_df)

            # Cache interval data
            if self.context in nwb.intervals:
                self._intervals_df = nwb.intervals[self.context].to_dataframe()

            # Extract metadata
            self._metadata = {
                'subject_id': nwb.subject.subject_id if nwb.subject else None,
                'session_start': nwb.session_start_time.isoformat() if nwb.session_start_time else None,
                'session_description': nwb.session_description,
                'n_units': len(self._units_df) if self._units_df is not None else 0,
            }

        # Save to disk cache
        try:
            with open(units_cache, "wb") as f:
                pickle.dump(self._units_df, f)
            with open(elecs_cache, "wb") as f:
                pickle.dump(self._electrodes_df, f)
            with open(intervals_cache, "wb") as f:
                pickle.dump(self._intervals_df, f)
            with open(meta_cache, "w", encoding="utf-8") as f:
                json.dump(self._metadata, f)
            log.info(f"✓ Cached NWB tables for {session_name} to disk cache")
        except Exception as e:
            log.warning(f"Failed to write disk cache for {session_name}: {e}")

    # ========================================================================
    # CORE ACCESSOR METHODS
    # ========================================================================

    def get_units(self, quality: Optional[str] = None, area: Optional[str] = None,
                  firing_rate_range: Optional[Tuple[float, float]] = None) -> pd.DataFrame:
        """
        Get units with optional filtering.

        Args:
            quality: Filter by quality ('stable_plus', 'stable', 'mua', 'unstable')
            area: Filter by brain area (V1, V3, V4, MT, MST, PFC, FEF)
            firing_rate_range: Tuple (min, max) firing rate in Hz

        Returns:
            Filtered units DataFrame

        Example:
            >>> stable_units = session.get_units(quality='stable_plus')
            >>> v1_units = session.get_units(area='V1')
            >>> high_fr = session.get_units(firing_rate_range=(10, 100))
        """
        if self._units_df is None:
            return pd.DataFrame()

        units = self._units_df.copy()

        if quality:
            if quality == 'stable_plus':
                units = units[units.get('stable_plus', False)]
            elif quality == 'stable':
                units = units[(units.get('is_stable', False)) & ~units.get('stable_plus', False)]

        if area:
            units = units[units.get('area') == area]

        if firing_rate_range:
            fr_min, fr_max = firing_rate_range
            units = units[(units.get('firing_rate', 0) >= fr_min) &
                         (units.get('firing_rate', 0) <= fr_max)]

        return units

    def get_electrodes(self, area: Optional[str] = None) -> pd.DataFrame:
        """Get electrodes, optionally filtered by area."""
        if self._electrodes_df is None:
            return pd.DataFrame()

        elecs = self._electrodes_df.copy()

        if area and 'location' in elecs.columns:
            elecs = elecs[elecs['location'].str.contains(area, na=False)]

        return elecs

    def get_epochs(self, phase: Optional[int] = None, condition: Optional[Union[int, str]] = None,
                   correct_only: bool = True) -> pd.DataFrame:
        """
        Get behavioral epochs with optional filtering.

        CRITICAL PARADIGM TIMING INVARIANT:
            phase = 2 (stimulus_number == 2.0) defines Presentation 1 (P1) onset (t = 0 ms).
            phase = 1 (stimulus_number == 1.0) is Fixation (fx) onset (-566 ms).
            phase = 3 (stimulus_number == 3.0) is Presentation 2 (P2) onset (1031 ms).
            phase = 4 (stimulus_number == 4.0) is Presentation 3 (P3) onset (2062 ms).
            phase = 5 (stimulus_number == 5.0) is Presentation 4 (P4) onset (3093 ms).

            To get P1-aligned sequence trial onset timestamps, use phase=2 or call session.get_trial_onsets(condition).

        Args:
            phase: stimulus_number (1=fixation, 2=p1, 3=p2, 4=p3, 5=p4)
            condition: condition code or name (e.g., 'AAXB', 'RRRR')
            correct_only: Include only correct trials

        Returns:
            Filtered intervals DataFrame
        """
        if self._intervals_df is None or len(self._intervals_df) == 0:
            log.warning(f"No interval data available (context: {self.context})")
            return pd.DataFrame()

        epochs = self._intervals_df.copy()

        # Convert columns to numeric (NWB stores them as strings '1.0', '2.0', etc.)
        if 'correct' in epochs.columns:
            epochs['correct'] = pd.to_numeric(epochs['correct'], errors='coerce')
        if 'stimulus_number' in epochs.columns:
            epochs['stimulus_number'] = pd.to_numeric(epochs['stimulus_number'], errors='coerce')
        if 'task_condition_number' in epochs.columns:
            epochs['task_condition_number'] = pd.to_numeric(epochs['task_condition_number'], errors='coerce')

        if correct_only and 'correct' in epochs.columns:
            epochs = epochs[epochs['correct'] == 1.0]

        if phase is not None and 'stimulus_number' in epochs.columns:
            epochs = epochs[epochs['stimulus_number'] == float(phase)]

        if condition is not None:
            if isinstance(condition, str):
                # Map condition name to codes -- RRXR/RRRX differ for V182o, see
                # condition_map_for_stem()'s docstring/CONDITION_MAP_V182O above.
                condition_map = condition_map_for_stem(self.nwb_path.stem)
                condition_codes = [float(c) for c in condition_map.get(condition, [])]
            else:
                condition_codes = [float(condition)]

            if 'task_condition_number' in epochs.columns:
                epochs = epochs[epochs['task_condition_number'].isin(condition_codes)]

        return epochs

    def get_trial_onsets(self, condition: Optional[Union[int, str]] = None,
                         correct_only: bool = True) -> np.ndarray:
        """
        Get canonical P1-aligned trial sequence onset timestamps (seconds) for a condition.

        Guarantees P1-alignment (t = 0 ms) by querying phase=2 (stimulus_number == 2.0).

        Args:
            condition: Condition name (e.g., 'RRRR', 'RXRR') or numeric code.
            correct_only: Include only correct trials.

        Returns:
            1D numpy array of float timestamps (seconds) for Presentation 1 (P1) onset.
        """
        epochs = self.get_epochs(phase=2, condition=condition, correct_only=correct_only)
        if len(epochs) == 0:
            return np.array([], dtype=float)
        return np.asarray(epochs["start_time"].values, dtype=float)

    def get_spike_times(self, unit_id: Union[int, str]) -> Optional[np.ndarray]:
        """
        Get spike times for a single unit.

        Args:
            unit_id: Unit cluster ID

        Returns:
            Array of spike times (in seconds), or None if unit not found

        Example:
            >>> spikes = session.get_spike_times(unit_id=42)
            >>> print(f"Unit 42: {len(spikes)} spikes")
        """
        if self._units_df is None or len(self._units_df) == 0:
            log.warning("No units in session")
            return None

        # Convert to numeric for comparison
        unit_id_numeric = float(unit_id) if isinstance(unit_id, (int, str)) else unit_id

        if hasattr(self, '_spike_cache') and unit_id_numeric in self._spike_cache:
            return self._spike_cache[unit_id_numeric]

        matching = pd.DataFrame()
        # Primary lookup: raw DataFrame row position. This is the actual,
        # established identity convention used throughout the real pipeline
        # (jnwb.unit_classification.classify_session_units's default
        # `unit_ids = list(units_df.index)`, scripts/classify_units_shuffle_sso.py,
        # scripts/filter_units.py, scripts/list_stable_plus_units.py all pass
        # raw row positions as "unit_id"). Row position is always globally
        # unique within a session by construction (pandas RangeIndex),
        # unlike the separate 'unit_id'/'cluster_id' DataFrame COLUMN (a
        # per-probe-local kilosort id that resets to 0 on every probe and is
        # NOT globally unique - confirmed 2026-07-12 it can collide across
        # 3+ areas within one session). Do not use the column as the primary
        # key; it is informational metadata, not the identity used elsewhere.
        if self._units_df.index.name == 'id' or 'id' in self._units_df.columns or self._units_df.index.name is None:
            if unit_id_numeric in self._units_df.index:
                matching = self._units_df.loc[[unit_id_numeric]]

        if len(matching) == 0:
            # Find the unit row (handle both cluster_id and unit_id columns)
            if 'cluster_id' in self._units_df.columns:
                unit_col = 'cluster_id'
            elif 'unit_id' in self._units_df.columns:
                unit_col = 'unit_id'
            else:
                log.error("No unit_id or cluster_id column in units table")
                return None

            # Find matching unit row by column
            matching = self._units_df[pd.to_numeric(self._units_df[unit_col], errors='coerce') == unit_id_numeric]

        if len(matching) == 0:
            log.warning(f"Unit {unit_id} not found")
            return None

        # Get spike_times from the first matching row
        spike_times = matching.iloc[0]['spike_times']

        if spike_times is None or len(spike_times) == 0:
            log.warning(f"Unit {unit_id}: no spike times")
            return None

        res = np.array(spike_times)
        if hasattr(self, '_spike_cache'):
            self._spike_cache[unit_id_numeric] = res
        return res

    # ========================================================================
    # ANALYSIS METHODS: PLOTTING
    # ========================================================================

    def trial_averaged_plot(self, area: str, phase: int = 2, condition: Optional[str] = None,
                            plot_kwargs: Optional[Dict] = None) -> Dict:
        """
        Trial-averaged LFP/TFR plot for area × condition.

        Fast shortcut for epoching, averaging, and visualizing power by condition.

        Args:
            area: Brain area (V1, V3, V4, MT, MST, PFC, FEF)
            phase: stimulus_number (1=fixation, 2=p1, 3=p2, 4=p3, 5=p4)
            condition: Condition name (AAAB, AAXB, AAAX, etc.)
            plot_kwargs: Matplotlib kwargs (figsize, cmap, etc.)

        Returns:
            Dictionary with {'figure': fig, 'axes': axes, 'data': power_array}

        Example:
            >>> session.trial_averaged_plot(area='V1', phase=2, condition='AAXB')
        """
        import matplotlib.pyplot as plt
        tfr_data = self.tfr_from_preprocessed(area=area, band=None, condition=condition)
        if tfr_data is None:
            return {'error': f'Failed to load TFR for {area}'}

        # Average across trials (axis 3) and channels (axis 0)
        mean_power = np.mean(tfr_data, axis=(0, 3))  # (frequencies, time_samples)

        # Baseline subtraction (first 25% of time samples)
        baseline_n = max(1, mean_power.shape[1] // 4)
        baseline = np.mean(mean_power[:, :baseline_n], axis=1, keepdims=True)
        power_db = 10.0 * np.log10(np.maximum(mean_power, 1e-12) / np.maximum(baseline, 1e-12))

        pk = plot_kwargs or {}
        fig, ax = plt.subplots(figsize=pk.get('figsize', (8, 6)), facecolor='white')
        
        n_freqs, n_time = power_db.shape
        freqs = np.linspace(1, 150, n_freqs)
        times = np.linspace(-1000, 2000, n_time)

        vmax = pk.get('vmax', np.percentile(np.abs(power_db), 98))
        im = ax.pcolormesh(times, freqs, power_db, shading='auto',
                           cmap=pk.get('cmap', 'RdBu_r'), vmin=-vmax, vmax=vmax)
        
        cb = fig.colorbar(im, ax=ax, label='Power (dB re baseline)')
        ax.set_title(f"Trial-Averaged TFR Power: {area} ({condition}, Phase {phase})", fontsize=11, fontweight='bold')
        ax.set_xlabel("Time relative to stimulus onset (ms)")
        ax.set_ylabel("Frequency (Hz)")
        ax.axvline(0, color='black', linestyle='--', alpha=0.5)

        return {'figure': fig, 'axes': ax, 'data': power_db, 'status': 'completed'}

    def channel_averaged_plot(self, area: str, phase: int = 2, condition: Optional[str] = None) -> Dict:
        """
        Channel-averaged power spectrum for area (across all channels in area).

        Args:
            area: Brain area
            phase: stimulus_number
            condition: Optional condition filter

        Returns:
            Dictionary with figure and averaged power array

        Example:
            >>> session.channel_averaged_plot(area='V4', phase=3, condition='AAXB')
        """
        import matplotlib.pyplot as plt
        tfr_data = self.tfr_from_preprocessed(area=area, band=None, condition=condition)
        if tfr_data is None:
            return {'error': f'Failed to load TFR for {area}'}

        # Average across channels (0) and trials (3), then across time (2) -> (frequencies,)
        psd = np.mean(tfr_data, axis=(0, 2, 3))

        freqs = np.linspace(1, 150, len(psd))

        fig, ax = plt.subplots(figsize=(8, 5), facecolor='white')
        ax.plot(freqs, psd, color='black', linewidth=1.5)
        ax.set_title(f"Channel-Averaged Power Spectrum: {area}", fontsize=11, fontweight='bold')
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power")
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        return {'figure': fig, 'axes': ax, 'data': psd, 'status': 'completed'}

    def spectrolaminar_motif(self, area: str, condition: str = 'AAAB',
                             layer_masks: Optional[Dict] = None) -> Dict:
        """
        Spectrolaminar analysis: cross-frequency coupling by cortical layer.

        Uses boundaries to analyze spectral content by depth.

        Args:
            area: Brain area
            condition: Behavioral condition (e.g., 'AAXB' for p2 omission)
            layer_masks: Optional dict with layer boundary info {area: {'superficial': (0,10), 'deep': (10,20)}}

        Returns:
            Dictionary with spectral × layer heatmaps and statistics

        Example:
            >>> session.spectrolaminar_motif(area='MT', condition='omission')
        """
        tfr_data = self.tfr_from_preprocessed(area=area, band=None, condition=condition)
        if tfr_data is None:
            return {'error': f'Failed to load TFR for {area}'}

        from .analyzers import TFRAnalyzer
        if layer_masks is None:
            n_ch = tfr_data.shape[0]
            # Create a simple mask: superficial=first half, deep=second half
            layer_bounds = {
                'superficial_mask': [True] * (n_ch // 2) + [False] * (n_ch - n_ch // 2),
                'deep_mask': [False] * (n_ch // 2) + [True] * (n_ch - n_ch // 2)
            }
        else:
            layer_bounds = layer_masks

        res = TFRAnalyzer.average_across_channels(tfr_data, layer_mask=layer_bounds)
        
        # Guard index access if res is 2D (time × trials) instead of 3D (layer × time × trials)
        if res.ndim >= 3:
            superficial = res[0]
            deep = res[1]
        else:
            # If 2D (no layers resolved), return res for both
            superficial = res
            deep = res

        return {'layer_data': {'superficial': superficial, 'deep': deep}, 'status': 'completed'}

    # ========================================================================
    # ANALYSIS METHODS: SINGLE UNITS
    # ========================================================================

    def find_single_units(self, quality: str = 'stable_plus', area: Optional[str] = None,
                         firing_rate_range: Tuple[float, float] = (1, 200),
                         responsiveness: Optional[str] = None) -> pd.DataFrame:
        """
        Find single units matching quality/area/response criteria.

        Convenience wrapper around get_units() with sensible defaults.

        Args:
            quality: Unit quality ('stable_plus', 'stable', 'mua', 'unstable')
            area: Restrict to brain area
            firing_rate_range: (min, max) firing rate in Hz
            responsiveness: Filter by response type ('omission_responsive', 'stimulus_suppressed', etc.)

        Returns:
            Filtered units DataFrame with all metadata

        Example:
            >>> v1_units = session.find_single_units(quality='stable_plus', area='V1')
            >>> high_fr = session.find_single_units(firing_rate_range=(20, 200))
        """
        log.info(f"Finding units: quality={quality}, area={area}, fr={firing_rate_range}")
        units = self.get_units(quality=quality, area=area, firing_rate_range=firing_rate_range)

        if responsiveness and responsiveness in units.columns:
            units = units[units[responsiveness] == True]

        return units

    def channel_unit_mapping(self) -> pd.DataFrame:
        """
        Map recording channels to single units via peak_channel.

        Quick reference: which unit was recorded on which channel?

        Returns:
            DataFrame with columns: unit_id, channel_id, area, layer

        Example:
            >>> mapping = session.channel_unit_mapping()
            >>> v1_channels = mapping[mapping['area'] == 'V1']
        """
        log.info("Building channel-unit mapping")
        if self._units_df is None:
            return pd.DataFrame()

        units = self._units_df.copy()

        # Use peak_channel_id (from NWB) or peak_channel_global (from external metadata)
        peak_channel_col = 'peak_channel_global' if 'peak_channel_global' in units.columns else 'peak_channel_id'

        cols_to_use = ['cluster_id', peak_channel_col, 'area', 'layer']
        # Only include columns that exist
        cols_to_use = [c for c in cols_to_use if c in units.columns]

        if len(cols_to_use) < 4:
            log.warning(f"Missing columns for mapping. Have: {cols_to_use}")
            return pd.DataFrame()

        mapping = units[cols_to_use].copy()
        mapping = mapping.rename(columns={'cluster_id': 'unit_id', peak_channel_col: 'channel_id'})

        return mapping.reset_index(drop=True)

    def lfp_channel_areas(self) -> pd.DataFrame:
        """
        Map LFP recording channels to brain areas via electrode locations.

        Fast reference: which channels are in which area?

        Returns:
            DataFrame with columns: channel_id, area, layer

        Example:
            >>> lfp_map = session.lfp_channel_areas()
            >>> v1_lfp = lfp_map[lfp_map['area'] == 'V1']
        """
        log.info("Extracting LFP channel areas")
        if self._electrodes_df is None:
            return pd.DataFrame()

        elecs = self._electrodes_df.copy()
        if 'id' not in elecs.columns:
            elecs = elecs.reset_index()
            if 'id' not in elecs.columns and 'index' in elecs.columns:
                elecs = elecs.rename(columns={'index': 'id'})

        # Extract area from location string (e.g., 'V1/L2/3' → 'V1')
        if 'location' in elecs.columns:
            elecs['area'] = elecs['location'].str.split('/').str[0]
            if '/' in elecs['location'].iloc[0] if len(elecs) > 0 else False:
                elecs['layer'] = elecs['location'].str.split('/').str[1]
            else:
                elecs['layer'] = ''

        id_col = 'id' if 'id' in elecs.columns else 'channel_id'
        if id_col not in elecs.columns:
            elecs[id_col] = elecs.index
        return elecs[[id_col, 'area', 'layer']].rename(columns={id_col: 'channel_id'})

    # ========================================================================
    # ANALYSIS METHODS: TFR & SPECTRAL
    # ========================================================================

    def tfr_from_preprocessed(
        self,
        area: str,
        band: str = "alpha",
        condition: Optional[str] = None,
        tfr_dir: Optional[Path] = None,
    ) -> Optional[np.ndarray]:
        """
        Load preprocessed TFR array from OMISSION_TFR_DIR / tfr_arrays.

        Filename contract:
          {session_prefix}-{A|B|C|D}-{area}-{CONDITION}.npy
        Array contract (float32): (n_trials, n_channels, n_freqs, n_times)
          freqs ≈ arange(3, 201, 2); times ≈ -1000 + arange(500)*10 ms.

        Area aliases: V3d/V3a also try file token V3; V4 also tries DP.
        Bare dual-file token V3 is returned whole (caller may half-slice).

        Returns:
            memmap/ndarray or None if no matching file exists.
        """
        import os
        import re

        from . import paths as _paths

        tfr_root = _paths.tfr_dir(tfr_dir)
        stem = self.nwb_path.stem
        # strip trailing _rec for prefix used in tfr filenames
        session_prefix = re.sub(r"_rec$", "", stem)

        area_tokens = [area]
        if area in ("V3d", "V3a", "V3D", "V3A"):
            area_tokens.append("V3")
        if area == "V4":
            area_tokens.append("DP")
        if area == "V3":
            area_tokens.extend(["V3d", "V3a"])

        candidates: List[Path] = []
        if not tfr_root.is_dir():
            log.warning(f"TFR dir missing: {tfr_root}")
            return None

        for token in area_tokens:
            if condition:
                pat = f"{session_prefix}-*-{token}-{condition}.npy"
                candidates.extend(sorted(tfr_root.glob(pat)))
            else:
                pat = f"{session_prefix}-*-{token}-*.npy"
                candidates.extend(sorted(tfr_root.glob(pat)))

        # de-dupe preserving order
        seen = set()
        uniq: List[Path] = []
        for p in candidates:
            if p.name not in seen:
                seen.add(p.name)
                uniq.append(p)

        if not uniq:
            log.info(
                f"No TFR file for session={session_prefix} area={area} "
                f"condition={condition} under {tfr_root}"
            )
            return None

        path = uniq[0]
        log.info(f"Loading TFR: {path.name} (band={band})")
        arr = np.load(path, mmap_mode="r")
        if arr.ndim != 4:
            log.warning(f"Unexpected TFR ndim={arr.ndim} in {path.name}")
            return np.asarray(arr)

        # Optional band slice on frequency axis (axis=2)
        if band and str(band).lower() not in ("none", "all", "*"):
            from .sequence_layout import BANDS_7

            band_key = str(band)
            # accept alpha → Alpha etc.
            lookup = {k.lower(): k for k in BANDS_7}
            lookup.update(
                {
                    "alpha": "Alpha",
                    "theta": "Theta",
                    "beta": "l-beta",
                    "lbeta": "l-beta",
                    "hbeta": "h-beta",
                    "gamma": "Gamma_L",
                    "low_gamma": "Gamma_L",
                    "high_gamma": "Gamma_H",
                }
            )
            canon = lookup.get(band_key.lower(), band_key)
            if canon in BANDS_7:
                fmin, fmax = BANDS_7[canon]
                freqs = np.arange(3, 201, 2)
                if arr.shape[2] == len(freqs):
                    fmask = (freqs >= fmin) & (freqs <= fmax)
                    return arr[:, :, fmask, :]
        return arr

    def plot_tfr(self, area: str, condition: str = 'stimulus',
                 phase: int = 2, plot_kwargs: Optional[Dict] = None) -> Dict:
        """
        Plot time-frequency representation for area × condition.

        Does **not** invent synthetic TFR when files are missing — returns
        status='missing_tfr' instead (no silent science).
        """
        log.info(f"Plotting TFR: {area} {condition} phase={phase}")
        import matplotlib.pyplot as plt

        tfr_data = self.tfr_from_preprocessed(area=area, band=None, condition=condition)
        if tfr_data is None:
            msg = (
                f"No preprocessed TFR for area={area} condition={condition}. "
                f"Run scripts/precompute_tfr_arrays.py or check OMISSION_TFR_DIR / readiness."
            )
            log.error(msg)
            return {
                "figure": None,
                "axes": None,
                "data": None,
                "status": "missing_tfr",
                "error": msg,
            }

        # Mean across trials and channels → (freqs, time); trials-first contract
        mean_power = np.mean(np.asarray(tfr_data), axis=(0, 1))
        if mean_power.ndim != 2:
            mean_power = np.mean(np.asarray(tfr_data), axis=(0, 3))

        # dB normalise: subtract pre-stim baseline (first 20 bins ≈ fx)
        baseline = np.mean(mean_power[:, :20], axis=1, keepdims=True)
        mean_db = mean_power - baseline

        n_freqs, n_time = mean_db.shape
        freqs = np.arange(3, 201, 2) if n_freqs == 99 else np.linspace(1, 150, n_freqs)
        times = (-1000.0 + np.arange(n_time) * 10.0) if n_time == 500 else np.linspace(-1000, 2000, n_time)

        pk = plot_kwargs or {}
        fig, ax = plt.subplots(figsize=pk.get('figsize', (10, 6)), facecolor='white')
        vmax = np.percentile(np.abs(mean_db), 97)
        im = ax.pcolormesh(times, freqs, mean_db, shading='auto',
                           cmap=pk.get('cmap', 'RdBu_r'),
                           vmin=-vmax, vmax=vmax)
        cb = fig.colorbar(im, ax=ax, pad=0.02)
        cb.set_label('Power (dB re baseline)', fontsize=11)
        ax.set_yscale('log')
        ax.set_yticks([4, 8, 15, 30, 60, 100, 150])
        ax.get_yaxis().set_major_formatter(plt.ScalarFormatter())
        ax.set_xlabel('Time from stimulus onset (ms)', fontsize=11)
        ax.set_ylabel('Frequency (Hz)', fontsize=11)
        ax.set_title(
            f'Trial-Averaged TFR  ·  {area}  ·  {condition}  ·  Phase {phase}',
            fontsize=12,
            fontweight='bold',
        )
        ax.axvline(0, color='white', linestyle='--', linewidth=1.2, alpha=0.7)
        fig.tight_layout()

        return {'figure': fig, 'axes': ax, 'data': mean_db, 'status': 'completed'}

    # ========================================================================
    # ANALYSIS METHODS: RASTERS & SINGLE-UNIT PLOTS
    # ========================================================================

    def raster_suite(self, unit_id: Union[int, str], condition: Optional[str] = None,
                    phase: int = 2, window_ms: Tuple[int, int] = (-1000, 2000)) -> Dict:
        """
        Full raster suite: raster plot + PSTH + autocorrelogram.

        Three-panel figure for single-unit analysis (if condition is specified),
        or the publication-grade 5x4 aligned raster suite (if condition is None).

        Args:
            unit_id: Unit cluster ID
            condition: Behavioral condition (omission condition, e.g., 'AAXB', or None)
            phase: stimulus_number (1-5, default: 2 = p1)
            window_ms: Time window relative to phase onset (ms)

        Returns:
            Dictionary with figure and metrics, or Matplotlib figure object
        """
        log.info(f"Raster suite: unit={unit_id} condition={condition} phase={phase}")
        
        from .viz import raster_suite_omission
        import matplotlib.pyplot as plt

        if condition is None:
            # Replicate the exact legacy aligned raster suite (all 3 families)
            # Default window for full suite is (-1000, 4000) as in legacy script
            fig = raster_suite_omission(self, unit_id=unit_id, phase=phase, window_ms=(-1000, 4000))
            return {'figure': fig, 'status': 'completed', 'type': 'full_suite'}
        
        # Otherwise, generate a 3-panel single-condition figure
        from .functions import raster_plot, psth_analysis, autocorrelogram

        ras_res = raster_plot(self, unit_id=unit_id, condition=condition, phase=phase, window_ms=window_ms)
        psth_res = psth_analysis(self, unit_id=unit_id, condition=condition, phase=phase)
        acg_res = autocorrelogram(self, unit_id=unit_id)

        if 'error' in ras_res:
            return ras_res
        if 'error' in psth_res:
            return psth_res

        fig, axes = plt.subplots(3, 1, figsize=(10, 12), facecolor='white')
        
        # 1. Raster Plot
        ax_ras = axes[0]
        from collections import defaultdict
        spikes_by_trial = defaultdict(list)
        for sp in ras_res['raster_data']:
            spikes_by_trial[sp['trial_id']].append(sp['spike_time_ms'])
        
        unique_trial_ids = sorted(list(spikes_by_trial.keys()))
        trial_id_map = {tid: i for i, tid in enumerate(unique_trial_ids)}
        
        for trial_id, trial_spikes in spikes_by_trial.items():
            y_pos = trial_id_map[trial_id]
            ax_ras.vlines(trial_spikes, y_pos - 0.4, y_pos + 0.4, colors='black', linewidth=0.5)
        
        ax_ras.set_ylim(-0.5, max(0.5, len(unique_trial_ids) - 0.5))
        ax_ras.set_title(f"Spike Raster (Condition: {condition}, Phase: {phase})", fontsize=10, fontweight='bold')
        ax_ras.set_ylabel("Trials", fontsize=9)
        ax_ras.set_xlim(window_ms[0], window_ms[1])
        ax_ras.spines['top'].set_visible(False)
        ax_ras.spines['right'].set_visible(False)

        # 2. PSTH Plot
        ax_psth = axes[1]
        if 'psth_rate_hz' in psth_res:
            ax_psth.plot(psth_res['bin_times_ms'], psth_res['psth_rate_hz'], color='#1565C0', linewidth=1.5)
            ax_psth.axhline(psth_res['baseline_rate_hz'], color='gray', linestyle='--', linewidth=1.0)
        ax_psth.set_title("PSTH", fontsize=10, fontweight='bold')
        ax_psth.set_ylabel("FR (Hz)", fontsize=9)
        ax_psth.set_xlim(window_ms[0], window_ms[1])
        ax_psth.spines['top'].set_visible(False)
        ax_psth.spines['right'].set_visible(False)

        # 3. Autocorrelogram Plot
        ax_acg = axes[2]
        if 'acg' in acg_res:
            lags = np.linspace(-acg_res.get('max_lag_ms', 100), acg_res.get('max_lag_ms', 100), len(acg_res['acg']))
            ax_acg.bar(lags, acg_res['acg'], width=lags[1]-lags[0], color='gray', alpha=0.7)
        ax_acg.set_title("Autocorrelogram", fontsize=10, fontweight='bold')
        ax_acg.set_xlabel("Lag (ms)", fontsize=9)
        ax_acg.set_ylabel("Counts", fontsize=9)
        ax_acg.spines['top'].set_visible(False)
        ax_acg.spines['right'].set_visible(False)

        plt.suptitle(f"Unit {unit_id} Analysis Suite", fontsize=12, fontweight='bold', y=0.98)
        plt.tight_layout()

        return {
            'figure': fig,
            'raster_metrics': {'n_trials': ras_res['n_trials'], 'n_spikes': ras_res['n_spikes']},
            'psth_metrics': {'baseline_rate_hz': psth_res['baseline_rate_hz']},
            'acg_metrics': {'is_single_unit': acg_res.get('is_single_unit', False)},
            'status': 'completed',
            'type': 'single_condition'
        }

    def lfp_tfr_trace_suite_omission(self, area: str, layer: str, session_specific: bool = True, **kwargs) -> Dict:
        """
        Generate the 2-row LFP TFR trace suite for an area-layer.

        Args:
            area: Brain area (e.g. 'FEF', 'V4')
            layer: Putative layer ('superficial' or 'deep')
            session_specific: If True, filters TFR files to only match the current session ID (default: True)
            **kwargs: Arguments to pass to jnwb.viz.lfp_tfr_trace_suite_omission

        Returns:
            Dictionary with figure and status
        """
        from .viz import lfp_tfr_trace_suite_omission
        fig = lfp_tfr_trace_suite_omission(self, area=area, layer=layer, session_specific=session_specific, **kwargs)
        return {'figure': fig, 'status': 'completed'}

    def lfp_tfr_trace_correlation(self, band_name: str, **kwargs) -> Dict:
        """
        Generate the area-layer LFP trace correlation matrix.

        Insignificant correlations (FDR p-value > alpha) are set to 0.

        Args:
            band_name: Band to correlate ('Theta', 'Alpha', 'Beta-1', etc.)
            **kwargs: Arguments to pass to jnwb.viz.lfp_tfr_trace_correlation

        Returns:
            Dictionary with figure, correlation matrix, and connection stats
        """
        from .viz import lfp_tfr_trace_correlation
        return lfp_tfr_trace_correlation(self, band_name=band_name, **kwargs)

    # ========================================================================
    # ANALYSIS METHODS: POPULATION STATISTICS
    # ========================================================================

    def pie_charts(self, criteria: Optional[Dict] = None, by_area: bool = True,
                  by_layer: bool = False) -> Dict:
        """
        Generate pie charts of unit populations by specified criteria.

        Useful for population summaries: which units are stable? where?

        Args:
            criteria: Filter dict, e.g. {'is_stable_plus': True, 'firing_rate': (1, 100)}
                - Keys: column names in units DataFrame
                - Values: single value, list/set of values, or tuple (min, max)
            by_area: Generate separate charts per area
            by_layer: Generate separate charts per layer

        Returns:
            Dictionary with {'figures': {group: fig}, 'counts': {group: count}}

        Example:
            >>> result = session.pie_charts(
            ...     criteria={'is_stable_plus': True},
            ...     by_area=True
            ... )
        """
        log.info(f"Pie charts: criteria={criteria}, by_area={by_area}, by_layer={by_layer}")

        if self._units_df is None:
            return {'figures': {}, 'counts': {}}

        units = self._units_df.copy()

        # Apply criteria
        if criteria:
            for key, value in criteria.items():
                if key not in units.columns:
                    continue
                if isinstance(value, tuple) and len(value) == 2:
                    units = units[(units[key] >= value[0]) & (units[key] <= value[1])]
                elif isinstance(value, (list, set)):
                    units = units[units[key].isin(value)]
                else:
                    units = units[units[key] == value]

        # Generate pie charts per area/layer/overall
        import matplotlib.pyplot as plt
        figs = {}
        counts = {}

        if by_area and 'area' in units.columns:
            groups = units.groupby('area')
        elif by_layer and 'layer' in units.columns:
            groups = units.groupby('layer')
        else:
            groups = [('All', units)]

        for name, group in groups:
            if len(group) == 0:
                continue
            fig, ax = plt.subplots(figsize=(6, 6))
            stable_col = 'stable_plus' if 'stable_plus' in group.columns else 'is_stable'
            if stable_col in group.columns:
                counts_val = group[stable_col].value_counts()
                ax.pie(counts_val, labels=counts_val.index, autopct='%1.1f%%', startangle=90)
                ax.set_title(f"Quality distribution: {name}")
                figs[str(name)] = fig
                counts[str(name)] = len(group)

        return {'figures': figs, 'counts': counts}

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def info(self) -> Dict:
        """Get session summary info."""
        return {
            'file': str(self.nwb_path.name),
            'subject': self._metadata.get('subject_id'),
            'session_start': str(self._metadata.get('session_start')),
            'n_units': len(self._units_df) if self._units_df is not None else 0,
            'n_channels': len(self._electrodes_df) if self._electrodes_df is not None else 0,
            'n_epochs': len(self._intervals_df) if self._intervals_df is not None else 0,
        }

    def summary(self) -> str:
        """Print formatted session summary."""
        info = self.info()
        lines = [
            f"OmissionSession: {info['file']}",
            f"  Subject: {info['subject']}",
            f"  Units: {info['n_units']}",
            f"  Channels: {info['n_channels']}",
            f"  Epochs: {info['n_epochs']}",
        ]
        return '\n'.join(lines)

    def __repr__(self):
        info = self.info()
        return (f"OmissionSession(file={info['file']}, "
                f"subject={info['subject']}, "
                f"units={info['n_units']}, "
                f"channels={info['n_channels']})")

    def __str__(self):
        return self.summary()
