"""`zflip` fitted inside `vflip2`'s window, with `vflip2`'s orientation."""

import dataclasses

import numpy as np
import pytest

import jnwb

FS, N_SAMPLES, TAU_S = 1000.0, 4000, 2e-3
N_ROWS = 30
# Relative tolerance on the recovered delay gradient. Over seeds 0 to 19 of `_probe`, the
# windowed fit's largest relative error was 0.034; 0.10 is about three times that, and the
# whole-probe fit on the same probes stayed at 0.50 to 0.54 of the planted value.
RTOL = 0.10


def _psd(inverted=False):
    """A 30-row PSD with alpha/beta power deep (row 22) and gamma power superficial (row 8)."""
    rng = np.random.default_rng(5)
    freqs = np.arange(1.0, 151.0)
    depth = np.arange(float(N_ROWS))[:, None]
    psd = (1.0 / freqs) * (1.0 + 3.0 * np.exp(-((depth - 8.0) ** 2) / 8.0)
                           * np.exp(-((freqs - 80.0) ** 2) / 200.0)
                           + 3.0 * np.exp(-((depth - 22.0) ** 2) / 8.0)
                           * np.exp(-((freqs - 15.0) ** 2) / 20.0))
    psd = psd * rng.lognormal(0.0, 0.05, size=psd.shape)
    return (psd[::-1] if inverted else psd), freqs


@pytest.fixture(scope="module")
def upright():
    res = jnwb.vflip2(*_psd(), contact_spacing=100.0)
    assert res.accepted and res.orientation == "upright", "fixture must be accepted, upright"
    assert (res.proximal_channel, res.distal_channel) == (6, 23)
    return res


@pytest.fixture(scope="module")
def inverted():
    res = jnwb.vflip2(*_psd(inverted=True), contact_spacing=100.0)
    assert res.accepted and res.orientation == "inverted", "fixture must be accepted, inverted"
    return res


def _lag(row, first, last):
    """Delay of `row` in TAU_S: up one per row inside [first, last], down one outside."""
    if row < first:
        return first - row
    if row <= last:
        return row - first
    return (last - first) - (row - last)


def _probe(seed, first=6, last=23, noise=0.1):
    """One broadband signal, delayed by TAU_S more at each row inside the window and by TAU_S
    less at each row outside it, plus independent noise at `noise` SD per contact."""
    rng = np.random.default_rng(seed)
    spectrum = np.fft.rfft(rng.normal(size=N_SAMPLES))
    f = np.fft.rfftfreq(N_SAMPLES, 1.0 / FS)
    rows = [np.fft.irfft(spectrum * np.exp(-2j * np.pi * f * _lag(r, first, last) * TAU_S),
                         n=N_SAMPLES) for r in range(N_ROWS)]
    return np.array(rows) + noise * rng.normal(size=(N_ROWS, N_SAMPLES))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_window_recovers_a_gradient_the_whole_probe_misses(upright, seed):
    data = _probe(seed)
    whole = jnwb.zflip(data, FS, orientation="superficial_to_deep", rng=seed)
    assert not np.isclose(whole.tau_per_channel_s, TAU_S, rtol=RTOL), (
        "precondition: the whole-probe fit must not recover the planted gradient"
    )
    res = jnwb.zflip(data, FS, orientation=upright, window=upright, rng=seed)
    assert res.accepted
    assert res.window == (6, 23) and res.n_channels == 18
    assert res.adjacent_wpli.shape == (17,)
    np.testing.assert_allclose(res.tau_per_channel_s, TAU_S, rtol=RTOL)
    assert res.directionality == "superficial_to_deep"


def test_a_pair_in_either_order_is_the_window_vflip2_names(upright):
    data = _probe(0)
    from_result = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=upright,
                             n_surrogates=20, rng=0)
    reversed_pair = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(23, 6),
                               n_surrogates=20, rng=0)
    sliced = jnwb.zflip(data[6:24], FS, orientation="superficial_to_deep", n_surrogates=20,
                        rng=0)
    for other in (reversed_pair, sliced):
        for name in ("adjacent_wpli", "adjacent_delays_s", "adjacent_linearity_r2"):
            np.testing.assert_array_equal(getattr(from_result, name), getattr(other, name))
        assert from_result.p_value == other.p_value
        assert from_result.tau_per_channel_s == other.tau_per_channel_s
    assert np.isfinite(from_result.tau_per_channel_s), "the window must fit a gradient"
    assert reversed_pair.window == (6, 23) and sliced.window is None


def test_the_whole_probe_as_a_window_changes_no_number():
    data = _probe(0)
    default = jnwb.zflip(data, FS, orientation="superficial_to_deep", n_surrogates=20, rng=0)
    full = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(0, N_ROWS - 1),
                      n_surrogates=20, rng=0)
    d, f = default.to_dict(), full.to_dict()
    assert d.pop("window") is None and f.pop("window") == (0, N_ROWS - 1)
    for key in d:
        np.testing.assert_array_equal(d[key], f[key], err_msg=key)


def test_rejection_reasons_name_probe_rows():
    data = _probe(0)
    data[10] = 0.0
    res = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(6, 23),
                     n_surrogates=20, rng=0)
    assert "Contact(s) [10] constant" in res.rejection_reason
    assert np.isnan(res.adjacent_wpli[[3, 4]]).all()  # probe pairs (9, 10) and (10, 11)
    assert np.isfinite(np.delete(res.adjacent_wpli, [3, 4])).all()


def _window_pairs(first=6, last=23):
    return str([(r, r + 1) for r in range(first, last)])


def test_a_ramp_contact_is_named_by_its_probe_row():
    data = _probe(0)
    data[10] = np.linspace(-1.0, 1.0, N_SAMPLES)
    res = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(6, 23),
                     n_surrogates=0)
    assert "Contact(s) [10] linear in time to round-off" in res.rejection_reason


def test_an_out_of_band_contact_is_named_by_its_probe_row():
    data = _probe(0)
    data[10] = np.sin(2 * np.pi * 60.0 * np.arange(N_SAMPLES) / FS)
    res = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(6, 23),
                     n_surrogates=0)
    assert "Contact(s) [10] carry less than" in res.rejection_reason


def test_weak_pairs_are_named_by_their_probe_rows():
    # Every pair's wPLI is below 1.0, so min_wpli=1.0 lists every pair of the window as weak.
    res = jnwb.zflip(_probe(0), FS, orientation="superficial_to_deep", window=(6, 23),
                     min_wpli=1.0, n_surrogates=0)
    assert f"Adjacent pair(s) {_window_pairs()} wPLI below min_wpli" in res.rejection_reason


def test_pairs_without_a_significant_null_are_named_by_their_probe_rows():
    # With 10 surrogates the smallest pair p is 1/11 > alpha, so no pair is significant.
    res = jnwb.zflip(_probe(0), FS, orientation="superficial_to_deep", window=(6, 23),
                     n_surrogates=10, rng=0)
    assert np.all(res.adjacent_wpli >= 0.15), "pairs must be coupled, so only the null fails"
    assert (f"Adjacent pair(s) {_window_pairs()} wPLI not significant"
            in res.rejection_reason)


def test_rows_outside_the_window_need_not_be_finite():
    data = _probe(0)
    data[0, 5] = np.nan
    with pytest.raises(ValueError, match="finite input"):
        jnwb.zflip(data, FS, orientation="superficial_to_deep", n_surrogates=0)
    res = jnwb.zflip(data, FS, orientation="superficial_to_deep", window=(6, 23),
                     n_surrogates=0)
    assert res.window == (6, 23)


@pytest.mark.parametrize("name, expected", [("upright", "superficial_to_deep"),
                                            ("inverted", "deep_to_superficial")])
def test_an_accepted_vflip2_orientation_is_the_named_row_order(request, name, expected):
    v2 = request.getfixturevalue(name)
    data = _probe(0)
    from_v2 = jnwb.zflip(data, FS, orientation=v2, window=(6, 23), n_surrogates=20, rng=0)
    named = jnwb.zflip(data, FS, orientation=expected, window=(6, 23), n_surrogates=20, rng=0)
    assert from_v2.orientation == expected
    assert from_v2.directionality == named.directionality != "unidentifiable"
    assert from_v2.tau_per_channel_s == named.tau_per_channel_s


@pytest.mark.parametrize("argument", ["orientation", "window"])
def test_a_rejected_vflip2_result_is_refused(argument):
    rejected = jnwb.vflip2(*_psd(), contact_spacing=100.0, omega_cut=20.0)
    assert not rejected.accepted and rejected.proximal_channel is not None, (
        "fixture must be a rejected result that still names a window"
    )
    kwargs = {"orientation": "superficial_to_deep", argument: rejected}
    with pytest.raises(ValueError, match="rejected vflip2 result as " + argument):
        jnwb.zflip(_probe(0), FS, n_surrogates=0, **kwargs)


@pytest.mark.parametrize("argument", ["orientation", "window"])
def test_a_vflip2_result_without_a_window_is_refused(upright, argument):
    no_window = dataclasses.replace(upright, proximal_channel=None, distal_channel=None)
    kwargs = {"orientation": "superficial_to_deep", argument: no_window}
    with pytest.raises(ValueError, match="no window as " + argument):
        jnwb.zflip(_probe(0), FS, n_surrogates=0, **kwargs)


@pytest.mark.parametrize("window, match", [
    ((-1, 10), "outside the probe"),
    ((5, N_ROWS), "outside the probe"),
    ((4, 5), "hold 2 contact"),
    ((7, 7), "hold 1 contact"),
    ((1.0, 5), "integer probe rows"),
    ((True, 5), "integer probe rows"),
    ((1, 2, 3), "integer probe rows"),
    (5, "integer probe rows"),
], ids=["negative", "past-the-end", "two-rows", "one-row", "float", "bool", "triple", "scalar"])
def test_a_bad_window_is_refused(window, match):
    with pytest.raises(ValueError, match=match):
        jnwb.zflip(_probe(0), FS, orientation="superficial_to_deep", window=window,
                   n_surrogates=0)


def _window_fields(result):
    return (result.proximal_channel, result.distal_channel, result.orientation)


@pytest.mark.parametrize("change", [{"distal_channel": 22}, {"proximal_channel": 7},
                                    {"orientation": "inverted"}],
                         ids=["distal", "proximal", "orientation"])
def test_window_and_orientation_from_different_vflip2_results_are_refused(upright, change):
    other = dataclasses.replace(upright, **change)
    assert other.accepted and _window_fields(other) != _window_fields(upright), (
        "fixture must be a different accepted result"
    )
    with pytest.raises(ValueError, match="different vflip2 results") as err:
        jnwb.zflip(_probe(0), FS, orientation=other, window=upright, n_surrogates=0)
    assert f"({upright.proximal_channel}, {upright.distal_channel}" in str(err.value)
    assert f"({other.proximal_channel}, {other.distal_channel}" in str(err.value)


def test_the_same_or_an_equal_vflip2_result_is_accepted(upright):
    copy = dataclasses.replace(upright)
    assert copy is not upright and _window_fields(copy) == _window_fields(upright), (
        "fixture must be an equal, distinct result"
    )
    for orientation in (upright, copy):
        res = jnwb.zflip(_probe(0), FS, orientation=orientation, window=upright, n_surrogates=0)
        assert res.window == (6, 23) and res.orientation == "superficial_to_deep"
