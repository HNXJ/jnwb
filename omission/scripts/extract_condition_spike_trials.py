r"""
Per-trial, per-area binned spike-count (rate) time series, RXRR vs RRRR -- the SPK-SPK input
for fig06's directed connectivity network, matching fig05's LFP-LFP design: same window
(-500..+2593 ms re: p1), same 10 ms bins, same two conditions, same area10 pooling, so a
Granger/TE call on this output is directly comparable to fig05_lfp_lfp_coupling.py's.

WHY POPULATION-POOLED, NOT PER-UNIT
    Matches fig05's node granularity: LFP band power is already a channel-pooled, area-level
    signal, not per-channel. Pooling every unit in an area10 label into one population spike
    train (via jnwb.connectivity.bin_spikes on the concatenated, sorted spike times) keeps the
    node definition identical across the LFP-LFP and SPK-SPK networks -- an area is an area
    either way -- rather than adding a per-unit combinatorial explosion (6000+ units) this
    figure was never scoped for.

QUALITY SCOPE
    All units in omission_grand_units.csv contribute (quality 0 and 1 both), not just the
    "stable" subset -- population rate for a connectivity node is not the same use case as a
    single-unit classification claim, and restricting to quality==1 would silently change area
    coverage (thinner areas losing more units than others) in a way not disclosed if done by
    default. Stated here, not buried.

CONDITIONS / ALIGNMENT
    precompute_condition_onsets(session, correct_only=True) gives p1-onset trial times in
    SECONDS per condition -- identical correct-trials-only, p1-aligned convention every other
    condition-based extraction in this repo uses. RXRR, RRRR only (matches fig05).

OUTPUT
    outputs/condition_spike_trials/trials.npz   one (n_trials, n_bins) float32 rate (Hz) array
        per "session|area10|cond" key, checkpointed after every session
    outputs/condition_spike_trials/index.csv
    outputs/condition_spike_trials/receipt.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import omission as oa  # noqa: E402
from omission.jnwb_ext.unit_classification import precompute_condition_onsets  # noqa: E402
from jnwb.connectivity import bin_spikes  # noqa: E402
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
UNITS_CSV = _P.REPO_ROOT / "outputs/classification/omission_grand_units.csv"
OUT_DIR = _P.REPO_ROOT / "outputs/condition_spike_trials"

WIN_S = (-0.5, 2.593)          # p1 onset to the p3/d3 boundary -- matches fig05's LFP window
BIN_MS = 10.0
CONDS = ["RXRR", "RRRR"]
MIN_UNITS_PER_AREA = 1


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    units = pd.read_csv(UNITS_CSV)
    sessions = sorted(units["session"].unique())
    if limit:
        sessions = sessions[:limit]

    out_arrays, rows, skipped = {}, [], []
    t0 = time.time()
    for si, session in enumerate(sessions, 1):
        # File naming is not uniform across cohorts: C31o/V198o use "..._rec.nwb", V182o uses
        # "....nwb" with no "_rec" suffix -- confirmed by listing D:/analysis/nwb directly
        # (2026-08-04), not assumed. Try both rather than silently skipping half the corpus.
        candidates = [os.path.join(NWB_DIR, f"{session}_rec.nwb"),
                     os.path.join(NWB_DIR, f"{session}.nwb")]
        path = next((p for p in candidates if os.path.exists(p)), None)
        if path is None:
            skipped.append((session, f"no nwb file (tried {candidates})"))
            continue
        try:
            sess = oa.read(path)
        except Exception as e:
            skipped.append((session, f"read failed: {e}"))
            continue
        onsets = precompute_condition_onsets(sess, correct_only=True)

        sess_units = units[units.session == session]
        for area, g in sess_units.groupby("area10"):
            spikes = []
            for unit_row in g["unit_row"]:
                try:
                    st = sess.get_spike_times(int(unit_row))
                except Exception:
                    continue
                if st is not None and len(st) > 0:
                    spikes.append(np.asarray(st, dtype=float))
            if len(spikes) < MIN_UNITS_PER_AREA:
                continue
            pooled = np.sort(np.concatenate(spikes))

            for cond in CONDS:
                trial_starts = onsets.get(cond, np.array([]))
                if len(trial_starts) == 0:
                    continue
                binned = bin_spikes(pooled, window=WIN_S, bin_size_ms=BIN_MS,
                                   trial_starts=trial_starts, output="rate")
                key = f"{session}|{area}|{cond}"
                out_arrays[key] = binned.astype(np.float32)
                rows.append({"key": key, "session": session, "area": area, "cond": cond,
                            "n_trials": binned.shape[0], "n_units": len(spikes)})

        times = WIN_S[0] * 1000.0 + np.arange(round((WIN_S[1] - WIN_S[0]) * 1000.0 / BIN_MS)) * BIN_MS
        np.savez_compressed(os.path.join(OUT_DIR, "trials.npz"), times=times, **out_arrays)
        pd.DataFrame(rows).to_csv(os.path.join(OUT_DIR, "index.csv"), index=False)
        print(f"[{datetime.now():%H:%M:%S}] session {si}/{len(sessions)} ({session}), "
             f"{len(out_arrays)} keys so far, {time.time()-t0:.0f}s", flush=True)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__),
        "purpose": "Per-trial, per-area10 population spike-rate time series, RXRR vs RRRR, "
                  "p1-aligned -- input for fig06's directed SPK-SPK connectivity network.",
        "nwb_dir": NWB_DIR, "units_csv": UNITS_CSV,
        "n_sessions_processed": len(sessions) - len(skipped), "n_sessions_skipped": len(skipped),
        "skipped": skipped, "conditions": CONDS,
        "window_s_re_p1": list(WIN_S), "bin_ms": BIN_MS,
        "quality_scope": "all units (quality 0 and 1 both) -- see module docstring",
        "n_keys": len(out_arrays), "areas": sorted(set(r["area"] for r in rows)),
        "runtime_s": round(time.time() - t0, 1),
        "env": {"python": sys.version.split()[0], "numpy": np.__version__,
               "pandas": pd.__version__},
    }
    with open(os.path.join(OUT_DIR, "receipt.json"), "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2)
    print(f"\nWROTE {OUT_DIR}/trials.npz ({len(out_arrays)} keys), index.csv, receipt.json")
    print(f"areas={receipt['areas']}  runtime={receipt['runtime_s']}s")


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
