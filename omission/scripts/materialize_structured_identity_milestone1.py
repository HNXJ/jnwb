#!/usr/bin/env python3
"""Materialize Structured Identity Experiment v1 Milestone 1 artifacts.

This command builds ontology/fold/null metadata only.  It does not extract model features,
fit a decoder, allocate GPU work, or train M2/M3.  All generated artifacts belong under
``context/figures/fig04_omission_identity_decoding/structured_identity_experiment_v1/``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import omission as oa  # noqa: E402
from jnwb import paths  # noqa: E402
from omission.jnwb_ext.structured_identity import (  # noqa: E402
    MAIN_ANALYSIS,
    POSITIVE_CONTROL,
    assign_outer_folds,
    build_canonical_trial_table,
    build_inner_validation_partitions,
    build_milestone_receipt,
    build_permutation_plan,
    build_representation_ladder,
)


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_1"
)
TARGETS = (
    "expected_identity",
    "preceding_identity",
    "omission_position",
    "sequence_family",
    "presented_identity",
)


def _truthy(value) -> bool:
    return str(value).strip().lower() in {"1", "1.0", "true", "yes"}


def _resolve_sessions(readiness_csv: Path, nwb_dir: Path):
    readiness = pd.read_csv(readiness_csv)
    included, excluded = [], []
    for row in readiness.to_dict("records"):
        stem = str(row["stem"])
        if not (_truthy(row.get("nwb_ok")) and _truthy(row.get("sidecar_ok"))):
            excluded.append({"stem": stem, "reason": "readiness_gate"})
            continue
        candidates = [
            nwb_dir / Path(str(row.get("nwb_path", ""))).name,
            nwb_dir / f"{stem}.nwb",
            nwb_dir / f"{stem.replace('_rec', '')}.nwb",
        ]
        path = next((candidate for candidate in candidates if candidate.exists()), None)
        if path is None:
            excluded.append({"stem": stem, "reason": "eligible_nwb_missing"})
            continue
        included.append(
            {
                "stem": stem,
                "subject": str(row.get("subject", "")),
                "session_id": str(row.get("session_id", "")),
                "path": str(path),
            }
        )
    return included, excluded


from jnwb.paths import sha256_file as _sha256


def _class_balance(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    eligible = table[table["eligible"]].copy()
    for target in TARGETS:
        if target not in eligible:
            continue
        values = eligible.dropna(subset=[target])
        if values.empty:
            continue
        counts = (
            values.groupby(["session", "analysis", "slot_key", target], dropna=False)
            .size()
            .reset_index(name="n_trials")
            .rename(columns={target: "target_value"})
        )
        counts["target_name"] = target
        rows.append(counts)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _null_manifest(table: pd.DataFrame, n_permutations: int, seed: int) -> pd.DataFrame:
    rows = []
    eligible = table[table["eligible"]].copy()
    group_cols = ["session", "analysis", "slot_key"]
    for key, group in eligible.groupby(group_cols, sort=True, dropna=False):
        key_values = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        for target in TARGETS:
            subset = group.dropna(subset=[target])
            if subset[target].nunique() < 2:
                rows.append(
                    {
                        **key_values,
                        "target_name": target,
                        "status": "constant_target",
                        "n_permutations": 0,
                        "scheme": "within_group",
                    }
                )
                continue
            if subset["cycle"].nunique() < 2:
                rows.append(
                    {
                        **key_values,
                        "target_name": target,
                        "status": "insufficient_groups",
                        "n_permutations": 0,
                        "scheme": "within_group",
                        "n_groups": int(subset["cycle"].nunique()),
                    }
                )
                continue
            plan = build_permutation_plan(
                subset[target].to_numpy(),
                subset["cycle"].to_numpy(),
                n_permutations=n_permutations,
                seed=seed,
            )
            for manifest in plan["draw_manifest"].to_dict("records"):
                rows.append(
                    {
                        **key_values,
                        "target_name": target,
                        "status": "planned",
                        "scheme": plan["scheme"],
                        "n_permutations": plan["n_permutations"],
                        **manifest,
                    }
                )
    return pd.DataFrame(rows)


def run(
    *,
    readiness_csv: Path,
    nwb_dir: Path,
    output_dir: Path,
    seed: int = 42,
    n_permutations: int = 20,
    limit: int | None = None,
) -> dict:
    sessions, excluded = _resolve_sessions(readiness_csv, nwb_dir)
    if limit is not None:
        sessions = sessions[:limit]
    if not sessions:
        raise RuntimeError("no sessions passed the readiness and path gates")

    tables = []
    session_manifest = []
    for meta in sessions:
        print(f"ontology [{len(tables) + 1}/{len(sessions)}] {meta['stem']}", flush=True)
        session = oa.read(meta["path"])
        table = build_canonical_trial_table(session)
        tables.append(table)
        session_manifest.append(
            {
                "stem": meta["stem"],
                "subject": meta["subject"],
                "session_id": meta["session_id"],
                "input_filename": Path(meta["path"]).name,
                "n_rows": int(len(table)),
                "n_eligible": int(table["eligible"].sum()) if not table.empty else 0,
                "n_cycles": int(table.loc[table["eligible"], "cycle"].nunique())
                if not table.empty
                else 0,
            }
        )
    trial_table = pd.concat(tables, ignore_index=True) if tables else pd.DataFrame()
    eligible = trial_table[trial_table["eligible"]].copy()
    outer = assign_outer_folds(eligible)
    inner = build_inner_validation_partitions(outer)
    balance = _class_balance(trial_table)
    nulls = _null_manifest(trial_table, n_permutations=n_permutations, seed=seed)

    # Contract-only tensor smoke: this validates axis and vectorization semantics, not science.
    contract = build_representation_ladder(
        np.arange(4 * 3 * 5, dtype=np.float64).reshape(4, 3, 5), modality="SPK"
    )["contract"]
    contract["tensor_smoke_shape"] = [4, 3, 5]
    contract["training_run"] = False

    output_dir.mkdir(parents=True, exist_ok=True)
    paths_out = {
        "trial_ontology": output_dir / "canonical_trial_ontology.csv",
        "outer_folds": output_dir / "outer_fold_plan.csv",
        "inner_folds": output_dir / "inner_validation_plan.csv",
        "class_balance": output_dir / "target_class_balance.csv",
        "null_manifest": output_dir / "permutation_null_plan.csv",
        "representation_contract": output_dir / "representation_contract.json",
    }
    trial_table.to_csv(paths_out["trial_ontology"], index=False)
    outer.to_csv(paths_out["outer_folds"], index=False)
    inner.to_csv(paths_out["inner_folds"], index=False)
    balance.to_csv(paths_out["class_balance"], index=False)
    nulls.to_csv(paths_out["null_manifest"], index=False)
    paths_out["representation_contract"].write_text(
        json.dumps(contract, indent=2), encoding="utf-8"
    )

    git_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    receipt = build_milestone_receipt(
        git_sha=git_sha,
        session_manifest=session_manifest,
        excluded_sessions=excluded,
        output_paths={
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in paths_out.items()
        },
        counts={
            "ontology_rows": int(len(trial_table)),
            "eligible_rows": int(len(eligible)),
            "outer_fold_rows": int(len(outer)),
            "valid_outer_fold_rows": int(
                (outer["outer_fold_status"] == "valid").sum()
            ),
            "insufficient_outer_fold_rows": int(
                (outer["outer_fold_status"] == "insufficient_groups").sum()
            ),
            "inner_partition_rows": int(len(inner)),
            "balance_rows": int(len(balance)),
            "null_manifest_rows": int(len(nulls)),
        },
        null_scheme="within_group",
        n_permutations=n_permutations,
        seed=seed,
    )
    receipt["run_scope"] = {"limit": limit, "full_eligible_corpus": limit is None}
    receipt["representation_contract_path"] = str(
        paths_out["representation_contract"].relative_to(REPO_ROOT)
    ).replace("\\", "/")
    git_status = subprocess.check_output(
        ["git", "status", "--short"], cwd=REPO_ROOT, text=True
    )
    receipt["worktree"] = {
        "dirty": bool(git_status.strip()),
        "status_short": git_status.splitlines(),
        "receipt_sha_refers_to": "HEAD only; uncommitted source changes are not in git_sha",
    }
    receipt["output_hashes"] = {key: _sha256(path) for key, path in paths_out.items()}
    receipt_path = output_dir / "milestone_1_receipt.json"
    receipt["receipt_path"] = str(receipt_path.relative_to(REPO_ROOT)).replace("\\", "/")
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Milestone 1 complete: {len(sessions)} sessions, {len(eligible)} eligible trials, "
        f"{len(outer)} outer-fold rows, {len(nulls)} null-plan rows; no models trained.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--readiness",
        type=Path,
        default=REPO_ROOT / "artifacts" / "data" / "session_readiness.csv",
    )
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--permutations", type=int, default=20)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(f"NWB directory not found: {args.nwb_dir}")
    run(
        readiness_csv=args.readiness,
        nwb_dir=args.nwb_dir,
        output_dir=args.output_dir,
        seed=args.seed,
        n_permutations=args.permutations,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
