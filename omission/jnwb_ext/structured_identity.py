"""Milestone 1 infrastructure for Structured Identity Experiment v1.

This module contains no model fitting.  It materializes the frozen experiment's ontology,
grouped fold geometry, representation contracts, and exchangeability-matched null plans.
Training remains explicitly unauthorized until the Milestone 1 receipt is reviewed.
"""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd

from .omission_identity import OMISSION_IDENTITY_CONDITIONS, detect_trial_cycles
from jnwb.permutation import build_permutation_plan
from jnwb.decoding import (
    assign_outer_folds,
    build_inner_validation_partitions,
    build_representation_ladder,
)
from .trial_ontology import CONDITION_ONTOLOGY, build_trial_ontology

# assign_outer_folds, build_inner_validation_partitions, build_representation_ladder, and
# build_permutation_plan PROMOTED 2026-08-23 to jnwb.decoding / jnwb.permutation
# (99%-jnwb-sufficiency normalization) -- re-imported here under their original names so no
# call site in this module or its callers needs to change.

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
