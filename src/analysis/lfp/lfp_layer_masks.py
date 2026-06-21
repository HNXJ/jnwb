"""Putative laminar channel masks from spectrolaminar crossover (vFLIP2 motif)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from src.analysis.lfp.lfp_constants import FS_LFP
from src.analysis.lfp.lfp_laminar_mapping import compute_spectrolaminar_profiles, find_crossover

LFP_ARRAYS_DIR = Path("D:/workspace/data/arrays")
DEFAULT_MASK_CACHE = Path(
    "D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr/layer_masks.json"
)

PROBE_LETTER_TO_INDEX: dict[str, str] = {"A": "0", "B": "1", "C": "2"}
LAYER_NAMES: tuple[str, str] = ("superficial_putative", "deep_putative")
CLASSIFICATION_CONDITION = "RRRR"

SESSION_SHORT_RE = re.compile(r"ses-(\d+)")


@dataclass(frozen=True)
class ProbeLayerClassification:
    session_id: str
    probe_letter: str
    crossover_idx: float
    orientation: str
    n_channels: int
    n_superficial: int
    n_deep: int
    classification_condition: str
    method: str = "spectrolaminar_alpha_beta_gamma_crossover"


def session_short_id(session_full: str) -> str:
    """Extract numeric session id from ``sub-*_ses-230630`` style ids."""
    match = SESSION_SHORT_RE.search(session_full)
    if match is None:
        raise ValueError(f"Cannot parse session id from {session_full!r}")
    return match.group(1)


def _orientation_from_profiles(
    crossover_idx: float,
    ab_norm: np.ndarray,
    n_channels: int,
) -> str:
    """Infer superficial-to-deep orientation from alpha/beta gradient."""
    if np.isnan(crossover_idx):
        return "unresolved"
    co_int = int(round(crossover_idx))
    if not (10 < co_int < n_channels - 10):
        return "invalid_range"
    ab_above = float(np.nanmean(ab_norm[:co_int]))
    ab_below = float(np.nanmean(ab_norm[co_int:]))
    return "flipped" if ab_above > ab_below else "normal"


def layer_masks_from_crossover(
    n_channels: int,
    crossover_idx: float,
    orientation: str,
    *,
    margin_channels: int = 1,
) -> dict[str, np.ndarray]:
    """Return boolean masks for putative superficial and deep channels."""
    sup = np.zeros(n_channels, dtype=bool)
    deep = np.zeros(n_channels, dtype=bool)
    if np.isnan(crossover_idx) or orientation in {"unresolved", "invalid_range", "error"}:
        return {LAYER_NAMES[0]: sup, LAYER_NAMES[1]: deep}

    ch = np.arange(n_channels)
    if orientation == "flipped":
        sup = ch > crossover_idx + margin_channels
        deep = ch < crossover_idx - margin_channels
    else:
        sup = ch < crossover_idx - margin_channels
        deep = ch > crossover_idx + margin_channels
    return {LAYER_NAMES[0]: sup, LAYER_NAMES[1]: deep}


def classify_probe_layers_from_lfp(
    lfp_probe: np.ndarray,
    *,
    session_id: str,
    probe_letter: str,
    fs: float = FS_LFP,
    classification_condition: str = CLASSIFICATION_CONDITION,
) -> ProbeLayerClassification:
    """Classify 128-channel probe LFP into putative superficial vs deep."""
    if lfp_probe.ndim != 3:
        raise ValueError(f"Expected (trials, channels, samples), got {lfp_probe.shape}")

    n_channels = int(lfp_probe.shape[1])
    profiles = compute_spectrolaminar_profiles(lfp_probe, fs=fs)
    crossover_idx, ab_norm, _ = find_crossover(profiles)
    orientation = _orientation_from_profiles(crossover_idx, ab_norm, n_channels)
    masks = layer_masks_from_crossover(n_channels, crossover_idx, orientation)

    return ProbeLayerClassification(
        session_id=session_id,
        probe_letter=probe_letter,
        crossover_idx=float(crossover_idx),
        orientation=orientation,
        n_channels=n_channels,
        n_superficial=int(np.sum(masks[LAYER_NAMES[0]])),
        n_deep=int(np.sum(masks[LAYER_NAMES[1]])),
        classification_condition=classification_condition,
    )


def lfp_path_for_probe(session_full: str, probe_letter: str, condition: str = CLASSIFICATION_CONDITION) -> Path:
    """Resolve raw LFP array path for a session-probe pair."""
    session_short = session_short_id(session_full)
    probe_index = PROBE_LETTER_TO_INDEX[probe_letter]
    primary = LFP_ARRAYS_DIR / f"ses{session_short}-probe{probe_index}-lfp-{condition}.npy"
    if primary.exists():
        return primary
    alt = LFP_ARRAYS_DIR / f"ses{session_short}-probe{probe_letter}-lfp-{condition}.npy"
    if alt.exists():
        return alt
    return primary


def get_probe_layer_masks(
    session_full: str,
    probe_letter: str,
    *,
    lfp_dir: Path = LFP_ARRAYS_DIR,
    cache: dict[str, Any] | None = None,
) -> tuple[dict[str, np.ndarray], ProbeLayerClassification]:
    """Load or compute superficial/deep masks for one session-probe."""
    cache_key = f"{session_full}|{probe_letter}"
    if cache is not None and cache_key in cache:
        row = cache[cache_key]
        n_channels = int(row["n_channels"])
        masks = {
            LAYER_NAMES[0]: np.asarray(row["superficial_mask"], dtype=bool),
            LAYER_NAMES[1]: np.asarray(row["deep_mask"], dtype=bool),
        }
        meta = ProbeLayerClassification(**{k: row[k] for k in ProbeLayerClassification.__dataclass_fields__})
        return masks, meta

    lfp_path = lfp_path_for_probe(session_full, probe_letter)
    if not lfp_path.exists():
        raise FileNotFoundError(f"No LFP array for layer classification: {lfp_path}")

    lfp_probe = np.load(lfp_path, mmap_mode="r")
    meta = classify_probe_layers_from_lfp(
        lfp_probe,
        session_id=session_full,
        probe_letter=probe_letter,
    )
    masks = layer_masks_from_crossover(meta.n_channels, meta.crossover_idx, meta.orientation)
    return masks, meta


def build_layer_mask_cache(
    session_probe_pairs: list[tuple[str, str]],
    *,
    out_path: Path = DEFAULT_MASK_CACHE,
) -> dict[str, Any]:
    """Compute and persist layer masks for all session-probe pairs."""
    cache: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []

    for session_full, probe_letter in sorted(set(session_probe_pairs)):
        masks, meta = get_probe_layer_masks(session_full, probe_letter, cache=None)
        key = f"{session_full}|{probe_letter}"
        row = asdict(meta)
        row["superficial_mask"] = masks[LAYER_NAMES[0]].tolist()
        row["deep_mask"] = masks[LAYER_NAMES[1]].tolist()
        cache[key] = row
        rows.append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "method": "spectrolaminar_alpha_beta_gamma_crossover",
        "classification_condition": CLASSIFICATION_CONDITION,
        "n_probes": len(rows),
        "probes": rows,
        "by_key": cache,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def load_layer_mask_cache(path: Path = DEFAULT_MASK_CACHE) -> dict[str, Any]:
    """Load cached layer-mask metadata."""
    if not path.exists():
        return {"by_key": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "by_key" not in payload:
        payload["by_key"] = {}
    return payload
