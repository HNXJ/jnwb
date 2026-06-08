#!/usr/bin/env python3
"""Batch Phase 00-02 notebook audit across all PyNWB-loadable NWB sessions."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

NOTEBOOK_DIR = Path(__file__).resolve().parent
REPO = NOTEBOOK_DIR.parent
NWB_DIR = Path(r"D:\analysis\nwb")
BASELINE = NWB_DIR / "sub-C31o_ses-230630_rec.nwb"
BASELINE_RUN = REPO / "outputs" / "runs" / "52461b8e06890033c93c6dbfb2453a4699a732c2_0c34230e"

sys.path.insert(0, str(NOTEBOOK_DIR))
from _omission_run_common import validate_manifest  # noqa: E402

NOTEBOOKS = [
    ("00", NOTEBOOK_DIR / "00_colab_setup_and_manifest.ipynb"),
    ("01", NOTEBOOK_DIR / "01_nwb_schema_audit.ipynb"),
    ("02", NOTEBOOK_DIR / "02_task_timing_condition_audit.ipynb"),
]

SESSION_RE = re.compile(r"sub-(?P<subject>[^_]+)_ses-(?P<session>\d+)")


def parse_subject_session(path: Path) -> tuple[str, str]:
    match = SESSION_RE.search(path.name)
    if not match:
        return "unknown", path.stem
    return match.group("subject"), match.group("session")


def run_nbconvert(notebook: Path, env: dict[str, str], timeout: int = 900) -> tuple[int, float]:
    cmd = [
        "jupyter",
        "nbconvert",
        "--to",
        "notebook",
        "--execute",
        str(notebook),
        f"--ExecutePreprocessor.timeout={timeout}",
        "--output",
        f"_batch_{notebook.stem}.ipynb",
    ]
    start = time.time()
    proc = subprocess.run(cmd, cwd=str(NOTEBOOK_DIR), env=env, capture_output=True, text=True)
    return proc.returncode, time.time() - start


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def count_warnings(run_root: Path) -> int:
    total = 0
    for name in ("00_warnings.json", "01_warnings.json", "02_warnings.json"):
        payload = load_json(run_root / "warnings" / name)
        if isinstance(payload, list):
            total += len(payload)
    return total


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))


def classify_notebook02(manifest: dict | None, exit_code: int) -> tuple[str, str | None]:
    if exit_code != 0:
        if manifest is None:
            return "OTHER_ERROR", "nbconvert_exit_nonzero"
        status = manifest.get("notebook_status", "BLOCKED")
        if status == "PASS":
            return "PASS", None
        parser = manifest.get("condition_parser_status")
        if parser == "unresolved":
            return "BLOCKED_CONDITION_PARSER", "condition_parser_status_unresolved"
        return "OTHER_ERROR", "nbconvert_exit_nonzero"
    if manifest is None:
        return "MANIFEST_INVALID", "missing_task_timing_manifest"
    validation = validate_manifest(manifest, "02_task_timing_condition_audit")
    if validation["status"] != "PASS":
        return "MANIFEST_INVALID", ";".join(validation["errors"])
    if manifest.get("notebook_status") != "PASS":
        parser = manifest.get("condition_parser_status")
        if parser == "unresolved":
            return "BLOCKED_CONDITION_PARSER", "condition_parser_status_unresolved"
        return "OTHER_ERROR", manifest.get("notebook_status", "blocked")
    timing_path = Path(manifest["output_root"]) / "tables" / "timing_table.csv"
    if count_csv_rows(timing_path) != 9:
        return "BLOCKED_TIMING_CONSTANTS", "timing_epoch_count_not_9"
    return "PASS", None


def classify_notebook01(manifest: dict | None, exit_code: int) -> tuple[str, str | None]:
    if manifest is None:
        return "MANIFEST_INVALID" if exit_code == 0 else "OTHER_ERROR", "missing_nwb_schema_manifest"
    if manifest.get("pynwb_open_status") != "success":
        return "BLOCKED_NWB_OPEN_FAILED", str(manifest.get("pynwb_open_status", "failed"))
    if exit_code != 0:
        return "OTHER_ERROR", "nbconvert_exit_nonzero"
    validation = validate_manifest(manifest, "01_nwb_schema_audit")
    if validation["status"] != "PASS":
        return "MANIFEST_INVALID", ";".join(validation["errors"])
    return "PASS", None


def classify_notebook00(manifest: dict | None, exit_code: int) -> tuple[str, str | None]:
    if exit_code != 0:
        return "OTHER_ERROR", "nbconvert_exit_nonzero"
    if manifest is None:
        return "MANIFEST_INVALID", "missing_run_manifest"
    validation = validate_manifest(manifest, "00_colab_setup_and_manifest")
    if validation["status"] != "PASS":
        return "MANIFEST_INVALID", ";".join(validation["errors"])
    return "PASS", None


def summarize_existing_baseline() -> dict:
    run_manifest = load_json(BASELINE_RUN / "manifests" / "run_manifest.json")
    schema_manifest = load_json(BASELINE_RUN / "manifests" / "nwb_schema_manifest.json")
    task_manifest = load_json(BASELINE_RUN / "manifests" / "task_timing_condition_manifest.json")
    subject, session = parse_subject_session(BASELINE)
    nb00, _ = classify_notebook00(run_manifest, 0)
    nb01, b01 = classify_notebook01(schema_manifest, 0)
    nb02, b02 = classify_notebook02(task_manifest, 0)
    blocker = b01 or b02
    return {
        "subject": subject,
        "session": session,
        "nwb_path": str(BASELINE),
        "nwb_size_bytes": BASELINE.stat().st_size,
        "nwb_sha256": run_manifest.get("nwb_sha256") if run_manifest else "",
        "run_root": str(BASELINE_RUN),
        "notebook00_status": nb00,
        "notebook01_status": nb01,
        "notebook02_status": nb02,
        "time_base": task_manifest.get("time_base") if task_manifest else "",
        "area_mapping_status": task_manifest.get("area_mapping_status") if task_manifest else "",
        "condition_parser_status": task_manifest.get("condition_parser_status") if task_manifest else "",
        "condition_count": count_csv_rows(BASELINE_RUN / "tables" / "condition_table.csv"),
        "timing_epoch_count": count_csv_rows(BASELINE_RUN / "tables" / "timing_table.csv"),
        "warnings_count": count_warnings(BASELINE_RUN),
        "blocker": blocker or "",
        "runtime_total_seconds": 0.0,
        "source": "preserved_baseline_run",
    }


def audit_session(nwb_path: Path) -> dict:
    subject, session = parse_subject_session(nwb_path)
    env = os.environ.copy()
    env["OMISSION_REPO_ROOT"] = str(REPO)
    env["OMISSION_NWB_PATH"] = str(nwb_path)
    env.pop("OMISSION_RUN_ROOT", None)
    env.pop("OMISSION_NWB_SHA256", None)

    total_runtime = 0.0
    run_root: Path | None = None
    nb_status = {"00": "OTHER_ERROR", "01": "OTHER_ERROR", "02": "OTHER_ERROR"}
    blocker: str | None = None

    for nb_id, notebook in NOTEBOOKS:
        code, elapsed = run_nbconvert(notebook, env)
        total_runtime += elapsed
        if nb_id == "00":
            run_manifest = None
            if code == 0:
                # refresh env from notebook 00 outputs
                candidates = sorted((REPO / "outputs" / "runs").glob(f"*"))
                # read latest matching manifest for this nwb path
                for run_dir in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
                    manifest_path = run_dir / "manifests" / "run_manifest.json"
                    if not manifest_path.exists():
                        continue
                    data = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if Path(data.get("nwb_source_path", "")).resolve() == nwb_path.resolve():
                        run_manifest = data
                        run_root = Path(data["output_root"])
                        env["OMISSION_RUN_ROOT"] = str(run_root)
                        env["OMISSION_NWB_SHA256"] = data["nwb_sha256"]
                        break
            nb_status["00"], blocker = classify_notebook00(run_manifest, code)
            if nb_status["00"] != "PASS":
                blocker = blocker or "notebook00_failed"
                break
            continue

        if nb_id == "01":
            schema_manifest = load_json((run_root or Path()) / "manifests" / "nwb_schema_manifest.json") if run_root else None
            nb_status["01"], b = classify_notebook01(schema_manifest, code)
            if nb_status["01"] != "PASS":
                blocker = b or blocker
                if nb_status["01"] == "BLOCKED_NWB_OPEN_FAILED":
                    break
            continue

        if nb_id == "02":
            task_manifest = load_json((run_root or Path()) / "manifests" / "task_timing_condition_manifest.json") if run_root else None
            nb_status["02"], b = classify_notebook02(task_manifest, code)
            if nb_status["02"] != "PASS":
                blocker = b or blocker

    run_manifest = load_json((run_root or Path()) / "manifests" / "run_manifest.json") if run_root else None
    task_manifest = load_json((run_root or Path()) / "manifests" / "task_timing_condition_manifest.json") if run_root else None

    return {
        "subject": subject,
        "session": session,
        "nwb_path": str(nwb_path),
        "nwb_size_bytes": nwb_path.stat().st_size,
        "nwb_sha256": (run_manifest or {}).get("nwb_sha256", ""),
        "run_root": str(run_root) if run_root else "",
        "notebook00_status": nb_status["00"],
        "notebook01_status": nb_status["01"],
        "notebook02_status": nb_status["02"],
        "time_base": (task_manifest or {}).get("time_base", ""),
        "area_mapping_status": (task_manifest or {}).get("area_mapping_status", ""),
        "condition_parser_status": (task_manifest or {}).get("condition_parser_status", ""),
        "condition_count": count_csv_rows((run_root or Path()) / "tables" / "condition_table.csv") if run_root else 0,
        "timing_epoch_count": count_csv_rows((run_root or Path()) / "tables" / "timing_table.csv") if run_root else 0,
        "warnings_count": count_warnings(run_root) if run_root else 0,
        "blocker": blocker or "",
        "runtime_total_seconds": round(total_runtime, 3),
        "source": "batch_nbconvert",
    }


def write_batch_outputs(rows: list[dict]) -> None:
    out_dir = REPO / "outputs" / "runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "repo_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
        "repo_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=REPO, text=True).strip(),
        "nwb_directory": str(NWB_DIR),
        "session_count": len(rows),
        "pynwb_loadable_claim": "13/13 by prior read-only open check; 1/13 notebook-audited before batch; batch targets remaining 12",
        "hash_cache": "OMISSION_NWB_SHA256 + OMISSION_RUN_ROOT set after Notebook 00 for 01/02",
        "sessions": rows,
    }
    (out_dir / "batch_phase00_02_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fieldnames = [
        "subject", "session", "nwb_path", "nwb_size_bytes", "nwb_sha256", "run_root",
        "notebook00_status", "notebook01_status", "notebook02_status",
        "time_base", "area_mapping_status", "condition_parser_status",
        "condition_count", "timing_epoch_count", "warnings_count", "blocker", "runtime_total_seconds",
    ]
    with (out_dir / "batch_phase00_02_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# Phase 00-02 Multi-Session Batch Report",
        "",
        f"- repo SHA: `{summary['repo_sha']}`",
        f"- sessions accounted: **{len(rows)}/13**",
        f"- PyNWB-loadable: **13/13** (read-only inventory; not the same as notebook-audited)",
        f"- notebook-audited before batch: **1/13** (`sub-C31o_ses-230630_rec.nwb`)",
        "",
        "## Session status",
        "",
        "| subject | session | nb00 | nb01 | nb02 | conditions | blocker |",
        "|---|---:|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['subject']} | {row['session']} | {row['notebook00_status']} | "
            f"{row['notebook01_status']} | {row['notebook02_status']} | "
            f"{row['condition_count']} | {row['blocker'] or '—'} |"
        )
    (out_dir / "batch_phase00_02_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    all_nwb = sorted(NWB_DIR.glob("*.nwb"))
    if len(all_nwb) != 13:
        print(f"Expected 13 NWB files, found {len(all_nwb)}", file=sys.stderr)

    rows: list[dict] = []
    rows.append(summarize_existing_baseline())

    for nwb_path in all_nwb:
        if nwb_path.resolve() == BASELINE.resolve():
            continue
        print(f"[batch] auditing {nwb_path.name} ...", flush=True)
        rows.append(audit_session(nwb_path))

    rows.sort(key=lambda r: (r["subject"], r["session"]))
    write_batch_outputs(rows)
    print(json.dumps({"sessions": len(rows), "pass_all": sum(1 for r in rows if r["notebook02_status"] == "PASS")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
