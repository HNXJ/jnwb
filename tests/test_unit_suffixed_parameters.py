"""A time parameter whose name carries no unit puts a 1000x error one keystroke
away.

`examples/tutorials/03_spiking.py` calls `raster_psth(..., win_ms=(-100., 400.))` at line
38 and `compute_response_metrics(..., baseline_window=(-0.2, 0.0))` at line 61 in the same
body. Both take a float 2-tuple; only one says what a float means. Nine such parameters
across six exported functions now carry their unit, with the old spelling kept as an alias
and a conflict between the two an error -- the pattern `band_power(fs=, sampling_rate=)`
already implements.

Each test fails when its repair is reverted.
"""

from __future__ import annotations

import inspect
import re
import warnings

import numpy as np
import pytest

import jnwb
from jnwb._units import resolve_unit_alias
from jnwb.connectivity import (
    bin_spikes,
    binary_occupancy_mutual_information,
    spike_count_mutual_information,
    spike_mutual_information,
)
from jnwb.onset_fitting import fit_exponential_onset
from jnwb.spiking import compute_response_metrics

def _assert_metrics_equal(a, b):
    """`==` on these dicts is not equality: `response_zscore` is NaN in the undefined
    case (05-16) and `nan != nan`, so a plain `==` reports a difference that is not one.
    """
    assert a.keys() == b.keys()
    for key in a:
        x, y = a[key], b[key]
        if isinstance(x, float) and isinstance(y, float) and np.isnan(x) and np.isnan(y):
            continue
        assert x == y, f"{key}: {x!r} != {y!r}"


# (function, canonical unit-bearing name, old spelling)
RENAMED = [
    (compute_response_metrics, "baseline_window_s", "baseline_window"),
    (compute_response_metrics, "response_window_s", "response_window"),
    (bin_spikes, "window_s", "window"),
    (spike_mutual_information, "time_window_s", "time_window"),
    (binary_occupancy_mutual_information, "time_window_s", "time_window"),
    (spike_count_mutual_information, "time_window_s", "time_window"),
    (fit_exponential_onset, "t0_bounds_ms", "t0_bounds"),
    (fit_exponential_onset, "tau_bounds_ms", "tau_bounds"),
    (fit_exponential_onset, "baseline_window_ms", "baseline_window"),
    (fit_exponential_onset, "t0_grid_step_ms", "t0_grid_step"),
]

IDS = [f"{fn.__name__}.{new}" for fn, new, _ in RENAMED]


class TestEveryRenamedParameterKeepsItsAlias:
    @pytest.mark.parametrize("fn,new,old", RENAMED, ids=IDS)
    def test_both_spellings_are_accepted(self, fn, new, old):
        params = inspect.signature(fn).parameters
        assert new in params, f"{fn.__name__} lost the unit-bearing name {new}"
        assert old in params, f"{fn.__name__} dropped the alias {old}, breaking callers"

    @pytest.mark.parametrize("fn,new,old", RENAMED, ids=IDS)
    def test_the_alias_is_keyword_only_so_position_still_means_the_same_thing(
        self, fn, new, old
    ):
        """A caller passing positionally must keep hitting the same argument."""
        params = inspect.signature(fn).parameters
        assert params[old].kind is inspect.Parameter.KEYWORD_ONLY


class TestConflictingSpellingsRaise:
    """Repeating yourself is harmless; contradicting yourself is not. This is the case
    that matters: the value under one name in seconds and the other in milliseconds.
    """

    def test_compute_response_metrics(self):
        spikes = np.array([0.201, 0.205, 0.210])
        onsets = np.array([0.2])
        with pytest.raises(ValueError, match="Conflicting values"):
            compute_response_metrics(
                spikes, onsets,
                baseline_window_s=(-0.2, 0.0), baseline_window=(-200.0, 0.0),
            )
        with pytest.raises(ValueError, match="Conflicting values"):
            compute_response_metrics(
                spikes, onsets,
                response_window_s=(0.0, 0.1), response_window=(0.0, 100.0),
            )

    def test_bin_spikes(self):
        with pytest.raises(ValueError, match="Conflicting values"):
            bin_spikes(np.array([0.1]), window_s=(0.0, 1.0), window=(0.0, 1000.0))

    @pytest.mark.parametrize(
        "fn",
        [spike_mutual_information, binary_occupancy_mutual_information,
         spike_count_mutual_information],
    )
    def test_the_mutual_information_family(self, fn):
        s1 = np.array([0.1, 0.3, 0.5])
        s2 = np.array([0.15, 0.35, 0.55])
        with pytest.raises(ValueError, match="Conflicting values"):
            fn(s1, s2, time_window_s=(0.0, 1.0), time_window=(0.0, 1000.0))

    @pytest.mark.parametrize(
        "new,old,a,b",
        [
            ("t0_bounds_ms", "t0_bounds", (0.0, 100.0), (0.0, 0.1)),
            ("tau_bounds_ms", "tau_bounds", (1.0, 150.0), (0.001, 0.15)),
            ("baseline_window_ms", "baseline_window", (-50.0, 0.0), (-0.05, 0.0)),
            ("t0_grid_step_ms", "t0_grid_step", 5.0, 0.005),
        ],
    )
    def test_fit_exponential_onset(self, new, old, a, b):
        t = np.linspace(-50.0, 200.0, 60)
        rate = np.where(t < 20.0, 5.0, 5.0 + 10.0 * (1.0 - np.exp(-(t - 20.0) / 30.0)))
        with pytest.raises(ValueError, match="Conflicting values"):
            fit_exponential_onset(t, rate, **{new: a, old: b})

    def test_agreeing_spellings_are_not_a_conflict(self):
        spikes = np.array([0.201, 0.205, 0.210])
        onsets = np.array([0.2])
        both = compute_response_metrics(
            spikes, onsets,
            baseline_window_s=(-0.2, 0.0), baseline_window=(-0.2, 0.0),
        )
        one = compute_response_metrics(spikes, onsets, baseline_window_s=(-0.2, 0.0))
        _assert_metrics_equal(both, one)


class TestTheRenameChangedNoNumber:
    """The unit did not change; only the name did. Every one of these compares the old
    spelling against the new on the same input.
    """

    def test_compute_response_metrics(self):
        spikes = np.array([0.201, 0.205, 0.210, 0.215, 0.220, 0.05, 0.06])
        onsets = np.array([0.2, 1.2])
        old = compute_response_metrics(
            spikes, onsets, baseline_window=(-0.2, 0.0), response_window=(0.0, 0.1)
        )
        new = compute_response_metrics(
            spikes, onsets, baseline_window_s=(-0.2, 0.0), response_window_s=(0.0, 0.1)
        )
        positional = compute_response_metrics(spikes, onsets, (-0.2, 0.0), (0.0, 0.1))
        _assert_metrics_equal(old, new)
        _assert_metrics_equal(new, positional)

    def test_bin_spikes(self):
        spikes = np.array([0.1, 0.2, 0.45, 0.8])
        np.testing.assert_array_equal(
            bin_spikes(spikes, window=(0.0, 1.0), bin_size_ms=100.0),
            bin_spikes(spikes, window_s=(0.0, 1.0), bin_size_ms=100.0),
        )
        np.testing.assert_array_equal(
            bin_spikes(spikes, (0.0, 1.0), 100.0),
            bin_spikes(spikes, window_s=(0.0, 1.0), bin_size_ms=100.0),
        )

    @pytest.mark.parametrize(
        "fn",
        [spike_mutual_information, binary_occupancy_mutual_information,
         spike_count_mutual_information],
    )
    def test_the_mutual_information_family(self, fn):
        rng = np.random.default_rng(0)
        s1 = np.sort(rng.uniform(0.0, 1.0, 40))
        s2 = np.sort(rng.uniform(0.0, 1.0, 40))
        assert fn(s1, s2, time_window=(0.0, 1.0)) == fn(s1, s2, time_window_s=(0.0, 1.0))
        assert fn(s1, s2, (0.0, 1.0)) == fn(s1, s2, time_window_s=(0.0, 1.0))

    def test_fit_exponential_onset(self):
        t = np.linspace(-50.0, 200.0, 60)
        rate = np.where(t < 20.0, 5.0, 5.0 + 10.0 * (1.0 - np.exp(-(t - 20.0) / 30.0)))
        old = fit_exponential_onset(
            t, rate, t0_bounds=(0.0, 100.0), tau_bounds=(1.0, 150.0),
            baseline_window=(-50.0, 0.0), t0_grid_step=5.0,
        )
        new = fit_exponential_onset(
            t, rate, t0_bounds_ms=(0.0, 100.0), tau_bounds_ms=(1.0, 150.0),
            baseline_window_ms=(-50.0, 0.0), t0_grid_step_ms=5.0,
        )
        assert old == new

    def test_the_defaults_are_unchanged(self):
        t = np.linspace(-50.0, 200.0, 60)
        rate = np.where(t < 20.0, 5.0, 5.0 + 10.0 * (1.0 - np.exp(-(t - 20.0) / 30.0)))
        assert fit_exponential_onset(t, rate) == fit_exponential_onset(
            t, rate, t0_bounds_ms=(0.0, None), tau_bounds_ms=(1.0, 150.0),
            baseline_window_ms=None, t0_grid_step_ms=5.0,
        )


class TestNoUnitLessWindowRemainsInThePublicApi:
    """The acceptance criterion, enforced rather than asserted in prose: no exported
    function takes a float-valued window or bound whose name does not carry a unit.
    """

    WINDOWY = re.compile(r"(window|bounds|grid_step)$")

    # Same name, not a time, so no unit belongs in it. Each is justified by its own
    # annotation or docstring, not waved through:
    #   phase_slope_index.window / vflip_from_lfp.window -- `str`, a taper name ('hann')
    #   XFlipResult.block_bounds -- Tuple[Tuple[int, int], ...], channel index intervals
    #   jrsa.window -- sample indices along the aligned axis; jrsa takes no sampling rate
    NOT_A_TIME = {
        "phase_slope_index.window",
        "vflip_from_lfp.window",
        "XFlipResult.block_bounds",
        "jrsa.window",
    }

    def test_the_exempt_names_really_are_not_times(self):
        """The exemption list is a claim about those parameters, so check the claim."""
        for qualified in ("phase_slope_index.window", "vflip_from_lfp.window"):
            fn, pname = qualified.split(".")
            param = inspect.signature(getattr(jnwb, fn)).parameters[pname]
            # These modules use `from __future__ import annotations`, so the annotation
            # arrives as the string "str" rather than the type.
            assert str(param.annotation) in ("str", "<class 'str'>"), (
                f"{qualified} is no longer a taper name"
            )
            assert param.default == "hann"
        block_bounds = inspect.signature(jnwb.XFlipResult).parameters["block_bounds"]
        assert "int" in str(block_bounds.annotation)
        assert "sample indices" in jnwb.jrsa.__doc__

    def test_sweep(self):
        offenders = []
        for name in sorted(jnwb.__all__):
            obj = getattr(jnwb, name, None)
            if not callable(obj):
                continue
            try:
                sig = inspect.signature(obj)
            except (TypeError, ValueError):
                continue
            for pname, param in sig.parameters.items():
                if not self.WINDOWY.search(pname):
                    continue
                if pname.endswith(("_s", "_ms", "_sec")):
                    continue
                # An alias is allowed to keep the old spelling; it is keyword-only and
                # its unit-bearing twin exists beside it.
                twin = any(
                    f"{pname}_{suffix}" in sig.parameters for suffix in ("s", "ms")
                )
                if twin and param.kind is inspect.Parameter.KEYWORD_ONLY:
                    continue
                if f"{name}.{pname}" in self.NOT_A_TIME:
                    continue
                offenders.append(f"{name}.{pname}")
        assert not offenders, (
            "exported float window/bound parameters with no unit in the name: "
            f"{offenders}"
        )


class TestResolveUnitAliasItself:
    def test_neither_supplied_and_no_default_is_an_error(self):
        with pytest.raises(ValueError, match="requires w_s"):
            resolve_unit_alias(
                None, None, canonical_name="w_s", alias_name="w", func_name="f"
            )

    def test_neither_supplied_falls_back_to_the_default(self):
        assert resolve_unit_alias(
            None, None, canonical_name="w_s", alias_name="w", func_name="f",
            default=(0.0, 1.0),
        ) == (0.0, 1.0)

    def test_a_default_of_none_is_a_real_default_not_a_missing_one(self):
        """`baseline_window_ms=None` means "estimate it", which is not the same condition
        as "you forgot to pass it".
        """
        assert resolve_unit_alias(
            None, None, canonical_name="w_ms", alias_name="w", func_name="f",
            default=None,
        ) is None

    def test_either_one_alone_is_returned(self):
        kw = dict(canonical_name="w_s", alias_name="w", func_name="f")
        assert resolve_unit_alias((1.0, 2.0), None, **kw) == (1.0, 2.0)
        assert resolve_unit_alias(None, (3.0, 4.0), **kw) == (3.0, 4.0)


class TestJrsaWindowIsSamplesAndSaysSo:
    """Found while sweeping for unit-less time parameters, not reported by the audit.

    `jrsa`'s docstring read "Analysis window, e.g. (-500, 500) ms", but `_make_windows`
    slices sample indices and `jrsa` takes no sampling rate, so it cannot convert a time.
    A caller following the docstring got silence in both directions: on a 6-sample aligned
    axis `(-500, 500)` clamped to `(0, 6)` -- the whole axis, the unwindowed answer -- and
    `(10, 30)` clamped to an empty slice and returned a NaN statistic.
    """

    @staticmethod
    def _xy():
        rng = np.random.default_rng(0)
        return rng.normal(size=(40, 6)), rng.normal(size=(40, 6))

    def test_a_window_that_selects_nothing_raises(self):
        x1, x2 = self._xy()
        with pytest.raises(ValueError, match="selects no samples"):
            jnwb.jrsa(x1, x2, metric="cka", permutations=0, window=(10, 30))

    @pytest.mark.parametrize("window", [(-500, 500), (-10, 40), (0, 20)])
    def test_a_window_clamped_to_the_whole_axis_says_so(self, window):
        x1, x2 = self._xy()
        with pytest.warns(RuntimeWarning, match="covers the whole"):
            res = jnwb.jrsa(x1, x2, metric="cka", permutations=0, window=window)
        unwindowed = jnwb.jrsa(x1, x2, metric="cka", permutations=0)
        assert float(res.statistic) == float(unwindowed.statistic)

    def test_a_real_window_still_windows_quietly(self):
        x1, x2 = self._xy()
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            windowed = jnwb.jrsa(x1, x2, metric="cka", permutations=0, window=(0, 3))
            width = jnwb.jrsa(x1, x2, metric="cka", permutations=0, window=4)
        unwindowed = jnwb.jrsa(x1, x2, metric="cka", permutations=0)
        assert float(windowed.statistic) != float(unwindowed.statistic)
        assert float(width.statistic) != float(unwindowed.statistic)

    def test_the_docstring_no_longer_claims_milliseconds(self):
        doc = jnwb.jrsa.__doc__
        assert "sample indices" in doc
        assert "Analysis window, e.g. (-500, 500) ms." not in doc
