"""P0 forensics (2026-08-29, Hamm): for EVERY (trial_num, condition) collision, decide

  A. exact duplicate representation of one physical trial  -> deduplication is legitimate
  B. genuinely distinct physical trials sharing a trial_num -> the old code was deleting real data

by comparing the full event structure of each occurrence, not just its start_time.

Method. The interval table holds ONE ROW PER STIMULUS EVENT, not per trial (e.g. 15586 rows for
2008 stimulus_number==2 events in sub-C31o_ses-230816_rec). A physical trial is therefore a
CONTIGUOUS RUN of rows sharing a trial_num. For each trial_num that occurs in more than one such
run, this script compares the runs on: absolute onset, row-id span, length, and the full ordered
event signature (stimulus_number, event_code_type, codes, end_code) plus correct/is_omission.

Verdict per collision:
  A_exact_duplicate  -- identical event signature AND identical absolute timing
  B_distinct_trials  -- different absolute timing and/or different event signature
Anything else is reported as UNDETERMINED rather than forced into a bucket.

Run:
  OMISSION_NWB_DIR=... .venv/Scripts/python.exe \
    -m omission.scripts.dev_trial_collision_forensics_20260829
"""
import json
from collections import defaultdict
from pathlib import Path

import h5py
import numpy as np

from jnwb.paths import nwb_dir

OUT = Path(__file__).resolve().parents[1] / "artifacts" / ".lab" / "trial-collision-forensics-20260829.json"

AFFECTED = ["sub-C31o_ses-230816_rec", "sub-C31o_ses-230901_rec", "sub-V182o_ses-260629"]


def _col(iv, name):
    if name not in iv:
        return None
    arr = np.asarray(iv[name][()]).ravel()
    if arr.dtype.kind in "SO":
        return np.array([v.decode() if isinstance(v, bytes) else str(v) for v in arr], dtype=object)
    return arr


def _as_float(a):
    out = np.full(len(a), np.nan)
    for i, v in enumerate(a):
        try:
            out[i] = float(v)
        except (TypeError, ValueError):
            pass
    return out


def analyse(path: Path) -> dict:
    stem = path.stem
    with h5py.File(path, "r") as h:
        iv = h["intervals/omission_glo_passive"]
        start = np.asarray(iv["start_time"][()], dtype=float).ravel()
        stop = np.asarray(iv["stop_time"][()], dtype=float).ravel()
        row_id = np.asarray(iv["id"][()]).ravel()
        trial_num = _as_float(_col(iv, "trial_num"))
        stim = _as_float(_col(iv, "stimulus_number"))
        cond = _as_float(_col(iv, "task_condition_number"))
        block = _as_float(_col(iv, "task_block_number"))
        correct = _as_float(_col(iv, "correct"))
        is_om = _col(iv, "is_omission")
        ev_type = _col(iv, "event_code_type")
        codes = _col(iv, "codes")
        end_code = _col(iv, "end_code")

    order = np.argsort(start, kind="stable")

    # contiguous runs of identical trial_num in time order = one physical trial occurrence
    runs = []
    cur = [order[0]]
    for idx in order[1:]:
        if trial_num[idx] == trial_num[cur[-1]]:
            cur.append(idx)
        else:
            runs.append(cur)
            cur = [idx]
    runs.append(cur)

    by_trialnum = defaultdict(list)
    for run in runs:
        by_trialnum[float(trial_num[run[0]])].append(run)

    collisions = []
    for tn, occurrences in sorted(by_trialnum.items()):
        if len(occurrences) < 2:
            continue
        occ_summaries = []
        for run in occurrences:
            sig = tuple(
                (None if np.isnan(stim[i]) else stim[i],
                 ev_type[i] if ev_type is not None else None,
                 codes[i] if codes is not None else None,
                 end_code[i] if end_code is not None else None)
                for i in run
            )
            occ_summaries.append({
                "onset_s": float(start[run[0]]),
                "offset_s": float(stop[run[-1]]),
                "n_rows": len(run),
                "row_id_span": [int(row_id[run[0]]), int(row_id[run[-1]])],
                "conditions": sorted({None if np.isnan(cond[i]) else float(cond[i]) for i in run},
                                      key=lambda v: (v is None, v)),
                "blocks": sorted({None if np.isnan(block[i]) else float(block[i]) for i in run},
                                  key=lambda v: (v is None, v)),
                "correct": sorted({None if np.isnan(correct[i]) else float(correct[i]) for i in run},
                                   key=lambda v: (v is None, v)),
                "is_omission": sorted({str(is_om[i]) for i in run}) if is_om is not None else [],
                "_sig": sig,
            })

        onsets = [o["onset_s"] for o in occ_summaries]
        sigs = [o["_sig"] for o in occ_summaries]
        identical_timing = max(onsets) - min(onsets) < 1e-9
        identical_sig = all(s == sigs[0] for s in sigs)

        if identical_timing and identical_sig:
            verdict = "A_exact_duplicate"
        elif not identical_timing:
            verdict = "B_distinct_trials"
        elif identical_timing and not identical_sig:
            verdict = "UNDETERMINED_same_time_different_events"
        else:
            verdict = "UNDETERMINED"

        for o in occ_summaries:
            del o["_sig"]

        collisions.append({
            "trial_num": tn,
            "n_occurrences": len(occurrences),
            "verdict": verdict,
            "max_onset_separation_s": float(max(onsets) - min(onsets)),
            "event_signatures_identical": bool(identical_sig),
            "occurrences": occ_summaries,
        })

    verdicts = defaultdict(int)
    for c in collisions:
        verdicts[c["verdict"]] += 1

    return {
        "session": stem,
        "n_interval_rows": int(len(start)),
        "n_physical_trial_occurrences": len(runs),
        "n_distinct_trial_num_values": len(by_trialnum),
        "n_trial_nums_with_collisions": len(collisions),
        "verdict_counts": dict(verdicts),
        "max_onset_separation_s": max((c["max_onset_separation_s"] for c in collisions), default=0.0),
        "collisions": collisions,
    }


def main() -> None:
    root = Path(nwb_dir())
    reports = []
    for stem in AFFECTED:
        p = root / f"{stem}.nwb"
        if not p.exists():
            print(f"MISSING {p}")
            continue
        r = analyse(p)
        reports.append(r)
        print(f"\n=== {r['session']} ===")
        print(f"  interval rows: {r['n_interval_rows']}, physical trial occurrences (contiguous "
              f"trial_num runs): {r['n_physical_trial_occurrences']}, distinct trial_num values: "
              f"{r['n_distinct_trial_num_values']}")
        print(f"  trial_nums with >1 occurrence: {r['n_trial_nums_with_collisions']}")
        print(f"  verdicts: {r['verdict_counts']}")
        print(f"  max onset separation: {r['max_onset_separation_s']:.1f}s")
        for c in r["collisions"][:2]:
            print(f"    trial_num={c['trial_num']:.0f} verdict={c['verdict']} "
                  f"sep={c['max_onset_separation_s']:.1f}s sigs_identical={c['event_signatures_identical']}")
            for o in c["occurrences"]:
                print(f"       onset={o['onset_s']:12.3f} rows={o['n_rows']:3d} "
                      f"ids={o['row_id_span']} cond={o['conditions']} correct={o['correct']}")

    total = defaultdict(int)
    for r in reports:
        for k, v in r["verdict_counts"].items():
            total[k] += v
    print(f"\n=== CORPUS VERDICT TOTALS === {dict(total)}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "schema_version": 3,
        "id": "trial-collision-forensics-20260829",
        "kind": "evidence",
        "title": "Are (trial_num, condition) collisions duplicate rows or distinct physical trials?",
        "status": "provisional",
        "question": ("Hamm 2026-08-29: decide A (exact duplicate representation, dedup legitimate) "
                     "vs B (distinct physical trials, old code deleted real data) by comparing full "
                     "event structure, not merely start_time."),
        "method": ("The interval table stores one row per stimulus EVENT, not per trial. A physical "
                   "trial occurrence is a contiguous run of rows sharing a trial_num in time order. "
                   "For each trial_num with >1 such run, compare absolute onset, row-id span, run "
                   "length, and the full ordered event signature (stimulus_number, event_code_type, "
                   "codes, end_code) plus condition/block/correct/is_omission."),
        "nwb_has_no_stable_trial_identifier": ("intervals/omission_glo_passive['id'] is a positional "
                                               "row index 0..n-1 (verified: array_equal to arange), "
                                               "unique per ROW but carrying no physical trial "
                                               "identity, and rows != trials. No semantic trial id "
                                               "exists in the file."),
        "verdict_totals": dict(total),
        "per_session": reports,
    }, indent=2))
    print(f"\nWrote {OUT}")


if __name__ == "__main__":
    main()
