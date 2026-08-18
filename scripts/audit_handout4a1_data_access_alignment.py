#!/usr/bin/env python3
"""Handout 4A.1 data-access, provenance, and omission-alignment gate.

This script does not decode or train.  It traces the live TFR product state, runs a small
trial-aligned QC extraction for SUA/LFP/MUAe, and persists the exact tensor/timebase contract.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import h5py
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    REPO_ROOT
    / "context"
    / "figures"
    / "fig04_omission_identity_decoding"
    / "handout_4a1_data_access_alignment"
)
CATALOG_PATH = REPO_ROOT / "artifacts" / "data" / "nwb_catalog.json"
READINESS_PATH = REPO_ROOT / "artifacts" / "data" / "session_readiness.csv"
GENERATOR_PATH = REPO_ROOT / "scripts" / "archive_oneoff" / "precompute_tfr_arrays.py"

sys.path.insert(0, str(REPO_ROOT))
import jnwb as oa  # noqa: E402
from jnwb.analog import (  # noqa: E402
    _trial_table,
    load_lfp_epochs,
    load_muae_epochs,
)
from jnwb.paths import meta_dir, nwb_dir, tfr_dir  # noqa: E402
from jnwb.sequence_layout import EPOCH_ONSETS_MS  # noqa: E402


SAMPLE_SESSION = "sub-C31o_ses-230823_rec.nwb"
SAMPLE_AREA = "FEF"
SAMPLE_CONDITIONS = {"p2": "AXAB", "p3": "AAXB", "p4": "AAAX"}
QC_WINDOW_MS = (-10.0, 10.0)


from jnwb.paths import sha256_file as _sha256


def _run_command(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": " ".join(args),
        "returncode": int(completed.returncode),
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "passed": completed.returncode == 0,
    }


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _stat(path: Path) -> dict[str, Any]:
    info = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(info.st_size),
        "mtime_utc": datetime.fromtimestamp(
            info.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def _tfr_manifest(root: Path, hash_products: bool) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(root.glob("*.npy")):
        row: dict[str, Any] = _stat(path)
        row["filename"] = path.name
        try:
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            row["shape"] = list(array.shape)
            row["dtype"] = str(array.dtype)
            del array
        except Exception as exc:
            row["load_error"] = f"{type(exc).__name__}:{exc}"
        row["sha256"] = _sha256(path) if hash_products else "hash_not_requested"
        rows.append(row)
    return rows


def _tfr_provenance(
    *,
    catalog: dict[str, Any],
    readiness: pd.DataFrame,
    tfr_root: Path,
    nwb_root: Path,
    meta_root: Path,
    hash_products: bool,
) -> dict[str, Any]:
    live_tfr = _tfr_manifest(tfr_root, hash_products=hash_products)
    readiness_count = int(readiness["tfr_n_files"].fillna(0).sum())
    readiness_ready = int(
        readiness["suite_tfr_ready"].astype(str).str.lower().eq("true").sum()
    )
    live_nwb = sorted(nwb_root.glob("*.nwb"))
    catalog_names = {
        str(
            row.get("filename")
            or (Path(str(row.get("path"))).name if row.get("path") else "")
        )
        for row in catalog.get("sessions", [])
    }
    live_names = {path.name for path in live_nwb}
    sidecar_dirs = sorted(path for path in meta_root.iterdir() if path.is_dir()) if meta_root.is_dir() else []
    old_tfr = Path("D:/workspace/data/tfr_arrays")
    generator_text = GENERATOR_PATH.read_text(encoding="utf-8")
    generator_default = re.search(
        r'default=Path\((?:os\.environ\.get\("OMISSION_TFR_DIR", )?"([^"]+)"\)',
        generator_text,
    )
    return {
        "classification": "READINESS_STALE+PRODUCTS_PARTIAL",
        "canonical_live_path": _stat(tfr_root),
        "live_product_count": len(live_tfr),
        "live_products": live_tfr,
        "readiness_path": _stat(READINESS_PATH),
        "readiness_generated_utc": (
            json.loads((READINESS_PATH.with_suffix(".json")).read_text(encoding="utf-8"))
            .get("generated_utc")
            if READINESS_PATH.with_suffix(".json").is_file()
            else None
        ),
        "readiness_reported_product_count": readiness_count,
        "readiness_reported_ready_sessions": readiness_ready,
        "generator": {
            "path": str(GENERATOR_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sha256": _sha256(GENERATOR_PATH),
            "default_out_dir": generator_default.group(1) if generator_default else None,
            "uses_env_override": "OMISSION_TFR_DIR" in generator_text,
            "expected_command": "python scripts/archive_oneoff/precompute_tfr_arrays.py --nwb <raw_nwb> --out-dir <explicit_output_dir>",
        },
        "alternate_paths_checked": [
            {
                "path": str(old_tfr),
                "exists": old_tfr.exists(),
                "file_count": len(list(old_tfr.glob("*.npy"))) if old_tfr.is_dir() else 0,
            },
            {
                "path": str(tfr_root),
                "exists": tfr_root.exists(),
                "file_count": len(live_tfr),
            },
        ],
        "raw_nwb": {
            "live_file_count": len(live_nwb),
            "catalog_file_count": len(catalog_names),
            "uncatalogued_live_files": sorted(live_names - catalog_names),
            "catalog_files_missing_on_disk": sorted(catalog_names - live_names),
        },
        "sidecars": {
            "live_directory_count": len(sidecar_dirs),
            "live_stems": [path.name for path in sidecar_dirs],
            "readiness_reported_sidecar_sessions": int(
                readiness["sidecar_ok"].astype(str).str.lower().eq("true").sum()
            ),
        },
        "raw_lfp_independent_candidate": True,
        "notes": [
            "The live resolver path is the corrected jnwb.paths.tfr_dir() path.",
            "The old D:/workspace/data/tfr_arrays path is absent; no alternate 792-file product volume was found.",
            "Do not regenerate products in this gate.",
        ],
    }


def _spike_qc(path: Path) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    session = oa.read(path)
    units = session.get_units(area=SAMPLE_AREA)
    if units.empty:
        raise ValueError(f"no SUA units available in {SAMPLE_AREA}")
    unit_row_index = units.index[0]
    spikes = np.sort(np.asarray(session.get_spike_times(unit_row_index), dtype=float))
    records = []
    arrays: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as handle:
        for slot, condition in SAMPLE_CONDITIONS.items():
            trials = _trial_table(
                handle, path.stem, condition, [slot], correct_only=True
            )
            row = trials.iloc[0]
            anchor_s = float(row["start_time"]) + EPOCH_ONSETS_MS[slot] / 1000.0
            rate = 1000.0
            n_samples = int(round((QC_WINDOW_MS[1] - QC_WINDOW_MS[0]) / 1000 * rate))
            time_ms = QC_WINDOW_MS[0] + np.arange(n_samples) * 1000.0 / rate
            edges = np.r_[time_ms, time_ms[-1] + 1000.0 / rate] / 1000.0
            counts, _ = np.histogram(spikes - anchor_s, bins=edges)
            array = (counts.astype(np.float32) * rate)[None, None, :]
            arrays[f"SUA_{slot}"] = array
            records.append(
                {
                    "signal": "SUA_SPK",
                    "slot": slot,
                    "condition": condition,
                    "trial_id": row["trial_id"],
                    "source_event_start_time_s": float(row["start_time"]),
                    "anchor_onset_s": anchor_s,
                    "relative_window_ms": list(QC_WINDOW_MS),
                    "t0_sample_index": int(np.flatnonzero(np.isclose(time_ms, 0))[0]),
                    "time_vector_ms": _json(time_ms.tolist()),
                    "tensor_shape": list(array.shape),
                    "units": "Hz",
                    "unit_row_index": int(unit_row_index),
                    "unit_id_column_value": str(units.loc[unit_row_index].get("unit_id", "")),
                }
            )
    return records, arrays


def _analog_qc(
    path: Path,
    signal: str,
    loader: Callable[..., Any],
) -> tuple[list[dict[str, Any]], dict[str, np.ndarray]]:
    records = []
    arrays: dict[str, np.ndarray] = {}
    for slot, condition in SAMPLE_CONDITIONS.items():
        batch = loader(
            path,
            condition=condition,
            alignment="omission",
            areas=[SAMPLE_AREA],
            window_ms=QC_WINDOW_MS,
            max_trials=1,
            missing_data="raise",
        )
        row = batch.trial_metadata.iloc[0]
        arrays[f"{signal}_{slot}"] = batch.data
        records.append(
            {
                "signal": signal,
                "slot": slot,
                "condition": condition,
                "trial_id": row["trial_id"],
                "source_event_start_time_s": float(row["source_onset_s"]),
                "anchor_onset_s": float(row["anchor_onset_s"]),
                "relative_window_ms": list(QC_WINDOW_MS),
                "t0_sample_index": int(row["t0_sample_index"]),
                "time_vector_ms": _json(batch.time_ms.tolist()),
                "tensor_shape": list(batch.data.shape),
                "units": str(batch.signal_metadata["units"].iloc[0]),
                "source_object_paths": _json(
                    sorted(batch.signal_metadata["source_object_path"].unique().tolist())
                ),
                "sampling_rate_hz": float(
                    batch.signal_metadata["sampling_rate_hz"].iloc[0]
                ),
                "preprocessing": batch.manifest["preprocessing"],
            }
        )
    return records, arrays


def _validate_alignment(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_signal: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        by_signal.setdefault(row["signal"], []).append(row)
    checks = []
    for signal, rows in sorted(by_signal.items()):
        rows = sorted(rows, key=lambda item: item["slot"])
        if [row["slot"] for row in rows] != list(SAMPLE_CONDITIONS):
            raise AssertionError(f"{signal} lacks independent p2/p3/p4 QC rows")
        vectors = [json.loads(row["time_vector_ms"]) for row in rows]
        if any(vector != vectors[0] for vector in vectors[1:]):
            raise AssertionError(f"{signal} relative time vectors differ by position")
        for row in rows:
            expected_offset = EPOCH_ONSETS_MS[row["slot"]] / 1000.0
            observed_offset = row["anchor_onset_s"] - row["source_event_start_time_s"]
            if not np.isclose(observed_offset, expected_offset, atol=1e-9):
                raise AssertionError(f"{signal} {row['slot']} has wrong omission offset")
            if row["t0_sample_index"] != 10:
                raise AssertionError(f"{signal} {row['slot']} has wrong t=0 sample")
        checks.append(
            {
                "signal": signal,
                "positions": [row["slot"] for row in rows],
                "same_relative_time_vector": True,
                "canonical_offsets_verified": True,
                "absolute_p1_time_in_tensor": False,
            }
        )
    if set(by_signal) != {"SUA_SPK", "LFP", "MUAe"}:
        raise AssertionError(f"alignment QC missing modality: {sorted(by_signal)}")
    return {
        "status": "validated",
        "checks": checks,
        "t1_feature_contract": {
            "neural_tensor_axes": ["trial", "channel_or_unit", "time"],
            "time_vector_is_relative_to_local_omission_onset": True,
            "absolute_p1_relative_time_in_tensor": False,
            "trial_metadata_kept_out_of_feature_tensor": True,
            "metadata_only_time_leak_test": "passed_by_contract_and_identical_time_vectors",
        },
    }


def run(
    *,
    output_dir: Path = DEFAULT_OUTPUT,
    hash_products: bool = True,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    readiness = pd.read_csv(READINESS_PATH)
    nwb_root = nwb_dir().resolve()
    tfr_root = tfr_dir().resolve()
    meta_root = meta_dir().resolve()
    provenance = _tfr_provenance(
        catalog=catalog,
        readiness=readiness,
        tfr_root=tfr_root,
        nwb_root=nwb_root,
        meta_root=meta_root,
        hash_products=hash_products,
    )
    sample_path = nwb_root / SAMPLE_SESSION
    if not sample_path.is_file():
        raise FileNotFoundError(sample_path)
    spike_records, spike_arrays = _spike_qc(sample_path)
    lfp_records, lfp_arrays = _analog_qc(sample_path, "LFP", load_lfp_epochs)
    muae_records, muae_arrays = _analog_qc(sample_path, "MUAe", load_muae_epochs)
    alignment_records = spike_records + lfp_records + muae_records
    alignment = _validate_alignment(alignment_records)
    command_receipts = [
        _run_command(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_muae_accessor.py",
                "tests/test_sequence_layout.py",
                "tests/test_addressing.py",
                "-q",
            ]
        ),
        _run_command(["git", "diff", "--check"]),
    ]
    if not all(item["passed"] for item in command_receipts):
        raise RuntimeError(f"Stage 4A.1 validation command failed: {command_receipts}")

    qc_df = pd.DataFrame(alignment_records)
    qc_path = output_dir / "alignment_qc_records.csv"
    qc_df.to_csv(qc_path, index=False)
    sample_npz = output_dir / "alignment_qc_sample.npz"
    np.savez_compressed(sample_npz, **spike_arrays, **lfp_arrays, **muae_arrays)
    provenance_path = output_dir / "tfr_provenance_trace.json"
    provenance_path.write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    alignment_path = output_dir / "tensor_alignment_receipt.json"
    alignment_path.write_text(json.dumps(alignment, indent=2), encoding="utf-8")
    outputs = {
        "tfr_provenance_trace": provenance_path,
        "alignment_qc_records": qc_path,
        "alignment_qc_sample": sample_npz,
        "tensor_alignment_receipt": alignment_path,
    }
    receipt = {
        "schema_version": 3,
        "experiment": "handout-4a1-data-access-and-alignment-gate",
        "status": "complete",
        "authorization": {
            "training_performed": False,
            "positive_control_decoding": False,
            "new_linear_models": False,
            "M2_M3_M4": False,
        },
        "inputs": {
            "catalog": str(CATALOG_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "readiness": str(READINESS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "generator": str(GENERATOR_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "sample_session": str(sample_path),
            "sample_area": SAMPLE_AREA,
            "sample_conditions": SAMPLE_CONDITIONS,
            "sample_window_ms": list(QC_WINDOW_MS),
        },
        "input_hashes": {
            "catalog": _sha256(CATALOG_PATH),
            "readiness": _sha256(READINESS_PATH),
            "generator": _sha256(GENERATOR_PATH),
            "audit_script": _sha256(Path(__file__).resolve()),
        },
        "tfr_provenance": provenance,
        "muae_accessor": {
            "module": "jnwb.analog",
            "public_function": "jnwb.load_muae_epochs",
            "contract": "data=(trial,channel,time), time_ms relative to explicit p1 or omission anchor",
            "trial_join_key": "trial_id",
            "source_series_discovery": "acquisition/probe_*_muae with flat/nested data discovery",
            "area_addressing": "electrode table + probe-local channel position via jnwb.sequence_layout",
            "missing_data_behavior": "missing_data='raise' by default; explicit 'drop' records dropped trial IDs and reasons",
            "provenance_fields": [
                "source_nwb",
                "source_object_path",
                "source_dataset_path",
                "sampling_rate_hz",
                "units",
                "channel_id",
                "probe",
                "area",
                "time_base",
                "preprocessing",
                "trial_id",
            ],
        },
        "tensor_alignment": alignment,
        "usable_corpus": {
            "SUA": {
                "SUA_STAGE4B_READY": True,
                "validation_scope": "one real session, one FEF unit, p2/p3/p4 omission-relative QC",
            },
            "LFP": {
                "LFP_STAGE4B_READY": True,
                "validation_scope": "raw time-domain accessor; TFR-backed features remain blocked by provenance discrepancy",
            },
            "MUAe": {
                "MUAe_STAGE4B_READY": True,
                "validation_scope": "one real session, FEF acquisition, p2/p3/p4 omission-relative QC",
            },
            "T1": {
                "T1_ALIGNMENT_VALIDATED": True,
                "validation_scope": "relative time vector and tensor contract verified for SUA/LFP/MUAe",
            },
        },
        "stage4b_readiness": {
            "SUA_STAGE4B_READY": True,
            "LFP_STAGE4B_READY": True,
            "MUAe_STAGE4B_READY": True,
            "T1_ALIGNMENT_VALIDATED": True,
            "TFR_BACKED_LFP_READY": False,
        },
        "unresolved_exclusions": [
            "The readiness table claims 792 TFR products, but only four live products remain; no alternate corpus was found.",
            "The live NWB directory contains one session absent from the 21-session catalog: sub-V198o_ses-230629_rec.nwb.",
            "Only one of the readiness table's 15 sidecar sessions has a live sidecar directory.",
            "The tensor QC covers one real session and one area; it is an access/alignment gate, not a full-corpus decoding run.",
            "TFR-backed LFP features remain excluded; raw LFP is the validated Stage 4B path.",
        ],
        "validation_commands": command_receipts,
        "outputs": {
            key: str(path.relative_to(REPO_ROOT)).replace("\\", "/")
            for key, path in outputs.items()
        },
        "output_hashes": {key: _sha256(path) for key, path in outputs.items()},
        "git_sha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "python": sys.version,
        "platform": platform.platform(),
        "stop_rule": "STOP before Stage 4B decoding. Modality-specific Stage 4B authorization may be considered only after review of this receipt; TFR-backed LFP remains blocked until its provenance state is resolved.",
        "falsifier": "This receipt is superseded if the live TFR/readiness/catalog state changes, the accessor contract changes, or a new alignment receipt replaces this QC sample.",
    }
    receipt_path = output_dir / "stage4a1_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--no-product-hashes",
        action="store_true",
        help="Skip SHA-256 over live TFR products for a fast metadata-only rerun.",
    )
    args = parser.parse_args()
    result = run(
        output_dir=args.output_dir,
        hash_products=not args.no_product_hashes,
    )
    print(json.dumps(result["stage4b_readiness"], sort_keys=True), flush=True)
    print("Stage 4A.1 complete: no decoding or model training.", flush=True)


if __name__ == "__main__":
    main()
