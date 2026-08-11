#!/usr/bin/env python3
"""Decompose the persisted Milestone 2A diagnostics without retraining.

This script reads only the Milestone 2A cell, OOF, fold, and null artifacts.  It does not load
NWB files and does not fit a model.  The continuous score output is a signed ridge decision
score, not a calibrated probability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_2a"
)
DEFAULT_OUTPUT = DEFAULT_INPUT / "diagnostic_review"
PRIMARY = "omission_reversal"
POSITIVE = "presented_identity_positive_control"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _metrics(group: pd.DataFrame, primary: bool) -> dict[str, float]:
    expected = group["y_expected"].to_numpy(dtype=int)
    prediction = group["prediction"].to_numpy(dtype=int)
    result = {
        "n_oof_trials": int(len(group)),
        "accuracy_expected": float(np.mean(prediction == expected)),
        "balanced_accuracy_expected": float(
            np.mean(
                [
                    np.mean(prediction[expected == value] == value)
                    for value in (0, 1)
                    if np.any(expected == value)
                ]
            )
        ),
        "signed_evidence_expected": float(
            np.mean((2 * expected - 1) * group["decision_score"].to_numpy(float))
        ),
        "decision_score_mean": float(group["decision_score"].mean()),
        "decision_score_sd": float(group["decision_score"].std(ddof=1)),
    }
    if primary:
        previous = group["y_previous"].to_numpy(dtype=int)
        result.update(
            {
                "accuracy_previous": float(np.mean(prediction == previous)),
                "balanced_accuracy_previous": float(
                    np.mean(
                        [
                            np.mean(prediction[previous == value] == value)
                            for value in (0, 1)
                            if np.any(previous == value)
                        ]
                    )
                ),
                "signed_evidence_previous": float(
                    np.mean(
                        (2 * previous - 1)
                        * group["decision_score"].to_numpy(float)
                    )
                ),
            }
        )
        result["G_accuracy"] = (
            result["accuracy_expected"] - result["accuracy_previous"]
        )
        result["G_balanced"] = (
            result["balanced_accuracy_expected"]
            - result["balanced_accuracy_previous"]
        )
    return result


def _null_percentile(null_values: np.ndarray, observed: float) -> float:
    if len(null_values) == 0 or not np.isfinite(observed):
        return float("nan")
    return float((np.sum(null_values <= observed) + 1) / (len(null_values) + 1))


def _group_metrics(
    oof: pd.DataFrame, keys: list[str], primary: bool
) -> pd.DataFrame:
    rows = []
    for key, group in oof.groupby(keys, sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        rows.append({**dict(zip(keys, key)), **_metrics(group, primary)})
    return pd.DataFrame(rows)


def _leave_one_session_out(oof: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sessions = sorted(oof["session"].unique().tolist())
    for left_out in sessions:
        remaining = oof[oof["session"] != left_out]
        scopes = [("all_areas", remaining)]
        for area in sorted(oof["area"].unique()):
            area_sessions = set(oof.loc[oof["area"] == area, "session"])
            if left_out in area_sessions:
                scopes.append(
                    (f"area:{area}", remaining[remaining["area"] == area])
                )
        for scope, scoped in scopes:
            for representation, group in scoped.groupby(
                "representation", sort=True
            ):
                if group.empty:
                    continue
                rows.append(
                    {
                        "analysis": PRIMARY,
                        "scope": scope,
                        "left_out_session": left_out,
                        "representation": representation,
                        "n_sessions_remaining": int(
                            group["session"].nunique()
                        ),
                        "n_subjects_remaining": int(group["subject"].nunique()),
                        **_metrics(group, True),
                    }
                )
    return pd.DataFrame(rows)


def run(input_dir: Path, output_dir: Path) -> dict:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    required = {
        "cells": input_dir / "milestone_2a_cells.csv",
        "oof": input_dir / "milestone_2a_oof_predictions.csv",
        "folds": input_dir / "milestone_2a_fold_diagnostics.csv",
        "null": input_dir / "milestone_2a_null_distribution.csv",
        "receipt": input_dir / "milestone_2a_receipt.json",
    }
    for path in required.values():
        if not path.exists():
            raise FileNotFoundError(path)
    source_receipt = json.loads(required["receipt"].read_text(encoding="utf-8"))
    if source_receipt.get("analysis_status") != "complete":
        raise RuntimeError("source Milestone 2A receipt is not complete")

    cells = pd.read_csv(required["cells"])
    oof = pd.read_csv(required["oof"])
    folds = pd.read_csv(required["folds"])
    null = pd.read_csv(required["null"])
    if (cells["status"] != "success").any():
        raise RuntimeError("diagnostic input contains unsuccessful cells")

    primary_oof = oof[oof["analysis"] == PRIMARY].copy()
    positive_oof = oof[oof["analysis"] == POSITIVE].copy()
    primary_cells = cells[cells["analysis"] == PRIMARY].copy()
    positive_cells = cells[cells["analysis"] == POSITIVE].copy()
    primary_null = null[null["analysis"] == PRIMARY]
    positive_null = null[null["analysis"] == POSITIVE]

    group_keys = ["session", "subject", "area", "representation"]
    cell_rows = []
    for record in primary_cells.to_dict("records"):
        key_mask = np.ones(len(primary_oof), dtype=bool)
        for key in group_keys:
            key_mask &= primary_oof[key].eq(record[key]).to_numpy()
        group = primary_oof.loc[key_mask]
        null_mask = np.ones(len(primary_null), dtype=bool)
        for key in group_keys:
            null_mask &= primary_null[key].eq(record[key]).to_numpy()
        null_values = primary_null.loc[null_mask, "null_metric"].to_numpy(float)
        pos = positive_cells[
            (positive_cells["session"] == record["session"])
            & (positive_cells["subject"] == record["subject"])
            & (positive_cells["area"] == record["area"])
            & (positive_cells["representation"] == record["representation"])
        ]
        pos_null = positive_null[
            (positive_null["session"] == record["session"])
            & (positive_null["subject"] == record["subject"])
            & (positive_null["area"] == record["area"])
            & (positive_null["representation"] == record["representation"])
        ]
        row = {
            "analysis": PRIMARY,
            **{key: record[key] for key in group_keys},
            "test_position": "p4",
            "trial_N": int(len(group)),
            "eligible_trial_N": int(record["n_trials"]),
            "held_out_trial_N": int(len(group)),
            "outer_fold_N": int(record["n_outer_folds"]),
            "R0_R1_pair_available": False,
            "G": float(record["G_balanced"]),
            "A_expected": float(record["balanced_accuracy_expected"]),
            "A_previous": float(record["balanced_accuracy_previous"]),
            "G_null_p_two_sided": float(record["p_two_sided"]),
            "G_null_percentile": _null_percentile(
                null_values, float(record["G_balanced"])
            ),
            "continuous_signed_evidence_expected": float(
                np.mean(
                    (2 * group["y_expected"].to_numpy(int) - 1)
                    * group["decision_score"].to_numpy(float)
                )
            ),
            "continuous_score_is_calibrated_probability": False,
            "positive_control_accuracy": float(
                pos.iloc[0]["balanced_accuracy_expected"]
            )
            if not pos.empty
            else np.nan,
            "positive_control_null_p_two_sided": float(
                pos.iloc[0]["p_two_sided"]
            )
            if not pos.empty
            else np.nan,
            "positive_control_null_percentile": _null_percentile(
                pos_null["null_metric"].to_numpy(float),
                float(pos.iloc[0]["balanced_accuracy_expected"]),
            )
            if not pos.empty
            else np.nan,
        }
        cell_rows.append(row)
    cell_diagnostic = pd.DataFrame(cell_rows)

    paired = (
        cell_diagnostic.pivot_table(
            index=["session", "subject", "area", "test_position"],
            columns="representation",
            values=[
                "trial_N",
                "eligible_trial_N",
                "held_out_trial_N",
                "outer_fold_N",
                "A_expected",
                "A_previous",
                "G",
                "G_null_p_two_sided",
                "G_null_percentile",
                "positive_control_accuracy",
                "positive_control_null_p_two_sided",
                "positive_control_null_percentile",
                "continuous_signed_evidence_expected",
            ],
            aggfunc="first",
        )
        .reset_index()
    )
    paired.columns = [
        "_".join(str(part) for part in column if part != "").rstrip("_")
        if isinstance(column, tuple)
        else str(column)
        for column in paired.columns
    ]
    if "G_R0" in paired and "G_R1" in paired:
        paired["Delta_temporal_R1_minus_R0"] = paired["G_R1"] - paired["G_R0"]
        paired["R0_R1_pair_available"] = True
    else:
        paired["R0_R1_pair_available"] = False

    session_summary = _group_metrics(
        primary_oof, ["session", "subject", "representation"], True
    )
    area_summary = _group_metrics(
        primary_oof, ["area", "representation"], True
    )
    label_stratum = _group_metrics(
        primary_oof,
        ["session", "subject", "area", "representation", "y_expected"],
        True,
    )
    label_stratum["test_position"] = "p4"
    position_summary = pd.DataFrame(
        [
            {
                "analysis": PRIMARY,
                "omission_position": "p4",
                "n_oof_trials": int(len(primary_oof)),
                "n_sessions": int(primary_oof["session"].nunique()),
                "note": "position is fixed by the approved reversal design; no cross-position comparison is available in this primary test",
            }
        ]
    )
    continuous = _group_metrics(
        primary_oof, ["session", "subject", "area", "representation"], True
    )
    continuous = continuous[
        [
            "session",
            "subject",
            "area",
            "representation",
            "n_oof_trials",
            "signed_evidence_expected",
            "signed_evidence_previous",
            "decision_score_mean",
            "decision_score_sd",
        ]
    ]
    positive_summary = _group_metrics(
        positive_oof, ["session", "subject", "area", "representation"], False
    )
    positive_summary = positive_summary.rename(
        columns={
            "n_oof_trials": "trial_N",
            "balanced_accuracy_expected": "presented_accuracy",
            "auc_expected": "presented_auc",
            "signed_evidence_expected": "presented_signed_evidence",
        }
    )
    positive_summary["null_p_two_sided"] = np.nan
    positive_summary["null_percentile"] = np.nan
    for key, group in positive_null.groupby(group_keys, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        mask = np.ones(len(positive_summary), dtype=bool)
        for column, value in zip(group_keys, key):
            mask &= positive_summary[column].eq(value).to_numpy()
        positive_summary.loc[mask, "null_percentile"] = _null_percentile(
            group["null_metric"].to_numpy(float),
            float(positive_summary.loc[mask, "presented_accuracy"].iloc[0]),
        )
        cell = positive_cells
        for column, value in zip(group_keys, key):
            cell = cell[cell[column] == value]
        positive_summary.loc[mask, "null_p_two_sided"] = float(
            cell["p_two_sided"].iloc[0]
        )

    leave_one_out = _leave_one_session_out(primary_oof)
    leave_paired = (
        leave_one_out.pivot_table(
            index=["scope", "left_out_session"],
            columns="representation",
            values=[
                "balanced_accuracy_expected",
                "balanced_accuracy_previous",
                "G_balanced",
                "signed_evidence_expected",
                "n_oof_trials",
            ],
            aggfunc="first",
        )
        .reset_index()
    )
    leave_paired.columns = [
        "_".join(str(part) for part in column if part != "").rstrip("_")
        if isinstance(column, tuple)
        else str(column)
        for column in leave_paired.columns
    ]
    if "G_balanced_R0" in leave_paired and "G_balanced_R1" in leave_paired:
        leave_paired["Delta_temporal_R1_minus_R0"] = (
            leave_paired["G_balanced_R1"] - leave_paired["G_balanced_R0"]
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cell_diagnostic": output_dir / "cell_diagnostic.csv",
        "paired_cell_temporal_delta": output_dir / "paired_cell_temporal_delta.csv",
        "session_summary": output_dir / "session_summary.csv",
        "area_summary": output_dir / "area_summary.csv",
        "positive_control_summary": output_dir / "positive_control_summary.csv",
        "label_stratum_summary": output_dir / "label_stratum_summary.csv",
        "position_summary": output_dir / "position_summary.csv",
        "continuous_score_summary": output_dir / "continuous_score_summary.csv",
        "leave_one_session_out": output_dir / "leave_one_session_out.csv",
        "leave_one_session_out_paired": output_dir / "leave_one_session_out_paired.csv",
        "fold_diagnostic": output_dir / "fold_diagnostic.csv",
    }
    cell_diagnostic.to_csv(outputs["cell_diagnostic"], index=False)
    paired.to_csv(outputs["paired_cell_temporal_delta"], index=False)
    session_summary.to_csv(outputs["session_summary"], index=False)
    area_summary.to_csv(outputs["area_summary"], index=False)
    positive_summary.to_csv(outputs["positive_control_summary"], index=False)
    label_stratum.to_csv(outputs["label_stratum_summary"], index=False)
    position_summary.to_csv(outputs["position_summary"], index=False)
    continuous.to_csv(outputs["continuous_score_summary"], index=False)
    leave_one_out.to_csv(outputs["leave_one_session_out"], index=False)
    leave_paired.to_csv(outputs["leave_one_session_out_paired"], index=False)
    folds.to_csv(outputs["fold_diagnostic"], index=False)

    receipt = {
        "schema_version": 3,
        "experiment": "structured-identity-experiment-v1.1",
        "milestone": "2A_diagnostic_review",
        "status": "complete",
        "training_performed": False,
        "input_receipt": str(required["receipt"].relative_to(REPO_ROOT)).replace(
            "\\", "/"
        ),
        "input_hashes": {
            key: _sha256(path) for key, path in required.items()
        },
        "diagnostics": {
            "paired_cell_quantity": "Delta_temporal_R1_minus_R0 = G_R1 - G_R0",
            "primary_test_position": "p4",
            "position_decomposition_limit": "The approved primary reversal design fixes the held-out test position at p4; position is not an independent decomposition factor.",
            "continuous_score": "decision_score signed toward class B; continuous_signed_evidence_expected=(2*y_expected-1)*decision_score",
            "continuous_score_is_calibrated_probability": False,
            "decision_metric_remains": "G_balanced; continuous score is secondary only",
            "positive_control_null_percentile": "empirical fraction of grouped null values <= observed presented balanced accuracy",
            "cell_units": "session x area x representation",
            "biological_replicate_warning": "folds and cells remain nested within session and subject",
        },
        "counts": {
            "primary_cells": int(len(primary_cells)),
            "positive_control_cells": int(len(positive_cells)),
            "primary_oof_rows": int(len(primary_oof)),
            "paired_cells": int(len(paired)),
            "leave_one_session_out_rows": int(len(leave_one_out)),
        },
        "output_paths": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "verdict": "diagnostic_complete; no new model training; M2/M3 gate remains closed pending review",
    }
    receipt_path = output_dir / "diagnostic_review_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.input_dir, args.output_dir)
    print(
        f"Diagnostic review complete: {result['counts']}; "
        "no model training performed.",
        flush=True,
    )


if __name__ == "__main__":
    main()
