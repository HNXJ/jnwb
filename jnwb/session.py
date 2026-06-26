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

        self._load_nwb()
        log.info(f"✓ Loaded {self.nwb_path.name}")

    def _load_nwb(self):
        """Load NWB file and cache key dataframes."""
        with NWBHDF5IO(str(self.nwb_path), 'r', load_namespaces=True) as io:
            nwb = io.read()

            # Cache units
            if nwb.units is not None:
                self._units_df = nwb.units.to_dataframe().copy()

                # Enrich units with area info from electrode location (while file is open)
                if nwb.electrodes is not None:
                    elec_df = nwb.electrodes.to_dataframe().copy()

                    # Map peak_channel_id to electrode location (area)
                    if 'peak_channel_id' in self._units_df.columns and 'location' in elec_df.columns:
                        # Create a mapping from electrode index to area
                        chan_to_area = {}
                        for idx, row in elec_df.iterrows():
                            try:
                                chan_to_area[float(idx)] = row['location']
                            except:
                                pass

                        # Add area column by mapping peak_channel_id
                        self._units_df['area'] = self._units_df['peak_channel_id'].apply(
                            lambda x: chan_to_area.get(float(x), None) if pd.notna(x) else None
                        )

                        # Extract main area (first part of location string if comma-separated)
                        self._units_df['area'] = self._units_df['area'].apply(
                            lambda x: str(x).split(',')[0].strip() if pd.notna(x) else None
                        )

                    # Add layer as placeholder (would need layer_masks.json for proper assignment)
                    if 'z' in elec_df.columns and 'peak_channel_id' in self._units_df.columns:
                        chan_to_z = {}
                        for idx, row in elec_df.iterrows():
                            try:
                                chan_to_z[float(idx)] = row['z']
                            except:
                                pass

                        z_vals = self._units_df['peak_channel_id'].apply(
                            lambda x: chan_to_z.get(float(x), 500) if pd.notna(x) else 500
                        )
                        # Simple heuristic: deep/shallow based on z coordinate
                        self._units_df['layer'] = 'Unknown'
                        self._units_df.loc[z_vals > 1000, 'layer'] = 'Deep'
                        self._units_df.loc[z_vals <= 1000, 'layer'] = 'Superficial'
                    else:
                        self._units_df['layer'] = 'Unknown'

            # Ensure numeric columns are properly typed (after loading from NWB)
            for col in ['firing_rate', 'waveform_duration', 'quality', 'peak_channel_id']:
                if col in self._units_df.columns:
                    self._units_df[col] = pd.to_numeric(self._units_df[col], errors='coerce')

            # Create quality boolean columns from quality values
            if self._units_df is not None and 'quality' in self._units_df.columns:
                # quality == 1.0 means good/stable units
                self._units_df['is_stable'] = self._units_df['quality'] >= 1.0
                # For now, stable_plus = is_stable (could be refined with additional criteria)
                self._units_df['stable_plus'] = self._units_df['is_stable']

            # Cache electrodes
            if nwb.electrodes is not None:
                self._electrodes_df = nwb.electrodes.to_dataframe()

            # Cache interval data
            if self.context in nwb.intervals:
                self._intervals_df = nwb.intervals[self.context].to_dataframe()

            # Extract metadata
            self._metadata = {
                'subject_id': nwb.subject.subject_id if nwb.subject else None,
                'session_start': nwb.session_start_time,
                'session_description': nwb.session_description,
                'n_units': len(self._units_df) if self._units_df is not None else 0,
            }

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

        Args:
            phase: stimulus_number (1=fixation, 2=p1, 3=p2, 4=p3, 5=p4)
            condition: condition code or name (e.g., 'AAXB')
            correct_only: Include only correct trials

        Returns:
            Filtered intervals DataFrame

        Example:
            >>> p2_omission = session.get_epochs(phase=3, condition='AAXB')
            >>> all_p1 = session.get_epochs(phase=2)
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
                # Map condition name to codes
                condition_map = {
                    'AAAB': [1, 2], 'AXAB': [3], 'AAXB': [4], 'AAAX': [5],
                    'BBBA': [6, 7], 'BXBA': [8], 'BBXA': [9], 'BBBX': [10],
                    'RRRR': list(range(11, 27)), 'RXRR': list(range(27, 35)),
                    'RRXR': [35, 37, 39, 41], 'RRRX': [36, 38, 40] + list(range(42, 51))
                }
                condition_codes = [float(c) for c in condition_map.get(condition, [])]
            else:
                condition_codes = [float(condition)]

            if 'task_condition_number' in epochs.columns:
                epochs = epochs[epochs['task_condition_number'].isin(condition_codes)]

        return epochs

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

        # Find the unit row (handle both cluster_id and unit_id columns)
        if 'cluster_id' in self._units_df.columns:
            unit_col = 'cluster_id'
        elif 'unit_id' in self._units_df.columns:
            unit_col = 'unit_id'
        else:
            log.error("No unit_id or cluster_id column in units table")
            return None

        # Convert to numeric for comparison
        unit_id_numeric = float(unit_id) if isinstance(unit_id, (int, str)) else unit_id

        # Find matching unit row
        matching = self._units_df[pd.to_numeric(self._units_df[unit_col], errors='coerce') == unit_id_numeric]

        if len(matching) == 0:
            log.warning(f"Unit {unit_id} not found")
            return None

        # Get spike_times from the first matching row
        spike_times = matching.iloc[0]['spike_times']

        if spike_times is None or len(spike_times) == 0:
            log.warning(f"Unit {unit_id}: no spike times")
            return None

        return np.array(spike_times)

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
        log.info(f"Trial-averaging {area} phase={phase} condition={condition}")
        # TODO: Load TFR → filter epochs → average → plot
        return {'status': 'queued', 'area': area, 'phase': phase, 'condition': condition}

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
        log.info(f"Channel-averaging {area} phase={phase}")
        # TODO: Implement
        return {'status': 'queued'}

    def spectrolaminar_motif(self, area: str, condition: str = 'AAAB',
                            layer_masks: Optional[Dict] = None) -> Dict:
        """
        Spectrolaminar analysis: cross-frequency coupling by cortical layer.

        Uses CSD-derived layer boundaries to analyze spectral content by depth.

        Args:
            area: Brain area
            condition: Behavioral condition (e.g., 'AAXB' for p2 omission)
            layer_masks: Optional dict with layer boundary info {area: {'superficial': (0,10), 'deep': (10,20)}}

        Returns:
            Dictionary with spectral × layer heatmaps and statistics

        Example:
            >>> session.spectrolaminar_motif(area='MT', condition='omission')
        """
        log.info(f"Spectrolaminar motif: {area} {condition}")
        # TODO: Load CSD, identify layer boundaries, compute by-layer spectra
        return {'status': 'queued'}

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

        # Extract area from location string (e.g., 'V1/L2/3' → 'V1')
        if 'location' in elecs.columns:
            elecs['area'] = elecs['location'].str.split('/').str[0]
            if '/' in elecs['location'].iloc[0] if len(elecs) > 0 else False:
                elecs['layer'] = elecs['location'].str.split('/').str[1]
            else:
                elecs['layer'] = ''

        id_col = 'id' if 'id' in elecs.columns else elecs.index.name or 'channel'
        return elecs[[id_col, 'area', 'layer']].rename(columns={id_col: 'channel_id'})

    # ========================================================================
    # ANALYSIS METHODS: TFR & SPECTRAL
    # ========================================================================

    def tfr_from_preprocessed(self, area: str, band: str = 'alpha',
                             condition: Optional[str] = None,
                             tfr_dir: Optional[Path] = None) -> Optional[np.ndarray]:
        """
        Load preprocessed TFR array (time-frequency representation).

        Fast loader for precomputed TFR data (D:/workspace/data/tfr_arrays/).

        Args:
            area: Brain area
            band: Frequency band ('alpha', 'beta', 'gamma', etc.) or None for all
            condition: Behavioral condition code
            tfr_dir: Override default TFR directory

        Returns:
            TFR array (channels × frequency × time × trials) or None if not found

        Example:
            >>> tfr = session.tfr_from_preprocessed(area='V1', band='alpha', condition='AAXB')
        """
        log.info(f"Loading TFR: {area} band={band} condition={condition}")
        # TODO: Construct filename, load from tfr_dir
        return None

    def plot_tfr(self, area: str, condition: str = 'stimulus',
                 phase: int = 2, plot_kwargs: Optional[Dict] = None) -> Dict:
        """
        Plot time-frequency representation for area × condition.

        Args:
            area: Brain area
            condition: Behavioral condition name or code
            phase: stimulus_number (for timing alignment)
            plot_kwargs: Matplotlib parameters (figsize, cmap, etc.)

        Returns:
            Dictionary with {'figure': fig, 'axes': axes}

        Example:
            >>> session.plot_tfr(area='MT', condition='AAXB', phase=3)
        """
        log.info(f"Plotting TFR: {area} {condition} phase={phase}")
        # TODO: Implement TFR plotting
        return {'status': 'queued'}

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
        
        for trial_id, trial_spikes in spikes_by_trial.items():
            ax_ras.vlines(trial_spikes, trial_id - 0.4, trial_id + 0.4, colors='black', linewidth=0.5)
        
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

        # TODO: Generate pie charts
        return {'counts': len(units), 'status': 'queued'}

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
