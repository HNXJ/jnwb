"""Area × layer × condition TFR band figures with spectrolaminar channel masks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import plotly.graph_objects as go
from scipy import stats

from src.analysis.lfp.lfp_constants import (
    ALL_CONDITIONS,
    AREA_ALIAS_MAP,
    BANDS,
    CANONICAL_AREAS,
    OMISSION_ANALYSIS_WINDOWS_MS,
    SEQUENCE_TIMING_MS,
    colors_for_bands,
)
from src.analysis.lfp.lfp_layer_masks import (
    LAYER_NAMES,
    build_layer_mask_cache,
    get_probe_layer_masks,
    load_layer_mask_cache,
)
from src.analysis.lfp.lfp_preproc import baseline_normalize
from src.analysis.visualization.plotting import OmissionPlotter
from src.analysis.visualization.v1_tfr_baseline_figures import (
    BASELINE_WINDOW_MS,
    FREQS_HZ,
    TIMES_MS,
    aggregate_trial_stats,
    collapse_band,
)

TFR_DIR = Path("D:/workspace/data/tfr_arrays")
DEFAULT_OUT_DIR = Path(
    "D:/workspace/omission/outputs/publication_visual_review/area_layer_tfr"
)

CONDITION_PATTERN = "|".join(re.escape(c) for c in ALL_CONDITIONS)
TFR_FILE_RE = re.compile(
    rf"^(?P<session>.+)-(?P<probe>[ABC])-(?P<area>[A-Za-z0-9]+)-(?P<condition>{CONDITION_PATTERN})\.npy$"
)

BAND_COLORS = colors_for_bands(BANDS)

EPOCH_WINDOWS_MS: dict[str, tuple[float, float]] = {
    "fixation": (-500.0, 0.0),
    "p1": (SEQUENCE_TIMING_MS["p1"]["start"], SEQUENCE_TIMING_MS["p1"]["end"]),
    "p2": (SEQUENCE_TIMING_MS["p2"]["start"], SEQUENCE_TIMING_MS["p2"]["end"]),
    "p3": (SEQUENCE_TIMING_MS["p3"]["start"], SEQUENCE_TIMING_MS["p3"]["end"]),
    "p4": (SEQUENCE_TIMING_MS["p4"]["start"], SEQUENCE_TIMING_MS["p4"]["end"]),
}


@dataclass(frozen=True)
class TfrSource:
    session_id: str
    probe: str
    area_label: str
    condition: str
    path: Path
    n_trials: int


def area_search_tokens(canonical_area: str) -> list[str]:
    """File area tokens that map to a canonical area label."""
    tokens = [canonical_area]
    for alias, target in AREA_ALIAS_MAP.items():
        if target == canonical_area:
            tokens.append(alias)
    return sorted(set(tokens))


def discover_tfr_sources(
    area: str,
    condition: str,
    *,
    tfr_dir: Path = TFR_DIR,
) -> list[TfrSource]:
    """Find TFR arrays for a canonical area and condition."""
    tokens = set(area_search_tokens(area))
    sources: list[TfrSource] = []
    for path in sorted(tfr_dir.glob(f"*-{condition}.npy")):
        match = TFR_FILE_RE.match(path.name)
        if match is None:
            continue
        file_area = match.group("area")
        if file_area not in tokens:
            continue
        n_trials = int(np.load(path, mmap_mode="r").shape[0])
        sources.append(
            TfrSource(
                session_id=match.group("session"),
                probe=match.group("probe"),
                area_label=file_area,
                condition=condition,
                path=path,
                n_trials=n_trials,
            )
        )
    return sources


def layer_mean_baseline_db(
    power: np.ndarray,
    channel_mask: np.ndarray | None = None,
    *,
    times_ms: np.ndarray = TIMES_MS,
    baseline_window_ms: tuple[float, float] = BASELINE_WINDOW_MS,
) -> np.ndarray:
    """Average selected channels per trial, then baseline-normalize to dB."""
    if power.ndim != 4:
        raise ValueError(f"Expected 4D power array, got shape {power.shape}")

    if channel_mask is None:
        layer_mean = np.mean(power, axis=1)
    else:
        if not np.any(channel_mask):
            raise ValueError("Channel mask is empty; cannot compute layer mean")
        layer_mean = np.mean(power[:, channel_mask, :, :], axis=1)

    return baseline_normalize(
        layer_mean, times_ms, baseline_window=baseline_window_ms
    ).astype(np.float32)


def _time_mask(window_ms: tuple[float, float], times_ms: np.ndarray = TIMES_MS) -> np.ndarray:
    return (times_ms >= window_ms[0]) & (times_ms < window_ms[1])


def epoch_band_means(
    trials_db: np.ndarray,
    *,
    times_ms: np.ndarray = TIMES_MS,
) -> dict[str, dict[str, float]]:
    """Per-epoch per-band trial means (scalar per trial)."""
    out: dict[str, dict[str, float]] = {}
    for epoch, window in EPOCH_WINDOWS_MS.items():
        t_mask = _time_mask(window, times_ms)
        out[epoch] = {}
        for band, limits in BANDS.items():
            f_mask = (FREQS_HZ >= limits[0]) & (FREQS_HZ <= limits[1])
            band_ts = np.mean(trials_db[:, f_mask][:, :, t_mask], axis=(1, 2))
            out[epoch][band] = float(np.mean(band_ts))
    return out


def compute_band_epoch_stats(trials_db: np.ndarray) -> list[dict[str, Any]]:
    """One-sample t-tests vs 0 dB for each band × epoch combination."""
    rows: list[dict[str, Any]] = []
    for epoch, window in EPOCH_WINDOWS_MS.items():
        t_mask = _time_mask(window)
        for band, limits in BANDS.items():
            f_mask = (FREQS_HZ >= limits[0]) & (FREQS_HZ <= limits[1])
            values = np.mean(trials_db[:, f_mask][:, :, t_mask], axis=(1, 2))
            mean = float(np.mean(values))
            sem = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0
            if len(values) > 1:
                t_res = stats.ttest_1samp(values, popmean=0.0)
                p_value = float(t_res.pvalue)
                t_stat = float(t_res.statistic)
            else:
                p_value = np.nan
                t_stat = np.nan
            rows.append(
                {
                    "epoch": epoch,
                    "window_ms": window,
                    "band": band,
                    "mean_db": mean,
                    "sem_db": sem,
                    "n_trials": int(len(values)),
                    "t_stat": t_stat,
                    "p_value": p_value,
                    "test": "one_sample_ttest_vs_0db",
                }
            )
    return rows


def _stats_annotation_text(
    *,
    area: str,
    layer: str,
    condition: str,
    n_sessions: int,
    n_trials: int,
    n_channels_mean: float,
    classification_rows: list[dict[str, Any]],
    band_epoch_stats: list[dict[str, Any]],
    omission_window: tuple[int, int] | None,
) -> str:
    lines = [
        f"<b>{area} | {layer} | {condition}</b>",
        f"N sessions={n_sessions} | n trials={n_trials} | mean layer channels={n_channels_mean:.1f}",
        "Layer tags: spectrolaminar α/β vs γ crossover (putative sup/deep; L4 excluded)",
        f"Baseline dB window: {BASELINE_WINDOW_MS[0]} to {BASELINE_WINDOW_MS[1]} ms (fixation)",
    ]
    if omission_window is not None:
        lines.append(f"Omission epoch: {omission_window[0]}–{omission_window[1]} ms")
    if classification_rows:
        co_txt = ", ".join(
            f"{r['session_id'].split('_')[-1]}-{r['probe_letter']}:"
            f"co={r['crossover_idx']:.1f}({r['orientation']})"
            for r in classification_rows[:6]
        )
        if len(classification_rows) > 6:
            co_txt += f", +{len(classification_rows) - 6} more"
        lines.append(f"Crossovers: {co_txt}")
    lines.append("<br><b>Band × epoch (mean±SEM dB; one-sample t vs 0)</b>")
    for row in band_epoch_stats:
        p_txt = "p=nan" if np.isnan(row["p_value"]) else f"p={row['p_value']:.3g}"
        lines.append(
            f"{row['epoch']} {row['band']}: {row['mean_db']:+.2f}±{row['sem_db']:.2f} dB | {p_txt}"
        )
    return "<br>".join(lines)


def build_area_layer_band_figure(
    mean_db: np.ndarray,
    sem_db: np.ndarray,
    *,
    area: str,
    layer: str,
    condition: str,
    stats_text: str,
    omission_window: tuple[int, int] | None = None,
) -> go.Figure:
    """Band-resolved relative-power trajectory for one area-layer-condition."""
    plotter = OmissionPlotter(
        title=f"{area} {layer.replace('_', ' ')} — {condition}",
        x_label="Time from P1",
        y_label="Relative power",
        subtitle=(
            "Putative laminar channels | fixation baseline (-500, 0) ms | "
            "spectrolaminar motif classification"
        ),
        x_unit="ms",
        y_unit="dB",
    )

    for band, limits in BANDS.items():
        band_mean = collapse_band(mean_db, limits)
        band_sem = collapse_band(sem_db, limits)
        color = BAND_COLORS.get(band, "#CFB87C")
        plotter.add_shaded_error_bar(
            TIMES_MS,
            band_mean,
            band_sem,
            name=band,
            color=color,
        )

    for name, info in SEQUENCE_TIMING_MS.items():
        plotter.fig.add_vrect(
            x0=info["start"],
            x1=info["end"],
            fillcolor=info["color"],
            opacity=0.06,
            line_width=0,
        )
    if omission_window is not None:
        plotter.fig.add_vrect(
            x0=omission_window[0],
            x1=omission_window[1],
            fillcolor="#DC2626",
            opacity=0.12,
            line_width=1,
            line_color="#DC2626",
        )
    plotter.add_xline(0, "P1", color="#CFB87C")
    plotter.fig.update_xaxes(range=[-1000, 4000])
    plotter.fig.add_annotation(
        xref="paper",
        yref="paper",
        x=0,
        y=-0.22,
        text=stats_text,
        showarrow=False,
        align="left",
        font=dict(family="JetBrains Mono", size=9, color="#333333"),
    )
    plotter.fig.update_layout(height=760, margin=dict(l=80, r=40, t=100, b=260))
    return plotter.fig


def build_area_layer_condition_figure(
    area: str,
    layer: str,
    condition: str,
    *,
    tfr_dir: Path = TFR_DIR,
    mask_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one area × layer × condition band figure."""
    if layer not in LAYER_NAMES:
        raise ValueError(f"Unknown layer {layer!r}; expected one of {LAYER_NAMES}")

    sources = discover_tfr_sources(area, condition, tfr_dir=tfr_dir)
    if not sources:
        return {
            "area": area,
            "layer": layer,
            "condition": condition,
            "status": "missing_data",
            "n_sessions": 0,
            "n_trials": 0,
        }

    if mask_cache is None:
        mask_cache = load_layer_mask_cache().get("by_key", {})

    trial_blocks: list[np.ndarray] = []
    session_rows: list[dict[str, Any]] = []
    classification_rows: list[dict[str, Any]] = []
    channel_counts: list[int] = []

    for source in sources:
        masks, meta = get_probe_layer_masks(
            source.session_id,
            source.probe,
            cache=mask_cache,
        )
        mask = masks[layer]
        if not np.any(mask):
            session_rows.append(
                {
                    "session_id": source.session_id,
                    "probe": source.probe,
                    "status": "empty_layer_mask",
                    "n_layer_channels": 0,
                }
            )
            continue

        power = np.load(source.path, mmap_mode="r")
        trials_db = layer_mean_baseline_db(power[:, mask, :, :])
        trial_blocks.append(trials_db)
        channel_counts.append(int(np.sum(mask)))
        session_rows.append(
            {
                "session_id": source.session_id,
                "probe": source.probe,
                "area_label": source.area_label,
                "n_trials": source.n_trials,
                "n_layer_channels": int(np.sum(mask)),
                "crossover_idx": meta.crossover_idx,
                "orientation": meta.orientation,
                "status": "ok",
            }
        )
        classification_rows.append(
            {
                "session_id": source.session_id,
                "probe_letter": source.probe,
                "crossover_idx": meta.crossover_idx,
                "orientation": meta.orientation,
            }
        )

    if not trial_blocks:
        return {
            "area": area,
            "layer": layer,
            "condition": condition,
            "status": "no_valid_layer_channels",
            "n_sessions": len(sources),
            "n_trials": 0,
            "sessions": session_rows,
        }

    pooled = np.concatenate(trial_blocks, axis=0)
    mean_db, sem_db = aggregate_trial_stats(pooled)
    band_epoch_stats = compute_band_epoch_stats(pooled)
    omission_window = OMISSION_ANALYSIS_WINDOWS_MS.get(condition)

    stats_text = _stats_annotation_text(
        area=area,
        layer=layer,
        condition=condition,
        n_sessions=len(trial_blocks),
        n_trials=int(pooled.shape[0]),
        n_channels_mean=float(np.mean(channel_counts)),
        classification_rows=classification_rows,
        band_epoch_stats=band_epoch_stats,
        omission_window=omission_window,
    )
    fig = build_area_layer_band_figure(
        mean_db,
        sem_db,
        area=area,
        layer=layer,
        condition=condition,
        stats_text=stats_text,
        omission_window=omission_window,
    )

    return {
        "area": area,
        "layer": layer,
        "condition": condition,
        "status": "ok",
        "n_sessions": len(trial_blocks),
        "n_trials": int(pooled.shape[0]),
        "n_channels_mean": float(np.mean(channel_counts)),
        "sessions": session_rows,
        "band_epoch_stats": band_epoch_stats,
        "classification_rows": classification_rows,
        "figure": fig,
        "baseline_window_ms": BASELINE_WINDOW_MS,
        "omission_window_ms": omission_window,
    }


def build_all_area_layer_tfr_figures(
    *,
    tfr_dir: Path = TFR_DIR,
    out_dir: Path = DEFAULT_OUT_DIR,
    areas: list[str] | None = None,
    layers: tuple[str, ...] = LAYER_NAMES,
    conditions: list[str] | None = None,
    rebuild_masks: bool = False,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Generate all area × layer × condition band figures."""
    areas = list(areas or CANONICAL_AREAS)
    conditions = list(conditions or ALL_CONDITIONS)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_sources: list[tuple[str, str]] = []
    for area in areas:
        for condition in conditions:
            for source in discover_tfr_sources(area, condition, tfr_dir=tfr_dir):
                all_sources.append((source.session_id, source.probe))

    mask_cache_path = out_dir / "layer_masks.json"
    if rebuild_masks or not mask_cache_path.exists():
        build_layer_mask_cache(all_sources, out_path=mask_cache_path)
    mask_cache = load_layer_mask_cache(mask_cache_path).get("by_key", {})

    manifest_rows: list[dict[str, Any]] = []
    n_ok = 0
    n_missing = 0

    for area in areas:
        for layer in layers:
            layer_dir = out_dir / area / layer
            layer_dir.mkdir(parents=True, exist_ok=True)
            for condition in conditions:
                html_name = f"{area}_{layer}_{condition}_bands.html"
                html_path = layer_dir / html_name
                if skip_existing and html_path.exists():
                    row = {
                        "area": area,
                        "layer": layer,
                        "condition": condition,
                        "status": "skipped_existing",
                        "output_html": str(html_path),
                    }
                    manifest_rows.append(row)
                    n_ok += 1
                    continue
                result = build_area_layer_condition_figure(
                    area,
                    layer,
                    condition,
                    tfr_dir=tfr_dir,
                    mask_cache=mask_cache,
                )
                row = {k: v for k, v in result.items() if k != "figure"}
                html_name = f"{area}_{layer}_{condition}_bands.html"
                html_path = layer_dir / html_name
                if result.get("status") == "ok" and "figure" in result:
                    result["figure"].write_html(str(html_path), include_plotlyjs="cdn")
                    row["output_html"] = str(html_path)
                    n_ok += 1
                else:
                    row["output_html"] = None
                    n_missing += 1
                manifest_rows.append(row)

    manifest = {
        "n_areas": len(areas),
        "n_layers": len(layers),
        "n_conditions": len(conditions),
        "n_requested": len(areas) * len(layers) * len(conditions),
        "n_ok": n_ok,
        "n_missing": n_missing,
        "baseline_window_ms": BASELINE_WINDOW_MS,
        "layer_classification": "spectrolaminar_putative",
        "figures": manifest_rows,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest
