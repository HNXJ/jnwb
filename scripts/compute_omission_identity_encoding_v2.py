#!/usr/bin/env python3
r"""
Compute Omission Identity ("what was omitted?") Decoding v2 -- Figure 4 redesign, 2026-08-06.

WHY V2 EXISTS
    v1 (compute_omission_identity_encoding.py) was never run to completion on this corpus --
    confirmed 2026-08-06 by checking for its three output CSVs, none of which existed. The
    figure built from it (fig04_omission_identity_decoding) was rendering 100% synthetic
    fallback content. This script actually runs the analysis, and adds the battery of checks
    requested alongside the promotion: null-stratum calibration, a dual cross-validation
    comparison, a real-vs-confound sanity pass, a pooled mixed-effect model, a shuffle-based
    R^2 CI, a real-stimulus positive control, and an LFP same-channel negative control.

A REAL DESIGN CONSTRAINT THIS SCRIPT WORKS AROUND (found before writing any of this)
    `task_block_number` is PERFECTLY confounded with condition identity in this paradigm --
    verified empirically across 5 sessions: AXAB is always block 2.0, BXBA always block 4.0,
    RXRR always block 5.0, in every session checked, because each condition is presented as
    one whole contiguous block, never interleaved. That makes a literal "block" nuisance
    variable or "leave-one-block-out CV" mathematically degenerate (block IS the label). Per
    explicit direction, every "block"/"sub-block" reference below means a SUB-BLOCK temporal
    quartile split WITHIN each condition's own trial run (by trial order), not
    task_block_number itself. See jnwb/omission_identity.py's module note for the full
    derivation. A positive quartile-decode result is treated as DISQUALIFYING for the identity
    claim (per direction), not just noted.

SCOPE (documented, not hidden)
    The new battery (X|R null stratum, dual CV, sub-block sanity decoding, pooled mixed model,
    R^2 shuffle CI, stim-itself positive control, LFP control) runs at SLOT P2 ONLY, across all
    areas -- P2 is the headline slot and this keeps runtime tractable. The original v1 items
    (slot-by-slot decode at p2/p3/p4, the P2 timecourse sweep, the per-unit "spatial GLMM"
    logistic regression) are kept and run for all three slots as originally scoped, since they
    were never run before either.

OUTPUTS (outputs/classification/)
    omission_identity_decoding_master_v2.csv   -- one row per (session, area, slot): v1-style
                                                   slot decode, now actually computed.
    omission_identity_timecourse_master_v2.csv -- one row per (session, area, time_ms): v1-style
                                                   timecourse, now actually computed.
    omission_identity_glmm_coefficients_v2.csv -- one row per (session, unit): v1-style spatial
                                                   logistic-regression coefficients, now actually
                                                   computed (still NOT a real GLMM -- see README).
    omission_identity_full_battery_p2.csv      -- one row per (session, area): the new battery,
                                                   X|R null stratum, dual CV, quartile sanity.
    omission_identity_stim_control_p1.csv      -- one row per (session, area): AAAB-vs-BBBA
                                                   real-stimulus positive control at p1.
    omission_identity_lfp_control_p2.csv       -- one row per (session, area): same-channel
                                                   low-frequency LFP decode, mean-matched.
    omission_identity_pooled_glmm.json         -- corpus-level pooled mixed model + R^2 CIs.
    receipt.json                               -- provenance: n sessions, runtime, git-visible
                                                   scoping decisions.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import jnwb as oa  # noqa: E402
from jnwb.omission_identity import (  # noqa: E402
    OMISSION_IDENTITY_CONDITIONS,
    build_noise_controlled_spike_matrix,
    build_noise_controlled_spike_matrix_with_subblocks,
    decode_omission_identity_slot,
    decode_omission_identity_full,
    decode_time_from_features,
    shuffle_r2_ci,
    assign_subblock_quartiles,
)
from jnwb import paths as _P

OUT_DIR = REPO_ROOT / "outputs" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)
NWB_DIR = pathlib.Path(_P.nwb_dir())
TFR_DIR = pathlib.Path(_P.tfr_dir())
AREA_VEC_CSV = REPO_ROOT / "outputs" / "channel_area_vector" / "channel_area_vector.csv"

AREAS = ["FEF", "PFC", "TEO", "V4", "V3", "V2", "V1"]

WIN_START, WIN_END, WIN_SIZE, WIN_STEP = -500.0, 4124.0, 100.0, 25.0
TIME_CENTERS = np.arange(WIN_START + WIN_SIZE / 2.0, WIN_END - WIN_SIZE / 2.0 + WIN_STEP, WIN_STEP)

P2_WINDOW_MS = (1031.0, 1562.0)
P1_STIM_WINDOW_MS = (0.0, 531.0)  # real-stimulus response window at p1, matches fig05's stim-window convention
LOW_FREQ_HZ = (4.0, 30.0)  # theta+alpha+beta combined, "low-frequency" per the literal ask

TFR_FREQS_HZ = np.arange(3, 201, 2)
TFR_T0_MS, TFR_BIN_MS, TFR_N_TIMES = -1000.0, 10.0, 500


def _band_slice(lo_hz, hi_hz):
    m = np.where((TFR_FREQS_HZ >= lo_hz) & (TFR_FREQS_HZ < hi_hz))[0]
    return (m[0], m[-1] + 1) if len(m) else (0, 0)


def _time_slice(lo_ms, hi_ms):
    i0 = int(round((lo_ms - TFR_T0_MS) / TFR_BIN_MS))
    i1 = int(round((hi_ms - TFR_T0_MS) / TFR_BIN_MS))
    return max(0, i0), min(TFR_N_TIMES, i1)


_AREA_VEC = None


def _area_vec():
    global _AREA_VEC
    if _AREA_VEC is None:
        _AREA_VEC = pd.read_csv(AREA_VEC_CSV)
    return _AREA_VEC


def lfp_control_for_area(session, stem: str, area: str, unit_ids, epochs_a, epochs_b, epochs_r):
    """Same-channel LFP negative control: pull low-frequency (4-30 Hz) power on the exact
    channels the decoded units sit on (via peak_channel_id -> probe-local channel index,
    verified 2026-08-06 against session.get_electrodes()'s per-probe id ranges and
    channel_area_vector.csv's probe-local 'channel' column), run the identical
    noise-controlled decode. MEAN-MATCH control (per direction): each trial's low-frequency
    power is normalized by that trial's OWN total broadband power (3-200 Hz) on the same
    channel before classification, so a global gain/arousal difference between the A-block
    and B-block cannot masquerade as identity-specific low-frequency decodability -- only the
    RELATIVE low-frequency share of each trial's own power can drive the classifier.
    """
    units_df = session.get_units(area=area)
    units_df = units_df[units_df["unit_id"].isin(unit_ids)]
    if len(units_df) == 0 or "peak_channel_id" not in units_df.columns:
        return {"status": "no_channel_mapping"}

    electrodes = session.get_electrodes()
    probe_offsets = electrodes.index.to_series().groupby(electrodes["probe"]).min()
    probe_letter_of = {}
    for probe_name, offset in probe_offsets.items():
        letter = probe_name.replace("probe", "")[:1].upper()
        probe_letter_of[probe_name] = (letter, int(offset))

    def channel_key(peak_channel_id):
        for probe_name, (letter, offset) in probe_letter_of.items():
            n_on_probe = int((electrodes["probe"] == probe_name).sum())
            if offset <= peak_channel_id < offset + n_on_probe:
                return letter, int(peak_channel_id - offset)
        return None, None

    local_channels_by_probe = {}
    for pcid in units_df["peak_channel_id"].dropna().unique():
        letter, local = channel_key(int(float(pcid)))
        if letter is not None:
            local_channels_by_probe.setdefault(letter, set()).add(local)
    if not local_channels_by_probe:
        return {"status": "no_channel_mapping"}

    f0, f1 = _band_slice(*LOW_FREQ_HZ)
    fb0, fb1 = _band_slice(3, 200)
    t0, t1 = _time_slice(*P2_WINDOW_MS)

    def per_trial_feature(cond_code, probe_letter, chans):
        path = TFR_DIR / f"{stem}-{probe_letter}-{area}-{cond_code}.npy"
        if not path.exists():
            return None
        arr = np.load(path, mmap_mode="r")
        chans = sorted(c for c in chans if c < arr.shape[1])
        if not chans:
            return None
        low = arr[:, chans, f0:f1, t0:t1].mean(axis=(2, 3))
        total = arr[:, chans, fb0:fb1, t0:t1].mean(axis=(2, 3))
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = np.where(total > 0, low / total, np.nan)
        return np.asarray(ratio, dtype=np.float64)

    cond_cfg = OMISSION_IDENTITY_CONDITIONS["p2"]
    feats_a, feats_b = [], []
    for probe_letter, chans in local_channels_by_probe.items():
        fa = per_trial_feature(cond_cfg["A"], probe_letter, chans)
        fb = per_trial_feature(cond_cfg["B"], probe_letter, chans)
        if fa is None or fb is None:
            continue
        feats_a.append(fa)
        feats_b.append(fb)
    if not feats_a:
        return {"status": "no_tfr_array"}

    Xa = np.concatenate(feats_a, axis=1)
    Xb = np.concatenate(feats_b, axis=1)
    Xa = np.nan_to_num(Xa, nan=np.nanmean(Xa) if np.isfinite(np.nanmean(Xa)) else 0.0)
    Xb = np.nan_to_num(Xb, nan=np.nanmean(Xb) if np.isfinite(np.nanmean(Xb)) else 0.0)

    n_min = min(len(Xa), len(Xb))
    if n_min < 6 or Xa.shape[1] < 1:
        return {"status": "insufficient_data", "n_channels": int(Xa.shape[1])}
    rng = np.random.default_rng(42)
    ia = rng.choice(len(Xa), n_min, replace=False)
    ib = rng.choice(len(Xb), n_min, replace=False)
    X = np.concatenate([Xa[ia], Xb[ib]], axis=0)
    y = np.array([0] * n_min + [1] * n_min)

    from sklearn.model_selection import StratifiedKFold
    from sklearn.svm import SVC
    from sklearn.pipeline import Pipeline

    cv = StratifiedKFold(n_splits=min(5, n_min), shuffle=True, random_state=42)
    accs = []
    for tr, te in cv.split(X, y):
        pipe = Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=42))])
        pipe.fit(X[tr], y[tr])
        accs.append(pipe.score(X[te], y[te]))

    rng2 = np.random.default_rng(43)
    perm_accs = []
    for _ in range(100):
        y_perm = rng2.permutation(y)
        p_accs = []
        for tr, te in cv.split(X, y_perm):
            pipe = Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=42))])
            pipe.fit(X[tr], y_perm[tr])
            p_accs.append(pipe.score(X[te], y_perm[te]))
        perm_accs.append(np.mean(p_accs))
    p_val = float(np.mean(np.array(perm_accs) >= np.mean(accs)))
    p_val = p_val if p_val > 0 else 1.0 / 101

    return {
        "status": "success",
        "n_channels": int(X.shape[1]),
        "n_trials": int(len(y)),
        "accuracy": float(np.mean(accs)),
        "p_val": p_val,
        "perm_null_mean": float(np.mean(perm_accs)),
        "chance_baseline": 0.50,
        "feature": "low_freq_power_ratio_4_30Hz_over_3_200Hz_mean_matched",
    }


def _build_matrix_all_units_with_subblocks(session, epochs_cond_a, epochs_cond_b, time_window_ms,
                                            n_quantiles=4, random_state=42):
    """Pooled-across-all-areas variant of build_noise_controlled_spike_matrix_with_subblocks.

    BUG FOUND 2026-08-06: v1's "Spatial GLMM Feature Importance" step called
    build_noise_controlled_spike_matrix(session, "all", ...), which internally calls
    session.get_units(area="all") -- area is compared with `==`, so "all" never matches any
    real area label (V1/V4/FEF/...) and this ALWAYS returned zero units. v1's
    omission_identity_glmm_coefficients.csv would have been empty even if v1 had ever been run
    to completion -- confirmed here by actually running it and finding the file empty. Fixed by
    pooling units directly instead of relying on the area="all" sentinel."""
    n_a, n_b = len(epochs_cond_a), len(epochs_cond_b)
    if n_a == 0 or n_b == 0:
        return np.zeros((0, 0)), np.array([]), [], np.array([])
    q_a_full = assign_subblock_quartiles(epochs_cond_a, n_quantiles)
    q_b_full = assign_subblock_quartiles(epochs_cond_b, n_quantiles)
    n_min = min(n_a, n_b)
    rng = np.random.default_rng(random_state)
    idx_a = rng.choice(n_a, size=n_min, replace=False) if n_a > n_min else np.arange(n_a)
    idx_b = rng.choice(n_b, size=n_min, replace=False) if n_b > n_min else np.arange(n_b)
    sub_a = epochs_cond_a.iloc[idx_a].reset_index(drop=True)
    sub_b = epochs_cond_b.iloc[idx_b].reset_index(drop=True)
    epochs_df = pd.concat([sub_a, sub_b], ignore_index=True)
    labels = np.array([0] * n_min + [1] * n_min)
    quartiles = np.concatenate([q_a_full[idx_a], q_b_full[idx_b]])

    units_df = session.get_units()  # ALL areas, no filter -- the actual fix
    if len(units_df) == 0:
        return np.zeros((len(labels), 0)), labels, [], quartiles
    unit_ids = units_df["unit_id"].tolist()
    n_trials, n_units = len(labels), len(unit_ids)
    X = np.zeros((n_trials, n_units))
    win_sec = (time_window_ms[0] / 1000.0, time_window_ms[1] / 1000.0)
    onsets = epochs_df["start_time"].values
    for j, u_id in enumerate(unit_ids):
        spike_times = session.get_spike_times(u_id)
        if spike_times is None or len(spike_times) == 0:
            continue
        st = np.sort(spike_times)
        for i, onset in enumerate(onsets):
            lo = np.searchsorted(st, onset + win_sec[0], side="left")
            hi = np.searchsorted(st, onset + win_sec[1], side="right")
            X[i, j] = hi - lo
    return X, labels, unit_ids, quartiles


def main(limit=None):
    t0 = time.time()
    nwb_files = sorted(NWB_DIR.glob("*.nwb"))
    if limit:
        nwb_files = nwb_files[:limit]
    print(f"Found {len(nwb_files)} NWB files in {NWB_DIR}.")

    slot_rows, tc_rows, glmm_rows = [], [], []
    battery_rows, stim_rows, lfp_rows = [], [], []

    for f_idx, nwb_path in enumerate(nwb_files, 1):
        stem = nwb_path.stem.replace("_rec", "")
        print(f"[{f_idx}/{len(nwb_files)}] {stem}")
        session = oa.read(nwb_path)

        # --- v1 item 1: slot-by-slot decode, all 3 slots (never run before) ---
        for slot_key, cfg in OMISSION_IDENTITY_CONDITIONS.items():
            win_ms = (cfg["slot_onset_ms"], cfg["slot_end_ms"])
            for area in AREAS:
                res = decode_omission_identity_slot(
                    session=session, area=area, slot_key=slot_key, contrast=("A", "B"),
                    time_window_ms=win_ms, n_splits=5, n_permutations=100, random_state=42)
                res["session"] = stem
                slot_rows.append(res)

        # --- v1 item 2: P2 timecourse (never run before) ---
        epochs_axab = session.get_epochs(condition="AXAB")
        epochs_bxba = session.get_epochs(condition="BXBA")
        for area in AREAS:
            if len(session.get_units(area=area)) < 2:
                continue
            for t_c in TIME_CENTERS:
                X, labels, u_ids = build_noise_controlled_spike_matrix(
                    session, area, epochs_axab, epochs_bxba,
                    (t_c - WIN_SIZE / 2.0, t_c + WIN_SIZE / 2.0), random_state=42)
                if len(u_ids) < 2 or len(labels) < 6:
                    continue
                clf = LogisticRegression(C=1.0, max_iter=200)
                X_s = StandardScaler().fit_transform(X)
                cv_accs = cross_val_score(clf, X_s, labels, cv=3)
                tc_rows.append({"session": stem, "area": area, "time_ms": t_c,
                                 "accuracy": float(np.mean(cv_accs)), "n_units": len(u_ids),
                                 "n_trials": len(labels)})

        # --- v1 item 3: spatial logistic-regression "GLMM" coefficients, WITH the
        #     sub-block quartile added as a nuisance covariate (per direction) ---
        all_units = session.get_units()
        if len(all_units) >= 4 and len(epochs_axab) >= 3 and len(epochs_bxba) >= 3:
            X_all, labels_all, uid_all, q_all = _build_matrix_all_units_with_subblocks(
                session, epochs_axab, epochs_bxba, P2_WINDOW_MS, random_state=42)
            if X_all.shape[1] >= 4:
                X_with_q = np.concatenate([StandardScaler().fit_transform(X_all),
                                            pd.get_dummies(q_all, prefix="q").values.astype(float)], axis=1)
                clf = LogisticRegression(C=1.0, random_state=42, max_iter=500)  # l2 is sklearn's default
                clf.fit(X_with_q, labels_all)
                coefs = clf.coef_[0][: X_all.shape[1]]  # unit coefficients only, block dummies dropped from report
                for u_idx, u_id in enumerate(uid_all):
                    u_row = all_units[all_units["unit_id"] == u_id].iloc[0]
                    glmm_rows.append({
                        "session": stem, "unit_id": u_id, "area": u_row.get("area", "unknown"),
                        "coefficient_beta": float(coefs[u_idx]), "abs_beta": float(np.abs(coefs[u_idx])),
                        "quality": u_row.get("quality", "unknown"),
                        "note": "logistic regression w/ sub-block-quartile nuisance dummies; NOT a mixed model",
                    })

        # --- New battery, P2 only ---
        for area in AREAS:
            res = decode_omission_identity_full(
                session=session, area=area, slot_key="p2", contrast=("A", "B"),
                time_window_ms=P2_WINDOW_MS, n_splits=5, n_permutations=100,
                n_quantiles=4, random_state=42)
            res["session"] = stem
            oof_true, oof_score, oof_q = (res.pop("_oof_true", None), res.pop("_oof_score", None),
                                           res.pop("_oof_quartile", None))
            if oof_true is not None and len(oof_true):
                res["_oof_json"] = json.dumps({"y": oof_true.tolist(), "s": oof_score.tolist(),
                                                "q": oof_q.tolist()})
            battery_rows.append(res)

            # time-decoding sanity check, pooled A+B trials at P2
            epochs_ab_p2 = pd.concat([
                session.get_epochs(phase=2, condition=OMISSION_IDENTITY_CONDITIONS["p2"]["A"]),
                session.get_epochs(phase=2, condition=OMISSION_IDENTITY_CONDITIONS["p2"]["B"])],
                ignore_index=True)
            t_res = decode_time_from_features(session, area, epochs_ab_p2, P2_WINDOW_MS, random_state=42)
            t_res.update({"session": stem, "area": area})
            battery_rows[-1]["time_decode_r2"] = t_res.get("r2_observed", float("nan"))
            battery_rows[-1]["time_decode_r2_ci_lo"] = t_res.get("r2_null_ci_lo", float("nan"))
            battery_rows[-1]["time_decode_r2_ci_hi"] = t_res.get("r2_null_ci_hi", float("nan"))
            battery_rows[-1]["time_decode_p_val"] = t_res.get("p_val", float("nan"))

        # --- Stim-itself positive control: real stimulus at p1, AAAB vs BBBA ---
        epochs_aaab_p1 = session.get_epochs(phase=2, condition="AAAB")
        epochs_bbba_p1 = session.get_epochs(phase=2, condition="BBBA")
        for area in AREAS:
            X, labels, u_ids = build_noise_controlled_spike_matrix(
                session, area, epochs_aaab_p1, epochs_bbba_p1, P1_STIM_WINDOW_MS, random_state=42)
            if len(u_ids) < 2 or len(labels) < 6:
                stim_rows.append({"session": stem, "area": area, "status": "insufficient_data"})
                continue
            from sklearn.model_selection import StratifiedKFold
            from sklearn.svm import SVC
            from sklearn.pipeline import Pipeline
            cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            accs = []
            for tr, te in cv.split(X, labels):
                pipe = Pipeline([("scaler", StandardScaler()), ("clf", SVC(kernel="linear", C=1.0, random_state=42))])
                pipe.fit(X[tr], labels[tr])
                accs.append(pipe.score(X[te], labels[te]))
            stim_rows.append({"session": stem, "area": area, "status": "success",
                               "accuracy": float(np.mean(accs)), "n_units": len(u_ids),
                               "n_trials": len(labels), "chance_baseline": 0.50})

        # --- LFP same-channel control, P2 ---
        for area in AREAS:
            units_df = session.get_units(area=area)
            if len(units_df) < 1:
                continue
            epochs_r_p2 = session.get_epochs(phase=2, condition=OMISSION_IDENTITY_CONDITIONS["p2"]["R"])
            res = lfp_control_for_area(session, stem, area, units_df["unit_id"].tolist(),
                                        epochs_axab, epochs_bxba, epochs_r_p2)
            res.update({"session": stem, "area": area})
            lfp_rows.append(res)

    # --- write per-cell outputs ---
    pd.DataFrame(slot_rows).to_csv(OUT_DIR / "omission_identity_decoding_master_v2.csv", index=False)
    pd.DataFrame(tc_rows).to_csv(OUT_DIR / "omission_identity_timecourse_master_v2.csv", index=False)
    pd.DataFrame(glmm_rows).to_csv(OUT_DIR / "omission_identity_glmm_coefficients_v2.csv", index=False)
    df_battery = pd.DataFrame(battery_rows)
    df_battery.to_csv(OUT_DIR / "omission_identity_full_battery_p2.csv", index=False)
    pd.DataFrame(stim_rows).to_csv(OUT_DIR / "omission_identity_stim_control_p1.csv", index=False)
    pd.DataFrame(lfp_rows).to_csv(OUT_DIR / "omission_identity_lfp_control_p2.csv", index=False)

    # --- pooled mixed model + R^2 CI (corpus level, P2, all successful cells) ---
    pooled_y, pooled_s, pooled_session, pooled_q = [], [], [], []
    for row in battery_rows:
        if row.get("status") != "success" or "_oof_json" not in row:
            continue
        blob = json.loads(row["_oof_json"])
        pooled_y.extend(blob["y"]); pooled_s.extend(blob["s"]); pooled_q.extend(blob["q"])
        pooled_session.extend([row["session"]] * len(blob["y"]))
    pooled_result = {"status": "no_data"}
    if len(pooled_y) >= 20:
        import statsmodels.formula.api as smf
        pooled_df = pd.DataFrame({"y": pooled_y, "score": pooled_s, "session": pooled_session,
                                   "quartile": pooled_q})
        pooled_df["score_z"] = (pooled_df["score"] - pooled_df["score"].mean()) / pooled_df["score"].std()
        try:
            md = smf.mixedlm("score_z ~ C(y) + C(quartile)", pooled_df, groups=pooled_df["session"])
            mdf = md.fit(reml=True)
            r2ci = shuffle_r2_ci(pooled_df["y"].values.astype(float), pooled_df["score"].values,
                                  groups=pooled_df["session"].values, n_shuffle=200, random_state=42)
            pooled_result = {
                "status": "success", "n_trials_pooled": len(pooled_df),
                "n_sessions_pooled": pooled_df["session"].nunique(),
                "label_coef": float(mdf.params.get("C(y)[T.1]", float("nan"))),
                "label_pval": float(mdf.pvalues.get("C(y)[T.1]", float("nan"))),
                "model_summary": mdf.summary().as_text(),
                "r2_shuffle_ci": r2ci,
            }
        except Exception as e:
            pooled_result = {"status": "fit_failed", "error": str(e)}

    receipt = {
        "generated": datetime.now(timezone.utc).isoformat(), "n_sessions": len(nwb_files),
        "runtime_seconds": time.time() - t0,
        "scoping_decisions": [
            "New battery (X|R null stratum, dual CV, sub-block sanity, pooled mixed model, "
            "R2 shuffle CI, stim-itself control, LFP control) scoped to slot P2 only.",
            "'block'/'sub-block' means a within-condition temporal quartile split by trial "
            "order, NOT task_block_number -- task_block_number is perfectly confounded with "
            "condition identity in this design (verified empirically, see module docstring).",
            "Quartile (sub-block) decodability >= identity decodability is treated as "
            "DISQUALIFYING for the identity claim, per explicit direction -- see the pooled "
            "battery CSV's quartile_decode_accuracy column against accuracy_random_cv.",
        ],
    }
    with open(OUT_DIR / "omission_identity_pooled_glmm.json", "w") as fh:
        json.dump(pooled_result, fh, indent=2, default=str)
    with open(OUT_DIR / "receipt.json", "w") as fh:
        json.dump(receipt, fh, indent=2)

    print(f"\nDone in {time.time() - t0:.1f}s. Pooled GLMM status: {pooled_result.get('status')}")


if __name__ == "__main__":
    _limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(limit=_limit)
