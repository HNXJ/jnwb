#!/usr/bin/env python3
"""
Build per-session metadata sidecars via h5py (no PyNWB construct).

For each NWB in the catalog (or --session filter), write under
D:/workspace/data/metadata/{stem}/:

  electrodes.csv   — channel, probe, local_idx, location_raw, area, area_slot
  units.csv        — unit_id, peak_channel_id, area, quality, firing_rate, ...
  events.csv       — trial/event rows from intervals/omission_glo_passive
  h5_paths.json    — acquisition LFP/MUAe keys, intervals, units paths
  probe_areas.json — probe → ordered areas + channel slices

Dual-area rule (jnwb.sequence_layout):
  \"Y, Z\" / \"Y/Z\" → ch 1–64 = Y, ch 65–128 = Z
  bare \"V3\" → V3d then V3a
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import h5py
import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from jnwb.sequence_layout import (  # noqa: E402
    channel_slice_for_area,
    parse_probe_areas,
)

PROBE_LETTER = {"probeA": "A", "probeB": "B", "probeC": "C", "probeD": "D"}
PROBE_TO_LFP = {
    "probeA": "probe_0_lfp",
    "probeB": "probe_1_lfp",
    "probeC": "probe_2_lfp",
    "probeD": "probe_3_lfp",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--catalog",
        type=Path,
        default=Path("artifacts/data/nwb_catalog.json"),
    )
    p.add_argument(
        "--meta-root",
        type=Path,
        default=Path(os.environ.get("OMISSION_META_DIR", "D:/workspace/data/metadata")),
    )
    p.add_argument(
        "--session",
        nargs="*",
        default=None,
        help="Optional stem or session_prefix filters (substring match)",
    )
    p.add_argument(
        "--prefer-full",
        action="store_true",
        default=True,
        help="Skip short-nwb when a full file with same session_prefix exists",
    )
    p.add_argument(
        "--max-sessions",
        type=int,
        default=None,
        help="Cap sessions for smoke runs",
    )
    return p.parse_args()


def _as_str(x: Any) -> str:
    if isinstance(x, (bytes, np.bytes_)):
        return x.decode("utf-8", "replace")
    if isinstance(x, np.ndarray) and x.shape == ():
        return _as_str(x.item())
    return str(x)


def _read_col(group: h5py.Group, name: str) -> np.ndarray:
    return group[name][:]


def load_catalog_sessions(catalog_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return list(data.get("sessions", []))


def select_sessions(
    sessions: Sequence[Dict[str, Any]],
    filters: Optional[Sequence[str]],
    prefer_full: bool,
) -> List[Dict[str, Any]]:
    rows = list(sessions)
    if prefer_full:
        by_prefix: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            by_prefix.setdefault(r.get("session_prefix") or r["stem"], []).append(r)
        chosen: List[Dict[str, Any]] = []
        for _pref, group in by_prefix.items():
            full = [g for g in group if not g.get("short_nwb")]
            chosen.extend(full if full else group)
        rows = chosen
    if filters:
        toks = [t.lower() for t in filters]
        rows = [
            r
            for r in rows
            if any(
                t in str(r.get("stem", "")).lower()
                or t in str(r.get("session_prefix", "")).lower()
                or t in str(r.get("path", "")).lower()
                for t in toks
            )
        ]
    return rows


def build_electrodes(f: h5py.File) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    elec = f["general/extracellular_ephys/electrodes"]
    n = len(elec["id"])
    ids = _read_col(elec, "id")
    locs = [_as_str(x) for x in _read_col(elec, "location")]
    if "group_name" in elec:
        groups = [_as_str(x) for x in _read_col(elec, "group_name")]
    elif "probe" in elec:
        groups = [_as_str(x) for x in _read_col(elec, "probe")]
    else:
        raise KeyError("electrodes table missing group_name and probe")
    probes = (
        [_as_str(x) for x in _read_col(elec, "probe")]
        if "probe" in elec
        else list(groups)
    )

    rows: List[Dict[str, Any]] = []
    # local index within each probe (order of appearance)
    local_counters: Dict[str, int] = {}
    probe_labels: Dict[str, str] = {}  # probe -> location_raw (first seen)

    for i in range(n):
        probe = groups[i]
        local = local_counters.get(probe, 0)
        local_counters[probe] = local + 1
        loc_raw = locs[i]
        if probe not in probe_labels:
            probe_labels[probe] = loc_raw

        areas = parse_probe_areas(loc_raw)
        area = None
        area_slot = None
        if len(areas) == 1:
            area = areas[0]
            area_slot = 0
        elif len(areas) >= 2:
            # assign by local channel half / partition
            sl = None
            for slot, a in enumerate(areas):
                ch = channel_slice_for_area(areas, a, n_channels=128)
                if ch is None:
                    continue
                if ch.start <= local < ch.stop:
                    area = a
                    area_slot = slot
                    sl = ch
                    break
            if area is None:
                # fallback equal partition
                area = areas[min(local * len(areas) // 128, len(areas) - 1)]
                area_slot = areas.index(area)

        rows.append(
            {
                "channel_id": int(ids[i]),
                "global_index": i,
                "probe": probe,
                "probe_letter": PROBE_LETTER.get(probe, "?"),
                "local_idx": local,
                "location_raw": loc_raw,
                "area": area,
                "area_slot": area_slot,
                "lfp_key": PROBE_TO_LFP.get(probe),
            }
        )

    probe_meta: Dict[str, Any] = {}
    for probe, loc_raw in probe_labels.items():
        areas = parse_probe_areas(loc_raw)
        slices = {
            a: {
                "start": channel_slice_for_area(areas, a).start,
                "stop": channel_slice_for_area(areas, a).stop,
            }
            for a in areas
            if channel_slice_for_area(areas, a) is not None
        }
        probe_meta[probe] = {
            "location_raw": loc_raw,
            "areas": list(areas),
            "channel_slices": slices,
            "lfp_key": PROBE_TO_LFP.get(probe),
            "n_channels": local_counters.get(probe, 0),
        }
    return rows, probe_meta


def _as_optional_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (bytes, np.bytes_)):
        s = _as_str(x).strip()
        if not s or s.lower() in ("nan", "none"):
            return None
        try:
            return float(s)
        except ValueError:
            return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(v):
        return None
    return v


def build_units(f: h5py.File, channel_area: Dict[int, str]) -> List[Dict[str, Any]]:
    if "units" not in f:
        return []
    u = f["units"]
    ids = _read_col(u, "id")
    n = len(ids)
    peak = _read_col(u, "peak_channel_id") if "peak_channel_id" in u else [None] * n
    fr = _read_col(u, "firing_rate") if "firing_rate" in u else [None] * n
    qual = [_as_str(x) for x in _read_col(u, "quality")] if "quality" in u else [""] * n
    snr = _read_col(u, "snr") if "snr" in u else [None] * n
    presence = (
        _read_col(u, "presence_ratio") if "presence_ratio" in u else [None] * n
    )

    rows: List[Dict[str, Any]] = []
    for i in range(n):
        uid = _as_optional_float(ids[i])
        pch = _as_optional_float(peak[i])
        pch_i = int(pch) if pch is not None else None
        fr_v = _as_optional_float(fr[i])
        snr_v = _as_optional_float(snr[i])
        pr_v = _as_optional_float(presence[i])
        rows.append(
            {
                "unit_id": int(uid) if uid is not None else i,
                "peak_channel_id": pch_i,
                "area": channel_area.get(pch_i) if pch_i is not None else None,
                "quality": qual[i],
                "firing_rate": fr_v,
                "snr": snr_v,
                "presence_ratio": pr_v,
            }
        )
    return rows


def build_events(f: h5py.File) -> List[Dict[str, Any]]:
    path = "intervals/omission_glo_passive"
    if path not in f:
        return []
    g = f[path]
    n = len(g["id"])
    cols = [
        "id",
        "start_time",
        "stop_time",
        "trial_num",
        "stimulus_number",
        "task_condition_number",
        "correct",
        "is_omission",
        "codes",
        "phase",
    ]
    present = [c for c in cols if c in g]
    data = {c: _read_col(g, c) for c in present}

    rows: List[Dict[str, Any]] = []
    for i in range(n):
        row: Dict[str, Any] = {}
        for c in present:
            v = data[c][i]
            if isinstance(v, (bytes, np.bytes_)):
                row[c] = _as_str(v)
            elif isinstance(v, (np.floating, float)):
                row[c] = float(v)
            elif isinstance(v, (np.integer, int)):
                row[c] = int(v)
            else:
                row[c] = _as_str(v)
        rows.append(row)
    return rows


def build_h5_paths(f: h5py.File) -> Dict[str, Any]:
    acq = list(f["acquisition"].keys()) if "acquisition" in f else []
    lfp = sorted(k for k in acq if k.endswith("_lfp"))
    muae = sorted(k for k in acq if k.endswith("_muae"))
    intervals = list(f["intervals"].keys()) if "intervals" in f else []
    return {
        "electrodes": "general/extracellular_ephys/electrodes",
        "units": "units",
        "intervals_root": "intervals",
        "intervals": intervals,
        "events_table": "intervals/omission_glo_passive"
        if "omission_glo_passive" in intervals
        else None,
        "acquisition": acq,
        "lfp_keys": lfp,
        "muae_keys": muae,
        "lfp_data_template": "acquisition/{key}/data",
        "lfp_timestamps_template": "acquisition/{key}/timestamps",
    }


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def process_session(nwb_path: Path, out_dir: Path) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    with h5py.File(nwb_path, "r") as f:
        electrodes, probe_meta = build_electrodes(f)
        channel_area = {
            int(r["channel_id"]): r["area"] for r in electrodes if r.get("area")
        }
        units = build_units(f, channel_area)
        events = build_events(f)
        h5_paths = build_h5_paths(f)

    write_csv(out_dir / "electrodes.csv", electrodes)
    write_csv(out_dir / "units.csv", units)
    write_csv(out_dir / "events.csv", events)
    (out_dir / "probe_areas.json").write_text(
        json.dumps(probe_meta, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "h5_paths.json").write_text(
        json.dumps(h5_paths, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "nwb_path": str(nwb_path),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "n_electrodes": len(electrodes),
        "n_units": len(units),
        "n_events": len(events),
        "probes": list(probe_meta.keys()),
        "areas": sorted({r["area"] for r in electrodes if r.get("area")}),
    }
    (out_dir / "sidecar_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> None:
    args = parse_args()
    if not args.catalog.is_file():
        raise FileNotFoundError(
            f"Catalog missing: {args.catalog}. Run scripts/build_nwb_catalog.py first."
        )
    sessions = select_sessions(
        load_catalog_sessions(args.catalog), args.session, args.prefer_full
    )
    if args.max_sessions is not None:
        sessions = sessions[: args.max_sessions]
    if not sessions:
        raise SystemExit("No sessions selected")

    args.meta_root.mkdir(parents=True, exist_ok=True)
    results = []
    for s in sessions:
        nwb_path = Path(s["path"])
        stem = s["stem"]
        out_dir = args.meta_root / stem
        print(f"sidecar {stem} <- {nwb_path.name}")
        summary = process_session(nwb_path, out_dir)
        print(
            f"  electrodes={summary['n_electrodes']} units={summary['n_units']} "
            f"events={summary['n_events']} areas={summary['areas']}"
        )
        results.append({"stem": stem, **summary})

    index_path = args.meta_root / "sidecar_index.json"
    index_path.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "n_sessions": len(results),
                "sessions": results,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {index_path}")


if __name__ == "__main__":
    main()
