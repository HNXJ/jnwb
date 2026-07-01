"""
Tests for population decoding and functional connectivity modules.

Author: Claude Code
Date: 2026-06-30
"""

import numpy as np
import pandas as pd
import pytest
from jnwb import (
    decode_stimulus_identity,
    decode_omission_presence,
    spike_mutual_information,
    granger_causality,
    network_topology
)

# Mock session object for testing
class MockSession:
    def __init__(self):
        self.units_df = pd.DataFrame({
            'unit_id': [1, 2, 3],
            'area': ['V1', 'V1', 'V4'],
            'quality': ['stable_plus', 'stable', 'stable_plus']
        })
        self.epochs_df = pd.DataFrame({
            'start_time': [1.0, 2.0, 3.0, 4.0],
            'condition': ['AAAB', 'BBBA', 'AAAB', 'BBBA']
        })
        # Mock spike times
        self.spikes = {
            1: np.array([1.01, 1.05, 2.02, 3.01, 3.05, 4.02]),
            2: np.array([1.02, 2.03, 3.02, 4.03]),
            3: np.array([1.03, 2.04, 3.03, 4.04])
        }

    def get_units(self, quality=None, area=None):
        df = self.units_df.copy()
        if quality:
            df = df[df['quality'] == quality]
        if area:
            df = df[df['area'] == area]
        return df

    def get_epochs(self, condition=None):
        df = self.epochs_df.copy()
        if condition:
            df = df[df['condition'] == condition]
        return df

    def get_spike_times(self, unit_id):
        return self.spikes.get(unit_id, np.array([]))


def test_decoding_fallback():
    session = MockSession()
    
    # Success path: has enough trials for 2-fold Stratified CV
    res = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'BBBA'), n_splits=5)
    assert 'accuracy' in res
    assert 'best_params' in res
    assert 'C' in res['best_params']
    assert res['n_units'] == 2
    assert res['status'] == 'success'

    # Fallback path: trigger synthetic fallback via missing condition
    res_fallback = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'NONEXISTENT'), n_splits=5)
    assert 'accuracy' in res_fallback
    assert res_fallback['n_units'] == 10
    assert res_fallback['status'] == 'synthetic_fallback'

    res_omit = decode_omission_presence(session, area='V1')
    assert 'accuracy' in res_omit


def test_spike_mutual_information():
    # Identical spike trains
    spikes1 = np.array([1.0, 2.0, 3.0, 4.0])
    spikes2 = np.array([1.0, 2.0, 3.0, 4.0])
    mi = spike_mutual_information(spikes1, spikes2, time_window=(0.0, 5.0), bin_size_ms=10.0)
    assert isinstance(mi, float)
    assert mi >= 0.0

    # Non-overlapping spike trains
    spikes3 = np.array([0.5, 1.5, 2.5])
    spikes4 = np.array([5.0, 6.0, 7.0])
    mi_none = spike_mutual_information(spikes3, spikes4, time_window=(0.0, 10.0), bin_size_ms=10.0)
    assert mi_none >= 0.0


def test_granger_causality():
    # Bivariate signals
    t = np.linspace(0, 10, 1000)
    # Signal 1 drives Signal 2 with a lag of 2 samples
    s1 = np.sin(2 * np.pi * 5 * t) + np.random.normal(0, 0.1, len(t))
    s2 = np.zeros_like(s1)
    s2[2:] = 0.8 * s1[:-2] + np.random.normal(0, 0.1, len(t) - 2)

    res = granger_causality(s1, s2, order=3)
    assert 'F_1_to_2' in res
    assert 'F_2_to_1' in res
    assert res['F_1_to_2'] >= 0.0
    assert res['F_2_to_1'] >= 0.0

    # Test auto lag selection via AIC
    res_auto = granger_causality(s1, s2, order='auto')
    assert 'order_1_to_2' in res_auto
    assert 'order_2_to_1' in res_auto
    assert res_auto['order_1_to_2'] >= 1.0

    # Test GPU implementation call
    res_cuda = granger_causality(s1, s2, order=3, device='cuda')
    assert 'F_1_to_2' in res_cuda
    assert 'F_2_to_1' in res_cuda
    assert res_cuda['F_1_to_2'] >= 0.0


def test_network_topology():
    adj = np.array([
        [1.0, 0.4, 0.1],
        [0.4, 1.0, 0.8],
        [0.1, 0.8, 1.0]
    ])
    res = network_topology(adj, threshold=0.3)
    assert res['n_nodes'] == 3
    assert res['n_edges'] == 4  # 0.4, 0.4, 0.8, 0.8 (directional counts)
    assert 0.0 <= res['density'] <= 1.0
    assert len(res['in_degrees']) == 3


def test_decoding_gpu():
    session = MockSession()
    # Test decoding execution path with device='cuda'
    res_cuda = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'BBBA'), n_splits=5, device='cuda')
    assert 'accuracy' in res_cuda
    assert 'status' in res_cuda


def test_decoding_baseline_subtraction():
    session = MockSession()
    # Success path: has enough trials for 2-fold Stratified CV
    res = decode_stimulus_identity(
        session,
        area='V1',
        condition_pairs=('AAAB', 'BBBA'),
        time_window_ms=(0.0, 150.0),
        baseline_window_ms=(-150.0, 0.0),
        n_splits=5
    )
    assert 'accuracy' in res
    assert 'status' in res


def test_plot_granger_network_plotly():
    from jnwb import plot_granger_network_plotly
    adj = np.array([
        [0.0, 0.4, 0.01],
        [0.0, 0.0, 0.8],
        [0.1, 0.0, 0.0]
    ])
    fig = plot_granger_network_plotly(adj, node_labels=['V1', 'V2', 'V4'], threshold=0.05)
    assert fig is not None
    assert fig.layout.title.text == "Directed Granger Causality Network Graph"
