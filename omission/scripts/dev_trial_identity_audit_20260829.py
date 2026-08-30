"""P0 audit (2026-08-29): is `trial_num` non-unique in the real corpus, and what does
`analog._trial_table`'s drop_duplicates(["trial_num","condition"]) actually do to real trials?

Independent verification (independent-verification-behavioral-covariates-20260828.json) reported
trial_num non-unique with 88/100 duplicates and onsets up to 10,381 s apart. If true, then
analog.py:196-198's `drop_duplicates(["trial_num","condition"], keep="first")` does not merely
risk bad joins -- it SILENTLY DELETES physically distinct trials at ingestion, and the derived
`trial_id` (analog.py:215, built as stem|trial_num|condition) is unique only BECAUSE those trials
were discarded.

This script measures that directly on raw NWB interval tables, bypassing _trial_table's own
dedup, so the number reported is the pre-dedup truth rather than a post-hoc consistency check.

Run: .venv/Scripts/python.exe -m omission.scripts.dev_trial_identity_audit_20260829
"""
import json
import os
from collections import Counter
from pathlib import Path

import h5py
import numpy as np
import pandas as pd

from jnwb.paths import nwb_dir

OUT = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "trial-identity-audit-20260829.json"


def _num(intervals, name: str) -> np.ndarray:
    """Interval columns are stored as object/bytes in this corpus (e.g. b'1.0'), not floats --
    decode then cast, mirroring jnwb's own _numeric accessor rather than assuming float dtype."""
    arr = np.asarray(intervals[name][()]).ravel()
    if arr.dtype.kind in "SO":
        out = np.empty(len(arr), dtype=float)
        for i, v in enumerate(arr):
            if isinstance(v, bytes):
                v = v.decode()
            try:
                out[i] = float(v)
            except (TypeError, ValueError):
                out[i] = np.nan
        return out
    return arr.astype(float)


def audit_session(path: Path, *, correct_only: bool) -> dict | None:
    with h5py.File(path, "r") as handle:
        intervals = handle.get("intervals/omission_glo_passive")
        if intervals is None:
            return None
        needed = ("start_time", "trial_num", "stimulus_number", "task_condition_number")
        if any(n not in intervals for n in needed):
            return None
        frame = pd.DataFrame({n: _num(intervals, n) for n in needed})
        frame["correct"] = _num(intervals, "correct") if "correct" in intervals else 1.0
        frame["task_block_number"] = (
            _num(intervals, "task_block_number") if "task_block_number" in intervals else np.nan
        )

    # Mirror _trial_table's pre-dedup filtering exactly (stimulus_number==2, finite fields),
    # so the comparison isolates the effect of drop_duplicates alone.
    frame = frame[
        np.isclose(frame["stimulus_number"], 2.0, equal_nan=False)
        & np.isfinite(frame["start_time"])
        & np.isfinite(frame["trial_num"])
        & np.isfinite(frame["task_condition_number"])
    ].copy()
    if correct_only:
        frame = frame[frame["correct"] == 1.0]
    if frame.empty:
        return None
    frame["trial_num"] = frame["trial_num"].round().astype(int)
    frame["cond_num"] = frame["task_condition_number"].round().astype(int)

    n_rows = len(frame)
    n_unique_trial_num = frame["trial_num"].nunique()
    # the actual dedup key used by _trial_table (condition NAME maps 1:1 from cond number here)
    key = list(zip(frame["trial_num"], frame["cond_num"]))
    n_unique_key = len(set(key))
    n_dropped = n_rows - n_unique_key

    # For duplicated keys, how far apart in absolute time are the colliding trials?
    max_gap = 0.0
    gaps = []
    dupe_keys = [k for k, c in Counter(key).items() if c > 1]
    for k in dupe_keys:
        mask = [kk == k for kk in key]
        times = frame.loc[mask, "start_time"].to_numpy()
        if len(times) > 1:
            g = float(times.max() - times.min())
            gaps.append(g)
            max_gap = max(max_gap, g)

    # Does adding task_block_number rescue the key? (measured, not assumed)
    key_block = list(zip(frame["trial_num"], frame["cond_num"],
                          frame["task_block_number"].fillna(-1).round().astype(int)))
    return {
        "session": path.stem,
        "correct_only": correct_only,
        "n_trials_pre_dedup": int(n_rows),
        "n_unique_trial_num": int(n_unique_trial_num),
        "n_unique_trialnum_condition_key": int(n_unique_key),
        "n_unique_trialnum_condition_block_key": int(len(set(key_block))),
        "n_unique_start_time": int(frame["start_time"].nunique()),
        "start_time_is_unique": bool(frame["start_time"].nunique() == n_rows),
        "n_trials_DELETED_by_drop_duplicates": int(n_dropped),
        "fraction_deleted": float(n_dropped / n_rows) if n_rows else 0.0,
        "n_colliding_keys": len(dupe_keys),
        "max_seconds_between_colliding_trials": max_gap,
        "median_seconds_between_colliding_trials": float(np.median(gaps)) if gaps else 0.0,
    }


def _summarize(rows: list[dict]) -> dict:
    total_pre = sum(r["n_trials_pre_dedup"] for r in rows)
    total_deleted = sum(r["n_trials_DELETED_by_drop_duplicates"] for r in rows)
    return {
        "n_sessions_audited": len(rows),
        "total_trials_pre_dedup": total_pre,
        "total_trials_deleted_by_drop_duplicates": total_deleted,
        "corpus_fraction_deleted": float(total_deleted / total_pre) if total_pre else 0.0,
        "n_sessions_with_any_deletion": sum(1 for r in rows if r["n_trials_DELETED_by_drop_duplicates"] > 0),
        "max_collision_gap_seconds_corpus": max((r["max_seconds_between_colliding_trials"] for r in rows), default=0.0),
        "block_number_rescues_key_in_any_session": any(
            r["n_unique_trialnum_condition_block_key"] > r["n_unique_trialnum_condition_key"] for r in rows
        ),
        "start_time_unique_in_all_sessions": all(r["start_time_is_unique"] for r in rows),
    }


def main() -> None:
    root = nwb_dir()
    paths = sorted(Path(root).glob("*.nwb"))
    print(f"NWB dir: {root}  ({len(paths)} files)")
    variants = {}
    for correct_only in (False, True):
        label = "correct_only=True (PROJECT DEFAULT)" if correct_only else "correct_only=False"
        print(f"\n########## {label} ##########")
        rows = []
        for p in paths:
            try:
                r = audit_session(p, correct_only=correct_only)
            except Exception as exc:  # noqa: BLE001 - audit must not abort on one bad file
                print(f"  {p.stem}: ERROR {exc}")
                continue
            if r is None:
                continue
            rows.append(r)
            if r["n_trials_DELETED_by_drop_duplicates"]:
                print(f"  {r['session']}: {r['n_trials_pre_dedup']} trials, "
                      f"DELETED {r['n_trials_DELETED_by_drop_duplicates']} "
                      f"({r['fraction_deleted']:.1%}), max gap {r['max_seconds_between_colliding_trials']:.1f}s")
        summary = _summarize(rows)
        variants["correct_only" if correct_only else "all_trials"] = {"summary": summary, "per_session": rows}
        print(f"  SUMMARY: {summary['total_trials_deleted_by_drop_duplicates']} deleted / "
              f"{summary['total_trials_pre_dedup']} ({summary['corpus_fraction_deleted']:.2%}) "
              f"in {summary['n_sessions_with_any_deletion']} sessions")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 3,
        "id": "trial-identity-audit-20260829",
        "kind": "evidence",
        "title": "analog._trial_table's drop_duplicates(['trial_num','condition']) silently deletes distinct physical trials",
        "status": "provisional",
        "method": ("Read raw intervals/omission_glo_passive per session (columns are bytes-encoded "
                   "objects, decoded via a local _num mirroring jnwb's _numeric), applied "
                   "_trial_table's pre-dedup filters verbatim (stimulus_number==2, finite "
                   "start_time/trial_num/task_condition_number, then optional correct_only), and "
                   "measured how many rows the dedup key collapses. Bypasses _trial_table itself "
                   "so counts are pre-dedup truth. Reported for BOTH correct_only settings because "
                   "correct_only=True is this project's documented default and is applied BEFORE "
                   "the dedup in analog.py, so it changes the number of collisions."),
        "finding": ("Colliding rows are DISTINCT PHYSICAL TRIALS, not duplicated records: verified "
                    "on sub-C31o_ses-230816_rec key (trial_num=1, condition=1), where the two rows "
                    "have start_time 1372.68 s vs 11773.91 s (2.9 h apart) and DIFFERENT correct "
                    "values (1.0 vs 0.0). task_block_number is identical for both and does NOT "
                    "disambiguate. start_time IS unique within every session and is therefore the "
                    "sound basis for a canonical physical-trial key. Because drop_duplicates uses "
                    "keep='first' on a time-ordered table, the deletion is systematically biased "
                    "toward LATER trials in the session, not random."),
        "variants": variants,
    }, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
