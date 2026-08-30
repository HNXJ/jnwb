"""Is the absence of O+ units specific to sub-V182o_ses-260702, or subject-wide? (2026-08-29)

The first representative pilot session classified 409 units with is_o_plus = 0 and
is_o_plusplus = 0 (all o_plus_tier = "Null"), which removes the O+/O++ functional-class contrast
from the pilot. This script classifies the remaining V182o sessions to establish whether that is
a property of this session or of the subject, so the pilot's class-contrast scope can be set from
evidence rather than from one session.

Run:
  OMISSION_NWB_DIR=... OMISSION_ANALYSIS_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_v182o_oplus_yield_20260829
"""
import json
import logging
from pathlib import Path

import pandas as pd

logging.disable(logging.INFO)

from jnwb.paths import nwb_dir  # noqa: E402
from omission.jnwb_ext.session import OmissionSession  # noqa: E402
from omission.jnwb_ext.unit_classification import classify_session_units  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "v182o-oplus-yield-20260829.json"


def main() -> None:
    root = Path(nwb_dir())
    paths = sorted(root.glob("sub-V182o_*.nwb"))
    rows = []
    for p in paths:
        try:
            df = classify_session_units(OmissionSession(str(p)))
        except Exception as exc:  # noqa: BLE001
            rows.append({"session": p.stem, "error": f"{type(exc).__name__}: {exc}"})
            print(f"{p.stem}: ERROR {exc}", flush=True)
            continue
        counts = df["display_class"].value_counts().to_dict()
        row = {
            "session": p.stem,
            "n_units": int(len(df)),
            "n_o_plus": int(df["is_o_plus"].sum()),
            "n_o_plusplus": int(df["is_o_plusplus"].sum()),
            "display_class_counts": {str(k): int(v) for k, v in counts.items()},
            "n_pass_all_three_omission_q05": int(
                ((df["q_om_vs_base_shuffle"] < 0.05)
                 & (df["q_om_vs_ctrl_shuffle"] < 0.05)
                 & (df["q_om_vs_delay_shuffle"] < 0.05)).sum()
            ),
        }
        rows.append(row)
        print(f"{p.stem}: n={row['n_units']} O+={row['n_o_plus']} O++={row['n_o_plusplus']} "
              f"classes={row['display_class_counts']}", flush=True)

    ok = [r for r in rows if "error" not in r]
    summary = {
        "n_sessions": len(ok),
        "total_units": sum(r["n_units"] for r in ok),
        "total_o_plus": sum(r["n_o_plus"] for r in ok),
        "total_o_plusplus": sum(r["n_o_plusplus"] for r in ok),
        "sessions_with_any_o_plus": [r["session"] for r in ok if r["n_o_plus"] > 0],
    }
    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 3,
        "id": "v182o-oplus-yield-20260829",
        "kind": "evidence",
        "title": "O+/O++ unit yield across V182o sessions",
        "status": "provisional",
        "question": ("Is is_o_plus == 0 in sub-V182o_ses-260702 a session property or a "
                     "subject-wide property? Determines whether the representative pilot can "
                     "carry the requested O+/O++ functional-class contrast at all."),
        "summary": summary,
        "per_session": rows,
    }, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
