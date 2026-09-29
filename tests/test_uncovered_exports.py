"""Value-pinning tests for exported callables that no test ran.

Declared exclusion: the training path of `jnwb.nam.train_nam` is not run here. It needs
PyTorch, which no CI leg installs (the `torch` extra is not in `.[test,docs,vis]`), so a
test gated on torch would skip on every leg and pin nothing. Its refusal without torch is
pinned below instead.
"""

from unittest.mock import patch

import numpy as np
import pytest

import jnwb
from jnwb import DirectedResult, TFRAnalyzer, UnitAnalyzer


def _directed(**over):
    kw = dict(method="granger", x_to_y=0.25, y_to_x=0.05, net=0.2, unit="nats",
              p_x_to_y=0.01, p_y_to_x=0.5, p_net=0.02, n_trials=10, n_times=500, fs=1000.0,
              params={"order": 3}, diagnostics={})
    kw.update(over)
    return DirectedResult(**kw)


class TestDirectedResult:
    def test_to_dict_carries_every_field_and_omits_an_absent_spectrum(self):
        d = _directed(per_band={"beta": {"value": 0.1}}, diagnostics={"warnings": ["w"]}).to_dict()
        assert d == {
            "method": "granger", "x_to_y": 0.25, "y_to_x": 0.05, "net": 0.2, "unit": "nats",
            "p_x_to_y": 0.01, "p_y_to_x": 0.5, "p_net": 0.02, "per_band": {"beta": {"value": 0.1}},
            "n_trials": 10, "n_times": 500, "fs": 1000.0, "params": {"order": 3},
            "diagnostics": {"warnings": ["w"]},
        }
        spec = {"freqs": np.arange(3.0)}
        assert _directed(spectrum=spec).to_dict()["spectrum"] is spec

    def test_ok_is_false_exactly_when_a_warning_fired(self):
        assert _directed().ok is True
        assert _directed(diagnostics={"warnings": []}).ok is True
        assert _directed(diagnostics={"warnings": ["non-stationary"]}).ok is False

    def test_summary_lines(self):
        r = _directed(per_band={"beta": {"value": 0.1, "z": 2.5}},
                      diagnostics={"warnings": ["non-stationary"]})
        assert r.summary().splitlines() == [
            "granger  (10 trials x 500 samples, fs=1000.0 Hz)",
            "  X -> Y : +0.25 nats   p=0.01",
            "  Y -> X : +0.05 nats   p=0.5",
            "  net    : +0.2 nats   p=0.02",
            "  [beta] +0.1  z=+2.500",
            "  ! non-stationary",
        ]

    def test_summary_without_p_or_fs(self):
        r = _directed(p_x_to_y=None, p_y_to_x=None, p_net=None, fs=None)
        assert r.summary().splitlines()[:2] == ["granger  (10 trials x 500 samples)",
                                                "  X -> Y : +0.25 nats"]


class TestTfrByLayer:
    def test_channel_ranges_and_masks_give_the_same_trial_average(self):
        rng = np.random.default_rng(0)
        tfr = rng.standard_normal((6, 4, 5, 8))                 # channels x freq x time x trials
        by_range = TFRAnalyzer.by_layer(tfr, {"superficial": (0, 2), "deep": (4, 6)})
        mask = np.zeros(6, bool); mask[4:6] = True
        by_mask = TFRAnalyzer.by_layer(tfr, {"deep": mask})
        np.testing.assert_allclose(by_range["superficial"]["mean"], tfr[0:2].mean(-1), rtol=1e-12)
        np.testing.assert_allclose(by_range["deep"]["sem"],
                                   tfr[4:6].std(-1, ddof=1) / np.sqrt(8), rtol=1e-12)
        np.testing.assert_allclose(by_mask["deep"]["mean"], by_range["deep"]["mean"], rtol=1e-12)
        assert by_range["deep"]["n_trials"] == 8 and set(by_range) == {"superficial", "deep"}


class TestUnitRaster:
    def test_spikes_are_aligned_windowed_and_counted(self):
        spikes = np.array([0.5, 0.9, 1.0, 1.2, 3.0, 3.1, 5.5])
        onsets = np.array([1.0, 3.0])
        r = UnitAnalyzer.raster(spikes, onsets, window_ms=(-100, 200))
        assert r["n_trials"] == 2 and r["n_spikes"] == 5 and r["window_ms"] == (-100, 200)
        assert [t["trial"] for t in r["raster"]] == [0, 1]
        np.testing.assert_allclose(r["raster"][0]["spike_times"], [-0.1, 0.0, 0.2], rtol=1e-12, atol=1e-15)
        np.testing.assert_allclose(r["raster"][1]["spike_times"], [0.0, 0.1], rtol=1e-12, atol=1e-15)


def test_train_nam_refuses_without_torch():
    with patch("jnwb.nam._TORCH_AVAILABLE", False):
        with pytest.raises(ImportError, match=r"pip install 'jnwb\[torch\]'"):
            jnwb.nam.train_nam(None, None, None, None, None)
