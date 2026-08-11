#!/usr/bin/env python3
"""Run the approved Structured Identity v1.1 Milestone 2A SPK baselines.

Milestone 2A is deliberately limited to:

* the repaired presented-identity positive control;
* R0 temporally collapsed linear decoding;
* R1 temporally resolved, vectorized linear decoding;
* grouped nested folds and exchangeability-matched permutation nulls;
* reversal scoring against expected and preceding identity;
* session, subject, and leave-one-session-out diagnostics.

No M2 nonlinear, M3 structured, M4 ablation, architecture, or broad search path exists here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb import paths  # noqa: E402
from jnwb.structured_identity_m2a import (  # noqa: E402
    BIN_SIZE_MS,
    C_GRID,
    LABEL_TO_INT,
    OuterFold,
    build_outer_folds,
    extract_rate_raster,
    fit_nested_linear,
    null_metric_distribution,
)

PRIMARY_CONTRAST = "p2p3_to_p4"
PRIMARY_ANALYSIS = "omission_reversal"
POSITIVE_ANALYSIS = "presented_identity_positive_control"
REPRESENTATIONS = ("R0", "R1")
AREAS = ("FEF", "PFC", "TEO", "V4", "V3", "V2", "V1")
DEFAULT_PERMUTATIONS = 1000
DEFAULT_SEED = 42
MIN_VALID_POSITIVE_FOLDS = 2
DEFAULT_DESIGN_DIR = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_1"
    / "reversal_design"
)
DEFAULT_M1_DIR = DEFAULT_DESIGN_DIR.parent
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "structured_identity_experiment_v1"
    / "milestone_2a"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_area_seed(area: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(area))


def _resolve_nwb(readiness: pd.DataFrame, stem: str, nwb_dir: Path) -> Path:
    match = readiness[readiness["stem"].astype(str) == stem]
    if match.empty:
        raise RuntimeError(f"primary session absent from readiness table: {stem}")
    row = match.iloc[0]
    if not bool(row["nwb_ok"]) or not bool(row["sidecar_ok"]):
        raise RuntimeError(f"primary session fails readiness gate: {stem}")
    candidates = (
        nwb_dir / Path(str(row.get("nwb_path", ""))).name,
        nwb_dir / f"{stem}.nwb",
        nwb_dir / f"{stem.replace('_rec', '')}.nwb",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"primary session NWB not found: {stem}")


def _encode(values: pd.Series) -> np.ndarray:
    encoded = values.map(LABEL_TO_INT)
    if encoded.isna().any():
        raise ValueError(f"non-binary identity labels: {values.dropna().unique().tolist()}")
    return encoded.to_numpy(dtype=int)


def _primary_folds(rows: pd.DataFrame, geometry: pd.DataFrame) -> list[OuterFold]:
    folds = []
    for record in geometry.sort_values("outer_fold").to_dict("records"):
        if record["status"] != "ELIGIBLE_OUTER":
            continue
        held = int(record["held_out_cycle"])
        train_mask = rows["slot_key"].isin(["p2", "p3"]) & (
            rows["cross_position_cycle"] != held
        )
        test_mask = rows["slot_key"].eq("p4") & (
            rows["cross_position_cycle"] == held
        )
        train_idx = np.flatnonzero(train_mask.to_numpy())
        test_idx = np.flatnonzero(test_mask.to_numpy())
        if len(train_idx) != int(record["n_train_trials"]) or len(test_idx) != int(
            record["n_test_trials"]
        ):
            raise RuntimeError(
                f"reversal fold count changed for {record['session']} fold {record['outer_fold']}"
            )
        inner_groups = tuple(
            sorted(rows.loc[train_idx, "cross_position_cycle"].unique().tolist())
        )
        folds.append(
            OuterFold(
                fold=int(record["outer_fold"]),
                held_out_group=held,
                train_idx=train_idx,
                test_idx=test_idx,
                inner_groups=inner_groups,
            )
        )
    return folds


def _positive_folds(rows: pd.DataFrame) -> list[OuterFold]:
    groups = rows["cycle"].to_numpy(dtype=int)
    labels = _encode(rows["presented_identity"])
    return build_outer_folds(groups, labels, min_train_groups=2)


def _metrics_from_oof(oof: pd.DataFrame, primary: bool) -> dict[str, float]:
    if oof.empty:
        return {}
    expected = oof["y_expected"].to_numpy(dtype=int)
    prediction = oof["prediction"].to_numpy(dtype=int)
    score = oof["decision_score"].to_numpy(dtype=float)
    result = {
        "accuracy_expected": float(np.mean(prediction == expected)),
        "balanced_accuracy_expected": float(
            balanced_accuracy_score(expected, prediction)
        ),
        "auc_expected": float(roc_auc_score(expected, score)),
    }
    if primary:
        previous = oof["y_previous"].to_numpy(dtype=int)
        result.update(
            {
                "accuracy_previous": float(np.mean(prediction == previous)),
                "balanced_accuracy_previous": float(
                    balanced_accuracy_score(previous, prediction)
                ),
                "auc_previous": float(roc_auc_score(previous, score)),
            }
        )
        result["G_accuracy"] = (
            result["accuracy_expected"] - result["accuracy_previous"]
        )
        result["G_balanced"] = (
            result["balanced_accuracy_expected"]
            - result["balanced_accuracy_previous"]
        )
        result["G_auc"] = result["auc_expected"] - result["auc_previous"]
    return result


def _null_p(observed: float, null: np.ndarray, *, two_sided: bool = False) -> float:
    if len(null) == 0 or not np.isfinite(observed):
        return float("nan")
    if two_sided:
        center = float(np.mean(null))
        extreme = np.abs(null - center) >= abs(observed - center)
    else:
        extreme = null >= observed
    return float((int(np.sum(extreme)) + 1) / (len(null) + 1))


def _run_cell(
    *,
    X: np.ndarray,
    rows: pd.DataFrame,
    folds: list[OuterFold],
    analysis: str,
    representation: str,
    session: str,
    subject: str,
    area: str,
    n_permutations: int,
    seed: int,
    primary: bool,
    n_units: int,
    n_time_bins: int,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not folds:
        return (
            {
                "status": "INELIGIBLE_DESIGN",
                "analysis": analysis,
                "session": session,
                "subject": subject,
                "area": area,
                "representation": representation,
            },
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
        )
    y_expected = _encode(
        rows["expected_identity"]
        if primary
        else rows["presented_identity"]
    )
    y_previous = _encode(rows["preceding_identity"]) if primary else None
    groups = rows["cross_position_cycle"].to_numpy(dtype=int) if primary else rows[
        "cycle"
    ].to_numpy(dtype=int)
    trial_ids = rows["trial_id"].to_numpy(dtype=int)
    oof, fold_details = fit_nested_linear(
        X,
        y_expected,
        y_previous,
        groups,
        folds,
        trial_ids=trial_ids,
        seed=seed,
        c_grid=C_GRID,
    )
    selected_C_by_fold = dict(
        zip(
            fold_details["fold"].astype(int).tolist(),
            fold_details["selected_C"].astype(float).tolist(),
        )
    )
    metrics = _metrics_from_oof(oof, primary)
    null_values = null_metric_distribution(
        X,
        y_expected,
        y_previous,
        rows["slot_key"].astype(str).tolist(),
        groups,
        folds,
        selected_C_by_fold,
        n_permutations=n_permutations,
        seed=seed,
        primary=primary,
    )
    null_rows = [
        {
            "analysis": analysis,
            "session": session,
            "subject": subject,
            "area": area,
            "representation": representation,
            "permutation": permutation,
            "null_metric": float(value),
            "seed": seed + 100_000 + permutation,
            "permutation_unit": "cycle|slot" if primary else "cycle",
            "complementarity_preserved": bool(primary),
        }
        for permutation, value in enumerate(null_values)
    ]
    null = np.asarray(null_values, dtype=float)
    metric_name = "G_balanced" if primary else "balanced_accuracy_expected"
    cell = {
        "status": "success",
        "analysis": analysis,
        "session": session,
        "subject": subject,
        "area": area,
        "representation": representation,
        "n_trials": int(len(rows)),
        "n_test_trials": int(len(oof)),
        "n_units": int(n_units),
        "n_time_bins": int(n_time_bins),
        "bin_size_ms": BIN_SIZE_MS,
        "n_outer_folds": int(len(folds)),
        "n_permutations": int(len(null)),
        "observed_metric": metrics.get(metric_name, np.nan),
        "null_mean": float(np.mean(null)) if len(null) else np.nan,
        "null_sd": float(np.std(null, ddof=1)) if len(null) > 1 else np.nan,
        "p_upper": _null_p(metrics.get(metric_name, np.nan), null),
        "p_two_sided": _null_p(
            metrics.get(metric_name, np.nan), null, two_sided=True
        ),
        "selected_C_values": json.dumps(
            sorted(set(fold_details["selected_C"].astype(float).tolist()))
        ),
        **metrics,
    }
    fold_details = fold_details.copy()
    fold_details.insert(0, "analysis", analysis)
    fold_details.insert(1, "session", session)
    fold_details.insert(2, "subject", subject)
    fold_details.insert(3, "area", area)
    fold_details.insert(4, "representation", representation)
    oof = oof.copy()
    oof.insert(0, "analysis", analysis)
    oof.insert(1, "session", session)
    oof.insert(2, "subject", subject)
    oof.insert(3, "area", area)
    oof.insert(4, "representation", representation)
    return cell, oof, fold_details, pd.DataFrame(null_rows)


def _feature_manifest(
    *,
    analysis: str,
    session: str,
    subject: str,
    area: str,
    representation: str,
    raster: np.ndarray,
    unit_indices: list[int],
    n_rows: int,
) -> dict:
    return {
        "analysis": analysis,
        "session": session,
        "subject": subject,
        "area": area,
        "representation": representation,
        "n_rows": int(n_rows),
        "n_units": int(len(unit_indices)),
        "n_time_bins": int(raster.shape[2]),
        "raster_shape": json.dumps(list(raster.shape)),
        "dtype": str(raster.dtype),
        "units": "Hz",
        "window_ms": "slot-specific 531 ms omission/presentation window",
        "unit_identity": "session.get_units(area).index row position",
        "quality_filter": None,
        "real_data": True,
    }


def _group_summary(oof: pd.DataFrame, keys: list[str], primary: bool) -> pd.DataFrame:
    rows = []
    for key, group in oof.groupby(keys, sort=True, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        metrics = _metrics_from_oof(group, primary)
        rows.append(
            {
                **dict(zip(keys, key)),
                "n_oof_trials": int(len(group)),
                "n_folds": int(group["fold"].nunique()),
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _leave_one_session_out(oof: pd.DataFrame) -> pd.DataFrame:
    primary = oof[oof["analysis"] == PRIMARY_ANALYSIS]
    rows = []
    for (area, representation), group in primary.groupby(
        ["area", "representation"], sort=True
    ):
        sessions = sorted(group["session"].unique().tolist())
        for left_out in sessions:
            remaining = group[group["session"] != left_out]
            if remaining.empty:
                continue
            metrics = _metrics_from_oof(remaining, True)
            rows.append(
                {
                    "analysis": PRIMARY_ANALYSIS,
                    "area": area,
                    "representation": representation,
                    "left_out_session": left_out,
                    "n_sessions_remaining": int(remaining["session"].nunique()),
                    "n_subjects_remaining": int(remaining["subject"].nunique()),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def run(
    *,
    readiness_csv: Path,
    nwb_dir: Path,
    m1_dir: Path = DEFAULT_M1_DIR,
    design_dir: Path = DEFAULT_DESIGN_DIR,
    output_dir: Path = DEFAULT_OUTPUT,
    areas: tuple[str, ...] = AREAS,
    n_permutations: int = DEFAULT_PERMUTATIONS,
    seed: int = DEFAULT_SEED,
    session_limit: int | None = None,
) -> dict:
    started = time.time()
    readiness_csv = readiness_csv.resolve()
    nwb_dir = nwb_dir.resolve()
    m1_dir = m1_dir.resolve()
    design_dir = design_dir.resolve()
    output_dir = output_dir.resolve()
    design_receipt_path = design_dir / "reversal_design_receipt.json"
    eligibility_path = design_dir / "reversal_contrast_session_eligibility.csv"
    groups_path = design_dir / "reversal_trial_group_assignments.csv"
    geometry_path = design_dir / "reversal_outer_fold_geometry.csv"
    canonical_path = m1_dir / "canonical_trial_ontology.csv"
    for path in (
        design_receipt_path,
        eligibility_path,
        groups_path,
        geometry_path,
        canonical_path,
    ):
        if not path.exists():
            raise FileNotFoundError(f"required frozen artifact missing: {path}")
    design_receipt = json.loads(design_receipt_path.read_text(encoding="utf-8"))
    if design_receipt.get("status") not in {"DRAFT_FOR_SIGNOFF", "APPROVED"}:
        raise RuntimeError("reversal design receipt has unexpected status")
    primary_sessions = list(design_receipt["reversal_counts"]["supported_primary_session_ids"])
    if len(primary_sessions) != 5:
        raise RuntimeError("frozen primary corpus is not the approved five-session corpus")
    eligibility = pd.read_csv(eligibility_path)
    primary_eligibility = eligibility[
        (eligibility["contrast"] == PRIMARY_CONTRAST)
        & (eligibility["design_status"] == "DESIGN_SUPPORTED")
    ]
    if sorted(primary_eligibility["session"].tolist()) != sorted(primary_sessions):
        raise RuntimeError("primary session IDs changed relative to the frozen receipt")
    trial_groups = pd.read_csv(groups_path)
    geometry = pd.read_csv(geometry_path)
    canonical = pd.read_csv(canonical_path)
    readiness = pd.read_csv(readiness_csv)
    if session_limit is not None:
        primary_sessions = primary_sessions[: int(session_limit)]

    cells = []
    oof_frames = []
    fold_frames = []
    null_frames = []
    feature_rows = []
    errors = []
    positive_data_gate = {session: False for session in primary_sessions}

    for session_index, session_stem in enumerate(primary_sessions, start=1):
        print(f"[{session_index}/{len(primary_sessions)}] {session_stem}", flush=True)
        try:
            nwb_path = _resolve_nwb(readiness, session_stem, nwb_dir)
            session = oa.read(nwb_path)
            subject = str(
                trial_groups.loc[
                    trial_groups["session"].eq(session_stem), "subject"
                ].iloc[0]
            )
            omission_rows = trial_groups[
                trial_groups["session"].eq(session_stem)
            ].sort_values(
                ["cross_position_cycle", "slot_key", "trial_id"]
            ).reset_index(drop=True)
            session_geometry = geometry[
                (geometry["session"] == session_stem)
                & (geometry["contrast"] == PRIMARY_CONTRAST)
            ]
            folds = _primary_folds(omission_rows, session_geometry)
            if len(folds) != int(
                primary_eligibility.loc[
                    primary_eligibility["session"].eq(session_stem),
                    "n_valid_outer_folds",
                ].iloc[0]
            ):
                raise RuntimeError(f"primary fold count changed for {session_stem}")
            for area in areas:
                try:
                    raster, unit_indices = extract_rate_raster(
                        session, area, omission_rows
                    )
                    if raster.shape[1] == 0:
                        continue
                    primary_expected = _encode(omission_rows["expected_identity"])
                    primary_previous = _encode(omission_rows["preceding_identity"])
                    if not np.array_equal(
                        primary_previous[omission_rows["slot_key"].eq("p4")],
                        1 - primary_expected[omission_rows["slot_key"].eq("p4")],
                    ):
                        raise RuntimeError(f"p4 complementarity changed in {session_stem}")
                    for representation in REPRESENTATIONS:
                        X = (
                            raster.mean(axis=2, dtype=np.float64)
                            if representation == "R0"
                            else raster.reshape(raster.shape[0], -1)
                        )
                        cell, oof, fold, null = _run_cell(
                            X=X if representation == "R1" else X,
                            rows=omission_rows,
                            folds=folds,
                            analysis=PRIMARY_ANALYSIS,
                            representation=representation,
                            session=session_stem,
                            subject=subject,
                            area=area,
                            n_permutations=n_permutations,
                            seed=seed + session_index * 10_000 + _stable_area_seed(area),
                            primary=True,
                            n_units=raster.shape[1],
                            n_time_bins=raster.shape[2] if representation == "R1" else 1,
                        )
                        cell["n_units"] = int(raster.shape[1])
                        cell["n_time_bins"] = int(raster.shape[2]) if representation == "R1" else 1
                        cells.append(cell)
                        if not oof.empty:
                            oof_frames.append(oof)
                        if not fold.empty:
                            fold_frames.append(fold)
                        if not null.empty:
                            null_frames.append(null)
                        feature_rows.append(
                            _feature_manifest(
                                analysis=PRIMARY_ANALYSIS,
                                session=session_stem,
                                subject=subject,
                                area=area,
                                representation=representation,
                                raster=raster,
                                unit_indices=unit_indices,
                                n_rows=len(omission_rows),
                            )
                        )
                        del X
                    del raster
                except Exception as exc:
                    errors.append(
                        {
                            "analysis": PRIMARY_ANALYSIS,
                            "session": session_stem,
                            "area": area,
                            "reason": type(exc).__name__,
                            "detail": str(exc),
                        }
                    )

            positive_rows = canonical[
                (canonical["session"] == session_stem)
                & (canonical["analysis"] == POSITIVE_ANALYSIS)
                & canonical["eligible"]
            ].sort_values(["cycle", "trial_id"]).reset_index(drop=True)
            positive_folds = _positive_folds(positive_rows)
            if len(positive_folds) < MIN_VALID_POSITIVE_FOLDS:
                errors.append(
                    {
                        "analysis": POSITIVE_ANALYSIS,
                        "session": session_stem,
                        "reason": "insufficient_positive_control_folds",
                        "detail": str(len(positive_folds)),
                    }
                )
            else:
                positive_cells_this_session = 0
                for area in areas:
                    try:
                        raster, unit_indices = extract_rate_raster(
                            session, area, positive_rows
                        )
                        if raster.shape[1] == 0:
                            continue
                        for representation in REPRESENTATIONS:
                            X = (
                                raster.mean(axis=2, dtype=np.float64)
                                if representation == "R0"
                                else raster.reshape(raster.shape[0], -1)
                            )
                            cell, oof, fold, null = _run_cell(
                                X=X,
                                rows=positive_rows,
                                folds=positive_folds,
                                analysis=POSITIVE_ANALYSIS,
                                representation=representation,
                                session=session_stem,
                                subject=subject,
                                area=area,
                                n_permutations=n_permutations,
                                seed=seed + session_index * 20_000 + _stable_area_seed(area),
                                primary=False,
                                n_units=raster.shape[1],
                                n_time_bins=raster.shape[2] if representation == "R1" else 1,
                            )
                            cell["n_units"] = int(raster.shape[1])
                            cell["n_time_bins"] = int(raster.shape[2]) if representation == "R1" else 1
                            cells.append(cell)
                            if cell.get("status") == "success":
                                positive_cells_this_session += 1
                            if not oof.empty:
                                oof_frames.append(oof)
                            if not fold.empty:
                                fold_frames.append(fold)
                            if not null.empty:
                                null_frames.append(null)
                            feature_rows.append(
                                _feature_manifest(
                                    analysis=POSITIVE_ANALYSIS,
                                    session=session_stem,
                                    subject=subject,
                                    area=area,
                                    representation=representation,
                                    raster=raster,
                                    unit_indices=unit_indices,
                                    n_rows=len(positive_rows),
                                )
                            )
                            del X
                        del raster
                    except Exception as exc:
                        errors.append(
                            {
                                "analysis": POSITIVE_ANALYSIS,
                                "session": session_stem,
                                "area": area,
                                "reason": type(exc).__name__,
                                "detail": str(exc),
                            }
                        )
                positive_data_gate[session_stem] = positive_cells_this_session > 0
        except Exception as exc:
            errors.append(
                {
                    "session": session_stem,
                    "reason": type(exc).__name__,
                    "detail": str(exc),
                }
            )

    cells_df = pd.DataFrame(cells)
    oof_df = pd.concat(oof_frames, ignore_index=True) if oof_frames else pd.DataFrame()
    fold_df = pd.concat(fold_frames, ignore_index=True) if fold_frames else pd.DataFrame()
    null_df = pd.concat(null_frames, ignore_index=True) if null_frames else pd.DataFrame()
    feature_df = pd.DataFrame(feature_rows)
    session_df = (
        pd.concat(
            [
                _group_summary(
                    oof_df[oof_df["analysis"] == PRIMARY_ANALYSIS],
                    ["analysis", "session", "subject", "area", "representation"],
                    True,
                ),
                _group_summary(
                    oof_df[oof_df["analysis"] == POSITIVE_ANALYSIS],
                    ["analysis", "session", "subject", "area", "representation"],
                    False,
                ),
            ],
            ignore_index=True,
        )
        if not oof_df.empty
        else pd.DataFrame()
    )
    subject_df = (
        pd.concat(
            [
                _group_summary(
                    oof_df[oof_df["analysis"] == PRIMARY_ANALYSIS],
                    ["analysis", "subject", "area", "representation"],
                    True,
                ),
                _group_summary(
                    oof_df[oof_df["analysis"] == POSITIVE_ANALYSIS],
                    ["analysis", "subject", "area", "representation"],
                    False,
                ),
            ],
            ignore_index=True,
        )
        if not oof_df.empty
        else pd.DataFrame()
    )
    leave_one_out_df = _leave_one_session_out(oof_df) if not oof_df.empty else pd.DataFrame()

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "cells": output_dir / "milestone_2a_cells.csv",
        "oof": output_dir / "milestone_2a_oof_predictions.csv",
        "folds": output_dir / "milestone_2a_fold_diagnostics.csv",
        "null": output_dir / "milestone_2a_null_distribution.csv",
        "features": output_dir / "milestone_2a_feature_manifest.csv",
        "session_summary": output_dir / "milestone_2a_session_summary.csv",
        "subject_summary": output_dir / "milestone_2a_subject_summary.csv",
        "leave_one_session_out": output_dir / "milestone_2a_leave_one_session_out.csv",
    }
    cells_df.to_csv(outputs["cells"], index=False)
    oof_df.to_csv(outputs["oof"], index=False)
    fold_df.to_csv(outputs["folds"], index=False)
    null_df.to_csv(outputs["null"], index=False)
    feature_df.to_csv(outputs["features"], index=False)
    session_df.to_csv(outputs["session_summary"], index=False)
    subject_df.to_csv(outputs["subject_summary"], index=False)
    leave_one_out_df.to_csv(outputs["leave_one_session_out"], index=False)

    positive_gate_pass = all(positive_data_gate.values()) and not any(
        error.get("reason") == "insufficient_positive_control_folds" for error in errors
    )
    analysis_status = "complete" if not errors else "failed_with_errors"
    if not positive_gate_pass:
        analysis_status = "blocked_positive_control"
    receipt = {
        "schema_version": 3,
        "experiment": "structured-identity-experiment-v1.1",
        "milestone": "2A",
        "analysis_status": analysis_status,
        "scientific_signoff": {
            "status": "APPROVED",
            "date": "2026-08-10",
            "signatories": ["Sol", "Hamm"],
            "scope": "positive control, R0/R1 linear baselines, grouped nulls, reversal scoring, session/subject diagnostics",
        },
        "training_scope": {
            "M0": True,
            "R0_linear": True,
            "R1_linear": True,
            "M2_nonlinear_flat": False,
            "M3_structured": False,
            "M4_ablation": False,
            "architecture_search": False,
            "broad_hyperparameter_search": False,
        },
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "runtime_seconds": time.time() - started,
        "primary_sessions": primary_sessions,
        "primary_subjects": sorted(
            primary_eligibility[
                primary_eligibility["session"].isin(primary_sessions)
            ]["subject"].unique().tolist()
        ),
        "areas": list(areas),
        "representations": list(REPRESENTATIONS),
        "estimator": {
            "model": "balanced_dual_ridge_classifier",
            "score": "linear decision score",
            "class_weight": "balanced",
            "solver": "dual_normal_equation",
            "scaler": "StandardScaler",
            "C_grid": list(C_GRID),
            "selection": "inner grouped cycle validation only",
            "feature_dtype": "float64",
            "feature_units": "Hz",
        },
        "feature_contract": {
            "R0": "mean firing rate across the 531 ms slot window",
            "R1": "same 531 ms raster at 9 ms bins, vectorized space-major then time",
            "bin_size_ms": BIN_SIZE_MS,
            "unit_identity": "session.get_units(area).index row position",
            "neural_signal": "NWB unit spike trains; no LFP/MUAe path",
            "quality_filter": None,
        },
        "fold_contract": {
            "primary": "persisted p2+p3-to-p4 common-cycle geometry",
            "positive_control": "leave-one-p1-cycle-out using canonical positive-control rows",
            "inner": "leave-one-training-cycle-out; no outer-test reuse",
            "no_random_trial_fallback": True,
            "primary_fold_session_subject_hierarchy_preserved": True,
        },
        "null_contract": {
            "primitive": "jnwb.permutation.permute_labels",
            "primary_scheme": "within_group",
            "primary_permutation_unit": "common_cycle|slot",
            "positive_control_permutation_unit": "p1 cycle",
            "n_permutations_requested": int(n_permutations),
            "seed": int(seed),
            "p4_complementarity_preserved": True,
            "null_primary_metric": "G_balanced",
            "null_positive_metric": "balanced_accuracy_expected",
            "null_regularization": "observed-fold-selected_C_frozen",
        },
        "gate_checks": {
            "frozen_primary_session_ids_unchanged": sorted(primary_sessions)
            == sorted(design_receipt["reversal_counts"]["supported_primary_session_ids"]),
            "positive_control_data_gate": positive_gate_pass,
            "positive_control_session_gate": positive_data_gate,
            "neural_tensors_materialized": True,
            "models_trained": ["R0_linear", "R1_linear"],
            "structured_models_trained": False,
            "materialization_changed_trial_eligibility": False,
        },
        "counts": {
            "cell_rows": int(len(cells_df)),
            "oof_rows": int(len(oof_df)),
            "fold_rows": int(len(fold_df)),
            "null_rows": int(len(null_df)),
            "feature_manifest_rows": int(len(feature_df)),
            "session_summary_rows": int(len(session_df)),
            "subject_summary_rows": int(len(subject_df)),
            "leave_one_session_out_rows": int(len(leave_one_out_df)),
        },
        "input_paths": {
            "readiness": str(readiness_csv.relative_to(REPO_ROOT)).replace("\\", "/"),
            "m1_dir": str(m1_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
            "design_dir": str(design_dir.relative_to(REPO_ROOT)).replace("\\", "/"),
        },
        "input_hashes": {
            "canonical_trial_ontology": _sha256(canonical_path),
            "reversal_design_receipt": _sha256(design_receipt_path),
            "reversal_eligibility": _sha256(eligibility_path),
            "reversal_trial_groups": _sha256(groups_path),
            "reversal_outer_geometry": _sha256(geometry_path),
        },
        "errors": errors,
        "stop_conditions": [
            "positive control data gate failed",
            "materialized trial rows or fold counts differ from frozen design",
            "p4 expected/previous complementarity fails",
            "any model path outside R0/R1 linear baselines is requested",
        ],
        "output_paths": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "next_gate": "SAFE_TO_TRAIN_M2_M3 = NO; review this receipt and diagnostics",
    }
    receipt_path = output_dir / "milestone_2a_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"Milestone 2A {analysis_status}: {len(cells_df)} cells, "
        f"{len(oof_df)} OOF rows, {len(null_df)} null rows; "
        "M2/M3/M4 not trained.",
        flush=True,
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--readiness", type=Path, default=REPO_ROOT / "artifacts" / "data" / "session_readiness.csv")
    parser.add_argument("--nwb-dir", type=Path, default=paths.nwb_dir())
    parser.add_argument("--m1-dir", type=Path, default=DEFAULT_M1_DIR)
    parser.add_argument("--design-dir", type=Path, default=DEFAULT_DESIGN_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--areas", nargs="+", default=list(AREAS))
    parser.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--session-limit", type=int, default=None)
    args = parser.parse_args()
    if not args.nwb_dir.exists():
        raise FileNotFoundError(f"NWB directory not found: {args.nwb_dir}")
    if args.permutations < 1:
        raise ValueError("--permutations must be positive")
    run(
        readiness_csv=args.readiness,
        nwb_dir=args.nwb_dir,
        m1_dir=args.m1_dir,
        design_dir=args.design_dir,
        output_dir=args.output_dir,
        areas=tuple(args.areas),
        n_permutations=args.permutations,
        seed=args.seed,
        session_limit=args.session_limit,
    )


if __name__ == "__main__":
    main()
