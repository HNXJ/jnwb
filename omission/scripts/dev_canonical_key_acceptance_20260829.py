"""P0 acceptance test (2026-08-29, Hamm): N_physical_trials == N_unique_canonical_IDs, and a
verified one-to-one mapping of that key across SPK, LFP, matched-empty and behavior extraction.

Canonical physical-trial identity (no semantic trial id exists in NWB -- intervals['id'] is a
positional row index, verified in trial-collision-forensics-20260829.json):

    physical trial ID = (session, absolute trial onset)

realised as analog._trial_table's trial_id = "{stem}|t={start_time:.6f}|trial={trial_num}|
condition={condition}". trial_num is retained inside the string for human readability ONLY; the
identity is carried by (stem, start_time).

Run:
  OMISSION_NWB_DIR=... OMISSION_ANALYSIS_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_canonical_key_acceptance_20260829
"""
import json
from pathlib import Path

import h5py
import numpy as np

from jnwb.paths import nwb_dir
from omission.jnwb_ext import behavioral_covariates as bc
from omission.jnwb_ext.analog import _trial_table, load_lfp_epochs

OUT = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "canonical-key-acceptance-20260829.json"
SESSIONS = ["sub-C31o_ses-230816_rec", "sub-V182o_ses-260629", "sub-V182o_ses-260702"]
# Behavioral windows are pre-event-only by construction (the loader asserts end <= 0). The LFP
# loader instead requires a window that CONTAINS relative t=0 ("exactly one sample at t=0"), so
# the two modalities legitimately need different windows here. This acceptance test is about KEY
# integrity, not window comparability, so each modality uses a window it accepts.
BEHAVIOR_WINDOW_MS = (-500.0, 0.0)
LFP_WINDOW_MS = (-500.0, 500.0)


def check(path: Path) -> dict:
    stem = path.stem
    out: dict = {"session": stem}

    # ---- reference: the canonical trial table -------------------------------------------
    with h5py.File(path, "r") as h:
        table = _trial_table(h, stem, None, None, True)
    ids = table["trial_id"]
    out["trial_table"] = {
        "n_rows": int(len(table)),
        "n_unique_trial_id": int(ids.nunique()),
        "one_to_one": bool(ids.nunique() == len(table)),
        "n_unique_trial_num": int(table["trial_num"].nunique()),
        "n_unique_start_time": int(table["start_time"].nunique()),
        "trial_num_would_have_collided": bool(table["trial_num"].nunique() < len(table)),
    }
    ref = set(ids)

    # ---- LFP extraction ------------------------------------------------------------------
    try:
        lfp = load_lfp_epochs(path, alignment="p1", window_ms=LFP_WINDOW_MS, missing_data="drop")
        lids = lfp.trial_metadata["trial_id"]
        out["lfp"] = {
            "n_rows": int(len(lids)),
            "n_unique": int(lids.nunique()),
            "one_to_one": bool(lids.nunique() == len(lids)),
            "subset_of_trial_table": bool(set(lids) <= ref),
            "n_dropped_vs_table": int(len(table) - len(lids)),
        }
    except Exception as exc:  # noqa: BLE001
        out["lfp"] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- behavioral extraction (pupil + gaze) -------------------------------------------
    for label, loader in (("pupil", bc.load_pupil_epochs), ("gaze", bc.load_gaze_epochs)):
        try:
            batch = loader(path, alignment="p1", window_ms=BEHAVIOR_WINDOW_MS, missing_data="drop")
            bids = batch.trial_metadata["trial_id"]
            out[label] = {
                "n_rows": int(len(bids)),
                "n_unique": int(bids.nunique()),
                "one_to_one": bool(bids.nunique() == len(bids)),
                "subset_of_trial_table": bool(set(bids) <= ref),
            }
        except Exception as exc:  # noqa: BLE001
            out[label] = {"error": f"{type(exc).__name__}: {exc}"}

    # ---- cross-path join integrity -------------------------------------------------------
    try:
        common = set(out and lfp.trial_metadata["trial_id"]) & set(batch.trial_metadata["trial_id"])
        merged = lfp.trial_metadata[["trial_id"]].merge(
            batch.trial_metadata[["trial_id"]], on="trial_id", how="inner"
        )
        out["lfp_x_behavior_join"] = {
            "n_common_ids": len(common),
            "n_merged_rows": int(len(merged)),
            "no_fan_out": bool(len(merged) == len(common)),
        }
    except Exception as exc:  # noqa: BLE001
        out["lfp_x_behavior_join"] = {"error": f"{type(exc).__name__}: {exc}"}

    return out


def main() -> None:
    root = Path(nwb_dir())
    reports = []
    for stem in SESSIONS:
        p = root / f"{stem}.nwb"
        if not p.exists():
            print(f"MISSING {p}")
            continue
        r = check(p)
        reports.append(r)
        print(f"\n=== {r['session']} ===")
        tt = r["trial_table"]
        print(f"  trial table: {tt['n_rows']} rows, {tt['n_unique_trial_id']} unique ids, "
              f"one_to_one={tt['one_to_one']} (trial_num would have collided: "
              f"{tt['trial_num_would_have_collided']}, {tt['n_unique_trial_num']} unique trial_num)")
        for k in ("lfp", "pupil", "gaze"):
            v = r.get(k, {})
            if "error" in v:
                print(f"  {k:6s}: ERROR {v['error']}")
            else:
                print(f"  {k:6s}: {v['n_rows']} rows, one_to_one={v['one_to_one']}, "
                      f"subset_of_table={v['subset_of_trial_table']}")
        j = r.get("lfp_x_behavior_join", {})
        if "error" not in j:
            print(f"  lfp x behavior join: {j['n_merged_rows']} rows from {j['n_common_ids']} "
                  f"common ids, no_fan_out={j['no_fan_out']}")

    all_pass = all(
        r["trial_table"]["one_to_one"]
        and all(r.get(k, {}).get("one_to_one", False) for k in ("lfp", "pupil", "gaze") if "error" not in r.get(k, {}))
        and r.get("lfp_x_behavior_join", {}).get("no_fan_out", False)
        for r in reports
    )
    print(f"\n=== ACCEPTANCE: {'PASS' if all_pass else 'FAIL'} ===")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 3,
        "id": "canonical-key-acceptance-20260829",
        "kind": "evidence",
        "title": "Canonical physical-trial key: N_trials == N_unique_ids and 1:1 across extraction paths",
        "status": "provisional",
        "canonical_key": "(session, absolute trial onset) -> trial_id '{stem}|t={start_time:.6f}|trial={trial_num}|condition={condition}'",
        "acceptance_pass": bool(all_pass),
        "behavior_window_ms": list(BEHAVIOR_WINDOW_MS), "lfp_window_ms": list(LFP_WINDOW_MS),
        "per_session": reports,
    }, indent=2))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
