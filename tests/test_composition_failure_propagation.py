"""A failure in an intermediate must reach the caller, not become a number (06-22).

Two chains from the declared high-risk composition subset:

* **H7** -- ``epoch_continuous(boundary_policy="nan")`` into ``band_power``,
  ``compute_psd``, ``complex_tfr``, ``bandpass_filter``, ``spectral_tilt`` and
  ``gaussian_smooth_rate``. An epoch truncated by the end of the recording carries NaN
  by construction. Five of the six consumers refuse it; ``gaussian_smooth_rate``
  accepts it and spreads the NaN across the smoothing kernel without telling anyone.
* **H1's refusal leg** -- ``label_layers`` given a ``VFlipResult`` computed without
  ``probe_geometry`` reads a PSD-row index as a shaft rank (P-49). The mislabelling
  that follows is measured elsewhere; what is asserted here is only that the boundary
  must refuse.

Every refusal assertion below is paired with a control that runs the *same consumer*
with the *same arguments* on the untruncated epoch from the *same*
``epoch_continuous`` call. Without that control, ``pytest.raises(ValueError)`` is
satisfied by any unrelated rejection -- a too-short window, a bad frequency bound, a
missing baseline -- and would certify a consumer that had stopped looking at NaN
entirely. One such trap is live and is documented on ``band_power`` below.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

import jnwb
from jnwb import (
    aggregate_to_db,
    band_power,
    bandpass_filter,
    complex_tfr,
    compute_psd,
    epoch_continuous,
    gaussian_smooth_rate,
    label_layers,
    spectral_tilt,
    vflip_from_lfp,
)

LFP_FS = 1000.0
RATE_FS = 100.0
BIN_MS = 1000.0 / RATE_FS
SIGMA_MS = 20.0

#: The six consumers H7 names. ``gaussian_smooth_rate`` is the one that accepts a
#: boundary NaN; the other five refuse. Both halves are pinned, so a consumer that
#: stops refusing is as visible as one that starts.
H7_CONSUMERS = frozenset(
    {
        "band_power",
        "compute_psd",
        "complex_tfr",
        "bandpass_filter",
        "spectral_tilt",
        "gaussian_smooth_rate",
    }
)

#: Each refusing consumer with the call that reaches it and the text it refuses with.
#: The messages are pinned individually because they are **not** one shared sentence:
#: ``band_power``, ``compute_psd`` and ``spectral_tilt`` share the "must be finite;
#: remove or repair NaN or Inf samples first" wording, while ``complex_tfr`` and
#: ``bandpass_filter`` each have their own. Matching a single common substring would
#: have silently excused two of the five.
REFUSING_CONSUMERS = {
    # normalize=False is load-bearing, not incidental. Under the default
    # normalize=True and no baseline, band_power raises
    # "requires a non-empty baseline trace for dB normalization" on *finite* input
    # too -- so the natural spelling of this test would pass with the NaN check
    # deleted. That is the proxy this parameter removes.
    "band_power": (
        lambda a: band_power(a, fs=LFP_FS, normalize=False),
        r"band_power: lfp_trace must be finite; remove or repair NaN or Inf samples first",
    ),
    "compute_psd": (
        lambda a: compute_psd(a, fs=LFP_FS),
        r"compute_psd: lfp_data must be finite; remove or repair NaN or Inf samples first",
    ),
    "complex_tfr": (
        lambda a: complex_tfr(a, LFP_FS, np.array([10.0, 20.0])),
        r"data contains NaN or Inf values",
    ),
    "bandpass_filter": (
        lambda a: bandpass_filter(a, LFP_FS, 5.0, 50.0),
        r"Cannot filter data containing NaN values\. "
        r"Repair or omit missing values prior to filtering",
    ),
    "spectral_tilt": (
        lambda a: spectral_tilt(a, fs=LFP_FS),
        r"spectral_tilt: lfp_trace must be finite; remove or repair NaN or Inf samples first",
    ),
}


def _lfp_epochs() -> tuple[np.ndarray, np.ndarray]:
    """One interior epoch and one truncated by the end of the record, from one call.

    5000 samples at 1 kHz; the second onset at 4.9 s with a window of (-0.2, 0.3) s
    puts the last 200 of its 500 samples past the end of the recording.
    """
    data = np.random.default_rng(1).standard_normal(5000)
    epochs, _ = epoch_continuous(
        data, [1.0, 4.9], win_s=(-0.2, 0.3), fs=LFP_FS, boundary_policy="nan"
    )
    interior, truncated = epochs[0], epochs[1]
    # The fixture must build the case it is named after.
    assert interior.shape == truncated.shape == (500,)
    assert np.isnan(truncated).sum() == 200, "the second window must overhang the record"
    assert not np.isnan(interior).any(), "the first window must lie inside the record"
    return interior, truncated


def _rate_epochs() -> tuple[np.ndarray, np.ndarray]:
    """A 60-bin rate epoch overhanging the record by exactly one bin.

    300 bins at 100 Hz (10 ms bins); the onset at 2.71 s with a window of
    (-0.3, 0.3) s spans samples [241, 301) and so carries exactly one NaN.
    """
    series = np.ones(300, dtype=float)
    epochs, _ = epoch_continuous(
        series, [1.0, 2.71], win_s=(-0.3, 0.3), fs=RATE_FS, boundary_policy="nan"
    )
    interior, truncated = epochs[0], epochs[1]
    assert interior.shape == truncated.shape == (60,)
    assert np.isnan(truncated).sum() == 1, "exactly one bin must overhang"
    assert np.flatnonzero(np.isnan(truncated)).tolist() == [59]
    assert not np.isnan(interior).any()
    return interior, truncated


# --------------------------------------------------------------------------------------
# H7: the five consumers that refuse a boundary NaN
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("consumer", sorted(REFUSING_CONSUMERS))
def test_spectral_consumers_refuse_an_epoch_truncated_by_the_record_end(consumer: str) -> None:
    """The truncated epoch is refused by name; the interior epoch from the same call is not.

    The control is the whole discriminator. Asserting only that a ``ValueError``
    arrives would pass for a consumer that rejected the array's length, its dtype or
    its sampling rate -- none of which is the invariant. Running the identical call on
    the interior epoch, which differs from the truncated one *only* in carrying no
    boundary NaN, leaves the NaN as the sole available cause of the refusal.
    """
    call, message = REFUSING_CONSUMERS[consumer]
    interior, truncated = _lfp_epochs()

    accepted = call(interior)
    assert accepted is not None, f"{consumer} must accept an untruncated epoch"

    with pytest.raises(ValueError, match=message):
        call(truncated)


def test_every_consumer_h7_names_is_covered_here() -> None:
    """A roster that can lose a row silently is a roster that stops covering the chain.

    Five of six refusing is as much the finding as the sixth accepting, so the split
    is asserted rather than left implicit in which tests happen to exist.
    """
    covered = set(REFUSING_CONSUMERS) | {"gaussian_smooth_rate"}
    assert covered == set(H7_CONSUMERS)
    assert len(REFUSING_CONSUMERS) == 5
    assert "gaussian_smooth_rate" not in REFUSING_CONSUMERS


# --------------------------------------------------------------------------------------
# H7: the sixth consumer, which accepts it
# --------------------------------------------------------------------------------------


def test_gaussian_smooth_rate_spreads_a_boundary_nan_and_now_says_so() -> None:
    """One NaN bin in, nine out -- and the caller is told.

    The magnitude is the durable half of this test and is unchanged by the repair: the
    widening is bounded by the kernel radius -- ``sigma_bins = 2`` and
    ``gaussian_filter1d``'s default ``truncate=4.0`` give a radius of 8 -- so a boundary
    NaN, which sits at an epoch edge by construction, contaminates 8 further bins on its
    one available side.

    This test previously asserted that the contamination was *silent*, recording the
    measurement rather than the repair. P-112 is repaired, so that clause is inverted
    rather than deleted: the number of contaminated bins and the fact that the caller
    hears about them are both pinned, and the warning must carry the measured count so a
    warning that merely fires is not mistaken for one that reports.
    """
    interior, truncated = _rate_epochs()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        smoothed = gaussian_smooth_rate(truncated, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)

    assert np.isnan(truncated).sum() == 1
    assert np.isnan(smoothed).sum() == 9, "kernel radius 8, one-sided at the epoch edge"
    messages = [str(w.message) for w in caught]
    assert len(messages) == 1, messages
    assert "spread to 9" in messages[0], messages[0]

    # Control: the same call on the interior epoch stays finite, so the NaN in the
    # output came from the boundary and not from the smoothing itself -- and it warns
    # nothing, so the new warning is not unconditional.
    with warnings.catch_warnings(record=True) as clean_caught:
        warnings.simplefilter("always")
        assert np.isfinite(
            gaussian_smooth_rate(interior, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
        ).all()
    assert [str(w.message) for w in clean_caught] == []


def test_an_interior_nan_bin_widens_into_seventeen() -> None:
    """The subset's recorded figure, and the geometry it requires.

    H7 records "widens one NaN bin into 17" on a 60-bin trace at sigma=20 ms. That
    holds for a NaN in the *interior*, where the kernel reaches 8 bins each side. A
    boundary NaN produced by ``epoch_continuous`` is at an epoch edge, where the same
    call widens one bin into 9. Both numbers are pinned so neither can drift into the
    other.
    """
    interior_nan = np.ones(60, dtype=float)
    interior_nan[30] = np.nan
    assert np.isnan(gaussian_smooth_rate(interior_nan, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)).sum() == 17

    edge_nan = np.ones(60, dtype=float)
    edge_nan[59] = np.nan
    assert np.isnan(gaussian_smooth_rate(edge_nan, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)).sum() == 9


def test_gaussian_smooth_rate_tells_the_caller_it_lost_support() -> None:
    """The invariant: the caller is told, one way or the other.

    Which way was a repair decision and is not presumed here -- refusing the trace and
    reporting the lost support are both acceptable, and this asserts the disjunction. The
    repair chose reporting, so that callers knowingly smoothing a padded epoch are not
    broken. The strict xfail this carried is removed; the control that makes the fixture
    meaningful still lives in
    ``test_gaussian_smooth_rate_spreads_a_boundary_nan_and_now_says_so``, deliberately
    outside this test, because a strict xfail whose own setup breaks still reports xfail
    and a control placed in here could have masked the failure it existed to detect.
    """
    _, truncated = _rate_epochs()

    refused = False
    warned = False
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            gaussian_smooth_rate(truncated, bin_ms=BIN_MS, sigma_ms=SIGMA_MS)
        warned = len(caught) > 0
    except ValueError:
        refused = True

    assert refused or warned, (
        "gaussian_smooth_rate widened one boundary NaN across the kernel and returned "
        "an array with no indication that any support was lost"
    )


# --------------------------------------------------------------------------------------
# H7: the aggregation at the end of the chain must not absorb the failure
# --------------------------------------------------------------------------------------


def test_aggregate_to_db_propagates_a_missing_epoch_rather_than_averaging_around_it() -> None:
    """A refused epoch leaves a hole; the default must return NaN, not a plausible number.

    ``band_power`` refuses the truncated epoch, so the caller aggregating per-epoch
    powers holds a NaN in that slot. Under the default ``nan_policy="propagate"`` the
    result must be NaN.

    Asserting only ``isnan`` would pass on a wholly degenerate computation -- an
    all-NaN stack, a broken baseline, a raised-and-swallowed error. Two controls
    remove that: ``nan_policy="omit"`` must return a finite value, and it must equal
    the value obtained from the same stack with no hole in it, which shows the NaN is
    the missing epoch and nothing else.
    """
    interior, truncated = _lfp_epochs()
    with pytest.raises(ValueError, match="must be finite"):
        band_power(truncated, fs=LFP_FS, normalize=False)

    power = band_power(interior, fs=LFP_FS, normalize=False)
    assert np.isfinite(power) and power > 0.0
    baseline = np.full(3, power / 2.0)

    with_hole = np.array([power, power, np.nan])
    without_hole = np.array([power, power, power])

    propagated = aggregate_to_db(with_hole, baseline, how="mean_of_ratios", aggregate_over=0)
    assert np.isnan(propagated), "the default must not average around a missing epoch"

    omitted = aggregate_to_db(
        with_hole, baseline, how="mean_of_ratios", aggregate_over=0, nan_policy="omit"
    )
    intact = aggregate_to_db(without_hole, baseline, how="mean_of_ratios", aggregate_over=0)
    assert np.isfinite(omitted)
    assert omitted == pytest.approx(intact)
    assert intact == pytest.approx(10.0 * np.log10(2.0))


# --------------------------------------------------------------------------------------
# H1's refusal leg
# --------------------------------------------------------------------------------------

_N_CONTACTS = 24
_PITCH_UM = 50.0
#: Two-bank probe: electrode-table rows 0, 2, 4, ... occupy the upper half of the shaft
#: and rows 1, 3, 5, ... the lower half, so row order is not monotone in depth and the
#: two index spaces cannot coincide by accident.
_SHAFT_RANK_OF_ROW = np.concatenate(
    [np.arange(0, _N_CONTACTS, 2), np.arange(1, _N_CONTACTS, 2)]
)

#: The one refusal ``label_layers`` already performs at this boundary. A repair that
#: raised this instead would be refusing for a reason that does not hold here -- the
#: counts match -- so it is named and excluded rather than left to pass as a refusal.
_CHANNEL_COUNT_REFUSAL = "does not match"


def _two_bank_probe() -> tuple[np.ndarray, object]:
    """LFP in electrode-table row order, and the geometry describing that probe."""
    rng = np.random.default_rng(42)
    n_times = 4000
    t = np.arange(n_times) / LFP_FS
    by_rank = np.zeros((_N_CONTACTS, n_times))
    for rank in range(_N_CONTACTS):
        gamma_weight = max(0.0, 1.0 - abs(rank - 5.0) / 7.0)
        beta_weight = max(0.0, 1.0 - abs(rank - 18.0) / 7.0)
        by_rank[rank] = (
            rng.standard_normal(n_times)
            + gamma_weight * 2.0 * np.sin(2 * np.pi * 70.0 * t + rng.uniform(0, 2 * np.pi))
            + beta_weight * 2.5 * np.sin(2 * np.pi * 18.0 * t + rng.uniform(0, 2 * np.pi))
        )

    by_row = np.empty_like(by_rank)
    for row, rank in enumerate(_SHAFT_RANK_OF_ROW):
        by_row[row] = by_rank[rank]

    electrodes = pd.DataFrame(
        {
            "x": np.zeros(_N_CONTACTS),
            "y": np.zeros(_N_CONTACTS),
            "z": _SHAFT_RANK_OF_ROW * _PITCH_UM,
            "channel_id": [f"ch_{i}" for i in range(_N_CONTACTS)],
        }
    )
    geometry = jnwb.probe_geometry(electrodes, units="um", nominal_pitch=_PITCH_UM)
    assert geometry.is_linear
    return by_row, geometry


def test_the_two_index_spaces_actually_diverge_on_this_probe() -> None:
    """Fixture soundness for the refusal leg, kept out of the xfail that depends on it.

    A refusal test on a probe where supplying geometry changes nothing would assert a
    refusal nobody needs. This pins that the two routes genuinely disagree about what
    ``crossover_contact`` indexes, and that ``label_layers`` currently accepts the
    geometry-omitted result -- which is the behaviour the next test requires to change.

    The size of the resulting mislabelling belongs to 06-20 and is not asserted here.
    """
    lfp, geometry = _two_bank_probe()

    with_geometry = vflip_from_lfp(lfp, fs=LFP_FS, probe_geometry=geometry, min_support_score=0.0)
    without_geometry = vflip_from_lfp(lfp, fs=LFP_FS, min_support_score=0.0)
    assert with_geometry.accepted and without_geometry.accepted
    assert with_geometry.crossover_contact != pytest.approx(
        without_geometry.crossover_contact
    ), "the fixture must place the two index spaces apart"

    # The result now records which space its crossover is expressed in, and that field is
    # what lets the boundary tell the two apart. Before P-49 was repaired nothing on the
    # result carried it, `label_layers` read every crossover as a shaft rank, and this test
    # recorded the geometry-omitted result being accepted here with no warning and no
    # error. That acceptance is now a refusal, and asserting it belongs to
    # test_label_layers_refuses_a_vflip_result_computed_without_probe_geometry; this
    # fixture's own soundness claim is the divergence above.
    assert without_geometry.index_space == "channel"
    assert with_geometry.index_space == "shaft_rank"
    assert "probe_geometry" not in without_geometry.to_dict()


def test_label_layers_refuses_a_vflip_result_computed_without_probe_geometry() -> None:
    """The refusal leg of H1. The mislabelling it prevents is 06-20's; this is the refusal.

    The refusal must be attributable. ``label_layers`` already rejects a channel-count
    mismatch at this boundary, and the counts match here, so a repair raising that
    message would be refusing for a condition that does not hold -- it is excluded
    explicitly rather than accepted as "a ValueError was raised".
    """
    lfp, geometry = _two_bank_probe()
    without_geometry = vflip_from_lfp(lfp, fs=LFP_FS, min_support_score=0.0)

    with pytest.raises(ValueError) as raised:
        label_layers(without_geometry, geometry, granular_thickness_um=150.0)

    assert _CHANNEL_COUNT_REFUSAL not in str(raised.value), (
        "the channel counts agree on this probe, so a count mismatch is the wrong reason"
    )
