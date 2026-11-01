"""Per-session extraction for showcases 1 and 2 (PREREGISTRATION.md).

Usage: python scripts/extract_session.py SESSION_ID [SESSION_ID ...]

For each session writes results/sessions/<ses>/:
  conditions.csv  one row per 4-element sequence: block, context, pattern, P1-P4 onsets,
                  previous pattern, exclusion reason, running speed -1..0 s before P4
  units.csv       every unit with its metrics, area, inclusion and responsiveness
  counts.npz      spike counts of every quality-passing visual-area unit, 10-ms bins,
                  -250..+500 ms around P3 and P4 of every kept sequence: (units, sequences, 75);
                  `responsive` flags the preregistered (visually responsive) units
  session.json    validation, clock check, counts and the receipt
"""
import json
import re
import sys
import time

import numpy as np
import pandas as pd

from glo_common import AREA_RE, DATA, RESULTS, assets, receipt, sha256
import jnwb

WIN = (-0.25, 0.5)
BIN_MS = 10.0
MAIN_SET = {"xxxx", "xxxy"}
SEQ_SET = {"xxxx", "yyyy"}


def merged_overlap(starts, stops, a, b):
    """Boolean per row (a, b): overlaps any interval in (starts, stops)."""
    if len(starts) == 0:
        return np.zeros(len(a), bool)
    return np.array([np.any((starts < y) & (stops > x)) for x, y in zip(a, b)])


def sequences(g):
    """4-row sequences: finite orientation, one block, onset steps 0.9-1.1 s."""
    ori = g["orientation"].to_numpy()
    st = g["start_time"].to_numpy()
    sp = g["stop_time"].to_numpy()
    blk = g["stimulus_block"].to_numpy()
    seqs, run = [], []
    for i in range(len(g)):
        if np.isfinite(ori[i]) and (not run or blk[i] == blk[run[-1]]):
            run.append(i)
            continue
        if run:
            seqs.append(run)
        run = [i] if np.isfinite(ori[i]) else []
    if run:
        seqs.append(run)
    kept, broken = [], 0
    for r in seqs:
        steps = np.diff(st[r])
        if len(r) == 4 and np.all((steps > 0.9) & (steps < 1.1)):
            kept.append(r)
        else:
            broken += 1
    return kept, broken, ori, st, sp, blk


def assign_contexts(block_order, block_sets):
    """Split blocks after the first into main1, random, seq, main2 runs (PREREGISTRATION.md)."""
    ctx = {block_order[0]: "habituation"}
    rest = block_order[1:]
    i = 0
    runs = {"main1": [], "random": [], "seq": [], "main2": []}
    while i < len(rest) and block_sets[rest[i]] <= MAIN_SET:
        runs["main1"].append(rest[i]); i += 1
    while i < len(rest) and not block_sets[rest[i]] <= SEQ_SET:
        runs["random"].append(rest[i]); i += 1
    while i < len(rest) and block_sets[rest[i]] <= SEQ_SET:
        runs["seq"].append(rest[i]); i += 1
    while i < len(rest) and block_sets[rest[i]] <= MAIN_SET:
        runs["main2"].append(rest[i]); i += 1
    ok = i == len(rest) and all(runs.values())
    for name, bl in runs.items():
        for b in bl:
            ctx[b] = name
    return ctx, runs, ok, [int(b) for b in rest[i:]]


def extract(ses, asset):
    path = DATA / asset["path"].split("/")[-1]
    out = RESULTS / "sessions" / ses
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    rec = {"session_id": ses, "asset_id": asset["asset_id"], "asset_path": asset["path"],
           "dandi_sha256": asset["dandi_sha256"]}
    local = sha256(path)
    rec["local_sha256_match"] = local == asset["dandi_sha256"]
    if not rec["local_sha256_match"]:
        raise SystemExit(f"{ses}: local file digest differs from DANDI")
    with jnwb.nwb_read_io(str(path)) as io:
        nwb = io.read()
        rec["subject_id"] = nwb.subject.subject_id
        gt = nwb.intervals["init_grating_presentations"]
        g = pd.DataFrame({c: np.asarray(gt[c].data[:]) for c in ("start_time", "stop_time", "orientation", "stimulus_block")})
        g = g.sort_values("start_time", kind="stable").reset_index(drop=True)
        rf = nwb.intervals.get("create_receptive_field_mapping_presentations") if hasattr(nwb.intervals, "get") else None
        if rf is None and "create_receptive_field_mapping_presentations" in nwb.intervals:
            rf = nwb.intervals["create_receptive_field_mapping_presentations"]
        rf_s = np.asarray(rf["start_time"].data[:]) if rf is not None else np.array([])
        rf_e = np.asarray(rf["stop_time"].data[:]) if rf is not None else np.array([])
        inv = nwb.invalid_times
        if inv is not None and len(inv) > 0:
            iv_s, iv_e = np.asarray(inv["start_time"].data[:]), np.asarray(inv["stop_time"].data[:])
            nz = iv_e > iv_s
            iv_s, iv_e = iv_s[nz], iv_e[nz]
        else:
            iv_s = iv_e = np.array([])
        rec["invalid_times_nonzero"] = int(len(iv_s))
        rec["rf_mapping_rows"] = int(len(rf_s))
        stim_ts = np.asarray(nwb.processing["stimulus"]["timestamps"].timestamps[:])
        run_mod = nwb.processing["running"]["running_speed"]
        run_t = np.asarray(run_mod.timestamps[:])
        run_v = np.asarray(run_mod.data[:], dtype=float)

        # Clock check: grating start_time vs nearest processing/stimulus timestamps.
        idx = np.clip(np.searchsorted(stim_ts, g["start_time"].to_numpy()), 1, len(stim_ts) - 1)
        near = np.minimum(np.abs(stim_ts[idx] - g["start_time"].to_numpy()), np.abs(stim_ts[idx - 1] - g["start_time"].to_numpy()))
        rec["clock_check_ms"] = {"median_abs": float(np.median(near) * 1e3), "p95_abs": float(np.percentile(near, 95) * 1e3),
                                 "max_abs": float(np.max(near) * 1e3), "n_rows": int(len(near))}

        seqs, broken, ori, st, sp, blk = sequences(g)
        rec["n_sequences"], rec["n_broken_runs"] = len(seqs), broken
        first_block = blk[seqs[0][0]]
        hab = [r for r in seqs if blk[r[0]] == first_block]
        p13 = np.array([ori[r[:3]] for r in hab])
        xs, counts = np.unique(p13[:, 0], return_counts=True)
        x = float(xs[np.argmax(counts)])
        rec["x_orientation"] = x
        rec["habituation_p1to3_all_x"] = bool(np.all(p13 == x))
        pat = ["".join("x" if ori[i] == x else "y" for i in r) for r in seqs]
        order = []
        for r in seqs:
            if blk[r[0]] not in order:
                order.append(blk[r[0]])
        sets = {b: set() for b in order}
        for r, p in zip(seqs, pat):
            sets[blk[r[0]]].add(p)
        ctx, runs, ok, leftover = assign_contexts(order, sets)
        rec["context_split_ok"] = bool(ok)
        rec["context_blocks"] = {k: [int(b) for b in v] for k, v in runs.items()}
        rec["unassigned_blocks"] = leftover
        rows = []
        for k, (r, p) in enumerate(zip(seqs, pat)):
            a, b = st[r[0]], sp[r[-1]]
            reason = ""
            if ctx.get(blk[r[0]], "unassigned") == "habituation":
                reason = "habituation"
            elif merged_overlap(rf_s, rf_e, [a], [b])[0]:
                reason = "rf_mapping_overlap"
            elif merged_overlap(iv_s, iv_e, [a], [b])[0]:
                reason = "invalid_times"
            elif blk[r[0]] not in ctx:
                reason = "unassigned_block"
            p4 = st[r[3]]
            m = (run_t >= p4 - 1.0) & (run_t < p4)
            rows.append({"seq": k, "block": int(blk[r[0]]), "context": ctx.get(blk[r[0]], "unassigned"),
                         "pattern": p, "p1": st[r[0]], "p2": st[r[1]], "p3": st[r[2]], "p4": p4,
                         "prev_pattern": pat[k - 1] if k > 0 else "", "excluded": reason,
                         "run_speed_pre_p4": float(np.mean(run_v[m])) if m.any() else np.nan})
        cond = pd.DataFrame(rows)
        cond.to_csv(out / "conditions.csv", index=False)
        kept = cond[cond.excluded == ""]
        tab = kept.groupby(["context", "pattern"]).size().unstack(fill_value=0)
        rec["kept_counts"] = {c: {p: int(v) for p, v in r.items() if v} for c, r in tab.iterrows()}
        rec["excluded_counts"] = cond.excluded.value_counts().to_dict()

        def share(c, p):
            sub = kept[kept.context.isin(c)]
            return float((sub.pattern == p).mean()) if len(sub) else float("nan")

        v = {"main_xxxx_share": share(["main1", "main2"], "xxxx"),
             "random_n_patterns": int(kept[kept.context == "random"].pattern.nunique()),
             "seq_xxxx_share": share(["seq"], "xxxx")}
        v["pass"] = bool(ok and 0.15 <= v["main_xxxx_share"] <= 0.25 and v["random_n_patterns"] >= 8
                         and 0.45 <= v["seq_xxxx_share"] <= 0.55)
        rec["validation"] = v
        rec["clock_pass"] = rec["clock_check_ms"]["median_abs"] <= 10.0

        # Units.
        ut = nwb.units
        cols = ["quality", "presence_ratio", "isi_violations", "amplitude_cutoff", "firing_rate", "peak_channel_id"]
        u = pd.DataFrame({c: np.asarray(ut[c].data[:]) for c in cols})
        u["unit_index"] = np.arange(len(u))
        u["unit_id"] = np.asarray(ut.id.data[:])
        u["quality"] = u["quality"].astype(str)
        el = nwb.electrodes
        loc = pd.Series(np.asarray(el["location"].data[:]).astype(str), index=np.asarray(el.id.data[:]))
        u["location"] = loc.reindex(u["peak_channel_id"]).to_numpy()
        u["area"] = u["location"].astype(str).str.extract(AREA_RE, expand=False)
        eps = np.finfo(float).eps
        crit = {"quality": "good", "presence_ratio": (0.95 + eps, np.inf), "isi_violations": (-np.inf, 0.33 - eps),
                "amplitude_cutoff": (-np.inf, 0.1 - eps), "firing_rate": (0.1 + eps, np.inf)}
        passed = jnwb.filter_by_criteria(u, crit, unknown="raise")
        u["quality_pass"] = u.unit_index.isin(passed.unit_index)
        cand = u[u.quality_pass & u.area.notna()]
        resp_on = cond[(cond.context.isin(["habituation", "main1"])) &
                                     (cond.excluded.isin(["", "habituation"]))]["p1"].to_numpy()
        rec["n_p1_onsets_responsiveness"] = int(len(resp_on))
        u["responsive"] = False
        u["resp_z"] = np.nan
        u["resp_p"] = np.nan
        seq_keep = cond[cond.excluded == ""].reset_index(drop=True)
        onsets = {"p3": seq_keep["p3"].to_numpy(), "p4": seq_keep["p4"].to_numpy()}
        n_bins = int(round((WIN[1] - WIN[0]) * 1000 / BIN_MS))
        inc_idx, counts = [], {e: [] for e in onsets}
        check = []
        for _, row in cand.iterrows():
            spk = jnwb.unit_spike_times(nwb, int(row.unit_index))
            spk = np.sort(spk)
            m = jnwb.compute_response_metrics(spk, resp_on, baseline_window_s=(-0.25, 0.0), response_window_s=(0.05, 0.25))
            c = jnwb.classify_response_significance(m)
            u.loc[row.name, ["resp_z", "resp_p"]] = [m["response_zscore"], c["pvalue"]]
            u.loc[row.name, "responsive"] = bool(c["is_significant"])
            inc_idx.append(int(row.unit_index))  # every quality-passing visual unit; `responsive` flags the preregistered set
            for e, on in onsets.items():
                counts[e].append(jnwb.bin_spikes(spk, window_s=WIN, bin_size_ms=BIN_MS, trial_starts=on, output="count").astype(np.uint16))
            if len(check) < 3:  # rate_in_window equals the binned rate on 50-250 ms
                br = counts["p4"][-1][:, 30:50].sum(axis=1) / 0.2
                rw = np.array([jnwb.rate_in_window(spk, t, (50.0, 250.0)) for t in onsets["p4"]])
                check.append(bool(np.allclose(br, rw, rtol=1e-12, atol=0)))
        rec["rate_in_window_equals_binned"] = check
        u.to_csv(out / "units.csv", index=False)
        inc = u[u.unit_index.isin(inc_idx)].set_index("unit_index").loc[inc_idx]
        np.savez_compressed(out / "counts.npz", unit_index=np.array(inc_idx, int),
                            area=inc["area"].to_numpy().astype(str), responsive=inc["responsive"].to_numpy(bool),
                            seq=seq_keep["seq"].to_numpy(),
                            p3=np.stack(counts["p3"]) if inc_idx else np.zeros((0, len(seq_keep), n_bins), np.uint16),
                            p4=np.stack(counts["p4"]) if inc_idx else np.zeros((0, len(seq_keep), n_bins), np.uint16),
                            bin_ms=BIN_MS, win_s=np.array(WIN))
        rec["units_total"] = int(len(u))
        rec["units_quality_pass"] = int(u.quality_pass.sum())
        rec["units_quality_pass_vis"] = int(len(cand))
        rec["units_included_by_area"] = inc[inc.responsive.astype(bool)]["area"].value_counts().to_dict()
        rec["units_quality_vis_by_area"] = inc["area"].value_counts().to_dict()
    rec["seconds"] = round(time.time() - t0, 1)
    rec = receipt(rec)
    with open(out / "session.json", "w") as f:
        json.dump(rec, f, indent=1, default=str)
    print(ses, "split", rec["context_split_ok"], "valid", rec["validation"]["pass"], "clock_ms", round(rec["clock_check_ms"]["median_abs"], 3),
          "units", rec["units_included_by_area"], rec["seconds"], "s", flush=True)
    return rec


def main():
    a = assets()
    for ses in sys.argv[1:]:
        extract(ses, a[ses])


if __name__ == "__main__":
    main()
