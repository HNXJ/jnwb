"""Epoch artifact save/load with manifest audit."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from .errors import (
    BLOCKED_ARTIFACT_FORMAT_UNSUPPORTED,
    BLOCKED_ARTIFACT_SESSION_MISSING,
    BLOCKED_EMPTY_EPOCHS,
    JnwbBlockedError,
)
from .schema import EpochBatch

ARTIFACT_SCHEMA_VERSION = "jnwb_epoch_artifact_v1"

_LEGACY_SINGLE_KEYS = ("spk_epochs", "lfp_epochs", "muae_epochs", "epochs")
_SIGNAL_PREFIXES = ("spk", "lfp", "muae")


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


def _signal_key_prefix(signal: str) -> str:
    return signal.lower()


def _metadata_kind(signal: str) -> Literal["unit", "channel"]:
    return "unit" if signal.upper() == "SPK" else "channel"


def _array_key(signal: str, session: str) -> str:
    return f"{_signal_key_prefix(signal)}_epochs__{_safe_key(session)}"


def _signal_from_array_key(key: str) -> str | None:
    for prefix in _SIGNAL_PREFIXES:
        if key.startswith(f"{prefix}_epochs__") or key == f"{prefix}_epochs":
            return prefix.upper() if prefix != "muae" else "MUAe"
    if key == "epochs":
        return "SPK"
    return None


def _session_from_array_key(key: str) -> str | None:
    if "__" in key:
        return key.split("__", 1)[1]
    return None


def _find_epoch_keys(
    npz_files: list[str],
    signal: str | None = None,
    session: str | None = None,
) -> list[str]:
    """Find epoch array keys in an NPZ, with legacy fallback."""
    keys: list[str] = []
    prefixes: list[str]
    if signal is not None:
        prefixes = [f"{_signal_key_prefix(signal)}_epochs__"]
    else:
        prefixes = [f"{p}_epochs__" for p in _SIGNAL_PREFIXES]

    for fname in npz_files:
        if not any(fname.startswith(p) for p in prefixes):
            continue
        if session is None:
            keys.append(fname)
            continue
        sess_key = _safe_key(session)
        if fname.endswith(f"__{sess_key}"):
            keys.append(fname)

    if keys:
        return sorted(keys)

    if session is not None:
        return []

    for legacy in _LEGACY_SINGLE_KEYS:
        if legacy in npz_files:
            if signal is None or _signal_from_array_key(legacy) == signal.upper():
                return [legacy]
    return []


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
        raise JnwbBlockedError("No epoch batches to save", code=BLOCKED_EMPTY_EPOCHS)
    batches = _merge_batches_by_session(batches)
    for batch in batches:
        if np.asarray(batch.data).size == 0:
            raise JnwbBlockedError("Refusing to save empty epoch artifact", code=BLOCKED_EMPTY_EPOCHS)
    return batches, dict(batches[-1].manifest)


def _signal_metadata_csv_name(stem: str, signal: str) -> str:
    kind = _metadata_kind(signal)
    return f"{stem}_{kind}_metadata.csv"


def _filter_metadata_by_session(df: pd.DataFrame, session: str) -> pd.DataFrame:
    if df.empty:
        return df
    if "artifact_session_key" in df.columns:
        return df[df["artifact_session_key"] == session].reset_index(drop=True)
    if "session_id" in df.columns:
        return df[df["session_id"] == session].reset_index(drop=True)
    return df


def _load_manifest_json(path: Path) -> dict[str, Any]:
    manifest_path = path.with_name(path.stem + "_manifest.json")
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _batch_from_npz_key(
    z: np.lib.npyio.NpzFile,
    key: str,
    path: Path,
    file_manifest: dict[str, Any],
) -> EpochBatch:
    data = z[key]
    time_ms = z["time_axis_ms"] if "time_axis_ms" in z else z.get("time_ms", np.array([]))

    if "trial_metadata_json" in z:
        trial_meta = pd.DataFrame(json.loads(str(z["trial_metadata_json"])))
    else:
        trial_meta = pd.DataFrame()

    if "signal_metadata_json" in z:
        signal_meta = pd.DataFrame(json.loads(str(z["signal_metadata_json"])))
    else:
        signal_meta = pd.DataFrame()

    session = _session_from_array_key(key)
    if session is not None:
        trial_meta = _filter_metadata_by_session(trial_meta, session)
        signal_meta = _filter_metadata_by_session(signal_meta, session)

    signal_class = _signal_from_array_key(key) or file_manifest.get("signal_class", "SPK")

    manifest: dict[str, Any] = {
        "artifact_path": str(path),
        "artifact_schema_version": file_manifest.get("artifact_schema_version", ARTIFACT_SCHEMA_VERSION),
        "signal_class": signal_class,
        "array_key": key,
        "shape": tuple(data.shape),
        "session_id": session,
        "anchor_code": int(z["anchor_code"]) if "anchor_code" in z else file_manifest.get("p1_code", 101),
        "time_base": str(z["time_base"]) if "time_base" in z else file_manifest.get("time_base", "p1_relative"),
        "multi_session": bool(z["multi_session"]) if "multi_session" in z else file_manifest.get("multi_session", False),
    }
    if "condition_labels" in z:
        manifest["conditions"] = list(np.unique(z["condition_labels"]))
    manifest.update({k: v for k, v in file_manifest.items() if k not in manifest})
    return EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest=manifest,
    )


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
    Array keys: ``{signal_lower}_epochs__{session}`` (e.g. spk_epochs__, lfp_epochs__).
    """
    if format != "npz":
        raise JnwbBlockedError(
            f"Unsupported artifact format: {format}",
            code=BLOCKED_ARTIFACT_FORMAT_UNSUPPORTED,
        )

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = Path(manifest) if manifest else out_path.with_name(out_path.stem + "_manifest.json")

    batches, base_manifest = _consume_batches(epoch_batch_or_iter)
    signal_class = str(base_manifest.get("spec", {}).get("signal", "SPK"))
    metadata_kind = _metadata_kind(signal_class)
    time_ms = np.asarray(batches[0].time_ms)

    save_dict: dict[str, Any] = {
        "time_axis_ms": time_ms,
        "anchor_code": np.array(base_manifest.get("p1_code", 101)),
        "anchor_type": np.array("code101_p1_stimulus"),
        "time_base": np.array("p1_relative"),
        "session_keys": np.array([b.manifest.get("session_id", f"session_{i}") for i, b in enumerate(batches)]),
        "signal_class": np.array(signal_class),
        "artifact_schema_version": np.array(ARTIFACT_SCHEMA_VERSION),
    }

    trial_frames = []
    signal_frames = []
    shapes: list[list[int]] = []

    for i, batch in enumerate(batches):
        skey = str(batch.manifest.get("session_id", f"session_{i}"))
        arr = np.asarray(batch.data)
        save_dict[_array_key(signal_class, skey)] = arr
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
    signal_csv = out_path.with_name(_signal_metadata_csv_name(out_path.stem, signal_class))

    trial_meta.to_csv(trial_csv, index=False)
    signal_meta.to_csv(signal_csv, index=False)

    sampling_rate_hz = base_manifest.get("sampling_rate_hz")
    if sampling_rate_hz is None and batches:
        sampling_rate_hz = batches[0].manifest.get("sampling_rate_hz")

    full_manifest: dict[str, Any] = {
        "artifact_schema_version": ARTIFACT_SCHEMA_VERSION,
        "repo_sha": _git_sha(),
        "command": command,
        "creation_time_utc": datetime.now(timezone.utc).isoformat(),
        "input_nwb_paths": input_nwb_paths or [],
        "signal_class": signal_class,
        "signal_metadata_kind": metadata_kind,
        "conditions": base_manifest.get("conditions", []),
        "condition_numbers": trial_meta["condition_number"].unique().tolist()
        if "condition_number" in trial_meta.columns
        else [],
        "alignment_event": base_manifest.get("anchor"),
        "time_base": "p1_relative",
        "window_ms": base_manifest.get("spec", {}).get("window_ms"),
        "bin_ms": base_manifest.get("bin_ms"),
        "sampling_rate_hz": sampling_rate_hz,
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
        "trial_metadata_csv_hash_sha256": _file_hash(trial_csv),
        "signal_metadata_csv_hash_sha256": _file_hash(signal_csv),
        "multi_session": len(batches) > 1,
    }
    full_manifest.update(base_manifest)

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(full_manifest, f, indent=2, default=str)

    return full_manifest


def load_epoch_artifact(
    path: str | Path,
    session: str | None = None,
    load_all_sessions: bool = False,
    signal: str | None = None,
) -> EpochBatch | list[EpochBatch]:
    """Load epoch artifact from NPZ.

    Parameters
    ----------
    path
        Path to ``.npz`` artifact.
    session
        Load one session block by ID. Raises if missing.
    load_all_sessions
        When True, return one ``EpochBatch`` per session array key.
    signal
        Optional signal filter (SPK, LFP, MUAe).
    """
    path = Path(path)
    file_manifest = _load_manifest_json(path)

    with np.load(path, allow_pickle=True) as z:
        if signal is None and file_manifest.get("signal_class"):
            signal = str(file_manifest["signal_class"])

        keys = _find_epoch_keys(list(z.files), signal=signal, session=session)

        if session is not None and not keys:
            raise JnwbBlockedError(
                f"Session {session!r} not found in artifact {path}",
                code=BLOCKED_ARTIFACT_SESSION_MISSING,
                details={"available_keys": [k for k in z.files if "epochs" in k]},
            )

        if not keys:
            raise JnwbBlockedError(
                f"No epoch arrays found in artifact {path}",
                code=BLOCKED_ARTIFACT_SESSION_MISSING,
                details={"files": list(z.files)},
            )

        if load_all_sessions:
            return [_batch_from_npz_key(z, key, path, file_manifest) for key in keys]

        key = keys[0]
        return _batch_from_npz_key(z, key, path, file_manifest)
