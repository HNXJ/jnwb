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

    # Success path: nested stratified CV
    res = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'BBBA'), n_splits=5)
    assert 'accuracy' in res
    assert 'best_params' in res
    assert 'C' in res['best_params']
    assert res['n_units'] == 2
    assert res['status'] == 'success'
    assert res['cv_scheme'] == 'nested_stratified'
    assert 'majority_baseline' in res
    assert res['majority_baseline'] == 0.5
    assert res['n_per_class'] == {'AAAB': 2, 'BBBA': 2}

    # Insufficient trials: NaN accuracy, never synthetic metrics
    res_fallback = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'NONEXISTENT'), n_splits=5)
    assert 'accuracy' in res_fallback
    assert np.isnan(res_fallback['accuracy'])
    assert res_fallback['status'] == 'insufficient_trials'
    assert res_fallback['status'] != 'synthetic_fallback'

    res_omit = decode_omission_presence(session, area='V1')
    assert 'accuracy' in res_omit


def test_decoding_f1_auc_majority_baseline_keys():
    session = MockSession()

    # Success path: new metric keys present and sane
    res = decode_stimulus_identity(session, area='V1', condition_pairs=('AAAB', 'BBBA'), n_splits=5)
    for key in ('f1', 'auc', 'majority_baseline_accuracy'):
        assert key in res
    assert 0.0 <= res['majority_baseline_accuracy'] <= 1.0
    # f1/auc may be NaN for tiny mock datasets but must be float-typed when present
    assert isinstance(res['f1'], float)
    assert isinstance(res['auc'], float)

    # decode_omission_presence delegates to decode_stimulus_identity: same keys
    res_omit = decode_omission_presence(session, area='V1')
    for key in ('f1', 'auc', 'majority_baseline_accuracy'):
        assert key in res_omit

    # Insufficient-trials path still reports the new keys as NaN, never fabricated
    res_fallback = decode_stimulus_identity(
        session, area='V1', condition_pairs=('AAAB', 'NONEXISTENT'), n_splits=5
    )
    assert np.isnan(res_fallback['f1'])
    assert np.isnan(res_fallback['auc'])
    assert np.isnan(res_fallback['majority_baseline_accuracy'])


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

    # Count estimator is available and non-negative
    mi_count = spike_mutual_information(
        spikes1, spikes2, time_window=(0.0, 5.0), bin_size_ms=10.0, estimator="spike_count"
    )
    assert mi_count >= 0.0


def test_granger_causality():
    # Bivariate signals
    rng = np.random.default_rng(0)
    t = np.linspace(0, 10, 1000)
    # Signal 1 drives Signal 2 with a lag of 2 samples
    s1 = np.sin(2 * np.pi * 5 * t) + rng.normal(0, 0.1, len(t))
    s2 = np.zeros_like(s1)
    s2[2:] = 0.8 * s1[:-2] + rng.normal(0, 0.1, len(t) - 2)

    res = granger_causality(s1, s2, order=3)
    assert 'F_1_to_2' in res
    assert 'F_2_to_1' in res
    assert res['F_1_to_2'] >= 0.0
    assert res['F_2_to_1'] >= 0.0
    assert 'diagnostics' in res
    assert 'ok_for_interpretation' in res['diagnostics']

    # Ridge path
    res_ridge = granger_causality(s1, s2, order=3, ridge=1e-3)
    assert res_ridge['ridge'] == 1e-3

    # Test auto lag selection via AIC
    res_auto = granger_causality(s1, s2, order='auto')
    assert 'order_1_to_2' in res_auto
    assert 'order_2_to_1' in res_auto
    assert res_auto['order_1_to_2'] >= 1.0
    assert res_auto['lag_criterion'] == 'aic'

    # BIC auto
    res_bic = granger_causality(s1, s2, order='auto', criterion='bic')
    assert res_bic['lag_criterion'] == 'bic'

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


# ===========================================================================
# Generalized directed connectivity: granger / phase_slope_index / transfer_entropy
#
# Every test below drives a system whose direction is known by construction, so
# a passing assertion is a statement about the estimator, not about the data.
# ===========================================================================

from jnwb import (  # noqa: E402
    as_trials,
    bin_spikes,
    granger,
    phase_slope_index,
    transfer_entropy,
    directed_connectivity,
    directed_network,
    CANONICAL_BANDS,
)


def _ar_x_drives_y(n_trials=20, n_times=600, coupling=0.6, seed=1):
    """x is autonomous AR(2); y is AR(1) driven by x at lag 2. Truth: x -> y only."""
    rng = np.random.default_rng(seed)
    x = np.zeros((n_trials, n_times))
    y = np.zeros((n_trials, n_times))
    ex = rng.normal(0, 1, (n_trials, n_times))
    ey = rng.normal(0, 1, (n_trials, n_times))
    for t in range(2, n_times):
        x[:, t] = 0.55 * x[:, t - 1] - 0.30 * x[:, t - 2] + ex[:, t]
        y[:, t] = 0.50 * y[:, t - 1] + coupling * x[:, t - 2] + ey[:, t]
    return x, y


def _delayed_oscillation(n_trials=20, n_times=2000, fs=1000.0, delay=10, seed=3):
    """20 Hz source; y is the same source shifted later by `delay` samples."""
    rng = np.random.default_rng(seed)
    t = np.arange(n_times) / fs
    src = np.zeros((n_trials, n_times))
    for i in range(n_trials):
        phase = 2 * np.pi * 20 * t + rng.normal(0, 0.3) + np.cumsum(rng.normal(0, 0.02, n_times))
        src[i] = np.sin(phase)
    x = src + 0.5 * rng.normal(0, 1, (n_trials, n_times))
    y = np.roll(src, delay, axis=1) + 0.5 * rng.normal(0, 1, (n_trials, n_times))
    y[:, :delay] = 0.0
    return x, y, src


# --- shared input contract -------------------------------------------------

def test_as_trials_shapes_and_contract():
    assert as_trials(np.arange(10.0)).shape == (1, 10)
    assert as_trials(np.zeros((4, 100))).shape == (4, 100)
    assert as_trials(np.zeros((100, 4)), time_axis=0).shape == (4, 100)
    # ragged trials truncate to the shortest rather than padding
    assert as_trials([np.arange(10.0), np.arange(8.0)]).shape == (2, 8)


def test_as_trials_rejects_ambiguous_and_nonfinite():
    with pytest.raises(ValueError, match="1-D or 2-D"):
        as_trials(np.zeros((2, 3, 4)))
    with pytest.raises(ValueError, match="non-finite"):
        as_trials(np.array([1.0, np.nan, 3.0]))
    with pytest.raises(ValueError, match="identical"):
        granger(np.zeros((2, 50)), np.zeros((3, 50)))


# --- 1. Granger ------------------------------------------------------------

def test_granger_recovers_known_direction():
    x, y = _ar_x_drives_y()
    res = granger(x, y, order='auto', max_lag=8)
    assert res.method == 'granger'
    assert res.x_to_y > 0.1
    assert res.p_x_to_y < 1e-6
    assert res.y_to_x < 0.01
    assert res.p_y_to_x > 0.01
    assert res.net > 0


def test_granger_null_on_independent_signals():
    rng = np.random.default_rng(7)
    a = rng.normal(0, 1, (20, 600))
    b = rng.normal(0, 1, (20, 600))
    res = granger(a, b, order=3)
    assert res.p_x_to_y > 0.01 and res.p_y_to_x > 0.01
    assert abs(res.x_to_y) < 0.01 and abs(res.y_to_x) < 0.01


def test_granger_conditioning_removes_common_driver():
    """z drives x at lag 1 and y at lag 2; x has no path to y."""
    rng = np.random.default_rng(11)
    n_tr, n_t = 20, 600
    z = np.zeros((n_tr, n_t))
    x = np.zeros((n_tr, n_t))
    y = np.zeros((n_tr, n_t))
    ez = rng.normal(0, 1, (n_tr, n_t))
    for t in range(3, n_t):
        z[:, t] = 0.6 * z[:, t - 1] + ez[:, t]
        x[:, t] = 0.8 * z[:, t - 1] + 0.3 * rng.normal(0, 1, n_tr)
        y[:, t] = 0.8 * z[:, t - 2] + 0.3 * rng.normal(0, 1, n_tr)
    uncond = granger(x, y, order=3)
    cond = granger(x, y, order=3, Z=z)
    assert uncond.x_to_y > 0.5           # spurious without conditioning
    assert cond.x_to_y < 0.1 * uncond.x_to_y
    assert cond.params['n_conditioning'] == 1


def test_granger_surrogates_are_deterministic():
    x, y = _ar_x_drives_y(n_trials=8, n_times=400)
    a = granger(x, y, order=3, n_surrogates=20, seed=0)
    b = granger(x, y, order=3, n_surrogates=20, seed=0)
    assert a.x_to_y == b.x_to_y
    assert a.p_x_to_y == b.p_x_to_y
    assert a.p_x_to_y <= 0.05 < a.p_y_to_x
    assert a.diagnostics['surrogates']['n_surrogates'] == 20


# --- 2. Phase slope index --------------------------------------------------

def test_psi_sign_follows_the_leading_signal():
    x, y, _ = _delayed_oscillation()
    res = phase_slope_index(x, y, fs=1000.0, bands={'beta': (14, 30)}, nperseg=256)
    beta = res.per_band['beta']
    assert beta['value'] > 0       # x leads y
    assert beta['z'] > 2           # Nolte's conventional threshold
    assert res.net == res.x_to_y == -res.y_to_x


def test_psi_is_exactly_antisymmetric():
    x, y, _ = _delayed_oscillation(n_trials=6, n_times=1000)
    fwd = phase_slope_index(x, y, fs=1000.0, bands=(14, 30), nperseg=256)
    rev = phase_slope_index(y, x, fs=1000.0, bands=(14, 30), nperseg=256)
    assert np.isclose(fwd.per_band['band']['value'], -rev.per_band['band']['value'],
                      rtol=1e-10, atol=1e-12)


def test_psi_near_zero_for_zero_lag_common_source():
    """Volume conduction / shared reference: same source, no delay, no direction."""
    _, _, src = _delayed_oscillation()
    rng = np.random.default_rng(17)
    x = src + 0.6 * rng.normal(0, 1, src.shape)
    y = 0.8 * src + 0.6 * rng.normal(0, 1, src.shape)
    res = phase_slope_index(x, y, fs=1000.0, bands={'beta': (14, 30)}, nperseg=256)
    assert abs(res.per_band['beta']['z']) < 2


def test_psi_flags_a_band_it_cannot_resolve():
    """theta (4-8 Hz) needs df < 2 Hz; nperseg=256 at 1 kHz gives df=3.9 Hz."""
    x, y, _ = _delayed_oscillation(n_trials=4, n_times=1000)
    res = phase_slope_index(x, y, fs=1000.0, bands={'theta': (4, 8)}, nperseg=256)
    assert np.isnan(res.per_band['theta']['value'])
    assert any('psi_undefined' in w for w in res.diagnostics['warnings'])
    assert not res.ok


def test_psi_canonical_bands_match_project_doctrine():
    assert CANONICAL_BANDS == {
        'theta': (4.0, 8.0), 'alpha': (8.0, 14.0), 'beta': (14.0, 30.0),
        'low_gamma': (30.0, 50.0), 'high_gamma': (50.0, 80.0),
    }
    x, y, _ = _delayed_oscillation(n_trials=6, n_times=2000)
    res = phase_slope_index(x, y, fs=1000.0, bands='canonical', nperseg=1024)
    assert set(res.per_band) == set(CANONICAL_BANDS)
    assert res.per_band['beta']['value'] > 0
    assert all(v['n_freq_bins'] >= 2 for v in res.per_band.values())


def test_psi_requires_sampling_rate():
    with pytest.raises(ValueError, match="positive fs"):
        phase_slope_index(np.zeros((2, 100)), np.zeros((2, 100)), fs=0)


# --- 3. Transfer entropy ---------------------------------------------------

def test_transfer_entropy_recovers_known_direction():
    x, y = _ar_x_drives_y()
    res = transfer_entropy(x, y, k=1, l=1, delay=2, bins=4, n_surrogates=100, seed=0)
    assert res.unit == 'bits'
    assert res.x_to_y > 0.05 and res.p_x_to_y <= 0.01
    assert res.p_y_to_x > 0.05
    assert res.diagnostics['samples_per_joint_state'] > 10
    assert res.ok


def test_transfer_entropy_catches_nonlinear_coupling_granger_misses():
    """y[t] depends on x[t-1]**2 — no linear predictability at all."""
    rng = np.random.default_rng(23)
    x = rng.normal(0, 1, (25, 800))
    y = np.zeros_like(x)
    for t in range(2, 800):
        y[:, t] = 0.3 * y[:, t - 1] + 1.2 * (x[:, t - 1] ** 2 - 1.0) + 0.3 * rng.normal(0, 1, 25)
    gc_res = granger(x, y, order=3)
    te_res = transfer_entropy(x, y, k=1, l=1, delay=1, bins=5, n_surrogates=100, seed=0)
    assert gc_res.p_x_to_y > 0.05          # linear model sees nothing
    assert te_res.p_x_to_y <= 0.01         # information-theoretic model does


@pytest.mark.parametrize("estimator,kwargs", [
    ("quantile", {"bins": 4}),
    ("uniform", {"bins": 4}),
    ("symbolic", {"symbolic_order": 3}),
])
def test_transfer_entropy_estimators_agree_on_direction(estimator, kwargs):
    x, y = _ar_x_drives_y(n_trials=10)
    res = transfer_entropy(x, y, estimator=estimator, delay=2,
                           n_surrogates=60, seed=0, **kwargs)
    assert res.x_to_y > res.y_to_x
    assert res.p_x_to_y <= 0.05


def test_transfer_entropy_discrete_estimator_on_spike_counts():
    rng = np.random.default_rng(5)
    x = rng.poisson(1.0, (30, 500)).astype(float)
    y = np.zeros_like(x)
    for t in range(1, 500):
        y[:, t] = rng.poisson(0.2 + 0.5 * x[:, t - 1])
    res = transfer_entropy(x, y, estimator='discrete', delay=1, n_surrogates=100, seed=0)
    assert res.p_x_to_y <= 0.01 and res.p_y_to_x > 0.05
    # continuous data must be refused by the discrete estimator
    with pytest.raises(ValueError, match="continuous signal"):
        transfer_entropy(rng.normal(0, 1, (4, 200)), rng.normal(0, 1, (4, 200)),
                         estimator='discrete', n_surrogates=0)


def test_transfer_entropy_warns_when_surrogates_are_skipped():
    x, y = _ar_x_drives_y(n_trials=4, n_times=200)
    res = transfer_entropy(x, y, n_surrogates=0)
    assert res.p_x_to_y is None
    assert 'no_surrogates_raw_te_is_positively_biased' in res.diagnostics['warnings']


# --- spike bridge ----------------------------------------------------------

def test_bin_spikes_counts_rates_and_epoching():
    st = np.array([0.005, 0.015, 0.016, 0.099, 0.5])
    counts = bin_spikes(st, (0.0, 0.1), bin_size_ms=10.0)
    assert counts.shape == (1, 10)
    assert counts.sum() == 4          # 0.5 s falls outside the window
    assert counts[0, 1] == 2
    rates = bin_spikes(st, (0.0, 0.1), 10.0, output='rate')
    assert np.allclose(rates, counts / 0.01)
    epoched = bin_spikes(np.array([1.005, 1.015, 2.005]), (0.0, 0.1), 10.0,
                         trial_starts=[1.0, 2.0])
    assert epoched.shape == (2, 10)
    assert epoched.sum(axis=1).tolist() == [2.0, 1.0]
    _, centers = bin_spikes(st, (0.0, 0.1), 10.0, return_centers=True)
    assert np.isclose(centers[0], 0.005)


def test_spike_counts_flow_into_granger_unchanged():
    """The estimators take binned spikes with no modality-specific arguments."""
    rng = np.random.default_rng(31)
    starts = np.arange(30) * 5.0
    times = np.sort(np.concatenate(
        [s + rng.uniform(0, 1.0, rng.poisson(20)) for s in starts]))
    driver = bin_spikes(times, (0.0, 1.0), 10.0, trial_starts=starts)
    follower = np.roll(driver, 2, axis=1) + rng.poisson(0.2, driver.shape)
    res = granger(driver, follower, order=4)
    assert driver.shape == (30, 100)
    assert res.x_to_y > res.y_to_x
    assert res.p_x_to_y < 0.01


# --- dispatcher and network ------------------------------------------------

def test_directed_connectivity_dispatch():
    x, y = _ar_x_drives_y(n_trials=6, n_times=300)
    assert directed_connectivity(x, y, method='gc', order=3).method == 'granger'
    assert directed_connectivity(x, y, method='te', n_surrogates=0).method == 'transfer_entropy'
    assert directed_connectivity(x, y, method='psi', fs=1000.0, nperseg=128).method == 'psi'
    with pytest.raises(ValueError, match="Unknown method"):
        directed_connectivity(x, y, method='coherence')


def test_directed_network_orientation_and_fdr():
    x, y = _ar_x_drives_y(n_trials=10, n_times=400)
    rng = np.random.default_rng(43)
    noise = rng.normal(0, 1, x.shape)
    net = directed_network({'A': x, 'B': y, 'C': noise}, method='granger', order=3)
    i_a, i_b = net['labels'].index('A'), net['labels'].index('B')
    # M[i, j] is the influence of node i on node j
    assert net['matrix'][i_a, i_b] > net['matrix'][i_b, i_a]
    assert np.isnan(net['matrix'][0, 0])            # no self-loops
    assert net['fdr_family_size'] == 6              # all ordered pairs, one family
    assert np.isfinite(net['q_matrix'][i_a, i_b])
    assert net['q_matrix'][i_a, i_b] <= 0.05


def test_directed_network_psi_matrix_is_antisymmetric():
    x, y, _ = _delayed_oscillation(n_trials=6, n_times=1000)
    net = directed_network(np.stack([x, y]), method='psi', labels=['x', 'y'],
                           fs=1000.0, bands=(14, 30), nperseg=256)
    assert net['matrix'][0, 1] > 0
    assert np.isclose(net['matrix'][0, 1], -net['matrix'][1, 0])


def test_directed_result_surface():
    x, y = _ar_x_drives_y(n_trials=5, n_times=300)
    res = granger(x, y, order=3)
    assert res['method'] == res.method          # dict-style access
    assert 'x_to_y' in res.to_dict()
    assert isinstance(res.summary(), str)
    assert res.n_trials == 5 and res.n_times == 300
