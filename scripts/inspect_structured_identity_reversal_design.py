#!/usr/bin/env python3
"""Design-only inspection for Handout 3 v1.1 cross-position reversal contrasts.

This script reads the Milestone 1 ontology table, creates common session-level cycle labels for
p2/p3/p4 trials, and reports exact contrast eligibility and nested fold geometry.  It never loads
neural features and never fits or trains a model.
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
sys.path.insert(0, str(REPO_ROOT))

from jnwb.omission_identity import detect_trial_cycles  # noqa: E402

DEFAULT_INPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_1"
)
DEFAULT_OUTPUT = DEFAULT_INPUT / "reversal_design"
MAIN_ANALYSIS = "omitted_expected_identity"
MIN_COMMON_CYCLES = 3
MIN_OUTER_FOLDS = 2
MIN_INNER_PARTITIONS = 2

CONTRASTS = (
    {
        "contrast": "p2p3_to_p4",
        "role": "primary",
        "train_slots": ("p2", "p3"),
        "test_slots": ("p4",),
    },
    {
        "contrast": "p4_to_p2p3",
        "role": "secondary",
        "train_slots": ("p4",),
        "test_slots": ("p2", "p3"),
    },
    {
        "contrast": "p2_to_p4",
        "role": "secondary",
        "train_slots": ("p2",),
        "test_slots": ("p4",),
    },
    {
        "contrast": "p3_to_p4",
        "role": "secondary",
        "train_slots": ("p3",),
        "test_slots": ("p4",),
    },
    {
        "contrast": "p4_to_p2",
        "role": "secondary",
        "train_slots": ("p4",),
        "test_slots": ("p2",),
    },
    {
        "contrast": "p4_to_p3",
        "role": "secondary",
        "train_slots": ("p4",),
        "test_slots": ("p3",),
    },
)


from jnwb.paths import sha256_file as _sha256


def _classes(frame: pd.DataFrame, column: str = "expected_identity") -> tuple[int, int]:
    counts = frame[column].value_counts().to_dict()
    return int(counts.get("A", 0)), int(counts.get("B", 0))


def _common_cycle_table(table: pd.DataFrame) -> pd.DataFrame:
    eligible = table[
        (table["analysis"] == MAIN_ANALYSIS)
        & table["eligible"]
        & table["slot_key"].isin(["p2", "p3", "p4"])
    ].copy()
    eligible["cross_position_cycle"] = -1
    for session, index in eligible.groupby("session", sort=True).groups.items():
        ordered = eligible.loc[index].sort_values(["start_time", "trial_id"])
        cycles = detect_trial_cycles(ordered[["start_time"]].reset_index(drop=True))
        eligible.loc[ordered.index, "cross_position_cycle"] = cycles
    return eligible.sort_values(
        ["session", "cross_position_cycle", "start_time", "trial_id"]
    ).reset_index(drop=True)


def _label_proof(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for slot, group in table.groupby("slot_key", sort=True):
        counts = (
            group.groupby(
                ["preceding_identity", "expected_identity"], dropna=False
            )
            .size()
            .reset_index(name="n_trials")
        )
        for record in counts.to_dict("records"):
            previous = record["preceding_identity"]
            expected = record["expected_identity"]
            rows.append(
                {
                    "slot_key": slot,
                    "preceding_identity": previous,
                    "expected_identity": expected,
                    "relation": "equal" if previous == expected else "opposite",
                    "n_trials": int(record["n_trials"]),
                }
            )
    return pd.DataFrame(rows)


def _fold_reasons(train: pd.DataFrame, test: pd.DataFrame, n_train_cycles: int) -> list[str]:
    reasons = []
    if train.empty:
        reasons.append("NO_TRAIN_TRIALS")
    if test.empty:
        reasons.append("NO_TEST_TRIALS")
    if n_train_cycles < 2:
        reasons.append("TRAIN_CYCLES_LT_2")
    train_a, train_b = _classes(train)
    test_a, test_b = _classes(test)
    if train_a == 0:
        reasons.append("TRAIN_MISSING_A")
    if train_b == 0:
        reasons.append("TRAIN_MISSING_B")
    if test_a == 0:
        reasons.append("TEST_MISSING_A")
    if test_b == 0:
        reasons.append("TEST_MISSING_B")
    return reasons


def _contrast_geometry(session_table: pd.DataFrame, config: dict):
    train_slots = config["train_slots"]
    test_slots = config["test_slots"]
    train_all = session_table[session_table["slot_key"].isin(train_slots)]
    test_all = session_table[session_table["slot_key"].isin(test_slots)]
    session_reasons = [
        *(f"TRAIN_SLOT_MISSING_{slot}" for slot in train_slots if train_all[train_all["slot_key"] == slot].empty),
        *(f"TEST_SLOT_MISSING_{slot}" for slot in test_slots if test_all[test_all["slot_key"] == slot].empty),
    ]
    train_cycles = set(train_all["cross_position_cycle"].unique())
    test_cycles = set(test_all["cross_position_cycle"].unique())
    common_cycles = sorted(train_cycles & test_cycles)
    outer_rows = []
    inner_rows = []
    for outer_fold, held_out_cycle in enumerate(common_cycles):
        train = train_all[train_all["cross_position_cycle"] != held_out_cycle]
        test = test_all[test_all["cross_position_cycle"] == held_out_cycle]
        train_cycle_values = sorted(train["cross_position_cycle"].unique())
        reasons = [*session_reasons, *_fold_reasons(train, test, len(train_cycle_values))]
        valid = not reasons and len(common_cycles) >= MIN_COMMON_CYCLES
        if len(common_cycles) < MIN_COMMON_CYCLES:
            reasons.append("COMMON_CYCLES_LT_3")
            valid = False
        train_a, train_b = _classes(train)
        test_a, test_b = _classes(test)
        outer_rows.append(
            {
                "session": session_table["session"].iloc[0],
                "subject": session_table["subject"].iloc[0],
                "contrast": config["contrast"],
                "role": config["role"],
                "outer_fold": outer_fold,
                "held_out_cycle": int(held_out_cycle),
                "train_slots": "+".join(train_slots),
                "test_slots": "+".join(test_slots),
                "n_common_cycles": len(common_cycles),
                "n_train_trials": int(len(train)),
                "n_test_trials": int(len(test)),
                "n_train_cycles": len(train_cycle_values),
                "n_test_cycles": int(test["cross_position_cycle"].nunique()),
                "train_A": train_a,
                "train_B": train_b,
                "test_A": test_a,
                "test_B": test_b,
                "status": "ELIGIBLE_OUTER" if valid else "INELIGIBLE_DESIGN",
                "reason": ";".join(reasons) if reasons else "",
            }
        )
        if not valid:
            continue
        for inner_fold, validation_cycle in enumerate(train_cycle_values):
            inner_train = train[train["cross_position_cycle"] != validation_cycle]
            inner_validation = train[
                train["cross_position_cycle"] == validation_cycle
            ]
            train_a, train_b = _classes(inner_train)
            val_a, val_b = _classes(inner_validation)
            reasons = []
            if len(inner_train["cross_position_cycle"].unique()) < 1:
                reasons.append("INNER_TRAIN_CYCLES_LT_1")
            if train_a == 0:
                reasons.append("INNER_TRAIN_MISSING_A")
            if train_b == 0:
                reasons.append("INNER_TRAIN_MISSING_B")
            if val_a == 0:
                reasons.append("INNER_VALIDATION_MISSING_A")
            if val_b == 0:
                reasons.append("INNER_VALIDATION_MISSING_B")
            inner_rows.append(
                {
                    "session": session_table["session"].iloc[0],
                    "subject": session_table["subject"].iloc[0],
                    "contrast": config["contrast"],
                    "outer_fold": outer_fold,
                    "inner_fold": inner_fold,
                    "held_out_cycle": int(held_out_cycle),
                    "validation_cycle": int(validation_cycle),
                    "n_inner_train_trials": int(len(inner_train)),
                    "n_inner_validation_trials": int(len(inner_validation)),
                    "inner_train_cycles": int(
                        inner_train["cross_position_cycle"].nunique()
                    ),
                    "inner_validation_cycles": int(
                        inner_validation["cross_position_cycle"].nunique()
                    ),
                    "inner_train_A": train_a,
                    "inner_train_B": train_b,
                    "inner_validation_A": val_a,
                    "inner_validation_B": val_b,
                    "status": "ELIGIBLE_INNER" if not reasons else "INELIGIBLE_DESIGN",
                    "reason": ";".join(reasons),
                }
            )
    outer_columns = [
        "session",
        "subject",
        "contrast",
        "role",
        "outer_fold",
        "held_out_cycle",
        "train_slots",
        "test_slots",
        "n_common_cycles",
        "n_train_trials",
        "n_test_trials",
        "n_train_cycles",
        "n_test_cycles",
        "train_A",
        "train_B",
        "test_A",
        "test_B",
        "status",
        "reason",
    ]
    inner_columns = [
        "session",
        "subject",
        "contrast",
        "outer_fold",
        "inner_fold",
        "held_out_cycle",
        "validation_cycle",
        "n_inner_train_trials",
        "n_inner_validation_trials",
        "inner_train_cycles",
        "inner_validation_cycles",
        "inner_train_A",
        "inner_train_B",
        "inner_validation_A",
        "inner_validation_B",
        "status",
        "reason",
    ]
    return (
        pd.DataFrame(outer_rows, columns=outer_columns),
        pd.DataFrame(inner_rows, columns=inner_columns),
        len(common_cycles),
    )


def _session_summary(session_table: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    summary_rows = []
    all_outer = []
    all_inner = []
    for config in CONTRASTS:
        outer, inner, n_common_cycles = _contrast_geometry(session_table, config)
        all_outer.append(outer)
        all_inner.append(inner)
        n_valid_outer = int((outer["status"] == "ELIGIBLE_OUTER").sum())
        n_valid_inner = int((inner["status"] == "ELIGIBLE_INNER").sum())
        reasons = []
        for slot in config["train_slots"]:
            if session_table[session_table["slot_key"] == slot].empty:
                reasons.append(f"TRAIN_SLOT_MISSING_{slot}")
        for slot in config["test_slots"]:
            if session_table[session_table["slot_key"] == slot].empty:
                reasons.append(f"TEST_SLOT_MISSING_{slot}")
        if n_common_cycles < MIN_COMMON_CYCLES:
            reasons.append("COMMON_CYCLES_LT_3")
        if n_valid_outer < MIN_OUTER_FOLDS:
            reasons.append("VALID_OUTER_FOLDS_LT_2")
        if n_valid_inner < MIN_INNER_PARTITIONS:
            reasons.append("VALID_INNER_PARTITIONS_LT_2")
        summary_rows.append(
            {
                "session": session_table["session"].iloc[0],
                "subject": session_table["subject"].iloc[0],
                "contrast": config["contrast"],
                "role": config["role"],
                "train_slots": "+".join(config["train_slots"]),
                "test_slots": "+".join(config["test_slots"]),
                "n_train_trials": int(
                    session_table[
                        session_table["slot_key"].isin(config["train_slots"])
                    ].shape[0]
                ),
                "n_test_trials": int(
                    session_table[
                        session_table["slot_key"].isin(config["test_slots"])
                    ].shape[0]
                ),
                "n_common_cycles": n_common_cycles,
                "n_outer_folds": int(len(outer)),
                "n_valid_outer_folds": n_valid_outer,
                "n_inner_partitions": int(len(inner)),
                "n_valid_inner_partitions": n_valid_inner,
                "design_status": (
                    "DESIGN_SUPPORTED" if not reasons else "INELIGIBLE_DESIGN"
                ),
                "reason": ";".join(reasons),
            }
        )
    outer_all = pd.concat(all_outer, ignore_index=True) if all_outer else pd.DataFrame()
    inner_all = pd.concat(all_inner, ignore_index=True) if all_inner else pd.DataFrame()
    return pd.DataFrame(summary_rows), [outer_all, inner_all]


def run(input_dir: Path, output_dir: Path) -> dict:
    table = pd.read_csv(input_dir / "canonical_trial_ontology.csv")
    source_receipt = input_dir / "milestone_1_receipt.json"
    source = json.loads(source_receipt.read_text(encoding="utf-8"))
    eligible = _common_cycle_table(table)
    label_proof = _label_proof(eligible)
    assignments = eligible[
        [
            "session",
            "subject",
            "trial_id",
            "slot_key",
            "condition",
            "start_time",
            "cycle",
            "cross_position_cycle",
            "expected_identity",
            "preceding_identity",
        ]
    ].copy()

    summaries = []
    outer_frames = []
    inner_frames = []
    for _, session_table in eligible.groupby("session", sort=True):
        summary, geometry = _session_summary(session_table)
        summaries.append(summary)
        outer_frames.append(geometry[0])
        inner_frames.append(geometry[1])
    summary = pd.concat(summaries, ignore_index=True)
    outer = pd.concat(outer_frames, ignore_index=True)
    inner = pd.concat(inner_frames, ignore_index=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "trial_groups": output_dir / "reversal_trial_group_assignments.csv",
        "label_proof": output_dir / "reversal_label_relationship_proof.csv",
        "eligibility": output_dir / "reversal_contrast_session_eligibility.csv",
        "outer_geometry": output_dir / "reversal_outer_fold_geometry.csv",
        "inner_geometry": output_dir / "reversal_inner_fold_geometry.csv",
    }
    assignments.to_csv(outputs["trial_groups"], index=False)
    label_proof.to_csv(outputs["label_proof"], index=False)
    summary.to_csv(outputs["eligibility"], index=False)
    outer.to_csv(outputs["outer_geometry"], index=False)
    inner.to_csv(outputs["inner_geometry"], index=False)

    primary_supported = summary[
        (summary["contrast"] == "p2p3_to_p4")
        & (summary["design_status"] == "DESIGN_SUPPORTED")
    ]
    label_relationships = {}
    for slot, group in label_proof.groupby("slot_key", sort=True):
        relations = sorted(group["relation"].unique().tolist())
        label_relationships[slot] = {
            "relations_observed": relations,
            "exact_expected_relation": (
                relations == ["equal"] if slot in {"p2", "p3"} else relations == ["opposite"]
            ),
            "pairs": group[
                ["preceding_identity", "expected_identity", "n_trials"]
            ].to_dict("records"),
        }
    receipt = {
        "schema_version": 3,
        "design": "structured-identity-experiment-v1.1-cross-position-reversal",
        "status": "DRAFT_FOR_SIGNOFF",
        "input_receipt": str(source_receipt.relative_to(REPO_ROOT)).replace("\\", "/"),
        "input_receipt_sha256": _sha256(source_receipt),
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "training_run": False,
        "models_trained": [],
        "neural_tensors_materialized": False,
        "cycle_rule": "jnwb.omission_identity.detect_trial_cycles on combined eligible p2/p3/p4 timestamps per session",
        "primary_contrast": "p2+p3_to_p4",
        "label_relationship_proof": label_relationships,
        "score_columns": [
            "accuracy_against_expected_identity",
            "accuracy_against_previous_identity",
            "G_expected_minus_previous",
        ],
        "eligibility_contract": {
            "min_common_cycles": MIN_COMMON_CYCLES,
            "min_valid_outer_folds": MIN_OUTER_FOLDS,
            "min_valid_inner_partitions": MIN_INNER_PARTITIONS,
            "outer_train_requires_both_classes": True,
            "outer_test_requires_both_classes": True,
            "fallback_random_validation": False,
        },
        "source_counts": source["counts"],
        "reversal_counts": {
            "sessions_inspected": int(summary["session"].nunique()),
            "eligible_trial_rows": int(len(eligible)),
            "label_proof_rows": int(len(label_proof)),
            "contrast_rows": int(len(summary)),
            "supported_primary_sessions": int(
                len(primary_supported)
            ),
            "supported_primary_session_ids": primary_supported["session"].tolist(),
            "supported_primary_subjects": sorted(
                primary_supported["subject"].unique().tolist()
            ),
            "supported_primary_outer_folds": int(
                primary_supported["n_valid_outer_folds"].sum()
            ),
            "supported_primary_inner_partitions": int(
                primary_supported["n_valid_inner_partitions"].sum()
            ),
            "supported_any_contrast_session_rows": int(
                (summary["design_status"] == "DESIGN_SUPPORTED").sum()
            ),
            "outer_geometry_rows": int(len(outer)),
            "inner_geometry_rows": int(len(inner)),
        },
        "output_paths": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "decision": (
            "No Milestone 2 training authorization. Review primary cross-position support and "
            "label-reversal proof first."
        ),
    }
    receipt_path = output_dir / "reversal_design_receipt.json"
    receipt["output_hashes"] = {key: _sha256(path) for key, path in outputs.items()}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        "Reversal design inspection complete: "
        f"{receipt['reversal_counts']['supported_primary_sessions']} primary sessions supported, "
        f"{receipt['reversal_counts']['supported_any_contrast_session_rows']} supported contrast rows, "
        "no models trained.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()
