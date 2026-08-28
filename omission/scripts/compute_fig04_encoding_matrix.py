#!/usr/bin/env python3
"""Figure 4 v2: unified encoding matrix, four targets, one shared long-form schema.

Replaces ``compute_omission_identity_extended_v1.py``'s per-panel-CSV structure (kept on disk,
unedited, its softmax engine and window constants imported from here rather than duplicated).
One common grammar, ``X_{s,a}(t,u) -> Y``, varying only the TARGET, the time window, and the
control population:

* ``Y_stim``  -- real presented identity {A,B} at p1 (positive control, Panel A). R-family
  trials have no real p1 identity by construction (``trial_ontology.parse_condition``:
  ``has_real_identity = family_letter in ("A","B")``; ``POSITIVE_CONTROL`` rows are built only
  from AAAB/BBBA epochs, never from R conditions) -- confirmed empirically here, not assumed;
  ``Y_stim`` stays 2-class.
* ``Y_omit``  -- 3-way softmax [p_A,p_B,p_R] over the missing stimulus's identity, fit
  INDEPENDENTLY per slot (p2, p3, p4 each with their own LOCO folds -- Panel C diagonal). The
  documented p2/p3 preceding-identity degeneracy (expected_identity is deterministically
  recoverable from preceding_identity within a fixed slot -- Milestone 1 finding, cited in
  ``decode_identity_sliding_window.py``) only bites a POOLED-across-slot fit; an independent
  per-slot fit is not degenerate and is reported as such.
* ``Y_pos``   -- 3-way p2-vs-p3-vs-p4 decode (Panel E), feature window ALWAYS the same 0..531ms
  offset relative to that trial's own slot onset (so window shape cannot leak absolute position),
  per-cycle centered (subtract each unit's own cross-slot-cycle mean) to remove generic
  within-cycle level/gain drift before fitting.
* ``Y_prev``  -- binary decode of the immediately PRECEDING real stimulus's identity from
  omission-period activity (Panel G) -- the direct adaptation/history test. Not subject to the
  Y_omit degeneracy (different target); p2/p3/p4 pooled freely, same cross-slot cycle grouping
  and same feature window as Y_pos (computed once, reused for both targets).

Plus two panels built from Y_omit's per-slot fits rather than a fifth target:

* **Cross-position generalization matrix** ``G_ij`` (Panel F) -- diagonal reuses Y_omit's own
  per-slot cells (not recomputed); off-diagonal trains once on all of slot i (balanced, no CV
  split -- testing happens on the disjoint slot j), evaluates on all of slot j, permutation null
  built by permuting slot-i training labels within slot-i's own cycles.
* **Ablation** (Panel H) -- per (session, area, slot): the SSA index (within-cycle-centered
  omission-slot rate regressed on 1-back real identity, same computation as
  ``compute_omission_identity_extended_v1.compute_ssa_index``, imported not duplicated) ranks
  units; Y_omit is refit on that slot after removing the top-decile |SSA| units, and again after
  removing the SAME NUMBER of randomly-chosen units (repeated ``--ablation-draws`` times, default
  50 for this file's own smoke-test/full-corpus budget -- the plan's proposed default is 200;
  raise via ``--ablation-draws`` for a full-corpus run) to build a matched-random null
  distribution. Isolates "removing the adaptive units specifically hurts" from "removing any k
  units hurts by dimensionality alone."

**Population strata**: this first cut computes only ``population="all_units"``. S+/S-/O+/O++/
Other, stim-/omission-responsive, and adaptation-high/low (tertile split by this pipeline's own
SSA index) are explicitly NOT wired in yet -- sequenced as a fast-follow once this base engine is
verified against a smoke test, per the plan's own "adaptation-high/low is necessarily a second
pass" sequencing. Do not read this file's ``population`` column as covering every stratum in the
plan; it currently has exactly one value.

Outputs, all under ``--output-dir``:

* ``fig04_encoding_matrix_cells.csv`` -- one row per (session, area, population, target,
  position) for Y_stim/Y_omit(diagonal)/Y_pos/Y_prev;
* ``fig04_encoding_matrix_proba_oof.csv`` -- held-out [p_a,p_b,(p_r)] per trial, 2- and 3-class
  targets alike;
* ``fig04_encoding_matrix_crossposition.csv`` -- one row per (session, area, train_position,
  test_position) incl. diagonal (duplicated from cells, flagged via ``source="diagonal_reuse"``);
* ``fig04_encoding_matrix_ablation.csv`` -- one row per (session, area, slot_key);
* ``fig04_encoding_matrix_ssa.csv`` -- one row per (session, area, slot_key, unit) SSA index;
* ``fig04_encoding_matrix_receipt.json`` -- provenance, same conventions as the leakage-safe and
  extended-v1 scripts' receipts.

Spike-only. No LFP claim. Fixed-window (Stage 1) only -- Stage 2's time-resolved Panels B/D are
out of scope for this file; they reuse ``decode_identity_sliding_window.py`` directly.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, log_loss

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
sys.path.insert(0, str(REPO_ROOT))
OA_ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

import omission as oa  # noqa: E402
from omission.jnwb_ext.omission_identity import OMISSION_IDENTITY_CONDITIONS, detect_trial_cycles  # noqa: E402
from omission.jnwb_ext.structured_identity import (  # noqa: E402
    build_canonical_trial_table,
    POSITIVE_CONTROL,
    MAIN_ANALYSIS,
)
from jnwb import paths  # noqa: E402
from jnwb.paths import sha256_file as _sha256  # noqa: E402
from jnwb.permutation import permute_labels  # noqa: E402

from compute_omission_identity_leakage_safe import (  # noqa: E402
    AREAS,
    SLOTS,
    LABELS,
    DEFAULT_SEED,
    DEFAULT_PERMUTATIONS,
    ESTIMATOR,
    _spike_count_matrix,
    _balanced_training_indices,
    _within_cycle_permutation,
    _trial_table,
    _resolve_sessions,
    decode_binary_cycle_safe,
)
from compute_omission_identity_extended_v1 import (  # noqa: E402
    SOFTMAX_ESTIMATOR,
    _softmax_pipeline,
    decode_softmax_p4_cycle_safe,
    _ssa_trial_table,
    compute_ssa_index,
)

from omission.jnwb_ext.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402

POSITION_WINDOW_MS = (0.0, 531.0)  # relative to that trial's own slot onset -- see module docstring
REAL_STIM_WINDOW_MS = (EPOCH_ONSETS_MS["p1"], EPOCH_ONSETS_MS["d1"])  # 0..531ms, real A/B stim

DEFAULT_ABLATION_DRAWS = 50
POSITIONS = ("p2", "p3", "p4")
POSITION_INT = {p: i for i, p in enumerate(POSITIONS)}


# ---- shared trial-table builders --------------------------------------------------------------

def _effective_onset(table: pd.DataFrame) -> pd.Series:
    """Absolute onset (s) shifted to that row's own slot's onset offset."""
    offsets_ms = table["slot_key"].map(lambda s: OMISSION_IDENTITY_CONDITIONS[s]["slot_onset_ms"])
    return table["start_time"].astype(float) + offsets_ms.astype(float) / 1000.0


def _y_stim_table(session) -> pd.DataFrame:
    table = build_canonical_trial_table(session, slot_keys=POSITIONS)
    if table.empty:
        return pd.DataFrame()
    pc = table[(table["analysis"] == POSITIVE_CONTROL) & table["eligible"]].copy()
    if pc.empty:
        return pd.DataFrame()
    assert set(pc["presented_identity"].dropna().unique()) <= {"A", "B"}, (
        "Y_stim: found a non-A/B presented_identity -- R-family should never reach here"
    )
    pc["label_int"] = (pc["presented_identity"] == "A").astype(int)
    pc["cycle_id"] = pc["cycle"].astype(int)
    pc["start_time"] = pd.to_numeric(pc["start_time"], errors="coerce")
    return pc.dropna(subset=["start_time"]).reset_index(drop=True)


def _cross_slot_table(session) -> pd.DataFrame:
    """MAIN_ANALYSIS eligible p2/p3/p4 rows with a cross-slot cycle id and an effective onset.

    Same ``cross_position_cycle`` construction as ``decode_identity_sliding_window.py``'s
    ``reversal_generalization`` (sort combined rows by start_time, then
    ``detect_trial_cycles`` on the sorted table) -- shared by Y_pos and Y_prev, which read this
    same table with two different label columns.
    """
    table = build_canonical_trial_table(session, slot_keys=POSITIONS)
    if table.empty:
        return pd.DataFrame()
    main = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy()
    main = main.dropna(subset=["preceding_identity", "expected_identity"])
    if main.empty:
        return pd.DataFrame()
    main["start_time"] = pd.to_numeric(main["start_time"], errors="coerce")
    main = main.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)
    main["cross_cycle_id"] = detect_trial_cycles(main[["start_time"]])
    main["position_int"] = main["slot_key"].map(POSITION_INT)
    main["preceding_int"] = (main["preceding_identity"] == "A").astype(int)
    main["effective_onset_s"] = _effective_onset(main)
    return main


def _spike_matrix_from_onsets(session, area: str, onsets_s: np.ndarray, window_ms: tuple):
    """Like ``_spike_count_matrix`` but takes onsets directly rather than an epochs df."""
    epochs = pd.DataFrame({"start_time": onsets_s})
    return _spike_count_matrix(session, area, epochs, window_ms)


# ---- Y_pos: 3-way position decode, per-cycle centered ------------------------------------------

def _fixed_balanced_accuracy_k(y_true, y_pred, n_classes: int) -> float:
    labels = list(range(n_classes))
    matrix = confusion_matrix(y_true, y_pred, labels=labels).astype(float)
    denom = matrix.sum(axis=1)
    recalls = np.divide(np.diag(matrix), denom, out=np.full(n_classes, np.nan), where=denom > 0)
    return float(np.nanmean(recalls))


def decode_multiclass_balanced_cycle_safe(
    X: np.ndarray, labels: np.ndarray, cycles: np.ndarray, *, n_classes: int,
    seed: int = DEFAULT_SEED, n_permutations: int = DEFAULT_PERMUTATIONS,
) -> dict:
    """LOCO 3-way decode scored by balanced accuracy, within-cycle-permutation null.

    Same fold/balance/null bookkeeping as ``decode_binary_cycle_safe`` (leakage-safe script),
    generalized from 2 to ``n_classes`` via ``_softmax_pipeline``'s multinomial classifier and a
    k-class balanced-accuracy statistic instead of a 2-class one.
    """
    X = np.asarray(X, dtype=float)
    labels = np.asarray(labels, dtype=int)
    cycles = np.asarray(cycles, dtype=int)
    classes = tuple(range(n_classes))
    unique_cycles = np.unique(cycles)
    if len(unique_cycles) < 2 or len(set(np.unique(labels)) & set(classes)) < n_classes:
        return {"status": "insufficient_cycles_or_classes", "n_folds": 0}

    rng = np.random.default_rng(seed)
    oof_rows: list[dict] = []
    for fold, cycle in enumerate(unique_cycles):
        test = cycles == cycle
        train = ~test
        train_idx = _balanced_training_indices(train.nonzero()[0], labels, classes, rng)
        if len(train_idx) == 0 or len(np.unique(labels[test])) < 1:
            continue
        model = _softmax_pipeline(seed + fold)
        model.fit(X[train_idx], labels[train_idx])
        pred = model.predict(X[test])
        for row_idx, y, yhat in zip(np.flatnonzero(test), labels[test], pred):
            oof_rows.append({"row_index": int(row_idx), "fold": int(fold), "cycle_id": int(cycle),
                              "y_true": int(y), "y_pred": int(yhat)})
    if not oof_rows:
        return {"status": "no_valid_folds", "n_folds": 0}

    oof = pd.DataFrame(oof_rows).sort_values("row_index").reset_index(drop=True)
    observed = _fixed_balanced_accuracy_k(oof.y_true, oof.y_pred, n_classes)

    null_vals: list[float] = []
    for perm_idx in range(int(n_permutations)):
        perm_rng = np.random.default_rng(seed + 300_000 + perm_idx)
        perm_labels = _within_cycle_permutation(labels, cycles, perm_rng)
        perm_true: list[int] = []
        perm_pred: list[int] = []
        for fold, cycle in enumerate(unique_cycles):
            test = cycles == cycle
            train = ~test
            train_idx = _balanced_training_indices(train.nonzero()[0], perm_labels, classes, perm_rng)
            if len(train_idx) == 0 or len(np.unique(perm_labels[test])) < 1:
                continue
            model = _softmax_pipeline(seed + fold)
            model.fit(X[train_idx], perm_labels[train_idx])
            perm_pred.extend(model.predict(X[test]).tolist())
            perm_true.extend(perm_labels[test].tolist())
        if perm_true:
            null_vals.append(_fixed_balanced_accuracy_k(perm_true, perm_pred, n_classes))

    null = np.asarray(null_vals, dtype=float)
    p_value = float((np.sum(null >= observed) + 1) / (len(null) + 1)) if len(null) else float("nan")
    return {
        "status": "success",
        "accuracy_loco_balanced": observed,
        "p_permutation": p_value,
        "null_mean": float(np.mean(null)) if len(null) else float("nan"),
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else float("nan"),
        "n_permutations": int(len(null)),
        "n_folds": int(len(np.unique(oof.fold))),
        "oof": oof,
    }


def _center_within_cycle(X: np.ndarray, cycles: np.ndarray) -> np.ndarray:
    centered = X.copy()
    for cycle in np.unique(cycles):
        mask = cycles == cycle
        centered[mask] -= centered[mask].mean(axis=0, keepdims=True)
    return centered


# ---- cross-position generalization matrix G_ij --------------------------------------------------

def decode_cross_position(
    X_train: np.ndarray, y_train: np.ndarray, cycles_train: np.ndarray,
    X_test: np.ndarray, y_test: np.ndarray, *, seed: int, n_permutations: int,
) -> dict:
    """Train once on all of slot i (balanced), evaluate on all of slot j. Off-diagonal only --
    the diagonal is never computed this way, it reuses Y_omit's own LOCO cells (see module
    docstring)."""
    classes = (0, 1, 2)
    if len(set(np.unique(y_train)) & set(classes)) < 3 or len(set(np.unique(y_test)) & set(classes)) < 3:
        return {"status": "insufficient_classes"}
    rng = np.random.default_rng(seed)
    train_idx = _balanced_training_indices(np.arange(len(y_train)), y_train, classes, rng)
    if len(train_idx) == 0:
        return {"status": "insufficient_balanced_training_set"}
    model = _softmax_pipeline(seed)
    model.fit(X_train[train_idx], y_train[train_idx])
    proba = model.predict_proba(X_test)
    col_for = {cls: i for i, cls in enumerate(model.named_steps["classifier"].classes_)}
    proba_abr = np.stack([proba[:, col_for[c]] if c in col_for else np.zeros(len(proba))
                           for c in classes], axis=1)
    observed_loss = float(log_loss(y_test, proba_abr, labels=list(classes)))

    null_losses: list[float] = []
    for perm_idx in range(int(n_permutations)):
        perm_rng = np.random.default_rng(seed + 400_000 + perm_idx)
        perm_labels = _within_cycle_permutation(y_train, cycles_train, perm_rng)
        perm_train_idx = _balanced_training_indices(np.arange(len(perm_labels)), perm_labels, classes, perm_rng)
        if len(perm_train_idx) == 0:
            continue
        perm_model = _softmax_pipeline(seed)
        perm_model.fit(X_train[perm_train_idx], perm_labels[perm_train_idx])
        perm_proba = perm_model.predict_proba(X_test)
        col_for_p = {cls: i for i, cls in enumerate(perm_model.named_steps["classifier"].classes_)}
        perm_proba_abr = np.stack(
            [perm_proba[:, col_for_p[c]] if c in col_for_p else np.zeros(len(perm_proba)) for c in classes],
            axis=1,
        )
        null_losses.append(float(log_loss(y_test, perm_proba_abr, labels=list(classes))))

    null = np.asarray(null_losses, dtype=float)
    p_value = (
        float((np.sum(null <= observed_loss) + 1) / (len(null) + 1)) if len(null) else float("nan")
    )
    return {
        "status": "success",
        "cross_entropy": observed_loss,
        "p_permutation": p_value,
        "null_mean": float(np.mean(null)) if len(null) else float("nan"),
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else float("nan"),
        "n_permutations": int(len(null)),
        "n_train": int(len(train_idx)),
        "n_test": int(len(y_test)),
    }


# ---- ablation: SSA-controlled vs matched-random removal ----------------------------------------

def run_ablation(
    X: np.ndarray, labels: np.ndarray, cycles: np.ndarray, ssa_ranked_cols: list[int],
    *, seed: int, n_permutations: int, n_draws: int,
) -> dict:
    """D_X^full vs D_X^SSA-controlled (top-decile |SSA| removed) vs a matched-random-removal
    distribution (same unit count, ``n_draws`` random draws) -- see module docstring."""
    n_units = X.shape[1]
    n_remove = max(1, n_units // 10)
    if n_units < 3 or len(ssa_ranked_cols) < n_remove:
        return {"status": "insufficient_units"}

    full = decode_softmax_p4_cycle_safe(X, labels, cycles, seed=seed, n_permutations=n_permutations)
    if full.get("status") != "success":
        return {"status": "full_fit_failed"}

    ssa_remove = set(ssa_ranked_cols[:n_remove])
    ssa_keep_cols = [c for c in range(n_units) if c not in ssa_remove]
    ssa_controlled = decode_softmax_p4_cycle_safe(
        X[:, ssa_keep_cols], labels, cycles, seed=seed, n_permutations=n_permutations
    )

    rng = np.random.default_rng(seed + 500_000)
    random_losses: list[float] = []
    for draw in range(int(n_draws)):
        remove_cols = set(rng.choice(n_units, size=n_remove, replace=False).tolist())
        keep_cols = [c for c in range(n_units) if c not in remove_cols]
        # Each draw needs only cross_entropy, not its own well-powered null (the matched-random
        # DISTRIBUTION across draws is the object of interest here) -- one cheap permutation per
        # draw keeps this affordable at n_draws~50-200 while still returning a valid dict shape.
        result = decode_softmax_p4_cycle_safe(
            X[:, keep_cols], labels, cycles, seed=seed + 1000 + draw, n_permutations=1,
        )
        if result.get("status") == "success":
            random_losses.append(result["cross_entropy"])

    random_arr = np.asarray(random_losses, dtype=float)
    controlled_loss = ssa_controlled.get("cross_entropy", np.nan)
    percentile = (
        float(np.mean(random_arr >= controlled_loss)) if len(random_arr) and np.isfinite(controlled_loss)
        else float("nan")
    )
    return {
        "status": "success",
        "n_units_total": n_units,
        "n_units_removed": n_remove,
        "cross_entropy_full": full.get("cross_entropy", np.nan),
        "cross_entropy_ssa_removed": controlled_loss,
        "cross_entropy_random_removed_mean": float(np.mean(random_arr)) if len(random_arr) else np.nan,
        "cross_entropy_random_removed_sd": float(np.std(random_arr, ddof=1)) if len(random_arr) > 1 else np.nan,
        "n_random_draws": int(len(random_arr)),
        "ssa_percentile_of_controlled": percentile,
        "delta_ssa": full.get("cross_entropy", np.nan) - controlled_loss
        if np.isfinite(controlled_loss) else np.nan,
    }


# ---- driver --------------------------------------------------------------------------------

def run(*, readiness_csv: Path, nwb_dir: Path, output_dir: Path, seed: int = DEFAULT_SEED,
        n_permutations: int = DEFAULT_PERMUTATIONS, ablation_draws: int = DEFAULT_ABLATION_DRAWS,
        limit: int | None = None) -> dict:
    started = time.time()
    included, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    if limit is not None:
        included = included[:limit]
    if not included:
        raise RuntimeError("no eligible NWB sessions resolved from the readiness gate")

    POP = "all_units"
    cell_rows: list[dict] = []
    proba_oof_rows: list[dict] = []
    crossposition_rows: list[dict] = []
    ablation_rows: list[dict] = []
    ssa_rows: list[dict] = []
    errors: list[dict] = []

    for session_number, meta in enumerate(included, start=1):
        print(f"[{session_number}/{len(included)}] {meta['stem']}", flush=True)
        try:
            session = oa.read(meta["path"])

            # -- Y_stim (Panel A): real presented A/B at p1 --
            stim_table = _y_stim_table(session)
            for area in AREAS:
                if stim_table.empty:
                    continue
                X, units = _spike_matrix_from_onsets(
                    session, area, stim_table["start_time"].to_numpy(), REAL_STIM_WINDOW_MS
                )
                if X.shape[1] == 0:
                    continue
                labels = stim_table["label_int"].to_numpy(int)
                cycles = stim_table["cycle_id"].to_numpy(int)
                result = decode_binary_cycle_safe(X, labels, cycles, seed=seed, n_permutations=n_permutations)
                cell_rows.append({
                    "session": meta["stem"], "subject": meta["subject"], "area": area,
                    "population": POP, "target": "Y_stim", "position": "p1",
                    "fold_scheme": "leave_one_temporal_cycle_out",
                    "n_units": int(X.shape[1]), "n_trials_per_class": json.dumps(
                        {"A": int(np.sum(labels == 1)), "B": int(np.sum(labels == 0))}),
                    "status": result.get("status", "unknown"),
                    "accuracy_loco_balanced": result.get("accuracy_loco_balanced", np.nan),
                    "cross_entropy": np.nan,
                    "auc_loco": result.get("auc_loco", np.nan),
                    "p_permutation": result.get("p_permutation", np.nan),
                    "null_mean": result.get("null_mean", np.nan),
                    "null_sd": result.get("null_sd", np.nan),
                    "n_permutations": result.get("n_permutations", 0),
                    "n_folds": result.get("n_folds", 0),
                    "seed": seed, "feature_window_ms": json.dumps(list(REAL_STIM_WINDOW_MS)),
                    "estimator": json.dumps(ESTIMATOR, sort_keys=True),
                })

            # -- Y_omit (Panel C diagonal): per-slot 3-way softmax + SSA-based ablation (Panel H) --
            per_slot_softmax: dict[str, dict] = {}
            per_slot_table: dict[str, pd.DataFrame] = {}
            for slot_key in POSITIONS:
                table = _trial_table(session, slot_key)
                per_slot_table[slot_key] = table
                for area in AREAS:
                    if table.empty or table["cycle_id"].nunique() < 2:
                        continue
                    X, units = _spike_count_matrix(
                        session, area, table,
                        (OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
                         OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"]),
                    )
                    if X.shape[1] == 0:
                        continue
                    labels = table["label_int"].to_numpy(int)
                    cycles = table["cycle_id"].to_numpy(int)
                    result = decode_softmax_p4_cycle_safe(X, labels, cycles, seed=seed, n_permutations=n_permutations)
                    per_slot_softmax[(slot_key, area)] = {"result": result, "X": X, "labels": labels,
                                                            "cycles": cycles, "units": units}
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "population": POP, "target": "Y_omit", "position": slot_key,
                        "fold_scheme": "leave_one_temporal_cycle_out",
                        "n_units": int(X.shape[1]), "n_trials_per_class": json.dumps(
                            {"A": int(np.sum(labels == 0)), "B": int(np.sum(labels == 1)),
                             "R": int(np.sum(labels == 2))}),
                        "status": result.get("status", "unknown"),
                        "accuracy_loco_balanced": np.nan,
                        "cross_entropy": result.get("cross_entropy", np.nan),
                        "auc_loco": np.nan,
                        "p_permutation": result.get("p_permutation", np.nan),
                        "null_mean": result.get("null_mean", np.nan),
                        "null_sd": result.get("null_sd", np.nan),
                        "n_permutations": result.get("n_permutations", 0),
                        "n_folds": result.get("n_folds", 0),
                        "seed": seed,
                        "feature_window_ms": json.dumps(
                            [OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_onset_ms"],
                             OMISSION_IDENTITY_CONDITIONS[slot_key]["slot_end_ms"]]),
                        "estimator": json.dumps(SOFTMAX_ESTIMATOR, sort_keys=True),
                    })
                    # diagonal reuse into the cross-position table
                    crossposition_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "population": POP, "train_position": slot_key, "test_position": slot_key,
                        "source": "diagonal_reuse", "status": result.get("status", "unknown"),
                        "cross_entropy": result.get("cross_entropy", np.nan),
                        "p_permutation": result.get("p_permutation", np.nan),
                        "null_mean": result.get("null_mean", np.nan),
                        "null_sd": result.get("null_sd", np.nan),
                        "n_permutations": result.get("n_permutations", 0),
                        "n_train": np.nan, "n_test": int(X.shape[0]), "seed": seed,
                    })
                    if result.get("status") == "success":
                        for row in result["oof"].to_dict("records"):
                            proba_oof_rows.append({
                                "session": meta["stem"], "subject": meta["subject"], "area": area,
                                "population": POP, "target": "Y_omit", "position": slot_key, **row,
                            })

            # -- Panel F off-diagonal: cross-position generalization G_ij, i != j --
            for area in AREAS:
                for slot_i in POSITIONS:
                    cell_i = per_slot_softmax.get((slot_i, area))
                    if cell_i is None:
                        continue
                    for slot_j in POSITIONS:
                        if slot_i == slot_j:
                            continue
                        cell_j = per_slot_softmax.get((slot_j, area))
                        if cell_j is None:
                            continue
                        result = decode_cross_position(
                            cell_i["X"], cell_i["labels"], cell_i["cycles"],
                            cell_j["X"], cell_j["labels"],
                            seed=seed, n_permutations=n_permutations,
                        )
                        crossposition_rows.append({
                            "session": meta["stem"], "subject": meta["subject"], "area": area,
                            "population": POP, "train_position": slot_i, "test_position": slot_j,
                            "source": "trained", "status": result.get("status", "unknown"),
                            "cross_entropy": result.get("cross_entropy", np.nan),
                            "p_permutation": result.get("p_permutation", np.nan),
                            "null_mean": result.get("null_mean", np.nan),
                            "null_sd": result.get("null_sd", np.nan),
                            "n_permutations": result.get("n_permutations", 0),
                            "n_train": result.get("n_train", np.nan),
                            "n_test": result.get("n_test", np.nan), "seed": seed,
                        })

            # -- Y_pos (Panel E) & Y_prev (Panel G): shared cross-slot table + feature matrix --
            cross_table = _cross_slot_table(session)
            if not cross_table.empty and cross_table["cross_cycle_id"].nunique() >= 2:
                for area in AREAS:
                    X, units = _spike_matrix_from_onsets(
                        session, area, cross_table["effective_onset_s"].to_numpy(), POSITION_WINDOW_MS
                    )
                    if X.shape[1] == 0:
                        continue
                    cycles = cross_table["cross_cycle_id"].to_numpy(int)
                    X_centered = _center_within_cycle(X, cycles)

                    pos_labels = cross_table["position_int"].to_numpy(int)
                    pos_result = decode_multiclass_balanced_cycle_safe(
                        X_centered, pos_labels, cycles, n_classes=3, seed=seed, n_permutations=n_permutations,
                    )
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "population": POP, "target": "Y_pos", "position": "p2_p3_p4",
                        "fold_scheme": "leave_one_temporal_cycle_out",
                        "n_units": int(X.shape[1]), "n_trials_per_class": json.dumps(
                            {p: int(np.sum(pos_labels == i)) for p, i in POSITION_INT.items()}),
                        "status": pos_result.get("status", "unknown"),
                        "accuracy_loco_balanced": pos_result.get("accuracy_loco_balanced", np.nan),
                        "cross_entropy": np.nan, "auc_loco": np.nan,
                        "p_permutation": pos_result.get("p_permutation", np.nan),
                        "null_mean": pos_result.get("null_mean", np.nan),
                        "null_sd": pos_result.get("null_sd", np.nan),
                        "n_permutations": pos_result.get("n_permutations", 0),
                        "n_folds": pos_result.get("n_folds", 0),
                        "seed": seed, "feature_window_ms": json.dumps(list(POSITION_WINDOW_MS)),
                        "estimator": json.dumps(SOFTMAX_ESTIMATOR, sort_keys=True),
                        "note": "per_cycle_centered_cross_slot_cycles",
                    })

                    prev_labels = cross_table["preceding_int"].to_numpy(int)
                    prev_result = decode_binary_cycle_safe(
                        X, prev_labels, cycles, seed=seed, n_permutations=n_permutations,
                    )
                    cell_rows.append({
                        "session": meta["stem"], "subject": meta["subject"], "area": area,
                        "population": POP, "target": "Y_prev", "position": "p2_p3_p4_pooled",
                        "fold_scheme": "leave_one_temporal_cycle_out",
                        "n_units": int(X.shape[1]), "n_trials_per_class": json.dumps(
                            {"A": int(np.sum(prev_labels == 1)), "B": int(np.sum(prev_labels == 0))}),
                        "status": prev_result.get("status", "unknown"),
                        "accuracy_loco_balanced": prev_result.get("accuracy_loco_balanced", np.nan),
                        "cross_entropy": np.nan,
                        "auc_loco": prev_result.get("auc_loco", np.nan),
                        "p_permutation": prev_result.get("p_permutation", np.nan),
                        "null_mean": prev_result.get("null_mean", np.nan),
                        "null_sd": prev_result.get("null_sd", np.nan),
                        "n_permutations": prev_result.get("n_permutations", 0),
                        "n_folds": prev_result.get("n_folds", 0),
                        "seed": seed, "feature_window_ms": json.dumps(list(POSITION_WINDOW_MS)),
                        "estimator": json.dumps(ESTIMATOR, sort_keys=True),
                    })

            # -- Panel H: SSA index + ablation, per (area, slot) --
            ssa_table = _ssa_trial_table(session)
            for area in AREAS:
                ssa_here = compute_ssa_index(session, area, ssa_table)
                if not ssa_here.empty:
                    rows = ssa_here.copy()
                    rows.insert(0, "area", area)
                    rows.insert(0, "subject", meta["subject"])
                    rows.insert(0, "session", meta["stem"])
                    ssa_rows.extend(rows.to_dict("records"))
                    # pooled-across-slot |SSA| ranking for this (session, area), by unit_row
                    pooled = ssa_here.groupby("unit_row")["ssa_index"].apply(lambda s: np.mean(np.abs(s)))
                    for slot_key in POSITIONS:
                        cell = per_slot_softmax.get((slot_key, area))
                        if cell is None:
                            continue
                        unit_row_by_col = {i: row_index for i, row_index in enumerate(cell["units"].index)}
                        ranked_cols = sorted(
                            (c for c in range(cell["X"].shape[1]) if unit_row_by_col[c] in pooled.index),
                            key=lambda c: pooled.loc[unit_row_by_col[c]], reverse=True,
                        )
                        if len(ranked_cols) < cell["X"].shape[1]:
                            # units with no SSA estimate (e.g. too few trials) sort last, never
                            # preferentially removed as "top |SSA|"
                            ranked_cols += [c for c in range(cell["X"].shape[1]) if c not in ranked_cols]
                        ablation_result = run_ablation(
                            cell["X"], cell["labels"], cell["cycles"], ranked_cols,
                            seed=seed, n_permutations=n_permutations, n_draws=ablation_draws,
                        )
                        ablation_rows.append({
                            "session": meta["stem"], "subject": meta["subject"], "area": area,
                            "population": POP, "slot_key": slot_key, "seed": seed,
                            **ablation_result,
                        })

        except Exception as exc:
            errors.append({"session": meta["stem"], "reason": type(exc).__name__, "detail": str(exc)})
            print(f"  ERROR {type(exc).__name__}: {exc}", flush=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cells": output_dir / "fig04_encoding_matrix_cells.csv",
        "proba_oof": output_dir / "fig04_encoding_matrix_proba_oof.csv",
        "crossposition": output_dir / "fig04_encoding_matrix_crossposition.csv",
        "ablation": output_dir / "fig04_encoding_matrix_ablation.csv",
        "ssa": output_dir / "fig04_encoding_matrix_ssa.csv",
    }
    pd.DataFrame(cell_rows).to_csv(outputs["cells"], index=False)
    pd.DataFrame(proba_oof_rows).to_csv(outputs["proba_oof"], index=False)
    pd.DataFrame(crossposition_rows).to_csv(outputs["crossposition"], index=False)
    pd.DataFrame(ablation_rows).to_csv(outputs["ablation"], index=False)
    pd.DataFrame(ssa_rows).to_csv(outputs["ssa"], index=False)

    receipt = {
        "analysis_status": "complete" if not errors else "failed_with_errors",
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "git_sha": __import__("subprocess").check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "nwb_dir": str(nwb_dir),
        "readiness_csv": str(readiness_csv),
        "eligible_sessions": included,
        "excluded_sessions": excluded,
        "seed": seed,
        "n_permutations_requested": n_permutations,
        "ablation_draws": ablation_draws,
        "populations_computed": ["all_units"],
        "populations_pending": [
            "S+", "S-", "O+", "O++", "Other", "stimulus_responsive", "omission_responsive",
            "adaptation_high", "adaptation_low",
        ],
        "estimator_binary": ESTIMATOR,
        "estimator_softmax": SOFTMAX_ESTIMATOR,
        "fold_scheme": "leave_one_temporal_cycle_out",
        "targets": {
            "Y_stim": "presented A/B identity at p1, positive control; R excluded (no real "
                      "p1 identity by construction, asserted at runtime)",
            "Y_omit": "3-way [p_A,p_B,p_R] softmax, fit independently per slot (p2/p3/p4)",
            "Y_pos": "3-way p2/p3/p4 position decode, per-cycle centered, cross-slot cycle grouping",
            "Y_prev": "binary preceding-real-stimulus identity decoded from omission-slot activity",
        },
        "real_stim_window_ms": list(REAL_STIM_WINDOW_MS),
        "position_window_ms": list(POSITION_WINDOW_MS),
        "cross_position_matrix": "diagonal reused from Y_omit; off-diagonal trained on all of "
                                  "slot i (balanced, no CV split), evaluated on all of slot j",
        "ablation_definition": "top-decile |pooled SSA index| units removed vs n_draws random "
                                "same-size removals; cross-entropy on Y_omit's per-slot softmax",
        "signal": "SPK/SUA only",
        "errors": errors,
        "runtime_seconds": time.time() - started,
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "output_paths": {key: str(path) for key, path in outputs.items()},
    }
    receipt_path = output_dir / "fig04_encoding_matrix_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Completed {len(included)} eligible sessions, {len(cell_rows)} cells, "
        f"{len(crossposition_rows)} cross-position rows, {len(ablation_rows)} ablation rows "
        f"in {receipt['runtime_seconds']:.1f}s.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path,
                        default=OA_ROOT / "artifacts" / "data" / "session_readiness.csv")
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--output-dir", type=Path, default=OA_ROOT / "outputs" / "classification")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--ablation-draws", type=int, default=DEFAULT_ABLATION_DRAWS)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(
            f"NWB directory not found: {args.nwb_dir}; pass --nwb-dir or set OMISSION_NWB_DIR"
        )
    run(readiness_csv=args.readiness, nwb_dir=args.nwb_dir, output_dir=args.output_dir,
        seed=args.seed, n_permutations=args.permutations, ablation_draws=args.ablation_draws,
        limit=args.limit)


if __name__ == "__main__":
    main()
