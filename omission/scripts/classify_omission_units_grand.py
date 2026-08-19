r"""
Grand omission unit table: four questions, one pass, permutation-tested and FDR-corrected.

All windows are the 531 ms presentation window at the relevant slot. All tests are two-sided
permutation tests on the trial labels, 1,000 shuffles, seed 42, and every p is corrected
across units with Benjamini-Hochberg (FDR, not FWER) at q <= 0.05 (raised from 0.025
2026-08-13, direct request).

Q1  IS IT AN OMISSION? -- the unit must PEAK (or trough) at the omitted slot
    An omission produces three consecutive, visually identical empty periods: the delay
    before, the omitted slot, and the delay after. A unit is called O+ only if the omitted
    slot exceeds BOTH flanks separately, and O- only if it falls below BOTH. Requiring both
    removes the two confounds that a pooled-flank test cannot:

      monotonic decay   firing falls across the trial, giving pre > slot > post. That passes
                        a pooled-flank test as suppression but fails "below both".
      offset response   the delay after a stimulus carries its offset and sustained activity,
                        elevating the PRE flank. That can pass a pooled test as suppression,
                        or by disinhibition as excitation, but fails "above both".

    Only a genuine peak or trough at the omitted slot satisfies the conjunction.

    NULL: the same three windows are displaced together by D ~ Uniform(100, 200) ms, so the
    null asks what the same contrast looks like when measured slightly later. Displacement is
    forward only, which keeps the comparison inside the post-omission empty period rather than
    sliding back onto the preceding stimulus.

    Rejected alternatives, both recorded because they look reasonable and are not:
      - temporal jitter of +/-200 ms: overlaps its own null by 81 per cent and is blind to
        sustained responses, which is what these units have.
      - the matched full-sequence control at the same slot: that slot CONTAINS a stimulus, so
        the test becomes stimulus-present versus absent and labels every visually driven unit.

Q2  DOES IT KNOW WHEN? (2nd, 3rd or 4th position)
    The omission EFFECT -- slot minus its own flanking delays -- is compared across omitted
    positions. Using the effect rather than the raw rate removes the adaptation gradient,
    because each position is referenced to the delays adjacent to it rather than to the start
    of the trial. Permuting position labels gives the null.

Q3  DOES IT KNOW WHAT? (an omitted A versus an omitted B)
    A-family omissions (AXAB, AAXB, AAAX) against B-family omissions (BXBA, BBXA, BBBX), on
    the same effect measure. In those families the identity of the missing item is determined
    by the block; in the R family it is not, so the same contrast computed within the R family
    is reported alongside as a design control that should be null.

Q4  AFTER-PARTY UNITS (Q+/Q-)
    Does a stimulus that FOLLOWS an omission drive the unit differently from the first
    stimulus of the same trial? Adaptation alone makes later stimuli weaker, so the omission
    trials are compared against the matched control condition by difference in differences:
        (post-omission stimulus - p1) in the omission condition
      - (same slot            - p1) in the matched full-sequence control
    A positive value means the unit recovers or is sensitised after an omission beyond what
    adaptation predicts; that is Q+. Negative is Q-.

OUTPUT
    outputs/classification/omission_grand_units.csv
    outputs/classification/omission_grand_by_area.csv
    outputs/classification/omission_grand_receipt.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy import stats as sst

# _P (jnwb.paths) used to be imported after this insert referenced it -- NameError, fixed
# 2026-08-11 while regenerating this script's output for the v2 criteria addition. Repo root
# is this file's grandparent (scripts/<this file> -> repo root), computed without relying on
# jnwb being importable yet.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import omission as oa
from omission.jnwb_ext.unit_classification import (EPOCH_ONSETS_MS, PRESENTATION_DUR_MS,
                                      precompute_condition_onsets)
from jnwb import paths as _P

NWB_DIR = _P.nwb_dir()
OUT_DIR = _P.REPO_ROOT / "outputs/classification"
N_SHUF = 1000
ALPHA = 0.05  # raised from 0.025 2026-08-13, direct request (Hamm) -- corpus-wide, every
             # omission_class/knows_when/knows_what/after_class consumer is affected
NBINS = 6
MIN_TR = 6
POOL = {"V3": "V3a/d", "V3a": "V3a/d", "V3d": "V3a/d"}
STIM_MS, DELAY_MS = PRESENTATION_DUR_MS, 500.0

# v2 "omission reporter" criteria (added 2026-08-11, requested directly by Hamm, see
# artifacts/.lab/fig03-omission-reporter-v2-criteria-20260811.json). A new, additional
# classification alongside the original Q1 omission_class -- NOT a replacement. Landed as
# omission_class_v2 so the two populations can be compared before anything downstream
# (fig02's O++ exemplar pick, fig03 itself, any GLMM using omission_class) switches over.
#
# O+v2: at some point after the onset of the omitted slot p_x, up to the end of the following
#   delay d_x, firing is significantly higher than the mean rate of the PRECEDING delay
#   d_(x-1). "At some point" = the max over NBINS2 sub-windows spanning [p_x onset, d_x end]
#   (peak_rate), tested against mean_rate(d_(x-1)) with a forward-displacement permutation
#   null (same displacement philosophy as the original Q1: displace forward only, so the null
#   stays inside the post-omission empty period rather than sliding onto the real stimulus).
# O++v2: O+v2 AND ALSO that same peak is significantly higher than the peak of every OTHER
#   epoch in the trial (p1-p4, d1-d4, excluding p_x, d_x themselves AND d_(x-1), which O+v2
#   already tests) -- a single test against whichever competing epoch had the highest peak
#   that trial, not a corrected conjunction across all of them. This is the "unit reliably
#   behaves as if it is an omission reporter" property: the omission-window peak has to beat
#   the trial's own best real-stimulus response, not just its immediate neighbors.
OMIT_WIN_DUR_S = (STIM_MS + DELAY_MS) / 1000.0    # p_x onset -> d_x end, 1031 ms
NBINS2 = 12                                        # ~86 ms bins, matching NBINS=6/531ms density
EPOCH_ORDER_NO_FX = ("p1", "d1", "p2", "d2", "p3", "d3", "p4", "d4")

# omission condition -> (omitted slot, family, matched full-sequence control)
OMISSIONS = {"AXAB": (2, "A", "AAAB"), "AAXB": (3, "A", "AAAB"), "AAAX": (4, "A", "AAAB"),
             "BXBA": (2, "B", "BBBA"), "BBXA": (3, "B", "BBBA"), "BBBX": (4, "B", "BBBA"),
             "RXRR": (2, "R", "RRRR"), "RRXR": (3, "R", "RRRR"), "RRRX": (4, "R", "RRRR")}
DUR = PRESENTATION_DUR_MS / 1000.0


def bh(p):
    """Benjamini-Hochberg FDR, delegating to jnwb.StatisticalAnalysis.fdr_correct (scipy
    false_discovery_control). Was a local re-implementation with a backwards rank divisor
    (np.arange(n, 0, -1) instead of np.arange(1, n+1)) that silently under-corrected every
    q-value in this file's output until fixed 2026-08-14 -- see
    artifacts/.lab/bh-fdr-backwards-divisor-fix-20260814.json."""
    p = np.asarray(p, float)
    ok = np.isfinite(p)
    q = np.full(p.shape, np.nan)
    v = p[ok]
    if v.size == 0:
        return q
    q[ok] = oa.StatisticalAnalysis.fdr_correct(v)
    return q


def perm_p(obs, null):
    return (1.0 + np.sum(np.abs(null) >= abs(obs))) / (len(null) + 1.0)


def peak_rate(st, onsets, win_dur_s, nbins):
    """Per-trial PEAK rate: max over `nbins` sub-windows spanning [onset, onset+win_dur_s)."""
    if len(onsets) == 0:
        return np.zeros(0)
    edges = np.linspace(0.0, win_dur_s, nbins + 1)
    e = np.asarray(onsets)[:, None] + edges[None, :]
    c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=1).astype(float)
    bin_dur = win_dur_s / nbins
    return (c / bin_dur).max(axis=1)


def mean_rate(st, onsets, win_dur_s):
    """Per-trial MEAN rate over the whole [onset, onset+win_dur_s) window."""
    if len(onsets) == 0:
        return np.zeros(0)
    e = np.stack([np.asarray(onsets), np.asarray(onsets) + win_dur_s], axis=1)
    c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=1).astype(float)[:, 0]
    return c / win_dur_s


def displaced_peak_rate(st, onsets, D_arr, win_dur_s, nbins):
    """(N_SHUF, n_trials) peak rate for windows onset+D, D varying per shuffle."""
    edges = np.linspace(0.0, win_dur_s, nbins + 1)
    e = onsets[None, :, None] + D_arr[:, None, None] + edges[None, None, :]
    c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=-1).astype(float)
    bin_dur = win_dur_s / nbins
    return (c / bin_dur).max(axis=-1)


def displaced_mean_rate(st, onsets, D_arr, win_dur_s):
    """(N_SHUF, n_trials) mean rate for windows onset+D, D varying per shuffle."""
    e = onsets[None, :, None] + D_arr[:, None, None] + np.array([0.0, win_dur_s])[None, None, :]
    c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=-1).astype(float)[..., 0]
    return c / win_dur_s


def rates(st, onsets, edges, x, denom):
    """Per-trial rate and within-window slope for a set of window onsets."""
    if len(onsets) == 0:
        return np.zeros(0), np.zeros(0)
    e = np.asarray(onsets)[:, None] + edges[None, :]
    c = np.diff(np.searchsorted(st, e.ravel()).reshape(e.shape), axis=1).astype(float)
    r = c.sum(axis=1) / DUR
    s = ((c - c.mean(axis=1, keepdims=True)) @ x) / denom if denom > 0 else np.zeros(len(c))
    return r, s


def analyse(path, rng, rng_v2):
    sess = oa.read(str(path))
    on = precompute_condition_onsets(sess, correct_only=True)
    try:
        udf = sess.get_units()
    except Exception:
        udf = getattr(sess, "units", None)
    if udf is None or len(udf) == 0:
        return []

    edges = np.linspace(0.0, DUR, NBINS + 1)
    ctr = (edges[:-1] + edges[1:]) / 2.0
    x = ctr - ctr.mean()
    denom = (x ** 2).sum()

    # per omission condition: slot onsets, flank onsets, p1 onsets, post-omission stim onsets
    W = {}
    for cond, (slot, fam, ctrl) in OMISSIONS.items():
        t = on.get(cond)
        if t is None or len(t) == 0:
            continue
        t = np.asarray(t, float)
        p_on = EPOCH_ONSETS_MS[f"p{slot}"] / 1000.0
        pre = EPOCH_ONSETS_MS[f"d{slot - 1}"] / 1000.0
        post = EPOCH_ONSETS_MS[f"d{slot}"] / 1000.0
        nxt = slot + 1
        W[cond] = {
            "slot": t + p_on, "flank": np.concatenate([t + pre, t + post]),
            "pre": t + pre, "post": t + post,
            "p1": t + EPOCH_ONSETS_MS["p1"] / 1000.0, "fam": fam, "pos": slot,
            "post_stim": (t + EPOCH_ONSETS_MS[f"p{nxt}"] / 1000.0) if nxt <= 4 else None,
            "ctrl": ctrl, "ctrl_pos": nxt if nxt <= 4 else None,
        }
    if not W:
        return []
    ctrl_on = {c: np.asarray(on.get(c, []), float) for c in ("AAAB", "BBBA", "RRRR")}

    stem = os.path.basename(path).replace("_rec.nwb", "").replace(".nwb", "")
    out = []
    for ridx in range(len(udf)):
        try:
            st = np.sort(np.asarray(sess.get_spike_times(ridx), float))
        except Exception:
            continue
        if st.size < 2:
            continue
        m = udf.iloc[ridx]
        rec = {"session": stem, "unit_row": ridx, "unit_id": m.get("unit_id", ridx),
               "area": m.get("area"), "quality": m.get("quality"),
               "firing_rate": m.get("firing_rate"),
               "waveform_duration": m.get("waveform_duration"),
               "peak_channel_id": m.get("peak_channel_id"),
               "local_channel": m.get("local_channel"), "probe_id": m.get("probe_id")}

        # ---- per-condition effect: slot minus its own flanks -----------------------
        eff, slp, nsl = {}, {}, {}
        pooled_slot, pooled_flank = [], []
        for cond, w in W.items():
            rs, ss = rates(st, w["slot"], edges, x, denom)
            rf, sf = rates(st, w["flank"], edges, x, denom)
            if rs.size < MIN_TR or rf.size < MIN_TR:
                continue
            eff[cond] = rs.mean() - rf.mean()
            slp[cond] = ss.mean() - sf.mean()
            nsl[cond] = rs.size
            pooled_slot.append(rs)
            pooled_flank.append(rf)
        if not eff:
            continue

        # ---- Q1: does the unit peak (or trough) AT the omitted slot -----------------
        slot_r, pre_r, post_r, slot_s, pre_s, post_s = [], [], [], [], [], []
        for cond in eff:
            w = W[cond]
            rs, ss = rates(st, w["slot"], edges, x, denom)
            rp, sp = rates(st, w["pre"], edges, x, denom)
            rq, sq = rates(st, w["post"], edges, x, denom)
            n = min(rs.size, rp.size, rq.size)
            slot_r.append(rs[:n]); pre_r.append(rp[:n]); post_r.append(rq[:n])
            slot_s.append(ss[:n]); pre_s.append(sp[:n]); post_s.append(sq[:n])
        slot_r = np.concatenate(slot_r); pre_r = np.concatenate(pre_r)
        post_r = np.concatenate(post_r); slot_s = np.concatenate(slot_s)
        obs_pre = float(slot_r.mean() - pre_r.mean())
        obs_post = float(slot_r.mean() - post_r.mean())

        # null: displace all three windows together by D ~ U(100, 200) ms
        Ds = rng.uniform(0.100, 0.200, size=N_SHUF)
        s_on = np.concatenate([W[c]["slot"] for c in eff])
        p_on_ = np.concatenate([W[c]["pre"] for c in eff])
        q_on = np.concatenate([W[c]["post"] for c in eff])

        def disp(onsets):
            """(N_SHUF, n_trials, nbins) counts for windows displaced by each D at once."""
            e = onsets[None, :, None] + Ds[:, None, None] + edges[None, None, :]
            idx = np.searchsorted(st, e.ravel()).reshape(e.shape)
            return np.diff(idx, axis=-1).astype(float)

        cs, cp, cq = disp(s_on), disp(p_on_), disp(q_on)
        rs_ = cs.sum(axis=-1).mean(axis=1) / DUR
        rp_ = cp.sum(axis=-1).mean(axis=1) / DUR
        rq_ = cq.sum(axis=-1).mean(axis=1) / DUR
        npre = rs_ - rp_
        npost = rs_ - rq_
        nslope = (((cs - cs.mean(axis=-1, keepdims=True)) @ x) / denom).mean(axis=1)             if denom > 0 else np.zeros(N_SHUF)
        rec["q1_vs_pre_hz"] = obs_pre
        rec["q1_vs_post_hz"] = obs_post
        rec["q1_pre_p"] = perm_p(obs_pre, npre)
        rec["q1_post_p"] = perm_p(obs_post, npost)
        rec["q1_effect_hz"] = float(slot_r.mean() - 0.5 * (pre_r.mean() + post_r.mean()))
        rec["q1_p"] = max(rec["q1_pre_p"], rec["q1_post_p"])   # conjunction: the weaker leg
        rec["q1_slope_effect"] = float(slot_s.mean())
        rec["q1_ramp_p"] = perm_p(rec["q1_slope_effect"], nslope)

        # ---- v2: "omission reporter" criteria (see module docstring / constants above) -----
        peak_omit_pool, mean_pre_pool, best_competitor_pool = [], [], []
        for cond in eff:
            w = W[cond]
            slot = w["pos"]
            t_cond = w["p1"]  # raw trial-onset array for this condition (p1 onset, offset 0)
            pk_omit = peak_rate(st, w["slot"], OMIT_WIN_DUR_S, NBINS2)
            mn_pre = mean_rate(st, w["pre"], DELAY_MS / 1000.0)
            other_epochs = [e for e in EPOCH_ORDER_NO_FX
                            if e not in (f"p{slot}", f"d{slot}", f"d{slot - 1}")]
            competitor_peaks = []
            for ep in other_epochs:
                dur = (STIM_MS if ep.startswith("p") else DELAY_MS) / 1000.0
                onsets_ep = t_cond + EPOCH_ONSETS_MS[ep] / 1000.0
                competitor_peaks.append(peak_rate(st, onsets_ep, dur, NBINS))
            n2 = min([pk_omit.size, mn_pre.size] + [c.size for c in competitor_peaks])
            if n2 < MIN_TR:
                continue
            best_comp = np.max(np.stack([c[:n2] for c in competitor_peaks]), axis=0)
            peak_omit_pool.append(pk_omit[:n2])
            mean_pre_pool.append(mn_pre[:n2])
            best_competitor_pool.append(best_comp)

        if peak_omit_pool:
            peak_omit_pool = np.concatenate(peak_omit_pool)
            mean_pre_pool = np.concatenate(mean_pre_pool)
            best_competitor_pool = np.concatenate(best_competitor_pool)

            omit_on_all = np.concatenate([W[c]["slot"] for c in eff
                                          if W[c]["slot"].size >= MIN_TR])
            pre_on_all = np.concatenate([W[c]["pre"] for c in eff
                                         if W[c]["pre"].size >= MIN_TR])

            obs_v2_pre = float(peak_omit_pool.mean() - mean_pre_pool.mean())
            obs_v2_all = float(peak_omit_pool.mean() - best_competitor_pool.mean())

            # O+v2 null: displace BOTH the omission window and the preceding-delay window
            # together, forward only (same philosophy as Q1's own displacement null).
            # Independent stream (rng_v2), not the shared `rng` the original Q1-Q4 tests use --
            # drawing from `rng` here would shift every downstream permutation-null draw for
            # this unit and every unit/file processed afterward, silently perturbing v1's
            # results as a side effect of v2 code existing (found 2026-08-11 when the 22-session
            # rerun's v1 omission_class counts moved from the pre-v2 baseline; see
            # artifacts/.lab/fig03-omission-reporter-v2-criteria-20260811.json).
            Ds2 = rng_v2.uniform(0.100, 0.200, size=N_SHUF)
            npk_omit = displaced_peak_rate(st, omit_on_all, Ds2, OMIT_WIN_DUR_S, NBINS2)
            npre = displaced_mean_rate(st, pre_on_all, Ds2, DELAY_MS / 1000.0)
            null_v2_pre = npk_omit.mean(axis=1) - npre.mean(axis=1)
            rec["q1v2_omit_peak_hz"] = float(peak_omit_pool.mean())
            rec["q1v2_vs_pre_hz"] = obs_v2_pre
            rec["q1v2_vs_pre_p"] = perm_p(obs_v2_pre, null_v2_pre)

            # O++v2 null: displace only the omission-window peak; competitor epochs are real,
            # stimulus-locked events elsewhere in the trial and are not displaced.
            null_v2_all = npk_omit.mean(axis=1) - best_competitor_pool.mean()
            rec["q1v2_vs_all_hz"] = obs_v2_all
            rec["q1v2_vs_all_p"] = perm_p(obs_v2_all, null_v2_all)
        else:
            rec["q1v2_omit_peak_hz"] = np.nan
            rec["q1v2_vs_pre_hz"] = np.nan
            rec["q1v2_vs_pre_p"] = np.nan
            rec["q1v2_vs_all_hz"] = np.nan
            rec["q1v2_vs_all_p"] = np.nan

        # ---- Q2: does it know WHEN (position 2 vs 3 vs 4) ---------------------------
        pos_vals, pos_lab = [], []
        for cond, w in W.items():
            if cond in eff:
                pos_vals.append(eff[cond])
                pos_lab.append(w["pos"])
        rec["q2_n_positions"] = len(set(pos_lab))
        if len(set(pos_lab)) >= 2:
            pv = np.array(pos_vals)
            pl = np.array(pos_lab)
            obs = float(np.nanmax([pv[pl == p].mean() for p in set(pl)]) -
                        np.nanmin([pv[pl == p].mean() for p in set(pl)]))
            nn = np.empty(N_SHUF)
            for i in range(N_SHUF):
                s = rng.permutation(pl)
                nn[i] = (np.nanmax([pv[s == p].mean() for p in set(pl)]) -
                         np.nanmin([pv[s == p].mean() for p in set(pl)]))
            rec["q2_range_hz"] = obs
            rec["q2_p"] = (1.0 + np.sum(nn >= obs)) / (N_SHUF + 1.0)
            rec["q2_best_position"] = int(max(set(pl), key=lambda p: pv[pl == p].mean()))
        else:
            rec["q2_range_hz"] = np.nan
            rec["q2_p"] = np.nan
            rec["q2_best_position"] = np.nan

        # ---- Q3: does it know WHAT (omitted A vs omitted B), R as design control ----
        def fam_effect(f):
            v = [eff[c] for c in eff if W[c]["fam"] == f]
            return float(np.mean(v)) if v else np.nan
        eA, eB, eR = fam_effect("A"), fam_effect("B"), fam_effect("R")
        aslots = bslots = np.zeros(0)
        rec["q3_A_effect_hz"], rec["q3_B_effect_hz"], rec["q3_R_effect_hz"] = eA, eB, eR
        def fam_trial_effects(f):
            """Per-trial (slot - its own two flanks), so any orientation-selective carry-over
            from the surrounding stimuli is present in both terms and cancels."""
            v = []
            for c in eff:
                if W[c]["fam"] != f:
                    continue
                rs, _ = rates(st, W[c]["slot"], edges, x, denom)
                n = rs.size
                rf, _ = rates(st, W[c]["flank"], edges, x, denom)
                if rf.size == 2 * n:
                    v.append(rs - 0.5 * (rf[:n] + rf[n:]))
            return np.concatenate(v) if v else np.zeros(0)

        if np.isfinite(eA) and np.isfinite(eB):
            aslots = fam_trial_effects("A")
            bslots = fam_trial_effects("B")
        if aslots.size >= MIN_TR and bslots.size >= MIN_TR:
            ab = np.concatenate([aslots, bslots])
            ii = np.array([rng.permutation(ab.size) for _ in range(N_SHUF)])
            nab = ab[ii][:, :aslots.size].mean(axis=1) - ab[ii][:, aslots.size:].mean(axis=1)
            rec["q3_AB_diff_hz"] = float(aslots.mean() - bslots.mean())
            rec["q3_p"] = perm_p(rec["q3_AB_diff_hz"], nab)
        else:
            rec["q3_AB_diff_hz"] = np.nan
            rec["q3_p"] = np.nan

        # ---- Q4: after-party, difference in differences -----------------------------
        dd, ddn = [], 0
        for cond, w in W.items():
            if w["post_stim"] is None or cond not in eff:
                continue
            co = ctrl_on.get(w["ctrl"])
            if co is None or co.size < MIN_TR:
                continue
            ro, _ = rates(st, w["post_stim"], edges, x, denom)
            r1, _ = rates(st, w["p1"], edges, x, denom)
            cp = co + EPOCH_ONSETS_MS[f"p{w['ctrl_pos']}"] / 1000.0
            c1 = co + EPOCH_ONSETS_MS["p1"] / 1000.0
            rc, _ = rates(st, cp, edges, x, denom)
            rc1, _ = rates(st, c1, edges, x, denom)
            if min(ro.size, r1.size, rc.size, rc1.size) < MIN_TR:
                continue
            dd.append((ro.mean() - r1.mean()) - (rc.mean() - rc1.mean()))
            ddn += ro.size
        if dd:
            rec["q4_dd_hz"] = float(np.mean(dd))
            # null: permute omission and control trial labels within each contributing pair
            nn = np.empty(N_SHUF)
            pool = []
            for cond, w in W.items():
                if w["post_stim"] is None or cond not in eff:
                    continue
                co = ctrl_on.get(w["ctrl"])
                if co is None or co.size < MIN_TR:
                    continue
                ro, _ = rates(st, w["post_stim"], edges, x, denom)
                r1, _ = rates(st, w["p1"], edges, x, denom)
                rc, _ = rates(st, co + EPOCH_ONSETS_MS[f"p{w['ctrl_pos']}"] / 1000.0,
                              edges, x, denom)
                rc1, _ = rates(st, co + EPOCH_ONSETS_MS["p1"] / 1000.0, edges, x, denom)
                if min(ro.size, r1.size, rc.size, rc1.size) < MIN_TR:
                    continue
                pool.append((ro - r1.mean(), rc - rc1.mean()))
            for i in range(N_SHUF):
                v = []
                for a_, b_ in pool:
                    z = np.concatenate([a_, b_])
                    z = z[rng.permutation(z.size)]
                    v.append(z[:a_.size].mean() - z[a_.size:].mean())
                nn[i] = np.mean(v)
            rec["q4_p"] = perm_p(rec["q4_dd_hz"], nn)
            rec["q4_n_trials"] = ddn
        else:
            rec["q4_dd_hz"] = np.nan
            rec["q4_p"] = np.nan
            rec["q4_n_trials"] = 0
        out.append(rec)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    os.makedirs(OUT_DIR, exist_ok=True)
    rng = np.random.default_rng(42)
    # Independent stream for the v2 "omission reporter" test (added 2026-08-11) -- must never
    # share `rng` with the original Q1-Q4 tests, or v2's draws silently shift v1's results.
    rng_v2 = np.random.default_rng(43)
    files = sorted(f for f in os.listdir(NWB_DIR) if f.endswith(".nwb"))
    if args.limit:
        files = files[: args.limit]

    t0 = time.time()
    rows, failed = [], []
    for i, f in enumerate(files, 1):
        try:
            r = analyse(os.path.join(NWB_DIR, f), rng, rng_v2)
            rows += r
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: {len(r)} units "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:
            failed.append({"file": f, "error": f"{type(e).__name__}: {e}"})
            print(f"[{datetime.now():%H:%M:%S}] {i}/{len(files)} {f}: FAILED {e}", flush=True)

    df = pd.DataFrame(rows)
    if df.empty:
        print("no units")
        return
    for k in ["q1", "q1_ramp", "q2", "q3", "q4"]:
        col = f"{k}_p" if k != "q1_ramp" else "q1_ramp_p"
        df[col.replace("_p", "_q")] = bh(df[col].values)
    df["area10"] = df.area.replace(POOL)
    df["animal"] = df.session.str.split("_").str[0].str.replace("sub-", "", regex=False)

    # conjunction: significant against BOTH flanks, and in the same direction against both
    up = (df.q1_q <= ALPHA) & (df.q1_vs_pre_hz > 0) & (df.q1_vs_post_hz > 0)
    dn = (df.q1_q <= ALPHA) & (df.q1_vs_pre_hz < 0) & (df.q1_vs_post_hz < 0)
    rup = (df.q1_ramp_q <= ALPHA) & (df.q1_slope_effect > 0)
    rdn = (df.q1_ramp_q <= ALPHA) & (df.q1_slope_effect < 0)
    df["omission_class"] = np.where(up & rup, "O++", np.where(dn & rdn, "O--",
                            np.where(up, "O+", np.where(dn, "O-", "ns"))))

    # v2 "omission reporter" criteria -- BH-FDR corrected separately from the original Q1
    # family (its own family, per the multiplicity doctrine: this is a different question
    # asked of the same units, not a sub-test of Q1). Additional column, does not touch
    # omission_class. See module docstring above and
    # artifacts/.lab/fig03-omission-reporter-v2-criteria-20260811.json.
    df["q1v2_vs_pre_q"] = bh(df["q1v2_vs_pre_p"].values)
    df["q1v2_vs_all_q"] = bh(df["q1v2_vs_all_p"].values)
    v2_plus = (df.q1v2_vs_pre_q <= ALPHA) & (df.q1v2_vs_pre_hz > 0)
    v2_plusplus = v2_plus & (df.q1v2_vs_all_q <= ALPHA) & (df.q1v2_vs_all_hz > 0)
    df["omission_class_v2"] = np.where(v2_plusplus, "O++", np.where(v2_plus, "O+", "ns"))

    df["knows_when"] = df.q2_q <= ALPHA
    df["knows_what"] = df.q3_q <= ALPHA
    df["after_class"] = np.where((df.q4_q <= ALPHA) & (df.q4_dd_hz > 0), "Q+",
                         np.where((df.q4_q <= ALPHA) & (df.q4_dd_hz < 0), "Q-", "ns"))
    df.to_csv(os.path.join(OUT_DIR, "omission_grand_units.csv"), index=False)

    rows2 = []
    for a, g in df.groupby("area10"):
        n = len(g)
        rec = {"area": a, "screened": n}
        for c in ["O++", "O+", "O-", "O--"]:
            rec[c] = int((g.omission_class == c).sum())
        for c in ["O++", "O+"]:
            rec[f"{c}_v2"] = int((g.omission_class_v2 == c).sum())
        rec["knows_when"] = int(g.knows_when.sum())
        rec["knows_what"] = int(g.knows_what.sum())
        rec["Q+"] = int((g.after_class == "Q+").sum())
        rec["Q-"] = int((g.after_class == "Q-").sum())
        rows2.append(rec)
    by = pd.DataFrame(rows2)
    by.to_csv(os.path.join(OUT_DIR, "omission_grand_by_area.csv"), index=False)

    receipt = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "script": os.path.abspath(__file__), "n_shuffles": N_SHUF, "seed": 42,
        "alpha_fdr": ALPHA, "two_sided": True,
        "questions": {
            "q1": "the unit must peak or trough AT the omitted slot: significant against "
                  "BOTH flanking delays and in the same direction against both, with the null "
                  "displacing all three windows by D ~ U(100, 200) ms. Removes monotonic "
                  "decay and stimulus-offset confounds, which a pooled-flank test admits.",
            "q2": "does the omission effect differ across omitted position 2/3/4",
            "q3": "omitted-A vs omitted-B; R family reported as a design control",
            "q4": "difference in differences, post-omission stimulus vs p1, omission minus "
                  "matched control; Q+ recovers or sensitises beyond adaptation, Q- the opposite",
            "q1v2_omission_reporter": "ADDITIONAL, separate from q1/omission_class (added "
                "2026-08-11, requested directly by Hamm). O+v2: peak rate (max over 12 "
                "sub-windows) anywhere in [p_x onset, d_x end] is significantly higher than "
                "the mean rate of the preceding delay d_(x-1). O++v2: O+v2 AND that same peak "
                "is significantly higher than the peak of every other trial epoch (p1-p4, "
                "d1-d4, excluding p_x/d_x/d_(x-1)) via a single test against whichever "
                "competing epoch had the highest peak that trial -- 'behaves as if it is an "
                "omission reporter'. Own BH-FDR family, separate from q1's. See "
                "artifacts/.lab/fig03-omission-reporter-v2-criteria-20260811.json.",
        },
        "rejected_designs": {
            "temporal_jitter_200ms": "81 per cent window overlap; blind to sustained responses",
            "control_slot_same_position": "that slot contains a stimulus, so the test becomes "
                                          "stimulus present vs absent",
        },
        "n_units": int(len(df)), "n_sessions": int(df.session.nunique()),
        "counts": {k: int(v) for k, v in df.omission_class.value_counts().items()},
        "counts_v2": {k: int(v) for k, v in df.omission_class_v2.value_counts().items()},
        "v1_vs_v2_crosstab": {
            f"{a}->{b}": int(n) for (a, b), n in
            df.groupby(["omission_class", "omission_class_v2"]).size().items()
        },
        "knows_when": int(df.knows_when.sum()), "knows_what": int(df.knows_what.sum()),
        "after_counts": {k: int(v) for k, v in df.after_class.value_counts().items()},
        "failures": failed[:10], "runtime_s": round(time.time() - t0, 1),
        "env": {"python": platform.python_version(), "numpy": np.__version__},
    }
    json.dump(receipt, open(os.path.join(OUT_DIR, "omission_grand_receipt.json"), "w",
                            encoding="utf-8"), indent=2)
    print(f"\nunits {len(df):,} | " + " ".join(f"{k}={v}" for k, v in receipt["counts"].items()))
    print(f"knows_when {receipt['knows_when']} | knows_what {receipt['knows_what']} | "
          f"after {receipt['after_counts']}")
    print(by.to_string(index=False))


if __name__ == "__main__":
    main()
