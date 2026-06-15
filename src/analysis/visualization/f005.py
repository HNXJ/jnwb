"""f005 single-unit PSTH category figure from saved jnwb artifacts only."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from scripts.classify_units_s_s_o import (
    BLOCKED_ANCHOR_CODE100,
    BLOCKED_ANCHOR_NOT_CODE101,
    validate_anchor_provenance,
)

import jnwb

AFAMILY_CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX"]

EVENT_SLOTS_MS: dict[str, tuple[int, int]] = {
    "p1": (0, 531),
    "p2": (1031, 1562),
    "p3": (2062, 2593),
    "p4": (3093, 3624),
}

CONDITION_COLORS: dict[str, str] = {
    "AAAB": "#4285F4",
    "AXAB": "#8F00FF",
    "AAXB": "#008080",
    "AAAX": "#FFA500",
}

CLASS_ROWS: list[tuple[str, str]] = [
    ("S+", "S+ stimulus-excited units"),
    ("S-", "S− stimulus-inhibited units"),
    ("O/X", "O/X omission-correlated units"),
]

BLOCKED_F005_ARTIFACT_MISSING = "BLOCKED_F005_ARTIFACT_MISSING"
BLOCKED_F005_CLASSIFICATION_MISSING = "BLOCKED_F005_CLASSIFICATION_MISSING"
BLOCKED_F005_MANIFEST_MISSING = "BLOCKED_F005_MANIFEST_MISSING"
BLOCKED_F005_AREA_METADATA_MISSING = "BLOCKED_F005_AREA_METADATA_MISSING"

EPOCH_BUILD_COMMAND = (
    "python scripts/build_f005_afamily_spk_epochs.py --nwb-root <NWB_ROOT>"
)
CLASSIFY_COMMAND = (
    "python scripts/classify_units_s_s_o.py "
    "--epochs-p1 outputs/f005/afamily_spk_p1_epochs.npz "
    "--unit-metadata outputs/f005/afamily_spk_p1_unit_metadata.csv"
)


class F005FigureBlockedError(RuntimeError):
    code: str = "BLOCKED_F005"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        self.details = details or {}
        if code is not None:
            self.code = code
        super().__init__(f"{self.code}: {message}")


def _file_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _unknown_area(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return s in ("", "nan", "None", "unknown", "Unknown")


@dataclass
class F005LoadedInputs:
    sessions: list[dict[str, Any]]
    artifact_manifest: dict[str, Any]
    classification: pd.DataFrame
    epochs_path: Path
    classification_path: Path
    bin_ms: float


def _find_manifest_for_artifact(epochs_path: Path) -> Path | None:
    """Find manifest file for an artifact, trying multiple naming patterns."""
    candidates = [
        epochs_path.with_name(epochs_path.stem + "_manifest.json"),
        epochs_path.with_name("afamily_spk_p1_epochs_manifest.json"),  # build_f005 default
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def validate_f005_input_paths(
    epochs_path: str | Path,
    classification_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
) -> tuple[Path, Path, Path | None]:
    epochs_path = Path(epochs_path)
    classification_path = Path(classification_path)
    
    if manifest_path:
        manifest_path = Path(manifest_path)
    else:
        manifest_path = _find_manifest_for_artifact(epochs_path)

    if not epochs_path.exists():
        raise F005FigureBlockedError(
            f"Epoch artifact not found: {epochs_path}",
            code=BLOCKED_F005_ARTIFACT_MISSING,
            details={"build_command": EPOCH_BUILD_COMMAND},
        )
    if not classification_path.exists():
        raise F005FigureBlockedError(
            f"Classification table not found: {classification_path}",
            code=BLOCKED_F005_CLASSIFICATION_MISSING,
            details={"classify_command": CLASSIFY_COMMAND},
        )
    if not manifest_path or not manifest_path.exists():
        raise F005FigureBlockedError(
            f"Artifact manifest not found for: {epochs_path}",
            code=BLOCKED_F005_MANIFEST_MISSING,
            details={"build_command": EPOCH_BUILD_COMMAND},
        )
    return epochs_path, classification_path, manifest_path


def _anchor_provenance_from_manifest(manifest: dict[str, Any], npz: Any) -> dict[str, Any]:
    anchor_code = manifest.get("p1_code", manifest.get("anchor_code"))
    if anchor_code is None and hasattr(npz, "files") and "anchor_code" in npz.files:
        anchor_code = int(npz["anchor_code"])
    return {
        "anchor_code": anchor_code,
        "anchor_type": manifest.get("anchor_type", "code101_p1_stimulus"),
        "time_base": manifest.get("time_base", "p1_relative"),
    }


def validate_f005_anchor_provenance(provenance: dict[str, Any]) -> None:
    result = validate_anchor_provenance(provenance)
    if not result["valid"]:
        blocker = result.get("blocker", BLOCKED_ANCHOR_NOT_CODE101)
        raise F005FigureBlockedError(
            result.get("error", "Invalid anchor provenance"),
            code=blocker,
            details={"provenance": provenance},
        )


def validate_f005_area_metadata(
    classification: pd.DataFrame,
    *,
    allow_unknown_area: bool = False,
) -> None:
    if allow_unknown_area or "area" not in classification.columns:
        return
    known = classification["area"].apply(lambda v: not _unknown_area(v))
    if not known.any():
        raise F005FigureBlockedError(
            "All unit area metadata are unknown; pass --allow-unknown-area to skip area bars",
            code=BLOCKED_F005_AREA_METADATA_MISSING,
        )


def load_f005_inputs(
    epochs_path: str | Path,
    classification_path: str | Path,
    *,
    manifest_path: str | Path | None = None,
    allow_unknown_area: bool = False,
) -> F005LoadedInputs:
    epochs_path, classification_path, manifest_path = validate_f005_input_paths(
        epochs_path, classification_path, manifest_path=manifest_path
    )
    assert manifest_path is not None

    artifact_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    classification = pd.read_csv(classification_path)

    with np.load(epochs_path, allow_pickle=True) as npz:
        provenance = _anchor_provenance_from_manifest(artifact_manifest, npz)
        validate_f005_anchor_provenance(provenance)
    validate_f005_area_metadata(classification, allow_unknown_area=allow_unknown_area)

    loaded = jnwb.load_epoch_artifact(epochs_path, load_all_sessions=True)
    batches = loaded if isinstance(loaded, list) else [loaded]

    bin_ms = float(artifact_manifest.get("bin_ms") or 1.0)
    sessions: list[dict[str, Any]] = []
    for batch in batches:
        session_id = str(batch.manifest.get("session_id", "unknown"))
        trial_meta = batch.trial_metadata.copy()
        if "session_id" not in trial_meta.columns:
            trial_meta["session_id"] = session_id
        sessions.append(
            {
                "session_id": session_id,
                "data": np.asarray(batch.data, dtype=np.float32),
                "time_ms": np.asarray(batch.time_ms, dtype=np.float64),
                "trial_metadata": trial_meta,
                "signal_metadata": batch.signal_metadata,
            }
        )

    return F005LoadedInputs(
        sessions=sessions,
        artifact_manifest=artifact_manifest,
        classification=classification,
        epochs_path=epochs_path,
        classification_path=classification_path,
        bin_ms=bin_ms,
    )


def _baseline_window_mask(time_ms: np.ndarray) -> np.ndarray:
    return (time_ms >= -500) & (time_ms < 0)


def _hz_traces(data: np.ndarray, bin_ms: float) -> np.ndarray:
    return data / (bin_ms / 1000.0)


def compute_class_condition_psths(
    inputs: F005LoadedInputs,
    display_class: str,
) -> dict[str, dict[str, np.ndarray | int]]:
    """Mean ± SEM PSTH per A-family condition for one display class."""
    bin_ms = inputs.bin_ms
    curves: dict[str, dict[str, np.ndarray | int]] = {}
    time_ms_ref: np.ndarray | None = None

    for condition in AFAMILY_CONDITIONS:
        unit_traces: list[np.ndarray] = []
        for sess in inputs.sessions:
            session_id = sess["session_id"]
            cls_units = inputs.classification.loc[
                (inputs.classification["display_class"] == display_class)
                & (inputs.classification["session"].astype(str) == session_id),
                "unit_idx",
            ].to_numpy(dtype=int)
            if len(cls_units) == 0:
                continue

            trial_meta: pd.DataFrame = sess["trial_metadata"]
            trial_mask = trial_meta["condition"].astype(str).values == condition
            if not trial_mask.any():
                continue

            data = sess["data"][trial_mask][:, cls_units, :]
            time_ms = sess["time_ms"]
            if time_ms_ref is None:
                time_ms_ref = time_ms
            rates = _hz_traces(data, bin_ms)
            base_mask = _baseline_window_mask(time_ms)
            if base_mask.any():
                baseline = rates[:, :, base_mask].mean(axis=(0, 2), keepdims=True)
                rates = rates - baseline

            unit_traces.append(rates.mean(axis=0))

        if not unit_traces or time_ms_ref is None:
            curves[condition] = {
                "mean": np.array([]),
                "sem": np.array([]),
                "n_units": 0,
            }
            continue

        stacked = np.concatenate(unit_traces, axis=0)
        n_units = int(stacked.shape[0])
        mean = stacked.mean(axis=0)
        sem = stacked.std(axis=0, ddof=1) / np.sqrt(n_units) if n_units > 1 else np.zeros_like(mean)
        curves[condition] = {"mean": mean, "sem": sem, "n_units": n_units, "time_ms": time_ms_ref}

    return curves


def compute_area_counts_by_class(classification: pd.DataFrame) -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    if "area" not in classification.columns:
        return out
    for display_class, _ in CLASS_ROWS:
        subset = classification[classification["display_class"] == display_class]
        known = subset[~subset["area"].apply(_unknown_area)]
        if known.empty:
            out[display_class] = pd.Series(dtype=int)
        else:
            out[display_class] = known["area"].value_counts().sort_index()
    return out


def build_f005_category_figure(
    inputs: F005LoadedInputs,
    *,
    allow_unknown_area: bool = False,
    title: str = "f005 Single-Unit PSTH Categories (A-family, p1-aligned)",
) -> go.Figure:
    area_counts = compute_area_counts_by_class(inputs.classification)
    has_area_bars = (not allow_unknown_area) and any(len(v) > 0 for v in area_counts.values())

    cols = 2 if has_area_bars else 1
    col_widths = [0.72, 0.28] if has_area_bars else [1.0]
    fig = make_subplots(
        rows=3,
        cols=cols,
        shared_xaxes=True,
        column_widths=col_widths,
        vertical_spacing=0.06,
        horizontal_spacing=0.05,
        subplot_titles=[label for _, label in CLASS_ROWS],
    )

    x_max = max(
        (sess["time_ms"].max() for sess in inputs.sessions),
        default=4000.0,
    )

    for row_idx, (display_class, _) in enumerate(CLASS_ROWS, start=1):
        curves = compute_class_condition_psths(inputs, display_class)
        n_units_class = int(
            (inputs.classification["display_class"] == display_class).sum()
        )

        for condition in AFAMILY_CONDITIONS:
            curve = curves[condition]
            if curve.get("n_units", 0) == 0 or "time_ms" not in curve:
                continue
            time_ms = curve["time_ms"]
            mean = np.asarray(curve["mean"])
            sem = np.asarray(curve["sem"])
            color = CONDITION_COLORS[condition]
            fig.add_trace(
                go.Scatter(
                    x=time_ms,
                    y=mean + sem,
                    mode="lines",
                    line=dict(width=0),
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row_idx,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_ms,
                    y=mean - sem,
                    fill="tonexty",
                    mode="lines",
                    line=dict(width=0),
                    fillcolor=f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.15)",
                    showlegend=False,
                    hoverinfo="skip",
                ),
                row=row_idx,
                col=1,
            )
            fig.add_trace(
                go.Scatter(
                    x=time_ms,
                    y=mean,
                    mode="lines",
                    line=dict(color=color, width=2),
                    name=condition,
                    legendgroup=condition,
                    showlegend=(row_idx == 1),
                ),
                row=row_idx,
                col=1,
            )

        for slot, (x0, x1) in EVENT_SLOTS_MS.items():
            fig.add_vrect(
                x0=x0,
                x1=x1,
                fillcolor="lightgray",
                opacity=0.12,
                line_width=0,
                row=row_idx,
                col=1,
            )
        fig.add_vline(x=0, line_dash="dash", line_color="black", row=row_idx, col=1)
        fig.update_yaxes(title_text="Δ rate (Hz)", row=row_idx, col=1)
        fig.add_annotation(
            text=f"N={n_units_class}",
            xref="paper",
            yref="paper",
            x=0.01,
            y=1.0 - (row_idx - 1) / 3,
            showarrow=False,
            font=dict(size=10),
        )

        if has_area_bars:
            counts = area_counts.get(display_class, pd.Series(dtype=int))
            fig.add_trace(
                go.Bar(
                    x=counts.index.astype(str).tolist(),
                    y=counts.values.tolist(),
                    marker_color="#CFB87C",
                    showlegend=False,
                ),
                row=row_idx,
                col=2,
            )
            fig.update_yaxes(title_text="Units", row=row_idx, col=2)

    fig.update_xaxes(title_text="Time from p1 (ms)", range=[-1000, min(x_max, 4200)], row=3, col=1)
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=900,
        width=1100 if has_area_bars else 900,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=1),
    )
    return fig


def summarize_f005_counts(inputs: F005LoadedInputs) -> dict[str, Any]:
    cls = inputs.classification
    cond_counts = (
        pd.concat([s["trial_metadata"] for s in inputs.sessions], ignore_index=True)["condition"]
        .value_counts()
        .to_dict()
    )
    session_ids = sorted({s["session_id"] for s in inputs.sessions})
    area_known = 0
    if "area" in cls.columns:
        area_known = int((~cls["area"].apply(_unknown_area)).sum())

    return {
        "session_count": len(session_ids),
        "session_ids": session_ids,
        "total_units": int(len(cls)),
        "class_counts": cls["display_class"].value_counts().to_dict(),
        "area_coverage_units_with_known_area": area_known,
        "condition_trial_counts": cond_counts,
        "artifact_path": str(inputs.epochs_path),
        "artifact_hash_sha256": _file_hash(inputs.epochs_path),
        "classification_path": str(inputs.classification_path),
        "classification_hash_sha256": _file_hash(inputs.classification_path),
    }


def _write_static_image(fig: go.Figure, path: Path, fmt: str) -> bool:
    try:
        fig.write_image(str(path), format=fmt, scale=2)
        return True
    except Exception:
        return False


def save_f005_figure_outputs(
    fig: go.Figure,
    *,
    output_png: Path,
    output_svg: Path,
    output_html: Path,
) -> dict[str, Any]:
    output_png.parent.mkdir(parents=True, exist_ok=True)
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_html.parent.mkdir(parents=True, exist_ok=True)

    fig.write_html(str(output_html), include_plotlyjs="cdn")
    png_ok = _write_static_image(fig, output_png, "png")
    svg_ok = _write_static_image(fig, output_svg, "svg")

    return {
        "output_png": str(output_png),
        "output_svg": str(output_svg),
        "output_html": str(output_html),
        "png_written": png_ok,
        "svg_written": svg_ok,
        "png_hash_sha256": _file_hash(output_png) if png_ok else None,
        "svg_hash_sha256": _file_hash(output_svg) if svg_ok else None,
        "html_hash_sha256": _file_hash(output_html),
        "static_export_note": None
        if png_ok and svg_ok
        else "PNG/SVG require kaleido; HTML always written",
    }


def write_f005_manifest_and_qa(
    *,
    summary: dict[str, Any],
    figure_outputs: dict[str, Any],
    artifact_manifest: dict[str, Any],
    manifest_path: Path,
    qa_csv_path: Path,
) -> dict[str, Any]:
    full_manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact_schema_version": artifact_manifest.get("artifact_schema_version"),
        "signal_class": artifact_manifest.get("signal_class", "SPK"),
        "alignment_event": artifact_manifest.get("alignment_event", "p1"),
        "time_base": artifact_manifest.get("time_base", "p1_relative"),
        "anchor_code": artifact_manifest.get("p1_code", 101),
        "window_ms": artifact_manifest.get("window_ms"),
        "bin_ms": artifact_manifest.get("bin_ms"),
        "conditions": AFAMILY_CONDITIONS,
        "class_counts": summary["class_counts"],
        "condition_trial_counts": summary["condition_trial_counts"],
        "session_count": summary["session_count"],
        "session_ids": summary["session_ids"],
        "total_units": summary["total_units"],
        "area_coverage_units_with_known_area": summary["area_coverage_units_with_known_area"],
        "input_artifact_path": summary["artifact_path"],
        "input_artifact_hash_sha256": summary["artifact_hash_sha256"],
        "input_classification_path": summary["classification_path"],
        "input_classification_hash_sha256": summary["classification_hash_sha256"],
        **figure_outputs,
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(full_manifest, f, indent=2, default=str)

    qa_df = pd.DataFrame([{**summary, **figure_outputs}])
    qa_df.to_csv(qa_csv_path, index=False)
    return full_manifest


def run_f005_figure(
    epochs_path: str | Path,
    classification_path: str | Path,
    *,
    output_png: str | Path,
    output_svg: str | Path,
    output_html: str | Path,
    manifest_path: str | Path,
    qa_csv_path: str | Path | None = None,
    allow_unknown_area: bool = False,
) -> dict[str, Any]:
    inputs = load_f005_inputs(
        epochs_path,
        classification_path,
        allow_unknown_area=allow_unknown_area,
    )
    fig = build_f005_category_figure(inputs, allow_unknown_area=allow_unknown_area)
    summary = summarize_f005_counts(inputs)
    figure_outputs = save_f005_figure_outputs(
        fig,
        output_png=Path(output_png),
        output_svg=Path(output_svg),
        output_html=Path(output_html),
    )
    qa_csv_path = Path(qa_csv_path or Path(manifest_path).with_name(Path(manifest_path).stem + "_qa.csv"))
    return write_f005_manifest_and_qa(
        summary=summary,
        figure_outputs=figure_outputs,
        artifact_manifest=inputs.artifact_manifest,
        manifest_path=Path(manifest_path),
        qa_csv_path=qa_csv_path,
    )
