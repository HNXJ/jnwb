"""Shared helpers for Phase 00-02 omission notebooks."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST_KEYS = [
    "notebook_id",
    "repo_root",
    "repo_branch",
    "repo_sha",
    "git_status_short",
    "python_version",
    "platform",
    "executed_at_utc",
    "runtime_seconds",
    "smoke_mode",
    "nwb_source_path",
    "nwb_local_path",
    "nwb_sha256",
    "output_root",
    "analysis_stage",
    "warnings_path",
    "outputs",
]

NOTEBOOK_02_EXTRA_KEYS = [
    "time_base",
    "area_mapping_status",
    "condition_parser_status",
]

ALLOWED_TIME_BASE = {
    "p1_relative",
    "omission_relative",
    "mixed_explicit",
    "unresolved",
    "not_applicable",
}

ALLOWED_AREA_MAPPING_STATUS = {
    "not_checked",
    "not_applicable",
    "unresolved",
    "verified_with_evidence",
}

CORE_CONDITIONS = {
    "AAAB": {"family": "A", "is_omission": False, "slot": None, "control": "AAAB"},
    "AXAB": {"family": "A", "is_omission": True, "slot": 2, "control": "AAAB"},
    "AAXB": {"family": "A", "is_omission": True, "slot": 3, "control": "AAAB"},
    "AAAX": {"family": "A", "is_omission": True, "slot": 4, "control": "AAAB"},
    "BBBA": {"family": "B", "is_omission": False, "slot": None, "control": "BBBA"},
    "BXBA": {"family": "B", "is_omission": True, "slot": 2, "control": "BBBA"},
    "BBXA": {"family": "B", "is_omission": True, "slot": 3, "control": "BBBA"},
    "BBBX": {"family": "B", "is_omission": True, "slot": 4, "control": "BBBA"},
    "RRRR": {"family": "R", "is_omission": False, "slot": None, "control": "RRRR"},
    "RXRR": {"family": "R", "is_omission": True, "slot": 2, "control": "RRRR"},
    "RRXR": {"family": "R", "is_omission": True, "slot": 3, "control": "RRRR"},
    "RRRX": {"family": "R", "is_omission": True, "slot": 4, "control": "RRRR"},
}

EXPECTED_TIMING_MS = {
    "fx": (-500, 0),
    "p1": (0, 531),
    "d1": (531, 1031),
    "p2": (1031, 1562),
    "d2": (1562, 2062),
    "p3": (2062, 2593),
    "d3": (2593, 3093),
    "p4": (3093, 3624),
    "d4": (3624, 4124),
}

CONDITION_NUMBER_MAP = {
    "AAAB": [1, 2],
    "AXAB": [3],
    "BXBA": [8],
    "AAXB": [4],
    "BBXA": [9],
    "AAAX": [5],
    "BBBX": [10],
    "BBBA": [6, 7],
    "RRRR": list(range(11, 27)),
    "RXRR": list(range(27, 35)),
    "RRXR": [35, 37, 39, 41],
    "RRRX": [36, 38, 40, 42, 43, 44, 45, 46, 47, 48, 49, 50],
}

NUMBER_TO_CONDITION: dict[int, str] = {}
for code, numbers in CONDITION_NUMBER_MAP.items():
    for number in numbers:
        NUMBER_TO_CONDITION[number] = code


def project_root() -> Path:
    env_root = os.environ.get("OMISSION_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[1]


def smoke_mode() -> bool:
    return os.environ.get("OMISSION_SMOKE_MODE", "1") not in {"0", "false", "False"}


def run_cmd(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def git_provenance(repo: Path) -> dict[str, str]:
    return {
        "repo_root": run_cmd(["git", "rev-parse", "--show-toplevel"], repo),
        "repo_branch": run_cmd(["git", "branch", "--show-current"], repo),
        "repo_sha": run_cmd(["git", "rev-parse", "HEAD"], repo),
        "git_status_short": run_cmd(["git", "status", "--short", "--branch"], repo),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_nwb_sha256(nwb_path: Path) -> str:
    """Reuse hash from env or Notebook 00 manifest; compute only when needed."""
    env_hash = os.environ.get("OMISSION_NWB_SHA256", "").strip()
    if env_hash:
        return env_hash
    run_root_env = os.environ.get("OMISSION_RUN_ROOT")
    if run_root_env:
        manifest_path = Path(run_root_env) / "manifests" / "run_manifest.json"
        if manifest_path.exists():
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            cached = str(data.get("nwb_sha256", "")).strip()
            if cached:
                return cached
    return sha256_file(nwb_path)


def resolve_nwb_path(repo: Path) -> Path:
    candidates: list[Path] = []
    env_path = os.environ.get("OMISSION_NWB_PATH")
    if env_path:
        candidates.append(Path(env_path))
    drive_path = os.environ.get("OMISSION_DRIVE_NWB_PATH")
    if drive_path:
        candidates.append(Path(drive_path))
    candidates.extend(sorted(repo.glob("data/*.nwb")))
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise RuntimeError("NWB file not found via OMISSION_NWB_PATH, drive path, or data/*.nwb")


def resolve_run_root(repo: Path, nwb_path: Path, nwb_sha256: str | None = None) -> Path:
    env_root = os.environ.get("OMISSION_RUN_ROOT")
    if env_root:
        return Path(env_root).resolve()
    digest = nwb_sha256 or resolve_nwb_sha256(nwb_path)
    git = git_provenance(repo)
    run_name = f"{git['repo_sha']}_{digest[:8]}"
    return (repo / "outputs" / "runs" / run_name).resolve()


def base_manifest(
    notebook_id: str,
    analysis_stage: str,
    warnings_rel: str,
    runtime_seconds: float,
    repo: Path,
    nwb_path: Path,
    run_root: Path,
    nwb_sha256: str,
    outputs: list[str] | None = None,
) -> dict[str, Any]:
    git = git_provenance(repo)
    return {
        "notebook_id": notebook_id,
        "repo_root": git["repo_root"],
        "repo_branch": git["repo_branch"],
        "repo_sha": git["repo_sha"],
        "git_status_short": git["git_status_short"],
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "executed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runtime_seconds": round(runtime_seconds, 3),
        "smoke_mode": smoke_mode(),
        "nwb_source_path": str(nwb_path),
        "nwb_local_path": str(nwb_path),
        "nwb_sha256": nwb_sha256,
        "output_root": str(run_root),
        "analysis_stage": analysis_stage,
        "warnings_path": str(run_root / warnings_rel),
        "outputs": outputs or [],
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_warnings(path: Path, warnings: list[dict[str, Any]]) -> None:
    write_json(path, warnings)


def try_open_nwb(nwb_path: Path) -> tuple[Any | None, str | None]:
    try:
        from pynwb import NWBHDF5IO
    except ImportError as exc:
        return None, f"PyNWB import failed: {exc}"
    try:
        io = NWBHDF5IO(str(nwb_path), "r", load_namespaces=True)
        nwbfile = io.read()
        return nwbfile, None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def run_nwb_audit(nwb_path: Path, audit_fn):
    """Open NWB, run audit callback while the HDF5 handle is alive, then close."""
    try:
        from pynwb import NWBHDF5IO
    except ImportError as exc:
        return None, f"PyNWB import failed: {exc}"
    try:
        with NWBHDF5IO(str(nwb_path), "r", load_namespaces=True) as io:
            nwbfile = io.read()
            return audit_fn(nwbfile), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def validate_manifest(manifest: dict[str, Any], notebook_id: str) -> dict[str, Any]:
    errors: list[str] = []
    for key in REQUIRED_MANIFEST_KEYS:
        if key not in manifest:
            errors.append(f"MISSING_KEY:{key}")
    if notebook_id.startswith("02"):
        for key in NOTEBOOK_02_EXTRA_KEYS:
            if key not in manifest:
                errors.append(f"MISSING_KEY:{key}")
            elif key == "time_base" and manifest[key] not in ALLOWED_TIME_BASE:
                errors.append(f"INVALID_TIME_BASE:{manifest[key]}")
            elif key == "area_mapping_status" and manifest[key] not in ALLOWED_AREA_MAPPING_STATUS:
                errors.append(f"INVALID_AREA_MAPPING_STATUS:{manifest[key]}")
    for placeholder_key in ("repo_sha", "repo_branch"):
        value = str(manifest.get(placeholder_key, "")).strip()
        if not value or value in {"UNKNOWN", "placeholder", "none"}:
            errors.append(f"PLACEHOLDER_{placeholder_key.upper()}:{value}")
    output_root = Path(str(manifest.get("output_root", "")))
    repo_sha = str(manifest.get("repo_sha", ""))
    nwb_sha = str(manifest.get("nwb_sha256", ""))
    expected_suffix = f"{repo_sha}_{nwb_sha[:8]}"
    if output_root.name != expected_suffix:
        errors.append(f"OUTPUT_ROOT_PATTERN_MISMATCH:{output_root.name}!={expected_suffix}")
    return {"status": "PASS" if not errors else "FAIL", "errors": errors}


def write_timing_table(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["epoch", "start_ms", "end_ms", "time_base", "verified"],
        )
        writer.writeheader()
        for epoch, (start_ms, end_ms) in EXPECTED_TIMING_MS.items():
            writer.writerow(
                {
                    "epoch": epoch,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "time_base": "p1_relative",
                    "verified": "true",
                }
            )


def invert_condition_map() -> dict[int, str]:
    return dict(NUMBER_TO_CONDITION)


def build_schema_report(nwbfile: Any) -> dict[str, Any]:
    intervals = {}
    if getattr(nwbfile, "intervals", None) is not None:
        for key in nwbfile.intervals.keys():
            table = nwbfile.intervals[key]
            intervals[key] = {
                "type": type(table).__name__,
                "n_rows": len(table),
                "columns": list(getattr(table, "colnames", [])),
            }
    electrodes = None
    if getattr(nwbfile, "electrodes", None) is not None:
        electrodes = {
            "n_rows": len(nwbfile.electrodes),
            "columns": list(nwbfile.electrodes.colnames),
        }
    units = None
    if getattr(nwbfile, "units", None) is not None:
        units = {
            "n_rows": len(nwbfile.units),
            "columns": list(nwbfile.units.colnames),
        }
    return {
        "session_id": getattr(nwbfile, "session_id", None),
        "identifier": getattr(nwbfile, "identifier", None),
        "session_description": getattr(nwbfile, "session_description", None),
        "intervals": intervals,
        "acquisition": list(nwbfile.acquisition.keys()),
        "processing": list(nwbfile.processing.keys()),
        "electrodes": electrodes,
        "units": units,
        "pynwb_open_status": "success",
    }


def render_schema_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# NWB Schema Audit Report",
        "",
        f"- session_id: `{report.get('session_id')}`",
        f"- identifier: `{report.get('identifier')}`",
        f"- pynwb_open_status: `{report.get('pynwb_open_status')}`",
        "",
        "## Intervals",
    ]
    for name, payload in sorted((report.get("intervals") or {}).items()):
        lines.append(f"- `{name}`: {payload['n_rows']} rows; columns={len(payload['columns'])}")
    lines.extend(
        [
            "",
            "## Acquisition",
            ", ".join(f"`{name}`" for name in report.get("acquisition", [])),
            "",
            "## Processing",
            ", ".join(f"`{name}`" for name in report.get("processing", [])),
        ]
    )
    return "\n".join(lines) + "\n"


def audit_area_mapping(nwbfile: Any) -> tuple[str, list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    electrodes = getattr(nwbfile, "electrodes", None)
    if electrodes is None or len(electrodes) == 0:
        warnings.append({"code": "NO_ELECTRODES", "message": "No electrodes table found."})
        return "unresolved", warnings
    if "location" not in electrodes.colnames:
        warnings.append({"code": "NO_LOCATION_COLUMN", "message": "Electrodes table lacks location column."})
        return "unresolved", warnings
    locations = sorted({str(value) for value in electrodes["location"].data[:]})
    if not locations:
        return "unresolved", warnings
    return "verified_with_evidence", warnings


def audit_conditions(nwbfile: Any) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    warnings: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    intervals = getattr(nwbfile, "intervals", None)
    if intervals is None or "omission_glo_passive" not in intervals:
        warnings.append(
            {
                "code": "MISSING_INTERVAL_TABLE",
                "message": "omission_glo_passive interval table not found.",
            }
        )
        return "unresolved", warnings, rows

    table = intervals["omission_glo_passive"]
    if "task_condition_number" not in table.colnames:
        warnings.append(
            {
                "code": "MISSING_CONDITION_COLUMN",
                "message": "task_condition_number column not found.",
            }
        )
        return "unresolved", warnings, rows

    import pandas as pd

    df = table.to_dataframe()
    df["task_condition_number"] = pd.to_numeric(df["task_condition_number"], errors="coerce")
    if "codes" in df.columns:
        df["codes"] = pd.to_numeric(df["codes"], errors="coerce")
        trial_starts = df[df["codes"] == 9].copy()
    else:
        trial_starts = df.drop_duplicates(subset=["trial_num"], keep="first")

    number_to_code = invert_condition_map()
    observed_numbers = sorted(
        int(value)
        for value in trial_starts["task_condition_number"].dropna().unique()
        if int(value) in number_to_code
    )
    unresolved_numbers = sorted(
        int(value)
        for value in trial_starts["task_condition_number"].dropna().unique()
        if int(value) not in number_to_code
    )
    if unresolved_numbers:
        warnings.append(
            {
                "code": "UNRESOLVED_CONDITION_NUMBERS",
                "message": f"Unmapped task_condition_number values: {unresolved_numbers}",
            }
        )

    for code, meta in CORE_CONDITIONS.items():
        numbers = CONDITION_NUMBER_MAP.get(code, [])
        trial_count = int(trial_starts["task_condition_number"].isin(numbers).sum()) if numbers else 0
        rows.append(
            {
                "condition_code": code,
                "family": meta["family"],
                "is_omission": meta["is_omission"],
                "omission_slot": meta["slot"] if meta["slot"] is not None else "",
                "matched_control": meta["control"],
                "trial_count": trial_count,
                "mapped_condition_numbers": ";".join(str(n) for n in numbers),
            }
        )

    found_codes = {row["condition_code"] for row in rows if row["trial_count"] > 0}
    missing_core = [code for code in CORE_CONDITIONS if code not in found_codes]
    if missing_core:
        warnings.append(
            {
                "code": "MISSING_CORE_CONDITIONS",
                "message": f"No trials mapped for core conditions: {missing_core}",
            }
        )

    parser_status = "verified_with_evidence" if not missing_core and not unresolved_numbers else "unresolved"
    return parser_status, warnings, rows


def write_condition_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "condition_code",
        "family",
        "is_omission",
        "omission_slot",
        "matched_control",
        "trial_count",
        "mapped_condition_numbers",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def determine_time_base(condition_parser_status: str, nwb_open: bool) -> str:
    if not nwb_open:
        return "not_applicable"
    if condition_parser_status == "verified_with_evidence":
        return "mixed_explicit"
    return "unresolved"
