"""
Test Spiking Metrics Functions on Real NWB Data

Validates omission.jnwb_ext.spiking module against actual spike times from 13 sessions.
Tests: compute_response_metrics, classify_response_significance, classify_omission_response, phase_locking_index

Migrates X-file tests:
- build_spk_response_metric_contract.py
- build_spk_psth_smoke_inventory.py
- _response_metric_common.py
"""

import logging
from pathlib import Path
import numpy as np
import pytest

from omission import OmissionSession
from omission.jnwb_ext import spiking, metadata

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

NWB_DIR = Path("D:/analysis/nwb")
NWB_FILES = sorted(list(NWB_DIR.glob("*.nwb")))


class TestResponseMetrics:
    """Test compute_response_metrics on real spike data."""

    def test_response_metrics_single_unit(self):
        """Compute response metrics for a single unit."""
        session = OmissionSession(str(NWB_FILES[0]))

        # Get AAAB stimulus trials
        epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)
        if len(epochs) == 0:
            pytest.skip("No AAAB epochs found")

        # Pick first unit
        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))
        if len(units) == 0:
            pytest.skip("No units found")

        unit_id = units.iloc[0]['cluster_id'] if 'cluster_id' in units.columns else units.iloc[0]['unit_id']
        spike_times = session.get_spike_times(unit_id)

        if spike_times is None or len(spike_times) == 0:
            pytest.skip(f"Unit {unit_id} has no spikes")

        # Compute metrics
        metrics = spiking.compute_response_metrics(
            spike_times,
            epochs['start_time'].values
        )

        assert isinstance(metrics, dict)
        assert 'baseline_rate' in metrics
        assert 'response_rate' in metrics
        assert 'response_zscore' in metrics
        assert metrics['n_trials'] == len(epochs)

        log.info(f"Unit {unit_id}: baseline_rate={metrics['baseline_rate']:.2f} Hz, " +
                f"response_rate={metrics['response_rate']:.2f} Hz, " +
                f"z-score={metrics['response_zscore']:.2f}")

    def test_response_metrics_multiple_units(self):
        """Compute response metrics for multiple units in a session."""
        session = OmissionSession(str(NWB_FILES[0]))
        epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)

        if len(epochs) == 0:
            pytest.skip("No AAAB epochs found")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        # Test first 5 units
        metrics_list = []
        for idx, unit_row in units.head(5).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None:
                continue

            metrics = spiking.compute_response_metrics(spike_times, epochs['start_time'].values)
            metrics_list.append(metrics)

        assert len(metrics_list) > 0
        log.info(f"Computed metrics for {len(metrics_list)} units")

        # Summary statistics
        response_rates = [m['response_rate'] for m in metrics_list]
        log.info(f"Response rates: mean={np.mean(response_rates):.2f} Hz, " +
                f"range={np.min(response_rates):.2f}-{np.max(response_rates):.2f} Hz")


class TestResponseSignificance:
    """Test classify_response_significance."""

    def test_classify_significant_response(self):
        """Classify responses as significant or not."""
        session = OmissionSession(str(NWB_FILES[0]))
        epochs = session.get_epochs(phase=2, condition='AAAB', correct_only=True)

        if len(epochs) == 0:
            pytest.skip("No AAAB epochs found")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        # Classify first 10 units
        significant_count = 0
        for idx, unit_row in units.head(10).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None:
                continue

            metrics = spiking.compute_response_metrics(spike_times, epochs['start_time'].values)
            sig = spiking.classify_response_significance(metrics, zscore_threshold=1.96)

            if sig['is_significant']:
                significant_count += 1
                log.info(f"  Unit {unit_id}: significant (z={metrics['response_zscore']:.2f}, " +
                        f"p={sig['pvalue']:.4f}, confidence={sig['confidence']})")

        log.info(f"Significant units: {significant_count}/{min(10, len(units))}")


class TestOmissionResponse:
    """Test classify_omission_response for ghost signals."""

    def test_omission_response_classification(self):
        """Classify units for stimulus vs. omission response."""
        session = OmissionSession(str(NWB_FILES[0]))

        # Get stimulus (AAAB p2) and omission (AAXB p3 is omission slot) trials
        stimulus_epochs = session.get_epochs(phase=3, condition='AAAB', correct_only=True)
        omission_epochs = session.get_epochs(phase=4, condition='AAXB', correct_only=True)

        if len(stimulus_epochs) == 0 or len(omission_epochs) == 0:
            pytest.skip("Missing stimulus or omission epochs")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        # Classify first 5 units
        for idx, unit_row in units.head(5).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None:
                continue

            classification = spiking.classify_omission_response(
                spike_times,
                stimulus_epochs['start_time'].values,
                omission_epochs['start_time'].values
            )

            log.info(f"Unit {unit_id}: sig_s={classification['sig_s']}, sig_o={classification['sig_o']}, " +
                    f"stim_rate={classification['stimulus_rate']:.2f} Hz, " +
                    f"omis_rate={classification['omission_rate']:.2f} Hz")

    def test_ghost_signal_detection(self):
        """Identify units responsive to omission (ghost signals)."""
        session = OmissionSession(str(NWB_FILES[0]))

        # p4 stimulus vs omission (AAAX = p4 omission)
        stimulus_p4 = session.get_epochs(phase=5, condition='AAAB', correct_only=True)
        omission_p4 = session.get_epochs(phase=5, condition='AAAX', correct_only=True)

        if len(stimulus_p4) == 0 or len(omission_p4) == 0:
            pytest.skip("Missing p4 stimulus or omission epochs")

        units = metadata.get_all_units_metadata(str(NWB_FILES[0]))

        ghost_signal_units = []
        for idx, unit_row in units.head(20).iterrows():
            unit_id = unit_row['cluster_id'] if 'cluster_id' in unit_row.index else unit_row['unit_id']
            spike_times = session.get_spike_times(unit_id)

            if spike_times is None:
                continue

            classification = spiking.classify_omission_response(
                spike_times,
                stimulus_p4['start_time'].values,
                omission_p4['start_time'].values,
                p_threshold=0.05
            )

            # Ghost signal: significant response to omission (sig_o=True)
            if classification['sig_o']:
                ghost_signal_units.append({
                    'unit_id': unit_id,
                    'area': unit_row.get('area', 'Unknown'),
                    'omission_rate': classification['omission_rate'],
                    'stimulus_rate': classification['stimulus_rate'],
                    'pvalue': classification['pvalue_omission']
                })

        log.info(f"Ghost signal units (sig_o) found: {len(ghost_signal_units)}/20")
        if ghost_signal_units:
            for unit in ghost_signal_units[:5]:
                log.info(f"  {unit['unit_id']} ({unit['area']}): omis_rate={unit['omission_rate']:.2f} Hz")


class TestPhaseLocking:
    """Test phase_locking_index (candidate for Y-file implementation)."""

    def test_phase_locking_synthetic(self):
        """Test phase locking with synthetic data."""
        # Create synthetic phase-locked spikes
        n_cycles = 50
        lfp_timestamps = np.linspace(0, 10, 1000)  # 10 seconds at 100 Hz
        lfp_phase = 2 * np.pi * lfp_timestamps  # 1 Hz oscillation

        # Spikes that lock to phase 0 (peak of oscillation)
        spike_times = np.array([i + 0.05 for i in range(10)])  # Spikes near peaks

        pli = spiking.phase_locking_index(spike_times, lfp_phase, lfp_timestamps)

        assert pli['pli'] > 0, "Phase locking index should be positive for phase-locked spikes"
        assert pli['rayleigh_pvalue'] < 0.05, "Rayleigh test should show non-uniform distribution"

        log.info(f"Synthetic PLI: {pli['pli']:.3f}, Rayleigh p={pli['rayleigh_pvalue']:.4f}")

    def test_phase_locking_on_real_data(self):
        """Test phase locking on real spike data (if LFP data available)."""
        session = OmissionSession(str(NWB_FILES[0]))

        # Check if LFP data is available (may not be in all sessions)
        try:
            # Try to access LFP data (this will fail if not available)
            if session.nwb is None:
                pytest.skip("NWB file not accessible for LFP data")

            # For now, skip - would need to implement LFP access in OmissionSession
            pytest.skip("LFP access not yet implemented in OmissionSession")

        except Exception as e:
            pytest.skip(f"LFP data not available: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
