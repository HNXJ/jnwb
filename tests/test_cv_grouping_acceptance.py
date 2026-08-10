"""Sol/Hamm Handout 2 acceptance tests 1 and 2 -- demonstrate, on synthetic data with a known
ground truth, exactly the failure mode this whole patch pass exists to close: random/ungrouped
CV can "detect" a cycle-level confound that a grouped (leave-one-cycle-out) design correctly
sees through as chance, and the project's own within-cycle permutation null is calibrated when
there is truly no signal.

(Acceptance test 3 -- the twelve-condition ontology test -- lives in tests/test_trial_ontology.py.
Acceptance test 4 -- no retracted census values in executable code -- lives in
tests/test_no_retracted_census_in_live_code.py.)
"""
from __future__ import annotations

import numpy as np
import pytest
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from jnwb.permutation import permute_labels


def _make_cycle_aliased_dataset(n_cycles: int, trials_per_cycle: int, n_features: int, seed: int):
    """Labels are perfectly aliased with cycle identity (half the cycles are class 0, half are
    class 1 -- no per-trial signal at all beyond which cycle a trial belongs to). Features are
    pure noise plus a per-cycle random offset that is INDEPENDENT of class -- the offset carries
    no genuine class information, but it lets a same-cycle trial in train "give away" a
    same-cycle trial in test purely by shared nuisance structure, which is exactly the leakage
    random/ungrouped CV is vulnerable to.
    """
    rng = np.random.default_rng(seed)
    assert n_cycles % 2 == 0
    cycle_labels = np.array([0] * (n_cycles // 2) + [1] * (n_cycles // 2))
    rng.shuffle(cycle_labels)

    X_parts, y_parts, cycle_parts = [], [], []
    for cycle_id in range(n_cycles):
        offset = rng.normal(0, 5.0, size=n_features)  # class-independent nuisance, unique per cycle
        trial_noise = rng.normal(0, 1.0, size=(trials_per_cycle, n_features))
        X_parts.append(offset + trial_noise)
        y_parts.append(np.full(trials_per_cycle, cycle_labels[cycle_id]))
        cycle_parts.append(np.full(trials_per_cycle, cycle_id))

    X = np.concatenate(X_parts, axis=0)
    y = np.concatenate(y_parts, axis=0)
    cycles = np.concatenate(cycle_parts, axis=0)
    return X, y, cycles


def _random_kfold_accuracy(X, y, seed: int, n_splits: int = 5) -> float:
    """The exact pattern found live in the 12 quarantined decoding scripts: StratifiedKFold
    with shuffle=True, no group awareness."""
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs = []
    for train_idx, test_idx in cv.split(X, y):
        pipe = Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0))])
        pipe.fit(X[train_idx], y[train_idx])
        accs.append(pipe.score(X[test_idx], y[test_idx]))
    return float(np.mean(accs))


def _leave_one_cycle_out_accuracy(X, y, cycles) -> float:
    accs = []
    for cycle_id in np.unique(cycles):
        test = cycles == cycle_id
        train = ~test
        if len(np.unique(y[train])) < 2:
            continue
        pipe = Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0))])
        pipe.fit(X[train], y[train])
        accs.append(pipe.score(X[test], y[test]))
    return float(np.mean(accs))


class TestAcceptance1_RandomCvInflatesCycleConfound:
    def test_random_cv_shows_apparent_effect_grouped_cv_shows_chance(self):
        X, y, cycles = _make_cycle_aliased_dataset(
            n_cycles=12, trials_per_cycle=15, n_features=20, seed=42
        )

        random_cv_acc = _random_kfold_accuracy(X, y, seed=42)
        grouped_cv_acc = _leave_one_cycle_out_accuracy(X, y, cycles)

        # Random/ungrouped CV should look like a strong, "real" effect -- it can memorize each
        # cycle's own nuisance offset because same-cycle trials leak across the train/test split.
        assert random_cv_acc > 0.85, (
            f"expected random CV to show an inflated apparent effect (leakage), got "
            f"{random_cv_acc:.3f} -- the synthetic confound construction may need adjusting"
        )
        # Grouped (leave-one-cycle-out) CV never sees a held-out cycle's offset during training,
        # so it should be chance-compatible: there is no per-trial signal, only nuisance.
        assert 0.30 <= grouped_cv_acc <= 0.70, (
            f"expected leave-one-cycle-out CV to be chance-compatible (~0.5), got "
            f"{grouped_cv_acc:.3f} -- if this is inflated too, the synthetic construction leaked "
            f"signal outside the cycle-level nuisance as designed"
        )
        # The core claim: random CV overstates the effect relative to the grouped design.
        assert random_cv_acc - grouped_cv_acc > 0.25, (
            f"random CV ({random_cv_acc:.3f}) should substantially exceed grouped CV "
            f"({grouped_cv_acc:.3f}) on this cycle-aliased-label construction -- that gap IS "
            f"the confound this whole patch pass exists to prevent from being mistaken for a "
            f"real finding."
        )


class TestAcceptance2_WithinCyclePermutationNullIsCalibrated:
    def test_calibrated_null_on_pure_noise_no_signal_at_all(self):
        """No cycle-label aliasing this time -- labels are genuinely random with respect to
        both trial and cycle. A well-calibrated grouped-CV + within-cycle-permutation-null
        pipeline should report an observed accuracy that sits comfortably inside its own null
        distribution, not out in the tail."""
        from scripts.compute_omission_identity_leakage_safe import decode_binary_cycle_safe

        rng = np.random.default_rng(7)
        n_cycles, trials_per_cycle, n_features = 10, 12, 15
        X = rng.normal(size=(n_cycles * trials_per_cycle, n_features))
        y = rng.integers(0, 2, size=n_cycles * trials_per_cycle)
        cycles = np.repeat(np.arange(n_cycles), trials_per_cycle)

        result = decode_binary_cycle_safe(X, y, cycles, seed=7, n_permutations=200)

        assert result["status"] == "success"
        observed = result["accuracy_loco_balanced"]
        null_mean = result["null_mean"]
        null_sd = result["null_sd"]

        # Calibration check: the observed statistic, computed under the exact same LOCO design
        # as the null, should not look extreme relative to a null built from the same folds --
        # if it did, the null-construction (not the data) would be biased.
        z = abs(observed - null_mean) / null_sd if null_sd > 0 else 0.0
        assert z < 3.0, (
            f"observed accuracy {observed:.3f} is {z:.1f} null SDs from the null mean "
            f"{null_mean:.3f} (SD={null_sd:.3f}) on pure-noise data with no signal -- the null "
            f"construction (LOCO CV + within-cycle permutation) may be miscalibrated."
        )
        # p-value should not be spuriously significant on pure noise (loose threshold -- this
        # is one draw, not a full calibration sweep, but should not obviously fail).
        assert result["p_permutation"] > 0.01, (
            f"p={result['p_permutation']:.4f} on pure-noise data with no real signal -- "
            f"suspiciously significant for a calibrated null."
        )

    def test_within_group_permutation_preserves_per_cycle_class_balance(self):
        """A calibrated null must preserve the exact same per-cycle class counts as the real
        data, or it isn't testing the right null hypothesis (exchangeability within group, not
        globally)."""
        rng = np.random.default_rng(3)
        labels = np.array([0, 0, 1, 1, 1, 0, 1, 0, 0, 1])
        cycles = np.array([0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
        perm = permute_labels(labels, groups=cycles, scheme="within_group", rng=rng)
        for c in np.unique(cycles):
            m = cycles == c
            assert sorted(perm[m].tolist()) == sorted(labels[m].tolist())
