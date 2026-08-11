#!/usr/bin/env python3
"""Inspect Structured Identity Experiment v1 Milestone 1 design artifacts.

This is a receipt/table inspection pass only.  It does not load NWB files, materialize neural
features, fit estimators, or train models.
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

from jnwb.structured_identity import build_representation_ladder  # noqa: E402

DEFAULT_INPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_1"
)

MAIN_ANALYSIS = "omitted_expected_identity"
POSITIVE_CONTROL = "presented_identity_positive_control"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_column(analysis: str) -> str:
    return "expected_identity" if analysis == MAIN_ANALYSIS else "presented_identity"


def _class_count(frame: pd.DataFrame, column: str, prefix: str) -> dict:
    counts = frame[column].value_counts().to_dict()
    return {
        f"{prefix}_A": int(counts.get("A", 0)),
        f"{prefix}_B": int(counts.get("B", 0)),
        f"{prefix}_n": int(frame[column].notna().sum()),
    }


def _class_balance(table: pd.DataFrame) -> pd.DataFrame:
    eligible = table[table["eligible"]].copy()
    rows = []
    for (session, subject, analysis, slot), group in eligible.groupby(
        ["session", "subject", "analysis", "slot_key"], sort=True, dropna=False
    ):
        target = _target_column(analysis)
        row = {
            "session": session,
            "subject": subject,
            "analysis": analysis,
            "slot_key": slot,
            "target": target,
            "n_cycles": int(group["cycle"].nunique()),
        }
        row.update(_class_count(group, target, "target"))
        if analysis == MAIN_ANALYSIS:
            row.update(_class_count(group, "preceding_identity", "preceding"))
        rows.append(row)
    return pd.DataFrame(rows)


def _omission_position_distribution(table: pd.DataFrame) -> pd.DataFrame:
    frame = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy()
    return (
        frame.groupby(
            ["session", "subject", "omission_position"], sort=True, dropna=False
        )
        .size()
        .reset_index(name="n_trials")
    )


def _contingency(table: pd.DataFrame) -> pd.DataFrame:
    frame = table[(table["analysis"] == MAIN_ANALYSIS) & table["eligible"]].copy()
    return (
        frame.groupby(
            [
                "session",
                "subject",
                "slot_key",
                "preceding_identity",
                "expected_identity",
            ],
            sort=True,
            dropna=False,
        )
        .size()
        .reset_index(name="n_trials")
    )


def _sequence_family_distribution(table: pd.DataFrame) -> pd.DataFrame:
    frame = table[table["eligible"]].copy()
    return (
        frame.groupby(
            ["session", "subject", "analysis", "slot_key", "sequence_family"],
            sort=True,
            dropna=False,
        )
        .size()
        .reset_index(name="n_trials")
    )


def _cycles_per_class(table: pd.DataFrame) -> pd.DataFrame:
    frame = table[table["eligible"]].copy()
    rows = []
    for (session, subject, analysis, slot), group in frame.groupby(
        ["session", "subject", "analysis", "slot_key"], sort=True, dropna=False
    ):
        target = _target_column(analysis)
        for target_value, target_group in group.groupby(target, sort=True, dropna=False):
            rows.append(
                {
                    "session": session,
                    "subject": subject,
                    "analysis": analysis,
                    "slot_key": slot,
                    "target": target,
                    "target_value": target_value,
                    "n_trials": int(len(target_group)),
                    "n_cycles": int(target_group["cycle"].nunique()),
                    "cycles": ",".join(
                        str(int(value)) for value in sorted(target_group["cycle"].unique())
                    ),
                }
            )
    return pd.DataFrame(rows)


def _outer_fold_geometry(outer: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (session, subject, analysis, slot, fold), group in outer.groupby(
        ["session", "subject", "analysis", "slot_key", "outer_fold"], sort=True, dropna=False
    ):
        target = _target_column(analysis)
        all_rows = outer[
            (outer["session"] == session)
            & (outer["analysis"] == analysis)
            & (outer["slot_key"] == slot)
        ]
        train = all_rows[all_rows["outer_fold"] != fold]
        test = all_rows[all_rows["outer_fold"] == fold]
        row = {
            "session": session,
            "subject": subject,
            "analysis": analysis,
            "slot_key": slot,
            "outer_fold": int(fold),
            "held_out_cycle": int(group["outer_group"].iloc[0]),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "n_train_cycles": int(train["outer_group"].nunique()),
            "n_test_cycles": int(test["outer_group"].nunique()),
        }
        row.update(_class_count(train, target, "train"))
        row.update(_class_count(test, target, "test"))
        rows.append(row)
    return pd.DataFrame(rows)


def _inner_counts(inner: pd.DataFrame) -> pd.DataFrame:
    if inner.empty:
        return pd.DataFrame()
    return (
        inner.groupby(
            [
                "session",
                "analysis",
                "slot_key",
                "outer_fold",
                "inner_fold",
                "inner_role",
            ],
            sort=True,
            dropna=False,
        )
        .size()
        .reset_index(name="n_trials")
    )


def _nuisance_tables(table: pd.DataFrame, outer: pd.DataFrame):
    frame = table[
        (table["analysis"] == MAIN_ANALYSIS) & table["eligible"]
    ].merge(
        outer[["session", "analysis", "slot_key", "trial_id", "outer_fold"]],
        on=["session", "analysis", "slot_key", "trial_id"],
        how="inner",
        validate="one_to_one",
    )
    keys = [
        "preceding_identity",
        "omission_position",
        "sequence_family",
        "cycle",
    ]
    conditional = []
    summary = []
    for (session, subject, slot, fold), group in outer[
        outer["analysis"] == MAIN_ANALYSIS
    ].groupby(["session", "subject", "slot_key", "outer_fold"], sort=True):
        target_rows = frame[
            (frame["session"] == session)
            & (frame["slot_key"] == slot)
        ]
        for partition, subset in (
            ("outer_train", target_rows[target_rows["outer_fold"] != fold]),
            ("outer_test", target_rows[target_rows["outer_fold"] == fold]),
        ):
            if subset.empty:
                continue
            grouped = (
                subset.groupby(keys + ["expected_identity"], dropna=False)
                .size()
                .reset_index(name="n_trials")
            )
            totals = grouped.groupby(keys, dropna=False)["n_trials"].transform("sum")
            grouped["conditional_probability"] = grouped["n_trials"] / totals
            grouped.insert(0, "session", session)
            grouped.insert(1, "subject", subject)
            grouped.insert(2, "slot_key", slot)
            grouped.insert(3, "outer_fold", int(fold))
            grouped.insert(4, "partition", partition)
            conditional.append(grouped)

            by_key = grouped.groupby(keys, dropna=False)["conditional_probability"]
            max_prob = by_key.max()
            n_keys = int(max_prob.size)
            n_deterministic = int(np.isclose(max_prob, 1.0).sum())
            summary.append(
                {
                    "session": session,
                    "subject": subject,
                    "slot_key": slot,
                    "outer_fold": int(fold),
                    "partition": partition,
                    "conditioned_on": ",".join(keys),
                    "n_conditioning_keys": n_keys,
                    "n_deterministic_keys": n_deterministic,
                    "deterministic_key_fraction": (
                        float(n_deterministic / n_keys) if n_keys else float("nan")
                    ),
                    "max_conditional_probability": float(max_prob.max()),
                    "all_keys_deterministic": bool(
                        n_keys > 0 and n_deterministic == n_keys
                    ),
                }
            )
    return (
        pd.concat(conditional, ignore_index=True) if conditional else pd.DataFrame(),
        pd.DataFrame(summary),
    )


def _representation_review() -> dict:
    raster = np.arange(4 * 3 * 5, dtype=np.float64).reshape(4, 3, 5)
    ladder = build_representation_ladder(raster, modality="SPK")
    r1_as_raster = ladder["X_vec"].reshape(raster.shape)
    return {
        "actual_neural_feature_tensor_materialized": False,
        "contract_smoke_input_shape": list(raster.shape),
        "R0_X_rate_shape": list(ladder["X_rate"].shape),
        "R1_X_vec_shape": list(ladder["X_vec"].shape),
        "R2_X_structured_shape": list(ladder["X_structured"].shape),
        "R0_semantics": ladder["contract"]["r0"],
        "R1_semantics": ladder["contract"]["r1"],
        "R2_semantics": ladder["contract"]["r2"],
        "R1_R2_same_underlying_samples_on_contract_smoke": bool(
            np.array_equal(r1_as_raster, ladder["X_structured"])
        ),
        "R1_vectorization_order": ladder["contract"]["vectorization_order"],
        "SPK_space_axis_topology": ladder["contract"]["space_axis_topology"],
        "training_run": False,
    }


def run(input_dir: Path, output_dir: Path) -> dict:
    receipt_path = input_dir / "milestone_1_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    table = pd.read_csv(input_dir / "canonical_trial_ontology.csv")
    outer = pd.read_csv(input_dir / "outer_fold_plan.csv")
    inner = pd.read_csv(input_dir / "inner_validation_plan.csv")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "class_balance": output_dir / "expected_identity_class_balance_by_session.csv",
        "omission_position": output_dir / "omission_position_distribution.csv",
        "preceding_expected": output_dir / "preceding_identity_by_expected_identity.csv",
        "sequence_family": output_dir / "sequence_family_distribution.csv",
        "cycles_per_class": output_dir / "cycles_per_identity_class.csv",
        "outer_folds": output_dir / "outer_fold_train_test_counts.csv",
        "inner_counts": output_dir / "inner_validation_counts.csv",
        "nuisance_conditional": output_dir / "nuisance_conditional_table.csv",
        "nuisance_summary": output_dir / "nuisance_identifiability_summary.csv",
    }
    frames = {
        "class_balance": _class_balance(table),
        "omission_position": _omission_position_distribution(table),
        "preceding_expected": _contingency(table),
        "sequence_family": _sequence_family_distribution(table),
        "cycles_per_class": _cycles_per_class(table),
        "outer_folds": _outer_fold_geometry(outer),
        "inner_counts": _inner_counts(inner),
    }
    nuisance_table, nuisance_summary = _nuisance_tables(table, outer)
    frames["nuisance_conditional"] = nuisance_table
    frames["nuisance_summary"] = nuisance_summary
    for key, frame in frames.items():
        frame.to_csv(outputs[key], index=False)

    representation = _representation_review()
    (output_dir / "representation_review.json").write_text(
        json.dumps(representation, indent=2), encoding="utf-8"
    )

    nuisance = nuisance_summary
    review = {
        "schema_version": 3,
        "review": "structured-identity-experiment-v1-milestone-1-design-inspection",
        "input_receipt": str(receipt_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "input_receipt_sha256": _sha256(receipt_path),
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "training_run": False,
        "models_trained": [],
        "source_counts": receipt["counts"],
        "inspection_outputs": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "representation_review": "representation_review.json",
        "fold_geometry": {
            "n_outer_folds": int(len(frames["outer_folds"])),
            "n_outer_folds_with_single_training_cycle": int(
                (frames["outer_folds"]["n_train_cycles"] < 2).sum()
            ),
            "n_outer_folds_missing_train_A": int(
                (frames["outer_folds"]["train_A"] == 0).sum()
            ),
            "n_outer_folds_missing_train_B": int(
                (frames["outer_folds"]["train_B"] == 0).sum()
            ),
            "n_outer_folds_missing_test_A": int(
                (frames["outer_folds"]["test_A"] == 0).sum()
            ),
            "n_outer_folds_missing_test_B": int(
                (frames["outer_folds"]["test_B"] == 0).sum()
            ),
            "n_inner_insufficient_training_groups": int(
                (frames["inner_counts"]["inner_role"] == "insufficient_training_groups").sum()
            )
            if not frames["inner_counts"].empty
            else 0,
            "interpretation_gate": (
                "Outer folds with one training cycle or a missing training class cannot support "
                "the planned nested model-selection contract without an explicit exclusion rule."
            ),
        },
        "nuisance_identifiability": {
            "conditioning": [
                "preceding_identity",
                "omission_position",
                "sequence_family",
                "cycle",
            ],
            "n_summary_rows": int(len(nuisance)),
            "n_all_keys_deterministic": int(
                nuisance["all_keys_deterministic"].sum()
            )
            if not nuisance.empty
            else 0,
            "all_keys_deterministic_fraction": float(
                nuisance["all_keys_deterministic"].mean()
            )
            if not nuisance.empty
            else float("nan"),
            "max_conditional_probability": float(
                nuisance["max_conditional_probability"].max()
            )
            if not nuisance.empty
            else float("nan"),
            "interpretation_gate": (
                "Nuisance combinations must not be treated as independent evidence when "
                "they deterministically identify expected identity."
            ),
        },
        "review_verdict": (
            "training_gate_remains_closed_pending_design_review"
        ),
        "next_gate": (
            "Resolve the deterministic expected/preceding identity relationship and fold cells "
            "with insufficient training cycles/classes before Milestone 2."
        ),
    }
    review_path = output_dir / "milestone_1_design_inspection_receipt.json"
    review["output_hashes"] = {
        key: _sha256(path) for key, path in outputs.items()
    }
    review["output_hashes"]["representation_review"] = _sha256(
        output_dir / "representation_review.json"
    )
    review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")
    return review


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_INPUT / "review",
    )
    args = parser.parse_args()
    if not args.input_dir.exists():
        raise FileNotFoundError(args.input_dir)
    result = run(args.input_dir, args.output_dir)
    print(
        "Design inspection complete: "
        f"{result['nuisance_identifiability']['n_summary_rows']} nuisance summaries, "
        f"all_keys_deterministic={result['nuisance_identifiability']['n_all_keys_deterministic']}, "
        "no models trained.",
        flush=True,
    )


if __name__ == "__main__":
    main()
