#!/usr/bin/env python3
"""
Build a durable NWB session catalog from directory listing (no PyNWB open).

Writes:
  artifacts/data/nwb_catalog.json
  artifacts/data/nwb_catalog.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from jnwb import paths as _P

STEM_RE = re.compile(
    r"^(?P<stem>sub-(?P<subject>[^_]+)_ses-(?P<session>[^_]+)(?:_rec)?)"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--nwb-dir",
        type=Path,
        default=Path(os.environ.get("OMISSION_NWB_DIR", _P.nwb_dir())),
    )
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/data"),
    )
    p.add_argument(
        "--exclude-short",
        action="store_true",
        default=False,
        help=(
            "Exclude rows sourced from the short-nwb/ subdirectory "
            "(short/incomplete recordings) from the catalog. Default: "
            "False (include them, tagged short_nwb=True), for backward "
            "compatibility."
        ),
    )
    return p.parse_args()


def parse_stem(path: Path) -> Dict[str, Any]:
    m = STEM_RE.match(path.stem)
    if not m:
        return {
            "stem": path.stem,
            "subject": None,
            "session_id": None,
            "session_prefix": path.stem,
        }
    subject = m.group("subject")
    session = m.group("session")
    # TFR / suite prefix often omits _rec
    session_prefix = f"sub-{subject}_ses-{session}"
    return {
        "stem": path.stem,
        "subject": subject,
        "session_id": session,
        "session_prefix": session_prefix,
    }


def collect_nwbs(nwb_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not nwb_dir.is_dir():
        raise FileNotFoundError(f"NWB dir not found: {nwb_dir}")

    candidates: List[Path] = []
    candidates.extend(sorted(nwb_dir.glob("*.nwb")))
    short = nwb_dir / "short-nwb"
    if short.is_dir():
        candidates.extend(sorted(short.glob("*.nwb")))

    for path in candidates:
        st = path.stat()
        meta = parse_stem(path)
        rel_parent = path.parent.name
        rows.append(
            {
                **meta,
                "path": str(path.resolve()),
                "filename": path.name,
                "bytes": int(st.st_size),
                "mtime_utc": datetime.fromtimestamp(
                    st.st_mtime, tz=timezone.utc
                ).isoformat(),
                "short_nwb": rel_parent == "short-nwb" or "short-nwb" in path.parts,
            }
        )
    # Prefer full NWB over short-nwb duplicate stems: keep both, flag short
    return rows


def main() -> None:
    args = parse_args()
    rows = collect_nwbs(args.nwb_dir)
    if args.exclude_short:
        rows = [r for r in rows if not r["short_nwb"]]
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    catalog = {
        "schema_version": 1,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "nwb_dir": str(args.nwb_dir.resolve()),
        "n_files": len(rows),
        "sessions": rows,
    }
    json_path = out / "nwb_catalog.json"
    json_path.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")

    csv_path = out / "nwb_catalog.csv"
    fields = [
        "stem",
        "subject",
        "session_id",
        "session_prefix",
        "filename",
        "path",
        "bytes",
        "mtime_utc",
        "short_nwb",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})

    subjects = sorted({r["subject"] for r in rows if r["subject"]})
    print(f"wrote {json_path} n_files={len(rows)} subjects={subjects}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
