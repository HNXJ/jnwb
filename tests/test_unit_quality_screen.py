"""``screen_units_against_labels``: held-out agreement per session, its declines and refusals.

Each behaviour test has a planted mutant of the implementation that it catches (recorded in
the commit message). The synthetic corpus has three sessions whose label rates differ, so the
pooled figure and the per-session figures disagree.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import jnwb.unit_quality as unit_quality
from jnwb.unit_quality import (
    SCREEN_ESTIMAND,
    _screen_balanced_accuracy,
    _screen_kappa,
    screen_units_against_labels,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = (
    REPO_ROOT / "artifacts" / "evidence" / "0.2.14" / "api_proposals"
    / "noise_correlation_and_label_screen.md"
)

NUMBERS = ("balanced_accuracy", "kappa", "majority_baseline", "ci_low", "ci_high")
RATES = {"a": 0.9, "b": 0.5, "c": 0.5}


def _corpus(seed, n=80):
    """Sessions a, b, c with label rates 0.9, 0.5, 0.5; both metrics carry the label."""
    rng = np.random.default_rng(seed)
    frames, labels, sessions = [], [], []
    for s, rate in RATES.items():
        y = (rng.random(n) < rate).astype(int)
        frames.append(pd.DataFrame({
            "m1": 1.2 * y + rng.normal(size=n),
            "m2": 0.8 * y + rng.normal(size=n),
        }))
        labels.append(y)
        sessions.extend([s] * n)
    metrics = pd.concat(frames, ignore_index=True)
    return metrics, np.concatenate(labels), np.array(sessions)


def _screen(metrics, labels, sessions, rng, *, min_units=10, columns=("m1", "m2")):
    return screen_units_against_labels(
        metrics, labels, sessions,
        metric_columns=list(columns), classifier="linear_svm",
        min_units=min_units, rng=rng,
    )


def _record(result, session):
    (rec,) = [r for r in result["per_session"] if r["session"] == session]
    return rec


def _intervals(result):
    recs = [(r["ci_low"], r["ci_high"]) for r in result["per_session"]]
    return recs + [(result["pooled"]["ci_low"], result["pooled"]["ci_high"])]


# --- the item's check: pooled and per-session values differ ---------------------------------


def test_per_session_and_pooled_balanced_accuracy_differ_at_seeds_0_to_9():
    for seed in range(10):
        metrics, labels, sessions = _corpus(seed)
        rates = {s: labels[sessions == s].mean() for s in RATES}
        assert rates["a"] - rates["b"] > 0.2, f"seed {seed}: fixture lacks a label-rate gap"

        result = _screen(metrics, labels, sessions, seed)
        assert [r["status"] for r in result["per_session"]] == ["success"] * 3, seed
        pooled = result["pooled"]["balanced_accuracy"]
        gap = max(abs(r["balanced_accuracy"] - pooled) for r in result["per_session"])
        assert gap > 0.02, (
            f"seed {seed}: per-session and pooled balanced accuracy agree to {gap:.3f}; the "
            "pooled figure would hide the per-session differences"
        )


def test_result_holds_agreement_only_and_names_its_parts():
    metrics, labels, sessions = _corpus(0)
    result = _screen(metrics, labels, sessions, 0)
    assert set(result) == {
        "per_session", "pooled", "estimand", "metric_columns", "classifier", "min_units",
        "unaudited_columns", "seed",
    }
    assert [r["session"] for r in result["per_session"]] == ["a", "b", "c"]
    assert result["metric_columns"] == ["m1", "m2"]
    assert result["classifier"] == "linear_svm"
    assert result["min_units"] == 10
    assert result["unaudited_columns"] == []


# --- refusals ---------------------------------------------------------------------------------


def test_unknown_classifier_is_refused_naming_the_accepted_value():
    metrics, labels, sessions = _corpus(0)
    with pytest.raises(ValueError, match="'linear_svm'"):
        screen_units_against_labels(
            metrics, labels, sessions, metric_columns=["m1"], classifier="rbf",
            min_units=10, rng=0,
        )


def test_three_label_values_are_refused():
    metrics, labels, sessions = _corpus(0)
    labels = labels.copy()
    labels[:3] = 2
    with pytest.raises(ValueError, match="exactly two distinct values"):
        _screen(metrics, labels, sessions, 0)


# --- declines: absent column, NaN metric, training-side and held-out label degeneracy --------


def test_absent_metric_column_declines_every_session_and_names_it():
    metrics, labels, sessions = _corpus(0)
    result = _screen(metrics, labels, sessions, 0, columns=("m1", "not_a_column"))
    assert result["unaudited_columns"] == ["not_a_column"]
    for rec in result["per_session"]:
        assert rec["status"] == "unaudited_metric"
        assert rec["excluded_from_training"] is True
        assert all(np.isnan(rec[k]) for k in NUMBERS), rec
    assert all(np.isnan(result["pooled"][k]) for k in NUMBERS)
    assert result["pooled"]["n_units"] == 0


def test_nan_metric_declines_its_session_and_leaves_it_out_of_every_training_pool():
    metrics, labels, sessions = _corpus(0)
    dirty = metrics.copy()
    dirty.loc[np.flatnonzero(sessions == "b")[:3], "m1"] = np.nan
    result = _screen(dirty, labels, sessions, 0)

    b = _record(result, "b")
    assert b["status"] == "unaudited_metric"
    assert b["nonfinite_counts"] == {"m1": 3, "m2": 0}
    assert b["excluded_from_training"] is True
    assert all(np.isnan(b[k]) for k in NUMBERS), "a declined session must not read as a number"

    # Session a is fitted on c alone in both tables: b's clean rows must not reach its fit.
    keep = sessions != "b"
    without_b = _screen(metrics[keep].reset_index(drop=True), labels[keep], sessions[keep], 0)
    for key in ("balanced_accuracy", "kappa", "majority_baseline", "ci_low", "ci_high"):
        assert _record(result, "a")[key] == pytest.approx(
            _record(without_b, "a")[key], rel=1e-12
        ), key


def test_held_out_session_with_one_label_declines_single_class():
    metrics, labels, sessions = _corpus(0)
    labels = labels.copy()
    labels[sessions == "b"] = 1
    result = _screen(metrics, labels, sessions, 0)
    assert _record(result, "b")["status"] == "single_class"
    assert all(np.isnan(_record(result, "b")[k]) for k in NUMBERS)
    assert _record(result, "a")["status"] == "success"


def test_training_pool_with_one_label_declines_single_class_training():
    metrics, labels, sessions = _corpus(0)
    labels = labels.copy()
    labels[sessions == "b"] = 0
    labels[sessions == "c"] = 0
    result = _screen(metrics, labels, sessions, 0)
    assert _record(result, "a")["status"] == "single_class_training"
    assert all(np.isnan(_record(result, "a")[k]) for k in NUMBERS)
    assert _record(result, "b")["status"] == "single_class"


def test_too_few_labelled_units_declines_too_few_units_and_counts_the_unlabelled():
    metrics, labels, sessions = _corpus(0)
    labels = labels.astype(float)
    rows_b = np.flatnonzero(sessions == "b")
    labels[rows_b[5:]] = np.nan
    result = _screen(metrics, labels, sessions, 0, min_units=10)
    b = _record(result, "b")
    assert b["status"] == "too_few_units"
    assert b["n_units"] == 5
    assert b["n_unlabelled"] == 75
    assert all(np.isnan(b[k]) for k in NUMBERS)


def test_constant_training_metric_declines_constant_metric():
    metrics, labels, sessions = _corpus(0)
    metrics = metrics.copy()
    metrics.loc[sessions != "a", "m2"] = 0.0
    result = _screen(metrics, labels, sessions, 0)
    assert _record(result, "a")["status"] == "constant_metric"
    assert all(np.isnan(_record(result, "a")[k]) for k in NUMBERS)
    assert _record(result, "b")["status"] == "success"


# --- the estimand and the docstring ----------------------------------------------------------


def test_estimand_in_the_result_is_the_proposal_string():
    metrics, labels, sessions = _corpus(0)
    result = _screen(metrics, labels, sessions, 0)
    text = PROPOSAL.read_text(encoding="utf-8")
    (proposal_estimand,) = re.findall(r'`"estimand"`: "(.*?)" \(claim class', text)
    assert result["estimand"] == proposal_estimand
    assert result["estimand"] == SCREEN_ESTIMAND


def test_docstring_names_every_status_and_the_curator_label_limit():
    doc = screen_units_against_labels.__doc__
    for status in ("success", "unaudited_metric", "too_few_units", "single_class",
                   "single_class_training", "constant_metric"):
        assert f"``{status}``" in doc, status
    assert "never ground truth" in doc
    assert "single neuron" in doc
    assert "QC safeguard 5" in doc
    assert "certif" not in doc.lower()


# --- the formulae, on a table small enough to compute by hand --------------------------------


def test_balanced_accuracy_and_kappa_on_a_hand_table():
    y_true = np.array([0, 0, 0, 0, 1, 1])
    y_pred = np.array([0, 0, 0, 0, 0, 1])
    classes = np.array([0, 1])
    # Recalls are 4/4 and 1/2, so balanced accuracy is 0.75 where plain accuracy is 5/6.
    assert _screen_balanced_accuracy(y_true, y_pred, classes) == pytest.approx(0.75, rel=1e-12)
    # p_o = 5/6; p_e = (4/6)(5/6) + (2/6)(1/6) = 22/36; kappa = (30/36 - 22/36) / (14/36).
    assert _screen_kappa(y_true, y_pred, classes) == pytest.approx(4 / 7, rel=1e-12)


# --- rng: the same stream repeats, another changes, the reported seed rebuilds ---------------


def test_same_rng_repeats_the_intervals_and_another_rng_changes_them():
    metrics, labels, sessions = _corpus(0)
    first = _screen(metrics, labels, sessions, 3)
    assert _intervals(first) == _intervals(_screen(metrics, labels, sessions, 3))
    assert _intervals(first) != _intervals(_screen(metrics, labels, sessions, 4))
    assert first["seed"] == 3


def test_a_generator_is_reported_as_a_seed_that_rebuilds_the_intervals():
    metrics, labels, sessions = _corpus(0)
    drawn = _screen(metrics, labels, sessions, np.random.default_rng(9))
    rebuilt = _screen(metrics, labels, sessions, drawn["seed"])
    assert _intervals(drawn) == _intervals(rebuilt)


# --- the leave-one-session-out isolation check -----------------------------------------------


def test_held_out_session_labels_never_train_its_own_fit():
    # Session x carries the label in its metric; y and z carry none, so only x's own labels
    # could make x's predictions agree with its labels.
    rng = np.random.default_rng(5)
    n = 80
    frames, labels, sessions = [], [], []
    for s in ("x", "y", "z"):
        y = rng.integers(0, 2, size=n)
        signal = 2.0 * y if s == "x" else 0.0
        frames.append(pd.DataFrame({
            "m1": signal + rng.normal(size=n),
            "m2": rng.normal(size=n),
        }))
        labels.append(y)
        sessions.extend([s] * n)
    metrics = pd.concat(frames, ignore_index=True)
    labels = np.concatenate(labels)
    sessions = np.array(sessions)

    for s in ("y", "z"):
        m1 = metrics["m1"].to_numpy()[sessions == s]
        y = labels[sessions == s]
        assert abs(m1[y == 1].mean() - m1[y == 0].mean()) < 0.5, "y and z must not carry the label"

    result = _screen(metrics, labels, sessions, 0)
    x = _record(result, "x")
    assert x["status"] == "success"
    assert x["balanced_accuracy"] < 0.65, (
        f"x scored {x['balanced_accuracy']:.3f} on its own labels: they reached its fit"
    )


# --- labels and sessions as given: object arrays, one session, mixed session types -----------


def test_integer_labels_in_an_object_array_with_none_screen_and_none_is_unlabelled():
    metrics, labels, sessions = _corpus(0)
    held = np.flatnonzero(sessions == "b")[:4]
    objects = np.array(labels.tolist(), dtype=object)
    objects[held] = None
    assert objects.dtype == object and sum(x is None for x in objects) == 4, "fixture"
    as_float = labels.astype(float)
    as_float[held] = np.nan

    result = _screen(metrics, objects, sessions, 0)
    assert [r["status"] for r in result["per_session"]] == ["success"] * 3
    b = _record(result, "b")
    assert b["n_unlabelled"] == 4
    assert b["n_units"] == 76
    # The table with NaN for the same missing labels gives the same numbers.
    expected = _screen(metrics, as_float, sessions, 0)
    for got, want in zip(result["per_session"], expected["per_session"]):
        for key in NUMBERS:
            assert got[key] == pytest.approx(want[key], rel=1e-12), (got["session"], key)


def test_one_session_is_refused_as_needing_at_least_two():
    metrics, labels, _ = _corpus(0)
    with pytest.raises(ValueError, match="at least two"):
        _screen(metrics, labels, np.repeat("a", len(labels)), 0)


def test_session_ids_of_mixed_types_are_refused_naming_the_types():
    metrics, labels, sessions = _corpus(0)
    mixed = [str(s) for s in sessions]
    mixed[0] = 1
    with pytest.raises(ValueError, match=r"more than one type \(int, str\)"):
        _screen(metrics, labels, mixed, 0)


# --- the quantities a wrong formula would move: each killed by one test ----------------------


def _scripted_predictions(monkeypatch, predictions):
    """Replace the fit with fixed predictions, one array per held-out session in session order."""
    queue = list(predictions)

    def fit(X_train, y_train, X_test, random_state, *, groups_train=None):
        y_pred = np.asarray(queue.pop(0))
        assert len(y_pred) == len(X_test), "the scripted predictions are out of step"
        return y_pred, np.zeros(len(X_test)), 1.0

    monkeypatch.setattr(unit_quality, "_fit_predict_linear_svm", fit)


def test_majority_baseline_is_the_training_majority_scored_on_the_held_out_labels():
    metrics, labels, sessions = _corpus(0)
    result = _screen(metrics, labels, sessions, 0)
    for s in RATES:
        held = labels[sessions == s]
        majority = np.bincount(labels[sessions != s]).argmax()
        expected = float(np.mean(held == majority))
        assert 0.0 < expected < 1.0, f"{s}: the held-out labels all match the majority"
        assert _record(result, s)["majority_baseline"] == pytest.approx(expected, rel=1e-12), s


def test_interval_bounds_the_fraction_agreeing_not_the_predictions(monkeypatch):
    metrics, labels, sessions = _corpus(0)
    # Every held-out unit is predicted 1: the agreement fraction is the label rate, and an
    # interval over the predictions would sit at 1.
    _scripted_predictions(monkeypatch, [np.ones(80, dtype=int)] * 3)
    result = _screen(metrics, labels, sessions, 0)
    for s in RATES:
        rec = _record(result, s)
        agree = float(np.mean(labels[sessions == s] == 1))
        assert rec["ci_low"] <= agree <= rec["ci_high"], (s, rec["ci_low"], agree, rec["ci_high"])
        assert rec["ci_high"] < 1.0, f"{s}: the interval sits at the prediction rate"


def test_pooled_kappa_is_the_pooled_table_not_the_mean_of_the_sessions(monkeypatch):
    metrics, labels, sessions = _corpus(0)
    wrong = {"a": 8, "b": 30, "c": 20}
    predicted = {}
    for s in RATES:
        y = labels[sessions == s].copy()
        y[:wrong[s]] = 1 - y[:wrong[s]]
        predicted[s] = y
    _scripted_predictions(monkeypatch, [predicted[s] for s in RATES])
    result = _screen(metrics, labels, sessions, 0)

    def kappa(y, p):
        p_o = np.mean(y == p)
        p_e = sum(np.mean(y == c) * np.mean(p == c) for c in (0, 1))
        return (p_o - p_e) / (1 - p_e)

    truth = np.concatenate([labels[sessions == s] for s in RATES])
    guess = np.concatenate([predicted[s] for s in RATES])
    pooled = kappa(truth, guess)
    mean_of_sessions = np.mean([_record(result, s)["kappa"] for s in RATES])
    assert abs(pooled - mean_of_sessions) > 0.01, "the fixture does not separate the two"
    assert result["pooled"]["kappa"] == pytest.approx(pooled, rel=1e-12)
