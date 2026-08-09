#!/usr/bin/env python3
r"""
Figure 4 v3: cycle-deconfounded omission-identity decoding, 2026-08-06.

WHY V3 EXISTS
    v2 found that identity decoding at P2 did not survive a naive within-condition sub-block
    control, and diagnosed a confound: task_block_number is perfectly aliased with condition
    identity. That diagnosis was INCOMPLETE -- checked directly against trial start_time
    (not just the block-number label) and found each condition (AXAB/BXBA/RXRR, same at p3/p4)
    actually occurs in ~3 temporally separated repeats across the session, not one contiguous
    block. The A-then-B-then-R micro-order is fixed within every repeat (confirmed, no
    exceptions across sessions checked), but the repeats themselves span the whole session.

WHAT THIS SCRIPT ADDS (per direction)
    1. Real cycle detection (jnwb.omission_identity.detect_trial_cycles) instead of an
       artificial within-condition quartile split.
    2. Per-cycle mean-centering of every unit's spike count (A+B+R pooled within a cycle)
       before decoding -- deconfounds a "neuronal fatigue" (monotonic per-cycle level/gain
       shift) explanation directly, leaving only within-cycle relative differences.
    3. Leave-one-cycle-out CV for the 2-way A-vs-B decode on the centered features.
    4. A genuine 3-way (A vs B vs R) confusion-matrix decode, same cycle folds, class-balanced.
       R has no true identity by design -- the diagnostic is whether A/B off-diagonal confusion
       stays low while R does not systematically skew toward either the A or B column.
    5. An AREA-PROFILE dissociation check: does the area ranking of identity-decode accuracy
       track the area ranking of the confound proxies (quartile/time decodability, from the v2
       battery)? If a generic confound explained the effect, area rankings should correlate; if
       genuine content-specific coding is area-selective (e.g. frontal > early visual), the
       rankings should NOT simply track a confound that has no principled reason to be
       area-selective in the first place.

HONEST LIMIT, stated per this project's own doctrine (not hidden): this design rules out a
monotonic whole-session drift and a per-cycle mean/gain shift, but cannot by itself rule out a
fixed, order-locked transient that recurs identically after every block transition regardless
of content, since A always precedes B always precedes R in every cycle, every session (verified
empirically, no exceptions in this corpus).

OUTPUT
    outputs/classification/omission_identity_cycle_deconfound_p2.csv -- one row per
    (session, area): LOCO accuracy on mean-centered features, permutation p, 3-way confusion
    matrix (flattened), n_cycles, n_trials per class.
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb.omission_identity import decode_identity_cycle_deconfound  # noqa: E402
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)
NWB_DIR = pathlib.Path(_P.nwb_dir())
AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]
P2_WINDOW_MS = (1031.0, 1562.0)


def main(limit=None):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files.")

    rows = []
    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)
        for area in AREAS:
            res = decode_identity_cycle_deconfound(
                session=session, area=area, slot_key="p2", contrast=("A", "B"),
                time_window_ms=P2_WINDOW_MS, n_permutations=200, random_state=42)
            res["session"] = stem
            if "confusion_matrix_counts" in res:
                res["confusion_matrix_counts"] = json.dumps(res["confusion_matrix_counts"])
                res["confusion_matrix_row_normalized"] = json.dumps(
                    res["confusion_matrix_row_normalized"])
            rows.append(res)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "omission_identity_cycle_deconfound_p2.csv", index=False)
    ok = df[df.status == "success"]
    print(f"\nDone in {time.time()-t0:.1f}s. {len(ok)}/{len(df)} cells succeeded.")
    if len(ok):
        print("mean LOCO acc (mean-centered):", ok.acc_loco_meancentered.mean().round(3))
        print("n significant (p<0.05):", (ok.p_val_loco < 0.05).sum(), "/", len(ok))


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=_limit)
