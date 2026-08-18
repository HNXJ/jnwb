#!/usr/bin/env python3
"""Merge the independent Stage 4B modality shards into one receipt-backed map."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARTS = REPO_ROOT / "DUMMY"
DEFAULT_OUTPUT = Path("D:/analysis/handout4_stage4b_linear_map")


from jnwb.paths import sha256_file as _sha256


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _read_csv(parts: list[Path], name: str) -> pd.DataFrame:
    frames = []
    for part in parts:
        path = part / name
        if path.exists() and path.stat().st_size:
            frames.append(pd.read_csv(path))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _summary(cells: pd.DataFrame, output: Path) -> None:
    if cells.empty:
        for name in (
            "session_summary.csv",
            "subject_summary.csv",
            "leave_one_session_out.csv",
            "what_when_signal_matrix.csv",
            "coarse_window_map.csv",
        ):
            pd.DataFrame().to_csv(output / name, index=False)
        return
    session = (
        cells.groupby(
            ["task", "signal", "representation", "window", "subject", "session"],
            dropna=False,
        )
        .agg(
            observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
            null_effect=("null_effect", "mean"),
            permutation_p=("permutation_p", "median"),
            area_N=("area", "nunique"),
        )
        .reset_index()
    )
    subject = (
        session.groupby(
            ["task", "signal", "representation", "window", "subject"],
            dropna=False,
        )
        .agg(
            observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
            null_effect=("null_effect", "mean"),
            session_N=("session", "nunique"),
        )
        .reset_index()
    )
    loso = []
    for key, group in cells.groupby(
        ["task", "signal", "representation", "window"], dropna=False
    ):
        for omitted in sorted(group["session"].unique()):
            remaining = group[group["session"] != omitted]
            loso.append(
                {
                    "task": key[0],
                    "signal": key[1],
                    "representation": key[2],
                    "window": key[3],
                    "omitted_session": omitted,
                    "session_N": int(remaining["session"].nunique()),
                    "observed_balanced_accuracy": float(
                        remaining["observed_balanced_accuracy"].mean()
                    ),
                    "null_effect": float(remaining["null_effect"].mean()),
                }
            )
    primary = cells[cells["window"].eq("full_omission")].copy()
    primary["effect_relative_to_null"] = np.where(
        primary["task"].str.startswith("W1_reversal"),
        primary["G"],
        primary["null_effect"],
    )
    matrix = (
        primary.groupby(["task", "signal", "representation"], dropna=False)
        .agg(
            observed_effect_relative_to_null=("effect_relative_to_null", "mean"),
            observed_balanced_accuracy=("observed_balanced_accuracy", "mean"),
            eligible_session_N=("session", "nunique"),
            successful_cell_N=("session", "size"),
        )
        .reset_index()
    )
    matrix["task_family"] = np.where(
        matrix["task"].str.startswith(("W1", "W2", "W3")), "WHAT", "WHEN"
    )
    session.to_csv(output / "session_summary.csv", index=False)
    subject.to_csv(output / "subject_summary.csv", index=False)
    pd.DataFrame(loso).to_csv(output / "leave_one_session_out.csv", index=False)
    matrix.to_csv(output / "what_when_signal_matrix.csv", index=False)
    cells[~cells["window"].eq("full_omission")].to_csv(
        output / "coarse_window_map.csv", index=False
    )


def merge(parts: list[Path], output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    names = {
        "cell_results": "cell_results.csv",
        "predictions": "predictions.csv",
        "folds": "folds.csv",
        "null_distribution": "null_distribution.csv",
        "feature_manifest": "feature_manifest.csv",
        "failures": "failures.csv",
    }
    merged = {}
    for key, filename in names.items():
        frame = _read_csv(parts, filename)
        path = output / filename
        frame.to_csv(path, index=False)
        merged[key] = path
    manifests = []
    for part in parts:
        path = part / "trial_fold_manifest.json"
        if path.exists():
            manifests.extend(json.loads(path.read_text(encoding="utf-8")))
    manifest_path = output / "trial_fold_manifest.json"
    manifest_path.write_text(json.dumps(manifests, indent=2), encoding="utf-8")
    merged["trial_fold_manifest"] = manifest_path
    cells = pd.read_csv(merged["cell_results"]) if merged["cell_results"].stat().st_size else pd.DataFrame()
    _summary(cells, output)
    for filename in (
        "session_summary.csv",
        "subject_summary.csv",
        "leave_one_session_out.csv",
        "what_when_signal_matrix.csv",
        "coarse_window_map.csv",
    ):
        merged[filename.removesuffix(".csv")] = output / filename
    shard_receipts = [
        json.loads((part / "stage4b_receipt.json").read_text(encoding="utf-8"))
        for part in parts
    ]
    uncatalogued = shard_receipts[0]["frozen_corpus"]["uncatalogued_live_sessions"]
    receipt_paths = {
        key: _display(path) for key, path in merged.items()
    }
    receipt = {
        "schema_version": 3,
        "experiment": "handout-4-full-corpus-what-when-omission-information",
        "stage": "4B_linear_map",
        "status": "complete",
        "authorization": {
            "SAFE_TO_RUN_STAGE4B_LINEAR": True,
            "SAFE_TO_RUN_M2": False,
            "SAFE_TO_RUN_M3": False,
            "SAFE_TO_RUN_M4": False,
            "TFR_BACKED_LFP": False,
        },
        "frozen_corpus": {
            "catalog_sessions_used": 21,
            "uncatalogued_live_sessions": uncatalogued,
            "uncatalogued_status": "AVAILABLE_BUT_NOT_IN_FROZEN_CORPUS",
            "session_filenames": shard_receipts[0]["frozen_corpus"]["session_filenames"],
        },
        "modality_shards": [
            {
                "path": _display(part),
                "receipt_hash": _sha256(part / "stage4b_receipt.json"),
                "successful_cells": item["counts"]["successful_cells"],
                "failed_cells": item["counts"]["failed_cells"],
            }
            for part, item in zip(parts, shard_receipts)
        ],
        "coarse_windows_ms": shard_receipts[0]["coarse_windows_ms"],
        "model": shard_receipts[0]["model"],
        "null": shard_receipts[0]["null"],
        "counts": {
            "successful_cells": int(len(cells)),
            "failed_cells": int(len(pd.read_csv(merged["failures"]))),
            "prediction_rows": int(len(pd.read_csv(merged["predictions"]))),
            "null_rows": int(len(pd.read_csv(merged["null_distribution"]))),
            "trial_fold_manifest_rows": int(len(manifests)),
        },
        "outputs": receipt_paths,
        "output_hashes": {key: _sha256(path) for key, path in merged.items()},
        "input_hashes": {
            "runner": _sha256(REPO_ROOT / "scripts" / "run_handout4_stage4b_linear_map.py"),
            "merge_runner": _sha256(Path(__file__).resolve()),
            "stage4a_geometry": _sha256(
                REPO_ROOT
                / "context"
                / "figures"
                / "fig04_omission_identity_decoding"
                / "handout_4_stage4a"
                / "task_session_geometry.csv"
            ),
        },
        "commands": [
            "python scripts/run_handout4_stage4b_linear_map.py --signals SUA_SPK --n-permutations 100",
            "python scripts/run_handout4_stage4b_linear_map.py --signals MUAe --n-permutations 100",
            "python scripts/run_handout4_stage4b_linear_map.py --signals LFP --n-permutations 100",
            "python scripts/merge_handout4_stage4b_shards.py",
        ],
        "training_scope": {
            "nonlinear_flat_M2": False,
            "structured_M3": False,
            "ablation_M4": False,
            "architecture_search": False,
        },
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "stop_rule": "STOP after authorized linear map; do not train M2/M3/M4.",
        "falsifier": "Superseded if frozen corpus, Stage 4A geometry, Stage 4A.1 alignment, representation, null, or model contracts change.",
    }
    receipt_path = output / "stage4b_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--parts",
        nargs="+",
        type=Path,
        default=[
            Path("D:/analysis/handout4_stage4b_linear_map_parts/SUA"),
            Path("D:/analysis/handout4_stage4b_linear_map_parts/MUAe"),
            Path("D:/analysis/handout4_stage4b_linear_map_parts/LFP"),
        ],
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = merge([part.resolve() for part in args.parts], args.output_dir.resolve())
    print(json.dumps(result["counts"], sort_keys=True), flush=True)
    print("Stage 4B shard merge complete; M2/M3/M4 remain closed.", flush=True)


if __name__ == "__main__":
    main()
