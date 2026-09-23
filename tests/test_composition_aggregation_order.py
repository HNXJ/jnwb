"""Aggregation order across two composition chains, pinned on composed values.

Chains H5 and H6 of the subset ruled in `artifacts/evidence/0.2.6/composition_subset_0.2.6.md`:

    H5  band_power -> aggregate_to_db
    H6  complex_tfr -> TFRAccumulator.add_trial / .power() -> aggregate_to_db, to_db

What was already covered, and why it did not reach these chains. `TestAggregateToDb` in
`test_spectral.py` pins the log-last order on hand-written arrays, so it constrains
`aggregate_to_db` alone and never the value a producer hands it.
`test_agents_md_recipes.py` executes the block that composes the two but asserts no decibel,
so its only property is "no exception". For H6, the accumulator probes assert `power()` by
shape, and neither TFR test module mentions `to_db` or `aggregate_to_db` at all.

Every input below is generated from literals in this file, and every pinned decibel was
measured from that generator. The magnitudes recorded in the ratified subset -- 0.912209 dB
for H5 and 5.221199 dB for H6 -- were measured on inputs that were never recorded: the probe
scripts its Receipts section names were git-ignored and are not in the repository or its
history. The values here are therefore a re-measurement on a recorded generator rather than a
reproduction of those digits, and each separation assertion below also requires the declared
magnitude to be exceeded.

06-19's rule: an input on which both orders agree tests nothing. The gains are deliberately
unequal across trials, and the signal and baseline schedules differ, so all three quantities
-- mean_of_ratios, ratio_of_means and mean-of-decibels -- are separated.
"""

from __future__ import annotations

import numpy as np
import pytest

import jnwb

FS = 1000.0
SEED = 20260919

# --- H5 generator -------------------------------------------------------------------------
H5_N_TRIALS = 30
H5_N_TIMES = 2000
H5_SIGNAL_GAINS = np.linspace(0.5, 2.0, H5_N_TRIALS)
H5_BASELINE_GAINS = np.linspace(1.5, 0.75, H5_N_TRIALS)

# Measured on the generator above.
H5_MEAN_OF_RATIOS_DB = 3.366018896905
H5_RATIO_OF_MEANS_DB = 1.097407712383
H5_MEAN_OF_DECIBELS_DB = 0.373387279965
#: Declared for H5 in the ratified subset; the re-measured separation must exceed it.
H5_DECLARED_MARGIN_DB = 0.912209

# --- H6 generator -------------------------------------------------------------------------
H6_N_TRIALS = 12
H6_N_CHANNELS = 2
H6_N_TIMES = 512
H6_FREQS = np.array([10.0, 20.0, 30.0])
H6_SIGNAL_GAINS = np.linspace(0.5, 2.0, H6_N_TRIALS)
H6_BASELINE_GAINS = np.linspace(1.5, 0.75, H6_N_TRIALS)

# Measured on the generator above, over the cells every trial marked valid.
H6_SEPARATION_MIN_DB = 1.431448336494
H6_SEPARATION_MEDIAN_DB = 6.377634438100
#: Declared for H6 in the ratified subset; the re-measured separation must exceed it.
H6_DECLARED_MARGIN_DB = 5.221199

#: A decibel tolerance four orders of magnitude below the smallest separation asserted here,
#: so it pins the estimand rather than merely the sign of a difference.
DB_TOL = 1e-6


@pytest.fixture(scope="module")
def h5_band_powers():
    """Per-trial band powers built *through* `band_power`, which is what makes this H5."""
    rng = np.random.default_rng(SEED)
    trials = rng.normal(size=(H5_N_TRIALS, H5_N_TIMES)) * H5_SIGNAL_GAINS[:, None]
    baselines = rng.normal(size=(H5_N_TRIALS, H5_N_TIMES)) * H5_BASELINE_GAINS[:, None]
    beta = jnwb.CANONICAL_BANDS["beta"]
    power = np.array(
        [jnwb.band_power(t, fs=FS, freq_range=beta, normalize=False) for t in trials]
    )
    baseline = np.array(
        [jnwb.band_power(t, fs=FS, freq_range=beta, normalize=False) for t in baselines]
    )
    return power, baseline


@pytest.fixture(scope="module")
def h6_chain():
    """The accumulator route and the trial-stack route over the same trials."""
    rng = np.random.default_rng(SEED)
    trials = (
        rng.normal(size=(H6_N_TRIALS, H6_N_CHANNELS, H6_N_TIMES))
        * H6_SIGNAL_GAINS[:, None, None]
    )
    baselines = (
        rng.normal(size=(H6_N_TRIALS, H6_N_CHANNELS, H6_N_TIMES))
        * H6_BASELINE_GAINS[:, None, None]
    )
    shape = (H6_N_CHANNELS, len(H6_FREQS), H6_N_TIMES)
    acc = jnwb.TFRAccumulator(shape=shape)
    baseline_acc = jnwb.TFRAccumulator(shape=shape)
    stacked_power, stacked_baseline = [], []
    for signal_trial, baseline_trial in zip(trials, baselines):
        tfr = jnwb.complex_tfr(signal_trial, fs=FS, freqs=H6_FREQS)
        baseline_tfr = jnwb.complex_tfr(baseline_trial, fs=FS, freqs=H6_FREQS)
        acc.add_trial(tfr.z, valid=tfr.coi_mask)
        baseline_acc.add_trial(baseline_tfr.z, valid=baseline_tfr.coi_mask)
        stacked_power.append(np.abs(tfr.z) ** 2)
        stacked_baseline.append(np.abs(baseline_tfr.z) ** 2)
    return {
        "acc": acc,
        "baseline_acc": baseline_acc,
        "power": np.asarray(stacked_power),
        "baseline": np.asarray(stacked_baseline),
        # Cells every trial marked valid. Edge cells have n == 0 under the COI mask, so their
        # decibels are not finite and comparing estimands there would compare NaNs.
        "interior": acc.n == H6_N_TRIALS,
    }


class TestH5BandPowerToAggregateToDb:
    """`band_power` -> `aggregate_to_db`: the composed value, not the primitive's own algebra."""

    def test_the_composed_value_is_the_documented_log_last_value(self, h5_band_powers):
        """Average the ratios, then take 10*log10 once -- on `band_power` output.

        The equality against `to_db(mean(ratios))` alone would be internal consistency of
        `aggregate_to_db` and would hold for any producer, including a broken one. Pinning the
        composed decibel to a measured literal is what ties it to `band_power`: change the
        band or the within-band statistic and the literal moves, while the algebraic identity
        would not notice.

        What this does *not* catch, established by mutation rather than assumed: replacing the
        within-band `mean` by `sum` leaves every decibel here unchanged, because signal and
        baseline share a Welch grid and the bin count cancels in the ratio. Density against
        integrated power is invisible to any assertion on this chain's output, and belongs to
        whatever pins `band_power` itself.
        """
        power, baseline = h5_band_powers
        composed = float(
            jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=0)
        )
        hand_computed = float(jnwb.to_db(np.mean(power / baseline)))
        assert composed == pytest.approx(hand_computed, abs=1e-12)
        assert composed == pytest.approx(H5_MEAN_OF_RATIOS_DB, abs=DB_TOL)

    def test_log_last_is_separated_from_averaging_decibels(self, h5_band_powers):
        """The Jensen gap on this chain, pinned.

        Asserting only `!=` would pass on a separation of 1e-12, which is the degenerate input
        06-19 forbids. Both endpoints are pinned and the gap is required to exceed the
        magnitude the subset declared for H5.
        """
        power, baseline = h5_band_powers
        log_last = float(
            jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=0)
        )
        log_first = float(np.mean(jnwb.to_db(power / baseline)))
        assert log_first == pytest.approx(H5_MEAN_OF_DECIBELS_DB, abs=DB_TOL)
        # Jensen: mean(log x) <= log(mean x), so the correct order is the larger one.
        assert log_last > log_first
        assert log_last - log_first == pytest.approx(
            H5_MEAN_OF_RATIOS_DB - H5_MEAN_OF_DECIBELS_DB, abs=DB_TOL
        )
        assert log_last - log_first > H5_DECLARED_MARGIN_DB

    def test_the_two_estimands_are_separated_on_this_chain(self, h5_band_powers):
        """`how` selects an estimand, and on unequal baselines the two do not coincide.

        The baseline gain schedule differs from the signal's, which is what keeps this from
        being the degenerate case where both estimands are the same number.
        """
        power, baseline = h5_band_powers
        mean_of_ratios = float(
            jnwb.aggregate_to_db(power, baseline, how="mean_of_ratios", aggregate_over=0)
        )
        ratio_of_means = float(
            jnwb.aggregate_to_db(power, baseline, how="ratio_of_means", aggregate_over=0)
        )
        assert ratio_of_means == pytest.approx(H5_RATIO_OF_MEANS_DB, abs=DB_TOL)
        assert abs(mean_of_ratios - ratio_of_means) > 1.0
        assert ratio_of_means == pytest.approx(
            float(jnwb.to_db(power.sum() / baseline.sum())), abs=1e-12
        )

    def test_a_single_band_power_call_cannot_be_aggregated_over_a_trial_axis(self):
        """The shape trap: `band_power` returns a float, so the natural spelling raises.

        `pytest.raises(Exception)` would pass on a misspelled keyword, so the exact exception
        type is required and the message is matched.
        """
        rng = np.random.default_rng(SEED)
        trace = rng.normal(size=H5_N_TIMES)
        one_call = jnwb.band_power(
            trace, fs=FS, freq_range=jnwb.CANONICAL_BANDS["beta"], normalize=False
        )
        assert np.ndim(one_call) == 0
        with pytest.raises(np.exceptions.AxisError, match="out of bounds"):
            jnwb.aggregate_to_db(one_call, 1.0, how="mean_of_ratios", aggregate_over=0)


class TestH6AccumulatorToDecibels:
    """`complex_tfr` -> `TFRAccumulator` -> `aggregate_to_db`: what the route computes."""

    def test_the_accumulator_route_computes_ratio_of_means_whatever_how_names(self, h6_chain):
        """`power()` has already averaged over trials, so the ratio is formed on the means.

        This pins behaviour and presumes no repair. The identity alone would also hold on an
        input where the two estimands coincide -- which is the degenerate case 06-19 forbids --
        so the separation from the named estimand is asserted in the same test rather than
        left to another one that could be deleted independently.
        """
        chain = h6_chain
        interior = chain["interior"]
        assert interior.sum() > 0

        through_accumulator = jnwb.aggregate_to_db(
            chain["acc"].power(),
            chain["baseline_acc"].power(),
            how="mean_of_ratios",
            aggregate_over=None,
        )
        stacked_ratio_of_means = jnwb.aggregate_to_db(
            chain["power"], chain["baseline"], how="ratio_of_means", aggregate_over=0
        )
        stacked_mean_of_ratios = jnwb.aggregate_to_db(
            chain["power"], chain["baseline"], how="mean_of_ratios", aggregate_over=0
        )

        # What it computes: ratio_of_means, to floating point.
        np.testing.assert_allclose(
            through_accumulator[interior], stacked_ratio_of_means[interior], atol=1e-9
        )
        # What it was asked for: mean_of_ratios, which it is not.
        separation = np.abs(through_accumulator[interior] - stacked_mean_of_ratios[interior])
        assert separation.min() == pytest.approx(H6_SEPARATION_MIN_DB, abs=DB_TOL)
        assert np.median(separation) == pytest.approx(H6_SEPARATION_MEDIAN_DB, abs=DB_TOL)
        assert np.median(separation) > H6_DECLARED_MARGIN_DB

    def test_per_trial_decibels_are_a_third_distinct_value(self, h6_chain):
        """Taking the logarithm first is separated from both estimands on this chain."""
        chain = h6_chain
        interior = chain["interior"]
        per_trial_db = np.mean(jnwb.to_db(chain["power"] / chain["baseline"]), axis=0)
        through_accumulator = jnwb.aggregate_to_db(
            chain["acc"].power(),
            chain["baseline_acc"].power(),
            how="mean_of_ratios",
            aggregate_over=None,
        )
        stacked_mean_of_ratios = jnwb.aggregate_to_db(
            chain["power"], chain["baseline"], how="mean_of_ratios", aggregate_over=0
        )
        assert np.median(np.abs(per_trial_db[interior] - through_accumulator[interior])) > 1.0
        assert np.median(np.abs(per_trial_db[interior] - stacked_mean_of_ratios[interior])) > 1.0
        # Jensen holds cellwise against the log-last value over the same trials.
        assert np.all(per_trial_db[interior] <= stacked_mean_of_ratios[interior] + 1e-12)

    @pytest.mark.xfail(
        strict=True,
        reason=(
            "P-114: the accumulator has "
            "consumed the trial axis, so how='mean_of_ratios' names an estimand the input can "
            "no longer support. Whether aggregate_to_db should refuse the combination or "
            "deliver it is a public-API semantics choice and an AGENTS.md 12 stop, so this "
            "accepts either resolution."
        ),
    )
    def test_the_route_delivers_the_estimand_it_names_or_refuses_it(self, h6_chain):
        """Strict, so whichever repair lands, this xpasses and forces the marker's removal.

        A non-strict xfail would let the defect be repaired with nobody noticing, which is
        this repository's dominant failure class. Refusal is caught narrowly: a bare `except
        Exception` would turn any future unrelated error into a silent pass.
        """
        chain = h6_chain
        interior = chain["interior"]
        stacked_mean_of_ratios = jnwb.aggregate_to_db(
            chain["power"], chain["baseline"], how="mean_of_ratios", aggregate_over=0
        )
        try:
            through_accumulator = jnwb.aggregate_to_db(
                chain["acc"].power(),
                chain["baseline_acc"].power(),
                how="mean_of_ratios",
                aggregate_over=None,
            )
        except (TypeError, ValueError):
            return  # refusing to name an estimand it cannot form is an acceptable resolution
        np.testing.assert_allclose(
            through_accumulator[interior], stacked_mean_of_ratios[interior], atol=DB_TOL
        )

    def test_the_coi_mask_changes_the_edge_bins_and_leaves_the_interior_identical(self):
        """`add_trial(valid=coi_mask)` is not cosmetic: it removes the edge bins entirely.

        "The two differ at the edge" would pass if `power()` returned zeros everywhere, so the
        unmasked edge power is required to be strictly positive and the interior to be both
        identical and non-zero.
        """
        rng = np.random.default_rng(SEED)
        trials = (
            rng.normal(size=(H6_N_TRIALS, H6_N_CHANNELS, H6_N_TIMES))
            * H6_SIGNAL_GAINS[:, None, None]
        )
        shape = (H6_N_CHANNELS, len(H6_FREQS), H6_N_TIMES)
        masked = jnwb.TFRAccumulator(shape=shape)
        unmasked = jnwb.TFRAccumulator(shape=shape)
        coi_mask = None
        for trial in trials:
            tfr = jnwb.complex_tfr(trial, fs=FS, freqs=H6_FREQS)
            coi_mask = tfr.coi_mask
            masked.add_trial(tfr.z, valid=tfr.coi_mask)
            unmasked.add_trial(tfr.z)

        edge = ~coi_mask
        assert edge.sum() > 0 and coi_mask.sum() > 0
        masked_power, unmasked_power = masked.power(), unmasked.power()

        assert np.all(unmasked_power[edge] > 0.0)
        assert np.all(masked_power[edge] == 0.0)
        relative_change = np.abs(masked_power[edge] - unmasked_power[edge]) / unmasked_power[edge]
        np.testing.assert_allclose(relative_change, 1.0, atol=0.0)

        assert np.all(masked_power[coi_mask] > 0.0)
        np.testing.assert_array_equal(masked_power[coi_mask], unmasked_power[coi_mask])
