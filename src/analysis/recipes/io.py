"""IO utilities for analysis recipes.

Deterministic output saving and manifest management.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from src.analysis.recipes.specs import (
    EventSpec,
    WindowSpec,
    SignalSpec,
    AnalysisSpec,
    OutputSpec,
    RecipeResult,
)


def make_recipe_output_root(
    base_root: Path | str,
    repo_sha: str,
    nwb_sha8: str,
    recipe_id: str,
) -> Path:
    """Create deterministic recipe output directory.
    
    Path pattern:
        outputs/analysis_recipes/<repo_sha>_<nwb_sha8>/<recipe_id>/
    
    Parameters
    ----------
    base_root : Base outputs directory (e.g., Path("outputs/analysis_recipes"))
    repo_sha : Full git SHA of repository
    nwb_sha8 : First 8 characters of NWB file SHA256
    recipe_id : Unique recipe identifier
    
    Returns
    -------
    Path to recipe output directory
    
    Subdirectories created:
        arrays/     - .npz array files
        tables/     - .csv table files
        figures/    - .html preview figures
        notebooks/  - .ipynb executable notebooks
        manifests/  - .json provenance manifests
        reports/    - .md or .txt reports
        warnings/   - .json warning logs
    """
    root = Path(base_root)
    run_dir = root / f"{repo_sha}_{nwb_sha8}" / recipe_id
    
    # Create subdirectories
    for subdir in ["arrays", "tables", "figures", "notebooks", "manifests", "reports", "warnings"]:
        (run_dir / subdir).mkdir(parents=True, exist_ok=True)
    
    return run_dir


def save_array_npz(path: Path | str, **arrays: np.ndarray) -> None:
    """Save numpy arrays to compressed NPZ.
    
    Parameters
    ----------
    path : Destination path (.npz extension)
    **arrays : Named arrays to save
    
    Example
    -------
    >>> save_array_npz("arrays/spikes.npz", AAAB=spk_aaab, AXAB=spk_axab)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **arrays)


def save_table_csv(df: pd.DataFrame, path: Path | str) -> None:
    """Save DataFrame to CSV.
    
    Parameters
    ----------
    df : DataFrame to save
    path : Destination path (.csv extension)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_manifest_json(
    path: Path | str,
    payload: dict[str, Any],
    indent: int = 2,
) -> None:
    """Save JSON manifest.
    
    Parameters
    ----------
    path : Destination path (.json extension)
    payload : Dictionary to serialize
    indent : JSON indentation (default 2)
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle numpy arrays and other non-serializable types
    def make_serializable(obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [make_serializable(v) for v in obj]
        elif isinstance(obj, tuple):
            return [make_serializable(v) for v in obj]
        else:
            return obj
    
    serializable = make_serializable(payload)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=indent, default=str)


def write_recipe_manifest(
    result: RecipeResult,
    specs: dict[str, Any],
    provenance: dict[str, str],
    output_path: Path | str | None = None,
) -> Path:
    """Write comprehensive recipe manifest.
    
    Every recipe must save a manifest with full provenance.
    
    Manifest contents:
    {
        "recipe_id": str,
        "status": str,
        "created_at_utc": str,
        "provenance": {
            "repo_sha": str,
            "git_status_short": str,
            "nwb_path": str,
            "nwb_sha256": str,
            "source_functions": [str]
        },
        "specs": {
            "event_spec": {...},
            "window_spec": {...},
            "signal_spec": {...},
            "analysis_spec": {...},
            "output_spec": {...}
        },
        "outputs": {
            "arrays": {...},
            "tables": {...},
            "figures": {...},
            "notebooks": {...}
        },
        "input_shapes": {...},
        "output_shapes": {...},
        "time_base": str,
        "baseline_ms": [...],
        "conditions": [...],
        "areas": [...],
        "bands": {...},
        "layers": [...],
        "warnings": [...],
        "claim_status": "truth_safe_unverified",
        "computational_scaffold": true
    }
    
    Parameters
    ----------
    result : RecipeResult with output paths
    specs : Dict with event_spec, window_spec, signal_spec, analysis_spec, output_spec
    provenance : Dict with repo_sha, git_status_short, nwb_path, nwb_sha256, source_functions
    output_path : Optional override path (default: result.output_root/manifests/manifest.json)
    
    Returns
    -------
    Path to saved manifest
    """
    if output_path is None:
        output_path = Path(result.output_root) / "manifests" / "manifest.json"
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Extract specs
    event_spec = specs.get("event_spec", {})
    window_spec = specs.get("window_spec", {})
    signal_spec = specs.get("signal_spec", {})
    analysis_spec = specs.get("analysis_spec", {})
    output_spec = specs.get("output_spec", {})
    
    # Build manifest
    manifest: dict[str, Any] = {
        "recipe_id": result.recipe_id,
        "status": result.status,
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "provenance": {
            "repo_sha": provenance.get("repo_sha", ""),
            "git_status_short": provenance.get("git_status_short", ""),
            "nwb_path": provenance.get("nwb_path", ""),
            "nwb_sha256": provenance.get("nwb_sha256", ""),
            "source_functions": provenance.get("source_functions", []),
        },
        "specs": {
            "event_spec": event_spec.to_dict() if hasattr(event_spec, "to_dict") else event_spec,
            "window_spec": window_spec.to_dict() if hasattr(window_spec, "to_dict") else window_spec,
            "signal_spec": signal_spec.to_dict() if hasattr(signal_spec, "to_dict") else signal_spec,
            "analysis_spec": analysis_spec.to_dict() if hasattr(analysis_spec, "to_dict") else analysis_spec,
            "output_spec": output_spec.to_dict() if hasattr(output_spec, "to_dict") else output_spec,
        },
        "outputs": {
            "arrays": result.arrays,
            "tables": result.tables,
            "figures": result.figures,
            "notebooks": result.notebooks,
        },
        "input_shapes": result.metadata.get("input_shapes", {}),
        "output_shapes": result.metadata.get("output_shapes", {}),
        "time_base": event_spec.time_base if hasattr(event_spec, "time_base") else "unknown",
        "baseline_ms": list(window_spec.baseline_ms) if hasattr(window_spec, "baseline_ms") and window_spec.baseline_ms else None,
        "conditions": list(event_spec.conditions) if hasattr(event_spec, "conditions") else [],
        "areas": list(signal_spec.areas) if hasattr(signal_spec, "areas") else [],
        "bands": dict(analysis_spec.bands) if hasattr(analysis_spec, "bands") else {},
        "layers": ["superficial_putative", "deep_putative", "unresolved"],
        "warnings": result.warnings,
        "claim_status": "truth_safe_unverified",
        "computational_scaffold": True,
    }
    
    save_manifest_json(output_path, manifest)
    
    return output_path
