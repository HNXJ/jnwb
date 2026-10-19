"""``effective_sample_size``: the initial positive sequence count, on the cases its rule fixes.

White noise keeps its length, and an AR(1) of coefficient phi keeps n (1 - phi) / (1 + phi). A
channel that is constant only up to round-off is skipped, not averaged in. Each refusal is a
ValueError that names the function and the argument.
"""

from __future__ import annotations

import numpy as np
import pytest

from jnwb.statistics import effective_sample_size


def _ar1(n: int, phi: float, seed: int, n_channels: int = 1) -> np.ndarray:
    noise = np.random.default_rng(seed).standard_normal((n_channels, n))
    x = np.empty((n_channels, n))
    x[:, 0] = noise[:, 0]
    for t in range(1, n):
        x[:, t] = phi * x[:, t - 1] + noise[:, t]
    return x[0] if n_channels == 1 else x


def _lag1(x: np.ndarray) -> float:
    d = x - x.mean()
    return float(np.sum(d[:-1] * d[1:]) / np.sum(d * d))


def test_white_noise_keeps_its_length():
    x = np.random.default_rng(0).standard_normal(4000)
    assert abs(_lag1(x)) < 0.05, "fixture must be white: its lag-1 autocorrelation"
    assert effective_sample_size(x) == pytest.approx(4000, rel=0.10)


def test_ar1_keeps_the_closed_form_count():
    """Eight channels, because the count is estimated from the channel mean: one channel of
    4000 samples falls within 15% for 64 of seeds 0 to 99, eight channels for 98."""
    phi = 0.9
    x = _ar1(4000, phi, seed=1, n_channels=8)
    assert min(_lag1(c) for c in x) > 0.8, "fixture must be strongly autocorrelated"
    assert effective_sample_size(x) == pytest.approx(4000 * (1 - phi) / (1 + phi), rel=0.15)


def test_one_channel_as_1d_and_2d_agree():
    x = _ar1(1000, 0.5, seed=2)
    np.testing.assert_allclose(effective_sample_size(x), effective_sample_size(x[None, :]),
                               rtol=1e-12)


def test_a_constant_channel_is_skipped_not_averaged_in():
    constant = np.full(1000, 0.3)
    assert np.any(constant - constant.mean() != 0), "fixture must carry round-off, or it tests nothing"
    x = _ar1(1000, 0.5, seed=3)
    np.testing.assert_allclose(effective_sample_size(np.vstack([constant, x])),
                               effective_sample_size(x), rtol=1e-12)


def test_a_negative_first_lag_leaves_the_count_at_n():
    """The sum stops at the first lag whose mean is not positive. Lag 2 is positive here, so a
    sum that ran past lag 1 would pull the count far below n."""
    x = np.tile([1.0, -1.0], 50)
    assert _lag1(x) < 0, "fixture must have a negative first lag"
    assert effective_sample_size(x) == 100.0


@pytest.mark.parametrize("value, pattern", [
    (np.array([1.0, np.nan, 2.0, 3.0]), r"1 non-finite value"),
    (np.array([1.0, np.inf, 2.0, 3.0]), r"1 non-finite value"),
    (np.array([1.0]), r"at least 2 samples per channel, got 1"),
    (np.full((2, 50), 0.3), r"every channel is constant"),
    (np.zeros((2, 3, 4)), r"1-D .* or 2-D"),
])
def test_a_refusal_names_the_function_and_the_argument(value, pattern):
    with pytest.raises(ValueError, match=rf"^effective_sample_size: x .*{pattern}"):
        effective_sample_size(value)
