"""Epoch artifact save/load with manifest audit."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .schema import EpochBatch


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except OSError:
        pass
    return None


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _safe_key(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _merge_batches_by_session(batches: list[EpochBatch]) -> list[EpochBatch]:
    """Merge trial chunks that share a session_id."""
    grouped: dict[str, list[EpochBatch]] = {}
    for batch in batches:
        skey = str(batch.manifest.get("session_id", "unknown"))
        grouped.setdefault(skey, []).append(batch)

    merged: list[EpochBatch] = []
    for skey, parts in grouped.items():
        data = np.concatenate([np.asarray(p.data) for p in parts], axis=0)
        trial_meta = pd.concat([p.trial_metadata for p in parts], ignore_index=True)
        manifest = dict(parts[-1].manifest)
        manifest["session_id"] = skey
        manifest["shape"] = tuple(data.shape)
        manifest["n_chunks_merged"] = len(parts)
        merged.append(
            EpochBatch(
                data=data,
                time_ms=parts[0].time_ms,
                trial_metadata=trial_meta,
                signal_metadata=parts[0].signal_metadata,
                manifest=manifest,
            )
        )
    return merged


def _consume_batches(batch_or_iter: EpochBatch | Iterator[EpochBatch]) -> tuple[list[EpochBatch], dict]:
    if isinstance(batch_or_iter, EpochBatch):
        batches = [batch_or_iter]
    else:
        batches = list(batch_or_iter)
    if not batches:
        raise ValueError("No epoch batches to save")
    batches = _merge_batches_by_session(batches)
    return batches, dict(batches[-1].manifest)


def save_epoch_artifact(
    epoch_batch_or_iter: EpochBatch | Iterator[EpochBatch],
    out: str | Path,
    manifest: str | Path | None = None,
    format: str = "npz",
    command: str | None = None,
    input_nwb_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Save epoch batch(es) to NPZ plus JSON/CSV sidecars.

    Multi-session artifacts store one array per session key plus merged metadata.
    """
    if format != "npz":
        raise ValueError(f"Unsupported format: {format}")

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest) if manifest else out_path.with_name(out_path.stem + "_manifest.json")

    batches, base_manifest = _consume_batches(epoch_batch_or_iter)
    signal_class = base_manifest.get("spec", {}).get("signal", "SPK")
    time_ms = np.asarray(batches[0].time_ms)

    save_dict: dict[str, Any] = {
        "time_axis_ms": time_ms,
        "anchor_code": np.array(base_manifest.get("p1_code", 101)),
        "anchor_type": np.array("code101_p1_stimulus"),
        "time_base": np.array("p1_relative"),
        "session_keys": np.array([b.manifest.get("session_id", f"session_{i}") for i, b in enumerate(batches)]),
    }

    trial_frames = []
    signal_frames = []
    shapes: list[list[int]] = []

    for i, batch in enumerate(batches):
        skey = str(batch.manifest.get("session_id", f"session_{i}"))
        key = _safe_key(skey)
        arr = np.asarray(batch.data)
        save_dict[f"spk_epochs__{key}"] = arr
        shapes.append(list(arr.shape))
        trial_frames.append(batch.trial_metadata.assign(artifact_session_key=skey))
        signal_frames.append(batch.signal_metadata.assign(artifact_session_key=skey))

    trial_meta = pd.concat(trial_frames, ignore_index=True)
    signal_meta = pd.concat(signal_frames, ignore_index=True)
    condition_labels = trial_meta["condition"].to_numpy() if "condition" in trial_meta.columns else np.array([])

    save_dict["condition_labels"] = condition_labels
    save_dict["trial_metadata_json"] = np.array(trial_meta.to_json(orient="records"), dtype=np.str_)
    save_dict["signal_metadata_json"] = np.array(signal_meta.to_json(orient="records"), dtype=np.str_)
    save_dict["multi_session"] = np.array(len(batches) > 1)

    np.savez_compressed(out_path, **save_dict)

    trial_csv = out_path.with_name(out_path.stem + "_trial_metadata.csv")
    signal_csv = out_path.with_name(out_path.stem + "_unit_metadata.csv")

    trial_meta.to_csv(trial_csv, index=False)
    signal_meta.to_csv(signal_csv, index=False)

    full_manifest: dict[str, Any] = {
        "repo_sha": _git_sha(),
        "command": command,
        "creation_time_utc": datetime.now(timezone.utc).isoformat(),
        "input_nwb_paths": input_nwb_paths or [],
        "signal_class": signal_class,
        "conditions": base_manifest.get("conditions", []),
        "condition_numbers": trial_meta["condition_number"].unique().tolist() if "condition_number" in trial_meta.columns else [],
        "alignment_event": base_manifest.get("anchor"),
        "time_base": "p1_relative",
        "window_ms": base_manifest.get("spec", {}).get("window_ms"),
        "bin_ms": base_manifest.get("bin_ms"),
        "shapes_by_session": shapes,
        "shape": shapes[0] if shapes else [],
        "dtype": str(np.asarray(batches[0].data).dtype),
        "backend": base_manifest.get("spec", {}).get("backend", "numpy"),
        "session_ids": [str(b.manifest.get("session_id")) for b in batches],
        "n_sessions": len(batches),
        "n_trials_total": len(trial_meta),
        "unit_channel_inclusion": signal_meta.to_dict(orient="records"),
        "area_inclusion": sorted({a for a in signal_meta.get("area", pd.Series(dtype=object)).dropna().unique()}),
        "layer_inclusion": sorted({a for a in signal_meta.get("layer", pd.Series(dtype=object)).dropna().unique()}),
        "warnings": base_manifest.get("warnings", []),
        "artifact_path": str(out_path),
        "artifact_hash_sha256": _file_hash(out_path),
        "trial_metadata_csv": str(trial_csv),
        "signal_metadata_csv": str(signal_csv),
        "multi_session": len(batches) > 1,
    }
    full_manifest.update(base_manifest)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(full_manifest, f, indent=2, default=str)

    return full_manifest


def load_epoch_artifact(path: str | Path, session: str | None = None) -> EpochBatch:
    """Load epoch artifact from NPZ.

    If multi-session, pass session to load one block; otherwise loads the first/only block.
    """
    path = Path(path)
    with np.load(path, allow_pickle=True) as z:
        time_ms = z["time_axis_ms"] if "time_axis_ms" in z else z.get("time_ms", np.array([]))

        if "trial_metadata_json" in z:
            trial_meta = pd.DataFrame(json.loads(str(z["trial_metadata_json"])))
        else:
            trial_meta = pd.DataFrame()

        if "signal_metadata_json" in z:
            signal_meta = pd.DataFrame(json.loads(str(z["signal_metadata_json"])))
        else:
            signal_meta = pd.DataFrame()

        data = None
        if session is not None:
            key = f"spk_epochs__{_safe_key(session)}"
            if key in z:
                data = z[key]
        if data is None:
            for fname in z.files:
                if fname.startswith("spk_epochs__"):
                    data = z[fname]
                    if session is None:
                        break
        if data is None and "spk_epochs" in z:
            data = z["spk_epochs"]
        if data is None and "epochs" in z:
            data = z["epochs"]
        if data is None:
            raise KeyError("No spk_epochs array in artifact")

        if session is not None and "artifact_session_key" in trial_meta.columns:
            trial_meta = trial_meta[trial_meta["artifact_session_key"] == session].reset_index(drop=True)
            signal_meta = signal_meta[signal_meta["artifact_session_key"] == session].reset_index(drop=True)

        manifest = {
            "artifact_path": str(path),
            "shape": tuple(data.shape),
            "anchor_code": int(z["anchor_code"]) if "anchor_code" in z else 101,
            "time_base": str(z["time_base"]) if "time_base" in z else "p1_relative",
            "multi_session": bool(z["multi_session"]) if "multi_session" in z else False,
        }
        if "condition_labels" in z:
            manifest["conditions"] = list(np.unique(z["condition_labels"]))

    return EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest=manifest,
    )
