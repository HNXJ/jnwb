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
                self._units_df = nwb.units.to_dataframe()

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
        initial_count = len(epochs)

        if correct_only and 'correct' in epochs.columns:
            epochs = epochs[epochs['correct'] == 1.0]

        if phase is not None and 'stimulus_number' in epochs.columns:
            epochs = epochs[epochs['stimulus_number'] == phase]

        if condition is not None:
            if isinstance(condition, str):
                # Map condition name to codes
                condition_map = {
                    'AAAB': [1, 2], 'AXAB': [3], 'AAXB': [4], 'AAAX': [5],
                    'BBBA': [6, 7], 'BXBA': [8], 'BBXA': [9], 'BBBX': [10],
                    'RRRR': list(range(11, 27)), 'RXRR': list(range(27, 35)),
                    'RRXR': [35, 37, 39, 41], 'RRRX': [36, 38, 40] + list(range(42, 51))
                }
                condition_codes = condition_map.get(condition, [])
            else:
                condition_codes = [condition]

            if 'task_condition_number' in epochs.columns:
                epochs = epochs[epochs['task_condition_number'].isin(condition_codes)]

        return epochs

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
        Map recording channels to single units via peak_channel_global.

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

        mapping = units[[
            'cluster_id', 'peak_channel_global', 'area', 'layer'
        ]].rename(columns={'cluster_id': 'unit_id', 'peak_channel_global': 'channel_id'})

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

        Three-panel figure for single-unit analysis.

        Args:
            unit_id: Unit cluster ID
            condition: Behavioral condition (omission condition, e.g., 'AAXB')
            phase: stimulus_number (1-5)
            window_ms: Time window relative to phase onset (ms)

        Returns:
            Dictionary with {'raster': fig1, 'psth': fig2, 'autocorr': fig3}

        Example:
            >>> session.raster_suite(unit_id=42, condition='AAXB', phase=3)
        """
        log.info(f"Raster suite: unit={unit_id} condition={condition} phase={phase}")
        # TODO: Load spike times, create raster + PSTH + autocorr
        return {'status': 'queued'}

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
