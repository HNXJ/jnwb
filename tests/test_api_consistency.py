"""Siblings that answer the same question differently.

Each of these is a pair of functions a user reaches in one workflow, where one validates
and the other does not, or where the two disagree on a default. The defect is the
divergence, so the tests are written as parametrized sweeps over the siblings rather than
as one test per function.

Each test fails when its repair is reverted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

import jnwb
from jnwb.addressing import probe_geometry
from jnwb.nwb_events import resolve_interval_table
from jnwb.nwb_inspect import resolve_acquisition
from jnwb.spectral import (
    band_power,
    cross_area_coherence,
    harmonic_analysis,
    imaginary_coherency,
    spectral_tilt,
    wpli,
)
from jnwb.statistics import (
    StatisticalAnalysis,
    clopper_pearson,
    shuffle_pvalue_paired,
    shuffle_pvalue_unpaired,
)


def _write_nwb_with_trials(path):
    import pynwb

    nwb = pynwb.NWBFile(
        session_description="s", identifier="i",
        session_start_time=datetime.now(timezone.utc),
    )
    nwb.add_trial_column(name="stimulus", description="code")
    for i in range(3):
        nwb.add_trial(start_time=float(i), stop_time=float(i) + 0.5, stimulus="grating")
    with pynwb.NWBHDF5IO(str(path), "w") as io:
        io.write(nwb)
    return path


class TestResolversTakeTheSameInput:
    """`resolve_interval_table` was the only exported NWB function requiring an
    already-open `NWBFile`, with `table` required positionally. A path gave
    `AttributeError: 'str' object has no attribute 'intervals'`, against its exact
    sibling `resolve_acquisition(path_or_nwb, name=None)`.
    """

    def test_a_path_resolves(self, tmp_path):
        path = _write_nwb_with_trials(tmp_path / "t.nwb")
        assert resolve_interval_table(path) == "trials"
        assert resolve_interval_table(str(path)) == "trials"

    def test_table_is_optional_like_resolve_acquisition_s_name(self):
        import inspect

        for fn in (resolve_interval_table, resolve_acquisition):
            second = list(inspect.signature(fn).parameters.values())[1]
            assert second.default is None, f"{fn.__name__}: {second.name} must be optional"

    def test_an_open_handle_still_resolves(self, tmp_path):
        import pynwb

        path = _write_nwb_with_trials(tmp_path / "t.nwb")
        with pynwb.NWBHDF5IO(str(path), "r") as io:
            nwb = io.read()
            assert resolve_interval_table(nwb) == "trials"
            assert resolve_interval_table(nwb, "trials") == "trials"

    @pytest.mark.parametrize("name", ["trials", "intervals/trials", "/intervals/trials"])
    def test_every_accepted_name_form_survives(self, tmp_path, name):
        path = _write_nwb_with_trials(tmp_path / "t.nwb")
        assert resolve_interval_table(path, name) == "trials"

    def test_a_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            resolve_interval_table(tmp_path / "absent.nwb")

    @pytest.mark.parametrize("bad", [12345, None, 3.5, ["trials"]])
    def test_a_wrong_type_names_both_accepted_types(self, bad):
        with pytest.raises(TypeError, match="path .* or an open"):
            resolve_interval_table(bad)


class TestExceptionBasesAreReachable:
    """`NWBEventError` had four exported subclasses and was not in `__all__`;
    `MissingRequiredNWBFieldError` is documented at `docs/01:50` and was neither based nor
    exported; `ChannelIndexError` inherited `IndexError` while its three siblings
    inherited `Exception`, so no one `except` caught the family.
    """

    @pytest.mark.parametrize(
        "name", ["NWBEventError", "MissingRequiredNWBFieldError", "NWBInspectError"]
    )
    def test_the_base_is_importable_from_the_top_level(self, name):
        assert hasattr(jnwb, name)
        assert name in jnwb.__all__

    @pytest.mark.parametrize(
        "subclass",
        ["AmbiguousIntervalTableError", "IntervalTableNotFoundError",
         "ColumnNotFoundError", "InvalidOnsetValueError"],
    )
    def test_one_except_clause_catches_every_event_error(self, subclass):
        assert issubclass(getattr(jnwb, subclass), jnwb.NWBEventError)

    @pytest.mark.parametrize(
        "subclass",
        ["AmbiguousAcquisitionError", "AcquisitionNotFoundError",
         "ChannelIndexError", "UnitNotFoundError"],
    )
    def test_one_except_clause_catches_every_inspect_error(self, subclass):
        assert issubclass(getattr(jnwb, subclass), jnwb.NWBInspectError)

    def test_channel_index_error_is_still_an_index_error(self):
        """Its existing identity is preserved, so `except IndexError` keeps working."""
        assert issubclass(jnwb.ChannelIndexError, IndexError)

    def test_probe_geometry_raises_a_typed_error_not_a_bare_assert(self):
        """`assert coords is not None` with no message raised `AssertionError('')` -- and
        vanished under `python -O`, after which the next line ran `.shape` on None.
        """
        with pytest.raises(TypeError, match="expected an NWB electrodes table"):
            probe_geometry("x.nwb")


class TestAlternativeAndAlpha:
    """An `if/elif/else` whose fallthrough was two-sided."""

    @staticmethod
    def _ab():
        rng = np.random.default_rng(0)
        return rng.normal(0.8, 1.0, 30), rng.normal(0.0, 1.0, 30)

    SIBLINGS = (shuffle_pvalue_paired, shuffle_pvalue_unpaired)

    @pytest.mark.parametrize("fn", SIBLINGS)
    @pytest.mark.parametrize("bad", ["nonsense", "two_sided", "", "greater ?", "up"])
    def test_an_unknown_tail_raises_instead_of_selecting_two_sided(self, fn, bad):
        a, b = self._ab()
        with pytest.raises(ValueError, match="alternative must be one of"):
            fn(a, b, n_shuffles=99, rng=np.random.default_rng(1), alternative=bad)

    @pytest.mark.parametrize("fn", SIBLINGS)
    def test_case_and_whitespace_are_folded_not_ignored(self, fn):
        """`alternative='GREATER'` used to fall through to two-sided: p = 0.163 where the
        one-sided value is 0.093.
        """
        a, b = self._ab()
        loud = fn(a, b, n_shuffles=999, rng=np.random.default_rng(1), alternative="GREATER")
        plain = fn(a, b, n_shuffles=999, rng=np.random.default_rng(1), alternative="greater")
        padded = fn(a, b, n_shuffles=999, rng=np.random.default_rng(1), alternative=" Greater ")
        assert loud == plain == padded
        two = fn(a, b, n_shuffles=999, rng=np.random.default_rng(1), alternative="two-sided")
        assert plain[1] != two[1], "the folded value must not be the two-sided one"

    @pytest.mark.parametrize("fn", SIBLINGS)
    def test_both_siblings_default_to_two_sided(self, fn):
        a, b = self._ab()
        assert fn(a, b, n_shuffles=999, rng=np.random.default_rng(1)) == fn(
            a, b, n_shuffles=999, rng=np.random.default_rng(1), alternative="two-sided"
        )

    @pytest.mark.parametrize("alpha", [2.0, -1.0, 0.0, 1.0, float("nan")])
    def test_confirmatory_compare_validates_alpha_like_clopper_pearson(self, alpha):
        """`alpha=2.0` returned `confirmed_parametric=True` for q = 0.1188 -- a
        confirmation at an impossible significance level, from the confirmatory API.
        """
        a, b = self._ab()
        with pytest.raises(ValueError, match="alpha"):
            StatisticalAnalysis.confirmatory_compare(a, b, hypothesis="a > b", alpha=alpha)
        with pytest.raises(ValueError, match="alpha"):
            clopper_pearson(5, 10, alpha=alpha)

    def test_a_valid_alpha_still_runs(self):
        a, b = self._ab()
        res = StatisticalAnalysis.confirmatory_compare(a, b, hypothesis="a > b", alpha=0.05)
        assert res["alpha"] == 0.05
        assert isinstance(res["confirmed_parametric"], (bool, np.bool_))


class TestSpectralSurfaceValidatesIdentically:
    """`_resolve_fs` never checked positivity, so each caller failed in its own way
    further down -- or not at all -- and `imaginary_coherency` ravelled 2-D input that
    `cross_area_coherence` refuses.
    """

    @staticmethod
    def _xy():
        rng = np.random.default_rng(0)
        return rng.normal(size=2000), rng.normal(size=2000)

    ONE_TRACE = (
        ("band_power", lambda x, y, fs: band_power(x, fs=fs, normalize=False)),
        ("spectral_tilt", lambda x, y, fs: spectral_tilt(x, fs=fs)),
        ("harmonic_analysis", lambda x, y, fs: harmonic_analysis(x, fs=fs)),
    )
    TWO_TRACE = (
        ("wpli", lambda x, y, fs: wpli(x, y, fs=fs)),
        ("imaginary_coherency", lambda x, y, fs: imaginary_coherency(x, y, fs=fs)),
        (
            "cross_area_coherence",
            lambda x, y, fs: cross_area_coherence(
                x, y, fs=fs, freq_bands={"beta": (14.0, 30.0)}
            ),
        ),
    )

    @pytest.mark.parametrize("name,call", ONE_TRACE + TWO_TRACE, ids=lambda v: v if isinstance(v, str) else "")
    @pytest.mark.parametrize("bad_fs", [0.0, -1000.0, float("nan"), float("inf")])
    def test_every_entry_point_refuses_the_same_bad_fs(self, name, call, bad_fs):
        """`wpli(x, y, fs=0.0)` raised ZeroDivisionError and `fs=-1000.0` described a
        frequency grid running "0 to -500 Hz in steps of -3.90625 Hz".
        """
        x, y = self._xy()
        with pytest.raises(ValueError, match="fs must be finite and strictly positive"):
            call(x, y, bad_fs)

    @pytest.mark.parametrize("name,call", TWO_TRACE, ids=lambda v: v if isinstance(v, str) else "")
    def test_every_two_trace_entry_point_refuses_2d_input(self, name, call):
        """`.ravel()` joined the channels end to end and estimated across the join:
        `imaginary_coherency(np.stack([x, y]), np.stack([y, x]), fs=1000.)` returned a
        complete result for a discontinuity that is not in the data.
        """
        x, y = self._xy()
        with pytest.raises(ValueError, match="1-D time series"):
            call(np.stack([x, y]), np.stack([y, x]), 1000.0)

    @pytest.mark.parametrize("name,call", ONE_TRACE + TWO_TRACE, ids=lambda v: v if isinstance(v, str) else "")
    def test_a_good_call_still_works(self, name, call):
        x, y = self._xy()
        assert call(x, y, 1000.0) is not None

    def test_the_sampling_rate_alias_is_validated_too(self):
        x, _ = self._xy()
        with pytest.raises(ValueError, match="fs must be finite and strictly positive"):
            band_power(x, sampling_rate=-1.0, normalize=False)
        with pytest.raises(ValueError, match="Conflicting values"):
            band_power(x, fs=1000.0, sampling_rate=500.0, normalize=False)
