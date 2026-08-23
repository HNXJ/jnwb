#!/usr/bin/env python3
"""
Join NWB catalog + TFR inventory + sidecar presence into session_readiness.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set
from jnwb import paths as _P


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--catalog",
        type=Path,
        default=Path("artifacts/data/nwb_catalog.json"),
    )
    p.add_argument(
        "--tfr-dir",
        type=Path,
        default=Path(os.environ.get("OMISSION_TFR_DIR", _P.tfr_dir())),
    )
    p.add_argument(
        "--meta-root",
        type=Path,
        default=Path(os.environ.get("OMISSION_META_DIR", _P.meta_dir())),
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("artifacts/data/session_readiness.csv"),
    )
    return p.parse_args()


TFR_RE = re.compile(
    r"^(?P<prefix>sub-[^\\/]+_ses-[0-9]+)-[A-Z]-.+-(?P<cond>[A-Z0-9]+)\.npz$"
)


def tfr_index(tfr_dir: Path) -> Dict[str, Dict[str, Any]]:
    """prefix -> {n_files, conditions, areas_guess}.

    2026-08-14: the TFR corpus migrated .npy -> .npz (scripts/precompute_tfr_arrays.py, renamed
    2026-08-22 from precompute_tfr_arrays_v2.py) and
    grew a 4th probe letter (A/B/C/D), but this scan was never updated -- it globbed only *.npy
    and matched only [ABC], so it silently found 0 files against the current 970-file .npz
    corpus while session_readiness.csv kept reporting tfr_ok=0/22 (see context/PROJECT_STATE.md
    section 1, "OPEN INCONSISTENCY"). Fixed to match the corpus actually on disk.
    """
    out: Dict[str, Dict[str, Any]] = {}
    if not tfr_dir.is_dir():
        return out
    for path in tfr_dir.glob("*.npz"):
        m = TFR_RE.match(path.name)
        if not m:
            continue
        pref = m.group("prefix")
        cond = m.group("cond")
        # area token between probe and condition
        parts = path.name[len(pref) + 1 :].split("-")
        # e.g. A-FEF-RRRR.npz -> ['A','FEF','RRRR.npz'] after strip prefix-
        area = parts[1] if len(parts) >= 3 else None
        slot = out.setdefault(
            pref, {"n_files": 0, "conditions": set(), "areas": set()}
        )
        slot["n_files"] += 1
        slot["conditions"].add(cond)
        if area:
            slot["areas"].add(area)
    return out


def sidecar_ok(meta_root: Path, stem: str) -> bool:
    d = meta_root / stem
    needed = ("electrodes.csv", "units.csv", "events.csv", "h5_paths.json")
    return d.is_dir() and all((d / n).is_file() and (d / n).stat().st_size > 0 for n in needed)


def main() -> None:
    args = parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    sessions = catalog.get("sessions", [])
    tfr = tfr_index(args.tfr_dir)

    # Prefer full NWB rows for readiness (still list short as separate)
    rows: List[Dict[str, Any]] = []
    for s in sessions:
        pref = s.get("session_prefix") or s["stem"]
        tinfo = tfr.get(pref, {"n_files": 0, "conditions": set(), "areas": set()})
        n_tfr = int(tinfo["n_files"])
        conds = sorted(tinfo["conditions"]) if isinstance(tinfo["conditions"], set) else []
        r_family = {"RRRR", "RXRR", "RRXR", "RRRX"}
        tfr_r_family_ok = r_family.issubset(set(conds))
        sc_ok = sidecar_ok(args.meta_root, s["stem"])
        rows.append(
            {
                "stem": s["stem"],
                "session_prefix": pref,
                "subject": s.get("subject"),
                "session_id": s.get("session_id"),
                "short_nwb": bool(s.get("short_nwb")),
                "nwb_ok": True,
                "nwb_bytes": s.get("bytes"),
                "nwb_path": s.get("path"),
                "sidecar_ok": sc_ok,
                "tfr_ok": n_tfr > 0,
                "tfr_n_files": n_tfr,
                "tfr_r_family_ok": tfr_r_family_ok,
                "tfr_conditions": "|".join(conds),
                "suite_tfr_ready": (not s.get("short_nwb"))
                and sc_ok
                and n_tfr > 0
                and tfr_r_family_ok,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with args.out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    json_out = args.out.with_suffix(".json")
    json_out.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "n_rows": len(rows),
                "n_tfr_ok": sum(1 for r in rows if r["tfr_ok"]),
                "n_sidecar_ok": sum(1 for r in rows if r["sidecar_ok"]),
                "n_suite_tfr_ready": sum(1 for r in rows if r["suite_tfr_ready"]),
                "rows": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.out} n={len(rows)}")
    print(f"wrote {json_out}")
    print(
        "tfr_ok",
        sum(1 for r in rows if r["tfr_ok"]),
        "sidecar_ok",
        sum(1 for r in rows if r["sidecar_ok"]),
        "suite_tfr_ready",
        sum(1 for r in rows if r["suite_tfr_ready"]),
    )
    # highlight V182o
    for r in rows:
        if r.get("subject") == "V182o" and not r.get("short_nwb"):
            print(
                f"  V182o {r['session_prefix']}: tfr_ok={r['tfr_ok']} "
                f"sidecar_ok={r['sidecar_ok']} suite_tfr_ready={r['suite_tfr_ready']}"
            )


if __name__ == "__main__":
    main()
