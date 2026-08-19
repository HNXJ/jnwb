"""Milestone 1 infrastructure for Structured Identity Experiment v1.

This module contains no model fitting.  It materializes the frozen experiment's ontology,
grouped fold geometry, representation contracts, and exchangeability-matched null plans.
Training remains explicitly unauthorized until the Milestone 1 receipt is reviewed.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import pandas as pd

from .omission_identity import OMISSION_IDENTITY_CONDITIONS, detect_trial_cycles
from jnwb.permutation import permute_labels
from .trial_ontology import CONDITION_ONTOLOGY, build_trial_ontology

SPEC_VERSION = "structured-identity-experiment-v1"
MILESTONE = 1
SIGNOFF_STATUS = "APPROVED"
TRAINING_AUTHORIZED = False
MAIN_ANALYSIS = "omitted_expected_identity"
POSITIVE_CONTROL = "presented_identity_positive_control"
TARGET_COLUMNS = (
    "expected_identity",
    "preceding_identity",
    "omission_position",
    "sequence_family",
)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "1.0", "true", "yes"}
    return bool(value)


def _subject_session(session) -> tuple[str | None, str | None]:
    path = getattr(session, "nwb_path", None)
    session_name = Path(path).stem if path is not None else None
    metadata = getattr(session, "_metadata", None)
    subject = metadata.get("subject_id") if isinstance(metadata, Mapping) else None
    if not subject and session_name and session_name.startswith("sub-"):
        subject = session_name.split("_", 1)[0].removeprefix("sub-")
    return subject, session_name


def _append_positive_control_rows(session, rows: list[dict], trial_counter: int) -> int:
    """Append canonical AAAB/BBBA p1 trials for the presented-identity control."""
    subject, session_name = _subject_session(session)
    pieces = []
    for condition in ("AAAB", "BBBA"):
        epochs = session.get_epochs(phase=2, condition=condition, correct_only=False)
        if len(epochs) == 0:
            continue
        part = epochs[["start_time"]].copy()
        part["condition"] = condition
        part["correct_trial"] = pd.to_numeric(
            epochs.get("correct", pd.Series(True, index=epochs.index)), errors="coerce"
        ).fillna(0).eq(1.0).to_numpy()
        pieces.append(part)
    if not pieces:
        return trial_counter
    table = pd.concat(pieces, ignore_index=True)
    table["start_time"] = pd.to_numeric(table["start_time"], errors="coerce")
    table = table.dropna(subset=["start_time"]).reset_index(drop=True)
    table["cycle"] = detect_trial_cycles(table)
    condition_indices = {condition: 0 for condition in ("AAAB", "BBBA")}
    for _, row in table.iterrows():
        condition = str(row["condition"])
        onto = CONDITION_ONTOLOGY[condition]
        condition_index = condition_indices[condition]
        condition_indices[condition] += 1
        trial_counter += 1
        rows.append(
            {
                "trial_id": trial_counter,
                "subject": subject,
                "session": session_name,
                "analysis": POSITIVE_CONTROL,
                "slot_key": "p1",
                "cycle": int(row["cycle"]),
                "condition": condition,
                "condition_trial_index": condition_index,
                "sequence_family": onto["sequence_family"],
                "omission_position": onto["omission_position"],
                "preceding_identity": onto["preceding_identity"],
                "expected_identity": onto["expected_identity"],
                "presented_identity": onto["presented_identity"],
                "correct_trial": _as_bool(row["correct_trial"]),
                "start_time": float(row["start_time"]),
                "eligible_candidate": bool(_as_bool(row["correct_trial"])),
                "eligible": bool(_as_bool(row["correct_trial"])),
            }
        )
    return trial_counter


def build_canonical_trial_table(
    session, slot_keys: tuple[str, ...] = ("p2", "p3", "p4")
) -> pd.DataFrame:
    """Build the canonical experiment table from ``omission.jnwb_ext.trial_ontology``.

    The omission analysis uses only correct A/B-family omission trials with a non-null
    ``expected_identity``.  R-family rows are retained as diagnostics and are never silently
    relabeled as an identity target.  Presented AAAB/BBBA trials are added as a separate positive
    control using the same ontology constants.
    """
    ontology = build_trial_ontology(session, slot_keys=slot_keys, families=("A", "B", "R"))
    rows: list[dict] = []
    trial_counter = 0
    if not ontology.empty:
        for row in ontology.to_dict("records"):
            trial_counter += 1
            is_main = (
                _as_bool(row.get("correct_trial"))
                and row.get("sequence_family") in {"A", "B"}
                and pd.notna(row.get("expected_identity"))
            )
            rows.append(
                {
                    **row,
                    "analysis": MAIN_ANALYSIS,
                    "condition_trial_index": int(
                        sum(
                            1
                            for prior in rows
                            if prior.get("analysis") == MAIN_ANALYSIS
                            and prior.get("slot_key") == row["slot_key"]
                            and prior.get("condition") == row["condition"]
                        )
                    ),
                    "eligible_candidate": bool(is_main),
                    "eligible": bool(is_main),
                }
            )
    trial_counter = _append_positive_control_rows(session, rows, trial_counter)
    if not rows:
        return pd.DataFrame(
            columns=[
                "trial_id", "subject", "session", "analysis", "slot_key", "cycle", "condition",
                "condition_trial_index", "sequence_family", "omission_position",
                "preceding_identity", "expected_identity", "presented_identity", "correct_trial",
                "start_time", "eligible_candidate", "eligible", "n_cycles", "eligibility_reason",
            ]
        )
    table = pd.DataFrame(rows)
    table["trial_id"] = table["trial_id"].astype(int)
    table["cycle"] = table["cycle"].astype(int)
    table["correct_trial"] = table["correct_trial"].map(_as_bool)
    candidate_cycles = (
        table[table["eligible_candidate"]]
        .groupby(["session", "analysis", "slot_key"], dropna=False)["cycle"]
        .nunique()
        .rename("n_cycles")
    )
    table = table.join(
        candidate_cycles,
        on=["session", "analysis", "slot_key"],
    )
    table["n_cycles"] = table["n_cycles"].fillna(0).astype(int)
    table["eligible"] = table["eligible_candidate"] & table["n_cycles"].ge(2)
    table["eligibility_reason"] = np.select(
        [
            ~table["correct_trial"],
            table["eligible_candidate"] & table["n_cycles"].lt(2),
            table["analysis"].eq(MAIN_ANALYSIS) & table["sequence_family"].eq("R"),
            table["eligible"],
        ],
        ["incorrect_trial", "insufficient_cycles", "non_identity_family", "eligible"],
        default="not_primary_target",
    )
    return table.sort_values(["analysis", "slot_key", "cycle", "start_time", "trial_id"]).reset_index(
        drop=True
    )


def assign_outer_folds(
    trials: pd.DataFrame,
    *,
    analysis_cols: tuple[str, ...] = ("session", "analysis", "slot_key"),
    group_col: str = "cycle",
) -> pd.DataFrame:
    """Assign deterministic leave-one-group-out outer folds without touching features."""
    required = set(analysis_cols) | {group_col, "trial_id"}
    missing = required.difference(trials.columns)
    if missing:
        raise ValueError(f"trial table missing fold columns: {sorted(missing)}")
    out = trials.copy()
    out["outer_fold"] = -1
    out["outer_group"] = out[group_col]
    out["outer_fold_status"] = "unassigned"
    for _, index in out.groupby(list(analysis_cols), sort=True, dropna=False).groups.items():
        groups = sorted(out.loc[index, group_col].unique().tolist())
        if len(groups) < 2:
            out.loc[index, "outer_fold_status"] = "insufficient_groups"
            continue
        mapping = {group: fold for fold, group in enumerate(groups)}
        out.loc[index, "outer_fold"] = out.loc[index, group_col].map(mapping).astype(int)
        out.loc[index, "outer_fold_status"] = "valid"
    return out


def build_inner_validation_partitions(
    outer_trials: pd.DataFrame,
    *,
    analysis_cols: tuple[str, ...] = ("session", "analysis", "slot_key"),
) -> pd.DataFrame:
    """Build nested inner train/validation partitions from outer-training groups.

    The outer test group is never used in an inner partition.  If only one training group
    remains, an explicit ``insufficient_training_groups`` row is emitted instead of inventing a
    validation split.
    """
    rows: list[dict] = []
    for key, group in outer_trials.groupby(list(analysis_cols), sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        key_values = dict(zip(analysis_cols, key))
        for outer_fold in sorted(group["outer_fold"].unique()):
            train = group[group["outer_fold"] != outer_fold]
            train_groups = sorted(train["outer_group"].unique().tolist())
            if len(train_groups) < 2:
                rows.append(
                    {
                        **key_values,
                        "outer_fold": int(outer_fold),
                        "inner_fold": -1,
                        "trial_id": -1,
                        "inner_role": "insufficient_training_groups",
                        "inner_group": None,
                        "trial_group": None,
                        "validation_group": None,
                    }
                )
                continue
            for inner_fold, inner_group in enumerate(train_groups):
                for _, trial in train.iterrows():
                    rows.append(
                        {
                            **key_values,
                            "outer_fold": int(outer_fold),
                            "inner_fold": int(inner_fold),
                            "trial_id": int(trial["trial_id"]),
                            "inner_role": (
                                "inner_validation"
                                if trial["outer_group"] == inner_group
                                else "inner_train"
                            ),
                            "inner_group": int(inner_group),
                            "trial_group": int(trial["outer_group"]),
                            "validation_group": int(inner_group),
                        }
                    )
    return pd.DataFrame(rows)


def build_representation_ladder(
    raster: np.ndarray,
    *,
    modality: str = "SPK",
    spatial_axis_metadata: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Return R0/R1/R2 contracts without fitting a model.

    ``raster`` is `(n_trials, n_space, n_time)` with an explicit time axis.  R0 collapses time;
    R1 vectorizes without discarding samples; R2 preserves the tensor and records the topology
    constraint.  SPK units are unordered unless metadata supplies a preregistered order.
    """
    x = np.asarray(raster)
    if x.ndim != 3:
        raise ValueError("raster must have shape (n_trials, n_space, n_time)")
    if not np.isfinite(x).all():
        raise ValueError("raster contains NaN or Inf")
    modality = modality.upper()
    if modality not in {"SPK", "LFP"}:
        raise ValueError("modality must be 'SPK' or 'LFP'")
    if modality == "LFP" and spatial_axis_metadata is None:
        raise ValueError("LFP R2 requires explicit channel/probe spatial metadata")
    if modality == "SPK":
        topology = (
            "metadata_ordered_units"
            if spatial_axis_metadata is not None
            else "unordered_units_permutation_equivariant_required"
        )
    else:
        topology = "channel_probe_order_from_metadata"
    return {
        "X_rate": np.mean(x, axis=2, dtype=np.float64),
        "X_vec": x.reshape(x.shape[0], -1),
        "X_structured": x.copy(),
        "contract": {
            "modality": modality,
            "input_shape": list(x.shape),
            "r0": "X_rate: temporal aggregation; information may be discarded",
            "r1": "X_vec: bijective vectorization of the selected raster",
            "r2": "X_structured: preserved space x time organization",
            "space_axis_topology": topology,
            "vectorization_order": "C: space-major then time within each trial",
            "dtype": str(x.dtype),
            "training_authorized": False,
        },
    }


def build_permutation_plan(
    labels: Iterable[object],
    groups: Iterable[object],
    *,
    n_permutations: int,
    seed: int,
) -> dict[str, object]:
    """Create an explicit within-group null plan; no model fitting occurs."""
    y = np.asarray(list(labels))
    group_array = np.asarray(list(groups))
    if y.ndim != 1 or group_array.shape != y.shape:
        raise ValueError("labels and groups must be one-dimensional and equally sized")
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    draws = []
    for permutation in range(n_permutations):
        draw_seed = int(seed + permutation)
        permuted = permute_labels(
            y,
            groups=group_array,
            scheme="within_group",
            rng=np.random.default_rng(draw_seed),
        )
        digest = hashlib.sha256(np.ascontiguousarray(permuted).tobytes()).hexdigest()
        draws.append(
            {
                "permutation": permutation,
                "seed": draw_seed,
                "label_digest": digest,
                "n_samples": int(len(y)),
                "n_groups": int(len(np.unique(group_array))),
            }
        )
    return {
        "draw_manifest": pd.DataFrame(draws),
        "scheme": "within_group",
        "seed": int(seed),
        "n_permutations": int(n_permutations),
        "group_composition_preserved": True,
    }


def build_milestone_receipt(
    *,
    git_sha: str,
    session_manifest: list[dict],
    excluded_sessions: list[dict],
    output_paths: dict[str, str],
    counts: dict[str, int],
    null_scheme: str,
    n_permutations: int,
    seed: int,
) -> dict:
    """Build the machine-readable gate receipt; it explicitly records no model training."""
    return {
        "schema_version": 3,
        "experiment": SPEC_VERSION,
        "milestone": MILESTONE,
        "scientific_signoff": SIGNOFF_STATUS,
        "training_authorized": TRAINING_AUTHORIZED,
        "models_trained": [],
        "git_sha": git_sha,
        "python": sys.version,
        "platform": platform.platform(),
        "session_manifest": session_manifest,
        "excluded_sessions": excluded_sessions,
        "counts": counts,
        "representations": {
            "R0": "X_rate: temporal/rate collapse",
            "R1": "X_vec: bijective vectorization of X_raster",
            "R2": "X_structured: preserved space x time; SPK unit axis unordered by default",
        },
        "targets": {
            "primary": "expected_identity",
            "confounds": [
                "preceding_identity",
                "omission_position",
                "sequence_family",
            ],
            "grouping_variable": "cycle",
            "positive_control": "presented_identity",
        },
        "estimator_parameters": {
            "status": "not_fitted_milestone_1",
            "M0": "permutation/chance baseline contract only",
            "M1": "regularized linear decoder; hyperparameters must be selected inside inner folds",
            "M2": "not authorized before Milestone 1 review",
            "M3": "not authorized before Milestone 1 review",
            "M4": "not authorized before Milestone 1 review",
        },
        "outer_folds": "leave-one-cycle-out, deterministic cycle ordering",
        "inner_validation": "leave-one-training-cycle-out partitions; no outer-test reuse",
        "null": {
            "scheme": null_scheme,
            "n_permutations": int(n_permutations),
            "seed": int(seed),
            "primitive": "jnwb.permutation.permute_labels",
        },
        "output_paths": output_paths,
        "stop_rule": "review tensors, folds, balance, nuisance targets, and null before M2/M3 training",
    }
