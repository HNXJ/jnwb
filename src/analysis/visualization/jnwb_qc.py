"""jnwb visual QC and NWB analysis control suite."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS = _REPO_ROOT / "scripts"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import jnwb
from scripts.classify_units_s_s_o import validate_anchor_provenance
from src.jnwb.task import omission_offset_ms

AFAMILY_CONDITIONS = ["AAAB", "AXAB", "AAXB", "AAAX"]
EXPECTED_OMISSION_OFFSETS_MS = {"AXAB": 1031, "AAXB": 2062, "AAAX": 3093}

BLOCKED_QC_NWB_ROOT_MISSING = "BLOCKED_QC_NWB_ROOT_MISSING"
BLOCKED_QC_EMPTY_EVENTS = "BLOCKED_QC_EMPTY_EVENTS"
BLOCKED_QC_EMPTY_SIGNAL = "BLOCKED_QC_EMPTY_SIGNAL"
BLOCKED_QC_SHAPE_CONTRACT = "BLOCKED_QC_SHAPE_CONTRACT"
BLOCKED_QC_ANCHOR_PROVENANCE = "BLOCKED_QC_ANCHOR_PROVENANCE"
BLOCKED_QC_F005_ARTIFACT_MISSING = "BLOCKED_QC_F005_ARTIFACT_MISSING"
BLOCKED_QC_F005_CLASSIFICATION_MISSING = "BLOCKED_QC_F005_CLASSIFICATION_MISSING"

F005_EPOCH_BUILD_CMD = "python scripts/build_f005_afamily_spk_epochs.py --nwb-root <NWB_ROOT>"
F005_CLASSIFY_CMD = (
    "python scripts/classify_units_s_s_o.py "
    "--epochs-p1 outputs/f005/afamily_spk_p1_epochs.npz "
    "--unit-metadata outputs/f005/afamily_spk_p1_unit_metadata.csv"
)
F005_FIGURE_CMD = "python figures/f005_unit_psth_categories.py"

CONDITION_COLORS = {
    "AAAB": "#4285F4",
    "AXAB": "#8F00FF",
    "AAXB": "#008080",
    "AAAX": "#FFA500",
}


class JnwbQCBlockedError(RuntimeError):
    code: str = "BLOCKED_QC"

    def __init__(self, message: str, *, code: str | None = None, details: dict | None = None):
        self.details = details or {}
        if code is not None:
            self.code = code
        super().__init__(f"{self.code}: {message}")


@dataclass
class QCConfig:
    nwb_root: Path | None
    out_dir: Path
    conditions: list[str] = field(default_factory=lambda: list(AFAMILY_CONDITIONS))
    window_ms: tuple[int, int] = (-100, 300)
    bin_ms: float = 1.0
    max_sessions: int = 1
    max_units: int = 20
    max_channels: int = 16
    command: str = ""
    data_label: str = "REAL_NWB"
    f005_epochs: Path | None = None
    f005_classification: Path | None = None


def _git_sha() -> str | None:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
        if r.returncode == 0:
            return r.stdout.strip()
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


def _unknown_area(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip()
    return s in ("", "nan", "None", "unknown", "Unknown")


def validate_nwb_root(path: Path | None) -> Path:
    if path is None or not path.exists():
        raise JnwbQCBlockedError(
            f"NWB root not found: {path}",
            code=BLOCKED_QC_NWB_ROOT_MISSING,
        )
    return path


def validate_epoch_shape(signal: str, shape: tuple[int, ...]) -> None:
    if len(shape) != 3 or shape[0] == 0 or shape[1] == 0 or shape[2] == 0:
        raise JnwbQCBlockedError(
            f"Invalid {signal} epoch shape {shape}",
            code=BLOCKED_QC_SHAPE_CONTRACT,
            details={"expected": "trial x unit x time" if signal == "SPK" else "trial x channel x time"},
        )


def validate_event_address(event_addr: Any) -> None:
    if event_addr.p1_code != 101:
        raise JnwbQCBlockedError(
            f"Event address p1_code={event_addr.p1_code}, expected 101",
            code=BLOCKED_QC_ANCHOR_PROVENANCE,
        )
    prov = validate_anchor_provenance(
        {"anchor_code": event_addr.p1_code, "time_base": "p1_relative", "anchor_type": "p1_stimulus"}
    )
    if not prov["valid"]:
        raise JnwbQCBlockedError(
            prov.get("error", "Invalid anchor provenance"),
            code=BLOCKED_QC_ANCHOR_PROVENANCE,
            details={"blocker": prov.get("blocker")},
        )
    total = sum(len(v) for v in event_addr.events_by_session.values())
    if total == 0:
        raise JnwbQCBlockedError("No events addressed", code=BLOCKED_QC_EMPTY_EVENTS)


def _base_manifest(cfg: QCConfig, panel: str, **extra: Any) -> dict[str, Any]:
    return {
        "panel": panel,
        "repo_sha": _git_sha(),
        "command": cfg.command,
        "creation_time_utc": datetime.now(timezone.utc).isoformat(),
        "data_label": cfg.data_label,
        "conditions": cfg.conditions,
        "alignment_event": "p1",
        "time_base": "p1_relative",
        "anchor_code": 101,
        "window_ms": list(cfg.window_ms),
        "warnings": extra.pop("warnings", []),
        **extra,
    }


def _write_static(fig: go.Figure, path: Path, fmt: str) -> bool:
    try:
        fig.write_image(str(path), format=fmt, scale=2)
        return True
    except Exception:
        return False


def save_qc_figure(
    fig: go.Figure,
    stem: str,
    out_dir: Path,
    manifest_fields: dict[str, Any],
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / f"{stem}.html"
    png = out_dir / f"{stem}.png"
    svg = out_dir / f"{stem}.svg"
    manifest_path = out_dir / f"{stem}_manifest.json"

    fig.write_html(str(html), include_plotlyjs="cdn")
    png_ok = _write_static(fig, png, "png")
    svg_ok = _write_static(fig, svg, "svg")

    manifest = _base_manifest(
        manifest_fields.pop("_cfg"),
        stem,
        output_html=str(html),
        output_png=str(png) if png_ok else None,
        output_svg=str(svg) if svg_ok else None,
        html_hash_sha256=_file_hash(html),
        png_hash_sha256=_file_hash(png) if png_ok else None,
        svg_hash_sha256=_file_hash(svg) if svg_ok else None,
        **manifest_fields,
    )
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, default=str)
    return manifest


def build_inventory_dashboard(
    files: list[Any],
    event_addr: Any,
    signal_addrs: dict[str, Any],
    cfg: QCConfig,
) -> dict[str, Any]:
    rows = []
    for rec in files:
        skey = jnwb.files.session_key_from_record(rec)
        n_events = len(event_addr.events_by_session.get(skey, []))
        row = {
            "session": skey,
            "path": rec.path,
            "has_spk": rec.has_spk,
            "has_lfp": rec.has_lfp,
            "has_muae": rec.has_muae,
            "n_events": n_events,
        }
        for sig in ("SPK", "LFP", "MUAe"):
            addr = signal_addrs.get(sig)
            if addr and skey in addr.ids_by_session:
                row[f"n_{sig.lower()}"] = len(addr.ids_by_session[skey])
                areas = [
                    a
                    for a in addr.area_by_id.get(skey, {}).values()
                    if not _unknown_area(a)
                ]
                row[f"area_known_{sig.lower()}"] = len(areas)
            else:
                row[f"n_{sig.lower()}"] = 0
                row[f"area_known_{sig.lower()}"] = 0
        rows.append(row)
    df = pd.DataFrame(rows)

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("Signal availability", "Event counts", "Units/channels", "Area coverage"),
        specs=[[{"type": "bar"}, {"type": "bar"}], [{"type": "bar"}, {"type": "bar"}]],
    )
    sessions = df["session"].astype(str).tolist()
    for i, sig in enumerate(["spk", "lfp", "muae"]):
        fig.add_trace(
            go.Bar(name=sig.upper(), x=sessions, y=df[f"n_{sig}"].tolist(), showlegend=True),
            row=1,
            col=1,
        )
    fig.add_trace(go.Bar(x=sessions, y=df["n_events"].tolist(), name="events"), row=1, col=2)
    fig.add_trace(
        go.Bar(x=sessions, y=df["n_spk"].tolist(), name="SPK ids"),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Bar(x=sessions, y=df["area_known_spk"].tolist(), name="SPK area known"),
        row=2,
        col=2,
    )
    fig.update_layout(title=f"NWB inventory dashboard [{cfg.data_label}]", height=700, barmode="group")
    warnings = []
    if df["area_known_spk"].sum() == 0:
        warnings.append("All SPK area metadata unknown")

    inv_csv = cfg.out_dir / "01_inventory_table.csv"
    df.to_csv(inv_csv, index=False)

    return save_qc_figure(
        fig,
        "01_inventory_dashboard",
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": "inventory",
            "session_ids": sessions,
            "inventory_csv": str(cfg.out_dir / "01_inventory_table.csv"),
            "shape": [len(df), len(df.columns)],
            "area_metadata_status": "partial" if df["area_known_spk"].sum() else "unknown",
            "warnings": warnings,
            "input_nwb_paths": [r.path for r in files],
        },
    )


def build_event_timing_qc(event_addr: Any, cfg: QCConfig) -> dict[str, Any]:
    rows = []
    for skey, events in event_addr.events_by_session.items():
        for cond in cfg.conditions:
            evs = [e for e in events if e.get("condition") == cond]
            offset = omission_offset_ms(cond)
            expected = EXPECTED_OMISSION_OFFSETS_MS.get(cond)
            offset_ok = offset == expected if expected is not None else offset is None
            rows.append(
                {
                    "session": skey,
                    "condition": cond,
                    "n_events": len(evs),
                    "omission_offset_ms": offset,
                    "expected_offset_ms": expected,
                    "offset_ok": offset_ok,
                    "anchor": event_addr.anchor,
                    "p1_code": event_addr.p1_code,
                }
            )
    df = pd.DataFrame(rows)
    df.to_csv(cfg.out_dir / "02_event_counts.csv", index=False)

    fig = make_subplots(rows=2, cols=1, subplot_titles=("Events by condition", "Event timeline (p1-relative)"))
    for cond in cfg.conditions:
        sub = df[df["condition"] == cond]
        fig.add_trace(
            go.Bar(x=sub["session"].astype(str), y=sub["n_events"], name=cond, marker_color=CONDITION_COLORS[cond]),
            row=1,
            col=1,
        )

    y = 0
    for skey, events in event_addr.events_by_session.items():
        for ev in events[:200]:
            cond = ev.get("condition", "?")
            onset_ms = float(ev.get("onset_s", 0)) * 1000.0
            fig.add_trace(
                go.Scatter(
                    x=[onset_ms],
                    y=[y],
                    mode="markers",
                    marker=dict(color=CONDITION_COLORS.get(cond, "#888"), size=6),
                    name=cond,
                    showlegend=False,
                ),
                row=2,
                col=1,
            )
            y += 1

    bad_offsets = df[~df["offset_ok"]]
    warnings = []
    if not bad_offsets.empty:
        warnings.append(f"Offset mismatches: {len(bad_offsets)} rows")

    return save_qc_figure(
        fig,
        "02_event_timing_qc",
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": "events",
            "session_ids": sorted(event_addr.events_by_session.keys()),
            "shape": [len(df), len(df.columns)],
            "offset_checks": df.groupby("condition")["offset_ok"].all().to_dict(),
            "warnings": warnings,
            "input_nwb_paths": [],
        },
    )


def _load_signal_epochs(
    files: list[Any],
    event_addr: Any,
    signal: Literal["SPK", "LFP", "MUAe"],
    cfg: QCConfig,
) -> jnwb.EpochBatch:
    sessions = event_addr.sessions[: cfg.max_sessions]
    ev = jnwb.EventAddress(
        task=event_addr.task,
        conditions=event_addr.conditions,
        condition_numbers=event_addr.condition_numbers,
        anchor=event_addr.anchor,
        sessions=sessions,
        events_by_session={s: event_addr.events_by_session[s] for s in sessions},
        time_unit=event_addr.time_unit,
        p1_code=event_addr.p1_code,
        correct_only=event_addr.correct_only,
        warnings=event_addr.warnings,
    )
    max_items = cfg.max_units if signal == "SPK" else cfg.max_channels
    sig = jnwb.address_signals(
        files,
        signal=signal,
        sessions=sessions,
        require_area=False,
        max_items=max_items,
    )
    if not sig.sessions:
        raise JnwbQCBlockedError(f"No {signal} signal addressed", code=BLOCKED_QC_EMPTY_SIGNAL)
    use_files = [f for f in files if jnwb.files.session_key_from_record(f) in sig.sessions]
    batch_or_iter = jnwb.load_epochs(
        use_files,
        sig,
        ev,
        window_ms=cfg.window_ms,
        chunk_size=10000,
        bin_ms=cfg.bin_ms if signal == "SPK" else None,
    )
    if isinstance(batch_or_iter, jnwb.EpochBatch):
        return batch_or_iter
    batches = list(batch_or_iter)
    if not batches:
        raise JnwbQCBlockedError(f"Empty {signal} epochs", code=BLOCKED_QC_EMPTY_SIGNAL)
    data = np.concatenate([np.asarray(b.data) for b in batches], axis=0)
    trial_meta = pd.concat([b.trial_metadata for b in batches], ignore_index=True)
    return jnwb.EpochBatch(
        data=data,
        time_ms=batches[0].time_ms,
        trial_metadata=trial_meta,
        signal_metadata=batches[0].signal_metadata,
        manifest=batches[0].manifest,
    )


def build_spk_visual_smoke(batch: jnwb.EpochBatch, cfg: QCConfig) -> dict[str, Any]:
    data = np.asarray(batch.data)
    shape = tuple(data.shape)
    validate_epoch_shape("SPK", shape)
    time_ms = np.asarray(batch.time_ms)
    trial_meta = batch.trial_metadata
    signal_meta = batch.signal_metadata

    n_units = min(shape[1], 8)
    n_trials = min(shape[0], 40)
    fig = make_subplots(rows=2, cols=1, subplot_titles=("SPK raster (subset)", "SPK PSTH by condition"))
    sub = data[:n_trials, :n_units, :]
    for u in range(n_units):
        for t in range(n_trials):
            spikes = time_ms[sub[t, u, :] > 0]
            if len(spikes):
                fig.add_trace(
                    go.Scatter(
                        x=spikes,
                        y=[t + u * 0.01] * len(spikes),
                        mode="markers",
                        marker=dict(size=2, color="black"),
                        showlegend=False,
                    ),
                    row=1,
                    col=1,
                )
    rates = sub / (cfg.bin_ms / 1000.0)
    for cond in cfg.conditions:
        mask = trial_meta["condition"].astype(str).values[:n_trials] == cond
        if not mask.any():
            continue
        mean = rates[mask].mean(axis=(0, 1))
        fig.add_trace(
            go.Scatter(x=time_ms, y=mean, mode="lines", name=cond, line=dict(color=CONDITION_COLORS[cond])),
            row=2,
            col=1,
        )

    area_known = 0
    if "area" in signal_meta.columns:
        area_known = int((~signal_meta["area"].apply(_unknown_area)).sum())
    warnings = []
    if area_known == 0:
        warnings.append("All SPK unit area metadata unknown")

    return save_qc_figure(
        fig,
        "03_spk_visual_smoke",
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": "SPK",
            "shape": list(shape),
            "shape_contract": "trial x unit x time",
            "session_ids": trial_meta["session_id"].unique().tolist() if "session_id" in trial_meta.columns else [],
            "unit_channel_inclusion": signal_meta.to_dict(orient="records"),
            "area_metadata_status": "known" if area_known else "unknown",
            "bin_ms": cfg.bin_ms,
            "warnings": warnings,
        },
    )


def build_analog_visual_smoke(
    batch: jnwb.EpochBatch,
    signal: Literal["LFP", "MUAe"],
    cfg: QCConfig,
) -> dict[str, Any]:
    data = np.asarray(batch.data)
    shape = tuple(data.shape)
    validate_epoch_shape(signal, shape)
    time_ms = np.asarray(batch.time_ms)
    trial_mean = data.mean(axis=0)
    n_ch = min(trial_mean.shape[0], cfg.max_channels)

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=(f"{signal} trial-averaged image", f"{signal} channel traces"),
    )
    fig.add_trace(
        go.Heatmap(z=trial_mean[:n_ch], x=time_ms, y=list(range(n_ch)), colorscale="RdBu_r"),
        row=1,
        col=1,
    )
    for ch in range(min(4, n_ch)):
        fig.add_trace(go.Scatter(x=time_ms, y=trial_mean[ch], mode="lines", name=f"ch{ch}"), row=2, col=1)

    signal_meta = batch.signal_metadata
    area_known = 0
    if "area" in signal_meta.columns:
        area_known = int((~signal_meta["area"].apply(_unknown_area)).sum())
    warnings = []
    if area_known == 0:
        warnings.append(f"All {signal} channel area metadata unknown")

    stem = "04_lfp_visual_smoke" if signal == "LFP" else "05_muae_visual_smoke"
    return save_qc_figure(
        fig,
        stem,
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": signal,
            "shape": list(shape),
            "shape_contract": "trial x channel x time",
            "sampling_rate_hz": batch.manifest.get("sampling_rate_hz"),
            "unit_channel_inclusion": signal_meta.to_dict(orient="records"),
            "area_metadata_status": "known" if area_known else "unknown",
            "warnings": warnings,
        },
    )


def build_artifact_readback_qc(
    batches: dict[str, jnwb.EpochBatch],
    cfg: QCConfig,
) -> dict[str, Any]:
    art_dir = cfg.out_dir / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for signal, batch in batches.items():
        path = art_dir / f"qc_{signal.lower()}_epochs.npz"
        manifest_path = art_dir / f"qc_{signal.lower()}_epochs_manifest.json"
        saved = jnwb.save_epoch_artifact(
            batch,
            out=path,
            manifest=manifest_path,
            command=cfg.command,
            input_nwb_paths=[],
        )
        loaded = jnwb.load_epoch_artifact(path)
        saved_shape = tuple(np.asarray(batch.data).shape)
        loaded_shape = tuple(np.asarray(loaded.data).shape)
        match = saved_shape == loaded_shape
        rows.append(
            {
                "signal": signal,
                "save_path": str(path),
                "saved_shape": saved_shape,
                "loaded_shape": loaded_shape,
                "match": match,
                "artifact_hash": saved.get("artifact_hash_sha256"),
                "schema": saved.get("artifact_schema_version"),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(cfg.out_dir / "06_artifact_readback.csv", index=False)
    if not df["match"].all():
        raise JnwbQCBlockedError("Artifact readback shape mismatch", code=BLOCKED_QC_SHAPE_CONTRACT)

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(values=list(df.columns)),
                cells=dict(values=[df[c].astype(str).tolist() for c in df.columns]),
            )
        ]
    )
    fig.update_layout(title=f"Artifact readback QC [{cfg.data_label}]")
    return save_qc_figure(
        fig,
        "06_artifact_readback_qc",
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": "artifact",
            "readback_rows": rows,
            "shape": [len(df), len(df.columns)],
            "warnings": [],
        },
    )


def build_f005_readiness_qc(cfg: QCConfig) -> dict[str, Any]:
    epochs = cfg.f005_epochs or (_REPO_ROOT / "outputs/f005/afamily_spk_p1_epochs.npz")
    classification = cfg.f005_classification or (
        _REPO_ROOT / "outputs/f005/classification/unit_classification.csv"
    )
    rows = []
    blockers = []
    if not epochs.exists():
        blockers.append(
            {"code": BLOCKED_QC_F005_ARTIFACT_MISSING, "build_command": F005_EPOCH_BUILD_CMD}
        )
    if not classification.exists():
        blockers.append(
            {"code": BLOCKED_QC_F005_CLASSIFICATION_MISSING, "build_command": F005_CLASSIFY_CMD}
        )
    rows.append({"input": "epochs", "path": str(epochs), "exists": epochs.exists()})
    rows.append({"input": "classification", "path": str(classification), "exists": classification.exists()})

    fig_html = None
    if epochs.exists() and classification.exists():
        from src.analysis.visualization.f005 import run_f005_figure

        fig_dir = cfg.out_dir / "f005"
        run_f005_figure(
            epochs,
            classification,
            output_png=fig_dir / "f005_unit_psth_categories.png",
            output_svg=fig_dir / "f005_unit_psth_categories.svg",
            output_html=fig_dir / "f005_unit_psth_categories.html",
            manifest_path=fig_dir / "f005_unit_psth_categories_manifest.json",
            qa_csv_path=fig_dir / "f005_unit_psth_categories_qa.csv",
            allow_unknown_area=True,
        )
        fig_html = str(fig_dir / "f005_unit_psth_categories.html")
        status = "SUCCESS"
    else:
        status = "BLOCKED"

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(values=["input", "path", "exists"]),
                cells=dict(values=[[r["input"] for r in rows], [r["path"] for r in rows], [r["exists"] for r in rows]]),
            )
        ]
    )
    fig.update_layout(title=f"f005 readiness QC — {status}")
    manifest = save_qc_figure(
        fig,
        "07_f005_readiness_qc",
        cfg.out_dir,
        {
            "_cfg": cfg,
            "signal_class": "f005",
            "f005_status": status,
            "blockers": blockers,
            "f005_figure_html": fig_html,
            "warnings": [] if status == "SUCCESS" else ["f005 inputs missing"],
            "input_artifact_paths": [str(epochs), str(classification)],
        },
    )
    return manifest


def run_visual_qc(cfg: QCConfig) -> dict[str, Any]:
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    panels: dict[str, Any] = {}

    if cfg.nwb_root is None or not cfg.nwb_root.exists():
        raise JnwbQCBlockedError("NWB root missing", code=BLOCKED_QC_NWB_ROOT_MISSING)

    files = jnwb.list_nwb_files(cfg.nwb_root)
    if cfg.max_sessions:
        files = files[: cfg.max_sessions]

    event_addr = jnwb.address_events(files, conditions=cfg.conditions, anchor="p1", correct=True)
    validate_event_address(event_addr)

    signal_addrs: dict[str, Any] = {}
    for signal in ("SPK", "LFP", "MUAe"):
        try:
            signal_addrs[signal] = jnwb.address_signals(
                files,
                signal=signal,
                sessions=event_addr.sessions[: cfg.max_sessions],
                require_area=False,
                max_items=cfg.max_units if signal == "SPK" else cfg.max_channels,
            )
        except Exception as exc:
            signal_addrs[signal] = None
            panels[f"signal_{signal}_error"] = str(exc)

    panels["inventory"] = build_inventory_dashboard(files, event_addr, signal_addrs, cfg)
    panels["events"] = build_event_timing_qc(event_addr, cfg)

    artifact_batches: dict[str, jnwb.EpochBatch] = {}
    if signal_addrs.get("SPK"):
        spk_batch = _load_signal_epochs(files, event_addr, "SPK", cfg)
        panels["spk"] = build_spk_visual_smoke(spk_batch, cfg)
        artifact_batches["SPK"] = spk_batch

    for signal in ("LFP", "MUAe"):
        if signal_addrs.get(signal):
            try:
                batch = _load_signal_epochs(files, event_addr, signal, cfg)
                panels[signal.lower()] = build_analog_visual_smoke(batch, signal, cfg)
                artifact_batches[signal] = batch
            except JnwbQCBlockedError:
                raise
            except Exception as exc:
                panels[f"{signal.lower()}_skip"] = str(exc)

    if artifact_batches:
        panels["artifacts"] = build_artifact_readback_qc(artifact_batches, cfg)

    panels["f005"] = build_f005_readiness_qc(cfg)

    bundle = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "repo_sha": _git_sha(),
        "command": cfg.command,
        "data_label": cfg.data_label,
        "nwb_root": str(cfg.nwb_root),
        "out_dir": str(cfg.out_dir),
        "panels": panels,
    }
    bundle_path = cfg.out_dir / "bundle_manifest.json"
    with open(bundle_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, default=str)
    return bundle


def run_synthetic_fixture_qc(out_dir: Path, command: str = "synthetic_fixture") -> dict[str, Any]:
    """Run labeled synthetic QC for CI when real NWB is unavailable."""
    import jnwb as _jnwb

    session = "sub_SYN_ses_fixture"
    n_trials, n_units, n_time = 8, 4, 50
    data = np.random.poisson(1, (n_trials, n_units, n_time)).astype(np.float32)
    time_ms = np.linspace(-50, 50, n_time, endpoint=False)
    trial_meta = pd.DataFrame(
        {
            "session_id": [session] * n_trials,
            "condition": [AFAMILY_CONDITIONS[i % 4] for i in range(n_trials)],
        }
    )
    signal_meta = pd.DataFrame({"session_id": [session] * n_units, "area": ["V1"] * n_units})
    batch = _jnwb.EpochBatch(
        data=data,
        time_ms=time_ms,
        trial_metadata=trial_meta,
        signal_metadata=signal_meta,
        manifest={"session_id": session, "spec": {"signal": "SPK"}, "p1_code": 101},
    )
    cfg = QCConfig(nwb_root=None, out_dir=out_dir, command=command, data_label="SYNTHETIC_FIXTURE")
    cfg.out_dir.mkdir(parents=True, exist_ok=True)
    panels = {
        "spk_synthetic": build_spk_visual_smoke(batch, cfg),
        "artifacts": build_artifact_readback_qc({"SPK": batch}, cfg),
        "f005": build_f005_readiness_qc(cfg),
    }
    bundle = {
        "data_label": "SYNTHETIC_FIXTURE",
        "panels": panels,
        "out_dir": str(out_dir),
    }
    with open(out_dir / "bundle_manifest.json", "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, default=str)
    return bundle
