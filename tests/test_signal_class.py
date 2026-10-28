"""Per-call signal class: the generic-input operations take it, refuse a mix, and warn when it is omitted."""

from __future__ import annotations

import inspect
import warnings

import numpy as np
import pytest

import jnwb
from jnwb import _declarations
from jnwb.connectivity import _network
from jnwb.spectral import _coupling
from scripts import build_fact_graph

FS = 500.0
BAND = (8.0, 14.0)
COUPLING = "jnwb.spectral._coupling.imaginary_coherency"
NETWORK = "jnwb.connectivity._network.directed_network"


def _call(fn, *args, **kwargs):
    """Run ``fn``; return its result and the messages of the FutureWarnings it raised."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = fn(*args, **kwargs)
    return result, [str(w.message) for w in caught if issubclass(w.category, FutureWarning)]


def _signals(seed: int = 3, n: int = 600):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = 0.6 * np.roll(x, 2) + rng.normal(size=n)
    assert np.std(x) > 0 and np.std(y) > 0, "fixture must vary"
    return x, y


def _coherent_pair(seed: int = 4, n: int = 4000):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    y = np.roll(x, 5) + 0.5 * rng.normal(size=n)
    assert np.std(x) > 0 and np.std(y) > 0, "fixture must vary"
    return x, y


def _network_signals(n: int = 400):
    rng = np.random.default_rng(5)
    base = rng.normal(size=(3, n))
    base[1] += 0.8 * np.roll(base[0], 1)
    signals = {"A": base[0], "B": base[1], "C": base[2]}
    assert all(np.std(v) > 0 for v in signals.values()), "fixture must vary"
    return signals


# ---------------------------------------------------------------- granger_causality


def test_granger_causality_explicit_class_is_silent_and_keeps_the_numbers():
    x, y = _signals()
    omitted, _ = _call(jnwb.granger_causality, x, y, order=2)
    explicit, future = _call(jnwb.granger_causality, x, y, order=2, signal_class="lfp")
    assert np.isfinite(omitted["F_2_to_1"]), "fixture must give a finite statistic"
    assert future == [], future
    assert explicit["F_2_to_1"] == omitted["F_2_to_1"]
    assert explicit["F_1_to_2"] == omitted["F_1_to_2"]


def test_granger_causality_omitted_class_warns_naming_the_keyword_and_still_runs():
    x, y = _signals()
    result, future = _call(jnwb.granger_causality, x, y, order=2)
    assert len(future) == 1 and "signal_class=" in future[0], future
    assert np.isfinite(result["F_2_to_1"]), "the call must still compute"


@pytest.mark.parametrize("bad", ["spike", "LFP", None, 3])
def test_granger_causality_refuses_a_value_outside_the_two_classes(bad):
    x, y = _signals()
    with pytest.raises(ValueError, match="'spikes' or 'lfp'"):
        jnwb.granger_causality(x, y, order=2, signal_class=bad)


def test_granger_causality_refuses_a_pair_that_mixes_spikes_and_lfp():
    x, y = _signals()
    with pytest.raises(ValueError, match="never pooled") as info:
        jnwb.granger_causality(x, y, order=2, signal_class=("spikes", "lfp"))
    assert "granger_causality" in str(info.value)


def test_granger_causality_accepts_an_equal_pair_with_the_single_class_numbers():
    x, y = _signals()
    pair, future = _call(jnwb.granger_causality, x, y, order=2, signal_class=("lfp", "lfp"))
    single, _ = _call(jnwb.granger_causality, x, y, order=2, signal_class="lfp")
    assert future == [], future
    assert pair["F_2_to_1"] == single["F_2_to_1"]
    assert pair["F_1_to_2"] == single["F_1_to_2"]


# ---------------------------------------------------------------- directed_network


def test_directed_network_explicit_class_is_silent_and_keeps_the_matrix():
    signals = _network_signals()
    omitted, _ = _call(jnwb.directed_network, signals, method="granger", order=2, fdr=False)
    explicit, future = _call(jnwb.directed_network, signals, method="granger", order=2,
                             fdr=False, signal_class="lfp")
    assert np.isfinite(omitted["matrix"][0, 1]), "fixture must give a finite edge"
    assert future == [], future
    np.testing.assert_array_equal(explicit["matrix"], omitted["matrix"])


def test_directed_network_omitted_class_warns_once_and_keeps_the_matrix():
    signals = _network_signals()
    explicit, _ = _call(jnwb.directed_network, signals, method="granger", order=2, fdr=False,
                        signal_class="spikes")
    omitted, future = _call(jnwb.directed_network, signals, method="granger", order=2, fdr=False)
    assert len(future) == 1 and "signal_class=" in future[0], future
    np.testing.assert_array_equal(omitted["matrix"], explicit["matrix"])


def test_directed_network_refuses_a_pair_where_one_class_is_expected():
    signals = _network_signals()
    with pytest.raises(ValueError, match="takes one class"):
        jnwb.directed_network(signals, method="granger", order=2, fdr=False,
                              signal_class=("spikes", "lfp"))


def test_directed_network_consumes_the_class_and_does_not_pass_it_to_the_pairwise_estimator():
    rng = np.random.default_rng(6)
    signals = {k: v for k, v in zip("ABC", rng.normal(size=(3, 2000)))}
    out, future = _call(jnwb.directed_network, signals, method="psi", fs=FS, jackknife=False,
                        fdr=False, signal_class="lfp")
    assert out["method"] == "psi", "fixture must run the phase-slope estimator"
    assert future == [], future
    assert out["matrix"].shape == (3, 3)


# ---------------------------------------------------------------- imaginary_coherency


def test_imaginary_coherency_explicit_class_is_silent_and_keeps_the_numbers():
    x, y = _coherent_pair()
    omitted, _ = _call(jnwb.imaginary_coherency, x, y, fs=FS, freq_range=BAND)
    explicit, future = _call(jnwb.imaginary_coherency, x, y, fs=FS, freq_range=BAND,
                             signal_class="lfp")
    assert abs(omitted["icoh_mean"]) > 1e-3, "fixture must carry a lagged coupling"
    assert future == [], future
    assert explicit["icoh_mean"] == omitted["icoh_mean"]
    assert explicit["coh_mag_mean"] == omitted["coh_mag_mean"]


def test_imaginary_coherency_omitted_class_warns_naming_the_keyword_and_still_runs():
    x, y = _coherent_pair()
    result, future = _call(jnwb.imaginary_coherency, x, y, fs=FS, freq_range=BAND)
    assert len(future) == 1 and "signal_class=" in future[0], future
    assert np.isfinite(result["icoh_mean"]), "the call must still compute"


@pytest.mark.parametrize("bad", ["spike", "LFP", None, 3])
def test_imaginary_coherency_refuses_a_value_outside_the_two_classes(bad):
    x, y = _coherent_pair()
    with pytest.raises(ValueError, match="'spikes' or 'lfp'"):
        jnwb.imaginary_coherency(x, y, fs=FS, freq_range=BAND, signal_class=bad)


def test_imaginary_coherency_refuses_a_pair_that_mixes_spikes_and_lfp():
    x, y = _coherent_pair()
    with pytest.raises(ValueError, match="never pooled") as info:
        jnwb.imaginary_coherency(x, y, fs=FS, freq_range=BAND, signal_class=("lfp", "spikes"))
    assert "imaginary_coherency" in str(info.value)


def test_imaginary_coherency_accepts_an_equal_pair_with_the_single_class_numbers():
    x, y = _coherent_pair()
    pair, future = _call(jnwb.imaginary_coherency, x, y, fs=FS, freq_range=BAND,
                         signal_class=("spikes", "spikes"))
    single, _ = _call(jnwb.imaginary_coherency, x, y, fs=FS, freq_range=BAND,
                      signal_class="spikes")
    assert future == [], future
    assert pair["icoh_mean"] == single["icoh_mean"]


# ---------------------------------------------------------------- the fact I4 scan


def test_the_live_tree_holds_the_signal_class_scan():
    examined, found = build_fact_graph.signal_class_scan()
    assert examined == len(build_fact_graph.I4_OPERATIONS) == 3, examined
    assert found == [], found


def test_a_stand_in_without_the_keyword_is_reported(monkeypatch):
    def stand_in(signals, method="granger", labels=None, fdr=True, fdr_method="bh", n_jobs=1,
                 *, conditional=False, **kwargs):
        return {}

    assert "signal_class" not in inspect.signature(stand_in).parameters, "fixture must lack it"
    monkeypatch.setattr(_network, "directed_network", stand_in)
    _, found = build_fact_graph.signal_class_scan()
    assert [NETWORK, "signature has no keyword-only signal_class"] in found, found


def test_a_stand_in_with_a_positional_signal_class_is_reported(monkeypatch):
    def stand_in(x, y, fs=None, signal_class=None):
        return {}

    kind = inspect.signature(stand_in).parameters["signal_class"].kind
    assert kind is inspect.Parameter.POSITIONAL_OR_KEYWORD, "fixture must not be keyword-only"
    monkeypatch.setattr(_coupling, "imaginary_coherency", stand_in)
    _, found = build_fact_graph.signal_class_scan()
    assert [COUPLING, "signature has no keyword-only signal_class"] in found, found


def test_an_operation_with_no_declaration_is_reported(monkeypatch):
    assert COUPLING in _declarations.DECLARATIONS, "fixture must start declared"
    trimmed = {k: v for k, v in _declarations.DECLARATIONS.items() if k != COUPLING}
    monkeypatch.setattr(_declarations, "DECLARATIONS", trimmed)
    _, found = build_fact_graph.signal_class_scan()
    assert [COUPLING, "declares no input class in jnwb/_declarations.py"] in found, found


def test_the_signature_types_scan_does_not_report_the_three_as_stale():
    examined, found = build_fact_graph.signature_types_scan(jnwb)
    assert examined > 0, "the scan must examine callables"
    named = {key for key, _ in found}
    for key in build_fact_graph.I4_OPERATIONS:
        assert key not in named, found
